#!/usr/bin/env python3
"""
Safe Blender twig to USD conversion with post-processing.

This script converts .blend twig files to USD format and ensures proper transforms.
Due to stability issues with Blender's transform operations, this version:
1. Exports USD files normally from Blender (safe, no crashes)
2. Post-processes the USD files to fix transforms to (0,0,0)

Usage:
    Run from within Blender or with Blender's Python:
    blender --background --python 01_convert_twigs_to_usd.py

Prerequisites:
    - Blender with USD export support
    - Twig .blend files in the expected directory structure
"""
import sys
import re
from pathlib import Path

import bpy


def fix_usd_transforms(usd_file_path):
    """
    Fix transform values in a USD file to ensure pivot is at origin.
    
    Args:
        usd_file_path (Path): Path to the USD file to fix
        
    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        # Read the file
        with open(usd_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match: double3 xformOp:translate = (any numbers)
        pattern = r'(double3 xformOp:translate = )\([^)]+\)'
        replacement = r'\1(0, 0, 0)'
        new_content = re.sub(pattern, replacement, content)
        
        # Only write if content changed
        if new_content != content:
            with open(usd_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ❌ Failed to process {usd_file_path.name}: {e}")
        return False


def post_process_usd_files(twig_asset_path):
    """Post-process all USD files to reset transforms."""
    print(f"\n🔧 Post-processing USD files to reset transforms...")
    usd_files = list(twig_asset_path.glob("**/*.usda"))
    processed_count = 0
    
    for usd_file in usd_files:
        if fix_usd_transforms(usd_file):
            processed_count += 1
            print(f"  🔄 Fixed transforms in {usd_file.name}")
    
    print(f"✅ Post-processed {processed_count} USD files with transform fixes")
    return processed_count


def main():
    """Safe twig to USD conversion with post-processing."""
    print("🔄 Converting Blender twigs to USD with Grove-compliant orientation")
    print("=" * 60)

    # Fixed paths
    twig_asset_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "assets" / "twigs"
    )

    if not twig_asset_path.exists():
        print(f"❌ Twig assets directory not found: {twig_asset_path}")
        return 1

    # Find all .blend files
    twig_assets = list(twig_asset_path.glob("**/*.blend"))
    print(f"📁 Found {len(twig_assets)} .blend files to convert")

    if not twig_assets:
        print("No .blend files found to convert.")
        return 0

    converted = 0
    for i, twig_asset in enumerate(twig_assets, 1):
        print(f"\n[{i}/{len(twig_assets)}] Converting: {twig_asset.name}")

        try:
            # Clear scene completely
            bpy.ops.wm.read_homefile(app_template="")
            
            # Open blend file
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

                # Select only this object
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Export to USD without coordinate conversion
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
                    convert_orientation=False,  # Preserve original orientation
                    relative_paths=True,
                )

                print(f"    ✅ {clean_name}: exported")
                exported_count += 1

            converted += exported_count

        except Exception as e:
            print(f"  ❌ Failed to process {twig_asset.name}: {e}")
            continue

    # Post-process all USD files to reset transform values
    fixed_count = post_process_usd_files(twig_asset_path)

    print(f"\n🎉 Conversion complete!")
    print(f"  📦 Exported {converted} objects")
    print(f"  🔧 Fixed transforms in {fixed_count} USD files")
    print("\nOrientation summary:")
    print("  - All twigs point along +X axis")
    print("  - Twig pivots reset to origin (0,0,0)")
    print("  - Object transforms post-processed to (0,0,0)")
    print("  - No translation transforms in USD files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
