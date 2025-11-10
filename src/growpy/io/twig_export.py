#!/usr/bin/env python3
"""
Blender twig processor module - runs inside Blender Python environment.

This module is designed to be executed as a standalone script by Blender's Python
interpreter. It handles all Blender-specific operations for twig conversion,
including mesh processing, material setup, and export to USD formats.

Uses Blender's bundled USD (pxr) module via bpy.utils.expose_bundled_modules()
to add skeletons directly during export - no post-processing needed!

Texture Handling:
    - When both top and bottom diffuse textures exist, top texture is prioritized
    - This is a simplification - proper two-sided foliage would require advanced
      material setups
"""

import json
import shutil
import sys
from pathlib import Path

import bpy

# Import path needs adjustment for standalone script execution
try:
    from ..utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
except ImportError:
    # Standalone mode - do manual initialization
    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    import os

    from pxr import Plug

    env_path = os.environ.get("PXR_PLUGINPATH_NAME")
    if env_path:
        abs_path = os.path.abspath(env_path)
        if os.path.exists(abs_path):
            reg = Plug.Registry()
            if not reg.GetPluginWithName("unreal"):
                reg.RegisterPlugins(abs_path)

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt


def rename_prim_recursive(stage, old_path, new_path):
    """Rename a prim and update all references to it."""
    layer = stage.GetRootLayer()
    Sdf.CopySpec(layer, old_path, layer, new_path)
    stage.RemovePrim(old_path)

    # Update all references to the old path
    for prim in stage.Traverse():
        for rel in prim.GetRelationships():
            targets = rel.GetTargets()
            if targets:
                new_targets = []
                for target in targets:
                    target_str = str(target)
                    if str(old_path) in target_str:
                        new_target_str = target_str.replace(
                            str(old_path), str(new_path)
                        )
                        new_targets.append(Sdf.Path(new_target_str))
                    else:
                        new_targets.append(target)
                if new_targets != list(targets):
                    rel.SetTargets(new_targets)

        for attr in prim.GetAttributes():
            # Update connection paths
            connections = attr.GetConnections()
            if connections:
                new_connections = []
                for conn in connections:
                    conn_str = str(conn)
                    if str(old_path) in conn_str:
                        new_conn_str = conn_str.replace(str(old_path), str(new_path))
                        new_connections.append(Sdf.Path(new_conn_str))
                    else:
                        new_connections.append(conn)
                if new_connections != list(connections):
                    attr.SetConnections(new_connections)


def _add_twig_material(stage, mesh_prim, mesh_path):
    """Add simple green leaf material to twig mesh.

    Args:
        stage: USD stage
        mesh_prim: UsdGeom.Mesh prim
        mesh_path: Path to mesh prim
    """
    try:
        from pxr import Gf, Sdf, UsdShade

        # Define leaf green color
        LEAF_GREEN = Gf.Vec3f(0.3, 0.6, 0.2)

        # Create materials path under Twig root
        materials_path = "/Twig/Materials"
        UsdGeom.Scope.Define(stage, materials_path)

        # Create leaf material
        mat = UsdShade.Material.Define(stage, f"{materials_path}/LeafMaterial")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/LeafMaterial/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(LEAF_GREEN)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

        # Bind material to mesh
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim.GetPrim())
        binding_api.Bind(mat)
    except Exception:
        # Silently fail - material addition is optional
        pass


