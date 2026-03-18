#!/usr/bin/env python3
"""Generate merged CSV files combining open + competition for each species.

The open-grown tree is placed at (100, 0, 0) to avoid light competition
with the cluster at origin. Both the open tree (fid=1) and competition
center tree (fid=2) are exported via --export-trees 1,2.

Usage:
    python src/scripts/create_merged_csvs.py
"""

import csv
from pathlib import Path

DATASET_DIR = Path("data/input/dataset")
OPEN_TREE_X = 100.0


def merge_species(species_stem: str) -> None:
    open_csv = DATASET_DIR / f"{species_stem}_open.csv"
    comp_csv = DATASET_DIR / f"{species_stem}_competition.csv"
    merged_csv = DATASET_DIR / f"{species_stem}_merged.csv"

    if not open_csv.exists() or not comp_csv.exists():
        print(f"Skipping {species_stem}: missing open or competition CSV")
        return

    with open(open_csv, newline="") as f:
        reader = csv.DictReader(f)
        open_rows = list(reader)

    with open(comp_csv, newline="") as f:
        reader = csv.DictReader(f)
        comp_rows = list(reader)

    merged_rows = []

    # Open tree: fid=1, shifted to (100, 0, 0)
    for row in open_rows:
        row["x"] = str(OPEN_TREE_X)
        row["fid"] = "1"
        merged_rows.append(row)

    # Competition trees: center fid remapped from 1 to 2
    for row in comp_rows:
        if row["fid"] == "1":
            row["fid"] = "2"
        merged_rows.append(row)

    fieldnames = list(open_rows[0].keys())
    with open(merged_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"Created {merged_csv} ({len(merged_rows)} rows)")


def main():
    species = set()
    for csv_path in sorted(DATASET_DIR.glob("*_open.csv")):
        species.add(csv_path.stem.replace("_open", ""))

    for stem in sorted(species):
        merge_species(stem)

    print(f"\nDone. {len(species)} merged CSVs created.")


if __name__ == "__main__":
    main()
