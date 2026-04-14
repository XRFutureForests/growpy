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
        json.dump(
            {"materials": mat_names, "face_material_indices": face_mat_indices}, f
        )


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


from .twig_geometry import (  # noqa: F401
    _apply_interior_decimate,
    _cleanup_boundary_spikes,
    _get_alpha_texture_for_geometry,
    _smooth_boundary_edges,
    apply_normal_displacement,
    densify_and_trim_interleaved,
    densify_mesh,
    densify_mesh_to_target_edge,
    trim_by_alpha_mask,
)


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
            from growpy.io.usd.texture_utils import bump_to_normal

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
    interior_edge_mm=0.0,
    interior_boundary_rings=1,
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
        boundary_edge_mm: Target boundary edge length in millimeters (default: 0.5).
            Edges longer than this are split at midpoint during densification.
            Absolute unit ensures consistent output regardless of input mesh resolution.
        boundary_band_mm: Distance from silhouette in mm to include (default: 1.0)
        interior_decimate_ratio: Fallback decimation ratio for interior faces (0-1).
            Ignored when interior_edge_mm > 0.
        interior_edge_mm: Target interior edge length in millimeters (default: 0).
            When > 0, derives the decimation ratio automatically so interior
            faces converge to this edge size. 0 = disabled (uses ratio instead).
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
    exported_names: set = set()

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

            # Deduplicate: append letter suffix when multiple objects in one
            # .blend file resolve to the same standardized name.
            # Uses letters (a-z) to match Grove's variant naming convention
            # and skips letters already taken by naturally-named variants.
            if standardized_name in exported_names:
                for suffix in "abcdefghijklmnopqrstuvwxyz":
                    candidate = f"{standardized_name}_{suffix}"
                    if candidate not in exported_names:
                        standardized_name = candidate
                        break
            exported_names.add(standardized_name)

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
            interior_decimate = (
                0.0 < interior_decimate_ratio < 1.0
            ) or interior_edge_mm > 0
            if densify:
                # Validate textures before geometry processing
                # Textures should have been standardized during asset preparation
                from growpy.io.usd.texture_utils import validate_twig_textures

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
                        boundary_edge_mm=boundary_edge_mm,
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
                    _apply_interior_decimate(
                        obj,
                        ratio=interior_decimate_ratio,
                        boundary_rings=interior_boundary_rings,
                        interior_edge_mm=interior_edge_mm,
                    )

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
