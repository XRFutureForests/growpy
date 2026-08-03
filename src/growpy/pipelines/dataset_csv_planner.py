"""Dataset job rows, and optional CSV dumps of them.

The job matrix is a **job matrix**, not a spatial layout. Each row is one
dataset asset to produce -- species x surround radius, expanded at export into
height stages and density variants. The ``x``/``y``/``z`` columns carry no
spatial meaning: ``OPEN_TREE_X`` merely offsets each row so the variants stay
visually distinct, and each row is simulated in its own grove regardless.

Every value is derived from config -- ``Max Height`` and dataset membership from
tree_asset_lookup.csv, radii from ``[surround].radii`` -- so :func:`build_job_matrix`
needs nothing but a species name. Step 4 calls it directly; the ``*_merged.csv``
files that :func:`generate_dataset_csvs` writes are an inspection aid that
nothing reads back. They used to be the pipeline's input, which made them a
cache of config that could silently drift from it.

Contrast a CSV handed to ``growpy-generate-forest`` directly, where positions
are real, trees share a grove, and neighbours actually compete for light.
Growth-pacing calibration belongs to that path, not this one. Note that Grove
disables Surround once several trees share a grove, so surround-based
competition and true co-growth are mutually exclusive by construction.

Each row's surround_radius selects its competition level: 0 = open-grown (no
shell), >0 = Grove's built-in Surround light-competition shell at that distance
(see growpy.core.grove.enable_surround), giving the tall, slender, self-pruned
form of a forest-grown tree without simulating neighbour trees.
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


def build_job_matrix(
    species_name: str,
    twig_density: float = 1.0,
) -> pd.DataFrame:
    """Build one species' dataset job rows from config alone.

    One row per configured surround radius. Every value is derived --
    ``Max Height`` from tree_asset_lookup.csv, radii from [surround].radii --
    so this needs no input beyond the species name, and nothing about it can
    drift from config the way a CSV on disk can.

    Each row is simulated in its own grove, offset along x so the variants stay
    visually distinct (OPEN_TREE_X apart). That offset is cosmetic: the rows are
    a job matrix, not a spatial layout (see the module docstring).

    Raises:
        ValueError: if the species has no Max Height in the lookup table.
    """
    from growpy.config.paths import _find_species_row

    row = _find_species_row(species_name)
    max_height = row.get("Max Height")
    if max_height is None or pd.isna(max_height):
        raise ValueError(
            f"{species_name} has no Max Height in tree_asset_lookup.csv; "
            "cannot build dataset job rows for it."
        )
    return _job_rows(str(row["Common Name"]), int(max_height), twig_density)


def _job_rows(
    species_name: str,
    max_height: int,
    twig_density: float,
) -> pd.DataFrame:
    """One row per configured surround radius. Single source for job rows."""
    from growpy.config import get_config

    radii = get_config().surround_radii
    rows = [
        {
            "fid": i + 1,
            "species": species_name,
            "x": OPEN_TREE_X * i,
            "y": 0.0,
            "z": 0.0,
            "height": max_height,
            "twig_density": twig_density,
            "surround_radius": radius,
        }
        for i, radius in enumerate(radii)
    ]
    return pd.DataFrame(rows)


def generate_merged_csv(
    species_name: str,
    max_height: int,
    twig_density: float = 1.0,
) -> pd.DataFrame:
    """Job rows for one species, for writing to an inspection CSV.

    Nothing in the pipeline reads these CSVs any more -- step 4 builds the same
    rows in memory via :func:`build_job_matrix`. Kept so ``--generate-csvs`` can
    still dump the matrix for eyeballing.
    """
    return _job_rows(species_name, max_height, twig_density)


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


