"""Color-space helpers for species leaf/bark colors.

Shared between orchestrator-side code (e.g. ``unreal_scripts.py``)
and any module that needs to convert hex sRGB colors to linear RGBA
for Unreal Engine material assignment.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")


def srgb_to_linear(c: float) -> float:
    """Inverse sRGB EOTF (IEC 61966-2-1): sRGB float -> linear float."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(hex_str: str) -> tuple[float, float, float, float] | None:
    """Parse ``#RRGGBB[AA]`` hex (sRGB) and return linear ``(r, g, b, a)``.

    Alpha stays linear. Returns ``None`` if the string is empty or does
    not match the expected hex format.
    """
    if not hex_str:
        return None
    m = _HEX_RE.match(hex_str.strip())
    if not m:
        return None
    rgb_hex = m.group(1)
    alpha_hex = m.group(2)
    r = int(rgb_hex[0:2], 16) / 255.0
    g = int(rgb_hex[2:4], 16) / 255.0
    b = int(rgb_hex[4:6], 16) / 255.0
    a = int(alpha_hex, 16) / 255.0 if alpha_hex else 1.0
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


def load_species_colors() -> dict[str, dict[str, tuple[float, float, float, float]]]:
    """Load per-species leaf/bark linear-RGBA tuples from ``tree_asset_lookup.csv``.

    Returns:
        ``{standardized_name: {"leaf": (r,g,b,a), "bark": (r,g,b,a)}}``.
        Species with unparseable hex are skipped.
    """
    try:
        from growpy.config.paths import _get_lookup_table
    except Exception as e:
        logger.warning("Could not import lookup table helpers: %s", e)
        return {}

    try:
        df: Any = _get_lookup_table()
    except Exception as e:
        logger.warning("Could not load tree_asset_lookup.csv: %s", e)
        return {}

    out: dict[str, dict[str, tuple[float, float, float, float]]] = {}
    for _, row in df.iterrows():
        std = str(row.get("Standardized Name", "")).strip()
        if not std:
            continue
        leaf = hex_to_linear_rgba(str(row.get("Leaf Color", "") or ""))
        bark = hex_to_linear_rgba(str(row.get("Branch Color", "") or ""))
        if leaf is None and bark is None:
            continue
        out[std] = {}
        if leaf is not None:
            out[std]["leaf"] = leaf
        if bark is not None:
            out[std]["bark"] = bark
    return out
