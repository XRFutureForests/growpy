"""Tree export functionality for USD format with skeletal animation support.

This module handles USD tree export by merging functionality from blender_export
and usd_builder. It provides direct Grove model to USD conversion with proper
skeleton integration, material binding, and Nanite Assembly support.

Key Features:
- Direct Grove model to USD export without coordinate transformations
- Skeletal animation support with UsdSkel hierarchy
- Twig placement data preservation via primvars
- Material and texture binding
- Nanite Assembly creation for Unreal Engine 5.7+

Exported Grove Model Attributes (as USD primvars):
- All face_attribute_* exported as uniform primvars (per-face):
  * branch_id, branch_id_parent, tree_id
  * twig_long, twig_short, twig_upward, twig_dead
  * dead, end, direction
- All point_attribute_* exported as vertex primvars (per-vertex):
  * age, mass, thickness, orientation, pitch
  * vigor, shade, photosynthesis
  * bone_id, skeleton_joint_id
- Alternative twig placement methods (not currently exported):
  * model.get_twig_locations()
  * model.get_twig_orientations()
  * model.get_twig_directions()

Exported Skeleton Attributes:
- Skeleton points, poly_lines, location
- Skeleton attributes: branch_id, point_age, point_mass, point_radius
- Advanced bones from grove.tag_bone_id()

Grove-Level Attributes (not exported to USD):
- grove.total_mass - Total mass of all trees
- grove.number_of_branches - Total branch count
- grove.height - Maximum tree height
- grove.age - Grove age in flushes
- grove.roots - Root system geometry (if grown with grow_roots/build_roots)

Main Functions:
- build_tree_mesh(): Build USD mesh from Grove model (formerly build_tree_usd)
- add_skeleton_to_usd(): Add skeleton to existing USD file
- add_twig_skeleton_to_usd(): Add simple skeleton for twig meshes
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from ...utils.pxr_init import ensure_pxr_with_unreal_schema

logger = logging.getLogger(__name__)

ensure_pxr_with_unreal_schema()

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

from ...config import get_config
from ...constants import BREAST_HEIGHT_METERS


def build_tree_mesh(
    model: Any,
    skeleton: Any | None,
    output_path: Path,
    bones_info: list | None = None,
    up_axis: str = "Z",
    triangulated: bool = True,
    include_materials: bool = False,
    clean_export: bool = True,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
    species_name: str | None = None,
    tree_id: str | None = None,
    include_skeleton: bool = True,
    include_grove_attributes: bool = False,
    radial_scale: float = 1.0,
    scaled_points_out: list | None = None,
) -> bool:
    """Build USD file directly from Grove model using API geometry data.

    This unified function handles both skeletal and static mesh export.
    The skeletal approach (include_skeleton=True) is preferred for Nanite assemblies
    due to superior performance in Unreal Engine (60fps with voxelization).

    CRITICAL: The model must be triangulated BEFORE calling this function:
        model.triangulate()

    This ensures that face counts match between geometry and face attributes,
    preventing mismatches in twig placement and material assignment.

    CRITICAL: For skeletal export with proper vertex-to-bone mapping, bones_info must be provided.
    This enables direct vertex-to-bone mapping via model.point_attribute_bone_id.

    Args:
        model: Grove tree model from grove.build_models() - MUST be triangulated first
        skeleton: Optional Grove skeleton from grove.build_skeletons()
        output_path: Path where USD file will be saved
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this tree
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated (should always be True)
        include_materials: If False, creates simple geometry without materials/UVs
        clean_export: If True, creates minimal USD without default attributes (demo mode)
        skeleton_length: Bone length multiplier for skeleton creation (deprecated if bones_info provided)
        skeleton_reduce: Bone reduction factor for skeleton creation (deprecated if bones_info provided)
        skeleton_bias: Weight bias for skinning
        skeleton_connected: Use connected bone hierarchy (deprecated if bones_info provided)
        species_name: Species name for material/texture lookup and prim naming
        tree_id: Tree ID for unique prim naming (e.g., "0004")
        include_skeleton: If True and skeleton provided, add skeleton structure (skeletal mesh)
        include_grove_attributes: If True, add Grove metadata attributes as primvars (for analysis)
        scaled_points_out: Optional mutable list. When provided and radial_scale != 1.0,
            filled with (x, y, z) tuples of the final mesh points in Grove's Y-up
            coordinate space (before USD axis swap). Used by assembly export to
            compute twig face centroids from the scaled mesh.

    Returns:
        bool: True if USD file was created successfully
    """

    try:
        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata
        UsdGeom.SetStageUpAxis(
            stage, UsdGeom.Tokens.z if up_axis == "Z" else UsdGeom.Tokens.y
        )
        stage.SetMetadata("metersPerUnit", 1.0)

        # Store clean_export mode for skeleton addition
        if clean_export:
            stage.SetMetadata("customLayerData", {"clean_export": True})

        # Generate prim names from species for consistent naming convention
        # Uses {species}_stems pattern to match file naming convention
        if species_name:
            sanitized_species = species_name.replace(" ", "_").replace("-", "_").lower()
            root_name = f"{sanitized_species}_stems"
            mesh_name = f"{sanitized_species}_stems_mesh"
        else:
            root_name = "tree"
            mesh_name = "TreeMesh"

        # Define root xform
        root_path = Sdf.Path(f"/{root_name}")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Skip treeLocation metadata for clean export
        # Tree positioning is handled at the assembly level
        if not clean_export and hasattr(model, "location") and model.location:
            loc = model.location
            root_xform.GetPrim().SetCustomDataByKey(
                "treeLocation", Gf.Vec3f(loc.x, loc.y, loc.z)
            )

        # Define mesh with species-specific name
        mesh_path = root_path.AppendChild(mesh_name)
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Extract geometry data from Grove model
        points = model.points  # List of Vector objects with (x, y, z)
        faces = model.faces  # List of face definitions (point indices)
        uvs = model.uvs  # UV coordinates for texturing

        if not points or not faces:
            logger.warning(
                "Model has no geometry (0 points/faces) — skipping USD export"
            )
            return False

        # Convert points to USD format, applying height-aware radial scaling.
        # Corrects Grove's DBH to match yield table targets.
        #
        # Scale factor: distributed across the full tree height so
        # branches scale proportionally with the trunk. Full correction
        # at breast height, 30% correction retained at the crown.
        #
        # Scale direction: at branch-trunk junctions, the scaling axis
        # transitions from the trunk axis (at the connection surface) to
        # the branch axis (further along the branch). This prevents gaps
        # when shrinking — branch-base vertices follow the trunk surface
        # inward rather than collapsing toward their own branch centerline.
        #
        # Requires bones_info + vertex bone IDs; skipped otherwise.
        if (
            radial_scale != 1.0
            and bones_info
            and getattr(model, "point_attribute_bone_id", None)
        ):
            vertex_bone_ids = model.point_attribute_bone_id
            tree_height = max((p.y for p in points), default=0.0)
            breast_height = BREAST_HEIGHT_METERS
            blend_start = breast_height
            blend_end = max(breast_height + 1.0, tree_height * 0.85)
            blend_range = blend_end - blend_start

            # Crown retains 30% of the radial correction so the whole
            # tree thickens/thins proportionally instead of only the base.
            crown_ratio = 0.3
            crown_scale = 1.0 + (radial_scale - 1.0) * crown_ratio

            bone_id_offset = min(vertex_bone_ids)

            # Trunk branch_id = first bone's branch_id (bone index 7)
            trunk_branch_id = int(bones_info[0][7]) if len(bones_info[0]) >= 8 else -1

            # Build per-bone data
            bone_axes = []
            bone_starts = []
            bone_branch_ids = []
            for bone in bones_info:
                sp, ep = bone[2], bone[3]
                dx = ep.x - sp.x
                dy = ep.y - sp.y
                dz = ep.z - sp.z
                length = math.sqrt(dx * dx + dy * dy + dz * dz)
                if length > 1e-6:
                    inv = 1.0 / length
                    bone_axes.append((dx * inv, dy * inv, dz * inv))
                else:
                    bone_axes.append((0.0, 1.0, 0.0))
                bone_starts.append((sp.x, sp.y, sp.z))
                bone_branch_ids.append(
                    int(bone[7]) if len(bone) >= 8 else trunk_branch_id
                )

            # Normalize bone_starts to local space.
            min_z_idx = min(range(len(bone_starts)), key=lambda i: bone_starts[i][2])
            origin_x = bone_starts[min_z_idx][0]
            origin_y = bone_starts[min_z_idx][1]
            origin_z = bone_starts[min_z_idx][2]
            bone_starts = [
                (bx - origin_x, by - origin_y, bz - origin_z)
                for bx, by, bz in bone_starts
            ]

            # Determine which bones are trunk (order 0) vs branch
            is_trunk_bone = [
                bone_branch_ids[i] == trunk_branch_id for i in range(len(bones_info))
            ]

            # For each non-trunk bone, find the parent trunk bone axis
            # so we can blend the scaling direction at junctions.
            # Walk parent chain until we hit a trunk bone.
            parent_trunk_axis: list[tuple[float, float, float] | None] = [None] * len(
                bones_info
            )
            parent_trunk_start: list[tuple[float, float, float] | None] = [None] * len(
                bones_info
            )
            for idx in range(len(bones_info)):
                if is_trunk_bone[idx]:
                    continue
                cur = idx
                visited = set()
                while cur >= 0 and cur not in visited:
                    visited.add(cur)
                    parent_global = bones_info[cur][1]
                    parent_local = parent_global - bone_id_offset
                    if parent_local < 0 or parent_local >= len(bones_info):
                        break
                    if is_trunk_bone[parent_local]:
                        parent_trunk_axis[idx] = bone_axes[parent_local]
                        parent_trunk_start[idx] = bone_starts[parent_local]
                        break
                    cur = parent_local

            # Cumulative bone-chain distance from the first non-trunk bone
            # (branch root) to each bone along the branch. Used to blend
            # the scaling axis from trunk direction to branch direction.
            branch_root_of = {}
            for idx in range(len(bones_info)):
                if is_trunk_bone[idx] or parent_trunk_axis[idx] is None:
                    continue
                # Walk parent chain to find first non-trunk bone (root)
                cur = idx
                visited = set()
                root = idx
                while cur >= 0 and cur not in visited:
                    visited.add(cur)
                    parent_global = bones_info[cur][1]
                    parent_local = parent_global - bone_id_offset
                    if parent_local < 0 or parent_local >= len(bones_info):
                        break
                    if is_trunk_bone[parent_local]:
                        root = cur
                        break
                    root = parent_local
                    cur = parent_local
                branch_root_of[idx] = root

            junction_chain_dist = {}
            for idx in branch_root_of:
                root = branch_root_of[idx]
                if idx == root:
                    junction_chain_dist[idx] = 0.0
                else:
                    dist = 0.0
                    cur = idx
                    visited = set()
                    while cur != root and cur >= 0 and cur not in visited:
                        visited.add(cur)
                        parent_global = bones_info[cur][1]
                        parent_local = parent_global - bone_id_offset
                        if parent_local < 0 or parent_local >= len(bones_info):
                            break
                        csx, csy, csz = bone_starts[cur]
                        cpx, cpy, cpz = bone_starts[parent_local]
                        ddx, ddy, ddz = csx - cpx, csy - cpy, csz - cpz
                        dist += math.sqrt(ddx * ddx + ddy * ddy + ddz * ddz)
                        cur = parent_local
                    junction_chain_dist[idx] = dist

            # Distance over which the scaling axis transitions from trunk
            # to branch direction. Must exceed trunk radius so surface
            # vertices at the junction follow the trunk surface.
            axis_blend_dist = 0.5

            usd_points = []
            for i, p in enumerate(points):
                local_idx = vertex_bone_ids[i] - bone_id_offset
                local_idx = max(0, min(local_idx, len(bone_axes) - 1))

                # Height-based scale: radial_scale at breast height,
                # blending to crown_scale at blend_end. crown_scale
                # keeps partial correction so branches don't appear
                # under/oversized relative to the trunk.
                if p.y <= blend_start:
                    s = radial_scale
                elif p.y >= blend_end:
                    s = crown_scale
                else:
                    t = (p.y - blend_start) / blend_range
                    t = t * t * (3.0 - 2.0 * t)
                    s = radial_scale + (crown_scale - radial_scale) * t

                if abs(s - 1.0) < 1e-6:
                    usd_points.append(Gf.Vec3f(p.x, p.y, p.z))
                    continue

                # Determine scaling axis and reference point.
                # Trunk bones: use own axis directly.
                # Branch bones near junction: blend from trunk axis to
                # branch axis so vertices at the connection surface move
                # with the trunk rather than toward the branch centerline.
                if (
                    not is_trunk_bone[local_idx]
                    and parent_trunk_axis[local_idx] is not None
                ):
                    chain_d = junction_chain_dist.get(local_idx, 0.0)
                    jax, jay, jaz = bone_axes[local_idx]
                    jsx, jsy, jsz = bone_starts[local_idx]
                    along = max(
                        0.0,
                        (p.x - jsx) * jax + (p.y - jsy) * jay + (p.z - jsz) * jaz,
                    )
                    dist_along = chain_d + along
                    if dist_along >= axis_blend_dist:
                        # Far enough from junction — use branch axis
                        ax, ay, az = jax, jay, jaz
                        bx, by, bz = jsx, jsy, jsz
                    else:
                        # Blend axis: trunk axis -> branch axis
                        at = dist_along / axis_blend_dist
                        at = at * at * (3.0 - 2.0 * at)
                        pt_axis = parent_trunk_axis[local_idx] or (0.0, 1.0, 0.0)
                        pt_start = parent_trunk_start[local_idx] or (0.0, 0.0, 0.0)
                        tax, tay, taz = pt_axis
                        ax = tax + (jax - tax) * at
                        ay = tay + (jay - tay) * at
                        az = taz + (jaz - taz) * at
                        ln = math.sqrt(ax * ax + ay * ay + az * az)
                        if ln > 1e-6:
                            inv_ln = 1.0 / ln
                            ax *= inv_ln
                            ay *= inv_ln
                            az *= inv_ln
                        # Blend reference point: trunk start -> bone start
                        tbx, tby, tbz = pt_start
                        bx = tbx + (jsx - tbx) * at
                        by = tby + (jsy - tby) * at
                        bz = tbz + (jsz - tbz) * at
                else:
                    ax, ay, az = bone_axes[local_idx]
                    bx, by, bz = bone_starts[local_idx]

                vx, vy, vz = p.x - bx, p.y - by, p.z - bz
                dot = vx * ax + vy * ay + vz * az
                px, py, pz = vx - dot * ax, vy - dot * ay, vz - dot * az
                usd_points.append(
                    Gf.Vec3f(
                        p.x + (s - 1.0) * px,
                        p.y + (s - 1.0) * py,
                        p.z + (s - 1.0) * pz,
                    )
                )
        else:
            usd_points = [Gf.Vec3f(p.x, p.y, p.z) for p in points]

        # Export scaled vertex positions for twig face centroid computation.
        # Assembly export uses these to place twigs on the already-scaled mesh
        # instead of applying a separate radial transform.
        if scaled_points_out is not None and radial_scale != 1.0:
            scaled_points_out.extend((pt[0], pt[1], pt[2]) for pt in usd_points)

        # Convert faces to USD format
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = []
        for face in faces:
            face_vertex_indices.extend(face)

        # Set mesh topology
        mesh.CreatePointsAttr(usd_points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Add UVs for texture mapping
        # CRITICAL: UVs are required for bark textures to display correctly
        if uvs and len(uvs) > 0:
            primvars_api = UsdGeom.PrimvarsAPI(mesh)

            # Convert Grove UVs to USD format
            # Grove UVs are tuples (u, v)
            usd_uvs = [Gf.Vec2f(uv[0], uv[1]) for uv in uvs]

            # Create UV primvar with faceVarying interpolation
            # faceVarying means one UV per face-vertex (matches face_vertex_indices)
            uv_primvar = primvars_api.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
            )
            uv_primvar.Set(usd_uvs)

        # Add all model attributes from Grove (face and point attributes)
        # These provide rich data for analysis but add ~70% file size
        # Only include when explicitly requested for R&D/debugging
        if include_grove_attributes:
            _add_model_attributes(mesh, model)

        # Skip UV island metadata for clean export
        # UV data is included in the mesh but metadata is not needed for Nanite assembly
        if not clean_export and hasattr(model, "uv_islands") and model.uv_islands:
            # Store count and structure info as metadata
            mesh.GetPrim().SetCustomDataByKey("uvIslandCount", len(model.uv_islands))
            # Note: Full island data available but not stored to keep file size reasonable
            # Can be accessed via model.uv_islands or model.get_uv_islands_flat() if needed

        # Add normals for proper Unreal rendering (skip for clean export)
        _add_mesh_normals(mesh, model, clean_export=clean_export)

        # Add skeleton if provided and enabled (skeletal mesh export)
        if skeleton is not None and include_skeleton:
            skeleton_added = _add_skeleton_to_stage_inline(
                stage=stage,
                skeleton=skeleton,
                root_xform_prim=root_xform.GetPrim(),
                mesh_prim=mesh.GetPrim(),
                model=model,
                bones_info=bones_info,
                skeleton_length=skeleton_length,
                skeleton_reduce=skeleton_reduce,
                skeleton_bias=skeleton_bias,
                skeleton_connected=skeleton_connected,
                clean_export=clean_export,
                junction_blend_distance=junction_blend_distance,
                blend_mode=blend_mode,
            )
            if skeleton_added:
                pass
            else:
                pass

        # Add materials to mesh (required for Nanite assembly recognition)
        # Materials are created as siblings to TreeMesh inside /tree root
        _add_skeletal_materials(stage, mesh.GetPrim(), str(root_path), species_name)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        logger.error("USD export failed: %s", e, exc_info=True)
        return False


def strip_skeleton_from_usd(skeletal_path: Path, static_path: Path) -> bool:
    """Derive a static mesh USDA from a skeletal USDA by removing skeleton prims.

    Copies the skeletal file and strips all UsdSkel-related prims, properties,
    and API schemas. Much faster than re-running build_tree_mesh() since it only
    manipulates the USD scene graph without recomputing geometry.

    Args:
        skeletal_path: Path to source skeletal USDA file
        static_path: Path for output static USDA file
    """
    import shutil

    shutil.copy2(skeletal_path, static_path)

    layer = Sdf.Layer.FindOrOpen(str(static_path))
    if not layer or not layer.rootPrims:
        logger.warning("strip_skeleton: cannot open %s", static_path)
        return False

    root_spec = layer.rootPrims[0]

    # Change root type from SkelRoot to Xform
    if root_spec.typeName == "SkelRoot":
        root_spec.typeName = "Xform"

    # Remove SkelBindingAPI from root apiSchemas
    _remove_api_schema(root_spec, "SkelBindingAPI")

    # Find and remove the skeleton child prim, and strip skel properties from
    # the mesh. SdfChildrenView iteration yields child PrimSpec values (not
    # names) on the bundled USD build, so use each item directly and delete by
    # its name rather than indexing the view with a PrimSpec.
    skel_child = None
    mesh_child = None
    for child in root_spec.nameChildren:
        child_spec = (
            child if isinstance(child, Sdf.PrimSpec) else root_spec.nameChildren[child]
        )
        if child_spec.typeName == "Skeleton":
            skel_child = child_spec
        elif child_spec.typeName == "Mesh":
            mesh_child = child_spec

    if skel_child is not None:
        del root_spec.nameChildren[skel_child.name]

    if mesh_child:
        _remove_api_schema(mesh_child, "SkelBindingAPI")
        for prop_name in list(mesh_child.properties.keys()):
            if prop_name.startswith("skel:"):
                del mesh_child.properties[prop_name]

    # Remove skel:skeleton relationship from root if present
    for prop_name in list(root_spec.properties.keys()):
        if prop_name.startswith("skel:"):
            del root_spec.properties[prop_name]

    layer.Save()
    logger.debug("Derived static mesh: %s", static_path.name)
    return True


def is_bone_limit_error(error: ValueError) -> bool:
    """Check if a ValueError is about exceeding Unreal's bone limit."""
    msg = str(error)
    return "bones" in msg and "limit" in msg


