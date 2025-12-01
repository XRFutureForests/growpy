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
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Set

import bmesh
import bpy
import mathutils

try:
    from PIL import Image
except Exception:
    Image = None

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


def _add_twig_material(
    stage,
    mesh_prim,
    mesh_path,
    texture_dir=None,
    species_name=None,
    standardized_name=None,
):
    """Add material with opaque-only textures to twig mesh.

    CRITICAL: Filters out alpha/translucent/mask textures for Nanite compatibility.
    Nanite assemblies do not work well with transparency or opacity masks.
    Only base color (diffuse) textures are used.

    Args:
        stage: USD stage
        mesh_prim: UsdGeom.Mesh prim
        mesh_path: Path to mesh prim
        texture_dir: Optional path to textures directory
        species_name: Optional species name for material naming
        standardized_name: Standardized twig name for texture reference generation
    """
    try:
        from pxr import Gf, Sdf, UsdShade

        # Define leaf green color as fallback
        LEAF_GREEN = Gf.Vec3f(0.3, 0.6, 0.2)

        # Create materials path under Twig root
        materials_path = "/Twig/Materials"
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

            # CRITICAL: Use base color (diffuse) and normal textures for Nanite compatibility
            # Alpha/translucent/mask textures excluded for Nanite
            # Also check for two-sided textures (top/bottom)
            OPAQUE_TEXTURE_TYPES = ["diffuse", "diffuse_top", "normal"]

            # Build standardized texture name base
            # Extract base name (everything up to and including 'twig')
            base_name_parts = []
            if standardized_name:
                for part in standardized_name.split("_"):
                    base_name_parts.append(part)
                    if part == "twig":
                        break

            if not base_name_parts or "twig" not in base_name_parts:
                # Fallback to species_twig
                base_name = (
                    species_name.lower().replace(" ", "_") + "_twig"
                    if species_name
                    else "twig"
                )
            else:
                base_name = "_".join(base_name_parts)

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
    except Exception as e:
        # Silently fail - material addition is optional
        pass


def clean_static_usd_file(usd_path):
    """Clean static USD file by removing Blender export artifacts and ensuring proper structure.

    Removes DomeLight, Blender userProperties metadata, and ensures materials/textures are properly set up.
    Does NOT add skeleton - this is for static meshes only.

    Args:
        usd_path: Path to USD file

    Returns:
        bool: True if cleaning successful
    """
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

        # Create Twig root Xform (non-skeletal)
        root_path = Sdf.Path("/Twig")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Re-parent mesh under /Twig as TwigMesh
        new_mesh_path = root_path.AppendChild("TwigMesh")
        old_mesh_path = mesh_prim.GetPath()

        # Copy mesh to new location
        Sdf.CopySpec(
            stage.GetRootLayer(), old_mesh_path, stage.GetRootLayer(), new_mesh_path
        )

        # Remove old mesh
        stage.RemovePrim(old_mesh_path)

        # CRITICAL: Copy materials from /root/_materials to /Twig/Materials if they exist
        materials_prim = stage.GetPrimAtPath("/root/_materials")
        if materials_prim and materials_prim.IsValid():
            from pxr import UsdShade

            new_materials_path = root_path.AppendChild("Materials")
            materials_scope = stage.DefinePrim(new_materials_path, "Scope")

            # Copy all material definitions
            for child in materials_prim.GetChildren():
                # Clean material name (remove numeric suffixes)
                mat_name = child.GetName()
                clean_mat_name = mat_name.split(".")[0] if "." in mat_name else mat_name

                new_mat_path = new_materials_path.AppendChild(clean_mat_name)
                # Use CopySpec to copy entire material hierarchy
                Sdf.CopySpec(
                    stage.GetRootLayer(),
                    child.GetPath(),
                    stage.GetRootLayer(),
                    new_mat_path,
                )

            # Update mesh material binding to point to new location
            new_mesh_prim = stage.GetPrimAtPath(new_mesh_path)
            mat_binding_api = UsdShade.MaterialBindingAPI(new_mesh_prim)
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
                        UsdShade.MaterialBindingAPI.Apply(new_mesh_prim).Bind(
                            UsdShade.Material(mat_prim)
                        )

        # CRITICAL: Remove the old /root prim that Blender created
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())

        # Set Twig as default prim so it's the primary reference target
        twig_prim = stage.GetPrimAtPath("/Twig")
        if twig_prim and twig_prim.IsValid():
            stage.SetDefaultPrim(twig_prim)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        return False


