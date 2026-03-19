"""Dataset CSV generation: merged per-species CSVs and all-species CSV.

Reads species metadata from tree_asset_lookup.csv (Max Height, Competition
Spacing) and generates merged CSV files (open + competition combined) for each
dataset species, plus an all-species CSV for pipeline steps 1-3.
"""

import logging
import math
from pathlib import Path

import pandas as pd

from growpy.config import get_config
from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

DENSITY_VARIANTS = {
    "full": 1.0,
    "reduced": 0.5,
    "bare": 0.0,
}

# X offset for open-grown tree to avoid light competition with cluster
OPEN_TREE_X = 100.0


def _get_dataset_species(config=None) -> pd.DataFrame:
    """Load species with Max Height and Competition Spacing from lookup CSV."""
    if config is None:
        config = get_config()

    csv_path = Path(config.grove_dir).parent / "growpy" / "config" / "tree_asset_lookup.csv"
    if not csv_path.exists():
        csv_path = Path(__file__).parent.parent.parent / "config" / "tree_asset_lookup.csv"

    df = pd.read_csv(csv_path)
    dataset = df[df["Max Height"].notna() & df["Competition Spacing"].notna()].copy()
    dataset["Max Height"] = dataset["Max Height"].astype(int)
    dataset["Competition Spacing"] = dataset["Competition Spacing"].astype(int)
    return dataset


def _hex_neighbors(spacing: float) -> list:
    """Compute 6 hexagonal neighbor positions at given spacing.

    Returns list of (fid, x, y) tuples. Center tree is at origin (not included).
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


def generate_merged_csv(
    species_name: str,
    max_height: int,
    spacing: int,
    twig_density: float = 1.0,
) -> pd.DataFrame:
    """Generate merged DataFrame: open tree + competition cluster in one simulation.

    The open-grown tree (fid=1) is placed at (OPEN_TREE_X, 0, 0) to avoid
    light competition. The competition center tree is fid=2 at origin.
    Six hexagonal neighbors (fid=101-106) surround the center tree.
    """
    rows = [
        {
            "fid": 1,
            "species": species_name,
            "x": OPEN_TREE_X,
            "y": 0.0,
            "z": 0.0,
            "height": max_height,
            "twig_density": twig_density,
            "individual_type": "open_grown",
        },
        {
            "fid": 2,
            "species": species_name,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "height": max_height,
            "twig_density": twig_density,
            "individual_type": "competition",
        },
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

    Writes per-species merged CSVs ({std_name}_merged.csv) and one
    all_species.csv (one row per species, for pipeline steps 1-3).

    Args:
        output_dir: Directory to write CSV files to.
        density: Density variant key — full (1.0), reduced (0.5), bare (0.0).

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

        merged_df = generate_merged_csv(species, max_height, spacing, twig_density)
        merged_path = output_dir / f"{std_name}_merged.csv"
        merged_df.to_csv(merged_path, index=False)
        generated.append(merged_path)
        logger.info("  %s", merged_path.name)

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

    all_df = pd.DataFrame(all_species_rows)
    all_path = output_dir / "all_species.csv"
    all_df.to_csv(all_path, index=False)
    generated.append(all_path)
    logger.info("  %s", all_path.name)

    return generated
