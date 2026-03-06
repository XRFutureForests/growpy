"""Quality and LOD configuration for GrowPy.

Quality presets are defined in growpy.toml under [quality.<name>] sections.
A single hardcoded default is used as fallback when a key is missing from TOML
or when no TOML file is found.
"""

from typing import Any, Dict

# Fallback values used when a TOML preset omits a key (based on "high" profile).
_DEFAULT = {
    "resolution": 24,
    "resolution_reduce": 0.8,
    "build_cutoff_age": 0,
    "build_cutoff_thickness": 0.01,
    "build_blend": True,
    "build_end_cap": True,
    "skeleton_length": 0.25,
    "skeleton_reduce": 0.2,
    "skeleton_bias": 0.5,
    "skeleton_connected": True,
}


def _load_presets_from_toml() -> Dict[str, Dict[str, Any]]:
    """Load quality presets from growpy.toml [quality.*] sections.

    Each TOML preset is merged with _DEFAULT so that any omitted key
    gets a sensible fallback value.  If no TOML file is found a single
    preset named "default" is returned.
    """
    from .core import _find_toml_path

    toml_path = _find_toml_path()
    if not toml_path:
        return {"default": dict(_DEFAULT)}

    import tomllib

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    quality_section = data.get("quality", {})
    if not quality_section:
        return {"default": dict(_DEFAULT)}

    presets = {}
    for name, toml_values in quality_section.items():
        presets[name] = {**_DEFAULT, **toml_values}

    return presets


def get_quality_preset(preset_name: str) -> Dict[str, Any]:
    """Get a named quality preset for tree model building.

    Presets are defined in growpy.toml under [quality.<name>].
    Missing keys fall back to the built-in default (high-quality profile).

    WARNING: Unreal Engine uses 16-bit signed integers for bone indices.
        Maximum bone count is 32,767. Exceeding this causes crashes.
        Use higher skeleton_length/skeleton_reduce for large trees.
    """
    presets = _load_presets_from_toml()

    if preset_name not in presets:
        raise ValueError(
            f"Unknown quality preset: {preset_name}. "
            f"Choose from: {list(presets.keys())}"
        )

    return presets[preset_name]
