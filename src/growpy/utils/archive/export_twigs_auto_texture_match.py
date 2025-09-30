#!/usr/bin/env python3
"""
Twig export with automatic texture matching from available files.
Scans directory for texture files and intelligently matches them to materials.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script with automatic texture file matching."""
    script_content = '''#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

def center_object_at_origin(obj):
    """Move object to origin (0,0,0)."""
    import bpy

    obj.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Centered {obj.name} at origin")

def find_available_textures(blend_dir):
    """Find all texture files in the blend directory and subdirectories."""
    texture_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.hdr', '.bmp']
    textures = []

    for ext in texture_extensions:
        textures.extend(blend_dir.rglob(f"*{ext}"))
        textures.extend(blend_dir.rglob(f"*{ext.upper()}"))

    return textures

def is_color_texture(filename):
    """Determine if a texture file is likely a color/diffuse texture."""
    name_lower = filename.lower()

    # Skip these types
    skip_keywords = ['bump', 'normal', 'roughness', 'metallic', 'specular', 'ao', 'occlusion']
    for keyword in skip_keywords:
        if keyword in name_lower:
            return False

    # Prefer these types
    prefer_keywords = ['diffuse', 'albedo', 'color', 'base']
    for keyword in prefer_keywords:
        if keyword in name_lower:
            return True

    # Generally accept others unless they seem like special maps
    return True

def find_best_texture_for_material(material_name, available_textures):
    """Find the best texture file for a given material name."""
    color_textures = [tex for tex in available_textures if is_color_texture(tex.name)]

    if not color_textures:
        return None

    material_lower = material_name.lower()

    # Try to find textures that match the material name
    exact_matches = []
    partial_matches = []
    general_matches = []

    for texture in color_textures:
        tex_name_lower = texture.stem.lower()

        # Exact material name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            exact_matches.append(texture)
        # Partial matches (like "beech" in material matching "beechdiffuse")
        elif any(word in tex_name_lower for word in material_lower.split() if len(word) > 3):
            partial_matches.append(texture)
        # General color textures
        else:
            general_matches.append(texture)

    # Return best match
    if exact_matches:
        # Prefer diffuse/color textures if multiple exact matches
        for tex in exact_matches:
            if any(keyword in tex.stem.lower() for keyword in ['diffuse', 'color', 'albedo']):
                return tex
        return exact_matches[0]

    if partial_matches:
        return partial_matches[0]

    if general_matches:
        return general_matches[0]

    return None

def create_auto_material(material_name, available_textures, output_dir):
    """Create a material with automatically matched texture."""
    import bpy

    # Find best texture for this material
    best_texture = find_best_texture_for_material(material_name, available_textures)

    if not best_texture:
        print(f"    No suitable texture found for {material_name}")
        return None

    print(f"    Matched {material_name} -> {best_texture.name}")

    # Copy texture to output directory
    texture_name = f"{material_name}_{best_texture.name}"
    dest_texture = output_dir / texture_name

    try:
        shutil.copy2(best_texture, dest_texture)
        print(f"    Copied: {texture_name}")
    except Exception as e:
        print(f"    Failed to copy texture: {e}")
        return None

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{material_name}_Auto")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create node setup
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)

    tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
    tex_node.location = (-400, 0)

    # Load texture
    try:
        tex_image = bpy.data.images.load(str(dest_texture))
        tex_image.name = texture_name
        tex_node.image = tex_image
    except Exception as e:
        print(f"    Failed to load texture: {e}")
        return None

    # Connect nodes
    links = new_mat.node_tree.links
    links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Set material properties
    principled_node.inputs['Roughness'].default_value = 0.7
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    print(f"    Created auto material: {new_mat.name}")
    return new_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with automatic texture matching."""
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

        # Find available textures in the directory
        blend_dir = Path(blend_path).parent
        available_textures = find_available_textures(blend_dir)

        print(f"Found {len(available_textures)} texture files in directory:")
        for tex in available_textures:
            print(f"  📁 {tex.relative_to(blend_dir)}")

        # Find all mesh objects
        mesh_objects = [obj for obj in bpy.context.scene.objects
                       if obj.type == 'MESH' and obj.data]

        if not mesh_objects:
            print(f"No mesh objects found in {blend_path}")
            return False

        print(f"\\nFound {len(mesh_objects)} objects to export")

        exported_count = 0

        for obj in mesh_objects:
            try:
                print(f"\\n🌿 Processing: {obj.name}")

                # Center object at origin
                center_object_at_origin(obj)

                # Process materials with automatic texture matching
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        auto_material = create_auto_material(
                            slot.material.name,
                            available_textures,
                            output_dir
                        )

                        if auto_material:
                            slot.material = auto_material
                        else:
                            print(f"    Keeping original material (no texture found)")

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
        ], capture_output=True, text=True, timeout=120)

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
        print("Usage: python export_twigs_auto_texture_match.py <twig_directory>")
        print("Example: python export_twigs_auto_texture_match.py data/assets/twigs")
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
    print("🔍 Using automatic texture file matching from directories...")

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