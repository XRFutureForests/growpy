#!/usr/bin/env python3
"""
Smart twig export that properly handles different texture types and multiple textures per material.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script with smart texture handling."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

def center_object_at_origin(obj):
    """Move object to origin (0,0,0)."""
    import bpy

    # Clear location
    obj.location = (0, 0, 0)

    # Apply transforms
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)

    # Apply location, rotation, scale
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    print(f"  Centered {obj.name} at origin")

def is_color_texture(image_name):
    """Check if image is likely a color texture (not bump/normal)."""
    name_lower = image_name.lower()

    # Skip bump, normal, roughness, metallic maps
    skip_keywords = ['bump', 'normal', 'roughness', 'metallic', 'specular', 'ao', 'occlusion']

    for keyword in skip_keywords:
        if keyword in name_lower:
            return False

    return True

def find_best_textures(original_material):
    """Find the best color textures from a material, preferring diffuse/albedo over others."""
    if not original_material or not original_material.use_nodes:
        return []

    textures = []

    for node in original_material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            image_path = Path(node.image.filepath_from_user())
            if image_path.exists() and is_color_texture(node.image.name):
                textures.append({
                    'node': node,
                    'image': node.image,
                    'path': image_path,
                    'name': node.image.name
                })

    # Sort by preference: look for "top", "diffuse", "albedo", "color" first
    def texture_priority(tex):
        name_lower = tex['name'].lower()
        if any(keyword in name_lower for keyword in ['diffuse', 'albedo', 'color']):
            return 0  # Highest priority
        elif 'top' in name_lower:
            return 1  # Second priority
        elif 'bottom' in name_lower:
            return 2  # Third priority
        else:
            return 3  # Lowest priority

    textures.sort(key=texture_priority)

    print(f"    Found {len(textures)} color textures:")
    for i, tex in enumerate(textures):
        print(f"      {i+1}. {tex['name']} (priority: {texture_priority(tex)})")

    return textures

def create_smart_material(original_material, output_dir):
    """Create a material with smart texture selection."""
    import bpy

    if not original_material:
        return None

    textures = find_best_textures(original_material)

    if not textures:
        print(f"    No suitable color textures found for {original_material.name}")
        return original_material

    # Use the highest priority texture (first in sorted list)
    main_texture = textures[0]

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{original_material.name}_Smart")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create node setup
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)

    # Copy and setup main texture
    texture_path = main_texture['path']
    texture_name = f"{original_material.name}_{texture_path.name}"
    dest_texture = output_dir / texture_name

    try:
        shutil.copy2(texture_path, dest_texture)
        print(f"    Copied main texture: {texture_name}")

        # Load texture
        tex_image = bpy.data.images.load(str(dest_texture))
        tex_image.name = texture_name

        # Create texture node
        tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
        tex_node.image = tex_image
        tex_node.location = (-400, 0)

        # Connect to Principled BSDF
        links = new_mat.node_tree.links
        links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
        links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

        # Set good default values
        principled_node.inputs['Roughness'].default_value = 0.7
        if 'Specular IOR Level' in principled_node.inputs:
            principled_node.inputs['Specular IOR Level'].default_value = 0.5
        elif 'Specular' in principled_node.inputs:
            principled_node.inputs['Specular'].default_value = 0.5

        print(f"    Created smart material: {new_mat.name}")
        return new_mat

    except Exception as e:
        print(f"    Failed to setup texture: {e}")
        return original_material

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with smart material handling."""
    try:
        import bpy
    except ImportError as e:
        print(f"ERROR: Cannot import bpy: {e}")
        return False

    try:
        # Clear existing data
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Load the blend file
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))

        # Find all mesh objects
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

                # Center object at origin
                center_object_at_origin(obj)

                # Process materials with smart texture selection
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        smart_material = create_smart_material(slot.material, output_dir)
                        slot.material = smart_material

                # Select only this object
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Clean object name for filename
                clean_name = "".join(c for c in obj.name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                if not clean_name:
                    clean_name = f"twig_{exported_count}"

                fbx_path = output_dir / f"{clean_name}.fbx"

                # Export FBX
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
        ], capture_output=True, text=True, timeout=90)

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
        print("Usage: python export_twigs_smart_textures.py <twig_directory>")
        print("Example: python export_twigs_smart_textures.py data/assets/twigs")
        return

    twig_dir = Path(sys.argv[1])
    if not twig_dir.exists():
        print(f"❌ Directory not found: {twig_dir}")
        return

    blend_files = list(twig_dir.glob("**/*.blend"))
    if not blend_files:
        print(f"❌ No .blend files found in {twig_dir}")
        return

    print(f"🌿 Found {len(blend_files)} .blend files to process")
    print("🧠 Using smart texture selection (prioritizes color over bump maps)...")

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