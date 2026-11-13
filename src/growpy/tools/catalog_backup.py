"""Back up the tree catalog to the lab share (owner, 2026-11-13).

The catalog lives in the UE project (no version control) and its skeletons in growpy
``data/output`` (gitignored); both sit on one local disk. This mirrors, under
``<share>/tree_catalog/``:

* ``XRFF_Twin/Content/Generated/Trees/``: the catalog itself (graphs, meshes, twigs,
  materials);
* ``growpy/data/output/forest/``: per species the ``r??`` ladders the catalog is built
  from (growth JSONs, TAMF, icons) without the USD exports and without the plan's
  ``.carve``/``.floor`` copies (``growpy-pve-plan`` rewrites them), plus every
  ``unreal_scripts*`` plan folder;
* ``growpy/data/input/materials/``: the bark intake (its texture maps are not in git).

Twig assets (``data/assets``) are left out: they are rebuilt from the twig sources.
Incremental: a file is copied when it is missing on the share or differs in size or
modification time; nothing is deleted on the share. Writes ``MANIFEST_keep.csv``
(path, bytes, sha256, mtime). Run after each finished species and at each release.

    python -m growpy.tools.catalog_backup [--dry-run] [--project D:/Unreal/XRFF_Twin]
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SHARE = Path(
    r"\\unfnrd02.public.ads.uni-freiburg.de\unfnrd04\UNFN_XRLab\40_SideProjects"
    r"\tree_catalog"
)
PROJECT = Path("D:/Unreal/XRFF_Twin")
LADDER = re.compile(r"^[a-z_]+/r\d\d/[^/]+$")
PLAN_COPY = re.compile(r"_full_growth_data\.\w+\.json$")


def keep_forest(rel: str) -> bool:
    """Catalog ladders (no USD, no plan copies), species info and plan folders."""
    if rel.startswith("unreal_scripts"):
        return True
    if rel.endswith("/species_info.json") and rel.count("/") == 1:
        return True
    return (
        bool(LADDER.match(rel))
        and not rel.endswith(".usda")
        and not PLAN_COPY.search(rel)
    )


def sources(project: Path) -> list[tuple[Path, str, Callable[[str], bool]]]:
    """(source root, path under the share, keep(relative posix path))."""
    return [
        (
            project / "Content/Generated/Trees",
            "XRFF_Twin/Content/Generated/Trees",
            lambda r: True,
        ),
        (REPO / "data/output/forest", "growpy/data/output/forest", keep_forest),
        (REPO / "data/input/materials", "growpy/data/input/materials", lambda r: True),
    ]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def backup(srcs, dst: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """Mirror the kept files to dst; returns (kept, copied, bytes copied)."""
    manifest = dst / "MANIFEST_keep.csv"
    old = {}
    if manifest.exists():
        with manifest.open(encoding="utf-8") as fh:
            old = {r["path"]: r for r in csv.DictReader(fh)}
    rows, n_copy, b_copy = [], 0, 0
    for root, sub, keep in srcs:
        for here, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                src = Path(here) / name
                rel = src.relative_to(root).as_posix()
                if not keep(rel):
                    continue
                st = src.stat()
                key = f"{sub}/{rel}"
                out = dst / key
                same = (
                    out.exists()
                    and out.stat().st_size == st.st_size
                    and int(out.stat().st_mtime) == int(st.st_mtime)
                )
                if not same:
                    n_copy += 1
                    b_copy += st.st_size
                    if not dry_run:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, out)
                prev = old.get(key)
                unchanged = (
                    prev
                    and same
                    and int(prev["bytes"]) == st.st_size
                    and prev["mtime"] == str(int(st.st_mtime))
                )
                digest = (
                    prev["sha256"] if unchanged else ("" if dry_run else sha256(src))
                )
                rows.append(
                    {
                        "path": key,
                        "bytes": st.st_size,
                        "sha256": digest,
                        "mtime": int(st.st_mtime),
                    }
                )
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
        with manifest.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "bytes", "sha256", "mtime"])
            w.writeheader()
            w.writerows(rows)
    return len(rows), n_copy, b_copy


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--project", type=Path, default=PROJECT, help="UE project folder")
    ap.add_argument("--share", type=Path, default=SHARE)
    a = ap.parse_args(argv)
    t0 = time.time()
    kept, copied, size = backup(sources(a.project), a.share, a.dry_run)
    dry = " (dry run)" if a.dry_run else ""
    print(
        f"{kept} files kept; {copied} copied ({size / 1e9:.1f} GB), "
        f"{(time.time() - t0) / 60:.1f} min -> {a.share}{dry}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