def handle_bone_limit_error(error: ValueError) -> None:
    """Print actionable guidance for bone limit errors and exit."""
    logger.error("\nERROR: %s", error)
    logger.error(
        "\nTo reduce bone count, try one or more of:\n"
        "  CLI arguments:\n"
        "    --skeleton-reduce 0.6    (skip thin branches, most effective, range 0.0-1.0)\n"
        "    --skeleton-length 3.0    (merge nodes into longer bones, range 0.0-5.0)\n"
        "    --quality performance    (use a lower quality preset)\n"
        "  Config (config/forest.toml [forest.skeleton]):\n"
        "    reduce = 0.6\n"
        "    length = 3.0"
    )
    raise SystemExit(1) from error


def derive_static_from_skeletal(
    tree_dir: Path,
    species_clean: str,
    species_name: str,
    tree_id,
    model,
    twig_usd_map: dict,
    skip_validation: bool = False,
    stems_suffix: str = "",
    twig_placements=None,
    instances_dir: Path | None = None,
) -> str | None:
    """Derive a static mesh assembly from an existing skeletal one.

    Strips skeleton prims from a copy of the skeletal stems file,
    then creates a static assembly referencing the stripped stems.
    Returns the static assembly path string, or None on failure.
    """
    from .assembly_export import create_assembly

    ext = get_config().usd_ext
    suffix = f"_{stems_suffix}" if stems_suffix else ""
    skeletal_stems = tree_dir / f"{species_clean}{suffix}_stems_skeletal{ext}"
    static_stems = tree_dir / f"{species_clean}{suffix}_stems_static{ext}"

    if not skeletal_stems.exists():
        logger.warning(
            "Cannot derive static: skeletal stems not found: %s", skeletal_stems
        )
        return None

    if not strip_skeleton_from_usd(skeletal_stems, static_stems):
        return None

    if twig_placements is None:
        from ...core.twig import extract_twig_placements_from_model

        try:
            twig_placements = extract_twig_placements_from_model(model)
        except Exception as e:
            logger.warning(
                "Failed to extract twig placements for static derivation: %s", e
            )

    static_assembly = tree_dir / f"{species_clean}{suffix}_assembly_static{ext}"
    create_assembly(
        tree_usd_path=static_stems,
        output_path=static_assembly,
        species_name=species_name,
        tree_id=tree_id,
        twig_usd_paths=twig_usd_map,
        use_skeletal_mesh=False,
        twig_placements=twig_placements,
        validate=not skip_validation,
        instances_dir=instances_dir,
    )
    return str(static_assembly)


