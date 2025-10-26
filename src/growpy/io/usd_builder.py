"""USD file builder using direct Grove API geometry data.

This module creates USD files directly from Grove API data without using
Grove's model_to_usda_string export. This approach avoids coordinate
transformation issues since the Grove API provides geometry data in the
correct coordinate system.

Key benefits:
- No coordinate transformation needed
- Direct access to all Grove attributes
- Cleaner integration with skeleton and twig systems
- More control over USD structure
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple

# Try to use Blender's bundled USD first (recommended for bpy environments)
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

    USD_AVAILABLE = True
except ImportError:
    # Fall back to system-installed USD if bpy not available
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

        USD_AVAILABLE = True
    except ImportError:
        USD_AVAILABLE = False


def build_tree_usd(
    model: Any,
    output_path: Path,
    up_axis: str = "Z",
    triangulated: bool = True,
    include_materials: bool = True,
    clean_export: bool = False,
) -> bool:
    """Build USD file directly from Grove model using API geometry data.

    This function extracts geometry data directly from the Grove model using
    the Python API and constructs a USD file without coordinate transformations.

    Args:
        model: Grove tree model from grove.build_models()
        output_path: Path where USD file will be saved
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated
        include_materials: If False, creates simple geometry without materials/UVs
        clean_export: If True, creates minimal USD without default attributes (demo mode)

    Returns:
        bool: True if USD file was created successfully

    Example:
        >>> grove = gc.Grove()
        >>> grove.add_new_tree(...)
        >>> grove.simulate(5)
        >>> models = grove.build_models({...})
        >>> model = models[0]
        >>> model.triangulate()
        >>> build_tree_usd(model, Path("tree.usda"), up_axis="Z")
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

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

        # Define root xform
        root_path = Sdf.Path("/Tree")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Define mesh
        mesh_path = root_path.AppendChild("TreeMesh")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Extract geometry data from Grove model
        points = model.points  # List of Vector objects with (x, y, z)
        faces = model.faces  # List of face definitions (point indices)
        uvs = model.uvs  # UV coordinates for texturing

        # Convert points to USD format
        usd_points = [Gf.Vec3f(p.x, p.y, p.z) for p in points]

        # Convert faces to USD format
        # Faces can be triangles or quads depending on triangulation
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = []
        for face in faces:
            face_vertex_indices.extend(face)

        # Set mesh topology
        mesh.CreatePointsAttr(usd_points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Add UV coordinates and materials only if requested
        if include_materials:
            if uvs:
                primvars_api = UsdGeom.PrimvarsAPI(mesh)
                uv_primvar = primvars_api.CreatePrimvar(
                    "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
                )
                usd_uvs = [Gf.Vec2f(uv[0], uv[1]) for uv in uvs]
                uv_primvar.Set(usd_uvs)

            # Set display color (default gray for bark)
            mesh.CreateDisplayColorAttr([Gf.Vec3f(0.4, 0.3, 0.2)])

        # Add face attributes from Grove
        _add_grove_face_attributes(mesh, model)

        # Add point attributes from Grove
        _add_grove_point_attributes(mesh, model)

        # Add normals for proper Unreal rendering
        _add_mesh_normals(mesh, model)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error building USD file: {e}")
        import traceback

        traceback.print_exc()
        return False


def _add_grove_face_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove face attributes as USD primvars.

    These attributes are critical for twig placement and material assignment.
    Uses PascalCase naming convention to match Grove's native export.

    Args:
        mesh: USD mesh to add attributes to
        model: Grove model with face attributes
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Twig placement attributes
    if hasattr(model, "face_attribute_twig_long"):
        primvar = primvars_api.CreatePrimvar(
            "TwigLong", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_long)

    if hasattr(model, "face_attribute_twig_short"):
        primvar = primvars_api.CreatePrimvar(
            "TwigShort", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_short)

    if hasattr(model, "face_attribute_twig_upward"):
        primvar = primvars_api.CreatePrimvar(
            "TwigUpward", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_upward)

    if hasattr(model, "face_attribute_twig_dead"):
        primvar = primvars_api.CreatePrimvar(
            "TwigDead", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_dead)

    # Branch state attributes
    if hasattr(model, "face_attribute_dead"):
        primvar = primvars_api.CreatePrimvar(
            "Dead", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_dead)

    if hasattr(model, "face_attribute_end"):
        primvar = primvars_api.CreatePrimvar(
            "End", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_end)

    # Branch identification
    if hasattr(model, "face_attribute_branch_id"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndex", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_id)

    if hasattr(model, "face_attribute_branch_id_parent"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndexParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_id_parent)

    if hasattr(model, "face_attribute_branch_index_parent"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndexParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_index_parent)


def _add_grove_point_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove point attributes as USD primvars.

    These attributes provide useful metadata about tree structure and growth.

    Args:
        mesh: USD mesh to add attributes to
        model: Grove model with point attributes
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Age and structure
    if hasattr(model, "point_attribute_age"):
        primvar = primvars_api.CreatePrimvar(
            "Age", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_age)

    if hasattr(model, "point_attribute_mass"):
        primvar = primvars_api.CreatePrimvar(
            "Mass", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_mass)

    # Physical properties
    if hasattr(model, "point_attribute_thickness"):
        primvar = primvars_api.CreatePrimvar(
            "Thickness", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_thickness)

    if hasattr(model, "point_attribute_pitch"):
        primvar = primvars_api.CreatePrimvar(
            "Pitch", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_pitch)

    # Growth and lighting
    if hasattr(model, "point_attribute_vigor"):
        primvar = primvars_api.CreatePrimvar(
            "Vigor", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_vigor)

    if hasattr(model, "point_attribute_shade"):
        primvar = primvars_api.CreatePrimvar(
            "Shade", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_shade)

    if hasattr(model, "point_attribute_photosynthesis"):
        primvar = primvars_api.CreatePrimvar(
            "Photosynthesis", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_photosynthesis)


def add_skeleton_to_usd(
    usd_path: Path,
    grove: Any,
    tree_model: Any = None,
    skeleton_length: float = 2.0,
    skeleton_reduce: float = 0.4,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add skeleton to existing USD file using Grove's full skeleton polylines.

    This function uses the complete skeleton polyline data from Grove's skeleton
    builder to create a UsdSkel skeleton with proper bone chains for correct
    orientation in Unreal Engine.

    Args:
        usd_path: Path to existing USD file with tree mesh
        grove: Grove instance with simulated tree (used to build skeleton)
        tree_model: Tree model (unused, kept for compatibility)
        skeleton_length: Length threshold (unused, we use full skeleton)
        skeleton_reduce: Reduction factor (unused, we use full skeleton)
        skeleton_bias: Bias setting (unused, we use full skeleton)
        skeleton_connected: Connection setting (unused, we use full skeleton)

    Returns:
        bool: True if skeleton was added successfully

    Example:
        >>> model = grove.build_model(0, build_options)
        >>> build_tree_usd(model, Path("tree.usda"))
        >>> add_skeleton_to_usd(Path("tree.usda"), grove)
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Usd, UsdGeom, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Error: Could not open USD stage at {usd_path}")
            return False

        # Build skeleton from grove (gets full polyline data)
        skeletons = grove.build_skeletons()
        if not skeletons:
            print("Error: No skeletons generated from grove")
            return False

        skeleton = skeletons[0]

        # Create UsdSkel skeleton structure from full polylines
        _build_usdskel_from_bones(stage, skeleton, None)  # bones parameter now unused

        # Set defaultPrim to /Tree (now a SkelRoot)
        tree_prim = stage.GetPrimAtPath("/Tree")
        if tree_prim:
            stage.SetDefaultPrim(tree_prim)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding skeleton to USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def _build_usdskel_from_bones(
    stage: Usd.Stage,
    skeleton: Any,
    bones: List[Tuple],
) -> None:
    """Build UsdSkel skeleton from Grove skeleton polylines.

    Uses full skeleton polyline data for proper bone orientation instead of
    just the simplified bone list. This gives Unreal better bone direction info.

    Args:
        stage: USD stage to add skeleton to
        skeleton: Grove skeleton object with points and poly_lines
        bones: List of bone tuples from grove.tag_bone_id() (used for branch IDs)
    """
    from pxr import Gf, Sdf, UsdGeom, UsdSkel, Vt

    # Find mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if not mesh_prim:
        print("Warning: No mesh found in USD stage")
        return

    # Convert /Tree Xform to SkelRoot
    tree_prim = stage.GetPrimAtPath("/Tree")
    if tree_prim:
        # Define SkelRoot at /Tree path (overwrites the Xform type)
        skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/Tree"))
        tree_prim = skel_root.GetPrim()

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # This tree will be referenced into a Nanite Assembly, and only the
        # assembly root should have NaniteAssemblyRootAPI. Having it here
        # causes Unreal to see duplicate assembly roots and not recognize the assembly.
    else:
        # Fallback: create SkelRoot at /Tree
        skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/Tree"))
        tree_prim = skel_root.GetPrim()

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # This tree will be referenced into a Nanite Assembly, and only the
        # assembly root should have NaniteAssemblyRootAPI.

    # Create skeleton under /Tree
    skel_path = Sdf.Path("/Tree/TreeSkel")
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Set skeleton relationship for Unreal
    tree_prim.CreateRelationship("unreal:naniteAssembly:skeleton").SetTargets(
        [skel_path]
    )

    # Build joint hierarchy from skeleton polylines (not just bones)
    # This gives proper bone direction by using all skeleton vertices
    joint_tokens = []
    bind_transforms = []
    rest_transforms = []

    # Get skeleton data
    skeleton_points = skeleton.points  # All skeleton vertices
    skeleton_polylines = skeleton.poly_lines  # [[idx1, idx2, ...], ...] connectivity

    # Convert skeleton points to tuples if they're Vector objects
    # Handle both tuple and Vector formats
    def to_tuple(point):
        if isinstance(point, tuple):
            return point
        elif hasattr(point, "x"):
            return (point.x, point.y, point.z)
        else:
            return tuple(point)

    skeleton_points = [to_tuple(p) for p in skeleton_points]

    # DEBUG: Print polyline structure
    print(f"DEBUG: Skeleton has {len(skeleton_polylines)} polylines")
    for i, poly in enumerate(skeleton_polylines):
        print(f"DEBUG: Polyline {i}: {len(poly)} points = {list(poly)}")

    # Build hierarchical joints from polylines
    # Each polyline is a bone chain, points in polyline become joints
    bone_positions = {}  # point_idx -> world position
    point_to_joint_path = {}  # point_idx -> joint path string
    point_to_joint_index = {}  # point_idx -> joint array index (for skinning)

    # First pass: find where each branch connects to previous branches
    branch_connection_points = (
        {}
    )  # polyline_idx -> (parent_polyline_idx, parent_point_idx)

    for polyline_idx in range(1, len(skeleton_polylines)):
        # Find closest point on previous polylines to this branch's first point
        branch_start = skeleton_polylines[polyline_idx][0]
        branch_start_pos = skeleton_points[branch_start]

        min_dist = float("inf")
        connect_polyline = 0
        connect_point = 0

        # Check all previous polylines
        for prev_polyline_idx in range(polyline_idx):
            for point_idx in skeleton_polylines[prev_polyline_idx]:
                point_pos = skeleton_points[point_idx]
                dist = (
                    sum((branch_start_pos[i] - point_pos[i]) ** 2 for i in range(3))
                    ** 0.5
                )
                if dist < min_dist:
                    min_dist = dist
                    connect_polyline = prev_polyline_idx
                    connect_point = point_idx

        branch_connection_points[polyline_idx] = (connect_polyline, connect_point)

    # Build topology array for hierarchy (instead of hierarchical names)
    joint_parents = []  # Parent joint index for each joint (-1 for root)
    joint_counter = 0

    for polyline_idx, polyline in enumerate(skeleton_polylines):
        # Each polyline is a chain of connected points
        prev_joint_idx = None

        # For branch polylines, skip first point (already created by parent)
        start_idx = 1 if polyline_idx > 0 else 0

        for i, point_idx in enumerate(polyline[start_idx:], start=start_idx):
            point = skeleton_points[point_idx]
            world_pos = Gf.Vec3d(point[0], point[1], point[2])

            # Create FLAT joint name (no hierarchy in name - use topology array instead)
            joint_name = f"joint_{joint_counter}"

            # Determine parent joint index for topology array
            if i == start_idx:
                # First point in this polyline chain (after skip)
                if polyline_idx == 0:
                    # Root of first polyline - no parent
                    parent_idx = -1
                else:
                    # Branch polyline - parent is the shared point's joint
                    shared_point_idx = polyline[0]  # First point (shared with parent)
                    parent_idx = point_to_joint_index[shared_point_idx]
            else:
                # Connected to previous point in same polyline
                parent_idx = prev_joint_idx

            # Track this joint
            point_to_joint_index[point_idx] = joint_counter
            point_to_joint_path[point_idx] = joint_name  # Now just flat name
            joint_tokens.append(joint_name)
            joint_parents.append(parent_idx)
            bone_positions[point_idx] = world_pos

            prev_joint_idx = joint_counter
            joint_counter += 1

            # Create WORLD SPACE bindTransform
            bind_transform = Gf.Matrix4d(1.0)
            bind_transform.SetTranslateOnly(world_pos)
            bind_transforms.append(bind_transform)

            # Create LOCAL SPACE restTransform
            if i == 0:
                # First point - local = world (no parent in this polyline)
                local_pos = world_pos
            else:
                # Relative to previous point in polyline
                prev_point_idx = polyline[i - 1]
                parent_pos = bone_positions.get(prev_point_idx, Gf.Vec3d(0, 0, 0))
                local_pos = world_pos - parent_pos

            rest_transform = Gf.Matrix4d(1.0)
            rest_transform.SetTranslateOnly(local_pos)
            rest_transforms.append(rest_transform)

    # Set skeleton attributes with flat names + topology array
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # CRITICAL: Add topology array to preserve hierarchy with flat joint names
    # This is the USD-standard way to encode skeleton hierarchy
    # Use GetPrim().CreateAttribute since CreateJointParentsAttr may not exist in older USD
    joint_parents_attr = skel.GetPrim().CreateAttribute(
        "jointParents", Sdf.ValueTypeNames.IntArray, custom=False
    )
    joint_parents_attr.Set(Vt.IntArray(joint_parents))

    # Re-parent mesh under SkelRoot (/Tree) if needed
    new_mesh_path = Sdf.Path("/Tree/TreeMesh")
    old_mesh_path = mesh_prim.GetPath()

    # Only move mesh if it's not already at the correct path
    if old_mesh_path != new_mesh_path:
        Sdf.CopySpec(
            stage.GetRootLayer(), old_mesh_path, stage.GetRootLayer(), new_mesh_path
        )
        stage.RemovePrim(old_mesh_path)
        mesh_prim = stage.GetPrimAtPath(new_mesh_path)
    # else: mesh is already at correct path, no need to move

    # Get mesh schema (whether moved or not)
    mesh = UsdGeom.Mesh(mesh_prim)

    # Check if clean export mode is enabled
    clean_export = False
    custom_data = stage.GetMetadata("customLayerData")
    if custom_data and isinstance(custom_data, dict):
        clean_export = custom_data.get("clean_export", False)

    # Bind mesh to skeleton (now at /Tree/TreeSkel)
    # For clean export, manually set apiSchemas to avoid auto-generated relationships
    if clean_export:
        # Manually add SkelBindingAPI to apiSchemas
        api_schemas = mesh_prim.GetMetadata("apiSchemas") or Sdf.TokenListOp()
        if not isinstance(api_schemas, Sdf.TokenListOp):
            api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["SkelBindingAPI"]
        mesh_prim.SetMetadata("apiSchemas", api_schemas)

        # Create skeleton relationship without custom qualifier
        skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
        skel_rel.SetTargets([skel_path])
    else:
        # Standard mode: use BindingAPI.Apply
        binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

    # Apply MaterialBindingAPI if mesh has material bindings
    # USD requires this API to be applied if material:binding relationship exists
    if mesh_prim.HasRelationship("material:binding"):
        from pxr import UsdShade

        UsdShade.MaterialBindingAPI.Apply(mesh_prim)

    # Add skinning data (joint influences and weights)
    # Use BranchIndex from face attributes to map vertices to bones
    points = mesh.GetPointsAttr().Get()
    num_points = len(points)

    # Get BranchIndex primvar to know which branch each face belongs to
    primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
    branch_index_primvar = primvars_api.GetPrimvar("BranchIndex")

    # Create vertex-to-joint mapping
    joint_indices = []
    joint_weights = []

    if branch_index_primvar and branch_index_primvar.HasValue():
        # Get per-face branch indices from skeleton
        branch_indices = branch_index_primvar.Get()
        face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

        # Build mapping from branch_id to list of skeleton point indices in that branch
        branch_to_points = {}
        for polyline_idx, polyline in enumerate(skeleton_polylines):
            # Grove branch_id is 1-indexed
            branch_id = polyline_idx + 1
            branch_to_points[branch_id] = polyline

        print(f"DEBUG: point_to_joint_index has {len(point_to_joint_index)} entries")
        print(f"DEBUG: branch_to_points has {len(branch_to_points)} branches")
        print(
            f"DEBUG: First few mappings: {dict(list(point_to_joint_index.items())[:5])}"
        )

        # Map each vertex to closest joint in its branch
        # Strategy: For each face, find the skeleton polyline segment it's closest to,
        # then use the joint at the START of that segment
        vertex_to_joint = {}  # vertex_idx -> (joint_idx, weight)

        face_idx = 0
        vert_offset = 0
        for face_vert_count in face_vertex_counts:
            if face_idx < len(branch_indices):
                branch_id = branch_indices[face_idx]

                # Get skeleton points for this branch
                if branch_id in branch_to_points:
                    branch_points = branch_to_points[branch_id]

                    # Calculate face center from its vertices
                    face_center = Gf.Vec3d(0, 0, 0)
                    face_verts = []
                    for i in range(face_vert_count):
                        vertex_idx = face_vertex_indices[vert_offset + i]
                        face_verts.append(vertex_idx)
                        v_pos = points[vertex_idx]
                        face_center += Gf.Vec3d(v_pos[0], v_pos[1], v_pos[2])
                    face_center /= face_vert_count

                    # Find closest polyline segment (pair of consecutive skeleton points)
                    min_dist = float("inf")
                    closest_segment_start_idx = branch_points[0]

                    for i in range(len(branch_points) - 1):
                        start_pt_idx = branch_points[i]
                        end_pt_idx = branch_points[i + 1]

                        start_pos = skeleton_points[start_pt_idx]
                        end_pos = skeleton_points[end_pt_idx]

                        start_vec = Gf.Vec3d(start_pos[0], start_pos[1], start_pos[2])
                        end_vec = Gf.Vec3d(end_pos[0], end_pos[1], end_pos[2])

                        # Find closest point on segment to face_center
                        segment = end_vec - start_vec
                        to_face = face_center - start_vec

                        # Project to_face onto segment
                        segment_len_sq = segment * segment  # dot product with itself
                        if segment_len_sq > 0:
                            t = max(0.0, min(1.0, (to_face * segment) / segment_len_sq))
                        else:
                            t = 0.0

                        closest_on_segment = start_vec + segment * t
                        dist_vec = face_center - closest_on_segment
                        dist = (dist_vec * dist_vec) ** 0.5

                        if dist < min_dist:
                            min_dist = dist
                            # Use the START point of this segment as the controlling joint
                            closest_segment_start_idx = start_pt_idx

                    # Map this skeleton point index to joint index
                    joint_idx = point_to_joint_index.get(closest_segment_start_idx, 0)

                    # Assign this joint to all vertices of this face
                    for vertex_idx in face_verts:
                        vertex_to_joint[vertex_idx] = (joint_idx, 1.0)
                else:
                    # Branch not found, bind to root
                    for i in range(face_vert_count):
                        vertex_idx = face_vertex_indices[vert_offset + i]
                        vertex_to_joint[vertex_idx] = (0, 1.0)

            vert_offset += face_vert_count
            face_idx += 1

        # Build final arrays (one entry per vertex)
        for v_idx in range(num_points):
            if v_idx in vertex_to_joint:
                joint_idx, weight = vertex_to_joint[v_idx]
                joint_indices.append(joint_idx)
                joint_weights.append(weight)
            else:
                # Unassigned vertices bound to root
                joint_indices.append(0)
                joint_weights.append(1.0)
    else:
        # Fallback: all vertices bound to root
        joint_indices = [0] * num_points
        joint_weights = [1.0] * num_points

    # Set skinning attributes with proper element size
    if clean_export:
        # Use PrimvarsAPI directly for clean export
        primvars_api_skel = UsdGeom.PrimvarsAPI(mesh_prim)

        joint_indices_primvar = primvars_api_skel.CreatePrimvar(
            "skel:jointIndices",
            Sdf.ValueTypeNames.IntArray,
            UsdGeom.Tokens.vertex,
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(1)

        joint_weights_primvar = primvars_api_skel.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(1)
    else:
        # Standard mode: use BindingAPI (already created above)
        binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
        binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

    return skel


def add_twig_skeleton_to_usd(
    usd_path: Path,
    pivot_point: Tuple[float, float, float] = (0, 0, 0),
) -> bool:
    """Add simple skeleton to twig USD with single root joint at pivot.

    Creates a minimal skeleton structure for twigs with just a root joint
    positioned at the twig's pivot point (attachment point). This enables
    twig animation and wind effects in Unreal Engine.

    Args:
        usd_path: Path to existing USD file with twig mesh
        pivot_point: World position of root joint (pivot/attachment point)

    Returns:
        bool: True if skeleton was added successfully

    Example:
        >>> build_tree_usd(model, Path("twig.usda"))
        >>> add_twig_skeleton_to_usd(Path("twig.usda"), pivot_point=(0, 0, 0))
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Error: Could not open USD stage at {usd_path}")
            return False

        # Find mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            print(f"Warning: No mesh found in USD file {usd_path.name}")
            print(f"  This file may be corrupted or incomplete from Blender export")
            print(f"  File size: {usd_path.stat().st_size} bytes")
            return False

        # Verify mesh has points
        mesh = UsdGeom.Mesh(mesh_prim)
        points = mesh.GetPointsAttr().Get()
        if not points or len(points) == 0:
            print(f"Warning: Mesh in {usd_path.name} has no vertices")
            print(f"  This indicates a failed or incomplete Blender export")
            return False

        # Create skeleton root
        root_path = Sdf.Path("/Twig")
        skel_root = UsdSkel.Root.Define(stage, root_path)

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # Twigs are referenced into Nanite Assemblies via PointInstancer.
        # Only the assembly root should have NaniteAssemblyRootAPI.

        # Create skeleton with single root joint
        # Use "Skel" naming to match Nanite Assembly requirements
        skel_path = root_path.AppendChild("Skel")
        skel = UsdSkel.Skeleton.Define(stage, skel_path)

        # Create single root joint at pivot point
        joint_tokens = ["root"]
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

        # Re-parent mesh under SkelRoot
        # Use "Mesh" naming to match Nanite Assembly requirements
        new_mesh_path = root_path.AppendChild("Mesh")
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
        binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Set skinning data - all vertices bound to root joint
        points = mesh.GetPointsAttr().Get()
        num_points = len(points)

        # All vertices use joint 0 (root) with full weight
        joint_indices = [0] * num_points
        joint_weights = [1.0] * num_points

        # Set skinning attributes
        binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
        binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

        # CRITICAL: Remove any leftover /root prim from Blender export
        # The file should only contain /Twig (SkelRoot) for Unreal to properly recognize it
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())
            print(f"  Removed old /root prim (Blender export artifact)")

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding twig skeleton to USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def add_materials_to_usd(
    usd_path: Path,
    species_name: str,
    textures: Optional[dict] = None,
) -> bool:
    """Add material and texture bindings to USD file.

    Args:
        usd_path: Path to USD file
        species_name: Species name for material naming
        textures: Dictionary with texture paths (diffuse, normal, roughness)

    Returns:
        bool: True if materials were added successfully
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Sdf, Usd, UsdGeom, UsdShade

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Error: Could not open USD stage at {usd_path}")
            return False

        # Find mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            print("Warning: No mesh found in USD stage")
            return False

        # Create material
        material_path = mesh_prim.GetPath().GetParentPath().AppendChild("BarkMaterial")
        material = UsdShade.Material.Define(stage, material_path)

        # Create shader
        shader_path = material_path.AppendChild("Shader")
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")

        # Set material properties
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.4, 0.3, 0.2)
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)

        # Add texture inputs if provided
        if textures:
            # TODO: Add texture file references
            pass

        # Connect shader to material output
        material.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )

        # Bind material to mesh
        UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding materials to USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def _add_mesh_normals(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add computed normals to mesh for proper Unreal rendering.

    Args:
        mesh: USD mesh to add normals to
        model: Grove model with geometry data
    """
    try:
        # For now, use face normals (uniform interpolation)
        # This is simpler and works well for skeletal meshes
        # TODO: Compute proper vertex normals if needed

        # Get face count
        faces = model.faces if hasattr(model, "faces") else []
        if not faces:
            return

        # Create simple up-facing normals for now
        # In production, compute actual face normals from vertex positions
        normals = [Gf.Vec3f(0, 0, 1) for _ in faces]

        normals_attr = mesh.CreateNormalsAttr()
        normals_attr.Set(normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

    except Exception as e:
        # Non-critical, just skip normals
        pass


def build_skeletal_nanite_assembly(
    assembly_path: Path,
    tree_skel_usd_path: Path,
    twig_skel_usd_paths: Dict[str, Path],
    twig_placements: List[Dict],
    up_axis: str = "Z",
) -> bool:
    """Build skeletal Nanite Assembly USD with external references.

    Creates a Nanite Assembly structure that references external skeletal tree
    and twig USD files, with proper PointInstancer bindings for twigs.

    Args:
        assembly_path: Path for output assembly USD file
        tree_skel_usd_path: Path to skeletal tree USD file
        twig_skel_usd_paths: Dict mapping twig type to skeletal twig USD paths
        twig_placements: List of twig placement dicts with position, orientation, joint, etc.
        up_axis: Coordinate system up axis ("Y" or "Z")

    Returns:
        bool: True if assembly was created successfully

    Example Structure:
        /AssemblyRoot (Xform with NaniteAssemblyRootAPI)
            /TreeMesh (SkelRoot, references external tree_skel.usda)
            /TwigPrototypes (Scope)
                /twig_long (Xform, instanceable)
                    /TwigSkelRoot (SkelRoot, references external twig_skel.usda)
                /twig_short (Xform, instanceable)
                    /TwigSkelRoot (SkelRoot, references external twig_skel.usda)
            /TwigInstances (PointInstancer with NaniteAssemblySkelBindingAPI)
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        # Create new stage
        stage = Usd.Stage.CreateNew(str(assembly_path))

        # Set stage metadata
        UsdGeom.SetStageUpAxis(
            stage, UsdGeom.Tokens.z if up_axis == "Z" else UsdGeom.Tokens.y
        )
        stage.SetMetadata("metersPerUnit", 1.0)

        # Create assembly root name from file stem
        assembly_name = assembly_path.stem
        root_path = Sdf.Path(f"/{assembly_name}")

        # Define assembly root (Xform with NaniteAssemblyRootAPI)
        root_xform = UsdGeom.Xform.Define(stage, root_path)
        root_prim = root_xform.GetPrim()

        # Apply NaniteAssemblyRootAPI and GeomModelAPI using TokenListOp
        # Both schemas are required by Unreal Engine 5.7
        # CRITICAL: Use SetMetadata instead of ApplyAPI because Blender's bundled USD
        # doesn't have Unreal schemas loaded
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
        root_prim.SetMetadata("apiSchemas", api_schemas)

        # Set kind metadata to 'assembly' as required by Unreal (not 'group')
        root_prim.SetMetadata("kind", "assembly")

        # Set mesh type to skeletalMesh - CRITICAL: Must use uniform variability
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set("skeletalMesh")

        # Reference tree skeleton
        tree_mesh_path = root_path.AppendChild("TreeMesh")
        tree_skel_root = stage.DefinePrim(tree_mesh_path, "SkelRoot")

        # Add reference to external tree skeleton USD
        # Use relative path if in same directory
        if tree_skel_usd_path.parent == assembly_path.parent:
            tree_ref_path = f"./{tree_skel_usd_path.name}"
        else:
            tree_ref_path = str(tree_skel_usd_path.resolve())

        tree_skel_root.GetReferences().AddReference(tree_ref_path, "/Tree")

        # Set skeleton relationship to tree skeleton
        skel_rel_path = tree_mesh_path.AppendChild("TreeSkel")
        root_prim.CreateRelationship(
            "unreal:naniteAssembly:skeleton", custom=False
        ).SetTargets([skel_rel_path])

        # Create TwigPrototypes scope
        prototypes_path = root_path.AppendChild("TwigPrototypes")
        prototypes_scope = UsdGeom.Scope.Define(stage, prototypes_path)

        # Create twig prototype references (instanceable)
        twig_prototype_paths = {}
        for twig_type, twig_usd_path in twig_skel_usd_paths.items():
            # Create xform for this twig type
            twig_proto_path = prototypes_path.AppendChild(twig_type)
            twig_proto_xform = UsdGeom.Xform.Define(stage, twig_proto_path)
            twig_proto_prim = twig_proto_xform.GetPrim()

            # Make instanceable
            twig_proto_prim.SetInstanceable(True)

            # Create SkelRoot under twig prototype
            twig_skelroot_path = twig_proto_path.AppendChild("TwigSkelRoot")
            twig_skelroot = stage.DefinePrim(twig_skelroot_path, "SkelRoot")

            # Add reference to external twig skeleton USD
            # CRITICAL: Always use relative paths for portability
            # Check if twig is in same directory as assembly
            if twig_usd_path.parent.resolve() == assembly_path.parent.resolve():
                twig_ref_path = f"./{twig_usd_path.name}"
            else:
                # Twig not in same directory - this shouldn't happen for properly configured exports
                # But fall back to relative path if possible
                try:
                    twig_ref_path = f"./{twig_usd_path.name}"
                    print(
                        f"        WARNING: Twig not in same dir as assembly, using ./{twig_usd_path.name}"
                    )
                except:
                    twig_ref_path = str(twig_usd_path.resolve())
                    print(
                        f"        WARNING: Using absolute path for twig: {twig_ref_path}"
                    )

            twig_skelroot.GetReferences().AddReference(twig_ref_path, "/Twig")

            twig_prototype_paths[twig_type] = twig_proto_path

        # Create PointInstancer for twig instances
        instancer_path = root_path.AppendChild("TwigInstances")
        instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)
        instancer_prim = instancer.GetPrim()

        # Apply NaniteAssemblySkelBindingAPI using TokenListOp
        # CRITICAL: Use SetMetadata instead of ApplyAPI
        skel_binding_schemas = Sdf.TokenListOp()
        skel_binding_schemas.prependedItems = ["NaniteAssemblySkelBindingAPI"]
        instancer_prim.SetMetadata("apiSchemas", skel_binding_schemas)

        # Prepare instance data
        positions = []
        orientations = []
        scales = []
        proto_indices = []
        bind_joints = []
        bind_weights = []

        # Build prototype index map
        proto_list = list(twig_prototype_paths.values())

        for placement in twig_placements:
            twig_type = placement.get("twig_type", "twig_long")
            position = placement.get("position", (0, 0, 0))
            orientation = placement.get("orientation", (1, 0, 0, 0))  # (w, x, y, z)
            scale = placement.get("scale", (1, 1, 1))
            joint_name = placement.get("joint_name", "root")
            weight = placement.get("weight", 1.0)

            # Get prototype index
            if twig_type in twig_prototype_paths:
                proto_path = twig_prototype_paths[twig_type]
                proto_idx = proto_list.index(proto_path)
            else:
                # Default to first prototype
                proto_idx = 0

            positions.append(Gf.Vec3f(*position))
            orientations.append(Gf.Quath(*orientation))
            scales.append(Gf.Vec3f(*scale))
            proto_indices.append(proto_idx)
            bind_joints.append(joint_name)
            bind_weights.append(weight)

        # Set instancer attributes
        instancer.CreatePositionsAttr(positions)
        instancer.CreateOrientationsAttr(orientations)
        instancer.CreateScalesAttr(scales)
        instancer.CreateProtoIndicesAttr(proto_indices)

        # Set prototype relationships
        instancer.CreatePrototypesRel().SetTargets(proto_list)

        # Set bind joints and weights (NaniteAssemblySkelBindingAPI attributes)
        # CRITICAL: Create as uniform attributes to match working example format
        # Working: "uniform token[]" | Ours was: "token[] (interpolation=uniform)"

        bind_joints_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        bind_joints_attr.Set(bind_joints)
        bind_joints_attr.SetMetadata("elementSize", 1)

        bind_weights_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        bind_weights_attr.Set(bind_weights)
        bind_weights_attr.SetMetadata("elementSize", 1)

        # Set default prim
        stage.SetDefaultPrim(root_prim)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error building skeletal Nanite assembly: {e}")
        import traceback

        traceback.print_exc()
        return False
