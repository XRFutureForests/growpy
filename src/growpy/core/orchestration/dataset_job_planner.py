"""Dataset job planning: species selection and CSV discovery for step 4.

Resolves which species to run based on CLI selection mode (--species,
--pilot, --all) and locates the corresponding merged CSV files in the
dataset directory.
"""

from pathlib import Path

from growpy.utils.naming import standardize_species_name

PILOT_SPECIES = ["European Beech", "Norway Spruce"]

DATASET_DIR = Path("data/input/dataset")


def find_species_csv(species_name: str, dataset_dir: Path = DATASET_DIR) -> Path | None:
    """Return the merged CSV path for a species, or None if not found."""
    std_name = standardize_species_name(species_name)
    merged = dataset_dir / f"{std_name}_merged.csv"
    if merged.exists():
        return merged
    return None


def list_all_species(dataset_dir: Path = DATASET_DIR) -> list:
    """List standardized species names with merged CSV files in dataset_dir."""
    return [
        csv_path.stem.replace("_merged", "")
        for csv_path in sorted(dataset_dir.glob("*_merged.csv"))
    ]


def display_names_from_stems(stems: list) -> list:
    """Convert standardized stems back to display names (best-effort)."""
    return [stem.replace("_", " ").title() for stem in stems]


def resolve_species(args, dataset_dir: Path = DATASET_DIR) -> list:
    """Resolve the list of species display names from CLI args.

    Checks args.species, args.pilot, and args.all (from argparse).
    Returns a list of common name strings suitable for find_species_csv().
    """
    if getattr(args, "species", None):
        return [args.species]
    if getattr(args, "pilot", False):
        return list(PILOT_SPECIES)
    if getattr(args, "all", False):
        stems = list_all_species(dataset_dir)
        return display_names_from_stems(stems)
    return []
