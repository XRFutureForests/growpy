#!/usr/bin/env python3
"""
Enhanced twig converter with robust texture handling and standardized naming.

This improved version:
1. Detects and uses ALL available texture types (diffuse, alpha, normal, translucent, etc.)
2. Standardizes twig naming to match Grove tree attributes (apical/lateral/dead)
3. Handles varied texture naming conventions intelligently
4. Embeds textures properly in FBX exports
5. Creates comprehensive material setups for Unreal Engine

Twig Type Mapping:
    Grove Attributes -> Standard Names
    - twig_long / twig_end / Apical -> apical (terminal/end twigs)
    - twig_short / twig_side / Lateral -> lateral (side branches)
    - twig_upward -> upward (upward-facing twigs)
    - twig_dead / Dead -> dead (dead/winter twigs)
    - A/B/C/Var -> variation_a/b/c (variants within type)

Usage:
    python convert_twigs_v2.py <twig_directory> [--formats fbx usd usda]
    python convert_twigs_v2.py <single_blend_file> [--formats fbx usd]
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

# Standardized twig type mapping
TWIG_NAME_MAPPINGS = {
    # Apical/Terminal/End twigs (twig_long attribute)
    "apical": ["apical", "end", "long", "terminal", "tip"],
    # Lateral/Side twigs (twig_short attribute)
    "lateral": ["lateral", "side", "short", "laterall"],  # note: typo in some files
    # Upward-facing twigs (twig_upward attribute)
    "upward": ["upward", "up"],
    # Dead/Fall/Winter twigs (twig_dead attribute)
    "dead": ["dead", "fall", "winter", "bare"],
    # Summer/Spring variants
    "summer": ["summer", "spring", "green"],
}

# Texture type classifications with extended keywords
TEXTURE_CLASSIFICATIONS = {
    "diffuse": ["diffuse", "albedo", "color", "basecolor", "base", "diff", "col"],
    "alpha": ["alpha", "opacity", "mask", "transparent", "cutout"],
    "normal": ["normal", "norm", "nrm", "bump", "height"],
    "translucent": ["translucent", "translucency", "transmission", "sss", "subsurface"],
    "roughness": ["roughness", "rough", "gloss", "glossiness"],
    "metallic": ["metallic", "metal", "metalness"],
    "ao": ["ao", "ambient", "occlusion", "ambientocclusion"],
    "emissive": ["emissive", "emission", "glow"],
}

# Special texture patterns (top/bottom for leaves)
TEXTURE_MODIFIERS = {
    "top": ["top", "upper", "face"],
    "bottom": ["bottom", "lower", "back", "underside"],
}


def standardize_twig_name(original_name: str, species_name: str) -> Tuple[str, Dict]:
    """
    Convert varied twig naming to standardized format.

    Returns:
        (standardized_name, metadata_dict)

    Examples:
        "BeechApicalTwig" -> ("beech_apical", {"type": "apical", "species": "beech"})
        "ScotsPineVariationCLateralTwig" -> ("scots_pine_lateral_var_c", {...})
        "OakEuropeanLongTwig" -> ("european_oak_apical", {"type": "apical"})
    """
    name_lower = original_name.lower()

    # Extract metadata
    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",  # Default
        "variation": None,
        "season": None,
        "is_standardized": True,
    }

    # Detect twig type
    for standard_type, keywords in TWIG_NAME_MAPPINGS.items():
        if any(kw in name_lower for kw in keywords):
            metadata["type"] = standard_type
            break

    # Detect variation (A, B, C, Var, Variation)
    for letter in ["a", "b", "c", "d", "e"]:
        if f"var{letter}" in name_lower or f"variation{letter}" in name_lower:
            metadata["variation"] = letter
            break
        # Single letter patterns like "TwigA", "TwigB"
        if name_lower.endswith(f"twig{letter}") or name_lower.endswith(f"{letter}twig"):
            metadata["variation"] = letter
            break

    # Detect season
    for season_type, keywords in TWIG_NAME_MAPPINGS.items():
        if season_type in ["summer", "dead"] and any(
            kw in name_lower for kw in keywords
        ):
            metadata["season"] = season_type

    # Build standardized name
    parts = []

    # Species name (clean)
    species_clean = species_name.lower().replace(" ", "_")
    parts.append(species_clean)

    # Twig type
    if metadata["type"] != "generic":
        parts.append(metadata["type"])

    # Variation
    if metadata["variation"]:
        parts.append(f"var_{metadata['variation']}")

    # Season modifier
    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(metadata["season"])

    standardized = "_".join(parts)

    return standardized, metadata


def classify_texture_type(texture_path: Path, material_name: str = "") -> str:
    """
    Classify texture type from filename with context awareness.

    Handles:
    - Standard PBR naming (diffuse, normal, etc.)
    - Top/bottom variants for leaves
    - Compound names with duplicates
    """
    name_lower = texture_path.stem.lower()

    # Check for modifiers first (top/bottom)
    modifier = None
    for mod_type, keywords in TEXTURE_MODIFIERS.items():
        if any(kw in name_lower for kw in keywords):
            modifier = mod_type
            break

    # Classify base type
    base_type = "diffuse"  # Default
    for tex_type, keywords in TEXTURE_CLASSIFICATIONS.items():
        if any(kw in name_lower for kw in keywords):
            base_type = tex_type
            break

    # Combine with modifier if present
    if modifier and base_type == "diffuse":
        return f"diffuse_{modifier}"

    return base_type


def find_textures_for_material(
    blend_dir: Path, material_name: str, search_parent: bool = True
) -> Dict[str, Path]:
    """
    Find all available textures for a material with intelligent matching.

    Returns:
        Dict mapping texture type to file path
        e.g., {'diffuse': Path(...), 'alpha': Path(...), 'normal': Path(...)}
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]
    texture_map = {}

    # Search locations
    search_dirs = [blend_dir / "textures", blend_dir]
    if search_parent:
        search_dirs.extend([blend_dir.parent / "textures", blend_dir.parent])

    # Find all textures
    available_textures = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(search_dir.glob(f"*{ext}"))
            available_textures.extend(search_dir.glob(f"*{ext.upper()}"))

    # Remove duplicates and HDR placeholders
    available_textures = list(set(available_textures))
    available_textures = [
        t
        for t in available_textures
        if not t.stem.startswith("color_") or not t.suffix == ".hdr"
    ]

    if not available_textures:
        return texture_map

    # Match textures to material
    material_lower = material_name.lower()
    material_words = set(material_lower.replace("_", " ").split())

    for texture in available_textures:
        tex_name_lower = texture.stem.lower()
        tex_type = classify_texture_type(texture, material_name)

        # Scoring system for texture matching
        match_score = 0

        # Direct name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            match_score += 10

        # Word overlap
        tex_words = set(tex_name_lower.replace("_", " ").split())
        overlap = len(material_words & tex_words)
        match_score += overlap * 3

        # Species name in texture
        species_words = {"beech", "oak", "pine", "maple", "birch", "alder"}
        if any(word in tex_name_lower for word in material_words & species_words):
            match_score += 5

        # If few textures, be permissive
        if len(available_textures) <= 5:
            match_score += 2

        # Accept if reasonable match
        if match_score > 0:
            # Keep best match for each type
            if tex_type not in texture_map:
                texture_map[tex_type] = (texture, match_score)
            elif match_score > texture_map[tex_type][1]:
                texture_map[tex_type] = (texture, match_score)

    # Extract paths from (path, score) tuples
    texture_map = {k: v[0] for k, v in texture_map.items()}

    return texture_map