def add_skeleton_to_usd_file(usd_path, pivot_point=(0, 0, 0), clean_export=True):
    """Add skeleton to USD file and remove Blender export artifacts using Blender's bundled pxr module.

    Removes DomeLight, Blender userProperties metadata (data_name, Copyright), and ensures clean export.

    CRITICAL: Always uses clean_export=True to prevent material/texture issues with Nanite assemblies.
    Nanite assemblies with skeletal meshes have known problems with materials, textures, and masks.

    Args:
        usd_path: Path to USD file
        pivot_point: Root joint position (default: origin)
        clean_export: ALWAYS True - materials/textures cause Nanite import failures

    Returns:
        bool: True if skeleton added successfully
    """
    # Force clean export for Nanite compatibility
    clean_export = True
    try:
        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Remove DomeLight artifact from Blender export (if present)
        dome_light = stage.GetPrimAtPath("/root/env_light")
        if dome_light:
            stage.RemovePrim("/root/env_light")

        # Remove Blender-specific userProperties custom attributes
        for prim in stage.Traverse():
            # Remove userProperties:blender:data_name
            if prim.HasAttribute("userProperties:blender:data_name"):
                prim.RemoveProperty("userProperties:blender:data_name")
            # Remove userProperties:Copyright
            if prim.HasAttribute("userProperties:Copyright"):
                prim.RemoveProperty("userProperties:Copyright")
            # Remove userProperties:TwoSided (also common in Blender exports)
            if prim.HasAttribute("userProperties:TwoSided"):
                prim.RemoveProperty("userProperties:TwoSided")

        # Ensure texture paths use ./textures/ prefix
        for prim in stage.Traverse():
            for attr in prim.GetAttributes():
                if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                    asset_path = attr.Get()
                    if asset_path and isinstance(asset_path, Sdf.AssetPath):
                        path_str = asset_path.path
                        if path_str and not path_str.startswith("./textures/"):
                            # Add ./textures/ prefix if missing
                            filename = (
                                Path(path_str).name
                                if path_str.startswith("./")
                                else path_str
                            )
                            new_path = f"./textures/{filename}"
                            attr.Set(Sdf.AssetPath(new_path))

        # Find mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            return False

        # Verify mesh has vertices
        mesh = UsdGeom.Mesh(mesh_prim)
        points = mesh.GetPointsAttr().Get()
        if not points or len(points) == 0:
            return False

        # Create skeleton root (CamelCase naming)
        root_path = Sdf.Path("/Twig")
        skel_root = UsdSkel.Root.Define(stage, root_path)
        # Explicitly set typeName for validation
        skel_root.GetPrim().SetTypeName("SkelRoot")

        # CRITICAL: Add SkelBindingAPI to SkelRoot for proper Unreal Engine skeletal mesh interpretation
        # Without this, Unreal cannot properly bind the skeleton to the mesh
        if clean_export:
            # Manually add SkelBindingAPI to apiSchemas for clean export
            root_prim = skel_root.GetPrim()
            api_schemas = root_prim.GetMetadata("apiSchemas") or Sdf.TokenListOp()
            if not isinstance(api_schemas, Sdf.TokenListOp):
                api_schemas = Sdf.TokenListOp()
            api_schemas.prependedItems = ["SkelBindingAPI"]
            root_prim.SetMetadata("apiSchemas", api_schemas)
        else:
            # Standard mode: use BindingAPI.Apply
            UsdSkel.BindingAPI.Apply(skel_root.GetPrim())

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # Twigs are referenced into Nanite Assemblies via PointInstancer.
        # Only the assembly root should have NaniteAssemblyRootAPI.

        # Create skeleton with single root joint
        # Use "TwigSkel" naming to match Nanite Assembly requirements
        skel_path = root_path.AppendChild("TwigSkel")
        skel = UsdSkel.Skeleton.Define(stage, skel_path)

        # Create single root joint at pivot point
        joint_tokens = ["twig_root"]
        world_pos = Gf.Vec3d(pivot_point[0], pivot_point[1], pivot_point[2])

        # Bind transform (world space)
        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(world_pos)

        # Rest transform (local space, same as bind since no parent)
        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(world_pos)

        # Set skeleton attributes
        skel.CreateJointsAttr(joint_tokens)
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray([bind_transform]))
        skel.CreateRestTransformsAttr(Vt.Matrix4dArray([rest_transform]))

        # CRITICAL: Add jointIndices topology array for proper Unreal Engine skeleton parsing
        # For a single-bone skeleton, [-1] indicates the root joint has no parent
        # Without this attribute, Unreal cannot properly interpret the skeleton hierarchy
        try:
            # Try using official API first (newer USD versions)
            skel.CreateJointIndicesAttr().Set(Vt.IntArray([-1]))
        except AttributeError:
            # Fallback for older USD versions (like Blender's bundled USD)
            joint_indices_attr = skel.GetPrim().CreateAttribute(
                "jointIndices",
                Sdf.ValueTypeNames.IntArray,
                custom=False,
                variability=Sdf.VariabilityUniform,
            )
            joint_indices_attr.Set(Vt.IntArray([-1]))  # Re-parent mesh under SkelRoot
        # Use "TwigMesh" naming to match Nanite Assembly requirements
        new_mesh_path = root_path.AppendChild("TwigMesh")
        old_mesh_path = mesh_prim.GetPath()

        # Copy mesh to new location
        Sdf.CopySpec(
            stage.GetRootLayer(), old_mesh_path, stage.GetRootLayer(), new_mesh_path
        )

        # Remove old mesh
        stage.RemovePrim(old_mesh_path)

        # Get the new mesh prim
        mesh_prim = stage.GetPrimAtPath(new_mesh_path)
        mesh = UsdGeom.Mesh(mesh_prim)

        # Bind mesh to skeleton
        # For clean export, manually set apiSchemas; otherwise use BindingAPI.Apply
        if clean_export:
            # Manually add SkelBindingAPI to apiSchemas for clean export
            api_schemas = mesh_prim.GetMetadata("apiSchemas") or Sdf.TokenListOp()
            if not isinstance(api_schemas, Sdf.TokenListOp):
                api_schemas = Sdf.TokenListOp()
            api_schemas.prependedItems = ["SkelBindingAPI"]
            mesh_prim.SetMetadata("apiSchemas", api_schemas)

            # Create skeleton relationship without custom qualifier
            skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
            skel_rel.SetTargets([skel_path])
        else:
            # Standard mode with materials: use BindingAPI.Apply
            binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
            binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Set skinning data - all vertices bound to root joint
        num_points = len(points)

        # CRITICAL: Use elementSize=2 for USD skeletal mesh compatibility with Unreal
        # Format as pairs [primary, secondary] per vertex even for rigid binding
        # Each vertex bound to root joint with full weight, plus zero-weight padding
        joint_indices = []
        joint_weights = []
        for _ in range(num_points):
            # Primary influence: root joint (index 0) with full weight
            joint_indices.append(0)
            joint_weights.append(1.0)
            # Secondary influence: padding with zero weight
            joint_indices.append(0)
            joint_weights.append(0.0)

        # Set skinning attributes
        if clean_export:
            # Use PrimvarsAPI directly for clean export
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

            joint_indices_primvar = primvars_api.CreatePrimvar(
                "skel:jointIndices",
                Sdf.ValueTypeNames.IntArray,
                UsdGeom.Tokens.vertex,
            )
            joint_indices_primvar.Set(joint_indices)
            joint_indices_primvar.SetElementSize(
                2
            )  # Rigid binding with padding: 2 values per vertex

            joint_weights_primvar = primvars_api.CreatePrimvar(
                "skel:jointWeights",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.vertex,
            )
            joint_weights_primvar.Set(joint_weights)
            joint_weights_primvar.SetElementSize(
                2
            )  # Rigid binding with padding: 2 values per vertex
        else:
            # Standard mode: use BindingAPI with elementSize=2
            binding_api.CreateJointIndicesPrimvar(False, 2).Set(
                joint_indices
            )  # Rigid binding with padding: 2 values per vertex
            binding_api.CreateJointWeightsPrimvar(False, 2).Set(
                joint_weights
            )  # Rigid binding with padding: 2 values per vertex

        # CRITICAL: Never copy materials for Nanite assemblies
        # Materials, textures, and masks cause import failures with skeletal Nanite assemblies
        # All visual appearance should be configured in Unreal Engine after import
        if False:  # Disabled - clean_export always True for Nanite compatibility
            from pxr import UsdShade

            materials_prim = stage.GetPrimAtPath("/root/_materials")
            if materials_prim and materials_prim.IsValid():
                new_materials_path = root_path.AppendChild("Materials")
                materials_scope = stage.DefinePrim(new_materials_path, "Scope")

                # Copy all material definitions
                for child in materials_prim.GetChildren():
                    # Clean material name (remove numeric suffixes)
                    mat_name = child.GetName()
                    clean_mat_name = (
                        mat_name.split(".")[0] if "." in mat_name else mat_name
                    )

                    new_mat_path = new_materials_path.AppendChild(clean_mat_name)
                    # Use CopySpec to copy entire material hierarchy
                    Sdf.CopySpec(
                        stage.GetRootLayer(),
                        child.GetPath(),
                        stage.GetRootLayer(),
                        new_mat_path,
                    )

                    # Rename shaders with semantic names
                    mat_prim = stage.GetPrimAtPath(new_mat_path)
                    if mat_prim:
                        shader_renames = {}
                        for shader_prim in list(mat_prim.GetChildren()):
                            shader_name = shader_prim.GetName()
                            new_shader_name = None

                            # Check shader connections to determine type
                            shader = UsdShade.Shader(shader_prim)
                            file_input = shader.GetInput("file")
                            if file_input:
                                file_path = str(file_input.Get())
                                if "alpha" in file_path:
                                    new_shader_name = "AlphaTexture"
                                elif "normal" in file_path:
                                    new_shader_name = "NormalTexture"
                                elif "translucent" in file_path:
                                    new_shader_name = "TranslucentTexture"
                                elif "diffuse" in file_path:
                                    new_shader_name = "DiffuseTexture"

                            # Fallback naming based on shader name patterns
                            if not new_shader_name:
                                if (
                                    "Image_Texture_001" in shader_name
                                    or shader_name == "Image_Texture_001"
                                ):
                                    new_shader_name = "DiffuseTexture"
                                elif "Image_Texture_003" in shader_name:
                                    new_shader_name = "NormalTexture"
                                elif shader_name == "Image_Texture":
                                    new_shader_name = "AlphaTexture"

                            if new_shader_name and shader_name != new_shader_name:
                                old_shader_path = shader_prim.GetPath()
                                new_shader_path = mat_prim.GetPath().AppendChild(
                                    new_shader_name
                                )
                                shader_renames[old_shader_path] = new_shader_path
                                rename_prim_recursive(
                                    stage, old_shader_path, new_shader_path
                                )

                    # Update material binding paths in shader network
                    def update_material_paths(prim_path):
                        prim = stage.GetPrimAtPath(prim_path)
                        if not prim:
                            return
                        # Update all relationships that reference old material paths
                        for rel in prim.GetRelationships():
                            targets = rel.GetTargets()
                            if targets:
                                new_targets = []
                                for target in targets:
                                    target_str = str(target)
                                    if "/root/_materials/" in target_str:
                                        new_target_str = target_str.replace(
                                            "/root/_materials/",
                                            str(new_materials_path) + "/",
                                        )
                                        new_targets.append(Sdf.Path(new_target_str))
                                    else:
                                        new_targets.append(target)
                                rel.SetTargets(new_targets)
                        # Recursively update children
                        for child_prim in prim.GetChildren():
                            update_material_paths(child_prim.GetPath())

                    update_material_paths(new_mat_path)

                # Update mesh material binding to point to new location
                mat_binding_api = UsdShade.MaterialBindingAPI(mesh_prim)
                mat_binding = mat_binding_api.GetDirectBinding()
                if mat_binding:
                    mat_path = mat_binding.GetMaterialPath()
                    if mat_path and "/root/_materials/" in str(mat_path):
                        new_mat_path_str = str(mat_path).replace(
                            "/root/_materials/", str(new_materials_path) + "/"
                        )
                        # Also update for cleaned material name
                        path_parts = new_mat_path_str.split("/")
                        if path_parts:
                            mat_name = path_parts[-1].split(".")[0]
                            path_parts[-1] = mat_name
                            new_mat_path_str = "/".join(path_parts)

                        new_mat_path = Sdf.Path(new_mat_path_str)
                        mat_prim = stage.GetPrimAtPath(new_mat_path)
                        if mat_prim and mat_prim.IsValid():
                            UsdShade.MaterialBindingAPI.Apply(mesh_prim).Bind(
                                UsdShade.Material(mat_prim)
                            )

        # CRITICAL: Remove the old /root prim that Blender created
        # We've already copied everything we need (/TwigMesh and /_materials) to /Twig
        # Leaving /root in the file confuses Unreal - it should only see /Twig (SkelRoot)
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())

        # Set Twig as default prim so it's the primary reference target
        twig_prim = stage.GetPrimAtPath("/Twig")
        if twig_prim and twig_prim.IsValid():
            stage.SetDefaultPrim(twig_prim)

        # Add simple base color material (no textures)
        _add_twig_material(stage, mesh, new_mesh_path)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        return False


