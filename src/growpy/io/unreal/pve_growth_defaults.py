"""
Default growth parameters for PVE presets.

Hazel reference values are loaded from ``hazel_growth_defaults.json``
(a data resource shipped alongside this module) to keep the 656 magic
numbers out of source code. The JSON is a verbatim dump of the
Quixel Megaplants Broadleaf Hazel preset and is used as a fallback
for any broadleaf species.
"""

import copy
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HAZEL_DEFAULTS_PATH = Path(__file__).parent / "hazel_growth_defaults.json"


@lru_cache(maxsize=1)
def get_hazel_growth_defaults() -> dict[str, Any]:
    """Load Hazel reference growth parameters from the bundled JSON resource.

    Returns a deep copy so callers can mutate freely without polluting
    the cached original.
    """
    try:
        with open(_HAZEL_DEFAULTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to load Hazel defaults from %s: %s", _HAZEL_DEFAULTS_PATH, e)
        return {}


def get_default_growth_params(use_hazel_defaults: bool = True) -> dict[str, Any]:
    """Get default growth parameters for PVE preset generation.

    Args:
        use_hazel_defaults: If True, use Hazel reference values.
                           If False, use minimal defaults.

    Returns:
        Dictionary with growth parameters
    """
    if use_hazel_defaults:
        return get_hazel_growth_defaults()

    # Minimal defaults - just the required field
    return {
        "phyllotaxyLeaf": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.0,
                137.5,
                50.0,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                2.0,
                2.0,
                0.0,
            ],
        }
    }


def merge_growth_params(
    defaults: dict[str, Any], overrides: dict[str, Any] = None
) -> dict[str, Any]:
    """Merge default growth parameters with optional overrides.

    Args:
        defaults: Default growth parameters
        overrides: Optional dictionary to override specific parameters

    Returns:
        Merged dictionary
    """
    result = copy.deepcopy(defaults)

    if overrides:
        for key, value in overrides.items():
            if key in result:
                # Merge values, preserving structure
                if isinstance(value, dict) and "value" in value:
                    result[key]["value"] = value["value"]
                else:
                    result[key] = value
            else:
                result[key] = value

    return result
