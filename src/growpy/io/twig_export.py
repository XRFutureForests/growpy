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
import logging
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

import bmesh
import bpy
import mathutils
import numpy as np

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


def export_blender_mesh_to_usd(
    obj, output_path, include_normals=True, include_uvs=True
):
    """Export Blender mesh object to USD file using pxr directly.

    This is a fallback when bpy.ops.wm.usd_export is not available (e.g., in standalone bpy).
    Creates a basic USD file with geometry only (no materials/textures).

    Args:
        obj: Blender mesh object or empty with child mesh to export
        output_path: Path to write USD file
        include_normals: Include vertex normals in export
        include_uvs: Include UV coordinates in export (best effort)

    Returns:
        True if export succeeded, False otherwise
    """
    try:
        # Find actual mesh object (might be passed an empty with children)
        mesh_obj = obj
        if not hasattr(obj.data, "vertices"):
            # obj is an empty, find first mesh child
            found = False
            for child in obj.children:
                if hasattr(child.data, "vertices"):
                    mesh_obj = child
                    found = True
                    break
            if not found:
                logger.error("No mesh data found in object or its children")
                return False

        # Create USD stage and mesh prim
        stage = Usd.Stage.CreateNew(str(output_path))
        mesh = mesh_obj.data
        mesh_prim = UsdGeom.Mesh.Define(stage, Sdf.Path("/Mesh"))

        # Collect and set vertex positions
        points = []
        for vert in mesh.vertices:
            co = vert.co
            points.append(Gf.Vec3f(co.x, co.y, co.z))

        mesh_prim.CreatePointsAttr().Set(points)

        # Collect and set face vertex counts and indices
        face_vertex_counts = []
        face_vertex_indices = []

        for poly in mesh.polygons:
            face_vertex_counts.append(len(poly.vertices))
            face_vertex_indices.extend(poly.vertices)

        mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)
        mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices)

        # Add normals if requested
        if include_normals:
            normals = []
            for vert in mesh.vertices:
                n = vert.normal
                normals.append(Gf.Vec3f(n.x, n.y, n.z))
            mesh_prim.CreateNormalsAttr().Set(normals)

        # Save the stage
        stage.GetRootLayer().Save()
        return True

    except Exception as e:
        logger.error("Direct USD export failed: %s", e, exc_info=True)
        return False


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
        from pxr import Gf, Sdf, UsdShade

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

        # Derive prim name from output filename to follow naming convention
        # e.g., european_beech_foliage_a_static.usda -> european_beech_foliage_a
        prim_name = Path(usd_path).stem.replace("_skeletal", "").replace("_static", "")

        # Create root Xform with species-specific name
        root_path = Sdf.Path(f"/{prim_name}")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Re-parent mesh under root as {prim_name}_mesh
        new_mesh_path = root_path.AppendChild(f"{prim_name}_mesh")
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

            # Update material bindings (direct mesh binding + GeomSubset bindings)
            new_mesh_prim = stage.GetPrimAtPath(new_mesh_path)

            def _remap_material_binding(prim):
                mat_binding_api = UsdShade.MaterialBindingAPI(prim)
                mat_binding = mat_binding_api.GetDirectBinding()
                if not mat_binding:
                    return
                mat_path = mat_binding.GetMaterialPath()
                if not mat_path or "/root/_materials/" not in str(mat_path):
                    return
                new_mat_path_str = str(mat_path).replace(
                    "/root/_materials/", str(new_materials_path) + "/"
                )
                path_parts = new_mat_path_str.split("/")
                if path_parts:
                    mat_name = path_parts[-1].split(".")[0]
                    path_parts[-1] = mat_name
                    new_mat_path_str = "/".join(path_parts)
                new_mat_path = Sdf.Path(new_mat_path_str)
                mat_prim = stage.GetPrimAtPath(new_mat_path)
                if mat_prim and mat_prim.IsValid():
                    UsdShade.MaterialBindingAPI.Apply(prim).Bind(
                        UsdShade.Material(mat_prim)
                    )

            _remap_material_binding(new_mesh_prim)
            for child in new_mesh_prim.GetChildren():
                if child.IsA(UsdGeom.Subset):
                    _remap_material_binding(child)

        # CRITICAL: Remove the old /root prim that Blender created
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())

        # Set as default prim so it's the primary reference target
        foliage_prim = stage.GetPrimAtPath(f"/{prim_name}")
        if foliage_prim and foliage_prim.IsValid():
            stage.SetDefaultPrim(foliage_prim)

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

        # Derive prim name from output filename to follow naming convention
        prim_name = Path(usd_path).stem.replace("_skeletal", "").replace("_static", "")
        root_path = Sdf.Path(f"/{prim_name}")
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
        skel_path = root_path.AppendChild(f"{prim_name}_skel")
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
            joint_indices_attr.Set(Vt.IntArray([-1]))
        # Re-parent mesh under SkelRoot
        new_mesh_path = root_path.AppendChild(f"{prim_name}_mesh")
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

        # Remove the old /root prim that Blender created
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())

        # Set as default prim so it's the primary reference target
        foliage_prim = stage.GetPrimAtPath(f"/{prim_name}")
        if foliage_prim and foliage_prim.IsValid():
            stage.SetDefaultPrim(foliage_prim)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        return False


