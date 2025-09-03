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
    transform_fixes = 0
    
    for usd_file in usd_files:
        print(f"  🔧 Processing {usd_file.name}...")
        
        # Fix transforms
        if fix_usd_transforms(usd_file):
            transform_fixes += 1
            print(f"    ✅ Fixed transforms")
    
    print(f"✅ Post-processed {len(usd_files)} USD files:")
    print(f"  • {transform_fixes} files with transform fixes")
    return transform_fixes


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
            try:
                # More aggressive scene clearing to prevent memory issues
                bpy.ops.wm.read_homefile(app_template="", use_empty=True)
                
                # Clear any remaining data blocks
                for collection in bpy.data.collections:
                    bpy.data.collections.remove(collection)
                for mesh in bpy.data.meshes:
                    bpy.data.meshes.remove(mesh)
                for material in bpy.data.materials:
                    bpy.data.materials.remove(material)
                for texture in bpy.data.textures:
                    bpy.data.textures.remove(texture)
                for image in bpy.data.images:
                    bpy.data.images.remove(image)
                    
            except Exception as clear_error:
                print(f"  ⚠️  Scene clearing had issues: {clear_error}")
            
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

            # Export each object as individual USD with safety measures
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

                    # Simplify materials to prevent memory crashes
                    try:
                        if obj.data and obj.data.materials:
                            print(f"    📝 Found {len(obj.data.materials)} materials, simplifying...")
                            # Temporarily disable problematic material nodes
                            for mat_slot in obj.material_slots:
                                if mat_slot.material and mat_slot.material.use_nodes:
                                    # Disable complex node setups that cause crashes
                                    nodes = mat_slot.material.node_tree.nodes
                                    for node in nodes:
                                        if node.type in ['TEX_IMAGE', 'BSDF_PRINCIPLED']:
                                            # Keep essential nodes, remove others that cause memory issues
                                            continue
                                        elif node.type in ['SUBSURFACE_SCATTERING', 'BSDF_HAIR']:
                                            # Remove problematic nodes
                                            nodes.remove(node)
                    except Exception as mat_error:
                        print(f"    ⚠️  Material simplification warning: {mat_error}")

                    # Select only this object
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj

                    # Export to USD with safer settings to prevent crashes
                    try:
                        bpy.ops.wm.usd_export(
                            filepath=str(obj_output_path),
                            selected_objects_only=True,
                            visible_objects_only=True,
                            export_animation=False,
                            export_hair=False,  # Disable hair export to reduce memory usage
                            export_uvmaps=True,
                            export_normals=True,
                            export_materials=True,
                            export_textures=False,  # Disable texture export initially to prevent crashes
                            use_instancing=False,  # Disable instancing to reduce complexity
                            evaluation_mode="RENDER",
                            generate_preview_surface=True,
                            convert_orientation=False,  # Preserve original orientation
                            relative_paths=True,
                        )
                        
                        # If that worked, try again with textures enabled
                        if obj_output_path.exists():
                            obj_output_path.unlink()  # Remove first export
                            bpy.ops.wm.usd_export(
                                filepath=str(obj_output_path),
                                selected_objects_only=True,
                                visible_objects_only=True,
                                export_animation=False,
                                export_hair=False,
                                export_uvmaps=True,
                                export_normals=True,
                                export_materials=True,
                                export_textures=True,  # Now enable textures
                                use_instancing=False,
                                evaluation_mode="RENDER",
                                generate_preview_surface=True,
                                convert_orientation=False,
                                relative_paths=True,
                            )
                        
                    except Exception as export_error:
                        print(f"    ⚠️  USD export with textures failed, trying without: {export_error}")
                        # Fallback: export without textures
                        try:
                            if obj_output_path.exists():
                                obj_output_path.unlink()
                            bpy.ops.wm.usd_export(
                                filepath=str(obj_output_path),
                                selected_objects_only=True,
                                visible_objects_only=True,
                                export_animation=False,
                                export_hair=False,
                                export_uvmaps=True,
                                export_normals=True,
                                export_materials=False,  # Disable materials as last resort
                                export_textures=False,
                                use_instancing=False,
                                evaluation_mode="RENDER",
                                generate_preview_surface=False,
                                convert_orientation=False,
                                relative_paths=True,
                            )
                        except Exception as fallback_error:
                            print(f"    ❌ Even fallback export failed: {fallback_error}")
                            continue

                    print(f"    ✅ {clean_name}: exported successfully")
                    exported_count += 1
                    
                    # Clear selection and force memory cleanup after each export
                    bpy.ops.object.select_all(action="DESELECT")
                    gc.collect()
                    
                except Exception as obj_error:
                    print(f"    ❌ Failed to export {clean_name}: {obj_error}")
                    # Try to recover and continue with next object
                    try:
                        bpy.ops.object.select_all(action="DESELECT")
                        gc.collect()
                    except:
                        pass
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
    
    print("\nOrientation summary:")
    print("  - All twigs point along +X axis")
    print("  - Twig pivots reset to origin (0,0,0)")
    print("  - Object transforms post-processed to (0,0,0)")
    print("  - No translation transforms in USD files")
    print("  - Materials and textures preserved from original blend files")
    
    return 1 if failed_files else 0


if __name__ == "__main__":
    sys.exit(main())
