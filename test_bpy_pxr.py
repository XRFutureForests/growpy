"""Test if bpy's bundled pxr is accessible."""

import sys

import bpy

print(f"bpy version: {bpy.app.version_string}")
print(f"\nPython paths after importing bpy:")

# Check for Blender-related paths
blender_paths = [p for p in sys.path if "blender" in p.lower() or "bpy" in p.lower()]
for path in blender_paths:
    print(f"  {path}")

print("\nAttempting to import pxr...")
try:
    from pxr import Usd

    print(f"SUCCESS: pxr imported from bundled Blender!")
    print(f"USD version: {Usd.GetVersion()}")
except ImportError as e:
    print(f"FAILED: {e}")
    print("\nSearching for pxr in sys.path...")
    import os

    for path in sys.path:
        pxr_path = os.path.join(path, "pxr")
        if os.path.exists(pxr_path):
            print(f"  Found pxr at: {pxr_path}")
            print(f"  Found pxr at: {pxr_path}")
