"""Compare generated trees with real ones, descriptor by descriptor (``growpy.structure.compare``).

    growpy-qsm-compare <descriptors.csv> --out-dir <dir>

Writes ``generated_vs_real.csv`` (one row per species x height class x descriptor: real
quantiles, generated median, percentile, robust z, Cliff's delta, Mann-Whitney p with a
Benjamini-Hochberg FDR) and ``descriptor_gaps.csv`` (per descriptor, across cells, sorted
by how far generated trees sit from real ones).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from growpy.structure.compare import compare, gaps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "descriptors", type=Path, help="growpy-qsm-descriptors descriptors.csv"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--min-real", type=int, default=5, help="real trees a cell needs"
    )
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cells = compare(pd.read_csv(args.descriptors), args.min_real)
    cells.to_csv(
        args.out_dir / "generated_vs_real.csv", index=False, float_format="%.4g"
    )
    summary = gaps(cells)
    summary.to_csv(
        args.out_dir / "descriptor_gaps.csv", index=False, float_format="%.3g"
    )
    print(
        f"{len(cells)} cell x descriptor rows, {len(summary)} descriptors -> {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
