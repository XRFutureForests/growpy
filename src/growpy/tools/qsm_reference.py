"""Build the committed real-tree reference store (``growpy.structure.reference``).

    growpy-qsm-reference <descriptors.csv> [<descriptors.csv> ...]
    growpy-qsm-reference <...> --out-dir data/input/structure_reference --min-n 10

Reads ``growpy-qsm-descriptors`` tables, keeps the real trees (``source_kind == scan``)
of the catalog species and writes per species: percentiles p5/p25/p50/p75/p95 of every
descriptor, pooled and height-normalised (``height_bin == all``) and raw per 5 m height
bin where the bin holds at least ``--min-n`` trees; plus ``coverage.csv`` (trees per
species x source x tier x bin), ``descriptor_definitions.csv`` and ``manifest.json``.
The README in the store is hand-written and left alone.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from growpy.structure.reference import (
    BIN_M,
    CATALOG_SPECIES,
    MIN_N,
    build_reference,
    coverage,
    default_reference_dir,
    write_reference,
)


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("descriptors", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--min-n", type=int, default=MIN_N)
    parser.add_argument("--bin-m", type=float, default=BIN_M)
    parser.add_argument(
        "--all-species",
        action="store_true",
        help="keep every species, not the catalog's",
    )
    parser.add_argument("--note", default="", help="free text for the manifest")
    args = parser.parse_args(argv)
    out_dir = args.out_dir or default_reference_dir()
    table = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in args.descriptors], ignore_index=True
    )
    species = None if args.all_species else CATALOG_SPECIES
    reference = build_reference(table, species, args.bin_m, args.min_n)
    real = table[table["source_kind"] == "scan"]
    if species is not None:
        real = real[real["species_key"].isin(species)]
    cover = coverage(real, args.bin_m)
    manifest = {
        "built": date.today().isoformat(),
        "growpy_commit": _git_commit(),
        "inputs": [p.as_posix() for p in args.descriptors],
        "real_trees": int(len(real)),
        "real_trees_by_source": real["source"].value_counts().to_dict(),
        "species": sorted(reference["species_key"].unique()),
        "bin_m": args.bin_m,
        "min_n": args.min_n,
        "tier_rule": "tiers A and B when a row has >= min_n of them, else all tiers",
        "normalisation": "height_bin 'all': unit m / height, unit 1/m * height",
        "prune": "as in the inputs (growpy-qsm-descriptors defaults: laterals < 0.3 m "
        "and axes above order 2 removed)",
        "note": args.note,
    }
    write_reference(reference, cover, out_dir, manifest)
    pooled = reference[reference["height_bin"] == "all"]
    per_bin = reference[reference["height_bin"] != "all"]
    print(
        f"{len(reference)} rows: {pooled['species_key'].nunique()} species pooled, "
        f"{per_bin.groupby(['species_key', 'height_bin']).ngroups} species x bin cells "
        f"-> {out_dir}"
    )
    print(
        per_bin.groupby(["species_key", "height_bin"])["n"]
        .max()
        .unstack(fill_value=0)
        .to_string()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
