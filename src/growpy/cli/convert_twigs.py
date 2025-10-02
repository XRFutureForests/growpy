#!/usr/bin/env python3
"""
Convert Grove twig .blend files to FBX and/or USD format with optimized materials.

This script processes twig blend files and exports them with:
- Proper texture mapping (diffuse, alpha, normal, translucent)
- USD-compatible Principled BSDF materials
- FBX export with embedded textures (better material fidelity)
- Unreal Engine 5 Nanite support
- Automatic texture discovery and classification
- Objects centered at origin (0,0,0)
- Support for varied texture naming conventions

Usage:
    python convert_twigs.py <twig_directory> [--formats fbx usd usda]
    python convert_twigs.py <single_blend_file> [--formats fbx]

Examples:
    python convert_twigs.py data/assets/twigs                    # FBX + USDA (default)
    python convert_twigs.py data/assets/twigs --formats fbx      # FBX only
    python convert_twigs.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechSummerTwig.blend
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script optimized for USD export."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path
from typing import List

def center_object_at_origin(obj):
    """Move object to origin (0,0,0)."""
    import bpy

    obj.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Centered {obj.name} at origin")

def find_available_textures(blend_dir):
    """Find all texture files."""
    texture_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.hdr', '.bmp']
    textures = []

    for ext in texture_extensions:
        textures.extend(blend_dir.rglob(f"*{ext}"))
        textures.extend(blend_dir.rglob(f"*{ext.upper()}"))

    return textures

def classify_texture_type(filename):
    """Classify texture type for USD optimization."""
    name_lower = filename.lower()

    # Handle specific patterns
    if 'bump' in name_lower:
        return 'normal'
    if 'top' in name_lower and 'bump' not in name_lower:
        return 'diffuse_top'
    if 'bottom' in name_lower:
        return 'diffuse_bottom'

    # Standard classifications
    texture_types = {
        'diffuse': ['diffuse', 'albedo', 'color', 'base', 'diff'],
        'alpha': ['alpha', 'opacity', 'mask', 'transparent'],
        'normal': ['normal', 'norm', 'nrm'],
        'translucent': ['translucent', 'translucency', 'transmission', 'sss'],
    }

    for tex_type, keywords in texture_types.items():
        if any(keyword in name_lower for keyword in keywords):
            return tex_type

    return 'diffuse'

def find_best_textures_for_material(material_name, available_textures):
    """Find the best texture set for a material."""
    material_lower = material_name.lower()
    texture_map = {}

    # Group textures by type
    for texture in available_textures:
        tex_type = classify_texture_type(texture.stem)
        tex_name_lower = texture.stem.lower()

        # Check if texture matches this material
        material_match = False

        # Direct name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            material_match = True
        # Material name parts match
        elif any(word in tex_name_lower for word in material_lower.split() if len(word) > 2):
            material_match = True
        # Be permissive with few textures
        elif len(available_textures) <= 5:
            material_match = True

        if material_match:
            if tex_type not in texture_map:
                texture_map[tex_type] = texture

    # Handle diffuse priority (top > standard > bottom)
    # Remove redundant entries to avoid duplicates
    if 'diffuse_top' in texture_map:
        # If we have diffuse_top, use it and remove any generic diffuse
        if 'diffuse' in texture_map and texture_map['diffuse'] == texture_map['diffuse_top']:
            del texture_map['diffuse']
    elif 'diffuse' not in texture_map:
        # Only add fallback if no diffuse exists
        if 'diffuse_top' in texture_map:
            texture_map['diffuse'] = texture_map['diffuse_top']
        elif 'diffuse_bottom' in texture_map:
            texture_map['diffuse'] = texture_map['diffuse_bottom']

    return texture_map

def create_usd_optimized_material(material_name, available_textures, output_dir):
    """Create USD-optimized Principled BSDF material."""
    import bpy

    # Find textures for this material
    texture_map = find_best_textures_for_material(material_name, available_textures)

    if not texture_map:
        print(f"    No textures found for {material_name}")
        return None

    print(f"    Creating USD-optimized material for {material_name}")
    for tex_type, texture in texture_map.items():
        print(f"      {tex_type}: {texture.name}")

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{material_name}_USD")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create minimal node setup for USD compatibility
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)

    # Connect to output
    links = new_mat.node_tree.links
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Process textures with FBX-friendly connections
    y_offset = 200

    for tex_type, texture in texture_map.items():
        try:
            # Copy texture to output directory
            texture_name = f"{material_name}_{tex_type}_{texture.name}"
            dest_texture = output_dir / texture_name
            shutil.copy2(texture, dest_texture)

            # Load texture
            tex_image = bpy.data.images.load(str(dest_texture))
            tex_image.name = texture_name

            # Create texture node
            tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex_node.image = tex_image
            tex_node.location = (-300, y_offset)
            tex_node.label = tex_type.title()

            # Connect based on type with USD-friendly approach
            if tex_type in ['diffuse', 'diffuse_top']:
                links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
                print(f"        Connected {tex_type} to Base Color")

            elif tex_type == 'alpha':
                links.new(tex_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                new_mat.blend_method = 'BLEND'
                new_mat.show_transparent_back = False
                print(f"        Connected {tex_type} to Alpha")

            elif tex_type == 'normal':
                normal_node = new_mat.node_tree.nodes.new(type='ShaderNodeNormalMap')
                normal_node.location = (-100, y_offset - 100)
                links.new(tex_node.outputs['Color'], normal_node.inputs['Color'])
                links.new(normal_node.outputs['Normal'], principled_node.inputs['Normal'])
                print(f"        Connected {tex_type} via Normal Map")

            elif tex_type == 'translucent':
                if 'Subsurface Weight' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Subsurface Weight'])
                    principled_node.inputs['Subsurface Weight'].default_value = 0.1
                    print(f"        Connected {tex_type} to Subsurface")
                elif 'Subsurface' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Subsurface'])
                    principled_node.inputs['Subsurface'].default_value = 0.1
                    print(f"        Connected {tex_type} to Subsurface")

            y_offset -= 300

        except Exception as e:
            print(f"        Failed to process {tex_type}: {e}")

    # Set USD-friendly default values
    principled_node.inputs['Roughness'].default_value = 0.7

    # Set specular appropriately
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    # Set metallic to 0 for natural materials
    principled_node.inputs['Metallic'].default_value = 0.0

    print(f"    Created USD-optimized material: {new_mat.name}")
    return new_mat

def create_attachment_socket(obj):
    """Create an attachment socket/bone at the base of the twig.

    The Grove models twigs along the X-axis with the base at origin.
    This creates a single-bone armature at the origin to serve as
    the attachment point for Unreal Engine sockets.

    Args:
        obj: Blender mesh object

    Returns:
        Armature object or None
    """
    try:
        import bpy

        # Create armature
        armature = bpy.data.armatures.new(f"{obj.name}_Armature")
        armature_obj = bpy.data.objects.new(f"{obj.name}_Rig", armature)
        bpy.context.collection.objects.link(armature_obj)

        # Set armature as active and enter edit mode
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Create single bone at origin pointing along X-axis (twig growth direction)
        bone = armature.edit_bones.new("Socket_Attach")
        bone.head = (0.0, 0.0, 0.0)  # Base at origin
        bone.tail = (0.05, 0.0, 0.0)  # Short bone along X-axis (5cm)

        # Exit edit mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Parent mesh to armature (without deformation)
        obj.parent = armature_obj
        obj.parent_type = 'OBJECT'  # Object parenting, not bone

        # Reset mesh location relative to armature
        obj.matrix_parent_inverse = armature_obj.matrix_world.inverted()

        print(f"  Created attachment socket 'Socket_Attach' at origin")
        return armature_obj

    except Exception as e:
        print(f"  Warning: Failed to create attachment socket: {e}")
        return None


def export_single_blend_file(blend_path, output_dir, formats: List[str]):
    """Process blend file with USD optimization."""
    try:
        import bpy
    except ImportError as e:
        print(f"ERROR: Cannot import bpy: {e}")
        return False

    try:
        # Clear and load
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))

        # Find available textures
        blend_dir = Path(blend_path).parent
        available_textures = find_available_textures(blend_dir)

        print(f"Found {len(available_textures)} texture files")

        # Find mesh objects
        mesh_objects = [obj for obj in bpy.context.scene.objects
                       if obj.type == 'MESH' and obj.data]

        if not mesh_objects:
            print(f"No mesh objects found in {blend_path}")
            return False

        print(f"Found {len(mesh_objects)} objects to export")
        exported_count = 0

        for obj in mesh_objects:
            try:
                print(f"\\nProcessing: {obj.name}")

                # Center object
                center_object_at_origin(obj)

                # Replace materials with optimized versions
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        usd_material = create_usd_optimized_material(
                            slot.material.name,
                            available_textures,
                            output_dir
                        )
                        if usd_material:
                            slot.material = usd_material

                # Create attachment socket/bone at origin
                armature_obj = create_attachment_socket(obj)

                # Add Nanite metadata as custom properties (for foliage/twigs)
                obj["nanite_compatible"] = True
                obj["nanite_preserve_area"] = True  # TRUE for foliage (prevents thinning)
                obj["unreal_nanite"] = "enable"

                # Apply triangulation for Nanite consistency
                triangulate_mod = obj.modifiers.new(name="Triangulate_Nanite", type='TRIANGULATE')
                triangulate_mod.quad_method = 'BEAUTY'
                triangulate_mod.ngon_method = 'BEAUTY'

                # Select objects for export (mesh + armature if created)
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                if armature_obj:
                    armature_obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                clean_name = "".join(c for c in obj.name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                if not clean_name:
                    clean_name = f"twig_{exported_count}"

                # Export to requested formats
                for fmt in formats:
                    if fmt in ['usd', 'usda']:
                        # Export USD
                        usd_format = fmt
                        usd_path = output_dir / f"{clean_name}.{usd_format}"
                        print(f"  Exporting USD: {usd_path.name}")
                        bpy.ops.wm.usd_export(
                            filepath=str(usd_path),
                            selected_objects_only=True,
                            export_materials=True,
                            export_textures=True,
                            export_normals=True,
                            export_uvmaps=True,
                            export_mesh_colors=True,
                            export_armatures=True,  # Include attachment socket
                            use_instancing=False,
                            evaluation_mode='RENDER',
                            generate_preview_surface=True
                        )

                        # Add Nanite USD attributes (for foliage - Preserve Area enabled)
                        try:
                            from growpy.io.blender_export import add_nanite_attributes_to_usd
                            add_nanite_attributes_to_usd(usd_path, is_foliage=True)
                            print(f"  [OK] Exported Nanite-compatible USD: {clean_name}.{usd_format}")
                        except Exception as e:
                            print(f"  [WARN] Could not add Nanite attributes: {e}")
                            print(f"  [OK] Exported USD (without Nanite metadata): {clean_name}.{usd_format}")

                    elif fmt == 'fbx':
                        # Export FBX with Nanite optimization + attachment socket
                        fbx_path = output_dir / f"{clean_name}.fbx"
                        print(f"  Exporting FBX (Nanite-compatible): {fbx_path.name}")
                        bpy.ops.export_scene.fbx(
                            filepath=str(fbx_path),
                            use_selection=True,
                            object_types={'MESH', 'ARMATURE'},  # Include armature/socket
                            mesh_smooth_type='FACE',  # Single smoothing group (Nanite req)
                            use_mesh_modifiers=True,  # Apply triangulation
                            use_mesh_edges=False,  # Cleaner for Nanite
                            use_tspace=True,  # Tangent space for normals
                            use_custom_props=True,  # Export Nanite metadata
                            add_leaf_bones=False,
                            primary_bone_axis='Y',
                            secondary_bone_axis='X',
                            armature_nodetype='NULL',
                            bake_anim=False,
                            path_mode='COPY',
                            embed_textures=True,
                            batch_mode='OFF',
                            use_batch_own_dir=False,
                            axis_forward='-Z',
                            axis_up='Y'
                        )
                        print(f"  [OK] Exported Nanite-compatible FBX: {clean_name}.fbx")

                exported_count += 1

            except Exception as e:
                print(f"[ERROR] Failed to export {obj.name}: {e}")
                continue

        return exported_count > 0

    except Exception as e:
        print(f"Failed to process {blend_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: script.py <blend_file> <output_dir> [formats...]")
        sys.exit(1)

    blend_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    formats = sys.argv[3:] if len(sys.argv) > 3 else ['fbx']

    success = export_single_blend_file(blend_path, output_dir, formats)
    sys.exit(0 if success else 1)
'''
    return script_content


def process_blend_file_subprocess(blend_file: Path, formats: list) -> bool:
    """Process a single blend file in a separate subprocess."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(create_single_file_processor())
        script_path = Path(f.name)

    try:
        output_dir = blend_file.parent
        cmd = [
            sys.executable,
            str(script_path),
            str(blend_file),
            str(output_dir)
        ] + formats

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(f"Errors: {result.stderr.strip()}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout processing {blend_file.name}")
        return False
    except Exception as e:
        print(f"[ERROR] Subprocess error for {blend_file.name}: {e}")
        return False
    finally:
        script_path.unlink(missing_ok=True)


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Grove twig .blend files to FBX and/or USD format with optimized materials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process all twigs to FBX and USDA (default)
    python convert_twigs.py data/assets/twigs

    # Process to FBX only
    python convert_twigs.py data/assets/twigs --formats fbx

    # Process to USD binary format
    python convert_twigs.py data/assets/twigs --formats usd

    # Process to all formats
    python convert_twigs.py data/assets/twigs --formats fbx usd usda

    # Process single file
    python convert_twigs.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechSummerTwig.blend
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        nargs='?',
        default=None,
        help="Path to twig directory or single .blend file"
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="Alternative way to specify twigs directory"
    )
    parser.add_argument(
        "--formats",
        nargs='+',
        choices=['fbx', 'usd', 'usda'],
        default=['fbx', 'usda'],
        help="Export formats (default: fbx usda)"
    )

    args = parser.parse_args()

    # Determine target path
    if args.path:
        target_path = args.path
    elif args.twigs_dir:
        target_path = args.twigs_dir
    else:
        # Default to data/assets/twigs
        script_dir = Path(__file__).parent.parent.parent.parent
        target_path = script_dir / "data" / "assets" / "twigs"

    if not target_path.exists():
        print(f"[ERROR] Path not found: {target_path}")
        print("Usage: python convert_twigs.py <twig_directory_or_blend_file>")
        return

    formats_str = ', '.join(args.formats)
    print(f"Export formats: {formats_str}")

    if target_path.is_file() and target_path.suffix == '.blend':
        # Process single file
        print(f"Processing single file: {target_path.name}")
        if process_blend_file_subprocess(target_path, args.formats):
            print("Successfully processed")
        else:
            print("Failed to process")
        return

    # Process directory
    blend_files = list(target_path.glob("**/*.blend"))
    if not blend_files:
        print(f"[ERROR] No .blend files found in {target_path}")
        return

    print(f"Found {len(blend_files)} .blend files to process")
    print("Converting twigs with optimized materials and textures...")

    successful = 0
    failed = 0

    for blend_file in tqdm(blend_files, desc="Converting blend files"):
        print(f"\\nProcessing: {blend_file.name}")

        if process_blend_file_subprocess(blend_file, args.formats):
            successful += 1
        else:
            failed += 1

    print(f"\\nConversion complete:")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")


if __name__ == "__main__":
    main()