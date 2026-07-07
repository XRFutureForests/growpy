"""Dataset CSV generation: merged per-species CSVs and all-species CSV.

Reads species metadata from tree_asset_lookup.csv (Max Height, Competition
Group) and generates merged CSV files (open + competition combined) for each
dataset species, plus an all-species CSV for pipeline steps 1-3.

The "surround" individual uses Grove's built-in Surround light-competition
shell instead of simulating neighbour trees, so each merged CSV holds just
two single trees: one open-grown and one surround.
"""

import logging
from pathlib import Path

import pandas as pd

from growpy.config.paths import _get_lookup_table
from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

DENSITY_VARIANTS = {
    "full": 1.0,
    "reduced": 0.5,
    "bare": 0.0,
}

# Truthy markers for the tree_asset_lookup.csv "Dataset" column. A species is
# part of the production dataset when this column is marked (and it has both
# Max Height and Competition Group set). The "Dataset" column is the single
# source that controls dataset membership.
DATASET_MARKERS = frozenset({"yes", "true", "1", "x"})

# X offset for open-grown tree to avoid light competition with the surround tree
OPEN_TREE_X = 100.0


def _get_dataset_species() -> pd.DataFrame:
    """Load production-dataset species from the lookup CSV.

    A species belongs to the dataset when its ``Dataset`` column is marked
    (see :data:`DATASET_MARKERS`) and it has both ``Max Height`` and
    ``Competition Group`` set. The ``Dataset`` column is the only control for
    dataset membership.
    """
    df = _get_lookup_table()
    if "Dataset" not in df.columns:
        raise KeyError(
            "tree_asset_lookup.csv is missing the 'Dataset' column. Re-run "
            "'growpy-init-config --force' to refresh it, or add a 'Dataset' "
            "column and mark each species to include with 'yes'."
        )
    marker = df["Dataset"].fillna("").astype(str).str.strip().str.lower()
    dataset = df[
        marker.isin(DATASET_MARKERS)
        & df["Max Height"].notna()
        & df["Competition Group"].notna()
    ].copy()
    dataset["Max Height"] = dataset["Max Height"].astype(int)
    return dataset


def generate_merged_csv(
    species_name: str,
    max_height: int,
    twig_density: float = 1.0,
) -> pd.DataFrame:
    """Generate merged DataFrame: open-grown + surround tree in one file.

    Both are single trees, each simulated in its own grove. The open-grown tree
    (fid=1) is placed at (OPEN_TREE_X, 0, 0); the surround tree (fid=2) sits at
    the origin and gets Grove's Surround light-competition shell enabled during
    simulation (see growpy.core.grove.enable_surround), giving the tall, slender
    forest-grown form without simulating any neighbour trees.
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
            "individual_type": "surround",
        },
    ]
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
        merged_df = generate_merged_csv(species, max_height, twig_density)
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
        keep = all_df["species"].apply(lambda s: standardize_species_name(s) in common)
        removed = all_df[~keep]["species"].tolist()
        all_df = all_df[keep].reset_index(drop=True)
        all_df["fid"] = range(1, len(all_df) + 1)
        all_df.to_csv(all_species_path, index=False)
        for name in removed:
            logger.warning("Removed from all_species.csv (no merged CSV): %s", name)

    logger.info(
        "Dataset synchronized: %d species in both all_species.csv and merged CSVs.",
        len(common),
    )