def add_skeleton_to_usd_file(usd_path, pivot_point=(0, 0, 0), minimal_export=True):
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
        if minimal_export:
            # Manually add SkelBindingAPI to apiSchemas for minimal export
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
        # Rotate bone to point along +X axis (twig direction) instead of default +Y
        # Rotation: -90 degrees around Z axis transforms Y-forward to X-forward
        bind_transform = Gf.Matrix4d(1.0)
        rotation = Gf.Rotation(Gf.Vec3d(0, 0, 1), -90.0)  # Z-axis, -90 degrees
        bind_transform.SetRotateOnly(rotation)
        bind_transform.SetTranslateOnly(world_pos)

        # Rest transform (local space, same as bind since no parent)
        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetRotateOnly(rotation)
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
        # For minimal export, manually set apiSchemas; otherwise use BindingAPI.Apply
        if minimal_export:
            # Manually add SkelBindingAPI to apiSchemas for minimal export
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

        # CRITICAL: Use elementSize=2 dual-bone format for consistency
        # Twigs use rigid binding: root joint (index 0) with full weight, dummy second bone
        joint_indices = []
        joint_weights = []
        for _ in range(num_points):
            # Rigid binding in dual-bone format: [joint0, weight0, joint1, weight1]
            joint_indices.extend([0, 0])  # Root joint and dummy second joint
            joint_weights.extend([1.0, 0.0])  # Full weight on root, zero on dummy

        # Set skinning attributes
        if minimal_export:
            # Use PrimvarsAPI directly for minimal export
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

            joint_indices_primvar = primvars_api.CreatePrimvar(
                "skel:jointIndices",
                Sdf.ValueTypeNames.IntArray,
                UsdGeom.Tokens.vertex,
            )
            joint_indices_primvar.Set(joint_indices)
            joint_indices_primvar.SetElementSize(2)  # Dual-bone format for consistency

            joint_weights_primvar = primvars_api.CreatePrimvar(
                "skel:jointWeights",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.vertex,
            )
            joint_weights_primvar.Set(joint_weights)
            joint_weights_primvar.SetElementSize(2)  # Dual-bone format for consistency
        else:
            # Standard mode: use BindingAPI with elementSize=2
            binding_api.CreateJointIndicesPrimvar(False, 2).Set(
                joint_indices
            )  # Dual-bone format for consistency
            binding_api.CreateJointWeightsPrimvar(False, 2).Set(
                joint_weights
            )  # Dual-bone format for consistency

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

    # Detect variation - require explicit variation markers to avoid false positives
    # e.g., "VariationA", "VarB", "TwigA" but NOT "ScotsPineTwig" matching "etwig"
    for letter in ["a", "b", "c", "d", "e"]:
        if any(
            pat in name_lower
            for pat in [
                f"var{letter}",  # VarA, VarB, etc.
                f"variation{letter}",  # VariationA, VariationB, etc.
            ]
        ):
            metadata["variation"] = letter
            break
        # Also check for single letter suffix like "TwigA", "TwigB" but require preceding 'twig'
        # This avoids matching "ScotsPineTwig" as variation E (from "etwig")
        if f"twig{letter}" in name_lower and name_lower.index(
            f"twig{letter}"
        ) == name_lower.rindex("twig"):
            # Only match if this is the LAST occurrence and letter is after twig
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

    # Check for specific texture types first (alpha, normal, bump, etc.)
    # These take precedence over top/bottom classification
    if any(kw in name_lower for kw in ["alpha", "opacity", "mask"]):
        return "alpha"
    # Distinguish between normal maps (RGB) and bump maps (grayscale height)
    if any(kw in name_lower for kw in ["normal", "norm", "nrm"]):
        return "normal"
    if any(kw in name_lower for kw in ["bump", "height", "displacement"]):
        return "bump"

    # Check for top/bottom diffuse textures
    # These can have explicit "diffuse" keyword OR be implicit (e.g., "OakTop.png")
    has_top = "top" in name_lower or "upper" in name_lower or "face" in name_lower
    has_bottom = "bottom" in name_lower or "lower" in name_lower or "back" in name_lower
    has_diffuse_keyword = any(kw in name_lower for kw in ["diffuse", "albedo", "color"])

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
    # CRITICAL: Use base color (diffuse) and normal textures for Nanite compatibility
    # Alpha/translucent/mask textures excluded for Nanite
    # Bump maps are converted to normal maps (not copied as bump)
    # Two-sided textures (top/bottom) are both kept
    OPAQUE_TEXTURE_TYPES = [
        "diffuse",
        "diffuse_top",
        "diffuse_bottom",
        "normal",
        "bump",
    ]

    # Search for textures
    search_dirs = [blend_dir / "textures", blend_dir, blend_dir.parent / "textures"]
    available_textures = []

    for search_dir in search_dirs:
        if not Path(search_dir).exists():
            continue
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
            if part == "twig":
                break

        if not any(p == "twig" for p in base_name_parts):
            base_name = metadata.get("species", "").lower().replace(" ", "_") + "_twig"
        else:
            base_name = "_".join(base_name_parts)

        # Convert bump maps to normal maps (don't copy bump itself)
        if tex_type == "bump":
            from growpy.io.texture_utils import bump_to_normal

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


def _detect_leaf_material_indices(obj):
    """Return a set of material indices that likely correspond to leaves/foliage.

    For twig meshes, if no explicit leaf materials are found, returns ALL material
    indices since twigs are typically entirely foliage geometry that needs processing.
    """
    leaf_kw = ("leaf", "leaves", "foliage", "needle")
    bark_kw = ("bark", "branch", "twig", "wood")
    idxs = set()
    mats = getattr(obj.data, "materials", []) or []

    # First pass: look for explicit leaf materials
    for i, mat in enumerate(mats):
        name = (mat.name if mat else "").lower()
        if any(k in name for k in leaf_kw) and not any(k in name for k in bark_kw):
            idxs.add(i)

    # CRITICAL: For twigs, if no leaf materials found, treat entire mesh as foliage
    # This ensures geometry processing (alpha trim, densify, decimate) runs on all faces
    # Twig meshes are typically 100% leaf/foliage geometry without bark segments
    if not idxs:
        # Return all material indices (or {0} if no materials assigned)
        if mats:
            idxs = set(range(len(mats)))
        else:
            idxs = {0}  # Default to material slot 0 for unmaterialized meshes

    return idxs


def smooth_leaf_mesh(
    obj,
    iterations: int = 10,
    factor: float = 0.2,
    material_indices: Optional[Set[int]] = None,
):
    """Smooth selected (leaf) regions to reduce faceting from low-poly meshes.

    Uses Laplacian smoothing limited to vertices belonging to faces with
    material indices in `material_indices`. If `material_indices` is None,
    applies to the whole mesh.
    """
    import bmesh
    import bpy

    if iterations <= 0 or factor <= 0.0:
        return

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        v.select = False
    if material_indices:
        for f in bm.faces:
            if f.material_index in material_indices:
                for v in f.verts:
                    v.select = True
    else:
        for v in bm.verts:
            v.select = True

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

    try:
        bpy.ops.mesh.select_mode(type="VERT")
    except Exception:
        pass

    try:
        bpy.ops.mesh.smooth_laplacian(
            repeat=int(iterations), lambda_factor=float(factor), preserve_volume=True
        )
    except Exception:
        try:
            bpy.ops.mesh.vertices_smooth(repeat=int(iterations), factor=float(factor))
        except Exception:
            pass

    bpy.ops.object.mode_set(mode="OBJECT")


