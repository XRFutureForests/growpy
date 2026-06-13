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
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

import bmesh
import bpy

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


from .mesh_export import export_blender_mesh_to_usd  # noqa: F401  (re-exported for API/tests)
from .material_texture import (  # noqa: F401  (classify_texture_from_name re-exported)
    _add_twig_material,
    classify_texture_from_name,
    copy_opaque_textures_for_skeletal,
    setup_materials_with_textures,
)

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
        UsdGeom.Xform.Define(stage, root_path)

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
            stage.DefinePrim(new_materials_path, "Scope")

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

    except Exception:
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
        # (Material copying intentionally omitted: materials, textures, and masks
        # cause import failures with skeletal Nanite assemblies and are configured
        # in Unreal Engine after import.)

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

    except Exception:
        return False


from growpy.utils.naming import standardize_twig_name  # noqa: E402


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
    material_indices: set[int] | None = None,
):
    """Smooth selected (leaf) regions to reduce faceting from low-poly meshes.

    Uses Laplacian smoothing limited to vertices belonging to faces with
    material indices in `material_indices`. If `material_indices` is None,
    applies to the whole mesh.
    """
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
    _get_alpha_texture_for_geometry,
    apply_normal_displacement,
    cut_along_alpha_contour,
    densify_mesh,
    densify_mesh_to_target_edge,
    trim_by_alpha_mask,
)


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
            mesh as-is. When True, enables pre-densification, alpha contour cut,
            and interior decimation.
        alpha_trim_threshold: Alpha threshold for geometry trimming (0.0 = disabled)
        alpha_trim_method: Fallback trim method used only when the alpha image
            cannot be loaded (default: 'all' - conservative)
        boundary_edge_mm: Target leaf edge length in millimeters for pre-densification
            before the alpha contour cut (default: 0.5). Smaller values = denser
            mesh and finer Nanite detail; larger values = faster export, coarser mesh.
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
                    except Exception:
                        alpha_img = None

                # DENSIFY + CONTOUR CUT: first subdivide leaf edges to the
                # target length so the alpha silhouette has mixed (opaque/
                # transparent) edges to cut through. Grove meshes can be as
                # coarse as one quad per needle, leaving the contour cut
                # nothing to bite without pre-densification.
                # Then carve the exact alpha=threshold silhouette in one pass:
                # one new vertex per mixed edge, 3D position lerped, UVs
                # lerped per face so the texture mapping is preserved without
                # distortion. No boundary smoothing or spike cleanup needed.
                if (
                    densify
                    and leaf_mats
                    and alpha_img is not None
                    and alpha_trim_threshold > 0.0
                ):
                    densify_mesh_to_target_edge(
                        obj,
                        target_edge_mm=boundary_edge_mm,
                        material_indices=leaf_mats,
                        max_iterations=8,
                    )
                    cut_along_alpha_contour(
                        obj,
                        material_indices=leaf_mats,
                        alpha_img=alpha_img,
                        threshold=alpha_trim_threshold,
                    )
                elif alpha_trim_threshold > 0.0 and leaf_mats and alpha_tex_path:
                    # Fallback: face-level trim when alpha image couldn't be loaded
                    trim_by_alpha_mask(
                        obj,
                        str(alpha_tex_path),
                        alpha_trim_threshold,
                        require_alpha_channel=(not use_luminance),
                        material_indices=leaf_mats,
                        allow_luminance_for_masks=use_luminance,
                        method=alpha_trim_method,
                    )

                # Interior decimation - simplify leaf interiors, protect branches
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
                        copy_opaque_textures_for_skeletal(
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
                    setup_materials_with_textures(
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
    except Exception:
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
