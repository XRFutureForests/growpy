#!/usr/bin/env python3
"""
Simple Blender twig to USD conversion with proper Y-up orientation.

This script opens each .blend file in the twigs directory and exports each object as an individual USD file.
All twig USD files are exported with upAxis="Y" to match the tree coordinate system.

Usage:
    python 01_convert_twigs_to_usd.py

Prerequisites:
    - Blender bpy module available in environment
    - Twig .blend files in the expected directory structure

The script uses Blender's built-in convert_orientation feature to ensure proper Y-up coordinate system.
"""
import sys
from pathlib import Path

import bpy


def main():
    """Simple twig to USD conversion - exports each object individually with Y-up orientation."""
    print("🔄 Converting Blender twigs to USD")
    print("=" * 30)

    # Fixed paths
    twig_asset_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "assets" / "twigs"
    )

    if not twig_asset_path.exists():
        print(f"❌ Twig assets path not found: {twig_asset_path}")
        return 1

    # Find all .blend files
    twig_assets = list(twig_asset_path.glob("**/*.blend"))
    print(f"� Found {len(twig_assets)} .blend files to convert")

    converted = 0
    for i, twig_asset in enumerate(twig_assets, 1):
        print(f"\n[{i}/{len(twig_assets)}] Converting: {twig_asset.name}")

        output_path = twig_asset.with_suffix(".usda")

        # Skip if already converted
        if output_path.exists():
            print(f"  ✅ Already exists")
            converted += 1
            continue

        try:
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

                # Force overwrite existing files to apply new orientation
                print(f"    🔄 Exporting {clean_name}...")

                try:
                    # Select only this object
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj

                    # Export with Y-up axis to match tree coordinate system
                    # Set forward to +X so twigs point directly along X-axis (standard twig orientation)
                    # This should make twigs point in +X direction with +Y up

                    # Export this object to USD with comprehensive material/texture export
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
                        export_armatures=True,
                        export_shapekeys=True,
                        use_instancing=True,
                        evaluation_mode="RENDER",
                        generate_preview_surface=True,
                        convert_orientation=True,
                        export_global_up_selection="Y",
                        export_global_forward_selection="X",
                        relative_paths=True,
                    )

                    print(
                        f"    ✅ {clean_name}: exported with upAxis=Y and full materials"
                    )

                    exported_count += 1

                except Exception as obj_e:
                    print(f"    ❌ {clean_name}: failed - {obj_e}")

            converted += exported_count

        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print(
        f"\n🎉 Conversion complete! Exported {converted} individual objects as USD files"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
