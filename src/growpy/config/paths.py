"""Asset path resolution for GrowPy."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# GBIF integration for species name resolution
_GBIF_ENABLED = True  # Can be disabled if pygbif not available or API issues


def _get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


@lru_cache(maxsize=1)
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


def _find_species_row(species: str, use_gbif: bool = True) -> pd.Series:
    """Find species row in lookup table.

    Matching order:
    1. Common Name (exact, case-insensitive)
    2. Standardized Name (exact, case-insensitive)
    3. Scientific Name (exact, case-insensitive)
    4. Aliases (comma-separated list)
    5. GBIF fallback (resolves synonyms, misspellings, scientific names)

    Args:
        species: Species name (Common Name, Scientific Name, Alias, or synonym)
        use_gbif: Whether to use GBIF for unmatched names (default: True)

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

    # GBIF fallback - resolves synonyms, misspellings, alternative names
    if use_gbif and _GBIF_ENABLED:
        try:
            from growpy.utils.gbif_species import match_species_via_gbif

            gbif_match = match_species_via_gbif(species, lookup_df)
            if gbif_match is not None:
                return gbif_match
        except ImportError:
            pass  # pygbif not available

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

    The growth model directories are stored with standardized names (e.g., norway_spruce)
    matching the Standardized Name column in the lookup table.

    Args:
        species: Species name

    Returns:
        Path to growth model directory
    """
    row = _find_species_row(species)
    models_dir = get_assets_directory() / "growth_models"

    # Use standardized name for directory lookup (growth_models use standardized names)
    standardized_name = row.get("Standardized Name", "")
    if standardized_name and not pd.isna(standardized_name):
        model_path = models_dir / standardized_name
        if model_path.exists():
            return model_path

    # Fallback: try the Growth Model column (legacy family-based naming)
    model_name = row.get("Growth Model", "")
    if model_name and not pd.isna(model_name):
        model_path = models_dir / model_name
        if model_path.exists():
            return model_path

    # Fallback: derive from Common Name
    common_name = str(row["Common Name"]).lower().replace(" ", "_").replace("/", "_")
    model_path = models_dir / common_name

    return model_path


def get_bark_texture_path(species: str) -> Optional[Path]:
    """Get bark texture file path for species.

    The texture files are stored with standardized names (e.g., beech_60_bark.jpg)
    rather than the original Grove names (e.g., Beech60.jpg).

    Args:
        species: Species name

    Returns:
        Path to bark texture file, or None if not found
    """
    try:
        row = _find_species_row(species)
        texture_name = row.get("Bark Texture", "")

        if pd.isna(texture_name) or texture_name in ["—", "", "nan"]:
            return None

        textures_dir = get_assets_directory() / "textures"

        # Convert CamelCase Grove name to snake_case with _bark suffix
        # Examples: "Beech60.jpg" -> "beech_60_bark.jpg"
        #           "BaldCypress80.jpg" -> "bald_cypress_80_bark.jpg"
        texture_stem = Path(texture_name).stem
        texture_ext = Path(texture_name).suffix

        # Insert underscore before uppercase letters and numbers, convert to lowercase
        standardized_name = (
            re.sub(r"([A-Z])", r"_\1", texture_stem)
            .lower()
            .lstrip("_")
            .replace("__", "_")
        )
        # Insert underscore before numbers
        standardized_name = re.sub(r"([a-z])(\d)", r"\1_\2", standardized_name)

        texture_path = textures_dir / f"{standardized_name}_bark{texture_ext}"

        if texture_path.exists():
            return texture_path

        return None

    except (ValueError, KeyError):
        return None


def get_bark_normal_texture_path(species: str) -> Optional[Path]:
    """Get bark normal map texture file path for species.

    The normal texture files follow the same naming convention as diffuse textures
    but with _normal suffix (e.g., beech_60_bark_normal.jpg).

    Args:
        species: Species name

    Returns:
        Path to bark normal texture file, or None if not found
    """
    try:
        row = _find_species_row(species)
        texture_name = row.get("Bark Texture", "")

        if pd.isna(texture_name) or texture_name in ["—", "", "nan"]:
            return None

        textures_dir = get_assets_directory() / "textures"

        # Convert CamelCase Grove name to snake_case with _bark_normal suffix
        # Examples: "Beech60.jpg" -> "beech_60_bark_normal.jpg"
        #           "BaldCypress80.jpg" -> "bald_cypress_80_bark_normal.jpg"
        texture_stem = Path(texture_name).stem
        texture_ext = Path(texture_name).suffix

        # Insert underscore before uppercase letters and numbers, convert to lowercase
        standardized_name = (
            re.sub(r"([A-Z])", r"_\1", texture_stem)
            .lower()
            .lstrip("_")
            .replace("__", "_")
        )
        # Insert underscore before numbers
        standardized_name = re.sub(r"([a-z])(\d)", r"\1_\2", standardized_name)

        texture_path = textures_dir / f"{standardized_name}_bark_normal{texture_ext}"

        if texture_path.exists():
            return texture_path

        return None

    except (ValueError, KeyError):
        return None


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
        twig_files: Dict[str, List[Path]] = {}
        for usd_file in twig_dir.glob("*.usd*"):
            file_type = usd_file.stem.lower()
            if file_type not in twig_files:
                twig_files[file_type] = []
            twig_files[file_type].append(usd_file)

        return twig_files

    except (ValueError, KeyError):
        return {}
