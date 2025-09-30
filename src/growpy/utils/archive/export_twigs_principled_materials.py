#!/usr/bin/env python3
"""
Twig export that creates FBX-compatible Principled BSDF materials.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script that creates FBX-compatible Principled materials."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

def create_fbx_compatible_material(original_material, output_dir):
    """Create an FBX-compatible Principled BSDF material."""
    import bpy

    if not original_material:
        return None

    # Create new material with FBX-friendly name
    fbx_mat = bpy.data.materials.new(name=f"{original_material.name}_FBX")
    fbx_mat.use_nodes = True

    # Clear default nodes
    fbx_mat.node_tree.nodes.clear()

    # Add essential nodes for FBX compatibility
    output_node = fbx_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (300, 0)

    principled_node = fbx_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)

    # Link Principled to Output
    fbx_mat.node_tree.links.new(
        principled_node.outputs['BSDF'],
        output_node.inputs['Surface']
    )

    # Find main texture from original material
    main_texture_image = None
    if original_material.use_nodes:
        for node in original_material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                main_texture_image = node.image
                break

    if main_texture_image:
        # Copy texture file to output directory
        texture_path = Path(main_texture_image.filepath_from_user())
        if texture_path.exists():
            # Create simple texture name
            texture_name = f"{original_material.name}_{texture_path.name}"
            dest_texture = output_dir / texture_name

            try:
                shutil.copy2(texture_path, dest_texture)
                print(f"  Copied texture: {texture_name}")

                # Load the copied texture
                new_image = bpy.data.images.load(str(dest_texture))
                new_image.name = texture_name

                # Create texture node
                tex_node = fbx_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
                tex_node.image = new_image
                tex_node.location = (-300, 0)

                # Connect texture to Principled BSDF Base Color
                fbx_mat.node_tree.links.new(
                    tex_node.outputs['Color'],
                    principled_node.inputs['Base Color']
                )

                print(f"  Created FBX material with texture: {fbx_mat.name}")

            except Exception as e:
                print(f"  Failed to setup texture: {e}")

    # Set basic material properties
    principled_node.inputs['Roughness'].default_value = 0.5
    principled_node.inputs['Specular IOR Level'].default_value = 0.5

    return fbx_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with FBX-compatible materials."""
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
                print(f"\\n🌿 Processing object: {obj.name}")

                # Convert materials to FBX-compatible versions
                fbx_materials = []
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Converting material {i}: {slot.material.name}")
                        fbx_mat = create_fbx_compatible_material(slot.material, output_dir)
                        fbx_materials.append(fbx_mat)
                    else:
                        fbx_materials.append(None)

                # Replace materials on object
                for i, fbx_mat in enumerate(fbx_materials):
                    if i < len(obj.material_slots) and fbx_mat:
                        obj.material_slots[i].material = fbx_mat

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

                # Export FBX with materials
                print(f"  Exporting to: {fbx_path}")
                bpy.ops.export_scene.fbx(
                    filepath=str(fbx_path),
                    use_selection=True,
                    object_types={'MESH'},
                    global_scale=1.0,
                    path_mode='RELATIVE',  # Relative paths for portability
                    embed_textures=False,
                    use_mesh_modifiers=True,
                    mesh_smooth_type='FACE',
                    use_tspace=True
                )

                print(f"✅ Exported: {fbx_path}")
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
        print("Usage: python export_twigs_principled_materials.py <twig_directory>")
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
    print("🔄 Creating FBX-compatible Principled BSDF materials...")

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