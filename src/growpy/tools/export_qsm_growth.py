"""Write growth JSONs from a standardised QSM dataset, so real trees go through the same
tools as Grove trees (``growpy-structure-descriptors``, the PVE exporter).

    growpy-qsm-export-growth data/tmp/qsm_standardized/belgium --out-dir real/belgium
    growpy-qsm-export-growth <dataset> --out-dir <dir> --species-key scots_pine --tier B
    growpy-qsm-export-growth <dataset> --out-dir <dir> --species-key norway_spruce --limit 50
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from growpy.structure.growth_json import to_growth_json
from growpy.structure.store import iter_trees


def _safe(uid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", uid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "dataset", type=Path, help="a growpy-qsm-standardize output folder"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--species-key", help="only this growpy species key")
    parser.add_argument("--tier", help="only this quality tier (A, B or C)")
    parser.add_argument("--limit", type=int, help="stop after this many trees")
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for tree in iter_trees(args.dataset):
        meta = tree.meta
        if args.species_key and meta.get("species_key") != args.species_key:
            continue
        if args.tier and meta.get("tier") != args.tier:
            continue
        out = args.out_dir / f"{_safe(meta['tree_uid'])}_growth_data.json"
        out.write_text(json.dumps(to_growth_json(tree.cyl)), encoding="utf-8")
        written += 1
        if args.limit and written >= args.limit:
            break
    print(f"{written} growth JSONs -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
