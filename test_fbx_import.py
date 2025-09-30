#!/usr/bin/env python3
"""
Test importing the FBX back into Blender to check materials.
"""

import bpy
from pathlib import Path

def test_fbx_import():
    """Test importing FBX with materials."""

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import the FBX
    fbx_path = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig.fbx")

    print(f"🔄 Importing: {fbx_path}")
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))

    # Check what was imported
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"📦 Imported {len(mesh_objects)} mesh objects")

    for obj in mesh_objects:
        print(f"\\n🌿 Object: {obj.name}")
        print(f"   Material slots: {len(obj.material_slots)}")

        for i, slot in enumerate(obj.material_slots):
            if not slot.material:
                print(f"   Slot {i}: No material")
                continue

            mat = slot.material
            print(f"   Slot {i}: {mat.name}")
            print(f"   Uses nodes: {mat.use_nodes}")

            if mat.use_nodes:
                # Check for texture nodes
                texture_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
                print(f"   Texture nodes: {len(texture_nodes)}")

                for node in texture_nodes:
                    if node.image:
                        print(f"     🖼️ Image: {node.image.name}")
                        print(f"        Path: {node.image.filepath}")

                        # Check if texture file exists
                        texture_path = Path(node.image.filepath_from_user())
                        print(f"        Exists: {texture_path.exists()}")
                    else:
                        print(f"     ❌ Texture node without image")
            else:
                print(f"   ⚠️ Material not using nodes")

if __name__ == "__main__":
    test_fbx_import()