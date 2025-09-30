#!/usr/bin/env python3
"""
Memory-safe twig export using subprocess isolation.

This version processes each .blend file in a separate Python subprocess to prevent
memory crashes and conflicts with the bpy module.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script that processes a single blend file."""
    script_content = '''#!/usr/bin/env python3
import sys
from pathlib import Path

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file safely."""
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

        # Check materials
        materials_count = len([mat for mat in bpy.data.materials if mat])
        images_count = len([img for img in bpy.data.images if img])
        print(f"Found {materials_count} materials and {images_count} images")

        exported_count = 0

        for obj in mesh_objects:
            try:
                # Select only this object
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Check materials on object
                obj_materials = [slot.material for slot in obj.material_slots if slot.material]
                print(f"Object '{obj.name}' has {len(obj_materials)} materials")

                # Clean object name for filename
                clean_name = "".join(c for c in obj.name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                if not clean_name:
                    clean_name = f"twig_{exported_count}"

                fbx_path = output_dir / f"{clean_name}.fbx"

                # Ensure textures have correct paths before export
                for mat_slot in obj.material_slots:
                    if mat_slot.material and mat_slot.material.use_nodes:
                        for node in mat_slot.material.node_tree.nodes:
                            if node.type == 'TEX_IMAGE' and node.image:
                                # Make sure image path is absolute and exists
                                image_path = Path(node.image.filepath_from_user())
                                if not image_path.is_absolute():
                                    # Try to resolve relative to blend file
                                    blend_dir = Path(blend_path).parent
                                    potential_path = blend_dir / node.image.filepath_from_user()
                                    if potential_path.exists():
                                        node.image.filepath = str(potential_path.resolve())
                                        print(f"  Fixed texture path: {node.image.name} -> {potential_path}")

                # Export with materials and texture copying
                bpy.ops.export_scene.fbx(
                    filepath=str(fbx_path),
                    use_selection=True,
                    object_types={'MESH'},
                    global_scale=1.0,
                    path_mode='COPY',  # Copy textures to FBX location
                    embed_textures=False,  # Don't embed, copy files instead
                    use_mesh_modifiers=True,
                    mesh_smooth_type='FACE',
                    use_tspace=True,
                    # Include materials
                    use_custom_props=False,
                    bake_anim=False
                )

                print(f"Exported: {fbx_path}")
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
        ], capture_output=True, text=True, timeout=60)

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
        print("Usage: python export_twigs_subprocess.py <twig_directory>")
        print("Example: python export_twigs_subprocess.py data/assets/twigs")
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
    print("🔄 Processing each file in isolated subprocess...")

    successful = 0
    failed = 0

    for blend_file in tqdm(blend_files, desc="Processing blend files"):
        print(f"\n📁 Processing: {blend_file.name}")

        if process_blend_file_subprocess(blend_file):
            successful += 1
        else:
            failed += 1
            print(f"❌ Failed: {blend_file.name}")

    print(f"\n🎯 Export complete:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")


if __name__ == "__main__":
    main()