from growpy.utils.naming import standardize_twig_name  # noqa: E402


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

    Twig assets are primarily leaf/needle geometry. Any material NOT explicitly
    tagged as bark/branch/wood/dead is assumed to be a leaf and eligible for
    geometry processing (alpha trim, densify, interior decimate).
    """
    exclude_kw = ("bark", "branch", "wood", "dead")
    mats = getattr(obj.data, "materials", []) or []

    if not mats:
        return {0}

    idxs = set()
    for i, mat in enumerate(mats):
        name = (mat.name if mat else "").lower()
        if not any(k in name for k in exclude_kw):
            idxs.add(i)

    # If all materials were excluded, return empty set (skip processing)
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


def _save_face_material_sidecar(obj, output_dir: Path, standardized_name: str) -> None:
    """Save per-face material assignment from Blender mesh as JSON sidecar.

    Enables downstream OBJ export to split faces into leaf/wood/fruit groups
    for material-aware mesh simplification. Must be called after all geometry
    processing so face indices match the exported USD.
    """
    mesh = obj.data
    mats = getattr(mesh, "materials", []) or []
    if not mats or len(mats) < 2:
        return

    mat_names = [mat.name if mat else f"material_{i}" for i, mat in enumerate(mats)]
    face_mat_indices = [p.material_index for p in mesh.polygons]

    sidecar_path = output_dir / f"{standardized_name}_face_materials.json"
    with open(sidecar_path, "w") as f:
        json.dump({"materials": mat_names, "face_material_indices": face_mat_indices}, f)


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


def densify_mesh(obj, subdivision_levels=3, material_indices=None):
    """Densify mesh using subdivision to create more triangles.

    Args:
        obj: Blender mesh object
        subdivision_levels: Number of subdivision iterations (default: 3)
        material_indices: Optional set of material indices to restrict densification
    """
    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Use bmesh for subdivision
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        edges = bm.edges
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


def _measure_average_edge_length(mesh, material_indices=None):
    """Measure average edge length for faces matching material indices.

    Args:
        mesh: Blender mesh data
        material_indices: Optional set of material indices to filter by

    Returns:
        Average edge length in Blender units, or 0.0 if no edges found.
    """
    edge_set = set()
    for poly in mesh.polygons:
        if material_indices and poly.material_index not in material_indices:
            continue
        for edge_key in poly.edge_keys:
            edge_set.add(edge_key)

    if not edge_set:
        return 0.0

    total_length = 0.0
    for v0_idx, v1_idx in edge_set:
        v0 = mesh.vertices[v0_idx].co
        v1 = mesh.vertices[v1_idx].co
        total_length += (v0 - v1).length

    return total_length / len(edge_set)


def densify_mesh_to_target_edge(
    obj, target_edge_mm, material_indices=None, max_iterations=8
):
    """Densify mesh by iteratively subdividing until target edge length is reached.

    This ensures consistent mesh density across different twig sizes by targeting
    an absolute edge length rather than a fixed subdivision count.

    Args:
        obj: Blender mesh object
        target_edge_mm: Target edge length in millimeters (e.g., 0.5 for 0.5mm edges)
        material_indices: Optional set of material indices to restrict densification
        max_iterations: Maximum subdivision iterations to prevent runaway (default: 8)

    Returns:
        Final average edge length in mm
    """
    if target_edge_mm is None or target_edge_mm <= 0:
        return 0.0

    # Convert mm to Blender units (1 Blender unit = 1m = 1000mm for typical twig scale)
    target_edge_bu = target_edge_mm / 1000.0

    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Measure initial edge length
        initial_edge = _measure_average_edge_length(obj.data, material_indices)
        initial_edge_mm = initial_edge * 1000.0

        for iteration in range(max_iterations):
            # Measure current edge length
            current_edge = _measure_average_edge_length(obj.data, material_indices)
            if current_edge <= 0:
                break

            # Check if we've reached target (within 20% tolerance)
            if current_edge <= target_edge_bu * 1.2:
                break

            # Calculate how many cuts needed to approximately halve edge length
            # Each cut=1 roughly halves edge length
            ratio = current_edge / target_edge_bu
            if ratio <= 1.5:
                cuts = 1
            elif ratio <= 3:
                cuts = 2
            else:
                cuts = 3  # Don't go too aggressive per iteration

            # Subdivide
            bm = bmesh.new()
            bm.from_mesh(obj.data)

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
                    bm, edges=edges, cuts=cuts, use_grid_fill=True
                )

            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()

        # Return final edge length in mm
        final_edge = _measure_average_edge_length(obj.data, material_indices)
        final_edge_mm = final_edge * 1000.0

        logger.debug(
            "Adaptive densify: %.2fmm -> %.2fmm (target: %.2fmm, %d iterations)",
            initial_edge_mm, final_edge_mm, target_edge_mm, iteration + 1,
        )

        return final_edge_mm

    except Exception:
        return 0.0


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
    method="all",
    preserve_interior=True,
):
    """Trim mesh geometry based on alpha/opacity mask texture.

    Removes faces based on alpha values using specified method.

    Args:
        obj: Blender mesh object
        alpha_texture_path: Path to alpha/mask texture
        threshold: Alpha threshold for keeping geometry (0.0-1.0, default: 0.5)
        method: 'all' (default) = delete only if ALL vertices < threshold (conservative),
                'average' = delete if avg alpha < threshold (more aggressive)
        preserve_interior: If True (default), preserve faces whose center samples
                           an opaque alpha value, protecting thin geometry centers.
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
        faces_to_delete = []
        center_preserved = 0
        for face in bm.faces:
            if material_indices and face.material_index not in material_indices:
                continue

            # Sample alpha at each vertex of the face
            alpha_values = []
            uv_coords = []
            for loop in face.loops:
                uv = loop[uv_layer_bm].uv
                uv_coords.append((uv.x, uv.y))

                # Sample alpha texture
                x = int(uv.x * (img_width - 1))
                y = int((1.0 - uv.y) * (img_height - 1))  # Flip Y
                x = max(0, min(img_width - 1, x))
                y = max(0, min(img_height - 1, y))

                # Get alpha value (0-255)
                alpha = pixels[x, y] / 255.0
                if invert_mask:
                    alpha = 1.0 - alpha
                alpha_values.append(alpha)

            # PRESERVE_INTERIOR: Also sample alpha at face centroid
            # This protects thin geometry (needles) whose corners may sample
            # transparent areas but whose CENTER samples opaque texture
            if preserve_interior and uv_coords:
                center_u = sum(uv[0] for uv in uv_coords) / len(uv_coords)
                center_v = sum(uv[1] for uv in uv_coords) / len(uv_coords)
                cx = int(center_u * (img_width - 1))
                cy = int((1.0 - center_v) * (img_height - 1))
                cx = max(0, min(img_width - 1, cx))
                cy = max(0, min(img_height - 1, cy))
                center_alpha = pixels[cx, cy] / 255.0
                if invert_mask:
                    center_alpha = 1.0 - center_alpha
                # If center is opaque, preserve this face (needle center protection)
                if center_alpha >= threshold:
                    center_preserved += 1
                    continue

            # Delete face based on method
            if method == "all":
                # Delete only if ALL vertices below threshold (aggressive)
                if all(a < threshold for a in alpha_values):
                    faces_to_delete.append(face)
            else:  # method == "average" (default)
                # Delete if average alpha below threshold (better for thin geometry)
                avg_alpha = (
                    sum(alpha_values) / len(alpha_values) if alpha_values else 0.0
                )
                if avg_alpha < threshold:
                    faces_to_delete.append(face)

        # Delete marked faces
        total_faces_before = len(bm.faces)
        bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
        faces_remaining = len(bm.faces)

        center_msg = (
            f", {center_preserved} center-preserved"
            if preserve_interior and center_preserved > 0
            else ""
        )
        logger.debug(
            "Alpha trimming: deleted %d/%d faces (%.1f%%), %d remaining%s, threshold=%s",
            len(faces_to_delete), total_faces_before,
            100 * len(faces_to_delete) / total_faces_before,
            faces_remaining, center_msg, threshold,
        )

        # Write back to mesh
        bm.to_mesh(mesh)
        bm.free()

        mesh.update()
    except Exception as e:
        logger.warning("Alpha trimming failed: %s", e, exc_info=True)


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


