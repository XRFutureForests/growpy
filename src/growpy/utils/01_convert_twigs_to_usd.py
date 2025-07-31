#!/usr/bin/env python3
"""
Simple Blender twig to USD conversion.

This script opens each .blend file in the twigs directory and exports each object as an individual USD file.
Run this script from within Blender:
    blender --background --python 01_convert_twigs_to_usd.py
"""
import sys
from pathlib import Path

import bpy


def main():
    """Simple twig to USD conversion - exports each object individually."""
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
            mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
            
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
                obj_output_path = twig_asset.parent / f"{twig_asset.stem}_{clean_name}.usda"
                
                # Skip if already exists
                if obj_output_path.exists():
                    print(f"    ✅ {clean_name}: already exists")
                    exported_count += 1
                    continue
                
                try:
                    # Select only this object
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    
                    # Export this object to USD
                    bpy.ops.wm.usd_export(
                        filepath=str(obj_output_path),
                        selected_objects_only=True,
                        visible_objects_only=True,
                        export_animation=False,
                        export_uvmaps=True,
                        export_materials=True,
                        export_textures=True,
                        relative_paths=True,
                    )
                    
                    print(f"    ✅ {clean_name}: exported")
                    exported_count += 1
                    
                except Exception as obj_e:
                    print(f"    ❌ {clean_name}: failed - {obj_e}")

            converted += exported_count

        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print(f"\n🎉 Conversion complete! Exported {converted} individual objects as USD files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