def _remove_api_schema(prim_spec, schema_name: str) -> None:
    """Remove an API schema from a PrimSpec's apiSchemas metadata."""
    api_schemas = prim_spec.GetInfo("apiSchemas")
    if not api_schemas:
        return
    prepended = list(api_schemas.prependedItems)
    if schema_name in prepended:
        prepended.remove(schema_name)
        new_schemas = Sdf.TokenListOp()
        new_schemas.prependedItems = prepended
        prim_spec.SetInfo("apiSchemas", new_schemas)


# Helper functions for internal use


def _add_skeleton_to_stage_inline(
    stage: Usd.Stage,
    skeleton: Any,
    root_xform_prim: Usd.Prim,
    mesh_prim: Usd.Prim,
    model: Any | None = None,
    bones_info: list | None = None,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    clean_export: bool = True,
    junction_blend_distance: float = 0.1,
    blend_mode: str = "linear",
) -> bool:
    """Add skeleton to open USD stage using Grove's skeleton data.

    CRITICAL: If bones_info is provided, it will be used for direct vertex-to-bone mapping
    via model.point_attribute_bone_id. This is the preferred method as it uses Grove's
    internal mapping rather than distance calculations.

    Args:
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this tree
                   If provided, enables direct vertex-to-bone mapping
    """
    try:
        if not skeleton:
            return False

        # Create UsdSkel skeleton structure directly in the stage
        # Pass bones_info for direct vertex-to-bone mapping with junction blending
        _build_usdskel_from_bones(
            stage,
            skeleton,
            model,
            bones_info,
            clean_export=clean_export,
            verbose=False,  # Set to True for debugging
            junction_blend_distance=junction_blend_distance,
            blend_mode=blend_mode,
        )

        return True

    except Exception as e:
        logger.warning("Tree USD export failed: %s", e)
        return False


