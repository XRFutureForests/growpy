"""Check if bpy package includes USD/pxr."""

import glob
import os

import bpy

bpy_path = os.path.dirname(bpy.__file__)
print(f"bpy installed at: {bpy_path}")

# Search for USD/pxr files
print("\nSearching for USD/pxr files in bpy directory...")
usd_files = glob.glob(
    os.path.join(bpy_path, "**", "*usd*"), recursive=True
) + glob.glob(os.path.join(bpy_path, "**", "*pxr*"), recursive=True)

print(f"Found {len(usd_files)} USD/pxr related files")
if usd_files:
    print("\nFirst 20 files:")
    for f in usd_files[:20]:
        print(f"  {f}")
else:
    print("No USD/pxr files found in bpy package")
    print("\nThis confirms pip bpy doesn't bundle USD")
    print("\nThis confirms pip bpy doesn't bundle USD")
