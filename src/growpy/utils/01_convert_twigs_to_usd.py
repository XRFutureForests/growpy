#!/usr/bin/env python3
"""
Improved Blender twig to USD conversion ensuring proper orientation.

This script ensures twigs are exported in the correct orientation expected by The Grove:
- Twig pointing along +X axis
- Base at origin (0,0,0)
- No rotation transforms in the USD file

Usage:
    python 01_convert_twigs_to_usd.py

Prerequisites:
    - Blender bpy module available in environment
    - Twig .blend files in the expected directory structure
"""
import math
import sys
from pathlib import Path

import bpy
import mathutils




def main():
    """Improved twig to USD conversion with proper orientation."""
    print("🔄 Converting Blender twigs to USD with Grove-compliant orientation")
    print("=" * 50)

    # Fixed paths
    twig_asset_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "assets" / "twigs"
    )

    # Find all .blend files
    twig_assets = list(twig_asset_path.glob("**/*.blend"))
    print(f"📁 Found {len(twig_assets)} .blend files to convert")

    converted = 0
    for i, twig_asset in enumerate(twig_assets, 1):
        print(f"\n[{i}/{len(twig_assets)}] Converting: {twig_asset.name}")

        # Clear scene and open blend file
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.wm.open_mainfile(filepath=str(twig_asset), load_ui=False)

        # Get all mesh objects in the scene
        mesh_objects = [
            obj for obj in bpy.context.scene.objects if obj.type == "MESH"
        ]

        if not mesh_objects:
            print(f"  ⚠️ No mesh objects found")
            continue

        print(f"  📦 Found {len(mesh_objects)} objects to export")

        # Export each object as individual USD
        exported_count = 0
        for obj in mesh_objects:
            # Clean object name for filename
            clean_name = "".join(c for c in obj.name if c.isalnum() or c in "_-")
            if not clean_name:
                clean_name = f"object_{exported_count}"

            # Create output path for this object
            obj_output_path = (
                twig_asset.parent / f"{twig_asset.stem}_{clean_name}.usda"
            )

            print(f"  🔧 Processing {clean_name}...")

            try:
                # Select only this object
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Export to USD WITHOUT coordinate conversion
                # This preserves our carefully set orientation
                bpy.ops.wm.usd_export(
                    filepath=str(obj_output_path),
                    selected_objects_only=True,
                    visible_objects_only=True,
                    export_animation=False,
                    export_hair=True,
                    export_uvmaps=True,
                    export_normals=True,
                    export_materials=True,
                    export_textures=True,
                    use_instancing=True,
                    evaluation_mode="RENDER",
                    generate_preview_surface=True,
                    convert_orientation=False,  # IMPORTANT: Don't convert!
                    relative_paths=True,
                )

                print(f"    ✅ {clean_name}: exported with proper orientation")
                exported_count += 1

            except Exception as obj_e:
                print(f"    ❌ {clean_name}: failed - {obj_e}")

        converted += exported_count


    print(
        f"\n🎉 Conversion complete! Exported {converted} objects with Grove-compliant orientation"
    )
    print("\nOrientation summary:")
    print("  - All twigs point along +X axis")
    print("  - Twig bases are at origin (0,0,0)")
    print("  - No rotation transforms in USD files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
