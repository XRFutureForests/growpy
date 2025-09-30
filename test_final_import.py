#!/usr/bin/env python3
"""
Test the final fixed FBX import.
"""

import bpy
from pathlib import Path

def test_final_fbx():
    """Test importing the fixed FBX."""

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import the fixed FBX
    fbx_path = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig.fbx")

    print(f"🔄 Testing import: {fbx_path}")
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))

    # Check imported objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"📦 Imported {len(mesh_objects)} objects")

    for obj in mesh_objects:
        print(f"\\n🌿 Object: {obj.name}")
        print(f"   Location: {obj.location}")
        print(f"   Bounding box center: {[(obj.bound_box[i][j] + obj.bound_box[i+4][j])/2 for j in range(3) for i in [0]]}")

        # Check materials
        for i, slot in enumerate(obj.material_slots):
            if not slot.material:
                continue

            mat = slot.material
            print(f"   Material {i}: {mat.name}")

            if mat.use_nodes:
                # Find Principled BSDF and texture nodes
                principled_nodes = [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
                texture_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']

                print(f"     Principled BSDF nodes: {len(principled_nodes)}")
                print(f"     Texture nodes: {len(texture_nodes)}")

                # Check connections
                for tex_node in texture_nodes:
                    if tex_node.image:
                        print(f"       🖼️ Texture: {tex_node.image.name}")
                        print(f"          Path: {tex_node.image.filepath}")
                        print(f"          Exists: {Path(tex_node.image.filepath_from_user()).exists()}")

                        # Check if connected to Principled BSDF
                        connected_to_principled = False
                        for output in tex_node.outputs:
                            for link in output.links:
                                if link.to_node.type == 'BSDF_PRINCIPLED':
                                    connected_to_principled = True
                                    print(f"          ✅ Connected to Principled BSDF: {link.to_socket.name}")

                        if not connected_to_principled:
                            print(f"          ❌ NOT connected to Principled BSDF")

    # Test render preview
    print(f"\\n🎨 Setting up for preview...")
    if mesh_objects:
        obj = mesh_objects[0]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Switch to material preview shading
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        print("   Set viewport to Material Preview mode")
                        break

if __name__ == "__main__":
    test_final_fbx()