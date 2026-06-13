#!/usr/bin/env python3
"""Material and texture handling for twig USD export.

Functions for setting up Blender materials with textures, copying textures
for skeletal exports, and classifying texture types from filenames.
Runs inside Blender's Python environment.

DEPENDENCIES:
    - bpy (Blender Python API) - installed via conda environment (environment.yml)
    - pxr (USD tools: Gf, Sdf, UsdGeom, UsdShade) - bundled with bpy
    - All USD functionality available through bpy.utils.expose_bundled_modules()

Note: No standalone Blender installation is required. The code runs in Blender's
Python environment via the bpy module which includes pxr (USD tools) bundled within.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

import bpy

try:
    from pxr import Gf, Sdf, UsdGeom, UsdShade
except ImportError:
    # Standalone mode - do manual initialization
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    from pxr import Gf, Sdf, UsdGeom, UsdShade


# -----------------------------------------------------------------------------
# Texture classification
# -----------------------------------------------------------------------------


def classify_texture_from_name(name):
    """Classify texture type from filename, with support for material variants.

    Supports texture categories:
    - Seasonal variants: summer (preferred) > fall/winter > spring
    - Material parts: leaf (default), bark
    - View variants: top (preferred) > bottom
    """
    name_lower = name.lower()

    # Check for specific texture types first (alpha, normal, bump, etc.)
    # These take precedence over top/bottom classification
    if any(kw in name_lower for kw in ["alpha", "opacity", "mask"]):
        return "alpha"
    # Distinguish between normal maps (RGB) and bump maps (grayscale height)
    if any(kw in name_lower for kw in ["normal", "norm", "nrm"]):
        return "normal"
    if any(kw in name_lower for kw in ["bump", "height", "displacement"]):
        return "bump"

    # Check for bark texture
    if "bark" in name_lower:
        has_top = "top" in name_lower or "upper" in name_lower or "face" in name_lower
        has_bottom = (
            "bottom" in name_lower or "lower" in name_lower or "back" in name_lower
        )
        if has_top and not has_bottom:
            return "bark_top"
        if has_bottom and not has_top:
            return "bark_bottom"
        return "bark"

    # Check for top/bottom diffuse textures
    # These can have explicit "diffuse" keyword OR be implicit (e.g., "OakTop.png")
    has_top = "top" in name_lower or "upper" in name_lower or "face" in name_lower
    has_bottom = "bottom" in name_lower or "lower" in name_lower or "back" in name_lower

    # If it has top/bottom keywords, classify as two-sided texture
    # Even without explicit "diffuse" keyword (e.g., Grove's "OakTop.png")
    if has_top and not has_bottom:
        return "diffuse_top"
    if has_bottom and not has_top:
        return "diffuse_bottom"

    # Continue with other standard types
    if any(kw in name_lower for kw in ["translucent", "transmission", "sss"]):
        return "translucent"
    if any(kw in name_lower for kw in ["roughness", "rough"]):
        return "roughness"
    if any(kw in name_lower for kw in ["metallic", "metal"]):
        return "metallic"
    if "ao" in name_lower or "ambient" in name_lower:
        return "ao"

    return "diffuse"


# -----------------------------------------------------------------------------
# Texture copying for skeletal export
# -----------------------------------------------------------------------------


def copy_opaque_textures_for_skeletal(
    blend_dir, output_dir, standardized_name, metadata
):
    """Copy only opaque textures for skeletal twig exports.

    CRITICAL: Filters out alpha/translucent/mask textures for Nanite compatibility.
    Only copies opaque texture types (diffuse, normal).
    Converts bump maps to normal maps automatically.

    Args:
        blend_dir: Source directory containing textures
        output_dir: Output directory for texture copies
        standardized_name: Standardized twig name for texture naming
        metadata: Twig metadata dict

    Returns:
        Number of textures copied
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".exr"]
    # CRITICAL: Use base color (diffuse, bark) and normal textures for Nanite compatibility
    # Alpha/translucent/mask textures excluded for Nanite
    # Bump maps are converted to normal maps (not copied as bump)
    # Two-sided textures (top/bottom) are both kept
    # Bark textures are included as separate material
    OPAQUE_TEXTURE_TYPES = [
        "diffuse",
        "diffuse_top",
        "diffuse_bottom",
        "bark",
        "bark_top",
        "bark_bottom",
        "normal",
        "bump",
    ]

    # Search for textures
    search_dirs = [blend_dir / "textures", blend_dir, blend_dir.parent / "textures"]
    available_textures = []

    for search_dir in search_dirs:
        if Path(search_dir).exists():
            for ext in texture_extensions:
                available_textures.extend(Path(search_dir).glob(f"*{ext}"))

    if not available_textures:
        return 0

    # Create textures subdirectory
    textures_dir = output_dir / "textures"
    textures_dir.mkdir(exist_ok=True)

    # Copy base color and normal textures (converting bump to normal)
    copied_count = 0
    bump_converted = False  # Track if we've converted a bump map

    for tex_path in available_textures:
        tex_type = classify_texture_from_name(tex_path.stem)

        # Skip textures not in allowed list (no alpha/translucent/mask)
        if tex_type not in OPAQUE_TEXTURE_TYPES:
            continue

        # Generate standardized name
        tex_ext = tex_path.suffix
        base_name_parts = []
        for part in standardized_name.split("_"):
            base_name_parts.append(part)
            if part == "foliage":
                break

        if not any(p == "foliage" for p in base_name_parts):
            base_name = (
                metadata.get("species", "").lower().replace(" ", "_") + "_foliage"
            )
        else:
            base_name = "_".join(base_name_parts)

        # Convert bump maps to normal maps (don't copy bump itself)
        if tex_type == "bump":
            from growpy.io.usd.texture_utils import bump_to_normal

            # Generate normal map name
            standardized_tex_name = f"{base_name}_normal{tex_ext}"
            dest_tex = textures_dir / standardized_tex_name

            # Convert bump to normal if not already exists and we haven't converted yet
            if not dest_tex.exists() and not bump_converted:
                converted_path = bump_to_normal(tex_path, dest_tex)
                if converted_path:
                    copied_count += 1
                    bump_converted = True
            # Don't copy the original bump file - only the converted normal
        else:
            # Regular copy for diffuse, diffuse_top, diffuse_bottom, and normal
            # CRITICAL: Use power-of-2 resizing for Unreal virtual texture support
            standardized_tex_name = f"{base_name}_{tex_type}{tex_ext}"
            dest_tex = textures_dir / standardized_tex_name

            if not dest_tex.exists():
                from .texture_utils import copy_and_resize_texture

                if copy_and_resize_texture(tex_path, dest_tex):
                    copied_count += 1
                else:
                    # Fallback to regular copy
                    shutil.copy2(tex_path, dest_tex)
                    copied_count += 1

    return copied_count


