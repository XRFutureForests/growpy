#!/usr/bin/env python3
"""
Debug script to investigate texture export issues with a specific blend file.
"""

import bpy
from pathlib import Path

def debug_twig_materials(blend_file):
    """Debug materials and textures in a twig blend file."""
    print(f"🔍 Debugging: {blend_file}")

    # Clear and load
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))

    # Find mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.data]
    print(f"📦 Found {len(mesh_objects)} mesh objects")

    for obj in mesh_objects:
        print(f"\n🌿 Object: {obj.name}")
        print(f"   Material slots: {len(obj.material_slots)}")

        for i, slot in enumerate(obj.material_slots):
            if not slot.material:
                print(f"   Slot {i}: No material")
                continue

            mat = slot.material
            print(f"   Slot {i}: {mat.name}")
            print(f"   Uses nodes: {mat.use_nodes}")

            if mat.use_nodes:
                print(f"   Nodes: {len(mat.node_tree.nodes)}")
                for node in mat.node_tree.nodes:
                    print(f"     - {node.type}: {node.name}")
                    if node.type == 'TEX_IMAGE' and node.image:
                        print(f"       Image: {node.image.name}")
                        print(f"       Filepath: {node.image.filepath}")
                        print(f"       Filepath (user): {node.image.filepath_from_user()}")

                        # Check if file exists
                        image_path = Path(node.image.filepath_from_user())
                        if not image_path.is_absolute():
                            blend_dir = Path(blend_file).parent
                            full_path = blend_dir / node.image.filepath_from_user()
                            print(f"       Full path: {full_path}")
                            print(f"       Exists: {full_path.exists()}")
                        else:
                            print(f"       Exists: {image_path.exists()}")

    # Try test export
    if mesh_objects:
        obj = mesh_objects[0]
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        test_fbx = Path(blend_file).parent / "debug_test.fbx"
        print(f"\n📤 Test export to: {test_fbx}")

        # Try different export settings
        try:
            bpy.ops.export_scene.fbx(
                filepath=str(test_fbx),
                use_selection=True,
                object_types={'MESH'},
                global_scale=1.0,
                path_mode='COPY',
                embed_textures=False,
                use_mesh_modifiers=True,
                mesh_smooth_type='FACE',
                use_tspace=True
            )
            print("✅ Export succeeded")

            # Check what files were created
            parent_dir = test_fbx.parent
            files_after = list(parent_dir.glob("*"))
            print("Files in directory after export:")
            for f in files_after:
                if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr']:
                    print(f"  🖼️ {f.name}")
                elif f.suffix.lower() == '.fbx':
                    print(f"  📦 {f.name}")

        except Exception as e:
            print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    blend_file = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig.blend")
    if blend_file.exists():
        debug_twig_materials(blend_file)
    else:
        print(f"Blend file not found: {blend_file}")