def create_processor_script() -> str:
    """Generate Blender Python script for processing twigs."""

    return '''
import sys
import shutil
from pathlib import Path
import json

def process_twig_file(blend_file, output_dir, formats, species_name):
    """Process a single twig blend file."""
    import bpy
    
    print("")
    print(f"Processing: {Path(blend_file).name}")
    print(f"Species: {species_name}")
    
    # Load blend file
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))
    
    blend_path = Path(blend_file)
    blend_dir = blend_path.parent
    
    # Find all mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not mesh_objects:
        print("  [WARN] No mesh objects found")
        return []
    
    print(f"  Found {len(mesh_objects)} mesh object(s)")
    
    exported_files = []
    texture_manifest = {}
    
    for obj in mesh_objects:
        try:
            # Clear selection
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            
            # Standardize object name
            original_name = obj.name
            standardized_name, metadata = standardize_twig_name(original_name, species_name)
            
            print(f"  Processing: {original_name}")
            print(f"    -> Standardized: {standardized_name}")
            print(f"    -> Type: {metadata['type']}, Variation: {metadata.get('variation', 'none')}")
            
            # Center at origin
            obj.location = (0, 0, 0)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            
            # Create mount point (empty at origin for Unreal PCG attachment)
            mount_point = bpy.data.objects.new(f"{standardized_name}_mount", None)
            mount_point.location = (0, 0, 0)
            mount_point.empty_display_type = 'SPHERE'
            mount_point.empty_display_size = 0.01
            bpy.context.collection.objects.link(mount_point)
            
            # Parent mesh to mount point for proper hierarchy
            obj.parent = mount_point
            
            print(f"    -> Created mount point at origin")
            
            # Find and setup materials with textures
            material_setup_success = setup_materials_with_textures(
                obj, blend_dir, species_name, output_dir
            )
            
            if material_setup_success:
                print(f"    -> Materials: {len(obj.data.materials)} with textures")
            else:
                print(f"    -> Materials: {len(obj.data.materials)} (fallback)")
            
            # Select mount point and mesh for export (hierarchical export)
            bpy.ops.object.select_all(action='DESELECT')
            mount_point.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = mount_point
            
            # Export in requested formats
            for fmt in formats:
                if fmt in ['usd', 'usda']:
                    export_path = output_dir / f"{standardized_name}.{fmt}"
                    print(f"    -> Exporting USD: {export_path.name}")
                    
                    bpy.ops.wm.usd_export(
                        filepath=str(export_path),
                        selected_objects_only=True,
                        export_materials=True,
                        export_textures=True,
                        export_uvmaps=True,
                        export_normals=True,
                        export_mesh_colors=True,
                        use_instancing=False,
                        evaluation_mode='RENDER',
                        generate_preview_surface=True
                    )
                    
                    exported_files.append(export_path)
                    
                elif fmt == 'fbx':
                    export_path = output_dir / f"{standardized_name}.fbx"
                    print(f"    -> Exporting FBX: {export_path.name}")
                    
                    bpy.ops.export_scene.fbx(
                        filepath=str(export_path),
                        use_selection=True,
                        object_types={'MESH', 'EMPTY'},  # Include EMPTY for mount point
                        mesh_smooth_type='FACE',
                        use_mesh_modifiers=True,
                        use_mesh_edges=False,
                        use_tspace=True,
                        use_custom_props=True,
                        add_leaf_bones=False,
                        primary_bone_axis='Y',
                        secondary_bone_axis='X',
                        path_mode='COPY',
                        embed_textures=True,  # Critical for texture embedding
                        batch_mode='OFF',
                        axis_forward='-Z',
                        axis_up='Y'
                    )
                    
                    exported_files.append(export_path)
            
            # Store metadata
            texture_manifest[standardized_name] = {
                'original_name': original_name,
                'metadata': metadata,
                'materials': [mat.name for mat in obj.data.materials] if obj.data.materials else [],
                'export_formats': formats
            }
            
            print(f"    -> [OK] Exported successfully")
            
        except Exception as e:
            print(f"    -> [ERROR] {e}")
            continue
    
    # Save manifest
    if texture_manifest:
        manifest_path = output_dir / "twig_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(texture_manifest, f, indent=2)
        print("")
        print(f"  Saved manifest: {manifest_path.name}")
    
    return exported_files


def standardize_twig_name(original_name, species_name):
    """Standardize twig naming (matches main script logic)."""
    name_lower = original_name.lower()
    
    metadata = {
        'original_name': original_name,
        'species': species_name,
        'type': 'generic',
        'variation': None,
        'season': None,
    }
    
    # Detect type
    if any(kw in name_lower for kw in ['apical', 'end', 'long', 'terminal', 'tip']):
        metadata['type'] = 'apical'
    elif any(kw in name_lower for kw in ['lateral', 'side', 'short', 'laterall']):
        metadata['type'] = 'lateral'
    elif any(kw in name_lower for kw in ['upward', 'up']):
        metadata['type'] = 'upward'
    elif any(kw in name_lower for kw in ['dead', 'fall', 'winter', 'bare']):
        metadata['type'] = 'dead'
    elif any(kw in name_lower for kw in ['summer', 'spring', 'green']):
        metadata['season'] = 'summer'
    
    # Detect variation
    for letter in ['a', 'b', 'c', 'd', 'e']:
        if any(pat in name_lower for pat in [f'var{letter}', f'variation{letter}', f'twig{letter}', f'{letter}twig']):
            metadata['variation'] = letter
            break
    
    # Build name
    parts = [species_name.lower().replace(' ', '_')]
    
    if metadata['type'] != 'generic':
        parts.append(metadata['type'])
    
    if metadata['variation']:
        parts.append(f"var_{metadata['variation']}")
    
    if metadata['season'] and metadata['season'] != metadata['type']:
        parts.append(metadata['season'])
    
    return '_'.join(parts), metadata


def setup_materials_with_textures(obj, blend_dir, species_name, output_dir):
    """Setup materials with all available textures."""
    import bpy
    
    texture_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.bmp']
    
    # Find textures
    search_dirs = [blend_dir / 'textures', blend_dir, blend_dir.parent / 'textures']
    available_textures = []
    
    for search_dir in search_dirs:
        if not Path(search_dir).exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(Path(search_dir).glob(f"*{ext}"))
    
    # Remove placeholders
    available_textures = [
        t for t in available_textures 
        if not (t.stem.startswith('color_') and t.suffix == '.hdr')
    ]
    
    if not available_textures:
        print("      No textures found, using default material")
        return False
    
    # Clear existing materials
    obj.data.materials.clear()
    
    # Group existing materials by base name
    material_groups = {}
    existing_materials = list(bpy.data.materials)
    
    for texture in available_textures:
        # Find best material match
        mat_name = None
        for mat in existing_materials:
            if mat.name.lower() in texture.stem.lower() or texture.stem.lower() in mat.name.lower():
                mat_name = mat.name
                break
        
        if not mat_name:
            # Create generic material name
            mat_name = species_name
        
        if mat_name not in material_groups:
            material_groups[mat_name] = []
        material_groups[mat_name].append(texture)
    
    # If no good grouping, use all textures for single material
    if not material_groups:
        material_groups[species_name] = available_textures
    
    # Create materials
    materials_created = 0
    
    for mat_name, textures in material_groups.items():
        material = bpy.data.materials.new(name=f"{species_name}_{mat_name}")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        nodes.clear()
        
        # Create base nodes
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (400, 0)
        
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        # Classify and add textures
        texture_map = {}
        for tex in textures:
            tex_type = classify_texture_from_name(tex.stem)
            if tex_type not in texture_map:
                texture_map[tex_type] = tex
        
        print(f"      Material '{mat_name}': {list(texture_map.keys())}")
        
        # Add texture nodes
        y_offset = 300
        
        for tex_type, tex_path in texture_map.items():
            try:
                # Copy texture to output
                dest_tex = output_dir / tex_path.name
                if not dest_tex.exists():
                    shutil.copy2(tex_path, dest_tex)
                
                # Create texture node
                tex_node = nodes.new('ShaderNodeTexImage')
                # Use absolute path for texture loading
                tex_path_abs = Path(tex_path).resolve()
                tex_node.image = bpy.data.images.load(str(tex_path_abs))
                tex_node.location = (-400, y_offset)
                tex_node.label = tex_type.title()
                
                # Connect based on type
                if 'diffuse' in tex_type:
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                    if 'diffuse_top' in tex_type:
                        tex_node.label = "Diffuse Top"
                
                elif tex_type == 'alpha':
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Alpha'])
                    material.blend_method = 'CLIP'
                    if hasattr(material, 'shadow_method'):
                        material.shadow_method = 'CLIP'
                
                elif tex_type == 'normal':
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                    normal_map = nodes.new('ShaderNodeNormalMap')
                    normal_map.location = (-200, y_offset - 100)
                    links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
                
                elif tex_type == 'translucent':
                    # Transmission changed to Transmission Weight in newer Blender
                    if 'Transmission' in bsdf.inputs:
                        links.new(tex_node.outputs['Color'], bsdf.inputs['Transmission'])
                        bsdf.inputs['Transmission'].default_value = 0.3
                    elif 'Transmission Weight' in bsdf.inputs:
                        links.new(tex_node.outputs['Color'], bsdf.inputs['Transmission Weight'])
                        bsdf.inputs['Transmission Weight'].default_value = 0.3
                
                elif tex_type == 'roughness':
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Roughness'])
                
                elif tex_type == 'metallic':
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Metallic'])
                
                elif tex_type == 'ao':
                    # Multiply with base color
                    if 'diffuse' in texture_map:
                        mix = nodes.new('ShaderNodeMixRGB')
                        mix.blend_type = 'MULTIPLY'
                        mix.location = (-200, y_offset)
                        links.new(tex_node.outputs['Color'], mix.inputs[2])
                
                y_offset -= 250
                
            except Exception as e:
                print(f"      Warning: Could not load texture {tex_path.name}: {e}")
        
        # Set material properties for foliage
        # Specular changed to Specular IOR in Blender 4.x
        if 'Specular' in bsdf.inputs:
            bsdf.inputs['Specular'].default_value = 0.3
        elif 'Specular IOR' in bsdf.inputs:
            bsdf.inputs['Specular IOR'].default_value = 0.5
        if 'roughness' not in texture_map:
            bsdf.inputs['Roughness'].default_value = 0.7
        
        obj.data.materials.append(material)
        materials_created += 1
    
    return materials_created > 0


def classify_texture_from_name(name):
    """Classify texture type from filename."""
    name_lower = name.lower()
    
    # Check modifiers
    if 'top' in name_lower or 'upper' in name_lower:
        if any(kw in name_lower for kw in ['diffuse', 'albedo', 'color']):
            return 'diffuse_top'
    if 'bottom' in name_lower or 'lower' in name_lower:
        if any(kw in name_lower for kw in ['diffuse', 'albedo', 'color']):
            return 'diffuse_bottom'
    
    # Standard types
    if any(kw in name_lower for kw in ['alpha', 'opacity', 'mask']):
        return 'alpha'
    if any(kw in name_lower for kw in ['normal', 'norm', 'bump']):
        return 'normal'
    if any(kw in name_lower for kw in ['translucent', 'transmission', 'sss']):
        return 'translucent'
    if any(kw in name_lower for kw in ['roughness', 'rough']):
        return 'roughness'
    if any(kw in name_lower for kw in ['metallic', 'metal']):
        return 'metallic'
    if 'ao' in name_lower or 'ambient' in name_lower:
        return 'ao'
    
    return 'diffuse'


# Main execution
if __name__ == "__main__":
    blend_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    formats = sys.argv[3].split(',')
    species_name = sys.argv[4]
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    exported = process_twig_file(blend_file, output_dir, formats, species_name)
    
    print("")
    print(f"[OK] Processed {len(exported)} file(s)")
'''


