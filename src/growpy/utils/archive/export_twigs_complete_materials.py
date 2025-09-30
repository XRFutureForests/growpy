#!/usr/bin/env python3
"""
Complete twig export with all texture types (diffuse, alpha, normal, translucent).
Automatically matches and connects all available textures to proper material inputs.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from tqdm import tqdm


def create_single_file_processor():
    """Create a Python script with complete texture mapping."""
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

def classify_texture_type(filename):
    """Classify texture type based on filename, handling varied naming conventions."""
    name_lower = filename.lower()

    # Handle specific patterns first
    if 'bump' in name_lower:
        return 'normal'  # Bump maps are normal maps

    if 'top' in name_lower:
        return 'diffuse_top'  # Special handling for top textures

    if 'bottom' in name_lower:
        return 'diffuse_bottom'  # Special handling for bottom textures

    # Define texture type keywords
    texture_types = {
        'diffuse': ['diffuse', 'albedo', 'color', 'base', 'diff'],
        'alpha': ['alpha', 'opacity', 'mask', 'transparent'],
        'normal': ['normal', 'norm', 'nrm'],
        'translucent': ['translucent', 'translucency', 'transmission', 'sss'],
        'roughness': ['roughness', 'rough'],
        'metallic': ['metallic', 'metal', 'met'],
        'specular': ['specular', 'spec'],
        'ao': ['ao', 'occlusion', 'ambient']
    }

    for tex_type, keywords in texture_types.items():
        if any(keyword in name_lower for keyword in keywords):
            return tex_type

    # Default to diffuse if no specific type detected
    return 'diffuse'

def find_textures_for_material(material_name, available_textures):
    """Find all relevant textures for a material, organized by type."""
    material_lower = material_name.lower()

    # Group textures by type
    texture_map = {
        'diffuse': [],
        'diffuse_top': [],
        'diffuse_bottom': [],
        'alpha': [],
        'normal': [],
        'translucent': [],
        'roughness': [],
        'metallic': [],
        'specular': [],
        'ao': []
    }

    for texture in available_textures:
        tex_name_lower = texture.stem.lower()
        tex_type = classify_texture_type(tex_name_lower)

        # Check if this texture could belong to this material
        material_match = False

        # Direct name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            material_match = True
        # Partial match for material words
        elif any(word in tex_name_lower for word in material_lower.split() if len(word) > 3):
            material_match = True
        # For generic names or when very few textures, be more permissive
        elif len(available_textures) <= 5:  # If very few textures, accept all
            material_match = True
        # For materials with common words, try looser matching
        elif any(word in material_lower for word in ['leaf', 'bark', 'twig', 'branch'] if word in tex_name_lower):
            material_match = True

        if material_match:
            texture_map[tex_type].append(texture)

    # Return the best texture for each type
    result = {}
    for tex_type, textures in texture_map.items():
        if textures:
            # Sort by preference (prefer files with material name)
            def sort_key(tex):
                score = 0
                if material_lower in tex.stem.lower():
                    score += 10
                if tex_type in tex.stem.lower():
                    score += 5
                return score

            textures.sort(key=sort_key, reverse=True)
            result[tex_type] = textures[0]

    # Handle diffuse texture priority: prefer diffuse_top > diffuse > diffuse_bottom
    # If no standard diffuse but we have top/bottom, use the best available
    if 'diffuse' not in result:
        if 'diffuse_top' in result:
            result['diffuse'] = result['diffuse_top']
        elif 'diffuse_bottom' in result:
            result['diffuse'] = result['diffuse_bottom']

    return result

def create_complete_material(material_name, available_textures, output_dir):
    """Create a complete material with all texture types connected."""
    import bpy

    # Find textures for this material
    texture_map = find_textures_for_material(material_name, available_textures)

    # If no textures found, try to use any available texture as diffuse
    if not texture_map and available_textures:
        print(f"    No specific textures found for {material_name}, using first available texture")
        texture_map = {'diffuse': available_textures[0]}

    if not texture_map:
        print(f"    No textures found for {material_name}")
        return None

    print(f"    Found textures for {material_name}:")
    for tex_type, texture in texture_map.items():
        print(f"      {tex_type}: {texture.name}")

    # Create new material
    new_mat = bpy.data.materials.new(name=f"{material_name}_Complete")
    new_mat.use_nodes = True

    # Clear default nodes
    new_mat.node_tree.nodes.clear()

    # Create essential nodes
    output_node = new_mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (600, 0)

    principled_node = new_mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (300, 0)

    # Connect Principled to Output
    links = new_mat.node_tree.links
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Process each texture type
    y_offset = 200

    for tex_type, texture in texture_map.items():
        try:
            # Copy texture file
            texture_name = f"{material_name}_{tex_type}_{texture.name}"
            dest_texture = output_dir / texture_name
            shutil.copy2(texture, dest_texture)

            # Load texture
            tex_image = bpy.data.images.load(str(dest_texture))
            tex_image.name = texture_name

            # Create texture node
            tex_node = new_mat.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex_node.image = tex_image
            tex_node.location = (0, y_offset)
            tex_node.label = tex_type.title()

            # Connect to appropriate Principled BSDF input
            if tex_type == 'diffuse':
                links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])
                print(f"      Connected {tex_type} to Base Color")

            elif tex_type == 'alpha':
                links.new(tex_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                new_mat.blend_method = 'BLEND'  # Enable transparency
                print(f"      Connected {tex_type} to Alpha")

            elif tex_type == 'normal':
                # Create normal map node
                normal_node = new_mat.node_tree.nodes.new(type='ShaderNodeNormalMap')
                normal_node.location = (150, y_offset - 50)
                links.new(tex_node.outputs['Color'], normal_node.inputs['Color'])
                links.new(normal_node.outputs['Normal'], principled_node.inputs['Normal'])
                print(f"      Connected {tex_type} via Normal Map node")

            elif tex_type == 'translucent':
                if 'Transmission Weight' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Transmission Weight'])
                    print(f"      Connected {tex_type} to Transmission Weight")
                elif 'Transmission' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Transmission'])
                    print(f"      Connected {tex_type} to Transmission")

            elif tex_type == 'roughness':
                links.new(tex_node.outputs['Color'], principled_node.inputs['Roughness'])
                print(f"      Connected {tex_type} to Roughness")

            elif tex_type == 'metallic':
                links.new(tex_node.outputs['Color'], principled_node.inputs['Metallic'])
                print(f"      Connected {tex_type} to Metallic")

            elif tex_type == 'specular':
                if 'Specular IOR Level' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Specular IOR Level'])
                    print(f"      Connected {tex_type} to Specular IOR Level")
                elif 'Specular' in principled_node.inputs:
                    links.new(tex_node.outputs['Color'], principled_node.inputs['Specular'])
                    print(f"      Connected {tex_type} to Specular")

            y_offset -= 300

        except Exception as e:
            print(f"      Failed to process {tex_type} texture: {e}")
            continue

    # Set good default values
    principled_node.inputs['Roughness'].default_value = 0.7
    if 'Specular IOR Level' in principled_node.inputs:
        principled_node.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in principled_node.inputs:
        principled_node.inputs['Specular'].default_value = 0.5

    print(f"    Created complete material: {new_mat.name}")
    return new_mat

def export_single_blend_file(blend_path, output_dir):
    """Process a single blend file with complete material setup."""
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

        print(f"Found {len(available_textures)} texture files:")
        for tex in available_textures:
            tex_type = classify_texture_type(tex.stem)
            print(f"  {tex_type:>10}: {tex.relative_to(blend_dir)}")

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

                # Process materials with complete texture setup
                for i, slot in enumerate(obj.material_slots):
                    if slot.material:
                        print(f"  Processing material {i}: {slot.material.name}")
                        complete_material = create_complete_material(
                            slot.material.name,
                            available_textures,
                            output_dir
                        )

                        if complete_material:
                            slot.material = complete_material

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
        print("Usage: python export_twigs_complete_materials.py <twig_directory>")
        print("Example: python export_twigs_complete_materials.py data/assets/twigs")
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
    print("🎨 Creating complete materials with all texture types (diffuse, alpha, normal, translucent)...")

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