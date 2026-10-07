"""Structure descriptors for standardised QSM datasets, real and generated alike.

    growpy-qsm-descriptors <dataset> [<dataset> ...] --out-dir <dir>
    growpy-qsm-descriptors <...> --out-dir <dir> --species-key european_beech --tier A

Writes ``descriptors.csv`` (one row per tree: identity, species, size, every descriptor),
``descriptor_definitions.csv`` (unit, frame and scan robustness per descriptor) and
``descriptor_summary.csv`` (median, p10, p90 and n per source kind x species x height
class), so a generated cell can be read next to the real trees of its species and size.

Every tree is cut to the same resolution first, by branch length and order rather than
radius (radius means different things per source): laterals shorter than ``--min-length``
(default 0.3 m: beech and pine QSMs resolve branches down to about 0.1-0.2 m) go with
their subtrees, and axes above ``--max-order`` (default 2) go. ``--min-radius`` stays
available but is off by default.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from growpy.structure.descriptors import DEFINITIONS, definitions_table, describe
from growpy.structure.store import iter_trees

IDENTITY = [
    "tree_uid",
    "source",
    "source_kind",
    "tier",
    "plot",
    "species_latin",
    "species_key",
    "leaf_type",
    "growth_form",
    "valid_qsm",
    "height_m",
    "dbh_m",
]


def height_class(height: float, edges: list[float]) -> str:
    for lo, hi in zip(edges, edges[1:], strict=False):
        if lo <= height < hi:
            return f"h{lo:g}-{hi:g}"
    return f"h{edges[-1]:g}+"


def summarise(table: pd.DataFrame) -> pd.DataFrame:
    keys = ["source_kind", "species_key", "height_class"]
    rows = []
    for group, frame in table.groupby(keys, dropna=False):
        for key in DEFINITIONS:
            values = frame[key].dropna()
            if values.empty:
                continue
            rows.append(
                {
                    **dict(zip(keys, group, strict=True)),
                    "descriptor": key,
                    "n": len(values),
                    "p10": values.quantile(0.1),
                    "median": values.median(),
                    "p90": values.quantile(0.9),
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "datasets", nargs="+", type=Path, help="growpy-qsm-standardize outputs"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--min-radius", type=float, default=0.0, help="metres (default 0: off)"
    )
    parser.add_argument(
        "--min-length", type=float, default=0.3, help="metres (default 0.3)"
    )
    parser.add_argument(
        "--max-order",
        type=int,
        default=2,
        help="drop axes above this order (default 2)",
    )
    parser.add_argument("--species-key", help="only this growpy species key")
    parser.add_argument("--tier", help="only this quality tier")
    parser.add_argument("--limit", type=int, help="at most this many trees per dataset")
    parser.add_argument(
        "--height-classes",
        default="0,10,20,30,60",
        help="class edges in metres (default 0,10,20,30,60)",
    )
    args = parser.parse_args(argv)
    edges = [float(x) for x in args.height_classes.split(",")]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for dataset in args.datasets:
        done = 0
        for tree in iter_trees(dataset):
            meta = tree.meta
            if args.species_key and meta.get("species_key") != args.species_key:
                continue
            if args.tier and meta.get("tier") != args.tier:
                continue
            try:
                values = describe(
                    tree.cyl, args.min_radius, args.max_order, args.min_length
                )
            except Exception as exc:  # noqa: BLE001 - one odd tree must not end the run
                print(f"skip {meta['tree_uid']}: {exc}", file=sys.stderr)
                continue
            row = {k: meta.get(k) for k in IDENTITY}
            row["height_class"] = height_class(float(meta["height_m"]), edges)
            row.update(values)
            rows.append(row)
            done += 1
            if args.limit and done >= args.limit:
                break
        print(f"{dataset.name}: {done} trees")
    table = pd.DataFrame(rows)
    table.to_csv(args.out_dir / "descriptors.csv", index=False, float_format="%.4g")
    definitions_table().to_csv(args.out_dir / "descriptor_definitions.csv", index=False)
    summary = summarise(table) if len(table) else pd.DataFrame()
    summary.to_csv(
        args.out_dir / "descriptor_summary.csv", index=False, float_format="%.4g"
    )
    print(f"{len(table)} trees, {len(summary)} summary rows -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