def add_nanite_attributes_to_usd(usd_path: Path, is_foliage: bool = False) -> bool:
    """Add Nanite-specific USD attributes to exported USD file.

    Args:
        usd_path: Path to USD file
        is_foliage: Whether this is foliage (twigs/leaves) requiring Preserve Area

    Returns:
        bool: Success status
    """
    try:
        # Open USD stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Add Nanite attributes to all meshes
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                # Enable Nanite
                prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set(
                    "enable"
                )

                # For foliage, enable Preserve Area
                if is_foliage:
                    prim.CreateAttribute(
                        "unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool
                    ).Set(True)

        # Save changes
        stage.GetRootLayer().Save()
        return True

    except Exception as e:
        logger.warning("Failed to add Nanite attributes to %s: %s", usd_path, e)
        return False


def _add_model_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add all Grove model attributes as USD primvars.

    Dynamically discovers and adds all face_attribute_* and point_attribute_*
    from the model, handling different attribute types automatically.

    Face attributes are added with 'uniform' interpolation (per-face).
    Point attributes are added with 'vertex' interpolation (per-vertex).

    Skeleton-related attributes (bone_id, skeleton_joint_id) are skipped
    as they're handled separately during skeleton binding.
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Mapping of attribute value types to USD types
    def get_usd_type(attr_value):
        """Determine USD value type from Python attribute."""
        if not attr_value or len(attr_value) == 0:
            return None

        sample = attr_value[0]
        if isinstance(sample, bool):
            return Sdf.ValueTypeNames.BoolArray
        elif isinstance(sample, int):
            return Sdf.ValueTypeNames.IntArray
        elif isinstance(sample, float):
            return Sdf.ValueTypeNames.FloatArray
        elif isinstance(sample, (tuple, list)) and len(sample) == 3:
            # Vector3 type
            return Sdf.ValueTypeNames.Float3Array
        else:
            # Default to float for unknown types
            return Sdf.ValueTypeNames.FloatArray

    # Get all attribute names from model
    model_attrs = dir(model)

    # Process face attributes (per-face, uniform interpolation)
    face_attrs = [attr for attr in model_attrs if attr.startswith("face_attribute_")]
    for attr_name in sorted(face_attrs):
        try:
            attr_value = getattr(model, attr_name, None)
            if attr_value is None or len(attr_value) == 0:
                continue

            # Convert branch IDs from global to local indices
            # This requires branch_id_offset from skeleton building
            if attr_name in (
                "face_attribute_branch_id",
                "face_attribute_branch_id_parent",
            ):
                # These will be handled separately with proper offset conversion
                # For now, skip them - they'll be added after skeleton building
                continue

            usd_type = get_usd_type(attr_value)
            if usd_type is None:
                continue

            # Convert attribute name to PascalCase for USD
            # e.g., face_attribute_thickness -> Thickness
            primvar_name = "".join(
                word.capitalize()
                for word in attr_name.replace("face_attribute_", "").split("_")
            )

            primvar = primvars_api.CreatePrimvar(
                primvar_name, usd_type, UsdGeom.Tokens.uniform
            )
            primvar.Set(attr_value)

        except Exception as e:
            logger.debug("Skipped face attribute %s: %s", attr_name, e)

    # Process point attributes (per-vertex, vertex interpolation)
    point_attrs = [attr for attr in model_attrs if attr.startswith("point_attribute_")]

    for attr_name in sorted(point_attrs):
        try:
            # Skip bone_id as it's handled separately in skeleton binding
            # The jointIndices primvar will have the local bone indices
            if attr_name == "point_attribute_bone_id":
                continue

            attr_value = getattr(model, attr_name, None)
            if attr_value is None or len(attr_value) == 0:
                continue

            usd_type = get_usd_type(attr_value)
            if usd_type is None:
                continue

            # Convert attribute name to PascalCase for USD
            # e.g., point_attribute_thickness -> Thickness
            primvar_name = "".join(
                word.capitalize()
                for word in attr_name.replace("point_attribute_", "").split("_")
            )

            primvar = primvars_api.CreatePrimvar(
                primvar_name, usd_type, UsdGeom.Tokens.vertex
            )
            primvar.Set(attr_value)

        except Exception as e:
            logger.debug("Skipped point attribute %s: %s", attr_name, e)


