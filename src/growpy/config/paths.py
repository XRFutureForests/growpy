"""Asset path resolution for GrowPy."""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def _get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _get_lookup_table() -> pd.DataFrame:
    """Load tree asset lookup table.

    Looks in multiple locations:
    1. src/growpy/config/tree_asset_lookup.csv (packaged with code)
    2. config/tree_asset_lookup.csv (project root override)
    3. data/tree_asset_lookup.csv (legacy)

    Returns:
        DataFrame with species lookup data
    """
    project_root = _get_project_root()

    # Try locations in order
    lookup_paths = [
        Path(__file__).parent / "tree_asset_lookup.csv",  # Packaged with code
        project_root / "config" / "tree_asset_lookup.csv",  # Project root override
        project_root / "data" / "tree_asset_lookup.csv",  # Legacy
    ]

    for lookup_path in lookup_paths:
        if lookup_path.exists():
            return pd.read_csv(lookup_path)

    raise FileNotFoundError(
        f"tree_asset_lookup.csv not found in any location: {[str(p) for p in lookup_paths]}"
    )


def _find_species_row(species: str) -> pd.Series:
    """Find species row in lookup table.

    Args:
        species: Species name (Common Name, Scientific Name, or Alias)

    Returns:
        Series with species data

    Raises:
        ValueError: If species not found
    """
    lookup_df = _get_lookup_table()
    species_lower = species.lower()

    # Try Common Name
    match = lookup_df[lookup_df["Common Name"].str.lower() == species_lower]
    if not match.empty:
        return match.iloc[0]

    # Try Standardized Name
    if "Standardized Name" in lookup_df.columns:
        match = lookup_df[lookup_df["Standardized Name"].str.lower() == species_lower]
        if not match.empty:
            return match.iloc[0]

    # Try Scientific Name
    if "Scientific Name" in lookup_df.columns:
        match = lookup_df[lookup_df["Scientific Name"].str.lower() == species_lower]
        if not match.empty:
            return match.iloc[0]

    # Try Aliases
    if "Aliases" in lookup_df.columns:
        for _, row in lookup_df.iterrows():
            aliases = str(row.get("Aliases", "")).lower()
            if species_lower in [a.strip() for a in aliases.split(",")]:
                return row

    raise ValueError(f"Species '{species}' not found in lookup table")


def get_data_directory() -> Path:
    """Get data directory path."""
    return _get_project_root() / "data"


def get_assets_directory() -> Path:
    """Get assets directory path."""
    return get_data_directory() / "assets"


def get_preset_path(species: str) -> Path:
    """Get preset file path for species.

    The preset files are stored with standardized names (e.g., european_beech.seed.json)
    rather than the original Grove names (e.g., Fagaceae - Beech.seed.json).

    Args:
        species: Species name

    Returns:
        Path to preset file
    """
    row = _find_species_row(species)

    # Use standardized name for file lookup (preset files have been renamed)
    standardized_name = row.get("Standardized Name", "")
    if not standardized_name or pd.isna(standardized_name):
        # Fallback: try to derive from Common Name
        standardized_name = (
            str(row["Common Name"]).lower().replace(" ", "_").replace("/", "_")
        )

    presets_dir = get_assets_directory() / "presets"
    preset_path = presets_dir / f"{standardized_name}.seed.json"

    # Fallback: try original Grove preset name if standardized doesn't exist
    if not preset_path.exists():
        original_preset = row.get("Preset", "")
        if original_preset and not pd.isna(original_preset):
            preset_path = presets_dir / original_preset

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

    return preset_path


def get_growth_model_path(species: str) -> Path:
    """Get growth model directory for species.

    Args:
        species: Species name

    Returns:
        Path to growth model directory
    """
    row = _find_species_row(species)
    model_name = row["Growth Model"]

    models_dir = get_assets_directory() / "growth_models"
    model_path = models_dir / model_name

    return model_path


def get_twig_files_by_type(species: str) -> Dict[str, List[Path]]:
    """Get twig files organized by type for species.

    The twig directories are stored with standardized snake_case names
    (e.g., european_beech_twig) rather than the original Grove CamelCase names
    (e.g., EuropeanBeechTwig).

    Args:
        species: Species name

    Returns:
        Dict mapping twig type to list of file paths
    """
    try:
        row = _find_species_row(species)
        twig_name = row.get("Twig", "")

        if pd.isna(twig_name) or twig_name in ["—", "", "nan"]:
            return {}

        twigs_dir = get_assets_directory() / "twigs"

        # Convert CamelCase Grove name to snake_case (e.g., EuropeanBeechTwig -> european_beech_twig)
        # Insert underscore before uppercase letters, convert to lowercase
        import re

        twig_name_std = (
            re.sub(r"([A-Z])", r"_\1", str(twig_name).strip()).lower().lstrip("_")
        )

        # Try standardized name with _twig suffix
        twig_dir = twigs_dir / f"{twig_name_std}_twig"

        # Fallback: try original Grove name
        if not twig_dir.exists():
            twig_dir = twigs_dir / str(twig_name).strip()

        # Fallback: try without _twig suffix
        if not twig_dir.exists():
            twig_dir = twigs_dir / twig_name_std

        if not twig_dir.exists():
            return {}

        # Organize twig files by type
        twig_files = {}
        for usd_file in twig_dir.glob("*.usd*"):
            file_type = usd_file.stem.lower()
            if file_type not in twig_files:
                twig_files[file_type] = []
            twig_files[file_type].append(usd_file)

        return twig_files

    except (ValueError, KeyError):
        return {}
