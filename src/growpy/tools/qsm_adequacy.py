"""Adequacy checks for the gate's core descriptors (``growpy.structure.adequacy``).

    growpy-qsm-adequacy <real descriptors.csv> [...] --out-dir <dir>
    growpy-qsm-adequacy <...> --out-dir <dir> --arm baseline=<gate.csv> --arm btm0.1=<gate.csv>

Writes ``adequacy.csv`` (species effect, height tracking and source effect per
descriptor), ``candidates.csv`` (eligible descriptors with redundancy pruning) and, with
two or more ``--arm`` gate tables (the first is the baseline), ``sensitivity.csv``
(generated-median shift per arm in real IQRs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from growpy.structure.adequacy import adequacy, candidates, sensitivity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("descriptors", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--arm", action="append", default=[], metavar="NAME=GATE_CSV", help="sweep arm"
    )
    args = parser.parse_args(argv)
    real = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in args.descriptors], ignore_index=True
    )
    real = real[real["source_kind"] == "scan"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    adeq = adequacy(real)
    adeq.to_csv(args.out_dir / "adequacy.csv", index=False, float_format="%.4g")
    cand = candidates(adeq, real)
    cand.to_csv(args.out_dir / "candidates.csv", index=False, float_format="%.4g")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 50)
    cols = ["descriptor", "species_eps2", "height_rho_beech", "source_eps2_beech",
            "source_eps2_ash", "redundant_with", "meaning"]  # fmt: skip
    print(
        f"{int(adeq['eligible'].sum())} eligible of {len(adeq)}, "
        f"{int(cand['kept'].sum())} after redundancy pruning"
    )
    print(cand[cols].round(3).to_string(index=False))
    if len(args.arm) >= 2:
        arms = {}
        for item in args.arm:
            name, _, path = item.partition("=")
            arms[name] = pd.read_csv(path)
        sens = sensitivity(arms, next(iter(arms)))
        sens.to_csv(args.out_dir / "sensitivity.csv", index=False, float_format="%.3f")
    print(f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