def _add_skeletal_materials(
    stage: Usd.Stage,
    mesh_prim: Usd.Prim,
    root_path: str,
    species_name: str | None = None,
) -> None:
    """Add materials with opaque-only textures to skeletal tree mesh for Nanite assembly.

    Creates Materials scope as sibling to TreeMesh inside /tree root,
    matching the structure used in twig files. Includes bark textures for better visuals
    while excluding alpha/translucent textures for Nanite compatibility.

    Args:
        stage: USD stage
        mesh_prim: TreeMesh prim
        root_path: Path to root xform (e.g., "/tree")
        species_name: Optional species name for bark texture lookup
    """
    try:
        # Bark material color (brown) - fallback if no texture
        BARK_BROWN = Gf.Vec3f(0.4, 0.3, 0.2)

        # Create Materials scope as sibling to TreeMesh
        materials_path = root_path + "/Materials"
        UsdGeom.Scope.Define(stage, materials_path)

        # Create bark material with species-specific name for unique Unreal assets
        if species_name:
            safe = species_name.replace(" ", "_").replace("-", "_").lower()
            bark_mat_name = f"{safe}_bark"
        else:
            bark_mat_name = "bark"
        bark_mat = UsdShade.Material.Define(stage, f"{materials_path}/{bark_mat_name}")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/{bark_mat_name}/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")

        # Try to find and add bark texture if available
        # CRITICAL: Only opaque textures for Nanite compatibility
        texture_found = False
        texture_file = None
        normal_texture_file = None
        if species_name:
            from growpy.config.paths import (
                get_bark_normal_texture_path,
                get_bark_texture_path,
            )

            texture_file = get_bark_texture_path(species_name)
            normal_texture_file = get_bark_normal_texture_path(species_name)

            if texture_file and texture_file.exists():
                texture_found = True

                # Create UV reader for texture mapping
                uv_reader = UsdShade.Shader.Define(
                    stage, f"{materials_path}/{bark_mat_name}/uvmap"
                )
                uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
                uv_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
                uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

                # Create diffuse texture reader
                tex_reader = UsdShade.Shader.Define(
                    stage, f"{materials_path}/{bark_mat_name}/DiffuseTexture"
                )
                tex_reader.CreateIdAttr("UsdUVTexture")
                # Use relative path to textures/ subdirectory
                tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    f"./textures/{texture_file.name}"
                )
                tex_reader.CreateInput(
                    "sourceColorSpace", Sdf.ValueTypeNames.Token
                ).Set("sRGB")
                tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect UV reader to texture sampler
                tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                    uv_reader.ConnectableAPI(), "result"
                )

                # Connect texture to shader
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(tex_reader.ConnectableAPI(), "rgb")

                # Add normal map if available
                if normal_texture_file and normal_texture_file.exists():
                    normal_tex_reader = UsdShade.Shader.Define(
                        stage, f"{materials_path}/{bark_mat_name}/NormalTexture"
                    )
                    normal_tex_reader.CreateIdAttr("UsdUVTexture")
                    normal_tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                        f"./textures/{normal_texture_file.name}"
                    )
                    # Normal maps use raw color space (not sRGB)
                    normal_tex_reader.CreateInput(
                        "sourceColorSpace", Sdf.ValueTypeNames.Token
                    ).Set("raw")
                    normal_tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                    # Connect UV reader to normal texture sampler
                    normal_tex_reader.CreateInput(
                        "st", Sdf.ValueTypeNames.Float2
                    ).ConnectToSource(uv_reader.ConnectableAPI(), "result")

                    # Connect normal to shader
                    shader.CreateInput(
                        "normal", Sdf.ValueTypeNames.Normal3f
                    ).ConnectToSource(normal_tex_reader.ConnectableAPI(), "rgb")

        # Fallback to solid color if no texture found
        if not texture_found:
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                BARK_BROWN
            )

        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.5)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)
        bark_mat.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )

        # Apply MaterialBindingAPI to mesh and bind material
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding_api.Bind(bark_mat)

        # Copy texture files to output directory if found
        if texture_found and texture_file:
            from pathlib import Path

            from .texture_utils import copy_and_resize_texture

            # Get output directory from stage
            output_dir = Path(stage.GetRootLayer().realPath).parent

            # Create textures subdirectory (matches twig texture structure)
            textures_dir = output_dir / "textures"
            textures_dir.mkdir(exist_ok=True)

            # Copy diffuse texture file to textures/ subdirectory (power-of-2 for Unreal)
            dest_texture = textures_dir / texture_file.name
            if not dest_texture.exists():
                copy_and_resize_texture(texture_file, dest_texture)

            # Copy normal texture file if available
            if normal_texture_file and normal_texture_file.exists():
                dest_normal = textures_dir / normal_texture_file.name
                if not dest_normal.exists():
                    copy_and_resize_texture(normal_texture_file, dest_normal)

    except Exception:
        # Silently fail - material addition is optional
        pass


def _add_mesh_normals(
    mesh: UsdGeom.Mesh, model: Any, clean_export: bool = True
) -> None:
    """Add normals to mesh for proper Unreal rendering.

    Prefers using actual normals from model.shape if available,
    falls back to simple up-facing normals if not.

    Args:
        clean_export: If True, skip normals entirely (Nanite assemblies don't need them)
    """
    # Skip normals for clean export (reference files don't have them)
    if clean_export:
        return
    try:
        # Try to use real normals from model.shape
        if hasattr(model, "shape") and model.shape:
            # model.shape contains normal vectors for each vertex
            # Convert to USD format
            normals = []
            for normal in model.shape:
                if hasattr(normal, "x"):
                    # Vector object
                    normals.append(Gf.Vec3f(normal.x, normal.y, normal.z))
                elif isinstance(normal, (tuple, list)) and len(normal) == 3:
                    # Tuple/list format
                    normals.append(Gf.Vec3f(normal[0], normal[1], normal[2]))
                else:
                    # Unknown format, skip
                    continue

            if normals:
                normals_attr = mesh.CreateNormalsAttr()
                normals_attr.Set(normals)
                # Use vertex interpolation for per-vertex normals
                mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                return

        # Fallback: create simple per-face normals
        faces = model.faces if hasattr(model, "faces") else []
        if faces:
            # Create up-facing normals for each face
            normals = [Gf.Vec3f(0, 0, 1) for _ in faces]
            normals_attr = mesh.CreateNormalsAttr()
            normals_attr.Set(normals)
            mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

    except Exception:
        logger.warning("USD material/normal addition failed")


