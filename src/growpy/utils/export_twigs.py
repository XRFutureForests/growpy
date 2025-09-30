#!/usr/bin/env python3
"""
Main twig export utility for converting Grove .blend files to FBX with optimized materials.

This script processes twig blend files and exports them as FBX files with:
- Proper texture mapping (diffuse, alpha, normal, translucent)
- FBX-compatible Principled BSDF materials
- Automatic texture discovery and classification
- Objects centered at origin (0,0,0)
- Support for varied texture naming conventions

Usage:
    python export_twigs.py <twig_directory>
    python export_twigs.py <single_blend_file>

Examples:
    python export_twigs.py data/assets/twigs
    python export_twigs.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechSummerTwig.blend
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script optimized for FBX export."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

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
    """Classify texture type for FBX optimization."""
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

def create_fbx_optimized_material(material_name, available_textures, output_dir):
    """Create FBX-optimized Principled BSDF material."""
    import bpy

    # Find textures for this material
    texture_map = find_best_textures_for_material(material_name, available_textures)

    if not texture_map:
        print(f"    No textures found for {material_name}")
        return None

    print(f"    Creating FBX-optimized material for {material_name}")
    for tex_type, texture in texture_map.items():
        print(f"      {tex_type}: {texture.name}")

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{material_name}_FBX")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create minimal node setup for FBX compatibility
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

            # Connect based on type with FBX-friendly approach
            if tex_type in ['diffuse', 'diffuse_top']:
                links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
                print(f"        Connected {tex_type} to Base Color")

            elif tex_type == 'alpha':
                # For alpha, also connect to Base Color alpha for FBX compatibility
                links.new(tex_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                new_mat.blend_method = 'BLEND'
                new_mat.show_transparent_back = False
                print(f"        Connected {tex_type} to Alpha (FBX compatible)")

            elif tex_type == 'normal':
                # Use normal map node for proper FBX export
                normal_node = new_mat.node_tree.nodes.new(type='ShaderNodeNormalMap')
                normal_node.location = (-100, y_offset - 100)
                links.new(tex_node.outputs['Color'], normal_node.inputs['Color'])
                links.new(normal_node.outputs['Normal'], principled_node.inputs['Normal'])
                print(f"        Connected {tex_type} via Normal Map (FBX compatible)")

            elif tex_type == 'translucent':
                # For FBX, use subsurface instead of transmission
                if 'Subsurface Weight' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Subsurface Weight'])
                    principled_node.inputs['Subsurface Weight'].default_value = 0.1
                    print(f"        Connected {tex_type} to Subsurface (FBX compatible)")
                elif 'Subsurface' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Subsurface'])
                    principled_node.inputs['Subsurface'].default_value = 0.1
                    print(f"        Connected {tex_type} to Subsurface (FBX compatible)")

            y_offset -= 300

        except Exception as e:
            print(f"        Failed to process {tex_type}: {e}")

    # Set FBX-friendly default values
    principled_node.inputs['Roughness'].default_value = 0.7

    # Set specular appropriately for FBX
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    # Set metallic to 0 for natural materials
    principled_node.inputs['Metallic'].default_value = 0.0

    print(f"    Created FBX-optimized material: {new_mat.name}")
    return new_mat

def export_single_blend_file(blend_path, output_dir):
    """Process blend file with FBX optimization."""
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
                print(f"\\n🌿 Processing: {obj.name}")

                # Center object
                center_object_at_origin(obj)

                # Replace materials with FBX-optimized versions
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        fbx_material = create_fbx_optimized_material(
                            slot.material.name,
                            available_textures,
                            output_dir
                        )
                        if fbx_material:
                            slot.material = fbx_material

                # Export with FBX-optimized settings
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                clean_name = "".join(c for c in obj.name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                if not clean_name:
                    clean_name = f"twig_{exported_count}"

                fbx_path = output_dir / f"{clean_name}.fbx"

                print(f"  Exporting to: {fbx_path.name}")
                bpy.ops.export_scene.fbx(
                    filepath=str(fbx_path),
                    use_selection=True,
                    object_types={'MESH'},
                    global_scale=1.0,
                    path_mode='COPY',  # Copy textures for better compatibility
                    embed_textures=False,
                    use_mesh_modifiers=True,
                    mesh_smooth_type='FACE',
                    use_tspace=True,
                    # FBX-specific optimizations
                    use_custom_props=False,
                    bake_space_transform=True
                )

                print(f"✅ Exported: {clean_name}.fbx")
                exported_count += 1

            except Exception as e:
                print(f"❌ Failed to export {obj.name}: {e}")
                continue

        return exported_count > 0

    except Exception as e:
        print(f"Failed to process {blend_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: script.py <blend_file> <output_dir>")
        sys.exit(1)

    blend_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    success = export_single_blend_file(blend_path, output_dir)
    sys.exit(0 if success else 1)
'''
    return script_content


def process_blend_file_subprocess(blend_file: Path) -> bool:
    """Process a single blend file in a separate subprocess."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(create_single_file_processor())
        script_path = Path(f.name)

    try:
        output_dir = blend_file.parent
        result = subprocess.run([
            sys.executable,
            str(script_path),
            str(blend_file),
            str(output_dir)
        ], capture_output=True, text=True, timeout=120)

        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(f"Errors: {result.stderr.strip()}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"❌ Timeout processing {blend_file.name}")
        return False
    except Exception as e:
        print(f"❌ Subprocess error for {blend_file.name}: {e}")
        return False
    finally:
        script_path.unlink(missing_ok=True)


def main():
    """Main function."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python export_twigs.py <twig_directory_or_blend_file>")
        print("Example: python export_twigs.py data/assets/twigs")
        print("Example: python export_twigs.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechSummerTwig.blend")
        return

    target_path = Path(sys.argv[1])
    if not target_path.exists():
        print(f"❌ Path not found: {target_path}")
        return

    if target_path.is_file() and target_path.suffix == '.blend':
        # Process single file
        print(f"🌿 Processing single file: {target_path.name}")
        if process_blend_file_subprocess(target_path):
            print("✅ Successfully processed")
        else:
            print("❌ Failed to process")
        return

    # Process directory
    blend_files = list(target_path.glob("**/*.blend"))
    if not blend_files:
        print(f"❌ No .blend files found in {target_path}")
        return

    print(f"🌿 Found {len(blend_files)} .blend files to process")
    print("🎯 Creating FBX-optimized materials with proper texture mapping...")

    successful = 0
    failed = 0

    for blend_file in tqdm(blend_files, desc="Processing blend files"):
        print(f"\\n📁 Processing: {blend_file.name}")

        if process_blend_file_subprocess(blend_file):
            successful += 1
        else:
            failed += 1

    print(f"\\n🎯 Export complete:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")


if __name__ == "__main__":
    main()