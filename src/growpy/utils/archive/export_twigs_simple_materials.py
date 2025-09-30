#!/usr/bin/env python3
"""
Twig export that converts complex node materials to simple materials for FBX compatibility.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script that converts materials to FBX-compatible format."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

def convert_to_simple_material(material, output_dir):
    """Convert node-based material to simple material for FBX compatibility."""
    import bpy

    if not material or not material.use_nodes:
        return None

    # Find the main image texture node
    main_texture = None
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            main_texture = node
            break

    if not main_texture:
        return None

    # Create a new simple material
    simple_mat = bpy.data.materials.new(name=f"{material.name}_simple")
    simple_mat.use_nodes = False  # Use simple material, not nodes

    # Set basic material properties
    simple_mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)  # White base

    # Copy and setup texture image
    texture_path = Path(main_texture.image.filepath_from_user())
    if texture_path.exists():
        # Copy texture to output directory with simple name
        simple_texture_name = f"{material.name}_{texture_path.name}"
        dest_texture = output_dir / simple_texture_name

        try:
            shutil.copy2(texture_path, dest_texture)
            print(f"  Copied texture: {simple_texture_name}")

            # Create new image datablock with copied texture
            new_image = bpy.data.images.load(str(dest_texture))
            new_image.name = simple_texture_name

            # Set material to use this texture (legacy way)
            # Create texture slot
            tex = bpy.data.textures.new(name=f"{material.name}_tex", type='IMAGE')
            tex.image = new_image

            # Add texture slot to material
            mtex = simple_mat.texture_slots.add()
            mtex.texture = tex
            mtex.texture_coords = 'UV'
            mtex.use_map_color_diffuse = True

            print(f"  Created simple material: {simple_mat.name}")
            return simple_mat

        except Exception as e:
            print(f"  Failed to setup texture for {material.name}: {e}")
            return simple_mat

    return simple_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with simple material conversion."""
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
                # Convert materials to simple materials
                original_materials = []
                for slot in obj.material_slots:
                    if slot.material:
                        original_materials.append(slot.material)

                # Convert each material
                simple_materials = []
                for mat in original_materials:
                    simple_mat = convert_to_simple_material(mat, output_dir)
                    if simple_mat:
                        simple_materials.append(simple_mat)
                    else:
                        simple_materials.append(mat)

                # Replace materials on object
                for i, simple_mat in enumerate(simple_materials):
                    if i < len(obj.material_slots):
                        obj.material_slots[i].material = simple_mat

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

                # Export FBX with simple materials
                bpy.ops.export_scene.fbx(
                    filepath=str(fbx_path),
                    use_selection=True,
                    object_types={'MESH'},
                    global_scale=1.0,
                    path_mode='RELATIVE',  # Use relative paths for textures
                    embed_textures=False,
                    use_mesh_modifiers=True,
                    mesh_smooth_type='FACE',
                    use_tspace=True,
                    # Ensure materials are exported
                    use_custom_props=True
                )

                print(f"Exported FBX: {fbx_path}")
                exported_count += 1

            except Exception as e:
                print(f"Failed to export {obj.name}: {e}")
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

    # Create temporary script file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(create_single_file_processor())
        script_path = Path(f.name)

    try:
        # Output to same directory as blend file
        output_dir = blend_file.parent

        # Run subprocess
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
        # Clean up temporary script
        script_path.unlink(missing_ok=True)


def find_blend_files(twig_dir: Path) -> list:
    """Find all blend files in directory."""
    return list(twig_dir.glob("**/*.blend"))


def main():
    """Main function."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python export_twigs_simple_materials.py <twig_directory>")
        print("Example: python export_twigs_simple_materials.py data/assets/twigs")
        return

    twig_dir = Path(sys.argv[1])
    if not twig_dir.exists():
        print(f"❌ Directory not found: {twig_dir}")
        return

    blend_files = find_blend_files(twig_dir)
    if not blend_files:
        print(f"❌ No .blend files found in {twig_dir}")
        return

    print(f"🌿 Found {len(blend_files)} .blend files to process")
    print("🔄 Processing each file with simple material conversion...")

    successful = 0
    failed = 0

    for blend_file in tqdm(blend_files, desc="Processing blend files"):
        print(f"\\n📁 Processing: {blend_file.name}")

        if process_blend_file_subprocess(blend_file):
            successful += 1
        else:
            failed += 1
            print(f"❌ Failed: {blend_file.name}")

    print(f"\\n🎯 Export complete:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")


if __name__ == "__main__":
    main()