# -----------------------------------------------------------------------------
# USD material setup
# -----------------------------------------------------------------------------


def _add_twig_material(
    stage,
    mesh_prim,
    mesh_path,
    texture_dir=None,
    species_name=None,
    standardized_name=None,
    mesh_object_name=None,
):
    """Add material with opaque-only textures to twig mesh.

    CRITICAL: Filters out alpha/translucent/mask textures for Nanite compatibility.
    Nanite assemblies do not work well with transparency or opacity masks.
    Only base color (diffuse) textures are used.

    Supports separate bark and leaf materials - will prefer bark textures if mesh
    object name suggests it's a bark mesh (contains "bark" keyword).

    Args:
        stage: USD stage
        mesh_prim: UsdGeom.Mesh prim
        mesh_path: Path to mesh prim
        texture_dir: Optional path to textures directory
        species_name: Optional species name for material naming
        standardized_name: Standardized twig name for texture reference generation
        mesh_object_name: Optional mesh object name from Blender (used to detect material type)
    """
    try:
        # Define leaf green color as fallback
        LEAF_GREEN = Gf.Vec3f(0.3, 0.6, 0.2)

        # Create materials path under the mesh's parent (SkelRoot)
        root_path = mesh_path.GetParentPath()
        materials_path = str(root_path.AppendChild("Materials"))
        UsdGeom.Scope.Define(stage, materials_path)

        # Determine material name
        mat_name = species_name if species_name else "LeafMaterial"
        mat_name = mat_name.replace(" ", "_").replace("-", "_")

        # Create leaf material
        mat = UsdShade.Material.Define(stage, f"{materials_path}/{mat_name}")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/{mat_name}/Principled_BSDF"
        )
        shader.CreateIdAttr("UsdPreviewSurface")

        # Find and add opaque-only textures if texture_dir provided
        textures_found = False
        if texture_dir and texture_dir.exists():
            texture_extensions = [".png", ".jpg", ".jpeg", ".exr"]

            # CRITICAL: Use base color (diffuse, bark) and normal textures for Nanite compatibility
            # Alpha/translucent/mask textures excluded for Nanite
            # Also check for two-sided textures (top/bottom) and bark textures
            OPAQUE_TEXTURE_TYPES = ["diffuse", "diffuse_top", "bark", "normal"]

            # Build standardized texture name base
            # Extract base name (everything up to and including 'foliage')
            base_name_parts = []
            if standardized_name:
                for part in standardized_name.split("_"):
                    base_name_parts.append(part)
                    if part == "foliage":
                        break

            if not any(p == "foliage" for p in base_name_parts):
                # Fallback to species_foliage
                base_name = (
                    species_name.lower().replace(" ", "_") + "_foliage"
                    if species_name
                    else "foliage"
                )
            else:
                base_name = "_".join(base_name_parts)

            # Detect if this is a bark mesh (for separate bark/leaf materials)
            is_bark_mesh = mesh_object_name and "bark" in mesh_object_name.lower()

            # Look for standardized texture files
            texture_map = {}
            for tex_type in OPAQUE_TEXTURE_TYPES:
                for ext in texture_extensions:
                    # Try standardized name first
                    standardized_tex_name = f"{base_name}_{tex_type}{ext}"
                    tex_file = texture_dir / standardized_tex_name
                    if tex_file.exists():
                        texture_map[tex_type] = tex_file
                        break

                # Fallback: search for any matching texture if standardized not found
                if tex_type not in texture_map:
                    for ext in texture_extensions:
                        for tex_file in texture_dir.glob(f"*{tex_type}*{ext}"):
                            texture_map[tex_type] = tex_file
                            break
                        if tex_type in texture_map:
                            break

            # If this is a bark mesh, prefer bark textures and ignore diffuse
            if is_bark_mesh:
                # Move bark textures to diffuse slot for rendering
                if "bark" in texture_map and "diffuse" not in texture_map:
                    texture_map["diffuse"] = texture_map.pop("bark")
                elif "bark_top" in texture_map and "diffuse" not in texture_map:
                    texture_map["diffuse"] = texture_map.pop("bark_top")
                    texture_map.pop("bark_bottom", None)
                elif "bark_bottom" in texture_map and "diffuse" not in texture_map:
                    texture_map["diffuse"] = texture_map.pop("bark_bottom")
                # Remove non-bark diffuse textures for bark meshes
                texture_map.pop("diffuse_bottom", None)
                texture_map.pop("diffuse_top", None)
            else:
                # Regular leaf mesh: prefer diffuse, ignore bark
                texture_map.pop("bark", None)
                texture_map.pop("bark_top", None)
                texture_map.pop("bark_bottom", None)

                # Handle two-sided textures: prefer top over bottom
                # Note: USD doesn't support per-face textures for double-sided materials
                # (see https://docs.blender.org/manual/en/latest/files/import_export/usd.html)
                # Solution: Use top texture only, enable two-sided rendering (backface culling disabled)
                # Bottom texture is copied to output but NOT referenced in USD file
                if "diffuse_top" in texture_map:
                    texture_map["diffuse"] = texture_map["diffuse_top"]
                    # Remove bottom from map so it's not added to USD file
                    texture_map.pop("diffuse_bottom", None)
                elif "diffuse_bottom" in texture_map and "diffuse" not in texture_map:
                    # Use bottom only if no top texture exists
                    texture_map["diffuse"] = texture_map["diffuse_bottom"]

            # Add textures to shader
            # CRITICAL: Create UV reader for texture mapping
            # This connects the mesh UVs (primvars:st) to texture samplers
            uv_reader = None
            if texture_map:  # Only create if we have textures
                uv_reader = UsdShade.Shader.Define(
                    stage, f"{materials_path}/{mat_name}/uvmap"
                )
                uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
                uv_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
                uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

            if "diffuse" in texture_map:
                tex_node = UsdShade.Shader.Define(
                    stage, f"{materials_path}/{mat_name}/DiffuseTexture"
                )
                tex_node.CreateIdAttr("UsdUVTexture")
                # Use standardized texture name
                tex_node.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    f"./textures/{texture_map['diffuse'].name}"
                )
                tex_node.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(
                    "sRGB"
                )

                # Connect UV reader to texture sampler
                if uv_reader:
                    tex_node.CreateInput(
                        "st", Sdf.ValueTypeNames.Float2
                    ).ConnectToSource(uv_reader.ConnectableAPI(), "result")

                # Connect diffuse to base color
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(tex_node.ConnectableAPI(), "rgb")
                textures_found = True
            else:
                # Fallback to solid color
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                    LEAF_GREEN
                )

            # Add normal map if available
            if "normal" in texture_map:
                normal_tex_node = UsdShade.Shader.Define(
                    stage, f"{materials_path}/{mat_name}/NormalTexture"
                )
                normal_tex_node.CreateIdAttr("UsdUVTexture")
                normal_tex_node.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    f"./textures/{texture_map['normal'].name}"
                )
                # Normal maps use raw color space (not sRGB)
                normal_tex_node.CreateInput(
                    "sourceColorSpace", Sdf.ValueTypeNames.Token
                ).Set("raw")

                # Connect UV reader to normal texture sampler
                if uv_reader:
                    normal_tex_node.CreateInput(
                        "st", Sdf.ValueTypeNames.Float2
                    ).ConnectToSource(uv_reader.ConnectableAPI(), "result")

                # Connect normal to shader
                shader.CreateInput(
                    "normal", Sdf.ValueTypeNames.Normal3f
                ).ConnectToSource(normal_tex_node.ConnectableAPI(), "rgb")
                textures_found = True

            # Roughness and metallic textures removed - only using base color and normal
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

        if not textures_found:
            # No textures found - use simple color
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                LEAF_GREEN
            )
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

        # Add specular and opacity for proper Unreal rendering
        shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.5)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)

        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

        # Bind material to mesh
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim.GetPrim())
        binding_api.Bind(mat)
    except Exception:
        # Silently fail - material addition is optional
        pass