def _detect_alpha_inversion(alpha_img):
    """Detect if alpha mask uses inverted convention (black=opaque).

    Uses corner-based detection: samples corners of the texture to determine
    the "background" value (should be transparent in standard convention).

    The actual leaf/bark geometry doesn't extend to texture edges, so corners
    reliably represent the transparent background. If corners are bright,
    the convention is inverted (white=opaque).

    Returns:
        True if texture uses inverted convention (bright corners = white background)
    """
    if alpha_img is None:
        return False

    pixels_array = np.array(alpha_img, dtype=np.float32)
    h, w = pixels_array.shape

    # Sample corners: 10x10 patches at each corner
    patch_size = min(10, h // 4, w // 4)
    if patch_size < 2:
        # Image too small to detect reliably, assume standard
        return False

    corners = [
        pixels_array[0:patch_size, 0:patch_size],  # top-left
        pixels_array[0:patch_size, -patch_size:],  # top-right
        pixels_array[-patch_size:, 0:patch_size],  # bottom-left
        pixels_array[-patch_size:, -patch_size:],  # bottom-right
    ]

    # Calculate mean corner value (represents the background)
    corner_values = [corner.mean() for corner in corners]
    corner_mean = np.mean(corner_values)

    # If corners are bright (> ~155/255), background is white = inverted convention
    # If corners are dark (< ~100/255), background is black = standard convention
    return corner_mean > 155


def _sample_alpha_at_uv(uv_x, uv_y, alpha_img, invert=False):
    """Sample alpha value at UV coordinate from alpha image.

    Args:
        uv_x, uv_y: UV coordinates (0-1 range)
        alpha_img: PIL Image in grayscale mode
        invert: If True, invert alpha (1.0 - value)

    Returns:
        Alpha value 0.0-1.0
    """
    if alpha_img is None:
        return 1.0
    pixels = alpha_img.load()
    w, h = alpha_img.size
    x = int(max(0, min(w - 1, uv_x * (w - 1))))
    y = int(max(0, min(h - 1, (1.0 - uv_y) * (h - 1))))
    alpha = pixels[x, y] / 255.0
    return (1.0 - alpha) if invert else alpha


def densify_and_trim_interleaved(
    obj,
    material_indices,
    alpha_img,
    threshold,
    target_edge_factor=0.5,
    max_iterations=10,
    method="all",
):
    """Densify leaf edges with interleaved trimming - transition-face-aware algorithm.

    Algorithm:
        1. Pre-triangulate all leaf faces (ensure triangle assumption)
        2. Build vertex alpha map from texture sampling (auto-inverts if needed)
        3. Identify working faces:
           - Transition faces: have both opaque (>=threshold) and transparent (<threshold) vertices
           - Transparent faces: ALL vertices transparent AND at least one edge > target
           - Boundary faces: have at least one mesh boundary edge
        4. Delete small fully-transparent faces (all edges <= target)
        5. Subdivide long edges in working faces (edge_split affects all adjacent faces)
        6. Repeat steps 2-5 until no changes

    Key advantages:
        - Transition faces get densified first (the actual leaf silhouette boundary)
        - Transparent faces are subdivided only to make them small enough to delete
        - edge_split naturally propagates subdivision to neighboring faces
        - Auto-detects inverted alpha masks (black=opaque convention)

    Args:
        obj: Blender mesh object
        material_indices: Set of material indices for leaf geometry
        alpha_img: Alpha texture PIL Image (grayscale)
        threshold: Alpha threshold (0.0-1.0) - vertices below are "transparent"
        target_edge_factor: Target edge as fraction of avg edge (default: 0.5)
        max_iterations: Maximum subdivision iterations (default: 10)
        method: Trim method - "all" (delete only if ALL verts < threshold) or
                "average" (delete if avg < threshold). Default "all" is conservative.
    """
    try:
        mesh = obj.data
        if not mesh or not material_indices or alpha_img is None:
            return

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Detect if alpha mask needs inversion by sampling average alpha
        # If mean alpha < 0.5, the mask likely uses black=opaque convention
        invert_alpha = _detect_alpha_inversion(alpha_img)

        # Measure initial mesh scale
        avg_edge_length = _measure_average_edge_length(mesh, material_indices)
        if avg_edge_length <= 0:
            return

        target_edge_bu = avg_edge_length * max(0.1, min(1.0, target_edge_factor))

        initial_face_count = len(mesh.polygons)

        # Limit face growth to prevent runaway subdivision
        # Allow up to 20x original face count for thorough boundary densification
        # This allows fine subdivision (0.05 factor) without hitting the limit
        max_face_count = initial_face_count * 20

        total_faces_deleted = 0

        # PRE-PROCESSING: Ensure mesh is fully triangulated before edge detection
        # This satisfies the algorithm requirement to check and triangulate if needed
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        leaf_faces_to_triangulate = [
            f
            for f in bm.faces
            if f.material_index in material_indices and len(f.verts) > 3
        ]
        if leaf_faces_to_triangulate:
            bmesh.ops.triangulate(bm, faces=leaf_faces_to_triangulate)

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        for iteration in range(max_iterations):
            # Check face count limit
            current_face_count = len(mesh.polygons)
            if current_face_count > max_face_count:
                break

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            # Get UV layer
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                bm.free()
                return

            # Build vertex alpha map by sampling texture at UV coordinates
            vert_alpha = {}
            vert_uv = {}
            for face in bm.faces:
                if face.material_index not in material_indices:
                    continue
                for loop in face.loops:
                    vi = loop.vert.index
                    uv = loop[uv_layer].uv
                    alpha = _sample_alpha_at_uv(
                        uv.x, uv.y, alpha_img, invert=invert_alpha
                    )
                    # Average if vertex seen multiple times
                    if vi in vert_alpha:
                        vert_alpha[vi] = (vert_alpha[vi] + alpha) / 2
                        old_uv = vert_uv[vi]
                        vert_uv[vi] = ((old_uv[0] + uv.x) / 2, (old_uv[1] + uv.y) / 2)
                    else:
                        vert_alpha[vi] = alpha
                        vert_uv[vi] = (uv.x, uv.y)

            leaf_faces_set = {
                f for f in bm.faces if f.material_index in material_indices
            }

            # STEP 1: Identify working faces - THREE categories:
            # A) Transition faces: have BOTH opaque and transparent vertices (alpha threshold crossing)
            # B) Transparent faces: ALL vertices transparent with long edges (need subdivision)
            # C) Boundary faces: have at least one mesh boundary edge
            working_faces = set()
            transition_faces = set()
            transparent_faces = set()

            for face in leaf_faces_set:
                if len(face.verts) != 3:
                    continue

                alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                has_opaque = any(a >= threshold for a in alphas)
                has_transparent = any(a < threshold for a in alphas)
                all_transparent = all(a < threshold for a in alphas)

                # Category A: Transition face (crosses threshold)
                if has_opaque and has_transparent:
                    transition_faces.add(face)
                    working_faces.add(face)

                # Category B: Fully transparent face with long edges
                elif all_transparent:
                    max_edge = max(e.calc_length() for e in face.edges)
                    if max_edge > target_edge_bu:
                        transparent_faces.add(face)
                        working_faces.add(face)

                # Category C: Boundary face (mesh edge)
                for edge in face.edges:
                    adj_count = sum(1 for f in edge.link_faces if f in leaf_faces_set)
                    if adj_count == 1:  # Boundary edge
                        working_faces.add(face)
                        break

            # STEP 2: Delete small fully-transparent faces
            faces_to_delete = []
            for face in leaf_faces_set:
                if len(face.verts) != 3:
                    continue

                alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                if not all(a < threshold for a in alphas):
                    continue

                # All edges must be short enough to delete
                max_edge = max(e.calc_length() for e in face.edges)
                if max_edge <= target_edge_bu:
                    faces_to_delete.append(face)

            if faces_to_delete:
                bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
                total_faces_deleted += len(faces_to_delete)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                # Rebuild working faces after deletion
                leaf_faces_set = {
                    f for f in bm.faces if f.material_index in material_indices
                }
                working_faces = set()

                for face in leaf_faces_set:
                    if len(face.verts) != 3:
                        continue

                    alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                    has_opaque = any(a >= threshold for a in alphas)
                    has_transparent = any(a < threshold for a in alphas)
                    all_transparent = all(a < threshold for a in alphas)

                    if has_opaque and has_transparent:
                        working_faces.add(face)
                    elif all_transparent:
                        max_edge = max(e.calc_length() for e in face.edges)
                        if max_edge > target_edge_bu:
                            working_faces.add(face)
                    else:
                        for edge in face.edges:
                            adj_count = sum(
                                1 for f in edge.link_faces if f in leaf_faces_set
                            )
                            if adj_count == 1:
                                working_faces.add(face)
                                break

            # STEP 3: Find edges to subdivide in working faces
            edges_to_split = set()
            for face in working_faces:
                for edge in face.edges:
                    if edge.calc_length() > target_edge_bu:
                        edges_to_split.add(edge)

            # Check stopping condition
            if not faces_to_delete and not edges_to_split:
                bm.to_mesh(mesh)
                bm.free()
                mesh.update()
                break

            # STEP 4: Split edges at midpoint
            for edge in edges_to_split:
                if edge.is_valid:
                    try:
                        bmesh.utils.edge_split(edge, edge.verts[0], 0.5)
                    except Exception:
                        pass

            # STEP 5: Triangulate any n-gons created by subdivision
            # Important: triangulate ALL n-gons in leaf geometry, not just working faces
            new_ngons = [
                f
                for f in bm.faces
                if len(f.verts) > 3 and f.material_index in material_indices
            ]
            if new_ngons:
                bmesh.ops.triangulate(bm, faces=new_ngons)

            # Update mesh and prepare for next iteration
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

        # After all iterations, ensure ALL faces are triangles for Nanite compatibility
        bm = bmesh.new()
        bm.from_mesh(mesh)
        ngons = [f for f in bm.faces if len(f.verts) > 3]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)

        # FINAL PASS: Delete triangles that are fully transparent
        # Now that we have small triangles, we can identify fully-transparent ones
        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            final_faces_to_delete = []
            for face in bm.faces:
                if face.material_index not in material_indices:
                    continue
                # Sample all vertices
                all_transparent = True
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    alpha = _sample_alpha_at_uv(
                        uv.x, uv.y, alpha_img, invert=invert_alpha
                    )
                    if alpha >= threshold:
                        all_transparent = False
                        break
                if all_transparent:
                    # Also check centroid
                    loop_uvs = [
                        (loop[uv_layer].uv.x, loop[uv_layer].uv.y)
                        for loop in face.loops
                    ]
                    center_u = sum(uv[0] for uv in loop_uvs) / len(loop_uvs)
                    center_v = sum(uv[1] for uv in loop_uvs) / len(loop_uvs)
                    center_alpha = _sample_alpha_at_uv(
                        center_u, center_v, alpha_img, invert=invert_alpha
                    )
                    if center_alpha < threshold:
                        final_faces_to_delete.append(face)

            if final_faces_to_delete:
                bmesh.ops.delete(bm, geom=final_faces_to_delete, context="FACES")
                total_faces_deleted += len(final_faces_to_delete)

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        mesh.update()
        final_vert_count = len(mesh.vertices)
        final_face_count = len(mesh.polygons)

        logger.info(
            "Alpha trim: %d->%d faces (%d deleted)",
            initial_face_count, final_face_count, total_faces_deleted,
        )

    except Exception as e:
        logger.warning("Alpha trim error: %s", e, exc_info=True)


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


