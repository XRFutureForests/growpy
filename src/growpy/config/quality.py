"""Quality and LOD configuration for GrowPy."""

from typing import Dict, List


def get_lod_configs(lod_levels: List[str]) -> Dict[str, Dict[str, any]]:
    """Get LOD configuration settings.

    Args:
        lod_levels: List of LOD level names or ["all"]

    Returns:
        Dict mapping LOD names to config dicts
    """
    # Define standard LOD presets
    lod_presets = {
        "ultra": {
            "resolution": 32,
            "resolution_reduce": 0.9,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "detail_level": "maximum",
        },
        "high": {
            "resolution": 24,
            "resolution_reduce": 0.8,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.01,
            "detail_level": "high",
        },
        "medium": {
            "resolution": 16,
            "resolution_reduce": 0.7,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.02,
            "detail_level": "medium",
        },
        "low": {
            "resolution": 12,
            "resolution_reduce": 0.6,
            "build_cutoff_age": 2,
            "build_cutoff_thickness": 0.03,
            "detail_level": "low",
        },
        "performance": {
            "resolution": 8,
            "resolution_reduce": 0.5,
            "build_cutoff_age": 3,
            "build_cutoff_thickness": 0.05,
            "detail_level": "minimal",
        },
    }

    # If "all" is in lod_levels, return all presets
    if "all" in lod_levels:
        return lod_presets

    # Otherwise return only requested levels
    return {level: lod_presets[level] for level in lod_levels if level in lod_presets}