# -----------------------------------------------------------------------------
# Blender material setup
# -----------------------------------------------------------------------------


def _build_twig_texture_map(textures):
    """Classify a material's textures into a {tex_type: Path} map for Nanite export.

    Excludes alpha/translucent/mask textures, converts a bump map to a normal map
    when no normal exists, and collapses one-sided diffuse_top/diffuse_bottom into
    a single ``diffuse`` entry.
    """
    excluded_types = {"alpha", "translucent", "mask", "opacity"}
    texture_map = {}
    for tex in textures:
        tex_type = classify_texture_from_name(tex.stem)
        if tex_type in excluded_types:
            continue
        if tex_type not in texture_map:
            texture_map[tex_type] = tex

    # Convert bump maps to normal maps if needed
    if "bump" in texture_map and "normal" not in texture_map:
        from growpy.io.usd.texture_utils import bump_to_normal

        bump_path = texture_map["bump"]
        normal_path = bump_path.parent / f"{bump_path.stem}_normal{bump_path.suffix}"
        if not normal_path.exists():
            if bump_to_normal(bump_path, normal_path):
                texture_map["normal"] = normal_path
        else:
            texture_map["normal"] = normal_path
        del texture_map["bump"]

    # Collapse one-sided diffuse_top/diffuse_bottom into a single diffuse
    has_two_sided = "diffuse_top" in texture_map and "diffuse_bottom" in texture_map
    if not has_two_sided:
        if "diffuse_top" in texture_map:
            texture_map["diffuse"] = texture_map.pop("diffuse_top")
        elif "diffuse_bottom" in texture_map:
            texture_map["diffuse"] = texture_map.pop("diffuse_bottom")

    return texture_map


