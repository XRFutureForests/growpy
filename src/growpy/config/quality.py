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

    Note:
        build_cutoff_age and build_cutoff_thickness work with skeletal meshes.
        The skeleton is automatically filtered to only include bones that are
        referenced by the mesh geometry after cutoff is applied.

    Skeleton Parameters:
        skeleton_length: Bone length multiplier (0-5). Higher = fewer, longer bones.
        skeleton_reduce: Thickness threshold (0-1). Higher = skip thinner branches.
        skeleton_bias: Bone distribution (0-1). Higher = more bones near tips.
        skeleton_connected: If True, creates connected bone chains (more bones).

    WARNING: Unreal Engine uses 16-bit signed integers for bone indices.
        Maximum bone count is 32,767. Exceeding this causes crashes.
        Use higher skeleton_length/skeleton_reduce for large trees.
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
            # Skeleton: minimal reduction for maximum detail
            "skeleton_length": 0.1,
            "skeleton_reduce": 0.1,
            "skeleton_bias": 0.5,
            "skeleton_connected": True,
        },
        "high": {
            "resolution": 24,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.01,
            "build_blend": True,
            "build_end_cap": True,
            # Skeleton: light reduction
            "skeleton_length": 0.25,
            "skeleton_reduce": 0.2,
            "skeleton_bias": 0.5,
            "skeleton_connected": True,
        },
        "medium": {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.01,
            "build_blend": True,
            "build_end_cap": True,
            # Skeleton: balanced (Grove default values)
            "skeleton_length": 2.0,
            "skeleton_reduce": 0.4,
            "skeleton_bias": 0.5,
            "skeleton_connected": True,
        },
        "low": {
            "resolution": 12,
            "resolution_reduce": 0.85,
            "texture_repeat": 2,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.05,
            "build_blend": True,
            "build_end_cap": False,
            # Skeleton: aggressive reduction
            "skeleton_length": 3.0,
            "skeleton_reduce": 0.6,
            "skeleton_bias": 0.5,
            "skeleton_connected": True,
        },
        "performance": {
            "resolution": 8,
            "resolution_reduce": 0.9,
            "texture_repeat": 2,
            "build_cutoff_age": 2,
            "build_cutoff_thickness": 0.05,
            "build_blend": False,
            "build_end_cap": False,
            # Skeleton: maximum reduction for large trees
            "skeleton_length": 4.0,
            "skeleton_reduce": 0.8,
            "skeleton_bias": 0.5,
            "skeleton_connected": False,
        },
    }

    if preset_name not in presets:
        raise ValueError(
            f"Unknown quality preset: {preset_name}. Choose from: {list(presets.keys())}"
        )

    return presets[preset_name]
