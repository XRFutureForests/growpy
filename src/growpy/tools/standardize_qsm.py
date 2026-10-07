"""Standardise a published QSM dataset into the canonical cylinder + tree tables.

    growpy-qsm-standardize kew data/input/reference_qsm/kew_wakehurst --out-dir data/output/qsm/kew
    growpy-qsm-standardize belgium data/input/reference_qsm/belgium_beech_pine_ash_larch --out-dir ...
    growpy-qsm-standardize biodiv <QSM/corrected dir> --labels <labels.csv> --out-dir ...
    growpy-qsm-standardize biodiv-graphs <graph dir> --labels <labels.csv> --out-dir ...

Writes ``trees.csv``, ``cylinders.csv.gz`` and ``schema.json`` (see ``growpy.structure.store``).
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

from growpy.structure import sources
from growpy.structure.store import write_dataset

DATASET_SOURCES = {
    "kew": sources.kew,
    "belgium": sources.belgium,
    "ghent": sources.ghent,
    "treeml": sources.treeml,
    "growpy-forest": sources.growpy_forest,
}
LABELLED_SOURCES = {"biodiv": sources.biodiv, "biodiv-graphs": sources.biodiv_graphs}
SOURCES = (*DATASET_SOURCES, *LABELLED_SOURCES)


def _trees(args):
    if args.source in DATASET_SOURCES:
        return DATASET_SOURCES[args.source](args.input)
    if not args.labels:
        raise SystemExit(f"{args.source} needs --labels labels.csv")
    return LABELLED_SOURCES[args.source](args.input, args.labels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", choices=SOURCES)
    parser.add_argument(
        "input", type=Path, help="the dataset folder (graph folder for biodiv-graphs)"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, help="BioDiv labels.csv")
    parser.add_argument("--limit", type=int, help="stop after this many trees")
    args = parser.parse_args(argv)
    trees = _trees(args)
    if args.limit:
        trees = itertools.islice(trees, args.limit)
    count = write_dataset(trees, args.out_dir)
    print(f"{count} trees -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