def _build_usdskel_from_bones(
    stage: Usd.Stage,
    skeleton: Any,
    model: Any | None = None,
    bones_info: list[tuple] | None = None,
    twig_placements: dict[str, list[dict]] | None = None,
    verbose: bool = False,
    clean_export: bool = True,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
) -> None:
    """Build UsdSkel skeleton from Grove skeleton polylines.

    CRITICAL for Unreal Engine recognition:
    1. SkelRoot MUST have SkelBindingAPI applied
    2. SkelRoot MUST have skel:skeleton relationship pointing to Skeleton prim
    3. Mesh should NOT have any skel:* relationships (those go on SkelRoot only)

    CRITICAL for proper vertex-to-bone mapping:
    - If bones_info is provided AND model has point_attribute_bone_id, uses direct mapping
    - This is the preferred method as it uses Grove's internal vertex-to-bone assignments
    - Falls back to distance-based mapping only if point_attribute_bone_id is unavailable

    Args:
        stage: USD stage to add skeleton to
        skeleton: Grove skeleton object with points and poly_lines
        model: Optional Grove model with point_attribute_bone_id for direct mapping
        bones_info: Optional list of bone tuples from grove.tag_bone_id()
        twig_placements: Optional twig placement data (deprecated)
        verbose: Whether to print debug information
    """
    # Find mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if not mesh_prim:
        return

    # Get root path from mesh parent (supports species-specific naming)
    root_path = mesh_prim.GetPath().GetParentPath()
    tree_prim = stage.GetPrimAtPath(root_path)
    if tree_prim:
        # Redefine as SkelRoot if not already
        if not tree_prim.IsA(UsdSkel.Root):
            skel_root = UsdSkel.Root.Define(stage, root_path)
            tree_prim = skel_root.GetPrim()
    else:
        skel_root = UsdSkel.Root.Define(stage, root_path)
        tree_prim = skel_root.GetPrim()

    # CRITICAL: Apply SkelBindingAPI to SkelRoot using proper metadata
    # This is required for Unreal Engine to recognize the skeletal structure
    api_schemas = tree_prim.GetMetadata("apiSchemas")
    if api_schemas:
        # Append to existing schemas
        if "SkelBindingAPI" not in api_schemas.prependedItems:
            api_schemas.prependedItems.append("SkelBindingAPI")
            tree_prim.SetMetadata("apiSchemas", api_schemas)
    else:
        # Create new TokenListOp
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["SkelBindingAPI"]
        tree_prim.SetMetadata("apiSchemas", api_schemas)

    # Create skeleton as sibling to mesh (both under SkelRoot)
    # Use species-specific skeleton name for unique Unreal assets
    # The skeleton is a child of tree_prim (the SkelRoot)
    tree_prim_path = tree_prim.GetPath()
    tree_prim_name = tree_prim_path.name

    # Derive skeleton name from tree prim name pattern
    if "_" in tree_prim_name and tree_prim_name != "tree":
        # Species-specific naming: common_ash_0007 -> common_ash_0007_skel
        skel_name = f"{tree_prim_name}_skel"
    else:
        skel_name = "TreeSkel"

    skel_path = tree_prim_path.AppendChild(skel_name)
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Build joint hierarchy
    joint_tokens = []
    bind_transforms = []
    rest_transforms = []

    # Get tree offset for local space conversion
    tree_offset = (
        Gf.Vec3d(model.location.x, model.location.y, model.location.z)
        if model and hasattr(model, "location") and model.location
        else Gf.Vec3d(0, 0, 0)
    )

    # Build joint hierarchy from bones_info if available

    # bones_info format: (is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
    # CRITICAL: parent_bone_id values in bones_info are already global bone indices across all trees
    # However, bone indices in the array restart at 0 for each tree

    # Calculate bone ID offset from model's vertex bone IDs
    # The minimum bone_id in the model's vertices tells us the global offset for this tree
    # This is more reliable than checking parent_bone_id which is 0 for all tree roots
    if (
        model
        and hasattr(model, "point_attribute_bone_id")
        and model.point_attribute_bone_id
    ):
        bone_id_offset = min(model.point_attribute_bone_id)
    else:
        # Fallback to old method if no vertex bone IDs available
        first_bone = bones_info[0]
        is_tree_root, parent_bone_id = first_bone[0], first_bone[1]
        if is_tree_root and parent_bone_id == 0:
            bone_id_offset = 0
        elif is_tree_root:
            bone_id_offset = parent_bone_id
        else:
            bone_id_offset = 0

    first_branch_id = bones_info[0][7]  # branch_id from tuple

    # CRITICAL: Filter bones_info to only include bones referenced by mesh vertices
    # This prevents crashes when build_models() was called with cutoff parameters
    # that removed branches (and their vertices) but bones still exist in bones_info
    from ...core.skeleton import filter_bones_for_mesh

    original_bone_count = len(bones_info)
    bones_info, old_to_new_bone_map = filter_bones_for_mesh(
        model, bones_info, bone_id_offset
    )

    if verbose and len(bones_info) < original_bone_count:
        logger.debug(
            "Filtered bones: %d -> %d (removed unreferenced bones)",
            original_bone_count,
            len(bones_info),
        )

    # After filtering, bone_id_offset is 0 since bones are now renumbered
    bone_id_offset = 0

    # Calculate branch ID offset from FILTERED bones_info
    # (recalculate since first bone may have changed after filtering)
    first_branch_id = bones_info[0][7] if len(bones_info) > 0 else 0
    branch_id_offset = first_branch_id

    if verbose:
        logger.debug("Building skeleton from bones_info (%d bones)", len(bones_info))
        logger.debug("  Bone ID offset: %d", bone_id_offset)
        logger.debug("  Branch ID offset: %d", branch_id_offset)
        logger.debug("  Tree offset: %s", tree_offset)

    # Build joints using bones_info
    bone_id_to_joint_path = {}
    bone_positions = {}
    branch_id_to_joint_path = (
        {}
    )  # Maps local branch_id to joint path ending with branch_X

    # Create lookup dict for bones_info by global bone ID
    bones_info_dict = {}
    for bone_idx, bone_info in enumerate(bones_info):
        global_bone_id = bone_id_offset + bone_idx
        bones_info_dict[global_bone_id] = bone_info

    for bone_idx, bone_info in enumerate(bones_info):
        (
            is_tree_root,
            parent_bone_id,
            start_point,
            end_point,
            radius,
            mass,
            is_branch_root,
            branch_id,
        ) = bone_info

        # Global bone ID = local index + offset
        global_bone_id = bone_id_offset + bone_idx

        # Convert start point to tree-local space (world position - tree origin)
        world_pos = Gf.Vec3d(start_point.x, start_point.y, start_point.z)
        local_pos = world_pos - tree_offset
        bone_positions[global_bone_id] = local_pos

        # NATURAL HIERARCHY - Build joint paths following parent-child relationships
        # This preserves the natural bone structure from Grove
        local_branch_id = branch_id - branch_id_offset

        if bone_idx == 0:
            # First bone is always tree_root
            joint_name = "tree_root"
            joint_path = joint_name
        elif is_branch_root:
            # Branch root: tree_root/branch_X
            joint_name = f"branch_{local_branch_id}"
            # Get parent's joint path and append this joint
            if parent_bone_id in bone_id_to_joint_path:
                parent_joint_path = bone_id_to_joint_path[parent_bone_id]
                joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                joint_path = f"tree_root/{joint_name}"
        else:
            # Regular joint: follow parent hierarchy
            joint_name = f"joint_{bone_idx}"
            # Get parent's joint path and append this joint
            if parent_bone_id in bone_id_to_joint_path:
                parent_joint_path = bone_id_to_joint_path[parent_bone_id]
                joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                joint_path = f"tree_root/{joint_name}"

        # Store the bone's joint path
        bone_joint_path = joint_path
        bone_id_to_joint_path[global_bone_id] = bone_joint_path
        joint_tokens.append(bone_joint_path)

        # Create restTransform (LOCAL space - position relative to parent bone)
        # USD requirement: restTransforms are in local space
        if bone_idx == 0:
            # Root bone: identity transform (no translation from origin)
            relative_pos = Gf.Vec3d(0, 0, 0)
        else:
            # Calculate offset from parent bone position
            parent_pos = bone_positions.get(parent_bone_id, Gf.Vec3d(0, 0, 0))
            relative_pos = local_pos - parent_pos

        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(relative_pos)
        rest_transforms.append(rest_transform)

        # Create bindTransform (WORLD space - absolute position from tree origin)
        # USD requirement: bindTransforms are in world space (tree-local coordinates)
        # This is used by skinning to transform vertices from bind pose to animated pose
        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(local_pos)
        bind_transforms.append(bind_transform)

        # If this is a branch root, map branch_id to joint path for bindJoints lookup
        # The joint itself is already named "branch_X" so no separate joint needed
        if is_branch_root:
            branch_id_to_joint_path[local_branch_id] = bone_joint_path

    # Set skeleton attributes
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # Store branch_id mapping for later use in bindJoints
    # This allows assembly export to use: branch_id_to_joint_path[placement.branch_id]
    if hasattr(tree_prim, "branch_id_to_joint_path"):
        tree_prim.branch_id_to_joint_path = branch_id_to_joint_path

    # CRITICAL: Apply SkelBindingAPI to mesh and add skinning data
    # Unreal Engine requires BOTH SkelRoot and Mesh to have skeleton bindings
    mesh_api_schemas = mesh_prim.GetMetadata("apiSchemas")
    if mesh_api_schemas:
        if "SkelBindingAPI" not in mesh_api_schemas.prependedItems:
            mesh_api_schemas.prependedItems.append("SkelBindingAPI")
            mesh_prim.SetMetadata("apiSchemas", mesh_api_schemas)
    else:
        mesh_api_schemas = Sdf.TokenListOp()
        mesh_api_schemas.prependedItems = ["SkelBindingAPI"]
        mesh_prim.SetMetadata("apiSchemas", mesh_api_schemas)

    # Create skeleton relationship on mesh
    mesh_skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
    mesh_skel_rel.SetTargets([skel_path])

    # Add skinning data (joint indices and weights) to mesh
    mesh_geom = UsdGeom.Mesh(mesh_prim)
    points_attr = mesh_geom.GetPointsAttr()
    if points_attr:
        points = points_attr.Get()
        num_vertices = len(points)

        joint_indices = []
        joint_weights = []

        # CRITICAL: Use direct vertex-to-bone mapping if available
        # Grove provides point_attribute_bone_id after calling tag_bone_id() before build_models()
        if model and hasattr(model, "point_attribute_bone_id"):
            bone_ids = model.point_attribute_bone_id

            if verbose:
                logger.debug(
                    "Using hierarchical junction blending with blend_distance=%s",
                    junction_blend_distance,
                )
                logger.debug(
                    "  Vertices: %d, Joints: %d", len(bone_ids), len(joint_tokens)
                )
                unique_ids = set(bone_ids)
                logger.debug("  Unique bone IDs found: %s", sorted(unique_ids))
                logger.debug("  Bone ID range: %d to %d", min(bone_ids), max(bone_ids))

            # Build bone_to_joint_map using the old_to_new mapping from filtering
            # This maps original GLOBAL bone IDs to new filtered joint indices
            bone_to_joint_map = old_to_new_bone_map

            # Use calculate_vertex_weights with reduced weights at junctions
            from ...core.skeleton import calculate_vertex_weights

            joint_indices_flat, joint_weights_flat = calculate_vertex_weights(
                model=model,
                bone_to_joint_map=bone_to_joint_map,
                bones_info=bones_info,
                element_size=2,
                junction_blend_distance=junction_blend_distance,
                blend_mode=blend_mode,
            )

            # Unpack flat arrays (2 values per vertex from calculate_vertex_weights with dual-bone weighting)
            joint_indices = joint_indices_flat
            joint_weights = joint_weights_flat

            if verbose:
                logger.debug(
                    "  Calculated weights with %d vertices", len(joint_indices)
                )
                reduced_weight_count = sum(1 for w in joint_weights if w < 1.0)
                logger.debug(
                    "  Vertices with reduced weights: %d (%.1f%%)",
                    reduced_weight_count,
                    reduced_weight_count * 100 / len(joint_weights),
                )

        else:
            # Fallback: simple rigid binding to root joint
            # This should only happen if tag_bone_id() wasn't called before build_models()
            if verbose:
                logger.warning(
                    "point_attribute_bone_id not available, using fallback rigid binding"
                )
                logger.warning(
                    "Make sure to call grove.build_skeletons() and grove.tag_bone_id() BEFORE grove.build_models()"
                )

            for _ in range(num_vertices):
                # Bind each vertex to joint 0 with full weight
                joint_indices.append(0)
                joint_weights.append(1.0)

        # Create primvars for skinning
        primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

        # CRITICAL: Use elementSize=2 for dual-bone binding with parent/child weight blending
        # joint_indices and joint_weights are in dual-bone format from calculate_vertex_weights
        # Each vertex has two bone indices and two weight values that sum to 1.0

        # Joint indices primvar (2 influences per vertex)
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(2)

        # Joint weights primvar (2 influences per vertex for dual-bone weighting)
        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(2)

        # Add branch ID attributes with local indices (only if not clean export)
        # Convert from global branch IDs to local (0-based per tree)
        # These are debug/visualization attributes not required for Nanite
        if not clean_export:
            if model and hasattr(model, "face_attribute_branch_id"):
                global_branch_ids = model.face_attribute_branch_id
                local_branch_ids = [
                    branch_id - branch_id_offset for branch_id in global_branch_ids
                ]

                branch_id_primvar = primvars_api.CreatePrimvar(
                    "branchID", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
                )
                branch_id_primvar.Set(local_branch_ids)

                if verbose:
                    logger.debug(
                        "  Converted BranchId: %d faces, offset=%d",
                        len(local_branch_ids),
                        branch_id_offset,
                    )
                    logger.debug(
                        "    Global range: %d-%d",
                        min(global_branch_ids),
                        max(global_branch_ids),
                    )
                    logger.debug(
                        "    Local range: %d-%d",
                        min(local_branch_ids),
                        max(local_branch_ids),
                    )

            if model and hasattr(model, "face_attribute_branch_id_parent"):
                global_parent_ids = model.face_attribute_branch_id_parent
                local_parent_ids = [
                    parent_id - branch_id_offset if parent_id >= 0 else parent_id
                    for parent_id in global_parent_ids
                ]

                branch_parent_primvar = primvars_api.CreatePrimvar(
                    "branchIDParent",
                    Sdf.ValueTypeNames.IntArray,
                    UsdGeom.Tokens.uniform,
                )
                branch_parent_primvar.Set(local_parent_ids)

                if verbose:
                    logger.debug(
                        "  Converted BranchIdParent: %d faces", len(local_parent_ids)
                    )