def standardize_twig_name(original_name, species_name):
    """Convert Grove's CamelCase .blend filenames to snake_case USD output names.

    Args:
        original_name: Original .blend filename (e.g., 'AspenApicalTwig.blend')
        species_name: Clean species name from directory (e.g., 'aspen')

    Returns:
        (standardized_name, metadata) tuple
        e.g., ('aspen_apical', {'type': 'apical', ...})
    """
    name_lower = original_name.lower()

    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",
        "variation": None,
        "season": None,
    }

    # Detect type
    if any(kw in name_lower for kw in ["apical", "end", "long", "terminal", "tip"]):
        metadata["type"] = "apical"
    elif any(kw in name_lower for kw in ["lateral", "side", "short", "laterall"]):
        metadata["type"] = "lateral"
    elif any(kw in name_lower for kw in ["upward", "up"]):
        metadata["type"] = "upward"
    elif any(kw in name_lower for kw in ["dead", "fall", "winter", "bare"]):
        metadata["type"] = "dead"
    elif any(kw in name_lower for kw in ["summer", "spring", "green"]):
        metadata["season"] = "summer"

    # Detect variation
    for letter in ["a", "b", "c", "d", "e"]:
        if any(
            pat in name_lower
            for pat in [
                f"var{letter}",
                f"variation{letter}",
                f"twig{letter}",
                f"{letter}twig",
            ]
        ):
            metadata["variation"] = letter
            break

    # Build name
    parts = [species_name.lower().replace(" ", "_")]

    if metadata["type"] != "generic":
        parts.append(metadata["type"])

    if metadata["variation"]:
        parts.append(f"var_{metadata['variation']}")

    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(metadata["season"])

    return "_".join(parts), metadata


