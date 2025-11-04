"""Quality and LOD configuration for GrowPy."""

from typing import Any, Dict


def get_quality_preset(preset_name: str) -> Dict[str, Any]:
    """Get predefined quality preset for tree model building.

    Args:
        preset_name: One of 'ultra', 'high', 'medium', 'low', 'performance'

    Returns:
        Dictionary with build quality parameters

    Quality Presets:
        ultra:       32 vertices, maximum detail
        high:        24 vertices, high detail
        medium:      16 vertices, balanced
        low:         12 vertices, reduced detail
        performance: 8 vertices, minimal detail
    """
    presets = {
        "ultra": {
            "resolution": 32,
            "resolution_reduce": 0.75,
            "texture_repeat": 4,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "build_end_cap": True,
        },
        "high": {
            "resolution": 24,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.001,
            "build_blend": True,
            "build_end_cap": True,
        },
        "medium": {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.005,
            "build_blend": True,
            "build_end_cap": True,
        },
        "low": {
            "resolution": 12,
            "resolution_reduce": 0.85,
            "texture_repeat": 2,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.01,
            "build_blend": True,
            "build_end_cap": False,
        },
        "performance": {
            "resolution": 8,
            "resolution_reduce": 0.9,
            "texture_repeat": 2,
            "build_cutoff_age": 2,
            "build_cutoff_thickness": 0.02,
            "build_blend": False,
            "build_end_cap": False,
        },
    }

    if preset_name not in presets:
        raise ValueError(
            f"Unknown quality preset: {preset_name}. Choose from: {list(presets.keys())}"
        )

    return presets[preset_name]