def get_twig_usd_map_for_species(
    species_name: str,
    config: Any | None = None,
    prefer_skeletal: bool = False,
    prefer_static: bool = False,
) -> dict[str, list[Path]]:
    """Get mapping of twig types to USD file paths for a species.

    Returns ALL matching twig variants per grove type so that the assembly
    can randomly alternate between them for visual variety.

    NOTE: Twig references should NEVER use Nanite Assembly USD files.
    Nanite Assembly is only for the top-level tree assembly, not individual twigs.
    Using Nanite Assembly twigs causes Unreal Engine import crashes.

    Args:
        species_name: Name of tree species
        config: GrowPy configuration
        prefer_skeletal: If True, prefer skeletal twig variants (_skeletal.usda)
        prefer_static: If True, prefer static twig variants (_static.usda)

    Returns:
        Dict mapping grove twig types to lists of USD file paths:
        {'twig_long': [Path, Path], 'twig_short': [Path], ...}
    """
    if config is None:
        from growpy import get_config

        config = get_config()

    from growpy.config import get_twig_files_by_type

    twig_files_by_type = get_twig_files_by_type(species_name)

    if not twig_files_by_type:
        pass

    twig_usd_map: dict[str, list[Path]] = {}

    # Map Grove attribute names to twig file keywords
    type_mapping = {
        "twig_long": ["apical", "long", "end", "terminal", "foliage_a_", "foliage_c_"],
        "twig_short": ["lateral", "short", "side", "foliage_b_", "foliage_d_"],
        "twig_upward": ["upward", "up", "foliage_e_"],
        "twig_dead": ["dead", "fall", "winter"],
    }

    def _resolve_usd_path(twig_paths):
        """Find a valid USD file path from a list of twig paths."""
        for twig_file in twig_paths:
            for ext in [".usda", ".usdc", ".usd"]:
                usd_file = twig_file.with_suffix(ext)
                if "_nanite_assembly" in usd_file.name:
                    continue
                is_skeletal = "_skeletal" in usd_file.stem
                is_static = "_static" in usd_file.stem
                if prefer_static:
                    if is_static and usd_file.exists():
                        return usd_file
                    if not is_static:
                        static_file = (
                            usd_file.parent / f"{usd_file.stem}_static{usd_file.suffix}"
                        )
                        if static_file.exists():
                            return static_file
                elif prefer_skeletal:
                    if is_skeletal and usd_file.exists():
                        return usd_file
                    if not is_skeletal:
                        skeletal_file = (
                            usd_file.parent
                            / f"{usd_file.stem}_skeletal{usd_file.suffix}"
                        )
                        if skeletal_file.exists():
                            return skeletal_file
                else:
                    if is_skeletal or is_static:
                        continue
                    if usd_file.exists():
                        return usd_file
        return None

    # Collect ALL matching twig files per grove type
    for grove_type, keywords in type_mapping.items():
        matched_paths = []
        for keyword in keywords:
            for twig_type, twig_paths in twig_files_by_type.items():
                if keyword in twig_type.lower():
                    resolved = _resolve_usd_path(twig_paths)
                    if resolved and resolved not in matched_paths:
                        matched_paths.append(resolved)
        if matched_paths:
            twig_usd_map[grove_type] = matched_paths

    # If no type-specific matches found, assign all available twigs to all grove types
    # randomly. This handles species with non-standard naming.
    # twig_dead is excluded: without a dedicated dead-twig asset, dead positions
    # should be skipped (assembly_export does this when the type has no prototypes)
    # rather than filled with living foliage at the default upright orientation.
    if not twig_usd_map and twig_files_by_type:
        all_paths = []
        for twig_type, twig_paths in twig_files_by_type.items():
            resolved = _resolve_usd_path(twig_paths)
            if resolved and resolved not in all_paths:
                all_paths.append(resolved)
        if all_paths:
            for grove_type in type_mapping:
                if grove_type == "twig_dead":
                    continue
                twig_usd_map[grove_type] = list(all_paths)

    return twig_usd_map


