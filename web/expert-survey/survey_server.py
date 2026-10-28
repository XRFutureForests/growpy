"""Self-contained server for the tree look survey (XRFF-593): the page, one tree card at a
time, and the votes.

    python survey_server.py                       # http://localhost:8080/, votes in ./answers
    python survey_server.py --keys abc123,def456  # invitation keys (env SURVEY_KEYS)

Standard library only, so it runs in any Python 3.10+ (conda env, container, laptop).

- ``GET /``                          the page (``--site``)
- ``GET /img/<id>/<front|side>.png`` a card drawing from the item store (``--items``)
- ``GET /api/next?d=<device>&k=<key>``  the next card for this device: the species with the
  fewest votes so far, within it the kind (real / generated) with fewer votes, within that the
  tree with the fewest votes; never a tree this device has rated. ``{"done": true}`` when the
  device has rated them all
- ``POST /api/vote``   ``{d, k, id, rating 1-5, ms, pos, role, side}`` -> the source of the
  tree (its ``reveal``), only now; a device rates a tree once
- ``POST /api/flags``  ``{d, k, id, flags: [...]}`` "what looked off", for a tree the device rated
- ``GET /api/health``  ``{"ok": true, "items": n, "votes": n}``

The item store is written by ``add_items.py``; the server rereads ``manifest.jsonl`` when it
changes, so new trees go live without a restart. ``meta.json`` is never served. Votes are
appended to ``<data>/<survey>/votes.jsonl`` (one JSON record per line) and read back at start.
No accounts: a device is a random id the page keeps in the browser.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
from collections import defaultdict
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
DEVICE = re.compile(r"^[a-z0-9]{8,40}$")
ITEM = re.compile(r"^[0-9a-f]{10}$")
IMG = re.compile(r"^/img/([0-9a-f]{10})/(front|side)\.png$")
FLAGS = {"angles", "lengths", "regular", "drooping", "stem", "crown", "density", "artefact"}
ROLES = {"student", "practitioner", "researcher", "other"}
MAX_BODY = 4096
MAX_VOTES = 500_000


class State:
    """Items from the manifest, vote counts and per-device history, behind one lock."""

    def __init__(self, items_dir: Path, votes_file: Path):
        self.lock = threading.Lock()
        self.items_dir, self.votes_file = items_dir, votes_file
        self.items: dict[str, dict] = {}
        self.manifest_mtime = -1.0
        self.n_votes = 0
        self.item_votes: dict[str, int] = defaultdict(int)
        self.seen: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)  # device -> id -> (kind, rating)
        self._reload()
        if votes_file.exists():
            for line in votes_file.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("type") == "vote":
                    self._count(rec["d"], rec["id"], rec["kind"], rec["rating"])

    def _reload(self) -> None:
        manifest = self.items_dir / "manifest.jsonl"
        mtime = manifest.stat().st_mtime if manifest.exists() else 0.0
        if mtime == self.manifest_mtime:
            return
        items = {}
        if manifest.exists():
            for line in manifest.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    m = json.loads(line)
                    items[m["id"]] = m  # a later line for the same id (e.g. active: false) wins
        self.items, self.manifest_mtime = {k: v for k, v in items.items() if v.get("active", True)}, mtime

    def _count(self, device: str, item_id: str, kind: str, rating: int) -> None:
        self.n_votes += 1
        self.item_votes[item_id] += 1
        self.seen[device][item_id] = (kind, rating)

    def next_card(self, device: str) -> dict | None:
        with self.lock:
            self._reload()
            open_ = [m for i, m in self.items.items() if i not in self.seen[device]]
            if not open_:
                return None
            sp_votes, kind_votes = defaultdict(int), defaultdict(int)
            for i, n in self.item_votes.items():
                if i in self.items:
                    sp_votes[self.items[i]["species_key"]] += n
                    kind_votes[(self.items[i]["species_key"], self.items[i]["kind"])] += n

            def least(cands, key):
                low = min(key(m) for m in cands)
                return [m for m in cands if key(m) == low]

            open_ = least(open_, lambda m: sp_votes[m["species_key"]])
            sp = random.choice(open_)["species_key"]
            open_ = least([m for m in open_ if m["species_key"] == sp], lambda m: kind_votes[(sp, m["kind"])])
            m = random.choice(least(open_, lambda m: self.item_votes[m["id"]]))
            return {"id": m["id"], "species": m["species"], "species_key": m["species_key"],
                    "height_m": m["height_m"], "setting": m["setting"],
                    "front": f"img/{m['id']}/front.png", "side": f"img/{m['id']}/side.png"}

    def vote(self, rec: dict) -> dict:
        with self.lock:
            m = self.items.get(rec["id"])
            if m is None:
                raise KeyError("unknown item")
            if rec["id"] in self.seen[rec["d"]]:
                raise ValueError("already rated")
            if self.n_votes >= MAX_VOTES:
                raise OverflowError("survey full")
            rec |= {"type": "vote", "ts": _now(), "kind": m["kind"], "species_key": m["species_key"], "group": m["group"]}
            self._append(rec)
            self._count(rec["d"], rec["id"], m["kind"], rec["rating"])
            return {"reveal": m["reveal"], "kind": m["kind"], "you": self._score(rec["d"])}

    def flags(self, rec: dict) -> None:
        with self.lock:
            if rec["id"] not in self.seen[rec["d"]]:
                raise ValueError("rate the tree first")
            self._append(rec | {"type": "flags", "ts": _now()})

    def _score(self, device: str) -> dict:
        """Calls that matched the truth: real rated 4-5, generated rated 1-2 (3 is no call)."""
        done = self.seen[device].values()
        calls = [(k, r) for k, r in done if r != 3]
        hits = sum((k == "real") == (r >= 4) for k, r in calls)
        return {"rated": len(done), "calls": len(calls), "matched": hits}

    def _append(self, rec: dict) -> None:
        self.votes_file.parent.mkdir(parents=True, exist_ok=True)
        new = not self.votes_file.exists()
        with self.votes_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if new:
            os.chmod(self.votes_file, 0o644)  # the host admin copies the file as another uid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Handler(SimpleHTTPRequestHandler):
    state: State
    keys: set[str]

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _allowed(self, key: str) -> bool:
        return not self.keys or key in self.keys

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        url = urlsplit(self.path)
        if url.path == "/api/health":
            return self._json(HTTPStatus.OK, {"ok": True, "items": len(self.state.items), "votes": self.state.n_votes})
        if url.path == "/api/next":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if not self._allowed(q.get("k", "")):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "invitation key"})
            if not DEVICE.match(q.get("d", "")):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "device"})
            card = self.state.next_card(q["d"])
            return self._json(HTTPStatus.OK, card or {"done": True})
        if url.path.startswith("/api/"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        img = IMG.match(url.path)
        if img:
            f = self.state.items_dir / img[1] / f"{img[2]}.png"
            if img[1] not in self.state.items or not f.exists():
                return self.send_error(HTTPStatus.NOT_FOUND)
            raw = f.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        if url.path not in ("/", "/index.html"):
            return self.send_error(HTTPStatus.NOT_FOUND)  # the page is the only static file
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path not in ("/api/vote", "/api/flags"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body size"})
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "not JSON"})
        if not self._allowed(str(body.get("k", ""))):
            return self._json(HTTPStatus.FORBIDDEN, {"error": "invitation key"})
        d, item = str(body.get("d", "")), str(body.get("id", ""))
        if not DEVICE.match(d) or not ITEM.match(item):
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "device or item"})
        try:
            if path == "/api/flags":
                flags = sorted(set(map(str, body.get("flags") or [])) & FLAGS)
                self.state.flags({"d": d, "id": item, "flags": flags})
                return self._json(HTTPStatus.OK, {"ok": True})
            rating = body.get("rating")
            if not isinstance(rating, int) or not 1 <= rating <= 5:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "rating"})
            role = body.get("role") if body.get("role") in ROLES else None
            rec = {"d": d, "id": item, "rating": rating, "role": role, "side": bool(body.get("side")),
                   "ms": int(body.get("ms") or 0), "pos": int(body.get("pos") or 0)}
            return self._json(HTTPStatus.OK, self.state.vote(rec))
        except KeyError:
            return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown item"})
        except ValueError as e:
            return self._json(HTTPStatus.CONFLICT, {"error": str(e)})
        except OverflowError:
            return self._json(HTTPStatus.INSUFFICIENT_STORAGE, {"error": "survey full"})

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # keep invitation keys out of the log
        super().log_message(fmt, *(re.sub(r"k=[^&\s]*", "k=…", a) if isinstance(a, str) else a for a in args))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--site", type=Path, default=Path(os.environ.get("SURVEY_SITE", HERE / "site")))
    p.add_argument("--items", type=Path, default=Path(os.environ.get("SURVEY_ITEMS", HERE / "items")))
    p.add_argument("--data", type=Path, default=Path(os.environ.get("SURVEY_DATA", HERE / "answers")))
    p.add_argument("--survey", default=os.environ.get("SURVEY_ID", "tree-look-2026-10"))
    p.add_argument("--keys", default=os.environ.get("SURVEY_KEYS", ""), help="comma-separated; empty = open")
    p.add_argument("--host", default=os.environ.get("SURVEY_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("SURVEY_PORT", 8080)))
    a = p.parse_args()
    Handler.state = State(a.items, a.data / a.survey / "votes.jsonl")
    Handler.keys = {k.strip() for k in a.keys.split(",") if k.strip()}
    server = ThreadingHTTPServer((a.host, a.port), partial(Handler, directory=str(a.site)))
    print(f"survey {a.survey}: http://{a.host}:{a.port}/  {len(Handler.state.items)} items, "
          f"{Handler.state.n_votes} votes, {'invitation only' if Handler.keys else 'open'}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
