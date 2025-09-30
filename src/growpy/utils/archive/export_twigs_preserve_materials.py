#!/usr/bin/env python3
"""
Enhanced twig export that preserves complex material setups like top/bottom blending.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script that preserves complex material structures."""
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
    """Find all texture files in the blend directory and subdirectories."""
    texture_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.hdr', '.bmp']
    textures = []

    for ext in texture_extensions:
        textures.extend(blend_dir.rglob(f"*{ext}"))
        textures.extend(blend_dir.rglob(f"*{ext.upper()}"))

    return textures

def classify_texture_type(filename):
    """Classify texture type with better pattern recognition."""
    name_lower = filename.lower()

    # Handle specific patterns first
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
        'roughness': ['roughness', 'rough'],
        'metallic': ['metallic', 'metal', 'met'],
        'specular': ['specular', 'spec'],
        'ao': ['ao', 'occlusion', 'ambient']
    }

    for tex_type, keywords in texture_types.items():
        if any(keyword in name_lower for keyword in keywords):
            return tex_type

    return 'diffuse'

def fix_broken_texture_paths(material, available_textures, output_dir):
    """Fix broken texture paths in existing materials."""
    import bpy

    if not material or not material.use_nodes:
        return False

    fixed_any = False
    material_name_lower = material.name.lower()

    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            image_path = Path(node.image.filepath_from_user())

            # Check if the current image path is broken
            if not image_path.exists():
                print(f"    Fixing broken texture: {node.image.name}")

                # Try to find a replacement texture
                replacement = None

                # Look for textures with similar names
                for texture in available_textures:
                    tex_type = classify_texture_type(texture.stem)
                    tex_name_lower = texture.stem.lower()

                    # Try multiple matching strategies
                    if (
                        # Direct name match
                        any(word in tex_name_lower for word in material_name_lower.split() if len(word) > 2) or
                        # Type-based match for common names
                        (tex_type == 'diffuse' and 'diffuse' in node.image.name.lower()) or
                        (tex_type == 'alpha' and 'alpha' in node.image.name.lower()) or
                        (tex_type == 'normal' and ('normal' in node.image.name.lower() or 'bump' in node.image.name.lower())) or
                        (tex_type == 'translucent' and 'translucent' in node.image.name.lower())
                    ):
                        replacement = texture
                        break

                if replacement:
                    # Copy texture to output directory
                    texture_name = f"{material.name}_{replacement.name}"
                    dest_texture = output_dir / texture_name

                    try:
                        shutil.copy2(replacement, dest_texture)

                        # Load new image and replace
                        new_image = bpy.data.images.load(str(dest_texture))
                        new_image.name = texture_name
                        node.image = new_image

                        print(f"      Replaced with: {replacement.name}")
                        fixed_any = True

                    except Exception as e:
                        print(f"      Failed to replace texture: {e}")

    return fixed_any

def create_enhanced_material(original_material, available_textures, output_dir):
    """Create enhanced material that preserves complex setups when possible."""
    import bpy

    if not original_material:
        return None

    # Try to fix broken textures in the original material first
    if fix_broken_texture_paths(original_material, available_textures, output_dir):
        print(f"    Fixed broken textures in: {original_material.name}")
        return original_material

    # If original material works, use it
    if original_material.use_nodes:
        working_textures = 0
        for node in original_material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image_path = Path(node.image.filepath_from_user())
                if image_path.exists():
                    working_textures += 1

        if working_textures > 0:
            print(f"    Keeping original material: {original_material.name} ({working_textures} working textures)")
            return original_material

    # Otherwise create a new Principled BSDF material
    print(f"    Creating new Principled BSDF material for: {original_material.name}")

    # Find best textures
    texture_map = {}
    material_lower = original_material.name.lower()

    for texture in available_textures:
        tex_type = classify_texture_type(texture.stem)
        tex_name_lower = texture.stem.lower()

        # Check if texture matches this material
        if (
            material_lower in tex_name_lower or
            any(word in tex_name_lower for word in material_lower.split() if len(word) > 2) or
            len(available_textures) <= 5  # Be permissive with few textures
        ):
            if tex_type not in texture_map:
                texture_map[tex_type] = texture

    # Handle diffuse priority
    if 'diffuse' not in texture_map:
        if 'diffuse_top' in texture_map:
            texture_map['diffuse'] = texture_map['diffuse_top']
        elif 'diffuse_bottom' in texture_map:
            texture_map['diffuse'] = texture_map['diffuse_bottom']

    if not texture_map:
        print(f"    No suitable textures found for {original_material.name}")
        return original_material

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{original_material.name}_Enhanced")
    new_mat.use_nodes = True
    new_mat.node_tree.nodes.clear()

    # Create nodes
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (600, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (300, 0)

    links = new_mat.node_tree.links
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Add textures
    y_offset = 200
    for tex_type, texture in texture_map.items():
        try:
            # Copy texture
            texture_name = f"{original_material.name}_{tex_type}_{texture.name}"
            dest_texture = output_dir / texture_name
            shutil.copy2(texture, dest_texture)

            # Load and create texture node
            tex_image = bpy.data.images.load(str(dest_texture))
            tex_image.name = texture_name

            tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex_node.image = tex_image
            tex_node.location = (0, y_offset)
            tex_node.label = tex_type.title()

            # Connect appropriately
            if tex_type in ['diffuse', 'diffuse_top']:
                links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
                print(f"      Connected {tex_type} to Base Color")

            elif tex_type == 'alpha':
                links.new(tex_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                new_mat.blend_method = 'BLEND'
                print(f"      Connected {tex_type} to Alpha")

            elif tex_type == 'normal':
                normal_node = new_mat.node_tree.nodes.new(type='ShaderNodeNormalMap')
                normal_node.location = (150, y_offset - 50)
                links.new(tex_node.outputs['Color'], normal_node.inputs['Color'])
                links.new(normal_node.outputs['Normal'], principled_node.inputs['Normal'])
                print(f"      Connected {tex_type} via Normal Map")

            elif tex_type == 'translucent':
                if 'Transmission Weight' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Transmission Weight'])
                elif 'Transmission' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Transmission'])
                print(f"      Connected {tex_type} to transmission")

            y_offset -= 300

        except Exception as e:
            print(f"      Failed to process {tex_type}: {e}")

    # Set good defaults
    principled_node.inputs['Roughness'].default_value = 0.7
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    print(f"    Created enhanced material: {new_mat.name}")
    return new_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with enhanced material preservation."""
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

                # Process materials with preservation
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        enhanced_material = create_enhanced_material(
                            slot.material,
                            available_textures,
                            output_dir
                        )
                        slot.material = enhanced_material

                # Export
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
                    path_mode='RELATIVE',
                    embed_textures=False,
                    use_mesh_modifiers=True,
                    mesh_smooth_type='FACE',
                    use_tspace=True
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
        print("Usage: python export_twigs_preserve_materials.py <twig_directory_or_blend_file>")
        print("Example: python export_twigs_preserve_materials.py data/assets/twigs")
        print("Example: python export_twigs_preserve_materials.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechSummerTwig.blend")
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
    print("🔧 Using enhanced material preservation...")

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