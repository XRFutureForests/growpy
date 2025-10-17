"""Quality presets and LOD configurations for GrowPy."""

from typing import Dict, Any


def get_all_lod_configs() -> Dict[str, Dict[str, Any]]:
    """Get all available Level of Detail (LOD) build configurations.

    Returns:
        Dict containing all LOD configurations
    """
    return {
        "LOD1_High": {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "build_end_cap": True,
        },
        "LOD2_Medium": {
            "resolution": 12,
            "resolution_reduce": 0.85,
            "texture_repeat": 2,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.01,
            "build_blend": True,
            "build_end_cap": False,
        },
        "LOD3_Low": {
            "resolution": 8,
            "resolution_reduce": 0.9,
            "texture_repeat": 2,
            "build_cutoff_age": 2,
            "build_cutoff_thickness": 0.02,
            "build_blend": False,
            "build_end_cap": False,
        },
    }


def get_lod_configs(lod_levels: list) -> Dict[str, Dict[str, Any]]:
    """Get filtered LOD build configurations based on lod_levels setting.

    Args:
        lod_levels: List of LOD level names or ["all"]

    Returns:
        Dict of requested LOD configurations
    """
    all_configs = get_all_lod_configs()

    if "all" in lod_levels:
        return all_configs

    filtered_configs = {}
    for lod_level in lod_levels:
        if lod_level in all_configs:
            filtered_configs[lod_level] = all_configs[lod_level]

    return filtered_configs
