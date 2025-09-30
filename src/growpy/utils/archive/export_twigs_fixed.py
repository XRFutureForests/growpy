#!/usr/bin/env python3
"""
Fixed twig export with proper texture connections and object centering.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script that properly fixes materials and positions."""
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

def create_working_material(original_material, output_dir):
    """Create a working material with properly connected texture."""
    import bpy

    if not original_material:
        return None

    # Find the main image texture from original material
    main_image = None
    if original_material.use_nodes:
        for node in original_material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                main_image = node.image
                break

    if not main_image:
        print(f"  No texture found for {original_material.name}")
        return original_material

    # Copy texture file
    texture_path = Path(main_image.filepath_from_user())
    if not texture_path.exists():
        print(f"  Texture file not found: {texture_path}")
        return original_material

    # Create clean texture filename
    texture_name = f"{original_material.name}_{texture_path.name}"
    dest_texture = output_dir / texture_name

    try:
        shutil.copy2(texture_path, dest_texture)
        print(f"  Copied texture: {texture_name}")
    except Exception as e:
        print(f"  Failed to copy texture: {e}")
        return original_material

    # Create new material with proper setup
    new_mat = bpy.data.materials.new(name=f"{original_material.name}_Export")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create essential nodes
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)

    # Create texture node
    tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
    tex_node.location = (-400, 0)

    # Load the texture into the texture node
    try:
        tex_image = bpy.data.images.load(str(dest_texture))
        tex_image.name = texture_name
        tex_node.image = tex_image
        print(f"  Loaded texture into node: {texture_name}")
    except Exception as e:
        print(f"  Failed to load texture: {e}")
        return original_material

    # Connect nodes properly
    links = new_mat.node_tree.links

    # Connect texture to Principled BSDF
    links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])

    # Connect Principled to Output
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Set material properties for better visibility
    principled_node.inputs['Roughness'].default_value = 0.7
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    print(f"  Created working material: {new_mat.name}")
    return new_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with proper fixes."""
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

                # Fix materials
                working_materials = []
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Converting material {i}: {slot.material.name}")
                        working_mat = create_working_material(slot.material, output_dir)
                        working_materials.append(working_mat)

                        # Replace material on object
                        slot.material = working_mat
                    else:
                        working_materials.append(None)

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
                    use_tspace=True,
                    # Ensure materials are exported
                    use_custom_props=False,
                    bake_anim=False
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
        print("Usage: python export_twigs_fixed.py <twig_directory>")
        print("Example: python export_twigs_fixed.py data/assets/twigs")
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
    print("🔧 Processing with position centering and texture fixes...")

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