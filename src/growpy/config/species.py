"""Species lookup and matching for GrowPy."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_species_df: Optional[pd.DataFrame] = None


def load_species_lookup(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the species lookup table from CSV file.

    Args:
        csv_path: Optional path to CSV file

    Returns:
        Species lookup DataFrame
    """
    global _species_df
    if _species_df is not None:
        return _species_df

    if csv_path is None:
        current_file = Path(__file__)
        config_dir = current_file.parent
        project_root = current_file.parents[3]

        package_config = config_dir / "tree_asset_lookup.csv"
        if package_config.exists():
            csv_path = package_config
        elif (project_root / "config" / "tree_asset_lookup.csv").exists():
            csv_path = project_root / "config" / "tree_asset_lookup.csv"
        else:
            csv_path = project_root / "data" / "tree_asset_lookup.csv"

    _species_df = pd.read_csv(csv_path, encoding="utf-8")
    return _species_df


@lru_cache(maxsize=128)
def find_species_match(input_name: str) -> Optional[str]:
    """Find the best matching species name from the lookup table.

    Args:
        input_name: Input species name

    Returns:
        Matched species name or None
    """
    df = load_species_lookup()
    if df.empty:
        return None

    input_lower = input_name.lower().strip()
    common_names = df["Common Name"].str.lower().str.strip()

    # Exact match
    exact_match = df[common_names == input_lower]
    if not exact_match.empty:
        return exact_match.iloc[0]["Common Name"]

    # Match against Preset column (format: "Family - Common Name.seed.json")
    if "Preset" in df.columns:
        for idx, row in df.iterrows():
            preset = row.get("Preset", "")
            if pd.notna(preset) and preset.strip():
                # Remove .seed.json extension and compare
                preset_base = str(preset).replace(".seed.json", "").lower().strip()
                if input_lower == preset_base:
                    return row["Common Name"]

    # Aliases
    if "Aliases" in df.columns:
        for idx, row in df.iterrows():
            aliases_str = row.get("Aliases", "")
            if pd.notna(aliases_str) and aliases_str.strip():
                aliases = [a.strip().lower() for a in str(aliases_str).split(",")]
                if input_lower in aliases:
                    return row["Common Name"]

    # Partial match - input contains any word from species name
    for idx, species_name in enumerate(df["Common Name"]):
        species_words = species_name.lower().split()
        input_words = input_lower.split()
        if any(input_word in species_words for input_word in input_words):
            return species_name

    # Reverse partial match - species name contains any word from input
    for idx, species_name in enumerate(df["Common Name"]):
        species_lower = species_name.lower()
        input_words = input_lower.split()
        if any(word in species_lower for word in input_words):
            return species_name

    # Fallback mappings
    species_mappings = {
        "beech": "European beech",
        "oak": "European oak",
        "fir": "Silver fir",
        "silver fir": "Silver fir",
        "spruce": "Norway spruce",
        "pine": "Scots pine",
        "scots pine": "Scots pine",
        "birch": "Silver birch",
        "maple": "Field maple",
        "ash": "Common ash",
        "willow": "Willow",
        "poplar": "Grey poplar",
        "linden": "Small-leaved linden",
        "cherry": "Wild cherry",
        "chestnut": "Sweet chestnut",
        "hornbeam": "Hornbeam",
        "hazel": "Hazel",
        "elm": "Elm",
        "yew": "Yew",
    }

    if input_lower in species_mappings:
        mapped_name = species_mappings[input_lower]
        mapped_match = df[df["Common Name"].str.lower() == mapped_name.lower()]
        if not mapped_match.empty:
            return mapped_match.iloc[0]["Common Name"]

    return None


def get_available_species() -> List[str]:
    """Get list of all available species common names.

    Returns:
        List of common names
    """
    df = load_species_lookup()
    if df.empty:
        return []
    return df["Common Name"].tolist()


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Hex color string

    Returns:
        RGB tuple (0.0-1.0 range)
    """
    if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
        return (0.5, 0.5, 0.5)

    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return (r, g, b)


def get_species_colors(
    common_name: str,
) -> Optional[Dict[str, Tuple[float, float, float]]]:
    """Get branch and leaf colors for a given species.

    Args:
        common_name: Species common name

    Returns:
        Dictionary with 'branch_color' and 'leaf_color' as RGB tuples
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

    row = species_row.iloc[0]
    branch_hex = row.get("Branch Color", "#99664c")
    leaf_hex = row.get("Leaf Color", "#4c9933")

    return {"branch_color": hex_to_rgb(branch_hex), "leaf_color": hex_to_rgb(leaf_hex)}


def get_bark_texture(common_name: str) -> Optional[str]:
    """Get the standardized bark texture filename for a given species.

    Args:
        common_name: Species common name

    Returns:
        Standardized bark texture filename (e.g., "european_beech_bark.jpg") or None
    """
    df = load_species_lookup()
    if df.empty or "Bark Texture" not in df.columns:
        return None

    matched_name = find_species_match(common_name)
    if matched_name is None:
        return None

    species_row = df[df["Common Name"] == matched_name]
    if species_row.empty:
        return None

    bark_texture_original = species_row.iloc[0].get("Bark Texture")
    if pd.isna(bark_texture_original) or str(bark_texture_original) == "":
        return None

    # Return standardized name: "Beech60.jpg" -> "european_beech_bark.jpg"
    import re
    from pathlib import Path

    standardized_name = re.sub(r"[^\w\s-]", "", matched_name.lower())
    standardized_name = re.sub(r"[-\s]+", "_", standardized_name).strip("_")

    # Get file extension from original
    file_ext = Path(str(bark_texture_original)).suffix

    return f"{standardized_name}_bark{file_ext}"


def get_standardized_name(common_name: str) -> Optional[str]:
    """Get the standardized preset name for a species.

    Args:
        common_name: Species common name

    Returns:
        Standardized name (e.g., "european_beech") or None
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

    if "Standardized Name" in df.columns:
        return species_row.iloc[0].get("Standardized Name")

    # Fallback: generate from Common Name
    import re

    name = re.sub(r"[^\w\s-]", "", matched_name.lower())
    return re.sub(r"[-\s]+", "_", name).strip("_")


def get_species_data(common_name: str) -> Optional[dict]:
    """Get all species data for a given species as a dictionary.

    Args:
        common_name: Species common name

    Returns:
        Dictionary with all species data including colors
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

    row = species_row.iloc[0]
    species_dict = row.to_dict()

    colors = get_species_colors(common_name)
    if colors:
        species_dict.update(colors)

    return species_dict