def bundle_twigs_for_species(
    species_name: str,
    output_dir: Path,
    formats: list[str] | None = None,
    config: Any | None = None,
) -> dict[str, list[Path]]:
    """Bundle twig files for a species to output directory.

    Copies relevant twig meshes (USD) to species output folder
    for easier asset management in Unreal Engine.

    Twig files are named after the twig's native species (directory name),
    not the consuming species. Species sharing a twig all copy the same files.

    Args:
        species_name: Name of tree species
        output_dir: Output directory for this species
        formats: Export formats to copy ('usd', 'usda')
        config: GrowPy configuration

    Returns:
        Dict with 'twig_files' and 'manifest' paths
    """
    if formats is None:
        formats = ["usda"]

    if config is None:
        from growpy import get_config

        config = get_config()

    import shutil

    results = {"twig_files": [], "manifest": None}

    try:
        twig_dir = output_dir
        twig_dir.mkdir(parents=True, exist_ok=True)

        from growpy.config import get_twig_files_by_type

        twig_files_by_type = get_twig_files_by_type(species_name)

        if not twig_files_by_type:
            return results

        twig_manifest = {"species": species_name, "twig_files": [], "total_twigs": 0}
        copied_textures = set()

        all_twig_files = set()
        for twig_paths in twig_files_by_type.values():
            all_twig_files.update(twig_paths)

        for source_file in sorted(all_twig_files):
            if not source_file.exists():
                continue

            source_base = source_file.parent / source_file.stem

            for fmt in formats:
                if fmt == "usd":
                    extensions = [".usd", ".usda", ".usdc"]
                elif fmt == "usda":
                    extensions = [".usda", ".usdc", ".usd"]
                elif fmt == "usdc":
                    extensions = [".usdc", ".usda", ".usd"]
                else:
                    continue

                for ext in extensions:
                    fmt_source_file = source_base.with_suffix(ext)
                    if fmt_source_file.exists():
                        dest_file = twig_dir / fmt_source_file.name
                        shutil.copy2(fmt_source_file, dest_file)
                        results["twig_files"].append(dest_file)
                        twig_manifest["twig_files"].append(dest_file.name)
                        twig_manifest["total_twigs"] += 1
                        break

                    skeletal_file = (
                        source_base.parent / f"{source_base.stem}_skeletal{ext}"
                    )
                    if skeletal_file.exists():
                        dest_file = twig_dir / skeletal_file.name
                        if not dest_file.exists():
                            shutil.copy2(skeletal_file, dest_file)
                            results["twig_files"].append(dest_file)
                            twig_manifest["twig_files"].append(dest_file.name)
                            twig_manifest["total_twigs"] += 1

        # Copy opaque-only textures for Nanite compatibility
        source_texture_dir = None
        if all_twig_files:
            first_twig = next(iter(all_twig_files))
            source_texture_dir = first_twig.parent / "textures"

            if source_texture_dir.exists():
                dest_texture_dir = twig_dir / "textures"
                dest_texture_dir.mkdir(exist_ok=True)

                # Import texture classification function
                from growpy.io.usd.twig_export import classify_texture_from_name

                # CRITICAL: Only use base color (diffuse) textures
                # Normal maps and other texture types are excluded
                OPAQUE_TEXTURE_TYPES = ["diffuse"]

                texture_count = 0
                for texture_file in source_texture_dir.glob("*"):
                    if texture_file.is_file():
                        # Only copy standardized textures (contain _foliage_ or _twig_)
                        # Skip original Grove textures like BeechDiffuse.jpg
                        if (
                            "_foliage_" not in texture_file.stem
                            and "_twig_" not in texture_file.stem
                        ):
                            continue

                        # Classify texture type
                        tex_type = classify_texture_from_name(texture_file.stem)

                        # Skip non-base-color textures
                        if tex_type not in OPAQUE_TEXTURE_TYPES:
                            continue

                        dest_tex = dest_texture_dir / texture_file.name
                        if not dest_tex.exists():
                            from .texture_utils import copy_and_resize_texture

                            copy_and_resize_texture(texture_file, dest_tex)
                            texture_count += 1
                            copied_textures.add(texture_file.name)

    except Exception:
        logger.warning("Twig bundling failed")

    return results
