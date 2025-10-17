"""Asset path resolution for GrowPy."""

from pathlib import Path
from typing import Optional, List, Dict
import pandas as pd

from .species import load_species_lookup, find_species_match


def get_data_directory() -> Path:
    """Get the base data directory path.

    Returns:
        Path to the data directory
    """
    current_file = Path(__file__)
    project_root = current_file.parents[3]
    return project_root / "data"


def get_assets_directory() -> Path:
    """Get the assets directory path.

    Returns:
        Path to the assets directory
    """
    return get_data_directory() / "assets"


def get_preset_path(common_name: str) -> Path:
    """Get the full path to the preset file for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the preset file
    """
    df = load_species_lookup()
    matched_name = find_species_match(common_name)
    if matched_name is None:
        raise ValueError(
            f"Species '{common_name}' not found in lookup table"
        )

    preset_name = df.loc[df["Common Name"] == matched_name, "Preset"].values[0]
    assets_dir = get_assets_directory()
    return assets_dir / "presets" / preset_name


def get_growth_model_path(common_name: str) -> Path:
    """Get the full path to the growth model directory for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the growth model directory
    """
    df = load_species_lookup()
    matched_name = find_species_match(common_name)
    if matched_name is None:
        raise ValueError(f"Species '{common_name}' not found in lookup table")

    growth_model = df.loc[df["Common Name"] == matched_name, "Growth Model"].values[0]
    assets_dir = get_assets_directory()
    return assets_dir / "growth_models" / growth_model


def get_bark_texture_path(common_name: str) -> Optional[Path]:
    """Get the full path to the bark texture file for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the bark texture file or None
    """
    from .species import get_bark_texture

    bark_texture = get_bark_texture(common_name)
    if not bark_texture:
        return None

    assets_dir = get_assets_directory()
    texture_path = assets_dir / "textures" / bark_texture
    return texture_path if texture_path.exists() else None


def get_twig_for_species(common_name: str) -> Optional[str]:
    """Get the twig name for a given species.

    Args:
        common_name: Species common name

    Returns:
        Twig name or None
    """
    df = load_species_lookup()
    if df.empty:
        return None

    matched_name = find_species_match(common_name)
    if matched_name is None:
        return None

    species_row = df[df["Common Name"] == matched_name]
    if species_row.empty:
        return None

    twig = species_row.iloc[0]["Twig"]
    if pd.isna(twig) or str(twig) in ["—", "", "nan"]:
        return None

    return str(twig)


def get_twig_directory_path(common_name: str) -> Optional[Path]:
    """Get the full path to the twig directory for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the twig directory or None
    """
    twig_name = get_twig_for_species(common_name)
    if not twig_name:
        return None

    assets_dir = get_assets_directory()
    return assets_dir / "twigs" / twig_name


def get_twig_usd_directory_path(common_name: str) -> Optional[Path]:
    """Get the full path to the twig's USD directory for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the twig's USD directory or None
    """
    twig_dir = get_twig_directory_path(common_name)
    if not twig_dir:
        return None
    return twig_dir / "usd"


def get_twig_textures_path(common_name: str) -> Optional[Path]:
    """Get the full path to the twig's USD textures directory.

    Args:
        common_name: Species common name

    Returns:
        Path to the twig's USD textures directory or None
    """
    usd_dir = get_twig_usd_directory_path(common_name)
    if not usd_dir:
        return None
    return usd_dir / "textures"


def get_twig_prototype_path(common_name: str) -> Optional[Path]:
    """Get the full path to the twig prototype file for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the twig prototype file or None
    """
    twig_name = get_twig_for_species(common_name)
    if not twig_name:
        return None

    prototype_name = twig_name + "_prototype.usda"
    assets_dir = get_assets_directory()
    twig_dir = assets_dir / "twigs" / twig_name
    return twig_dir / "usd" / "prototypes" / prototype_name


def get_twig_material_path(common_name: str) -> Optional[Path]:
    """Get the full path to the twig material file for a given species.

    Args:
        common_name: Species common name

    Returns:
        Path to the twig material file or None
    """
    twig_name = get_twig_for_species(common_name)
    if not twig_name:
        return None

    material_name = twig_name + "_material.usda"
    assets_dir = get_assets_directory()
    twig_dir = assets_dir / "twigs" / twig_name
    return twig_dir / "usd" / "materials" / material_name


def get_available_twig_usd_files(common_name: str) -> List[Path]:
    """Get all available twig USD files for a given species.

    Args:
        common_name: Species common name

    Returns:
        List of Path objects to twig files
    """
    twig_dir = get_twig_directory_path(common_name)
    if not twig_dir or not twig_dir.exists():
        return []

    usd_files = list(twig_dir.glob("*.usda")) + list(twig_dir.glob("*.usd"))
    return sorted(usd_files)


def get_twig_files_by_type(common_name: str) -> Dict[str, List[Path]]:
    """Get twig USD files organized by type.

    Args:
        common_name: Species common name

    Returns:
        Dictionary with twig types as keys and lists of Path objects as values
    """
    usd_files = get_available_twig_usd_files(common_name)
    if not usd_files:
        return {}

    twig_types = {
        "apical": [],
        "lateral": [],
        "upward": [],
        "dead": [],
        "end": [],
        "side": [],
        "main": [],
        "variation": [],
        "other": [],
    }

    for file_path in usd_files:
        filename = file_path.stem.lower()

        if not file_path.exists() and file_path.suffix in [".usda", ".usd"]:
            parent_usd = file_path.parent.parent / file_path.name
            if parent_usd.exists():
                file_path = parent_usd

        if "apical" in filename or "end" in filename or "long" in filename:
            twig_types["apical"].append(file_path)
        elif "lateral" in filename or "side" in filename or "short" in filename:
            twig_types["lateral"].append(file_path)
        elif "_upward" in filename or "upward" in filename:
            twig_types["upward"].append(file_path)
        elif "_dead" in filename or "dead" in filename:
            twig_types["dead"].append(file_path)
        elif "end" in filename or "long" in filename:
            twig_types["end"].append(file_path)
        elif "side" in filename or "short" in filename:
            twig_types["side"].append(file_path)
        elif "variation" in filename or "var_" in filename:
            twig_types["variation"].append(file_path)
        elif filename.count("_") == 1:
            twig_types["main"].append(file_path)
        else:
            twig_types["other"].append(file_path)

    return {k: v for k, v in twig_types.items() if v}


def get_best_twig_file_for_type(
    common_name: str, twig_type: str = "auto"
) -> Optional[Path]:
    """Get the best twig USD file for a specific twig type.

    Args:
        common_name: Species common name
        twig_type: Type of twig ('apical', 'lateral', 'end', 'side', 'main', 'auto')

    Returns:
        Path to the best matching twig file or None
    """
    twig_files_by_type = get_twig_files_by_type(common_name)
    if not twig_files_by_type:
        return None

    if twig_type == "auto":
        priority_order = [
            "main",
            "apical",
            "lateral",
            "end",
            "side",
            "variation",
            "other",
        ]
        for preferred_type in priority_order:
            if preferred_type in twig_files_by_type and twig_files_by_type[preferred_type]:
                return twig_files_by_type[preferred_type][0]
        return None
    else:
        if twig_type in twig_files_by_type and twig_files_by_type[twig_type]:
            return twig_files_by_type[twig_type][0]
        return None