def _cleanup_boundary_spikes(
    obj,
    leaf_material_indices: Set[int],
    iterations: int = 2,
    area_factor: float = 0.2,
    short_len_factor: float = 0.25,
    angle_deg: float = 55.0,
):
    """Remove tiny boundary spike faces and collapse very short boundary edges.

    Targets sliver triangles created by alpha-based trimming that point inwards or
    stick out as small spikes. Heuristics:
      - Delete faces with >=2 boundary edges and very small area
      - Prefer deletion when the angle between the two boundary edges at the tip
        is sharp (below angle_deg)
      - Collapse boundary edges that are much shorter than the typical boundary
        edge length

    Args:
        obj: Blender mesh object (after alpha trimming)
        leaf_material_indices: Set of material indices for leaf geometry
        iterations: How many cleanup passes to run
        area_factor: Threshold as a fraction of median leaf-face area
        short_len_factor: Boundary edge collapse threshold as fraction of median
        angle_deg: Max angle at spike tip to qualify for deletion
    """
    mesh = obj.data
    if not mesh:
        return

    import bmesh

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Collect leaf faces and basic stats
    leaf_faces = [f for f in bm.faces if f.material_index in leaf_material_indices]
    if not leaf_faces:
        bm.free()
        return

    face_areas = [f.calc_area() for f in leaf_faces]
    if not face_areas:
        bm.free()
        return

    # Robust median area for thresholds
    sorted_areas = sorted(face_areas)
    median_area = sorted_areas[len(sorted_areas) // 2] or 1e-12

    # Boundary edge length stats
    boundary_edges = []
    leaf_face_set = set(leaf_faces)
    for e in bm.edges:
        if sum(1 for f in e.link_faces if f in leaf_face_set) == 1:
            boundary_edges.append(e)
    if boundary_edges:
        lengths = [e.calc_length() for e in boundary_edges]
        lengths.sort()
        median_len = lengths[len(lengths) // 2] or 1e-9
    else:
        median_len = 1e-9

    short_len_thresh = median_len * max(0.0, float(short_len_factor))
    spike_angle = math.radians(max(1.0, float(angle_deg)))

    for _ in range(max(1, int(iterations))):
        to_delete = set()

        for f in list(leaf_faces):
            # Count boundary edges for this face
            b_edges = [
                e
                for e in f.edges
                if sum(1 for lf in e.link_faces if lf in leaf_face_set) == 1
            ]
            if len(b_edges) < 2:
                continue

            area = f.calc_area()
            # Angle at the common vertex of two boundary edges (if exists)
            sharp = False
            if len(b_edges) >= 2:
                v_common = None
                s0 = set(b_edges[0].verts)
                s1 = set(b_edges[1].verts)
                inter = s0 & s1
                if inter:
                    v_common = list(inter)[0]
                if v_common is not None:
                    # Build vectors along the two edges from the common vertex
                    vecs = []
                    for e in b_edges[:2]:
                        other = e.other_vert(v_common)
                        v = other.co - v_common.co
                        if v.length_squared > 0:
                            vecs.append(v.normalized())
                    if len(vecs) == 2:
                        try:
                            ang = vecs[0].angle(vecs[1])
                            sharp = ang < spike_angle
                        except Exception:
                            sharp = False

            if area < median_area * area_factor or sharp:
                to_delete.add(f)

        if to_delete:
            bmesh.ops.delete(bm, geom=list(to_delete), context="FACES")
            # Refresh cached collections
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            # Rebuild leaf face list after deletions
            leaf_faces = [
                f for f in bm.faces if f.material_index in leaf_material_indices
            ]
            leaf_face_set = set(leaf_faces)

        # Collapse very short boundary edges
        to_collapse = [
            e
            for e in bm.edges
            if sum(1 for lf in e.link_faces if lf in leaf_face_set) == 1
            and e.calc_length() < short_len_thresh
        ]
        if to_collapse:
            try:
                bmesh.ops.collapse(bm, edges=to_collapse)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
            except Exception:
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _is_likely_tube_component(component, boundary_edge_set):
    """Check if a component with boundary edges is an open-ended cylinder.

    Open-ended cylinders have boundary edges only at their uncapped ends,
    forming small closed rings. Leaves have boundary edges around their
    entire perimeter (large single loop after alpha trimming).

    Uses two signals:
    - Boundary loop count: tubes have 2 loops (both ends open) or 1 (one end capped)
    - Boundary vertex ratio: tubes have few boundary verts (just the end rings)
      relative to total verts, while leaves have many (the entire silhouette)
    """
    comp_boundary = set()
    comp_verts = set()
    for f in component:
        for e in f.edges:
            if e in boundary_edge_set:
                comp_boundary.add(e)
        for v in f.verts:
            comp_verts.add(v)

    if not comp_boundary or len(comp_verts) < 8:
        return False

    # Count boundary loops (connected components of boundary edges)
    boundary_visited = set()
    loop_count = 0
    for start_edge in comp_boundary:
        if start_edge in boundary_visited:
            continue
        loop_count += 1
        stack = [start_edge]
        while stack:
            edge = stack.pop()
            if edge in boundary_visited:
                continue
            boundary_visited.add(edge)
            for v in edge.verts:
                for linked_edge in v.link_edges:
                    if (
                        linked_edge in comp_boundary
                        and linked_edge not in boundary_visited
                    ):
                        stack.append(linked_edge)

    comp_boundary_verts = set()
    for e in comp_boundary:
        for v in e.verts:
            comp_boundary_verts.add(v)

    boundary_vert_ratio = len(comp_boundary_verts) / len(comp_verts)

    # 2+ boundary loops (both ends open) with moderate boundary ratio -> tube
    if loop_count >= 2 and boundary_vert_ratio < 0.5:
        return True

    # Single open end (one end capped): very low boundary ratio -> tube
    if loop_count == 1 and boundary_vert_ratio < 0.15:
        return True

    return False


def _apply_interior_decimate(
    obj,
    ratio: float = 0.5,
    boundary_rings: int = 1,
):
    """Apply topology-based interior decimation on leaf/needle geometry.

    Classifies mesh faces by connected component topology:
    - Tube components (no boundary edges) = branch cylinders -> protected
    - Open-ended tube components (boundary at uncapped ends) -> protected
    - Plane components (has boundary edges) = leaves/needles -> interior decimated

    Boundary vertices (leaf silhouette edges) are also protected, so only the
    interior of leaf planes gets simplified.

    Args:
        obj: Blender mesh object (should be called AFTER alpha trimming)
        ratio: Decimation ratio (0.0-1.0, lower = more reduction)
        boundary_rings: Number of vertex rings to protect around boundary
    """
    if ratio <= 0.0 or ratio >= 1.0:
        return

    mesh = obj.data
    if not mesh:
        return

    import bmesh

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # Find boundary edges (edges with exactly 1 adjacent face)
    boundary_edge_set = set()
    for edge in bm.edges:
        if len(edge.link_faces) == 1:
            boundary_edge_set.add(edge)

    # Find connected face components and classify each
    visited = set()
    tube_verts = set()
    plane_faces = set()
    plane_verts = set()

    for start_face in bm.faces:
        if start_face in visited:
            continue
        component = set()
        stack = [start_face]
        while stack:
            face = stack.pop()
            if face in visited:
                continue
            visited.add(face)
            component.add(face)
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor not in visited:
                        stack.append(neighbor)

        has_boundary = any(e in boundary_edge_set for f in component for e in f.edges)
        if not has_boundary or _is_likely_tube_component(component, boundary_edge_set):
            for f in component:
                for v in f.verts:
                    tube_verts.add(v)
        else:
            plane_faces.update(component)
            for f in component:
                for v in f.verts:
                    plane_verts.add(v)

    if not plane_faces:
        bm.free()
        return

    # Find boundary vertices on plane components (leaf silhouette edges)
    boundary_verts = set()
    for edge in boundary_edge_set:
        for vert in edge.verts:
            boundary_verts.add(vert)

    if not boundary_verts:
        bm.free()
        return

    # Expand boundary protection by boundary_rings
    current = set(boundary_verts)
    for _ in range(max(0, int(boundary_rings))):
        grow = set()
        for v in current:
            for edge in v.link_edges:
                for nb in edge.verts:
                    if nb in plane_verts and nb not in boundary_verts:
                        grow.add(nb)
        if not grow:
            break
        boundary_verts.update(grow)
        current = grow

    # Protect: boundary verts (silhouette) + tube verts (branches) + non-mesh verts
    preserve_indices = {v.index for v in boundary_verts}
    preserve_indices.update(v.index for v in tube_verts)

    total = len(bm.verts)
    decimatable = total - len(preserve_indices)

    bm.free()

    if decimatable <= 0:
        logger.debug(
            "Interior decimate: skipped (no interior verts to decimate, "
            "%d tube + %d boundary = all verts protected)",
            len(tube_verts), len(boundary_verts),
        )
        return

    logger.info(
        "Interior decimate: %d tube verts protected, "
        "%d boundary verts protected, %d verts decimatable",
        len(tube_verts), len(boundary_verts), decimatable,
    )

    # Create/replace vertex group
    vg_name = "edge_protect"
    if vg_name in obj.vertex_groups:
        vg_old = obj.vertex_groups.get(vg_name)
        try:
            obj.vertex_groups.remove(vg_old)
        except Exception:
            pass
    vg = obj.vertex_groups.new(name=vg_name)

    if preserve_indices:
        try:
            vg.add(list(preserve_indices), 1.0, "REPLACE")
        except Exception:
            # Fallback: add in chunks to avoid limits
            inds = list(preserve_indices)
            step = 32766
            for i in range(0, len(inds), step):
                vg.add(inds[i : i + step], 1.0, "REPLACE")

    # Apply Decimate (Collapse) only to non-preserved (invert group)
    import bpy

    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    mod = obj.modifiers.new(name="InteriorDecimate", type="DECIMATE")
    mod.ratio = float(ratio)
    mod.vertex_group = vg.name
    mod.invert_vertex_group = True
    # Triangulate collapse produces more stable results for our pipeline
    if hasattr(mod, "use_collapse_triangulate"):
        mod.use_collapse_triangulate = True

    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        # If apply fails (rare), leave modifier on the stack
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

    # Group textures by material affinity and season.
    # Material EXISTENCE is determined by mesh structure (bark/leaf face regions
    # from joined twig objects), NOT by texture filenames.
    # Texture ASSIGNMENT uses filename affinity to route textures to the
    # correct material (bark-related textures -> bark material, etc.).
    bark_tex_keywords = ["bark", "twig", "branch", "wood", "stem"]
    material_groups = {}

    for texture in available_textures:
        tex_type = classify_texture_from_name(texture.stem)
        tex_lower = texture.stem.lower()

        # Route texture to bark or leaf group by filename affinity
        material_part = (
            "bark" if any(kw in tex_lower for kw in bark_tex_keywords) else "leaf"
        )

        # Detect season
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
        if mat_group_key not in material_groups:
            material_groups[mat_group_key] = []
        material_groups[mat_group_key].append(texture)

    # Consolidate season variants: if summer exists, prefer it
    season_prioritization = {
        "leaf": [],
        "bark": [],
    }

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
    # Material existence is driven by mesh structure, not texture filenames.
    if had_multiple_materials and original_bark_indices:
        has_bark_group = any(
            any(kw in name.lower() for kw in bark_keywords)
            for name in material_groups.keys()
        )
        if not has_bark_group:
            material_groups[f"{species_name}_bark"] = []

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

        # Classify and add textures (Nanite-compatible: no alpha/translucent/mask)
        EXCLUDED_TEXTURE_TYPES = {"alpha", "translucent", "mask", "opacity"}
        texture_map = {}
        for tex in textures:
            tex_type = classify_texture_from_name(tex.stem)
            if tex_type in EXCLUDED_TEXTURE_TYPES:
                continue
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


def process_twig_file(
    blend_file,
    output_dir,
    formats,
    species_name,
    minimal_export=True,
    include_skeleton=True,
    densify=False,
    alpha_trim_threshold=0.0,
    alpha_trim_method="all",
    smooth_boundary=False,
    smooth_iterations=3,
    smooth_factor=0.5,
    boundary_edge_mm=0.5,
    boundary_band_mm=1.0,
    interior_decimate_ratio=0.0,
):
    """Process a single twig blend file.

    Uses boundary-only densification to preserve interior mesh topology while
    creating high-detail silhouettes for Nanite compatibility.

    Args:
        blend_file: Path to .blend file
        output_dir: Output directory for exported files
        formats: List of export formats
        species_name: Name of species
        minimal_export: If True, creates minimal USD without materials/textures/attributes
        include_skeleton: If True, creates skeletal variant with skeleton
        densify: Master switch for geometry processing. When False, export .blend
            mesh as-is. When True, enables alpha trim, smoothing, and decimation.
        alpha_trim_threshold: Alpha threshold for geometry trimming (0.0 = disabled)
        alpha_trim_method: Trimming method (default: 'all' - conservative)
        smooth_boundary: Enable boundary edge smoothing
        smooth_iterations: Number of smoothing passes
        smooth_factor: Smoothing strength per iteration
        boundary_edge_mm: Target boundary edge length in mm (default: 0.5)
        boundary_band_mm: Distance from silhouette in mm to include (default: 1.0)
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

    # --- Pre-process: join sibling meshes per twig variant ---
    # Each .blend file contains twig variants (e.g., BeechTwigC, BeechTwigD).
    # Each variant has child meshes: BeechTwigs (bark) + BeechLeaves (leaves).
    # Join siblings into a single mesh with bark/leaf material distinction
    # so that the exported USDA preserves both material bindings.
    from collections import defaultdict

    _BARK_OBJ_KW = ["twig", "bark", "wood", "branch", "stem"]

    # Separate leaf-level meshes (no mesh children) from parent containers
    leaf_meshes = []
    parents_with_children = set()
    for obj in mesh_objects:
        if any(c.type == "MESH" for c in obj.children):
            parents_with_children.add(obj.name)
        else:
            leaf_meshes.append(obj)

    # Build collection type lookup (End -> apical, Side -> lateral, etc.)
    _TYPE_KEYWORDS = {
        "End": ["end", "apical", "long", "terminal", "tip"],
        "Side": ["side", "lateral", "short"],
        "Upward": ["upward", "up"],
        "Dead": ["dead", "fall", "winter", "bare"],
    }
    obj_collection_type = {}
    for coll in bpy.data.collections:
        coll_lower = coll.name.lower()
        coll_type = ""
        for type_label, keywords in _TYPE_KEYWORDS.items():
            if any(kw in coll_lower for kw in keywords):
                coll_type = type_label
                break
        if coll_type:
            for o in coll.all_objects:
                obj_collection_type[o.name] = coll_type

    # Group leaf meshes by direct parent
    parent_groups = defaultdict(list)
    for obj in leaf_meshes:
        key = obj.parent.name if obj.parent else obj.name
        parent_groups[key].append(obj)

    joined_objects = []
    for parent_name, siblings in parent_groups.items():
        if len(siblings) <= 1:
            obj = siblings[0]
            # Rename to parent for variant letter detection
            if obj.parent:
                coll_type = obj_collection_type.get(
                    obj.parent.name, obj_collection_type.get(obj.name, "")
                )
                new_name = obj.parent.name
                if coll_type and "Twig" in new_name:
                    new_name = new_name.replace("Twig", f"{coll_type}Twig", 1)
                obj.name = new_name
            joined_objects.append(obj)
            continue

        # Multiple siblings: assign bark/leaf materials from object names, then join
        species_lower = species_name.lower().replace(" ", "_")
        bark_mat = bpy.data.materials.new(name=f"{species_lower}_bark")
        leaf_mat = bpy.data.materials.new(name=f"{species_lower}_leaf")

        for sib in siblings:
            sib.data.materials.clear()
            if any(kw in sib.name.lower() for kw in _BARK_OBJ_KW):
                sib.data.materials.append(bark_mat)
            else:
                sib.data.materials.append(leaf_mat)
            for poly in sib.data.polygons:
                poly.material_index = 0

        bpy.ops.object.select_all(action="DESELECT")
        for sib in siblings:
            sib.select_set(True)
        bpy.context.view_layer.objects.active = siblings[0]
        bpy.ops.object.join()

        joined = bpy.context.view_layer.objects.active

        # Inject collection type into name for standardization
        coll_type = obj_collection_type.get(parent_name, "")
        new_name = parent_name
        if coll_type and "Twig" in new_name:
            new_name = new_name.replace("Twig", f"{coll_type}Twig", 1)
        joined.name = new_name
        joined_objects.append(joined)

    mesh_objects = joined_objects

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

            # Insert _foliage after species name but before variant/type
            # Example: western_red_cedar_foliage_apical (not western_red_cedar_apical)
            parts = standardized_name.split("_")

            # Find species name end (before type keywords or variant letters)
            species_parts = []
            for i, part in enumerate(parts):
                if part in ["apical", "lateral", "upward", "dead", "summer"] or (
                    len(part) == 1 and part in "abcde"
                ):
                    # Insert foliage before this position
                    species_parts.append("foliage")
                    species_parts.extend(parts[i:])
                    break
                species_parts.append(part)
            else:
                # No type found, append foliage at end
                species_parts.append("foliage")

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
            # densify acts as master switch: when False, export original .blend mesh as-is
            interior_decimate = 0.0 < interior_decimate_ratio < 1.0
            if densify:
                # Validate textures before geometry processing
                # Textures should have been standardized during asset preparation
                from growpy.io.texture_utils import validate_twig_textures

                is_valid, validation_msg = validate_twig_textures(blend_dir)
                if not is_valid:
                    logger.warning("%s", validation_msg)
                    logger.warning("Geometry processing may produce suboptimal results")

                leaf_mats = _detect_leaf_material_indices(obj)
                tex_map = _gather_texture_candidates(
                    blend_dir, standardized_name, species_name, metadata
                )

                # Get best alpha source: dedicated alpha/translucent texture, or diffuse embedded alpha
                alpha_tex_path, use_luminance = _get_alpha_texture_for_geometry(tex_map)

                # Load alpha image from best available source
                alpha_img = None
                if alpha_tex_path:
                    try:
                        from PIL import Image as PILImage

                        if use_luminance:
                            # Dedicated alpha/translucent texture - use as grayscale
                            img = PILImage.open(alpha_tex_path)
                            alpha_img = img.convert("L") if img.mode != "L" else img
                        else:
                            # Diffuse texture - extract embedded alpha channel
                            img = PILImage.open(alpha_tex_path)
                            if "A" in img.getbands():
                                alpha_img = img.getchannel("A")
                    except Exception as e:
                        alpha_img = None

                # INTERLEAVED DENSIFY + TRIM - new algorithm that subdivides
                # only transition edges and trims faces each iteration
                if (
                    densify
                    and leaf_mats
                    and alpha_img is not None
                    and alpha_trim_threshold > 0.0
                ):
                    densify_and_trim_interleaved(
                        obj,
                        material_indices=leaf_mats,
                        alpha_img=alpha_img,
                        threshold=alpha_trim_threshold,
                        target_edge_factor=boundary_edge_mm,
                        max_iterations=15,
                        method=alpha_trim_method,
                    )
                elif alpha_trim_threshold > 0.0 and leaf_mats and alpha_tex_path:
                    # Fallback: just trim without densification
                    trim_by_alpha_mask(
                        obj,
                        str(alpha_tex_path),
                        alpha_trim_threshold,
                        require_alpha_channel=(not use_luminance),
                        material_indices=leaf_mats,
                        allow_luminance_for_masks=use_luminance,
                        method=alpha_trim_method,
                    )

                # 3) Cleanup tiny spikes along the trimmed boundary
                if alpha_trim_threshold > 0.0 and leaf_mats and alpha_tex_path:
                    try:
                        _cleanup_boundary_spikes(
                            obj,
                            leaf_mats,
                            iterations=2,
                            area_factor=0.2,
                            short_len_factor=0.25,
                            angle_deg=55.0,
                        )
                    except Exception:
                        pass

                # 4) Smooth boundary edges to follow texture curves more naturally
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
                                boundary_rings=1,
                            )
                        except Exception:
                            pass

                # 5) Interior decimation - simplify leaf interiors, protect branches
                if interior_decimate:
                    try:
                        _apply_interior_decimate(
                            obj,
                            ratio=interior_decimate_ratio,
                            boundary_rings=1,
                        )
                    except Exception:
                        pass

                # Recalculate normals
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.normals_make_consistent(inside=False)
                bpy.ops.object.mode_set(mode="OBJECT")

            # Save per-face material mapping for downstream OBJ simplification
            # Must happen AFTER all geometry processing so face indices match exported USD
            _save_face_material_sidecar(obj, output_dir, standardized_name)

            bpy.ops.object.select_all(action="DESELECT")
            mount_point.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = mount_point

            # Export in requested formats
            for fmt in formats:
                if fmt in ["usd", "usda", "usdc"]:
                    # Export skeletal mesh variant (using _skeletal to match tree convention)
                    skel_export_path = (
                        output_dir / f"{standardized_name}_skeletal.{fmt}"
                    )

                    # CRITICAL: Export UVs only (no materials from Blender)
                    # Materials will be added later with only opaque textures (no alpha/translucent)
                    export_success = False

                    # Try Blender's USD export operator first
                    try:
                        result = bpy.ops.wm.usd_export(
                            filepath=str(skel_export_path),
                            selected_objects_only=True,
                            export_materials=False,
                            export_uvmaps=True,  # CRITICAL: Required for texture mapping
                            export_normals=True,
                            export_mesh_colors=False,
                            use_instancing=False,
                            evaluation_mode="RENDER",
                            generate_preview_surface=False,
                            relative_paths=True,
                            export_hair=False,
                            export_lights=False,
                        )
                        if result == {"FINISHED"}:
                            export_success = True
                        else:
                            logger.warning(
                                "Blender USD export operator returned: %s", result
                            )
                    except Exception as export_err:
                        logger.warning(
                            "Blender USD export operator failed: %s", export_err
                        )

                    if export_success:
                        exported_files.append(skel_export_path)
                    else:
                        logger.error(
                            "Skeletal USD export failed for %s", skel_export_path
                        )

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
                                        mesh_object_name=original_name,
                                    )

                                    stage.Save()
                        except Exception:
                            pass
                    else:
                        pass

                    # Export static mesh variant (always created alongside skeletal)
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
                    static_export_success = False

                    # Try Blender's USD export operator first
                    try:
                        result = bpy.ops.wm.usd_export(
                            filepath=str(static_export_path),
                            selected_objects_only=True,
                            export_materials=True,
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
                        if result == {"FINISHED"}:
                            static_export_success = True
                        else:
                            logger.warning(
                                "Blender USD export operator returned: %s", result
                            )
                    except Exception as export_err:
                        logger.warning(
                            "Blender USD export operator failed: %s", export_err
                        )

                    if static_export_success:
                        exported_files.append(static_export_path)
                    else:
                        logger.error(
                            "Static USD export failed for %s", static_export_path
                        )

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
            logger.error("Failed to export %s: %s", original_name, e, exc_info=True)
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
        # Standardized files use snake_case with full standardized name (e.g., european_beech_foliage_alpha.jpg)
        textures_dir = output_dir / "textures"
        if textures_dir.exists() and not include_skeleton:
            # Only clean up non-standardized textures if we just created standardized ones
            for tex_file in textures_dir.glob("*"):
                if not tex_file.is_file():
                    continue

                # Keep only files matching standardized naming pattern
                # Format: {species_name}_foliage_{texture_type}.{ext}
                # Remove files with CamelCase or non-standardized names
                filename = tex_file.stem

                # Check if this is a standardized name (contains species + _foliage_)
                species_lower = species_name.lower().replace(" ", "_")
                is_standardized = (
                    filename.startswith(species_lower)
                    and "_foliage_" in filename.lower()
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