def classify_texture_from_name(name):
    """Classify texture type from filename."""
    name_lower = name.lower()

    # Check modifiers
    if "top" in name_lower or "upper" in name_lower:
        if any(kw in name_lower for kw in ["diffuse", "albedo", "color"]):
            return "diffuse_top"
    if "bottom" in name_lower or "lower" in name_lower:
        if any(kw in name_lower for kw in ["diffuse", "albedo", "color"]):
            return "diffuse_bottom"

    # Standard types
    if any(kw in name_lower for kw in ["alpha", "opacity", "mask"]):
        return "alpha"
    if any(kw in name_lower for kw in ["normal", "norm", "bump"]):
        return "normal"
    if any(kw in name_lower for kw in ["translucent", "transmission", "sss"]):
        return "translucent"
    if any(kw in name_lower for kw in ["roughness", "rough"]):
        return "roughness"
    if any(kw in name_lower for kw in ["metallic", "metal"]):
        return "metallic"
    if "ao" in name_lower or "ambient" in name_lower:
        return "ao"

    return "diffuse"


def setup_materials_with_textures(
    obj, blend_dir, species_name, output_dir, standardized_name, metadata=None
):
    """Setup materials with all available textures."""
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

    # Clear existing materials
    obj.data.materials.clear()

    # Group existing materials by base name
    material_groups = {}
    existing_materials = list(bpy.data.materials)

    for texture in available_textures:
        # Find best material match
        mat_name = None
        for mat in existing_materials:
            if (
                mat.name.lower() in texture.stem.lower()
                or texture.stem.lower() in mat.name.lower()
            ):
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

        # Classify and add textures
        texture_map = {}
        for tex in textures:
            tex_type = classify_texture_from_name(tex.stem)
            if tex_type not in texture_map:
                texture_map[tex_type] = tex

        # If both diffuse_top and diffuse_bottom exist, prioritize top
        if "diffuse_top" in texture_map and "diffuse_bottom" in texture_map:
            # Use only top texture
            texture_map["diffuse"] = texture_map["diffuse_top"]
            del texture_map["diffuse_bottom"]
        elif "diffuse_top" in texture_map:
            # Rename diffuse_top to diffuse for standard connection
            texture_map["diffuse"] = texture_map["diffuse_top"]
            del texture_map["diffuse_top"]
        elif "diffuse_bottom" in texture_map:
            # Use bottom if that's all we have
            texture_map["diffuse"] = texture_map["diffuse_bottom"]
            del texture_map["diffuse_bottom"]

        # Debug: Show texture file names
        for tex_type, tex_path in texture_map.items():
            pass

        y_offset = 300

        # Create textures subdirectory
        textures_dir = output_dir / "textures"
        textures_dir.mkdir(exist_ok=True)

        for tex_type, tex_path in texture_map.items():
            try:
                # CRITICAL: Copy texture with standardized naming to textures/ subfolder
                # Format: textures/{species_twig}_{texture_type}{ext}
                # Remove variant suffixes (_var_a, _var_b, etc.) from texture names
                tex_ext = tex_path.suffix
                # Extract base species name (everything up to and including 'twig')
                base_name_parts = []
                found_twig = False
                for part in standardized_name.split("_"):
                    base_name_parts.append(part)
                    if part == "twig":
                        found_twig = True
                        break

                # If 'twig' not found, use species name from metadata
                if not found_twig:
                    base_name = metadata["species"].lower().replace(" ", "_") + "_twig"
                else:
                    base_name = "_".join(base_name_parts)

                standardized_tex_name = f"{base_name}_{tex_type}{tex_ext}"
                dest_tex = textures_dir / standardized_tex_name
                if not dest_tex.exists():
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

            except Exception as e:
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

    return materials_created > 0