def create_twig_nanite_assembly(
    twig_usd_path: Path,
    twig_name: str,
    species_name: str,
) -> bool:
    """Create a Nanite Assembly USD for a single twig following Unreal schema.

    Args:
        twig_usd_path: Path to standard twig USD file
        twig_name: Standardized twig name (e.g., "beech_apical")
        species_name: Species name

    Returns:
        bool: Success status
    """
    try:
        from pxr import Sdf, Usd, UsdGeom

        # Create Nanite Assembly file path
        nanite_path = twig_usd_path.parent / f"{twig_name}_NaniteAssembly.usda"

        # Create new stage
        stage = Usd.Stage.CreateNew(str(nanite_path))

        # Set stage metadata to match twig USD (Z-up, meters)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        # Root Xform with NaniteAssemblyRootAPI
        assembly_name = f"{twig_name.replace(' ', '_')}_NaniteAssembly"
        root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Apply NaniteAssemblyRootAPI using TokenListOp
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
        root_prim.SetMetadata("apiSchemas", api_schemas)

        # Set mesh type to staticMesh
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token, custom=False
        ).Set("staticMesh")

        # Twig mesh as ExternalRef
        twig_prim = stage.DefinePrim(f"/{assembly_name}/TwigMesh", "Xform")

        # Apply NaniteAssemblyExternalRefAPI using TokenListOp
        twig_api_schemas = Sdf.TokenListOp()
        twig_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
        twig_prim.SetMetadata("apiSchemas", twig_api_schemas)

        # Reference the standard twig USD (relative path)
        twig_prim.GetReferences().AddReference(f"./{twig_usd_path.name}")

        # Save stage
        stage.GetRootLayer().Save()

        return True

    except ImportError:
        # USD Python not available - skip Nanite Assembly creation
        return False
    except Exception as e:
        print(f"      Warning: Could not create Nanite Assembly: {e}")
        return False


