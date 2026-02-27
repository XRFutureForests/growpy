"""Quality and LOD configuration for GrowPy."""

from typing import Any, Dict


_DEFAULT_PRESETS = {
    "ultra": {
        "resolution": 32,
        "resolution_reduce": 0.75,
        "texture_repeat": 4,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.0,
        "build_blend": True,
        "build_end_cap": True,
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
        "skeleton_length": 4.0,
        "skeleton_reduce": 0.8,
        "skeleton_bias": 0.5,
        "skeleton_connected": False,
    },
}


def _load_presets_from_toml() -> Dict[str, Dict[str, Any]]:
    """Load quality presets from growpy.toml [quality.*] sections.

    Falls back to hardcoded defaults if TOML is unavailable.
    """
    from .core import _find_toml_path

    toml_path = _find_toml_path()
    if not toml_path:
        return _DEFAULT_PRESETS

    import tomllib

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    quality_section = data.get("quality", {})
    if not quality_section:
        return _DEFAULT_PRESETS

    presets = {}
    for name, defaults in _DEFAULT_PRESETS.items():
        toml_values = quality_section.get(name, {})
        merged = {**defaults, **toml_values}
        presets[name] = merged

    return presets


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
    presets = _load_presets_from_toml()

    if preset_name not in presets:
        raise ValueError(
            f"Unknown quality preset: {preset_name}. Choose from: {list(presets.keys())}"
        )

    return presets[preset_name]