def _gather_texture_candidates(blend_dir, standardized_name, species, metadata):
    """Find textures for twig geometry processing and export.

    Returns dict with texture types:
        - 'diffuse': Base color texture (may have embedded alpha)
        - 'normal': Normal map texture
        - 'alpha': Dedicated alpha/opacity texture (preferred for geometry trimming)
        - 'translucent': Translucency texture (can be used as alpha fallback)

    For geometry processing (trimming, decimation), alpha sources are prioritized:
        1. Dedicated 'alpha' texture file
        2. Dedicated 'translucent' texture file
        3. Embedded alpha channel in 'diffuse' texture (fallback)
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]
    search_dirs = [blend_dir / "textures", blend_dir, blend_dir.parent / "textures"]
    files = []
    for d in search_dirs:
        if Path(d).exists():
            for ext in texture_extensions:
                files.extend(Path(d).glob(f"*{ext}"))

    # Build base name up to 'twig'
    parts = []
    found_twig = False
    for part in standardized_name.split("_"):
        parts.append(part)
        if part == "twig":
            found_twig = True
            break
    if not found_twig:
        base_name = f"{species.lower().replace(' ', '_')}_twig"
    else:
        base_name = "_".join(parts)

    def pick(kind_words, prefer_top=True):
        def score(p: Path):
            n = p.stem.lower()
            # CRITICAL: Require at least one keyword match to be considered
            # Without this, base_name match alone would pick wrong textures
            # (e.g., diffuse texture picked as alpha just because it has species name)
            if not any(k in n for k in kind_words):
                return -1  # Not a match for this texture type
            s = 3  # Base score for keyword match
            if base_name in n:
                s += 5  # Bonus for matching standardized naming
            if prefer_top and ("top" in n or "upper" in n):
                s += 1
            return s

        best, best_s = None, -1
        for p in files:
            s = score(p)
            if s > best_s:
                best, best_s = p, s
        return best

    out = {}
    # Gather all texture types for geometry processing
    diffuse = pick(["diffuse", "albedo", "color", "basecolor", "base"])
    if diffuse:
        out["diffuse"] = diffuse
    normal = pick(["normal", "norm", "nrm", "bump"], prefer_top=False)
    if normal:
        out["normal"] = normal
    # Include alpha/translucent textures for geometry processing (trimming, decimation)
    alpha = pick(["alpha", "opacity", "mask", "cutout"], prefer_top=False)
    if alpha:
        out["alpha"] = alpha
    translucent = pick(
        ["translucent", "translucency", "transmission"], prefer_top=False
    )
    if translucent:
        out["translucent"] = translucent
    return out


def densify_mesh(obj, subdivision_levels=3, material_indices=None, target_edge_mm=None):
    """Densify mesh using subdivision to create more triangles.

    Args:
        obj: Blender mesh object
        subdivision_levels: Number of subdivision iterations (default: 3, ignored if target_edge_mm set)
        material_indices: Optional set of material indices to restrict densification
        target_edge_mm: Target edge length in millimeters. If set, subdivides adaptively
                       until edges are at or below this length. Provides consistent mesh
                       density across different twig sizes (e.g., conifer vs broadleaf).
                       Example: 2.0 = 2mm edges, suitable for most twigs.
    """
    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Use bmesh for subdivision
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        if target_edge_mm is not None and target_edge_mm > 0:
            # Convert mm to Blender units (1 Blender unit = 1000mm typically)
            # For twig meshes, scale is typically 1:1 so 1 unit = 1m = 1000mm
            target_edge_bu = target_edge_mm / 1000.0

            # Adaptive subdivision based on edge length
            max_iterations = 10  # Safety limit
            for iteration in range(max_iterations):
                # Collect edges that exceed target length
                edges_to_subdivide = []
                for e in bm.edges:
                    if material_indices:
                        # Check if edge belongs to a face with matching material
                        has_material = any(
                            f.material_index in material_indices for f in e.link_faces
                        )
                        if not has_material:
                            continue

                    edge_length = (e.verts[0].co - e.verts[1].co).length
                    if edge_length > target_edge_bu:
                        edges_to_subdivide.append(e)

                if not edges_to_subdivide:
                    break  # All edges are at or below target length

                # Subdivide long edges (1 cut = split in half)
                bmesh.ops.subdivide_edges(
                    bm, edges=edges_to_subdivide, cuts=1, use_grid_fill=True
                )
        else:
            # Original behavior: fixed subdivision levels
            edges = list(bm.edges)
            if material_indices:
                face_edges = set()
                for f in bm.faces:
                    if f.material_index in material_indices:
                        for e in f.edges:
                            face_edges.add(e)
                edges = list(face_edges)

            if edges:
                bmesh.ops.subdivide_edges(
                    bm, edges=edges, cuts=subdivision_levels, use_grid_fill=True
                )

        # Write back to mesh
        bm.to_mesh(obj.data)
        bm.free()

        obj.data.update()
    except Exception as e:
        pass


def apply_normal_displacement(
    obj, normal_texture_path, strength=0.005, material_indices=None
):
    """Displace mesh vertices based on normal map texture.

    Args:
        obj: Blender mesh object
        normal_texture_path: Path to normal map texture
        strength: Displacement strength multiplier (default: 0.01)
    """
    try:
        if Image is None:
            return
        if not normal_texture_path or not Path(normal_texture_path).exists():
            return

        # Load normal map image
        img = Image.open(normal_texture_path)
        img_width, img_height = img.size
        pixels = img.load()

        # Get UV layer
        if not obj.data.uv_layers.active:
            return

        uv_layer = obj.data.uv_layers.active.data
        mesh = obj.data

        # Build vertex UV mapping
        vertex_uvs = {}
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                loop = mesh.loops[loop_idx]
                vert_idx = loop.vertex_index
                uv = uv_layer[loop_idx].uv
                if vert_idx not in vertex_uvs:
                    vertex_uvs[vert_idx] = uv

        # If restricting to leaf faces, collect eligible vertices
        eligible = None
        if material_indices:
            eligible = set()
            for poly in mesh.polygons:
                if poly.material_index in material_indices:
                    for loop_idx in poly.loop_indices:
                        eligible.add(mesh.loops[loop_idx].vertex_index)

        # Displace vertices based on normal map
        for vert_idx, uv in vertex_uvs.items():
            if eligible is not None and vert_idx not in eligible:
                continue
            vert = mesh.vertices[vert_idx]

            # Sample normal map at UV coordinate
            x = int(uv.x * (img_width - 1))
            y = int((1.0 - uv.y) * (img_height - 1))  # Flip Y
            x = max(0, min(img_width - 1, x))
            y = max(0, min(img_height - 1, y))

            # Get pixel color (normal map RGB)
            pixel = pixels[x, y]
            if len(pixel) >= 3:
                # Convert from [0-255] to [-1, 1] range
                nx = (pixel[0] / 255.0) * 2.0 - 1.0
                ny = (pixel[1] / 255.0) * 2.0 - 1.0
                nz = (pixel[2] / 255.0) * 2.0 - 1.0

                # Normalize
                length = (nx * nx + ny * ny + nz * nz) ** 0.5
                if length > 0:
                    nx /= length
                    ny /= length
                    nz /= length

                # Displace along vertex normal weighted by normal map Z component
                displacement = mathutils.Vector(vert.normal) * nz * strength
                vert.co += displacement

        mesh.update()
    except Exception as e:
        pass


def trim_by_alpha_mask(
    obj,
    alpha_texture_path,
    threshold=0.5,
    require_alpha_channel=False,
    material_indices=None,
    allow_luminance_for_masks: bool = False,
):
    """Trim mesh geometry based on alpha/opacity mask texture.

    Uses face centroid UV sampling to determine if a face is in a transparent
    region. This approach works accurately for both low-poly and subdivided
    meshes, unlike vertex-based sampling which fails on dense geometry.

    Args:
        obj: Blender mesh object
        alpha_texture_path: Path to alpha/mask texture
        threshold: Alpha threshold for keeping geometry (0.0-1.0, default: 0.5)
        require_alpha_channel: If True, texture must have embedded alpha channel
        material_indices: Optional set of material indices to restrict trimming
        allow_luminance_for_masks: If True, use luminance for mask-named textures
    """
    try:
        if Image is None:
            return
        if not alpha_texture_path or not Path(alpha_texture_path).exists():
            return

        # Load alpha/translucency image
        img = Image.open(alpha_texture_path)
        bands = img.getbands()
        has_alpha = "A" in bands

        # Determine if we can use luminance as alpha for explicit mask textures
        name_lower = Path(alpha_texture_path).stem.lower()
        looks_like_mask = any(
            k in name_lower
            for k in ["alpha", "opacity", "mask", "transparent", "cutout"]
        )

        if require_alpha_channel and not has_alpha:
            return

        # Choose channel for trimming
        alpha_img = None
        if has_alpha:
            alpha_img = img.getchannel("A")
        elif allow_luminance_for_masks and looks_like_mask:
            # Use luminance for explicit mask textures
            alpha_img = img.convert("L")
        else:
            # No usable alpha information
            return

        img_width, img_height = alpha_img.size
        pixels = alpha_img.load()

        # Heuristic inversion for certain mask naming
        invert_mask = any(k in name_lower for k in ["mask", "cutout"])

        # Get UV layer
        if not obj.data.uv_layers.active:
            return

        mesh = obj.data
        uv_layer = mesh.uv_layers.active.data

        # Use bmesh for efficient face deletion
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Build UV layer reference in bmesh
        uv_layer_bm = bm.loops.layers.uv.active
        if not uv_layer_bm:
            bm.free()
            return

        # Mark faces for deletion based on alpha values
        # Uses face centroid UV sampling for accurate results with subdivided meshes
        faces_to_delete = []
        for face in bm.faces:
            if material_indices and face.material_index not in material_indices:
                continue

            # Calculate face centroid UV by averaging loop UVs
            centroid_u = 0.0
            centroid_v = 0.0
            loop_count = len(face.loops)
            for loop in face.loops:
                uv = loop[uv_layer_bm].uv
                centroid_u += uv.x
                centroid_v += uv.y
            centroid_u /= loop_count
            centroid_v /= loop_count

            # Sample alpha at face centroid (most accurate for dense geometry)
            x = int(centroid_u * (img_width - 1))
            y = int((1.0 - centroid_v) * (img_height - 1))  # Flip Y
            x = max(0, min(img_width - 1, x))
            y = max(0, min(img_height - 1, y))

            centroid_alpha = pixels[x, y] / 255.0
            if invert_mask:
                centroid_alpha = 1.0 - centroid_alpha

            # Delete face if centroid is below threshold (transparent region)
            if centroid_alpha < threshold:
                faces_to_delete.append(face)

        # Delete marked faces
        bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")

        # Write back to mesh
        bm.to_mesh(mesh)
        bm.free()

        mesh.update()
    except Exception:
        pass


def trim_vertices_by_alpha(
    obj,
    alpha_texture_path,
    threshold=0.5,
    require_alpha_channel=False,
    material_indices=None,
    allow_luminance_for_masks: bool = False,
):
    """Trim mesh by deleting vertices with alpha below threshold.

    This is simpler and more direct than face-based deletion. Deleting a vertex
    automatically removes all faces that used that vertex.

    Args:
        obj: Blender mesh object
        alpha_texture_path: Path to alpha/mask texture
        threshold: Alpha threshold - vertices below this are deleted (0.0-1.0, default: 0.5)
        require_alpha_channel: If True, texture must have embedded alpha channel
        material_indices: Optional set of material indices to restrict trimming
        allow_luminance_for_masks: If True, use luminance for mask-named textures
    """
    try:
        if Image is None:
            return
        if not alpha_texture_path or not Path(alpha_texture_path).exists():
            return

        # Load alpha image
        img = Image.open(alpha_texture_path)
        bands = img.getbands()
        has_alpha = "A" in bands

        name_lower = Path(alpha_texture_path).stem.lower()
        looks_like_mask = any(
            k in name_lower
            for k in ["alpha", "opacity", "mask", "transparent", "cutout"]
        )

        if require_alpha_channel and not has_alpha:
            return

        alpha_img = None
        if has_alpha:
            alpha_img = img.getchannel("A")
        elif allow_luminance_for_masks and looks_like_mask:
            alpha_img = img.convert("L")
        else:
            return

        img_width, img_height = alpha_img.size
        pixels = alpha_img.load()

        invert_mask = any(k in name_lower for k in ["mask", "cutout"])

        if not obj.data.uv_layers.active:
            return

        mesh = obj.data
        uv_layer = mesh.uv_layers.active.data

        # Build per-vertex alpha values (average across all UV instances)
        vert_alpha = {}
        vert_counts = {}

        # If material_indices specified, only consider vertices from those faces
        eligible_verts = None
        if material_indices:
            eligible_verts = set()
            for poly in mesh.polygons:
                if poly.material_index in material_indices:
                    for loop_idx in poly.loop_indices:
                        eligible_verts.add(mesh.loops[loop_idx].vertex_index)

        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                vi = mesh.loops[loop_idx].vertex_index

                if eligible_verts is not None and vi not in eligible_verts:
                    continue

                uv = uv_layer[loop_idx].uv
                x = int(uv.x * (img_width - 1))
                y = int((1.0 - uv.y) * (img_height - 1))
                x = max(0, min(img_width - 1, x))
                y = max(0, min(img_height - 1, y))

                alpha = pixels[x, y] / 255.0
                if invert_mask:
                    alpha = 1.0 - alpha

                vert_alpha[vi] = vert_alpha.get(vi, 0.0) + alpha
                vert_counts[vi] = vert_counts.get(vi, 0) + 1

        # Average the alpha values
        for vi in vert_alpha:
            vert_alpha[vi] /= vert_counts[vi]

        # Use bmesh for vertex deletion
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()

        # Collect vertices to delete
        verts_to_delete = []
        for v in bm.verts:
            if v.index in vert_alpha and vert_alpha[v.index] < threshold:
                verts_to_delete.append(v)

        # Delete vertices (automatically removes attached faces)
        bmesh.ops.delete(bm, geom=verts_to_delete, context="VERTS")

        # Clean up: remove loose edges and vertices
        loose_edges = [e for e in bm.edges if not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")

        loose_verts = [v for v in bm.verts if not v.link_edges]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
    except Exception:
        pass


def _load_alpha_image(
    texture_path, require_alpha_channel=False, allow_luminance_for_masks: bool = False
):
    """Load alpha mask PIL image (single-channel) from texture.

    Returns PIL Image in 'L' mode or None if not available/allowed.
    Prefers alpha channel; if require_alpha_channel=True, returns None when no alpha present.
    """
    if Image is None:
        return None
    try:
        if not texture_path or not Path(texture_path).exists():
            return None
        img = Image.open(texture_path)
        bands = img.getbands()
        has_alpha = "A" in bands
        if require_alpha_channel and not has_alpha:
            return None
        if has_alpha:
            return img.getchannel("A")
        # Allow luminance-only mask images when explicitly labeled as masks
        if allow_luminance_for_masks:
            name_lower = Path(texture_path).stem.lower()
            if any(
                k in name_lower
                for k in [
                    "alpha",
                    "opacity",
                    "mask",
                    "transparent",
                    "cutout",
                    "translucent",
                    "translucency",
                ]
            ):
                return img.convert("L")
        return None
    except Exception:
        return None


def _get_alpha_texture_for_geometry(tex_map: dict):
    """Get the best alpha source for geometry processing from texture map.

    Priority order:
        1. Dedicated 'alpha' texture file (use as luminance)
        2. Dedicated 'translucent' texture file (use as luminance)
        3. Embedded alpha channel in 'diffuse' texture (fallback)

    Args:
        tex_map: Dict from _gather_texture_candidates with texture paths

    Returns:
        (texture_path, use_luminance) tuple, or (None, False) if no alpha available
    """
    # Priority 1: Dedicated alpha texture
    if tex_map.get("alpha"):
        return tex_map["alpha"], True  # Use luminance for dedicated alpha files

    # Priority 2: Translucent texture as alpha source
    if tex_map.get("translucent"):
        return tex_map["translucent"], True  # Use luminance for translucent files

    # Priority 3: Embedded alpha in diffuse texture
    if tex_map.get("diffuse"):
        return tex_map["diffuse"], False  # Use embedded alpha channel

    return None, False


def _build_vertex_alpha_map(mesh, alpha_img):
    """Build per-vertex alpha map by sampling the alpha image at UVs.

    Returns: dict vert_index -> alpha [0..1]
    """
    if alpha_img is None or not mesh.uv_layers.active:
        return {}
    pixels = alpha_img.load()
    w, h = alpha_img.size
    uv_layer = mesh.uv_layers.active.data
    vert_alpha = {}
    # Use averaged alpha over all loops touching the vertex
    accum = {}
    counts = {}
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            loop = mesh.loops[loop_idx]
            vi = loop.vertex_index
            uv = uv_layer[loop_idx].uv
            x = int(max(0, min(w - 1, uv.x * (w - 1))))
            y = int(max(0, min(h - 1, (1.0 - uv.y) * (h - 1))))
            a = pixels[x, y] / 255.0
            accum[vi] = accum.get(vi, 0.0) + a
            counts[vi] = counts.get(vi, 0) + 1
    for vi, total in accum.items():
        vert_alpha[vi] = total / max(1, counts.get(vi, 1))
    return vert_alpha


def densify_mesh_edge_adaptive(
    obj,
    material_indices,
    alpha_img,
    threshold,
    base_cuts=4,
    edge_cuts=16,
):
    """Densify leaf mesh with higher density along alpha silhouette edges.

    - boundary edges (cross threshold or near it) subdivided with edge_cuts
    - interior leaf edges subdivided with base_cuts
    """
    try:
        mesh = obj.data
        if not material_indices:
            return
        # Build per-vertex alpha map
        v_alpha = _build_vertex_alpha_map(mesh, alpha_img)
        if not v_alpha:
            return
        # Collect candidate edges from leaf faces
        leaf_edge_keys = set()
        for poly in mesh.polygons:
            if poly.material_index in material_indices:
                # iterate poly edges via loops
                loop_indices = list(poly.loop_indices)
                for i in range(len(loop_indices)):
                    li0 = loop_indices[i]
                    li1 = loop_indices[(i + 1) % len(loop_indices)]
                    v0 = mesh.loops[li0].vertex_index
                    v1 = mesh.loops[li1].vertex_index
                    key = tuple(sorted((v0, v1)))
                    leaf_edge_keys.add(key)

        # Classify edges
        eps = 0.08  # near-threshold band
        boundary_keys = []
        interior_keys = []
        for v0, v1 in leaf_edge_keys:
            a0 = v_alpha.get(v0)
            a1 = v_alpha.get(v1)
            if a0 is None or a1 is None:
                continue
            crosses = (a0 - threshold) * (a1 - threshold) < 0.0
            near = (abs(a0 - threshold) < eps) or (abs(a1 - threshold) < eps)
            if crosses or near:
                boundary_keys.append((v0, v1))
            else:
                interior_keys.append((v0, v1))

        if not boundary_keys and not interior_keys:
            return

        # Build bmesh and mapping from edge key to bm edge
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Map current bm edges by key
        bm_edge_by_key = {}
        for e in bm.edges:
            kv = tuple(sorted((e.verts[0].index, e.verts[1].index)))
            bm_edge_by_key[kv] = e

        boundary_edges = [
            bm_edge_by_key[k] for k in boundary_keys if k in bm_edge_by_key
        ]
        interior_edges = [
            bm_edge_by_key[k] for k in interior_keys if k in bm_edge_by_key
        ]

        # Subdivide boundary first (high cuts), then interior (base cuts)
        if boundary_edges and edge_cuts > 0:
            bmesh.ops.subdivide_edges(
                bm, edges=boundary_edges, cuts=edge_cuts, use_grid_fill=True
            )
        if interior_edges and base_cuts > 0:
            bmesh.ops.subdivide_edges(
                bm, edges=interior_edges, cuts=base_cuts, use_grid_fill=True
            )

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
    except Exception:
        pass


def _smooth_boundary_edges(
    obj,
    leaf_material_indices: Set[int],
    alpha_img,
    threshold: float,
    smooth_iterations: int = 3,
    smooth_factor: float = 0.5,
    boundary_rings: int = 1,
):
    """Apply Laplacian smoothing to mesh boundary vertices after alpha trimming.

    This smooths the actual mesh edges (after face removal) to follow texture contours
    more naturally, reducing jagged appearance from regular subdivision grid.

    CRITICAL: Must be called AFTER alpha trimming, as it smooths the actual trimmed
    mesh boundary, not the pre-trim alpha threshold crossings.

    Args:
        obj: Blender mesh object (after alpha trimming)
        leaf_material_indices: Set of material indices for leaf geometry
        alpha_img: Not used - kept for API compatibility
        threshold: Not used - kept for API compatibility
        smooth_iterations: Number of smoothing passes (default: 3)
        smooth_factor: Smoothing strength per iteration (0.0-1.0, default: 0.5)
        boundary_rings: Width of boundary region to smooth (default: 1)
    """
    if smooth_iterations <= 0 or smooth_factor <= 0.0:
        return

    mesh = obj.data
    if not mesh:
        return

    # Build adjacency and identify boundary edges
    # A boundary edge has at least one adjacent face and is on the mesh perimeter
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Collect leaf faces
    leaf_faces = set()
    for face in bm.faces:
        if face.material_index in leaf_material_indices:
            leaf_faces.add(face)

    if not leaf_faces:
        bm.free()
        return

    # Find boundary vertices - vertices on edges with only one adjacent leaf face
    boundary_verts = set()
    for edge in bm.edges:
        # Count adjacent leaf faces
        adjacent_leaf_faces = sum(1 for f in edge.link_faces if f in leaf_faces)

        # Boundary edge has exactly 1 adjacent leaf face (outer perimeter)
        if adjacent_leaf_faces == 1:
            for vert in edge.verts:
                boundary_verts.add(vert)

    if not boundary_verts:
        bm.free()
        return

    # Expand boundary by boundary_rings
    all_leaf_verts = set()
    for face in leaf_faces:
        for vert in face.verts:
            all_leaf_verts.add(vert)

    current = set(boundary_verts)
    for _ in range(max(0, int(boundary_rings))):
        grow = set()
        for v in current:
            for edge in v.link_edges:
                for nb in edge.verts:
                    if nb in all_leaf_verts and nb not in boundary_verts:
                        grow.add(nb)
        if not grow:
            break
        boundary_verts.update(grow)
        current = grow

    # Apply Laplacian smoothing to boundary vertices
    for iteration in range(smooth_iterations):
        # Calculate new positions
        new_positions = {}
        for vert in boundary_verts:
            # Get connected vertices through edges
            neighbors = []
            for edge in vert.link_edges:
                for nb in edge.verts:
                    if nb != vert and nb in all_leaf_verts:
                        neighbors.append(nb)

            if not neighbors:
                continue

            # Average neighbor positions
            avg_pos = mathutils.Vector((0, 0, 0))
            for nb in neighbors:
                avg_pos += nb.co
            avg_pos /= len(neighbors)

            # Blend between original and averaged position
            new_pos = vert.co.lerp(avg_pos, smooth_factor)
            new_positions[vert] = new_pos

        # Apply new positions
        for vert, new_pos in new_positions.items():
            vert.co = new_pos

    # Write back to mesh
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _measure_interior_edge_length(mesh, leaf_material_indices: Set[int]) -> float:
    """Measure average edge length for interior (leaf) geometry.

    Returns average edge length in Blender units, or 0.0 if no edges found.
    """
    interior_edges = set()
    for poly in mesh.polygons:
        if poly.material_index in leaf_material_indices:
            for edge_key in poly.edge_keys:
                interior_edges.add(edge_key)

    if not interior_edges:
        return 0.0

    total_length = 0.0
    for v0_idx, v1_idx in interior_edges:
        v0 = mesh.vertices[v0_idx].co
        v1 = mesh.vertices[v1_idx].co
        total_length += (v0 - v1).length

    return total_length / len(interior_edges)


def _apply_interior_decimate(
    obj,
    leaf_material_indices: Set[int],
    alpha_img,
    threshold: float,
    boundary_rings: int = 1,
    target_edge_mm: float = None,
    max_iterations: int = 3,
):
    """Apply iterative edge-protected interior decimation on leaf regions.

    Uses Blender's Decimate modifier in iterative passes with measured edge lengths
    to achieve consistent target mesh density. Each pass measures the current average
    edge length and calculates the optimal ratio to approach the target.

    Features:
        - UV preservation via delimit={'UV'} prevents breaking UV islands
        - Iterative refinement (2-3 passes) for accurate target edge length
        - Edge band protection preserves alpha silhouette quality
        - Non-leaf geometry (bark/wood) fully protected

    Args:
        obj: Blender mesh object
        leaf_material_indices: Set of material indices for leaf geometry
        alpha_img: PIL alpha image for boundary detection
        threshold: Alpha threshold for boundary detection
        boundary_rings: Number of vertex rings to protect around boundary
        target_edge_mm: Target interior edge length in millimeters.
                       Example: 5.0 = 5mm interior edges (coarser than boundary).
        max_iterations: Maximum decimation passes (default: 3, allows convergence)
    """
    import bpy

    mesh = obj.data
    if not mesh or not mesh.uv_layers.active:
        return

    if target_edge_mm is None or target_edge_mm <= 0:
        return

    # Convert mm to Blender units (1 Blender unit = 1000mm)
    target_edge_bu = target_edge_mm / 1000.0

    # Measure initial edge length
    current_avg_edge = _measure_interior_edge_length(mesh, leaf_material_indices)
    if current_avg_edge <= 0:
        return

    # Early exit if already at or above target
    if current_avg_edge >= target_edge_bu * 0.95:
        return

    # Per-vertex alpha for edge detection
    v_alpha = _build_vertex_alpha_map(mesh, alpha_img)
    if not v_alpha:
        return

    # Build adjacency from edges
    adjacency = {}
    for e in mesh.edges:
        v0, v1 = e.vertices[0], e.vertices[1]
        adjacency.setdefault(v0, set()).add(v1)
        adjacency.setdefault(v1, set()).add(v0)

    # Collect leaf vertices and initial edge vertices (crossing threshold)
    leaf_vertices = set()
    edge_vertices = set()
    for poly in mesh.polygons:
        is_leaf = poly.material_index in leaf_material_indices
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            if is_leaf:
                leaf_vertices.add(vi)
        if is_leaf:
            loop_indices = list(poly.loop_indices)
            for i in range(len(loop_indices)):
                li0 = loop_indices[i]
                li1 = loop_indices[(i + 1) % len(loop_indices)]
                v0 = mesh.loops[li0].vertex_index
                v1 = mesh.loops[li1].vertex_index
                a0 = v_alpha.get(v0)
                a1 = v_alpha.get(v1)
                if a0 is None or a1 is None:
                    continue
                if (a0 - threshold) * (a1 - threshold) < 0.0:
                    edge_vertices.add(v0)
                    edge_vertices.add(v1)

    if not leaf_vertices:
        return

    # Expand edge band by boundary_rings using adjacency
    current = set(edge_vertices)
    for _ in range(max(0, int(boundary_rings))):
        grow = set()
        for v in current:
            for nb in adjacency.get(v, ()):
                if nb in leaf_vertices and nb not in edge_vertices:
                    grow.add(nb)
        if not grow:
            break
        edge_vertices.update(grow)
        current = grow

    # Preserve set = edge band (leaf) + all non-leaf vertices
    preserve = set(edge_vertices)
    if len(leaf_material_indices) > 0:
        for poly in mesh.polygons:
            if poly.material_index not in leaf_material_indices:
                for li in poly.loop_indices:
                    preserve.add(mesh.loops[li].vertex_index)

    # Create vertex group for edge protection
    vg_name = "edge_protect"
    if vg_name in obj.vertex_groups:
        vg_old = obj.vertex_groups.get(vg_name)
        try:
            obj.vertex_groups.remove(vg_old)
        except Exception:
            pass
    vg = obj.vertex_groups.new(name=vg_name)

    if preserve:
        try:
            vg.add(list(preserve), 1.0, "REPLACE")
        except Exception:
            inds = list(preserve)
            step = 32766
            for i in range(0, len(inds), step):
                vg.add(inds[i : i + step], 1.0, "REPLACE")

    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    # Iterative decimation with edge length feedback
    for iteration in range(max_iterations):
        # Measure current edge length
        current_avg_edge = _measure_interior_edge_length(
            obj.data, leaf_material_indices
        )
        if current_avg_edge <= 0:
            break

        # Check if we've reached target (within 5% tolerance)
        if current_avg_edge >= target_edge_bu * 0.95:
            break

        # Calculate ratio based on measured edge length
        # Decimation ratio relates to edge length squared (area relationship)
        # ratio = (current/target)^2 gives the approximate face count ratio
        calculated_ratio = (current_avg_edge / target_edge_bu) ** 2
        ratio = max(0.1, min(0.95, calculated_ratio))

        # Apply Decimate modifier
        mod = obj.modifiers.new(name=f"InteriorDecimate_{iteration}", type="DECIMATE")
        mod.ratio = float(ratio)
        mod.vertex_group = vg.name
        mod.invert_vertex_group = True

        # UV preservation - prevent collapsing edges that would break UV islands
        if hasattr(mod, "delimit"):
            mod.delimit = {"UV"}

        # Triangulate for stable results
        if hasattr(mod, "use_collapse_triangulate"):
            mod.use_collapse_triangulate = True

        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            break

    # Cleanup vertex group
    try:
        if vg_name in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[vg_name])
    except Exception:
        pass


def setup_materials_with_textures(
    obj, blend_dir, species_name, output_dir, standardized_name, metadata=None
):
    """Setup materials with all available textures.

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

        # Convert bump maps to normal maps if needed
        if "bump" in texture_map and "normal" not in texture_map:
            from growpy.io.texture_utils import bump_to_normal

            # Generate normal map from bump
            bump_path = texture_map["bump"]
            normal_path = textures_dir / f"{bump_path.stem}_normal{bump_path.suffix}"

            if not normal_path.exists():
                converted = bump_to_normal(bump_path, normal_path)
                if converted:
                    texture_map["normal"] = normal_path
            else:
                texture_map["normal"] = normal_path

            # Remove bump from map since we've converted it
            del texture_map["bump"]

        # Handle two-sided materials (top/bottom diffuse textures)
        # Keep both if available for two-sided rendering
        has_two_sided = "diffuse_top" in texture_map and "diffuse_bottom" in texture_map

        if not has_two_sided:
            # Single-sided: use top or bottom as main diffuse
            if "diffuse_top" in texture_map:
                texture_map["diffuse"] = texture_map["diffuse_top"]
                del texture_map["diffuse_top"]
            elif "diffuse_bottom" in texture_map:
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
                    from growpy.io.texture_utils import bump_to_normal

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