def process_twig_directory(
    twig_dir: Path,
    formats: List[str] = ["fbx", "usda"],
    create_nanite_assemblies: bool = True,
) -> Dict[str, List[Path]]:
    """Process all twig blend files in a directory.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        create_nanite_assemblies: Create Nanite Assembly USD for each twig
    """

    blend_files = list(twig_dir.rglob("*.blend"))

    if not blend_files:
        print(f"No .blend files found in {twig_dir}")
        return {}

    print(f"\nFound {len(blend_files)} .blend file(s)")
    print(f"Export formats: {', '.join(formats)}")
    if create_nanite_assemblies and ("usd" in formats or "usda" in formats):
        print(f"Nanite Assemblies: Enabled")
    print(f"{'='*60}\n")

    # Create temporary processor script
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(create_processor_script())
        processor_script = Path(f.name)

    try:
        results = {}

        for blend_file in tqdm(blend_files, desc="Converting twigs"):
            try:
                # Determine species name from directory
                species_name = blend_file.parent.name.replace("Twig", "").replace(
                    "_", " "
                )
                output_dir = blend_file.parent

                # Run processor script with Python (which has bpy module)
                cmd = [
                    sys.executable,
                    str(processor_script),
                    str(blend_file),
                    str(output_dir),
                    ",".join(formats),
                    species_name,
                ]

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
                )

                # Show output
                if result.stdout:
                    print(result.stdout)

                if result.returncode == 0:
                    # Find exported files
                    exported_usd_files = []
                    for fmt in formats:
                        exported = list(output_dir.glob(f"*.{fmt}"))
                        if species_name not in results:
                            results[species_name] = []
                        results[species_name].extend(exported)

                        # Track USD files for Nanite Assembly creation
                        if fmt in ["usd", "usda"]:
                            exported_usd_files.extend(exported)

                    # Create Nanite Assembly versions
                    if create_nanite_assemblies and exported_usd_files:
                        print(f"\n  Creating Nanite Assemblies...")
                        for usd_file in exported_usd_files:
                            # Skip if it's already a Nanite Assembly or manifest
                            if (
                                "_NaniteAssembly" in usd_file.name
                                or usd_file.suffix == ".json"
                            ):
                                continue

                            twig_name = usd_file.stem
                            if create_twig_nanite_assembly(
                                usd_file, twig_name, species_name
                            ):
                                nanite_file = (
                                    usd_file.parent / f"{twig_name}_NaniteAssembly.usda"
                                )
                                if nanite_file.exists():
                                    print(f"    ✓ {nanite_file.name}")
                                    results[species_name].append(nanite_file)

                else:
                    print(f"\n[ERROR] Processing {blend_file.name}")
                    if result.stderr:
                        print(result.stderr[-1000:])  # Last 1000 chars

            except subprocess.TimeoutExpired:
                print(f"\n[ERROR] Timeout processing {blend_file.name} (>5 minutes)")
            except Exception as e:
                print(f"\n[ERROR] Exception processing {blend_file.name}: {e}")

        return results

    finally:
        # Cleanup
        if processor_script.exists():
            processor_script.unlink()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Grove twig files with robust texture handling and standardized naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert all twigs with Nanite Assemblies (default)
    python convert_twigs.py data/assets/twigs --formats usda
    
    # Convert with both FBX and Nanite Assembly USD
    python convert_twigs.py data/assets/twigs --formats fbx usda
    
    # Convert without Nanite Assemblies
    python convert_twigs.py data/assets/twigs --formats usda --no-nanite-assembly
    
    # Convert specific species
    python convert_twigs.py data/assets/twigs/Betulaceae_Downy_birch --formats usda

