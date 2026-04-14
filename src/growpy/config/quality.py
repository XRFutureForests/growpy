"""Quality and LOD configuration for GrowPy.

Quality presets are defined in quality.toml under [quality.<name>] sections.
A single hardcoded default is used as fallback when a key is missing from TOML
or when no TOML file is found.
"""

from typing import Any, Dict

# Fallback values when a TOML preset omits a key.
# Based on Grove 2.3 defaults from Properties.py and OperatorBuildSkeleton.py.
_DEFAULT = {
    "resolution": 16,
    "resolution_reduce": 0.78,
    "build_cutoff_age": 0,
    "build_cutoff_thickness": 0.0,
    "build_blend": True,
    "build_end_cap": True,
    "skeleton_length": 2.0,
    "skeleton_reduce": 0.4,
    "skeleton_bias": 0.5,
    "skeleton_connected": True,
}


def _load_presets_from_toml() -> Dict[str, Dict[str, Any]]:
    """Load quality presets from TOML [quality.*] sections.

    Uses the same multi-file loader as the main config so that presets
    defined in any *.toml file inside the resolved config directory are discovered.
    Each TOML preset is merged with _DEFAULT so that any omitted key
    gets a sensible fallback value.  If no TOML file is found a single
    preset named "default" is returned.
    """
    from .core import _find_config_dir, _load_toml_data

    cfg_dir = _find_config_dir()
    if not cfg_dir:
        return {"default": dict(_DEFAULT)}

    data = _load_toml_data(cfg_dir)

    quality_section = data.get("quality", {})
    if not quality_section:
        return {"default": dict(_DEFAULT)}

    presets = {}
    for name, toml_values in quality_section.items():
        presets[name] = {**_DEFAULT, **toml_values}

    return presets


def get_quality_preset(preset_name: str) -> Dict[str, Any]:
    """Get a named quality preset for tree model building.

    Presets are defined in config/quality.toml under [quality.<name>].
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