def _group_twig_textures(
    available_textures,
    species_name,
    had_multiple_materials,
    original_bark_indices,
):
    """Group twig textures into bark/leaf materials by filename affinity and season.

    Routes bark-affinity vs leaf-affinity textures to separate materials and
    consolidates seasonal variants (summer preferred, else fall/winter/spring).
    Ensures a bark material exists when the mesh has bark faces, and falls back
    to a single species material when no grouping applies.

    Returns a dict of material_name -> list[Path].
    """
    bark_keywords = ["twig", "bark", "wood", "branch", "stem"]
    bark_tex_keywords = ["bark", "twig", "branch", "wood", "stem"]
    material_groups = {}

    for texture in available_textures:
        tex_lower = texture.stem.lower()
        material_part = (
            "bark" if any(kw in tex_lower for kw in bark_tex_keywords) else "leaf"
        )

        season = None
        if "summer" in tex_lower:
            season = "summer"
        elif "fall" in tex_lower or "autumn" in tex_lower:
            season = "fall"
        elif "winter" in tex_lower or "bare" in tex_lower:
            season = "winter"
        elif "spring" in tex_lower:
            season = "spring"

        mat_group_key = f"{material_part}_{season}" if season else material_part
        material_groups.setdefault(mat_group_key, []).append(texture)

    # Consolidate season variants: if summer exists, prefer it
    season_prioritization = {"leaf": [], "bark": []}
    for group_key in list(material_groups.keys()):
        if "summer" in group_key:
            material_type = group_key.replace("_summer", "")
            season_prioritization[material_type] = material_groups.pop(group_key)
        elif "fall" in group_key or "winter" in group_key or "spring" in group_key:
            material_type = group_key.split("_")[0]
            if f"{material_type}_summer" not in material_groups:
                if not season_prioritization[material_type]:
                    season_prioritization[material_type] = material_groups.pop(
                        group_key
                    )
                else:
                    material_groups.pop(group_key)
            else:
                material_groups.pop(group_key)
        elif material_groups[group_key]:
            material_type = group_key.split("_")[0]
            if not season_prioritization[material_type]:
                season_prioritization[material_type] = material_groups.pop(group_key)

    # Build final material groups with species prefix
    final_material_groups = {}
    for material_type, textures in season_prioritization.items():
        if textures:
            mat_name = (
                f"{species_name}_{material_type}" if material_type else species_name
            )
            final_material_groups[mat_name] = textures

    material_groups = (
        final_material_groups if final_material_groups else material_groups
    )

    # Ensure bark material exists when mesh has bark faces (from joined objects).
    if had_multiple_materials and original_bark_indices:
        has_bark_group = any(
            any(kw in name.lower() for kw in bark_keywords) for name in material_groups
        )
        if not has_bark_group:
            material_groups[f"{species_name}_bark"] = []

    if not material_groups:
        material_groups[species_name] = available_textures

    return material_groups