def process_twig_file(blend_file, output_dir, formats, species_name, clean_export=True):
    """Process a single twig blend file.

    Args:
        blend_file: Path to .blend file
        output_dir: Output directory for exported files
        formats: List of export formats
        species_name: Name of species
        clean_export: If True, creates minimal USD without materials/textures (default for Nanite)
    """
    import bpy

    # Load blend file
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))

    blend_path = Path(blend_file)
    blend_dir = blend_path.parent

    # Find all mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]

    if not mesh_objects:
        return []

    exported_files = []
    texture_manifest = {}

    for obj in mesh_objects:
        try:
            # Clear selection
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            # Standardize object name with _twig after species but before variant/type
            original_name = obj.name
            standardized_name, metadata = standardize_twig_name(
                original_name, species_name
            )

            # Insert _twig after species name but before variant/type
            # Example: western_red_cedar_twig_apical (not western_red_cedar_apical_twig)
            parts = standardized_name.split("_")

            # Find species name end (before type keywords)
            species_parts = []
            for i, part in enumerate(parts):
                if part in ["apical", "lateral", "var", "upward", "dead", "summer"]:
                    # Insert twig before this position
                    species_parts.append("twig")
                    species_parts.extend(parts[i:])
                    break
                species_parts.append(part)
            else:
                # No type found, append twig at end
                species_parts.append("twig")

            standardized_name = "_".join(species_parts)

            # Center at origin
            obj.location = (0, 0, 0)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # Triangulate mesh to avoid tangent space export warnings
            # This ensures all polygons are triangles before export
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.quads_convert_to_tris(
                quad_method="BEAUTY", ngon_method="BEAUTY"
            )
            bpy.ops.object.mode_set(mode="OBJECT")

            # Note: UV coordinate fixes removed - they were breaking alpha channel
            # The texture orientation issue may be in the original texture files
            # or the way they're mapped in the original .blend files

            # Enable two-sided mesh rendering with smooth shading
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            # Recalculate normals to ensure they're consistent
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")

            # Note: use_auto_smooth removed in Blender 4.1+
            if hasattr(obj.data, "use_auto_smooth"):
                obj.data.use_auto_smooth = False
            for poly in obj.data.polygons:
                poly.use_smooth = True

            # Add custom properties for Unreal export
            obj["TwoSided"] = 1
            obj["DoubleSided"] = True
            obj.data["TwoSided"] = 1

            # Create mount point (empty at origin for Unreal PCG attachment)
            mount_point = bpy.data.objects.new(f"{standardized_name}_mount", None)
            mount_point.location = (0, 0, 0)
            mount_point.empty_display_type = "SPHERE"
            mount_point.empty_display_size = 0.01
            bpy.context.collection.objects.link(mount_point)

            # Parent mesh to mount point for proper hierarchy
            obj.parent = mount_point

            # CRITICAL: Material setup disabled for Nanite compatibility
            # Nanite assemblies with skeletal meshes have known issues with materials, textures, and masks
            # All visual appearance should be configured in Unreal Engine after import
            material_setup_success = False  # Disabled - clean export always for Nanite

            # Skip material setup entirely
            # if not clean_export:
            #     material_setup_success = setup_materials_with_textures(
            #         obj, blend_dir, species_name, output_dir, standardized_name, metadata
            #     )

            bpy.ops.object.select_all(action="DESELECT")
            mount_point.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = mount_point

            # Export in requested formats
            for fmt in formats:
                if fmt in ["usd", "usda"]:
                    # Export skeletal mesh variant (using _skeletal to match tree convention)
                    skel_export_path = (
                        output_dir / f"{standardized_name}_skeletal.{fmt}"
                    )

                    # CRITICAL: Force clean export - no materials, textures, or UVs
                    # Nanite assemblies require geometry-only USD files
                    bpy.ops.wm.usd_export(
                        filepath=str(skel_export_path),
                        selected_objects_only=True,
                        export_materials=False,  # Force disabled for Nanite
                        export_textures=False,  # Force disabled for Nanite
                        export_uvmaps=False,  # Force disabled for Nanite
                        export_normals=True,
                        export_mesh_colors=False,  # Force disabled for Nanite
                        use_instancing=False,
                        evaluation_mode="RENDER",
                        generate_preview_surface=False,  # Force disabled for Nanite
                        relative_paths=True,
                        export_hair=False,
                        export_lights=False,
                    )

                    exported_files.append(skel_export_path)

                    # Add skeleton directly using Blender's bundled USD
                    # This also fixes texture paths and removes DomeLight
                    if add_skeleton_to_usd_file(
                        skel_export_path,
                        pivot_point=(0.0, 0.0, 0.0),
                        clean_export=clean_export,
                    ):
                        pass
                    else:
                        pass

            texture_manifest[standardized_name] = {
                "original_name": original_name,
                "metadata": metadata,
                "materials": (
                    [mat.name for mat in obj.data.materials]
                    if obj.data.materials
                    else []
                ),
                "export_formats": formats,
            }

        except Exception as e:
            continue

    # Note: Manifest file removed - not needed in output
    # Twig metadata is preserved in file naming and structure

    # Cleanup: Remove original .blend file, ReadMe.txt, and source textures
    try:
        if blend_file.exists():
            blend_file.unlink()

        readme_file = output_dir / "ReadMe.txt"
        if readme_file.exists():
            readme_file.unlink()

        # Remove original source texture files (now standardized copies exist in textures/)
        # Original files use CamelCase or species-specific naming (e.g., BeechAlpha.jpg)
        # Standardized files use snake_case with full standardized name (e.g., european_beech_twig_alpha.jpg)
        textures_dir = output_dir / "textures"
        if textures_dir.exists():
            for tex_file in textures_dir.glob("*"):
                if not tex_file.is_file():
                    continue

                # Keep only files matching standardized naming pattern
                # Format: {species_name}_twig_{texture_type}.{ext}
                # Remove files with CamelCase or non-standardized names
                filename = tex_file.stem

                # Check if this is a standardized name (contains species + _twig_)
                species_lower = species_name.lower().replace(" ", "_")
                is_standardized = (
                    filename.startswith(species_lower) and "_twig_" in filename.lower()
                )

                if not is_standardized:
                    tex_file.unlink()

        # Remove any old texture files from root directory only (legacy from previous exports)
        for old_tex in output_dir.glob("*.[jpJP][pnPN][gG]"):
            # Remove root-level textures (textures should be in textures/ subfolder)
            old_tex.unlink()

        # Remove .hdr placeholders from root
        for hdr_file in output_dir.glob("*.hdr"):
            if hdr_file.stem.startswith("color_"):
                hdr_file.unlink()
    except Exception as e:
        pass

    return exported_files


if __name__ == "__main__":
    # Direct Python execution - standard argument parsing
    blend_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    formats = sys.argv[3].split(",")
    species_name = sys.argv[4]
    clean_export = "--clean-export" in sys.argv[5:] if len(sys.argv) > 5 else True

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = process_twig_file(
        blend_file, output_dir, formats, species_name, clean_export
    )
