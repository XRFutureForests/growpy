"""Self-contained server for the expert tree survey: the static page plus one answer endpoint.

    python survey_server.py                      # http://localhost:8080/, answers in ./answers
    python survey_server.py --port 8090 --data /media/data/xrff-survey

Standard library only, so it runs in any Python 3.10+ (conda env, container, laptop).

- ``GET /...``            files from ``--site`` (the page, ``items.json``, ``img/``)
- ``POST /api/answers``   one respondent's whole session (the page's state object); written
                          to ``<data>/<survey>/<session>.json``, replacing the previous save of
                          that session, so a respondent who resumes keeps one file
- ``GET /api/health``     ``{"ok": true, "answers": <files>}``

Answers are never served back. Limits keep a public endpoint from filling the disk: body
<= 512 KiB, a JSON object with the configured survey id and a short alphanumeric session id,
at most ``--max-files`` sessions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSION = re.compile(r"^[a-z0-9]{6,40}$")
MAX_BODY = 512 * 1024


class Handler(SimpleHTTPRequestHandler):
    survey_id: str
    data_dir: Path
    max_files: int

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _answer_dir(self) -> Path:
        return self.data_dir / self.survey_id

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self.path.split("?")[0] == "/api/health":
            d = self._answer_dir()
            n = len(list(d.glob("*.json"))) if d.exists() else 0
            return self._json(HTTPStatus.OK, {"ok": True, "survey": self.survey_id, "answers": n})
        if self.path.startswith("/api/"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/api/answers":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body size"})
        try:
            doc = json.loads(self.rfile.read(length))
        except ValueError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "not JSON"})
        if not isinstance(doc, dict) or doc.get("survey") != self.survey_id:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "unknown survey"})
        session = str(doc.get("session", ""))
        if not SESSION.match(session) or not isinstance(doc.get("answers"), dict):
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad session"})
        d = self._answer_dir()
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{session}.json"
        if not target.exists() and len(list(d.glob("*.json"))) >= self.max_files:
            return self._json(HTTPStatus.INSUFFICIENT_STORAGE, {"error": "survey full"})
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        os.chmod(tmp, 0o644)  # mkstemp makes 0600; the host admin copies the files as another uid
        os.replace(tmp, target)
        return self._json(HTTPStatus.OK, {"ok": True})

    def end_headers(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")  # a re-deploy shows at once
        super().end_headers()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--site", type=Path, default=Path(os.environ.get("SURVEY_SITE", HERE / "site")))
    p.add_argument("--data", type=Path, default=Path(os.environ.get("SURVEY_DATA", HERE / "answers")))
    p.add_argument("--survey", default=os.environ.get("SURVEY_ID", "tree-architecture-2026-10"))
    p.add_argument("--host", default=os.environ.get("SURVEY_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("SURVEY_PORT", 8080)))
    p.add_argument("--max-files", type=int, default=2000)
    a = p.parse_args()
    Handler.survey_id, Handler.data_dir, Handler.max_files = a.survey, a.data, a.max_files
    server = ThreadingHTTPServer((a.host, a.port), partial(Handler, directory=str(a.site)))
    print(f"survey {a.survey}: http://{a.host}:{a.port}/  answers -> {a.data}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
