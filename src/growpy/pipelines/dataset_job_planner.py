"""Dataset job planning: which species step 4 should run.

Selection comes from ``config/tree_asset_lookup.csv`` (the ``Dataset`` column),
not from which CSV files happen to exist on disk. Globbing ``*_merged.csv`` used
to make a file's presence a second, hidden species switch that could disagree
with config -- deleting a merged CSV silently dropped that species from the run.
"""

from pathlib import Path

PILOT_SPECIES = ["European Beech", "Norway Spruce"]

DATASET_DIR = Path("data/input/dataset")


def list_all_species(dataset_dir: Path = DATASET_DIR) -> list:
    """Standardized names of every species marked for the dataset.

    Args:
        dataset_dir: Unused; kept so existing callers need no change. Species
            membership is a config question, not a filesystem one.
    """
    from growpy.pipelines.dataset_csv_planner import _get_dataset_species
    from growpy.utils.naming import standardize_species_name

    return sorted(
        standardize_species_name(name)
        for name in _get_dataset_species()["Common Name"]
    )


def display_names_from_stems(stems: list) -> list:
    """Convert standardized stems back to display names (best-effort)."""
    return [stem.replace("_", " ").title() for stem in stems]


def resolve_species(args, dataset_dir: Path = DATASET_DIR) -> list:
    """Resolve the list of species display names from CLI args.

    Checks args.species, args.pilot, and args.all (from argparse).
    """
    if getattr(args, "species", None):
        return [args.species]
    if getattr(args, "pilot", False):
        return list(PILOT_SPECIES)
    if getattr(args, "all", False):
        # Common Name directly from config, not a round-trip through the
        # standardized stem -- .title()'d stems lose punctuation (e.g.
        # "small_leaved_linden" -> "Small Leaved Linden", but the lookup
        # table's Common Name is "Small-leaved linden" with a hyphen), which
        # then fails _find_species_row's exact match in generate_forest.py.
        from growpy.pipelines.dataset_csv_planner import _get_dataset_species

        return sorted(_get_dataset_species()["Common Name"].tolist())
    return []
