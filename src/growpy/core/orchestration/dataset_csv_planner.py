"""Dataset CSV generation: merged per-species CSVs and all-species CSV.

Reads species metadata from tree_asset_lookup.csv (Max Height, Competition
Spacing) and generates merged CSV files (open + competition combined) for each
dataset species, plus an all-species CSV for pipeline steps 1-3.

Competition layout: 3 neighbors in an equilateral triangle around the center
tree, with species-specific spacing based on crown width.
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

# Southern German forest species selection (5 conifer + 5 broadleaf).
DATASET_SPECIES = [
    "Norway spruce",
    "European beech",
    "Silver fir",
    "Scots pine",
    "European oak",
    "Douglas fir",
    "Sycamore maple",
    "Common ash",
    "European larch",
    "Silver birch",
]

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
    dataset = dataset[dataset["Common Name"].isin(DATASET_SPECIES)]
    dataset["Max Height"] = dataset["Max Height"].astype(int)
    dataset["Competition Spacing"] = dataset["Competition Spacing"].astype(int)
    return dataset


def _triangle_neighbors(spacing: float) -> list:
    """Compute 3 equilateral triangle neighbor positions at given spacing.

    Places neighbors at 120-degree intervals around the center tree (origin),
    each at the given spacing distance. The resulting equilateral triangle
    has side length spacing * sqrt(3).

    Returns list of (fid, x, y) tuples. Center tree is at origin (not included).
    """
    s = spacing
    h = s * math.sqrt(3) / 2  # s * 0.866
    return [
        (101, round(s, 3), 0.0),
        (102, round(-s / 2, 3), round(h, 3)),
        (103, round(-s / 2, 3), round(-h, 3)),
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
    Three equilateral-triangle neighbors (fid=101-103) surround the center tree,
    spaced according to the species crown width.
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
    for fid, x, y in _triangle_neighbors(spacing):
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


def synchronize_dataset_csvs(dataset_dir: Path) -> None:
    """Ensure all_species.csv and *_merged.csv files cover the same species.

    Removes rows from all_species.csv for species without a merged CSV,
    and deletes merged CSVs for species not listed in all_species.csv.
    """
    all_species_path = dataset_dir / "all_species.csv"
    if not all_species_path.exists():
        return

    all_df = pd.read_csv(all_species_path)
    if "species" not in all_df.columns:
        return

    # Species in all_species.csv (standardized name -> row index)
    all_species_std = {
        standardize_species_name(s): s for s in all_df["species"].tolist()
    }

    # Species with merged CSVs on disk
    merged_std = {
        p.stem.replace("_merged", "") for p in dataset_dir.glob("*_merged.csv")
    }

    common = set(all_species_std.keys()) & merged_std
    only_in_all = set(all_species_std.keys()) - merged_std
    only_in_merged = merged_std - set(all_species_std.keys())

    if not only_in_all and not only_in_merged:
        return

    # Remove orphan merged CSVs
    for std_name in sorted(only_in_merged):
        orphan = dataset_dir / f"{std_name}_merged.csv"
        if orphan.exists():
            orphan.unlink()
            logger.warning("Removed orphan merged CSV: %s", orphan.name)

    # Filter all_species.csv to common species only
    if only_in_all:
        keep = all_df["species"].apply(
            lambda s: standardize_species_name(s) in common
        )
        removed = all_df[~keep]["species"].tolist()
        all_df = all_df[keep].reset_index(drop=True)
        all_df["fid"] = range(1, len(all_df) + 1)
        all_df.to_csv(all_species_path, index=False)
        for name in removed:
            logger.warning(
                "Removed from all_species.csv (no merged CSV): %s", name
            )

    logger.info(
        "Dataset synchronized: %d species in both all_species.csv and merged CSVs.",
        len(common),
    )
