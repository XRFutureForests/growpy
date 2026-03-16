#!/usr/bin/env python3
"""Generate input CSV files for dataset production.

Reads species metadata from tree_asset_lookup.csv (Max Height, Competition Spacing)
and generates open-grown and competition CSV templates for each dataset species,
plus an all-species CSV for pipeline steps 1-3.

See docs/dataset-specification.md for the full dataset specification.
"""

import argparse
import logging
import math
from pathlib import Path

import pandas as pd

from growpy.config import get_config
from growpy.utils.log import setup_logging
from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

DENSITY_VARIANTS = {
    "full": 1.0,
    "reduced": 0.5,
    "bare": 0.0,
}


def _get_dataset_species(config=None) -> pd.DataFrame:
    """Load species with Max Height and Competition Spacing from lookup CSV."""
    if config is None:
        config = get_config()

    csv_path = Path(config.grove_dir).parent / "growpy" / "config" / "tree_asset_lookup.csv"
    if not csv_path.exists():
        csv_path = Path(__file__).parent.parent / "config" / "tree_asset_lookup.csv"

    df = pd.read_csv(csv_path)
    dataset = df[df["Max Height"].notna() & df["Competition Spacing"].notna()].copy()
    dataset["Max Height"] = dataset["Max Height"].astype(int)
    dataset["Competition Spacing"] = dataset["Competition Spacing"].astype(int)
    return dataset


def _hex_neighbors(spacing: float) -> list:
    """Compute 6 hexagonal neighbor positions at given spacing.

    Returns list of (fid, x, y) tuples for the 6 neighbors.
    Center tree (fid=1) is at origin and not included.
    """
    s = spacing
    h = s * math.sqrt(3) / 2  # s * 0.866
    return [
        (101, round(s, 3), 0.0),
        (102, round(-s, 3), 0.0),
        (103, round(s / 2, 3), round(h, 3)),
        (104, round(-s / 2, 3), round(h, 3)),
        (105, round(s / 2, 3), round(-h, 3)),
        (106, round(-s / 2, 3), round(-h, 3)),
    ]


def generate_open_csv(
    species_name: str, max_height: int, twig_density: float = 1.0
) -> pd.DataFrame:
    """Generate open-grown CSV: single tree at origin."""
    return pd.DataFrame(
        [
            {
                "fid": 1,
                "species": species_name,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "height": max_height,
                "twig_density": twig_density,
                "individual_type": "open_grown",
            }
        ]
    )


def generate_competition_csv(
    species_name: str,
    max_height: int,
    spacing: int,
    twig_density: float = 1.0,
) -> pd.DataFrame:
    """Generate competition CSV: center tree + 6 hexagonal neighbors."""
    rows = [
        {
            "fid": 1,
            "species": species_name,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "height": max_height,
            "twig_density": twig_density,
            "individual_type": "competition",
        }
    ]
    for fid, x, y in _hex_neighbors(spacing):
        rows.append(
            {
                "fid": fid,
                "species": species_name,
                "x": x,
                "y": y,
                "z": 0.0,
                "height": max_height,
                "twig_density": twig_density,
                "individual_type": "competition",
            }
        )
    return pd.DataFrame(rows)


def generate_dataset_csvs(output_dir: Path, density: str = "full") -> list:
    """Generate all dataset CSV files.

    Args:
        output_dir: Directory to write CSV files to.
        density: Density variant to use (full, reduced, bare).

    Returns:
        List of generated CSV file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = _get_dataset_species()
    twig_density = DENSITY_VARIANTS.get(density, 1.0)

    generated = []
    all_species_rows = []

    for _, row in dataset.iterrows():
        species = row["Common Name"]
        std_name = standardize_species_name(species)
        max_height = row["Max Height"]
        spacing = row["Competition Spacing"]

        # Open-grown CSV
        open_df = generate_open_csv(species, max_height, twig_density)
        open_path = output_dir / f"{std_name}_open.csv"
        open_df.to_csv(open_path, index=False)
        generated.append(open_path)
        logger.info(f"  {open_path.name}")

        # Competition CSV
        comp_df = generate_competition_csv(species, max_height, spacing, twig_density)
        comp_path = output_dir / f"{std_name}_competition.csv"
        comp_df.to_csv(comp_path, index=False)
        generated.append(comp_path)
        logger.info(f"  {comp_path.name}")

        # Collect unique species for all-species CSV
        all_species_rows.append(
            {
                "fid": len(all_species_rows) + 1,
                "species": species,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "height": max_height,
                "twig_density": twig_density,
            }
        )

    # All-species CSV (one tree per species, for pipeline steps 1-3)
    all_df = pd.DataFrame(all_species_rows)
    all_path = output_dir / "all_species.csv"
    all_df.to_csv(all_path, index=False)
    generated.append(all_path)
    logger.info(f"  {all_path.name}")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate dataset input CSV files for all 16 species."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/input/dataset"),
        help="Output directory for CSV files (default: data/input/dataset)",
    )
    parser.add_argument(
        "--density",
        choices=["full", "reduced", "bare"],
        default="full",
        help="Twig density variant (default: full)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    logger.info(f"Generating dataset CSVs in {args.output_dir}")
    files = generate_dataset_csvs(args.output_dir, args.density)
    logger.info(f"Generated {len(files)} CSV files")


if __name__ == "__main__":
    main()
