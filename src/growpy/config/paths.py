"""Asset path resolution for GrowPy."""

import logging
import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from growpy.utils.naming import camel_to_snake

logger = logging.getLogger(__name__)

# GBIF integration for species name resolution
_GBIF_ENABLED = True  # Can be disabled if pygbif not available or API issues


def get_project_root() -> Path:
    """Get project root directory.

    Resolution order:
    1. GROWPY_PROJECT_ROOT env var (explicit override, survives wheel installs)
    2. Traverse up from this file's location (works for editable installs only)
    """
    env_root = os.environ.get("GROWPY_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    # Editable-install assumption: src/growpy/config/paths.py -> project root is 4 levels up
    return Path(__file__).parent.parent.parent.parent


def _get_lookup_table_path() -> Path:
    """Resolve the path to tree_asset_lookup.csv.

    Resolution order:
    1. <resolved config dir>/tree_asset_lookup.csv (follows GROWPY_CONFIG)
    2. <project root>/config/tree_asset_lookup.csv
    3. <package templates>/tree_asset_lookup.csv (package fallback)
    """
    from .core import _find_config_dir

    project_root = get_project_root()
    cfg_dir = _find_config_dir()

    lookup_paths = []
    if cfg_dir:
        lookup_paths.append(cfg_dir / "tree_asset_lookup.csv")
    lookup_paths.append(project_root / "config" / "tree_asset_lookup.csv")
    lookup_paths.append(Path(__file__).parent / "templates" / "tree_asset_lookup.csv")

    for lookup_path in lookup_paths:
        if lookup_path.exists():
            return lookup_path

    raise FileNotFoundError(
        f"tree_asset_lookup.csv not found in any location: {[str(p) for p in lookup_paths]}"
    )


@lru_cache(maxsize=1)
def _get_lookup_table() -> pd.DataFrame:
    """Load tree asset lookup table as a DataFrame."""
    return pd.read_csv(_get_lookup_table_path())


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

    # Try Aliases (vectorized: no iterrows loop)
    if "Aliases" in lookup_df.columns:
        mask = (
            lookup_df["Aliases"]
            .fillna("")
            .str.lower()
            .str.split(",")
            .apply(lambda parts: species_lower in [a.strip() for a in parts])
        )
        match = lookup_df[mask]
        if not match.empty:
            return match.iloc[0]

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


def get_species_growth_habit(species: str) -> str | None:
    """Return the coarse growth habit for a species: "conifer" or "broadleaf".

    Derived from the Competition Group column in tree_asset_lookup.csv (e.g.
    "slow_conifer", "fast_broadleaf"). Returns None if the species can't be
    resolved or the row has no Competition Group value.
    """
    try:
        row = _find_species_row(species)
    except ValueError:
        return None

    group = row.get("Competition Group")
    if group is None or pd.isna(group):
        return None

    group = str(group).lower()
    if "conifer" in group:
        return "conifer"
    if "broadleaf" in group:
        return "broadleaf"
    return None


def get_data_directory() -> Path:
    """Get data directory path."""
    return get_project_root() / "data"


def get_assets_directory() -> Path:
    """Get assets directory path."""
    return get_data_directory() / "assets"


def _radius_suffix(radius: float) -> str:
    """Filename/dirname suffix for a surround radius ("" for the 0/baseline case)."""
    return "" if not radius else f".r{radius:02g}"


def radius_label(radius: float) -> str:
    """Zero-padded directory/asset label for a surround radius (e.g. r00, r07, r15).

    Unlike _radius_suffix(), this always returns a label (including for the
    0/open-grown case) since it's used for standalone folder/filename
    components (e.g. ``european_oak/r00/``) rather than a filename suffix.
    """
    return f"r{radius:02g}"


def get_preset_path(species: str, radius: float = 0.0) -> Path:
    """Get preset file path for species, optionally for a specific surround radius.

    The preset files are stored with standardized names (e.g., european_beech.seed.json)
    rather than the original Grove names (e.g., Fagaceae - Beech.seed.json).

    Args:
        species: Species name
        radius: Surround radius (meters). 0 = base/open-grown preset
            (``<name>.seed.json``). >0 looks for a radius-specific calibrated
            preset (``<name>.r{radius}.seed.json``) first, falling back to the
            base preset when no radius-specific calibration exists yet.

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
    preset_path = presets_dir / f"{standardized_name}{_radius_suffix(radius)}.seed.json"

    if radius and not preset_path.exists():
        logger.warning(
            "No radius-specific preset for %s at radius=%s, falling back to base preset",
            standardized_name,
            radius,
        )
        preset_path = presets_dir / f"{standardized_name}.seed.json"

    # Fallback: try original Grove preset name if standardized doesn't exist
    if not preset_path.exists():
        original_preset = row.get("Preset", "")
        if original_preset and not pd.isna(original_preset):
            preset_path = presets_dir / original_preset

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

    return preset_path


def get_growth_model_path(species: str, radius: float = 0.0) -> Path:
    """Get growth model directory for species, optionally for a specific surround radius.

    The growth model directories are stored with standardized names (e.g., norway_spruce)
    matching the Standardized Name column in the lookup table.

    Args:
        species: Species name
        radius: Surround radius (meters). 0 = base growth model directory.
            >0 looks for a radius-specific subdirectory (``<name>/r{radius}/``)
            first, falling back to the base directory when no radius-specific
            growth model exists yet.

    Returns:
        Path to growth model directory
    """
    row = _find_species_row(species)
    models_dir = get_assets_directory() / "growth_models"

    def _resolve(base: Path) -> Path | None:
        if radius:
            radius_dir = base / radius_label(radius)
            if radius_dir.exists():
                return radius_dir
        return base if base.exists() else None

    # Use standardized name for directory lookup (growth_models use standardized names)
    standardized_name = row.get("Standardized Name", "")
    if standardized_name and not pd.isna(standardized_name):
        resolved = _resolve(models_dir / standardized_name)
        if resolved:
            return resolved

    # Fallback: try the Growth Model column (legacy family-based naming)
    model_name = row.get("Growth Model", "")
    if model_name and not pd.isna(model_name):
        resolved = _resolve(models_dir / model_name)
        if resolved:
            return resolved

    # Fallback: derive from Common Name
    common_name = str(row["Common Name"]).lower().replace(" ", "_").replace("/", "_")
    resolved = _resolve(models_dir / common_name)
    if resolved:
        return resolved

    raise FileNotFoundError(
        f"Growth model not found for species '{species}'. "
        f"Tried: {standardized_name}, {model_name}, {common_name} under {models_dir}"
    )


def _normalize_grove_texture_name(texture_name: str) -> tuple:
    """Convert a CamelCase Grove texture filename to a snake_case stem + extension.

    Examples:
        "Beech60.jpg"       -> ("beech_60", ".jpg")
        "BaldCypress80.jpg" -> ("bald_cypress_80", ".jpg")
    """
    stem = Path(texture_name).stem
    ext = Path(texture_name).suffix
    # Insert underscore before uppercase letters, then before digit-after-letter
    standardized = (
        re.sub(r"([A-Z])", r"_\1", stem).lower().lstrip("_").replace("__", "_")
    )
    standardized = re.sub(r"([a-z]{2,})(\d)", r"\1_\2", standardized)
    return standardized, ext


def get_bark_texture_path(species: str) -> Path | None:
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
        standardized_name, ext = _normalize_grove_texture_name(texture_name)
        texture_path = textures_dir / f"{standardized_name}_bark{ext}"

        if texture_path.exists():
            return texture_path

        return None

    except (ValueError, KeyError):
        logger.warning("Failed to resolve bark texture for %s", species)
        return None


def get_bark_normal_texture_path(species: str) -> Path | None:
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
        standardized_name, ext = _normalize_grove_texture_name(texture_name)
        texture_path = textures_dir / f"{standardized_name}_bark_normal{ext}"

        if texture_path.exists():
            return texture_path

        return None

    except (ValueError, KeyError):
        logger.warning("Failed to resolve bark normal texture for %s", species)
        return None


def get_twig_files_by_type(species: str) -> dict[str, list[Path]]:
    """Get twig files organized by type for species.

    The twig directories are stored with standardized snake_case names
    (e.g., european_beech_twig) rather than the original Grove CamelCase names
    (e.g., EuropeanBeechTwig).

    Twig files are named after the twig's native species (the directory name),
    not the consuming species. Species sharing a twig (e.g. Norway spruce and
    Silver fir both using PacificSilverFirTwig) reference the same files.

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

        twig_name_std = camel_to_snake(str(twig_name).strip())

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

        # Organize twig files by type - return all USD files in the directory.
        # Files are named after the twig's native species (directory name),
        # so no species filtering is needed.
        twig_files: dict[str, list[Path]] = {}
        for usd_file in twig_dir.glob("*.usd*"):
            file_type = usd_file.stem.lower()

            if file_type not in twig_files:
                twig_files[file_type] = []
            twig_files[file_type].append(usd_file)

        return twig_files

    except (ValueError, KeyError):
        logger.warning("Failed to resolve twig files for %s", species)
        return {}