Output per twig:
    - standard_name.usda                   # Standard USD (DCC compatible)
    - standard_name_NaniteAssembly.usda   # Nanite Assembly (Unreal optimized)
        """,
    )
    parser.add_argument(
        "path", type=Path, help="Path to twig directory or single .blend file"
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["fbx", "usd", "usda"],
        default=["fbx", "usda"],
        help="Export formats (default: fbx usda)",
    )
    parser.add_argument(
        "--create-nanite-assembly",
        dest="create_nanite_assembly",
        action="store_true",
        default=True,
        help="Create Nanite Assembly USD for each twig (default: True)",
    )
    parser.add_argument(
        "--no-nanite-assembly",
        dest="create_nanite_assembly",
        action="store_false",
        help="Skip Nanite Assembly USD creation",
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    if args.path.is_file() and args.path.suffix == ".blend":
        # Single file
        print(f"Processing single file: {args.path.name}")
        results = process_twig_directory(
            args.path.parent, args.formats, args.create_nanite_assembly
        )
    elif args.path.is_dir():
        # Directory
        results = process_twig_directory(
            args.path, args.formats, args.create_nanite_assembly
        )
    else:
        print(f"Error: Invalid path (must be .blend file or directory)")
        return 1

    # Summary
    print(f"\n{'='*60}")
    print("Conversion Complete")
    print(f"{'='*60}")

    total_files = sum(len(files) for files in results.values())
    print(f"\nTotal exported: {total_files} files")
    print(f"Species processed: {len(results)}")

    # Count Nanite Assemblies
    if args.create_nanite_assembly:
        nanite_count = sum(
            1
            for files in results.values()
            for f in files
            if "_NaniteAssembly" in f.name
        )
        if nanite_count > 0:
            print(f"Nanite Assemblies created: {nanite_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
