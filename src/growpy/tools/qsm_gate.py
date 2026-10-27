"""Gate generated trees against the real reference store (``growpy.structure.gate``).

    growpy-qsm-gate <descriptors.csv> [<descriptors.csv> ...] --out-dir <dir>
    growpy-qsm-gate <...> --out-dir <dir> --reference data/input/structure_reference

Scores the generated rows of ``growpy-qsm-descriptors`` tables. Score unthinned growth
JSONs only (``export_mode = "growth_json_only"`` with ``min_branch_radius_fraction`` 0):
the export cuts bias lateral lengths up and conifer crown ratios down. Writes:

    gate.csv          species x height bin x descriptor: inside p5-p95, median in IQR,
                      IQR ratio, too-regular flag, pass, core
    verdict.csv       species x height bin over the core descriptors
    consistency.csv   growth over time per grown individual (height, DBH, crown base,
                      trunk), when the table carries height-stage snapshots
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from growpy.structure.gate import gate, growth_consistency, verdict
from growpy.structure.reference import load_core_set, load_reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("descriptors", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, default=None, help="store dir (default: committed)"
    )
    args = parser.parse_args(argv)
    table = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in args.descriptors], ignore_index=True
    )
    gated = gate(table, load_reference(args.reference), load_core_set(args.reference))
    if gated.empty:
        print("nothing gated: no generated species with a reference row")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    gated.to_csv(args.out_dir / "gate.csv", index=False, float_format="%.4g")
    v = verdict(gated)
    v.to_csv(args.out_dir / "verdict.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(v.drop(columns="failing").to_string(index=False))
    if {"source_tree_id", "trunk_length_m"} <= set(table.columns):
        cons = growth_consistency(table)
        if len(cons):
            cons.to_csv(
                args.out_dir / "consistency.csv", index=False, float_format="%.3f"
            )
            print(
                f"\ngrowth over time: {int(cons['consistent'].sum())} of {len(cons)} "
                "individuals consistent"
            )
    print(f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
