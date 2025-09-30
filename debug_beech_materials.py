#!/usr/bin/env python3
"""
Debug script to investigate beech twig materials specifically.
"""

import bpy
from pathlib import Path

def debug_blend_materials(blend_file):
    """Debug materials and textures in any blend file."""
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
                print(f"   Nodes ({len(mat.node_tree.nodes)}):")
                for node in mat.node_tree.nodes:
                    print(f"     - {node.type}: {node.name}")

                    if node.type == 'TEX_IMAGE' and node.image:
                        print(f"       🖼️ Image: {node.image.name}")
                        print(f"          Filepath: {node.image.filepath}")
                        print(f"          Filepath (user): {node.image.filepath_from_user()}")

                        # Check if file exists
                        image_path = Path(node.image.filepath_from_user())
                        if not image_path.is_absolute():
                            blend_dir = Path(blend_file).parent
                            full_path = blend_dir / node.image.filepath_from_user()
                            print(f"          Full path: {full_path}")
                            print(f"          Exists: {full_path.exists()}")

                            # Check what's connected to this node
                            print(f"          Connected to:")
                            for output in node.outputs:
                                for link in output.links:
                                    print(f"            -> {link.to_node.name}.{link.to_socket.name}")
                        else:
                            print(f"          Exists: {image_path.exists()}")
            else:
                print(f"   ⚠️ Material not using nodes")

    # Check what texture files are available
    blend_dir = Path(blend_file).parent
    print(f"\n📁 Available files in {blend_dir.name}:")
    for file_path in sorted(blend_dir.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.hdr']:
            print(f"  🖼️ {file_path.relative_to(blend_dir)}")

if __name__ == "__main__":
    # Test with European beech twig
    beech_files = list(Path("data/assets/twigs").glob("**/EuropeanBeechSummerTwig.blend"))
    if beech_files:
        debug_blend_materials(beech_files[0])
    else:
        print("No EuropeanBeechSummerTwig.blend found")