def process_twig_file(
    blend_file,
    output_dir,
    formats,
    species_name,
    minimal_export=True,
    include_skeleton=True,
    densify=False,
    alpha_trim_threshold=0.0,
    subdiv_levels=3,
    edge_adaptive=False,
    edge_subdiv_levels=None,
    interior_decimate=False,
    boundary_rings=1,
    smooth_boundary=False,
    smooth_iterations=3,
    smooth_factor=0.5,
    target_edge_mm=None,
    interior_edge_mm=None,
    vertex_trim=False,
):
    """Process a single twig blend file.

    Args:
        blend_file: Path to .blend file
        output_dir: Output directory for exported files
        formats: List of export formats
        species_name: Name of species
        minimal_export: If True, creates minimal USD without materials/textures/attributes (geometry only)
        include_skeleton: If True, creates skeletal variant with skeleton (default: True, set False for static)
        densify: If True, subdivide mesh for higher polygon count (default: False)
        alpha_trim_threshold: Alpha threshold for geometry trimming (0.0 = disabled, default: 0.0)
        subdiv_levels: Number of subdivision levels (ignored if target_edge_mm is set)
        target_edge_mm: Target boundary edge length in mm for subdivision (overrides subdiv_levels)
        interior_edge_mm: Target interior edge length in mm for decimation. Uses iterative
                         decimation with edge length feedback and UV preservation.
        vertex_trim: If True, use vertex-based alpha trimming instead of face-based
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

            # Optional geometry processing for enhanced leaf detail
            # Restrict to leaf materials to avoid artifacts on twigs/bark
            if densify or alpha_trim_threshold > 0.0 or interior_decimate:
                leaf_mats = _detect_leaf_material_indices(obj)
                tex_map = _gather_texture_candidates(
                    blend_dir, standardized_name, species_name, metadata
                )

                # Get best alpha source: dedicated alpha/translucent texture, or diffuse embedded alpha
                alpha_tex_path, use_luminance = _get_alpha_texture_for_geometry(tex_map)

                # Load alpha image from best available source
                alpha_img = None
                if alpha_tex_path:
                    if use_luminance:
                        # Dedicated alpha/translucent texture - use luminance
                        alpha_img = _load_alpha_image(
                            alpha_tex_path,
                            require_alpha_channel=False,
                            allow_luminance_for_masks=True,
                        )
                    else:
                        # Diffuse texture - use embedded alpha channel
                        alpha_img = _load_alpha_image(
                            alpha_tex_path,
                            require_alpha_channel=True,
                            allow_luminance_for_masks=False,
                        )

                # 1) Densify leaf region (edge-adaptive only when explicitly enabled)
                if densify and leaf_mats:
                    if edge_adaptive:
                        if alpha_img is not None and alpha_trim_threshold > 0.0:
                            # Heavier cuts on edges, lighter inside
                            edge_cuts = max(1, int(subdiv_levels))
                            base_cuts = max(0, int(round(subdiv_levels * 0.25)))
                            densify_mesh_edge_adaptive(
                                obj,
                                material_indices=leaf_mats,
                                alpha_img=alpha_img,
                                threshold=alpha_trim_threshold,
                                base_cuts=base_cuts,
                                edge_cuts=edge_cuts,
                            )
                        else:
                            densify_mesh(
                                obj,
                                subdivision_levels=subdiv_levels,
                                material_indices=leaf_mats,
                                target_edge_mm=target_edge_mm,
                            )
                    else:
                        densify_mesh(
                            obj,
                            subdivision_levels=subdiv_levels,
                            material_indices=leaf_mats,
                            target_edge_mm=target_edge_mm,
                        )

                # Optional: extra edge-only densify pass using alpha silhouette
                # Runs after primary densify (uniform or adaptive) to increase edge detail
                if (
                    densify
                    and leaf_mats
                    and edge_subdiv_levels is not None
                    and int(edge_subdiv_levels) > 0
                ):
                    if alpha_img is not None and alpha_trim_threshold > 0.0:
                        densify_mesh_edge_adaptive(
                            obj,
                            material_indices=leaf_mats,
                            alpha_img=alpha_img,
                            threshold=alpha_trim_threshold,
                            base_cuts=0,
                            edge_cuts=max(1, int(edge_subdiv_levels)),
                        )

                # 2) Trim leaf edges using alpha texture
                # Uses dedicated alpha/translucent texture if available, else diffuse embedded alpha
                # MUST run before interior decimation so we only decimate remaining geometry
                if alpha_trim_threshold > 0.0 and leaf_mats and alpha_tex_path:
                    if vertex_trim:
                        # Vertex-based trimming: simpler, deletes vertices below threshold
                        trim_vertices_by_alpha(
                            obj,
                            str(alpha_tex_path),
                            alpha_trim_threshold,
                            require_alpha_channel=(not use_luminance),
                            material_indices=leaf_mats,
                            allow_luminance_for_masks=use_luminance,
                        )
                    else:
                        # Face-based trimming: samples at face centroid
                        trim_by_alpha_mask(
                            obj,
                            str(alpha_tex_path),
                            alpha_trim_threshold,
                            require_alpha_channel=(not use_luminance),
                            material_indices=leaf_mats,
                            allow_luminance_for_masks=use_luminance,
                        )

                # 3) Interior decimation (edge-protected) to reduce interior density
                # Runs AFTER trimming to only decimate the remaining opaque geometry
                # Uses iterative decimation with edge length feedback and UV preservation
                if interior_decimate and leaf_mats:
                    has_target_edge = (
                        interior_edge_mm is not None and interior_edge_mm > 0
                    )
                    if (
                        alpha_img is not None
                        and has_target_edge
                        and alpha_trim_threshold > 0.0
                    ):
                        try:
                            _apply_interior_decimate(
                                obj,
                                leaf_mats,
                                alpha_img,
                                threshold=alpha_trim_threshold,
                                boundary_rings=max(0, int(boundary_rings)),
                                target_edge_mm=interior_edge_mm,
                            )
                        except Exception:
                            pass

                # 4) Smooth boundary edges to follow texture curves more naturally
                # Applied AFTER trimming to smooth the jagged edges created by regular subdivision grid
                if smooth_boundary and leaf_mats:
                    if alpha_img is not None and alpha_trim_threshold > 0.0:
                        try:
                            _smooth_boundary_edges(
                                obj,
                                leaf_mats,
                                alpha_img,
                                threshold=alpha_trim_threshold,
                                smooth_iterations=max(1, int(smooth_iterations)),
                                smooth_factor=min(max(0.0, float(smooth_factor)), 1.0),
                                boundary_rings=max(0, int(boundary_rings)),
                            )
                        except Exception:
                            pass

                # Recalculate normals
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.normals_make_consistent(inside=False)
                bpy.ops.object.mode_set(mode="OBJECT")

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

                    # CRITICAL: Export UVs for texture mapping but disable materials/textures at Blender level
                    # Materials and textures will be added later via USD with opaque-only filtering
                    bpy.ops.wm.usd_export(
                        filepath=str(skel_export_path),
                        selected_objects_only=True,
                        export_materials=False,  # Disabled - added later with opaque-only filtering
                        export_textures=False,  # Disabled - added later with opaque-only filtering
                        export_uvmaps=True,  # CRITICAL: Required for texture mapping
                        export_normals=True,
                        export_mesh_colors=False,  # Force disabled for Nanite
                        use_instancing=False,
                        evaluation_mode="RENDER",
                        generate_preview_surface=False,  # Disabled - created later
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
                        minimal_export=minimal_export,
                    ):
                        # Copy opaque-only textures for skeletal twig (no alpha/translucent for Nanite)
                        textures_copied = copy_opaque_textures_for_skeletal(
                            blend_dir, output_dir, standardized_name, metadata
                        )

                        # Add opaque-only textures to skeletal twig material
                        try:
                            from pxr import Usd, UsdGeom

                            stage = Usd.Stage.Open(str(skel_export_path))
                            if stage:
                                # Find mesh prim
                                mesh_prim = None
                                for prim in stage.Traverse():
                                    if prim.IsA(UsdGeom.Mesh):
                                        mesh_prim = prim
                                        break

                                if mesh_prim:
                                    # Find textures directory
                                    texture_dir = output_dir / "textures"

                                    # Add material with opaque-only textures
                                    _add_twig_material(
                                        stage,
                                        UsdGeom.Mesh(mesh_prim),
                                        mesh_prim.GetPath(),
                                        texture_dir=(
                                            texture_dir
                                            if texture_dir.exists()
                                            else None
                                        ),
                                        species_name=species_name,
                                        standardized_name=standardized_name,
                                    )

                                    stage.Save()
                        except Exception:
                            pass
                    else:
                        pass

                    # Export static mesh variant if requested (no skeleton)
                    if not include_skeleton:
                        static_export_path = (
                            output_dir / f"{standardized_name}_static.{fmt}"
                        )

                        # Enable materials for static export
                        material_setup_success = setup_materials_with_textures(
                            obj,
                            blend_dir,
                            species_name,
                            output_dir,
                            standardized_name,
                            metadata,
                        )

                        # Export with materials and textures
                        bpy.ops.wm.usd_export(
                            filepath=str(static_export_path),
                            selected_objects_only=True,
                            export_materials=True,
                            export_textures=True,
                            export_uvmaps=True,
                            export_normals=True,
                            export_mesh_colors=False,
                            use_instancing=False,
                            evaluation_mode="RENDER",
                            generate_preview_surface=True,
                            relative_paths=True,
                            export_hair=False,
                            export_lights=False,
                        )

                        exported_files.append(static_export_path)

                        # Clean up static USD (remove skeleton artifacts, fix structure)
                        if clean_static_usd_file(static_export_path):
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

    # Cleanup: Keep original .blend file (preserve source assets)
    # Only remove auxiliary files that can be regenerated
    try:
        # Remove ReadMe.txt
        readme_file = output_dir / "ReadMe.txt"
        if readme_file.exists():
            readme_file.unlink()

        # Remove original source texture files ONLY if standardized copies exist
        # This allows running skeletal-only export without breaking future static exports
        # Original files use CamelCase or species-specific naming (e.g., BeechAlpha.jpg)
        # Standardized files use snake_case with full standardized name (e.g., european_beech_twig_alpha.jpg)
        textures_dir = output_dir / "textures"
        if textures_dir.exists() and not include_skeleton:
            # Only clean up non-standardized textures if we just created standardized ones
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

    # Parse optional flags
    args = sys.argv[5:] if len(sys.argv) > 5 else []
    minimal_export = "--minimal-export" in args
    densify = "--densify" in args

    # Parse numeric parameters
    displacement_strength = 0.0
    alpha_trim_threshold = 0.0
    subdiv_levels = 3

    for arg in args:
        if arg.startswith("--displacement="):
            try:
                displacement_strength = float(arg.split("=")[1])
            except ValueError:
                pass
        elif arg.startswith("--alpha-trim="):
            try:
                alpha_trim_threshold = float(arg.split("=")[1])
            except ValueError:
                pass
        elif arg.startswith("--subdiv="):
            try:
                subdiv_levels = max(1, int(arg.split("=")[1]))
            except ValueError:
                pass

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = process_twig_file(
        blend_file,
        output_dir,
        formats,
        species_name,
        minimal_export,
        densify=densify,
        displacement_strength=displacement_strength,
        alpha_trim_threshold=alpha_trim_threshold,
        subdiv_levels=subdiv_levels,
    )
