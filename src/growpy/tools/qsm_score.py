"""Score the catalog against real trees per species (``growpy.structure.score``).

    growpy-qsm-score <descriptors.csv> [<descriptors.csv> ...] --out-dir <dir>
    growpy-qsm-score <...> --out-dir <dir> --top 12 --form

Concatenates ``growpy-qsm-descriptors`` tables (generated and real trees), compares each
generated species with its reference species (silver fir and Douglas fir with Norway
spruce, flagged as a proxy) and writes:

    gaps_by_species.csv     one row per species x height class x descriptor (compare)
    descriptor_gaps.csv     robust, conifer-safe descriptors per species, sorted by |z|
    species_summary.csv     share within one spread (|robust z| < 1) per species
    form_table.csv          (--form) visible-trait medians, generated / real, 10-30 m

The 2026-10-26 re-score is ``growpy-qsm-score <growpy+belgium+kew>/descriptors.csv
<biodiv tier A>/descriptors.csv``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from growpy.structure.score import (
    descriptor_gaps,
    form_table,
    score_cells,
    species_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("descriptors", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--min-real", type=int, default=5, help="real trees a cell needs"
    )
    parser.add_argument("--top", type=int, default=8, help="gaps printed per species")
    parser.add_argument("--form", action="store_true", help="also write form_table.csv")
    args = parser.parse_args(argv)
    table = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in args.descriptors], ignore_index=True
    )
    cells = score_cells(table, args.min_real)
    if cells.empty:
        print("nothing to score: no generated species with a real reference")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cells.to_csv(args.out_dir / "gaps_by_species.csv", index=False)
    gaps = descriptor_gaps(cells)
    gaps.to_csv(args.out_dir / "descriptor_gaps.csv", index=False)
    summary = species_summary(cells)
    summary.to_csv(
        args.out_dir / "species_summary.csv", index=False, float_format="%.3f"
    )
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 48)
    print(summary.round(2).to_string(index=False))
    for species, g in gaps.groupby("species_key"):
        print(f"\n{species}:")
        print(
            g.head(args.top)[
                ["descriptor", "cells", "z_med", "real_med", "gen_med", "desc"]
            ]
            .round(3)
            .to_string(index=False)
        )
    if args.form:
        form = form_table(table)
        form.to_csv(args.out_dir / "form_table.csv")
        print("\n" + form.to_string())
    print(f"\n-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