def setup_materials_with_textures(
    obj, blend_dir, species_name, output_dir, standardized_name, metadata=None
):
    """Setup Blender materials with all available textures.

    Returns:
        dict: Texture map of texture_type -> Path, or None if no textures
    """
    if metadata is None:
        metadata = {"species": species_name}
    import bpy

    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]

    # Find textures
    search_dirs = [blend_dir / "textures", blend_dir, blend_dir.parent / "textures"]
    available_textures = []

    for search_dir in search_dirs:
        if not Path(search_dir).exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(Path(search_dir).glob(f"*{ext}"))

    # Remove placeholders
    available_textures = [
        t
        for t in available_textures
        if not (t.stem.startswith("color_") and t.suffix == ".hdr")
    ]

    if not available_textures:
        return False

    # Save original material info for face-material index remapping
    bark_keywords = ["twig", "bark", "wood", "branch", "stem"]
    original_bark_indices = set()
    if obj.data.materials:
        for i, mat in enumerate(obj.data.materials):
            if mat and any(kw in mat.name.lower() for kw in bark_keywords):
                original_bark_indices.add(i)
    saved_face_indices = [poly.material_index for poly in obj.data.polygons]
    had_multiple_materials = len(obj.data.materials) > 1

    # Clear existing materials
    obj.data.materials.clear()

    # Group textures into bark/leaf materials (seasonal variants consolidated).
    material_groups = _group_twig_textures(
        available_textures,
        species_name,
        had_multiple_materials,
        original_bark_indices,
    )

    # Create materials
    materials_created = 0

    for mat_name, textures in material_groups.items():
        # Clean material name - remove any numeric suffixes (.001, .002, etc.)
        clean_mat_name = mat_name.split(".")[0]

        # Avoid duplication if clean_mat_name already contains species_name
        species_lower = species_name.lower().replace(" ", "_")
        clean_lower = clean_mat_name.lower().replace(" ", "_")

        if species_lower in clean_lower:
            # Material name already has species name, use as-is
            final_mat_name = clean_mat_name
        else:
            # Add species prefix
            final_mat_name = f"{species_name}_{clean_mat_name}"

        # Check if material already exists and remove it to avoid .001 suffixes
        existing_mat = bpy.data.materials.get(final_mat_name)
        if existing_mat:
            bpy.data.materials.remove(existing_mat)

        material = bpy.data.materials.new(name=final_mat_name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        nodes.clear()

        # Create base nodes
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (400, 0)

        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        # Build the {tex_type: Path} map for this material (Nanite-safe).
        texture_map = _build_twig_texture_map(textures)

        y_offset = 300

        # Create textures subdirectory
        textures_dir = output_dir / "textures"
        textures_dir.mkdir(exist_ok=True)

        for tex_type, tex_path in texture_map.items():
            try:
                # CRITICAL: Copy texture with standardized naming to textures/ subfolder
                # Bark materials use {species}_twig_{type} naming;
                # leaf materials use {species}_foliage_{type} naming.
                tex_ext = tex_path.suffix
                species_base = (
                    metadata["species"].lower().replace(" ", "_")
                    if metadata
                    else species_name.lower().replace(" ", "_")
                )

                # Choose base name depending on material type
                is_bark_material = any(
                    kw in final_mat_name.lower()
                    for kw in ["bark", "twig", "wood", "branch", "stem"]
                )
                if is_bark_material:
                    base_name = f"{species_base}_twig"
                else:
                    # Extract foliage base from standardized_name
                    base_name_parts = []
                    found_foliage = False
                    for part in standardized_name.split("_"):
                        base_name_parts.append(part)
                        if part == "foliage":
                            found_foliage = True
                            break
                    if found_foliage:
                        base_name = "_".join(base_name_parts)
                    else:
                        base_name = f"{species_base}_foliage"

                standardized_tex_name = f"{base_name}_{tex_type}{tex_ext}"
                dest_tex = textures_dir / standardized_tex_name
                if not dest_tex.exists():
                    # CRITICAL: Use power-of-2 resizing for Unreal virtual texture support
                    from .texture_utils import copy_and_resize_texture

                    if not copy_and_resize_texture(tex_path, dest_tex):
                        # Fallback to regular copy
                        shutil.copy2(tex_path, dest_tex)

                # Load texture from textures subdirectory (enables relative path export)
                # USD will reference textures with ./textures/ prefix
                tex_node = nodes.new("ShaderNodeTexImage")
                tex_node.image = bpy.data.images.load(str(dest_tex.resolve()))
                # Make path relative with textures/ prefix
                tex_node.image.filepath = f"//textures/{dest_tex.name}"
                tex_node.location = (-400, y_offset)
                # Use semantic naming for shader nodes (e.g., DiffuseTexture, AlphaTexture)
                tex_node.name = f"{tex_type.replace('_', '').title()}Texture"
                tex_node.label = tex_type.title()

                # Connect based on type
                if tex_type == "diffuse":
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                elif tex_type == "diffuse_top":
                    # Two-sided material: use top texture with geometry node for face orientation
                    # For now, just use top as main texture
                    # USD/Unreal will handle two-sided rendering
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                elif tex_type == "diffuse_bottom":
                    # Only used if top texture connected via MixRGB later
                    # For now, skip - top texture takes precedence
                    pass

                elif tex_type == "bark":
                    # Bark textures treated same as diffuse (separate material)
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                elif tex_type == "bark_top":
                    # Bark texture with top/bottom variants
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                elif tex_type == "bark_bottom":
                    # Bark bottom variant - skip if top exists
                    pass

                elif tex_type == "alpha":
                    # Alpha masks: use Non-Color for proper grayscale interpretation
                    tex_node.image.colorspace_settings.name = "Non-Color"

                    # Check if alpha needs inversion by examining filename
                    # Some alpha masks use white=transparent, others use black=transparent
                    needs_invert = any(
                        keyword in tex_path.stem.lower()
                        for keyword in ["mask", "cutout"]
                    )

                    if needs_invert:
                        # Invert the alpha (white becomes transparent)
                        invert_node = nodes.new("ShaderNodeInvert")
                        invert_node.location = (-200, y_offset)
                        links.new(
                            tex_node.outputs["Color"], invert_node.inputs["Color"]
                        )
                        links.new(invert_node.outputs["Color"], bsdf.inputs["Alpha"])
                    else:
                        # Direct connection (white=opaque, black=transparent)
                        links.new(tex_node.outputs["Color"], bsdf.inputs["Alpha"])

                    # Use CLIP mode for clean alpha cutout (works well in USD)
                    # This prevents the "layer" effect you're seeing
                    material.blend_method = "CLIP"
                    material.alpha_threshold = 0.5  # Hard cutoff for clean edges
                    material.show_transparent_back = True
                    if hasattr(material, "shadow_method"):
                        material.shadow_method = "CLIP"
                    material.use_backface_culling = False

                elif tex_type == "normal":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    normal_map = nodes.new("ShaderNodeNormalMap")
                    normal_map.location = (-200, y_offset - 100)
                    links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
                    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

                elif tex_type == "bump":
                    # Bump maps should have been converted to normal maps already
                    # But if still present, convert on-the-fly
                    from growpy.io.usd.texture_utils import bump_to_normal

                    normal_path = (
                        textures_dir / f"{tex_path.stem}_normal{tex_path.suffix}"
                    )
                    if not normal_path.exists():
                        bump_to_normal(tex_path, normal_path)

                    if normal_path.exists():
                        # Load and use the converted normal map
                        tex_node.image.colorspace_settings.name = "Non-Color"
                        normal_map = nodes.new("ShaderNodeNormalMap")
                        normal_map.location = (-200, y_offset - 100)
                        links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
                        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

                elif tex_type == "translucent":
                    # Transmission changed to Transmission Weight in newer Blender
                    if "Transmission" in bsdf.inputs:
                        links.new(
                            tex_node.outputs["Color"], bsdf.inputs["Transmission"]
                        )
                        bsdf.inputs["Transmission"].default_value = 0.3
                    elif "Transmission Weight" in bsdf.inputs:
                        links.new(
                            tex_node.outputs["Color"],
                            bsdf.inputs["Transmission Weight"],
                        )
                        bsdf.inputs["Transmission Weight"].default_value = 0.3

                elif tex_type == "roughness":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Roughness"])

                elif tex_type == "metallic":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Metallic"])

                elif tex_type == "ao":
                    # Multiply with base color
                    if "diffuse" in texture_map:
                        mix = nodes.new("ShaderNodeMixRGB")
                        mix.blend_type = "MULTIPLY"
                        mix.location = (-200, y_offset)
                        links.new(tex_node.outputs["Color"], mix.inputs[2])

                y_offset -= 250

            except Exception:
                pass

        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.3
        elif "Specular IOR" in bsdf.inputs:
            bsdf.inputs["Specular IOR"].default_value = 0.5
        if "roughness" not in texture_map:
            bsdf.inputs["Roughness"].default_value = 0.7

        # CRITICAL: Enable two-sided rendering for leaf/twig materials
        # This ensures visibility from both sides
        material.use_backface_culling = False
        material["TwoSided"] = True

        obj.data.materials.append(material)
        materials_created += 1

    # Remap face material indices to preserve bark/leaf assignment
    if had_multiple_materials and materials_created > 1:
        new_bark_idx = None
        new_leaf_idx = None
        for i, mat in enumerate(obj.data.materials):
            if mat and any(kw in mat.name.lower() for kw in bark_keywords):
                new_bark_idx = i
            elif new_leaf_idx is None:
                new_leaf_idx = i
        if new_bark_idx is not None and new_leaf_idx is not None:
            for i, old_idx in enumerate(saved_face_indices):
                if old_idx in original_bark_indices:
                    obj.data.polygons[i].material_index = new_bark_idx
                else:
                    obj.data.polygons[i].material_index = new_leaf_idx

    # Return texture map for geometry processing
    if material_groups and materials_created > 0:
        # Merge all texture groups into single map for first material
        combined_texture_map = {}
        for mat_textures in material_groups.values():
            for tex_path in mat_textures:
                tex_type = classify_texture_from_name(tex_path.stem)
                if tex_type not in combined_texture_map:
                    combined_texture_map[tex_type] = tex_path
        return combined_texture_map

    return None
