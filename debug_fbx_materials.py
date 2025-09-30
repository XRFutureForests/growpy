#!/usr/bin/env python3
"""
Debug script to test FBX material export and import.
"""

import bpy
from pathlib import Path

def test_fbx_material_export():
    """Test FBX export with proper material setup."""

    # Clear and load the twig
    bpy.ops.wm.read_factory_settings(use_empty=True)
    blend_file = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig.blend")
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))

    # Get the twig object
    obj = bpy.context.scene.objects.get('MannaGumTwig')
    if not obj:
        print("❌ No MannaGumTwig object found")
        return

    print(f"🌿 Working with object: {obj.name}")

    # Check current materials
    for i, slot in enumerate(obj.material_slots):
        if not slot.material:
            continue

        mat = slot.material
        print(f"📄 Material {i}: {mat.name}")

        if mat.use_nodes:
            # Look for image texture nodes
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    print(f"  🖼️ Image texture: {node.image.name}")
                    print(f"     Path: {node.image.filepath}")

                    # Make sure image is loaded
                    if not node.image.has_data:
                        print("     ⚠️ Image has no data, trying to reload...")
                        node.image.reload()

                    # Ensure absolute path
                    abs_path = Path(node.image.filepath_from_user())
                    if abs_path.exists():
                        node.image.filepath = str(abs_path)
                        print(f"     ✅ Set absolute path: {abs_path}")

    # Select only this object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Test export with different settings
    output_dir = Path("data/assets/twigs/MannaGumTwig")

    test_files = {
        "test_auto.fbx": {"path_mode": 'AUTO'},
        "test_copy.fbx": {"path_mode": 'COPY'},
        "test_absolute.fbx": {"path_mode": 'ABSOLUTE'},
        "test_relative.fbx": {"path_mode": 'RELATIVE'},
        "test_strip.fbx": {"path_mode": 'STRIP'},
    }

    for filename, settings in test_files.items():
        fbx_path = output_dir / filename
        print(f"\\n📤 Testing export: {filename} with path_mode='{settings['path_mode']}'")

        try:
            bpy.ops.export_scene.fbx(
                filepath=str(fbx_path),
                use_selection=True,
                object_types={'MESH'},
                global_scale=1.0,
                path_mode=settings['path_mode'],
                embed_textures=False,
                use_mesh_modifiers=True,
                mesh_smooth_type='FACE',
                use_tspace=True,
                # Try to ensure materials are included
                use_custom_props=True,
                bake_anim=False
            )
            print(f"     ✅ Export succeeded")

            # Check file size
            if fbx_path.exists():
                size = fbx_path.stat().st_size
                print(f"     📊 File size: {size:,} bytes")

        except Exception as e:
            print(f"     ❌ Export failed: {e}")

    # Test import back into Blender
    print("\\n🔄 Testing import back...")

    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Import the FBX
    test_fbx = output_dir / "test_copy.fbx"
    if test_fbx.exists():
        try:
            bpy.ops.import_scene.fbx(filepath=str(test_fbx))
            print("✅ FBX import succeeded")

            # Check what was imported
            imported_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
            for obj in imported_objects:
                print(f"📦 Imported object: {obj.name}")
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        mat = slot.material
                        print(f"  📄 Material {i}: {mat.name}")

                        # Check if material has texture nodes
                        if mat.use_nodes:
                            tex_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
                            print(f"       Texture nodes: {len(tex_nodes)}")
                            for node in tex_nodes:
                                if node.image:
                                    print(f"         🖼️ {node.image.name}: {node.image.filepath}")
                                else:
                                    print(f"         ❌ Texture node with no image")
                        else:
                            print(f"       ⚠️ Material not using nodes")
                    else:
                        print(f"  ❌ Empty material slot {i}")

        except Exception as e:
            print(f"❌ FBX import failed: {e}")

if __name__ == "__main__":
    test_fbx_material_export()