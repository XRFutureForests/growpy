"""Shared Blender and Grove utilities for export modules."""

import bpy

try:
    bpy.utils.expose_bundled_modules()
    BPY_AVAILABLE = True
except (ImportError, OSError, AttributeError):
    bpy = None
    BPY_AVAILABLE = False

import the_grove_22_core as gc


def check_bpy_available() -> bool:
    """Check if bpy is available at runtime.

    Returns:
        True if Blender Python API is available
    """
    return BPY_AVAILABLE


def get_bpy():
    """Get bpy module if available.

    Returns:
        bpy module or None
    """
    return bpy if BPY_AVAILABLE else None
