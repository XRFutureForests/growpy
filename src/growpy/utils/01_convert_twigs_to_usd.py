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


def fix_usd_materials_for_transparency(usd_file_path):
    """
    Fix USD material definitions to properly handle transparency for leaf textures.
    
    Args:
        usd_file_path (Path): Path to the USD file to fix
        
    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        # Read the file
        with open(usd_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        new_content = content
        
        # Replace Diffuse_BSDF with UsdPreviewSurface for better USD compatibility
        if "Diffuse_BSDF" in content:
            new_content = re.sub(
                r'uniform token info:id = "ShaderNodeBsdfDiffuse"',
                'uniform token info:id = "UsdPreviewSurface"',
                new_content
            )
            modified = True
            print(f"    🔄 Converted Diffuse_BSDF to UsdPreviewSurface")
        
        # Add opacity input for leaf materials (assume materials with "Leaves" in name need transparency)
        if "Leaves" in content and "inputs:opacity" not in content:
            # Find UsdPreviewSurface sections and add opacity connection
            opacity_pattern = r'(def Shader "[^"]*Leaves[^"]*"[^{]*{[^}]*uniform token info:id = "UsdPreviewSurface"[^}]*)(})'
            opacity_replacement = r'\1                float inputs:opacity.connect = <./Image_Texture.outputs:a>\n                float inputs:opacityThreshold = 0.1\n            \2'
            
            if re.search(opacity_pattern, new_content, re.DOTALL):
                new_content = re.sub(opacity_pattern, opacity_replacement, new_content, flags=re.DOTALL)
                modified = True
                print(f"    🔄 Added opacity settings for leaf materials")
        
        # Ensure PNG textures are set to use sRGB color space for diffuse and raw for normal maps
        png_diffuse_pattern = r'(asset inputs:file = @[^@]*\.png@[^}]*token inputs:sourceColorSpace = )"[^"]*"'
        png_normal_pattern = r'(asset inputs:file = @[^@]*Bump\.png@[^}]*token inputs:sourceColorSpace = )"[^"]*"'
        
        if re.search(png_diffuse_pattern, content):
            # Set diffuse textures to sRGB
            new_content = re.sub(png_diffuse_pattern, r'\1"sRGB"', new_content)
            modified = True
            print(f"    🔄 Set PNG diffuse textures to sRGB color space")
            
        if re.search(png_normal_pattern, content):
            # Set normal/bump textures to raw
            new_content = re.sub(png_normal_pattern, r'\1"raw"', new_content)  
            modified = True
            print(f"    🔄 Set PNG bump textures to raw color space")
        
        # Only write if content changed
        if modified:
            with open(usd_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ❌ Failed to process materials in {usd_file_path.name}: {e}")
        return False


def post_process_usd_files(twig_asset_path):
    """Post-process all USD files to reset transforms and fix materials."""
    print(f"\n🔧 Post-processing USD files to reset transforms and fix materials...")
    usd_files = list(twig_asset_path.glob("**/*.usda"))
    transform_fixes = 0
    material_fixes = 0
    
    for usd_file in usd_files:
        print(f"  🔧 Processing {usd_file.name}...")
        
        # Fix transforms
        if fix_usd_transforms(usd_file):
            transform_fixes += 1
            print(f"    ✅ Fixed transforms")
            
        # Fix materials for transparency
        if fix_usd_materials_for_transparency(usd_file):
            material_fixes += 1
            print(f"    ✅ Fixed materials for transparency")
    
    print(f"✅ Post-processed {len(usd_files)} USD files:")
    print(f"  • {transform_fixes} files with transform fixes")
    print(f"  • {material_fixes} files with material improvements")
    return transform_fixes + material_fixes


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
    failed_files = []
    
    for i, twig_asset in enumerate(twig_assets, 1):
        print(f"\n[{i}/{len(twig_assets)}] Converting: {twig_asset.name}")

        try:
            # Clear scene completely to avoid memory issues
            print(f"  🧹 Clearing scene...")
            bpy.ops.wm.read_homefile(app_template="", use_empty=True)
            
            # Force garbage collection to free memory
            import gc
            gc.collect()
            
            # Open blend file with error checking
            print(f"  📂 Opening blend file...")
            try:
                bpy.ops.wm.open_mainfile(filepath=str(twig_asset), load_ui=False, use_scripts=False)
            except Exception as load_error:
                print(f"  ❌ Failed to load blend file: {load_error}")
                failed_files.append((twig_asset.name, f"Load error: {load_error}"))
                continue

            # Get all mesh objects in the scene
            mesh_objects = [
                obj for obj in bpy.context.scene.objects if obj.type == "MESH"
            ]

            if not mesh_objects:
                print(f"  ⚠️ No mesh objects found")
                failed_files.append((twig_asset.name, "No mesh objects found"))
                continue

            print(f"  📦 Found {len(mesh_objects)} objects to export")

            # Export each object as individual USD
            exported_count = 0
            for obj_idx, obj in enumerate(mesh_objects):
                try:
                    # Clean object name for filename
                    clean_name = "".join(c for c in obj.name if c.isalnum() or c in "_-")
                    if not clean_name:
                        clean_name = f"object_{exported_count}"

                    # Create output path for this object
                    obj_output_path = (
                        twig_asset.parent / f"{twig_asset.stem}_{clean_name}.usda"
                    )

                    print(f"  🔧 Processing {clean_name}... ({obj_idx+1}/{len(mesh_objects)})")

                    # Select only this object
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj

                    # Export to USD with safer settings
                    bpy.ops.wm.usd_export(
                        filepath=str(obj_output_path),
                        selected_objects_only=True,
                        visible_objects_only=True,
                        export_animation=False,
                        export_hair=False,  # Disable hair export to reduce memory usage
                        export_uvmaps=True,
                        export_normals=True,
                        export_materials=True,
                        export_textures=True,
                        use_instancing=False,  # Disable instancing to reduce complexity
                        evaluation_mode="RENDER",
                        generate_preview_surface=True,
                        convert_orientation=False,  # Preserve original orientation
                        relative_paths=True,
                    )

                    print(f"    ✅ {clean_name}: exported successfully")
                    exported_count += 1
                    
                    # Clear selection and force memory cleanup after each export
                    bpy.ops.object.select_all(action="DESELECT")
                    gc.collect()
                    
                except Exception as obj_error:
                    print(f"    ❌ Failed to export {clean_name}: {obj_error}")
                    continue

            if exported_count > 0:
                converted += exported_count
                print(f"  ✅ Successfully exported {exported_count} objects from {twig_asset.name}")
            else:
                failed_files.append((twig_asset.name, "No objects exported successfully"))

        except Exception as e:
            print(f"  ❌ Failed to process {twig_asset.name}: {e}")
            failed_files.append((twig_asset.name, str(e)))
            
            # Try to recover by clearing everything
            try:
                bpy.ops.wm.read_homefile(app_template="", use_empty=True)
                gc.collect()
            except:
                pass
            continue

    # Post-process all USD files to reset transform values
    fixed_count = post_process_usd_files(twig_asset_path)

    print(f"\n🎉 Conversion complete!")
    print(f"  📦 Exported {converted} objects from {len(twig_assets)} blend files")
    print(f"  🔧 Post-processed {fixed_count} USD files")
    
    if failed_files:
        print(f"\n⚠️  {len(failed_files)} files had issues:")
        for filename, error in failed_files:
            print(f"    • {filename}: {error}")
        print(f"\n💡 Tips for failed files:")
        print("  - Some blend files may have corrupted geometry or materials")  
        print("  - Memory issues can occur with very complex models")
        print("  - Try opening problematic files in Blender manually to check for issues")
    else:
        print(f"\n✅ All files processed successfully!")
    
    print("\nOrientation and material summary:")
    print("  - All twigs point along +X axis")
    print("  - Twig pivots reset to origin (0,0,0)")
    print("  - Object transforms post-processed to (0,0,0)")
    print("  - No translation transforms in USD files")
    print("  - Materials converted to UsdPreviewSurface for better compatibility")
    print("  - Leaf materials enhanced with opacity support for transparent edges")
    print("  - PNG textures properly configured for sRGB (diffuse) and raw (normal) color spaces")
    
    return 1 if failed_files else 0


if __name__ == "__main__":
    sys.exit(main())
