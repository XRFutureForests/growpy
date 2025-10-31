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

    CRITICAL: The model must be triangulated BEFORE calling this function:
        model.triangulate()

    This ensures that face counts match between geometry and face attributes,
    preventing mismatches in twig placement and material assignment.

    Args:
        model: Grove tree model from grove.build_models() - MUST be triangulated first
        output_path: Path where USD file will be saved
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated (should always be True)
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
        >>> model.triangulate()  # CRITICAL: Must triangulate first
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
        root_path = Sdf.Path("/tree")
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

            # Create proper USD materials with UsdPreviewSurface
            _add_usd_materials(stage, mesh, model, str(mesh_path))

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


def _add_usd_materials(
    stage: Usd.Stage, mesh_prim: UsdGeom.Mesh, model: Any, mesh_path: str
) -> None:
    """Create proper USD materials for Unreal Engine compatibility.

    Creates UsdPreviewSurface materials bound to geometry subsets for:
    - Green: Live twigs/leaves (TwigLong, TwigShort, TwigUpward)
    - Brown: Dead twigs
    - Brown: Tree bark/branches (stem)

    Args:
        stage: USD stage to create materials in
        mesh_prim: USD mesh prim to bind materials to
        model: Grove model with face attributes
        mesh_path: Full USD path to the mesh prim
    """
    from pxr import UsdShade

    # Get face count
    num_faces = len(model.faces) if hasattr(model, "faces") else 0
    if num_faces == 0:
        return

    # Define color palette
    BARK_BROWN = Gf.Vec3f(0.45, 0.30, 0.20)
    TWIG_GREEN = Gf.Vec3f(0.25, 0.50, 0.20)
    DEAD_BROWN = Gf.Vec3f(0.35, 0.25, 0.15)

    # Classify faces by material type
    bark_faces = []
    twig_faces = []
    dead_faces = []

    # Initialize all faces as bark
    face_types = ["bark"] * num_faces

    # Mark live twigs
    if hasattr(model, "face_attribute_twig_long"):
        for face_idx, is_twig in enumerate(model.face_attribute_twig_long):
            if is_twig and face_idx < num_faces:
                face_types[face_idx] = "twig"

    if hasattr(model, "face_attribute_twig_short"):
        for face_idx, is_twig in enumerate(model.face_attribute_twig_short):
            if is_twig and face_idx < num_faces:
                face_types[face_idx] = "twig"

    if hasattr(model, "face_attribute_twig_upward"):
        for face_idx, is_twig in enumerate(model.face_attribute_twig_upward):
            if is_twig and face_idx < num_faces:
                face_types[face_idx] = "twig"

    # Mark dead (overrides twig)
    if hasattr(model, "face_attribute_twig_dead"):
        for face_idx, is_dead in enumerate(model.face_attribute_twig_dead):
            if is_dead and face_idx < num_faces:
                face_types[face_idx] = "dead"

    if hasattr(model, "face_attribute_dead"):
        for face_idx, is_dead in enumerate(model.face_attribute_dead):
            if is_dead and face_idx < num_faces:
                face_types[face_idx] = "dead"

    # Group faces by type
    for face_idx, face_type in enumerate(face_types):
        if face_type == "bark":
            bark_faces.append(face_idx)
        elif face_type == "twig":
            twig_faces.append(face_idx)
        elif face_type == "dead":
            dead_faces.append(face_idx)

    # Create materials scope
    materials_path = mesh_path + "/Materials"
    UsdGeom.Scope.Define(stage, materials_path)

    # Helper to create material with UsdPreviewSurface
    def create_material(name: str, color: Gf.Vec3f) -> UsdShade.Material:
        mat = UsdShade.Material.Define(stage, f"{materials_path}/{name}")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/{name}/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        return mat

    # Create materials
    bark_mat = create_material("BarkMaterial", BARK_BROWN)
    twig_mat = create_material("TwigMaterial", TWIG_GREEN)
    dead_mat = create_material("DeadMaterial", DEAD_BROWN)

    # Create geometry subsets and bind materials
    if bark_faces:
        bark_subset = UsdGeom.Subset.Define(stage, mesh_path + "/BarkSubset")
        bark_subset.CreateElementTypeAttr("face")
        bark_subset.CreateIndicesAttr(bark_faces)
        UsdShade.MaterialBindingAPI(bark_subset).Bind(bark_mat)

    if twig_faces:
        twig_subset = UsdGeom.Subset.Define(stage, mesh_path + "/TwigSubset")
        twig_subset.CreateElementTypeAttr("face")
        twig_subset.CreateIndicesAttr(twig_faces)
        UsdShade.MaterialBindingAPI(twig_subset).Bind(twig_mat)

    if dead_faces:
        dead_subset = UsdGeom.Subset.Define(stage, mesh_path + "/DeadSubset")
        dead_subset.CreateElementTypeAttr("face")
        dead_subset.CreateIndicesAttr(dead_faces)
        UsdShade.MaterialBindingAPI(dead_subset).Bind(dead_mat)


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
    add_twig_bones: bool = True,
    verbose: bool = False,
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
        add_twig_bones: If True, add twig mount bones to skeleton (default: True)
        verbose: If True, print detailed debug information (default: False)

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

        # Extract twig placements from mesh if add_twig_bones is enabled
        twig_placements = None
        if add_twig_bones:
            from .twig_placement import extract_twig_placements_from_usd

            print("  Extracting twig placements from mesh...")
            twig_placements = extract_twig_placements_from_usd(usd_path)
            if twig_placements and any(twig_placements.values()):
                total_twigs = sum(
                    len(placements) for placements in twig_placements.values()
                )
                print(
                    f"  Found {total_twigs} twig placement(s) across {len(twig_placements)} type(s)"
                )
            else:
                print("  No twig placements found, skipping twig bones")
                twig_placements = None

        # Create UsdSkel skeleton structure from full polylines
        _build_usdskel_from_bones(stage, skeleton, None, twig_placements)

        # Set defaultPrim to /tree (now a SkelRoot)
        tree_prim = stage.GetPrimAtPath("/tree")
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
    twig_placements: Optional[Dict[str, List[Dict]]] = None,
    verbose: bool = False,
) -> None:
    """Build UsdSkel skeleton from Grove skeleton polylines.

    Uses full skeleton polyline data for proper bone orientation instead of
    just the simplified bone list. This gives Unreal better bone direction info.

    CRITICAL: When twig_placements is provided, adds dedicated twig mount bones
    to the skeleton. These bones enable PointInstancer binding in Nanite Assemblies.

    Args:
        stage: USD stage to add skeleton to
        skeleton: Grove skeleton object with points and poly_lines
        bones: List of bone tuples from grove.tag_bone_id() (used for branch IDs)
        twig_placements: Optional dict mapping twig type to list of placement dicts
                         Each placement has 'position', 'normal', and other twig data
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

    # Convert /tree Xform to SkelRoot
    tree_prim = stage.GetPrimAtPath("/tree")
    if tree_prim:
        # Define SkelRoot at /tree path (overwrites the Xform type)
        skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/tree"))
        tree_prim = skel_root.GetPrim()

        # NOTE: DO NOT apply UnrealNaniteAssemblyRootAPI here
        # This tree will be referenced into a Nanite Assembly, and only the
        # assembly root should have NaniteAssemblyRootAPI. Having it here
        # causes Unreal to see duplicate assembly roots and not recognize the assembly.
    else:
        # Fallback: create SkelRoot at /tree
        skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/tree"))
        tree_prim = skel_root.GetPrim()

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # This tree will be referenced into a Nanite Assembly, and only the
        # assembly root should have NaniteAssemblyRootAPI.

    # Create skeleton under /tree
    skel_path = Sdf.Path("/tree/TreeSkel")
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Set skeleton relationships on SkelRoot (required by UsdSkel spec)
    # These tell the SkelRoot where to find skeleton and animation data
    binding_api = UsdSkel.BindingAPI.Apply(tree_prim)
    binding_api.CreateSkeletonRel().SetTargets([skel_path])
    binding_api.CreateAnimationSourceRel().SetTargets([skel_path])

    # DO NOT set unreal:naniteAssembly:skeleton here!
    # This Unreal-specific relationship should ONLY be in assembly files.
    # Standalone tree USDs should only use standard USD skeleton relationships.
    # Setting this here causes double-binding when tree is loaded in assembly context.

    # Build joint hierarchy from skeleton polylines (not just bones)
    # This gives proper bone direction by using all skeleton vertices
    joint_tokens = []
    bind_transforms = []
    rest_transforms = []

    # Get skeleton data
    skeleton_points = skeleton.points  # All skeleton vertices
    skeleton_polylines = skeleton.poly_lines  # [[idx1, idx2, ...], ...] connectivity

    # Get skeleton point radii (bone thickness)
    skeleton_radii = []
    if hasattr(skeleton, "point_attribute_radius"):
        skeleton_radii = list(skeleton.point_attribute_radius)
    elif hasattr(skeleton, "point_radius"):
        skeleton_radii = list(skeleton.point_radius)
    elif hasattr(skeleton, "radii"):
        skeleton_radii = list(skeleton.radii)
    elif hasattr(skeleton, "radius"):
        skeleton_radii = list(skeleton.radius)
    else:
        # Fallback: assume uniform small radius
        skeleton_radii = [0.002] * len(skeleton_points)

    if verbose and skeleton_radii:
        print(
            f"DEBUG: Radius range: {min(skeleton_radii):.4f} - {max(skeleton_radii):.4f}"
        )

    # Get skeleton point masses (for vertex-to-joint association)
    skeleton_masses = []
    if hasattr(skeleton, "point_attribute_mass"):
        skeleton_masses = list(skeleton.point_attribute_mass)
    elif hasattr(skeleton, "point_mass"):
        skeleton_masses = list(skeleton.point_mass)
    elif hasattr(skeleton, "masses"):
        skeleton_masses = list(skeleton.masses)
    elif hasattr(skeleton, "mass"):
        skeleton_masses = list(skeleton.mass)

    if verbose and skeleton_masses:
        print(
            f"DEBUG: Mass range: {min(skeleton_masses):.4f} - {max(skeleton_masses):.4f}"
        )

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

    # Build hierarchical joint names (working approach from commit 5eef351)
    joint_counter = 0

    for polyline_idx, polyline in enumerate(skeleton_polylines):
        # Each polyline is a chain of connected points
        prev_joint_path = None

        # For branch polylines, skip first point (already created by parent)
        start_idx = 1 if polyline_idx > 0 else 0

        for i, point_idx in enumerate(polyline[start_idx:], start=start_idx):
            point = skeleton_points[point_idx]
            world_pos = Gf.Vec3d(point[0], point[1], point[2])

            # Create joint name
            joint_name = f"joint_{joint_counter}"

            # Track mapping from skeleton point to joint index
            point_to_joint_index[point_idx] = joint_counter
            joint_counter += 1

            # Build hierarchical path (CRITICAL: This is the working approach!)
            if i == start_idx:
                # First point in this polyline chain (after skip)
                if polyline_idx == 0:
                    # Root of first polyline
                    joint_path = joint_name
                else:
                    # Branch polyline - connect to the shared point's joint
                    shared_point_idx = polyline[0]  # First point (shared with parent)
                    parent_joint_path = point_to_joint_path[shared_point_idx]
                    joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                # Connected to previous point in same polyline
                joint_path = f"{prev_joint_path}/{joint_name}"

            point_to_joint_path[point_idx] = joint_path
            joint_tokens.append(joint_path)
            bone_positions[point_idx] = world_pos

            prev_joint_path = joint_path

            # Create WORLD SPACE bindTransform
            # UsdSkel bindTransforms are the world transforms of joints at bind time
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

    # Add twig mount bones to skeleton (CRITICAL for Nanite Assembly skeletal binding)
    # These bones allow twigs to be bound to specific skeleton joints via PointInstancer
    if twig_placements:
        print(f"    Adding twig mount bones to skeleton...")
        twig_counter = 0
        twig_joint_names = (
            {}
        )  # Map twig placement index to joint name for assembly binding

        for twig_type, placements in twig_placements.items():
            for placement_idx, placement in enumerate(placements):
                twig_pos = placement.get("position", (0, 0, 0))
                twig_world_pos = Gf.Vec3d(twig_pos[0], twig_pos[1], twig_pos[2])

                # Find nearest joint in existing skeleton
                nearest_joint_path = None
                nearest_distance = float("inf")

                for i, joint_path in enumerate(joint_tokens):
                    joint_bind_transform = bind_transforms[i]
                    joint_pos = joint_bind_transform.ExtractTranslation()

                    # Calculate distance
                    delta = twig_world_pos - joint_pos
                    distance = (delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2) ** 0.5

                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_joint_path = joint_path

                if nearest_joint_path:
                    # Create twig mount bone as child of nearest joint
                    # Use hierarchical naming: parent_joint/twig_N
                    twig_name = f"twig_{twig_counter}"
                    twig_joint_path = f"{nearest_joint_path}/{twig_name}"

                    # Store mapping for assembly binding (use full hierarchical path)
                    twig_joint_names[f"{twig_type}_{placement_idx}"] = twig_joint_path

                    # Get parent joint position
                    parent_joint_idx = joint_tokens.index(nearest_joint_path)
                    parent_pos = bind_transforms[parent_joint_idx].ExtractTranslation()

                    # Calculate local offset from parent
                    local_offset = twig_world_pos - parent_pos

                    # Add twig bone to skeleton
                    joint_tokens.append(twig_joint_path)

                    # Bind transform (world space)
                    # UsdSkel bindTransforms are world transforms at bind time
                    twig_bind_transform = Gf.Matrix4d(1.0)
                    twig_bind_transform.SetTranslateOnly(twig_world_pos)
                    bind_transforms.append(twig_bind_transform)

                    # Rest transform (local space, offset from parent)
                    twig_rest_transform = Gf.Matrix4d(1.0)
                    twig_rest_transform.SetTranslateOnly(local_offset)
                    rest_transforms.append(twig_rest_transform)

                    twig_counter += 1

        print(f"    [OK] Added {twig_counter} twig mount bone(s) to skeleton")

        # Store twig joint mapping in stage metadata for assembly binding
        stage.SetMetadata("customLayerData", {"twig_joint_names": twig_joint_names})

    # Set skeleton attributes (hierarchy encoded in joint paths - NO topology array)
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # Re-parent mesh under SkelRoot (/tree) if needed
    new_mesh_path = Sdf.Path("/tree/TreeMesh")
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

    # Bind mesh to skeleton (now at /tree/tree_skel)
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

        if verbose:
            print(
                f"DEBUG: point_to_joint_index has {len(point_to_joint_index)} entries"
            )

        # Pre-compute cumulative geodesic distances along each branch polyline
        # This ensures correct binding for downward-growing branches and variable segment lengths
        branch_cumulative_distances = (
            {}
        )  # branch_id -> {point_idx: cumulative_distance}

        for branch_id, polyline in branch_to_points.items():
            cumulative_dist = 0.0
            point_distances = {polyline[0]: 0.0}

            for i in range(1, len(polyline)):
                prev_idx = polyline[i - 1]
                curr_idx = polyline[i]

                prev_pos = skeleton_points[prev_idx]
                curr_pos = skeleton_points[curr_idx]

                # Compute Euclidean distance between consecutive points
                segment_length = (
                    sum((curr_pos[j] - prev_pos[j]) ** 2 for j in range(3)) ** 0.5
                )
                cumulative_dist += segment_length
                point_distances[curr_idx] = cumulative_dist

            branch_cumulative_distances[branch_id] = point_distances

        # SEGMENT-BASED VERTEX BINDING WITH TWIG BONE EXCLUSION
        # Bind each vertex to the 2 joints of its closest skeleton segment
        # CRITICAL: Exclude twig mount bones - they should NOT affect tree mesh vertices

        vertex_branch_hints = {}  # vertex_idx -> branch_id (from connected faces)

        # First pass: collect branch hints for each vertex
        face_idx = 0
        vert_offset = 0
        for face_vert_count in face_vertex_counts:
            if face_idx < len(branch_indices):
                branch_id = branch_indices[face_idx]
                # Mark all vertices in this face as belonging to this branch
                for i in range(face_vert_count):
                    vertex_idx = face_vertex_indices[vert_offset + i]
                    # Use the first branch hint we find for each vertex
                    if vertex_idx not in vertex_branch_hints:
                        vertex_branch_hints[vertex_idx] = branch_id
            vert_offset += face_vert_count
            face_idx += 1

        # Identify which joint indices are twig mount bones (exclude from tree mesh binding)
        twig_joint_indices = set()
        for joint_idx, joint_path in enumerate(joint_tokens):
            # Twig mount bones have names ending with "twig_N"
            if "/twig_" in joint_path:
                twig_joint_indices.add(joint_idx)

        print(
            f"    Binding tree mesh vertices (excluding {len(twig_joint_indices)} twig mount bones)..."
        )

        # POLYLINE-BASED BINDING: Use BranchIndex + skeleton polylines for topology-aware binding
        # Each face has a BranchIndex that corresponds to a skeleton polyline
        # Vertices bind to the polyline segments based on their position along the branch

        # Build mapping from polyline_idx to skeleton point indices
        polyline_to_points = {}
        for polyline_idx, polyline in enumerate(skeleton_polylines):
            polyline_to_points[polyline_idx + 1] = (
                polyline  # polylines are 1-indexed as branch IDs
            )

        print(
            f"    Using polyline-based binding: {len(skeleton_polylines)} skeleton polylines"
        )

        # Build polyline-based segment lookup
        # For each polyline, store all its segments with cumulative geodesic distances
        polyline_segments = (
            {}
        )  # polyline_idx -> [(start_joint, end_joint, start_pos, end_pos, cumul_dist_start, cumul_dist_end), ...]

        for polyline_idx, polyline in enumerate(skeleton_polylines):
            branch_id = polyline_idx + 1
            segments = []
            cumul_dist = 0.0

            for i in range(len(polyline) - 1):
                start_pt_idx = polyline[i]
                end_pt_idx = polyline[i + 1]

                # Skip segments involving twig mount bones
                start_joint_idx = point_to_joint_index.get(start_pt_idx, 0)
                end_joint_idx = point_to_joint_index.get(end_pt_idx, 0)

                if (
                    start_joint_idx in twig_joint_indices
                    or end_joint_idx in twig_joint_indices
                ):
                    continue

                # Get positions
                start_pos = Gf.Vec3d(*skeleton_points[start_pt_idx])
                end_pos = Gf.Vec3d(*skeleton_points[end_pt_idx])

                # Calculate segment length
                segment_vec = end_pos - start_pos
                segment_len = segment_vec.GetLength()

                # Store segment with cumulative distance along polyline
                dist_start = cumul_dist
                cumul_dist += segment_len
                dist_end = cumul_dist

                segments.append(
                    (
                        start_joint_idx,
                        end_joint_idx,
                        start_pos,
                        end_pos,
                        dist_start,
                        dist_end,
                    )
                )

            if segments:
                polyline_segments[branch_id] = segments

        total_segments = sum(len(segs) for segs in polyline_segments.values())
        print(
            f"    Built {total_segments} polyline-based skeleton segments across {len(polyline_segments)} branches"
        )

        # Collect branch hints for each vertex from face BranchIndex
        vertex_branch_hints = {}  # vertex_idx -> branch_id
        face_idx = 0
        vert_offset = 0
        for face_vert_count in face_vertex_counts:
            if face_idx < len(branch_indices):
                branch_id = branch_indices[face_idx]
                # Mark all vertices in this face as belonging to this branch
                for i in range(face_vert_count):
                    vertex_idx = face_vertex_indices[vert_offset + i]
                    # Use the first branch hint we find for each vertex
                    if vertex_idx not in vertex_branch_hints:
                        vertex_branch_hints[vertex_idx] = branch_id
            vert_offset += face_vert_count
            face_idx += 1

        # Bind each vertex to the nearest HIERARCHICAL parent-child joint pair
        # This prevents stretching by ensuring vertices only bind to adjacent joints
        vertex_to_joints = {}  # vertex_idx -> [(joint_idx, weight), ...]

        # Build parent-child relationships from polylines
        joint_parent = {}  # joint_idx -> parent_joint_idx
        joint_children = {}  # joint_idx -> [child_joint_idx, ...]

        for polyline_idx, polyline in enumerate(skeleton_polylines):
            for i in range(len(polyline) - 1):
                child_pt = polyline[i + 1]
                parent_pt = polyline[i]

                if (
                    child_pt in point_to_joint_index
                    and parent_pt in point_to_joint_index
                ):
                    child_joint = point_to_joint_index[child_pt]
                    parent_joint = point_to_joint_index[parent_pt]

                    # Skip twig joints
                    if (
                        child_joint in twig_joint_indices
                        or parent_joint in twig_joint_indices
                    ):
                        continue

                    joint_parent[child_joint] = parent_joint
                    if parent_joint not in joint_children:
                        joint_children[parent_joint] = []
                    joint_children[parent_joint].append(child_joint)

        # Build list of valid parent-child bone segments with their positions
        bone_segments = []  # [(parent_joint, child_joint, parent_pos, child_pos), ...]
        for child_joint, parent_joint in joint_parent.items():
            # Find skeleton point indices for these joints
            parent_pt = None
            child_pt = None
            for pt_idx, j_idx in point_to_joint_index.items():
                if j_idx == parent_joint:
                    parent_pt = pt_idx
                if j_idx == child_joint:
                    child_pt = pt_idx

            if parent_pt is not None and child_pt is not None:
                parent_pos = Gf.Vec3d(*skeleton_points[parent_pt])
                child_pos = Gf.Vec3d(*skeleton_points[child_pt])
                bone_segments.append((parent_joint, child_joint, parent_pos, child_pos))

        if verbose:
            print(f"    Binding {num_points} vertices...")

        # ERROR: This function operates on already-exported USD files without Grove API access
        # Weight calculation requires Grove's tag_bone_id() which needs the Grove instance
        # This post-processing approach is deprecated - use blender_export.py instead
        print("    ERROR: USD post-processing weight calculation is deprecated.")
        print(
            "    Please use export_grove_tree_as_usda_native() from blender_export.py"
        )
        print(
            "    which properly uses Grove's tag_bone_id() for accurate skeletal rigging."
        )

        # Fallback: bind all vertices to root joint with full weight
        print("    Using fallback: binding all vertices to root joint")
        for v_idx in range(num_points):
            vertex_to_joints[v_idx] = [(0, 1.0), (0, 0.0)]

    # USD format: flat arrays where element_size indicates influences per vertex
    max_influences = 2  # Use 2 joints per vertex for smooth deformation

    for v_idx in range(num_points):
        # All vertices bound to root with padding
        for _ in range(max_influences):
            joint_indices.append(0)
            joint_weights.append(1.0 if _ == 0 else 0.0)

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
        joint_indices_primvar.SetElementSize(max_influences)

        joint_weights_primvar = primvars_api_skel.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(max_influences)
    else:
        # Standard mode: use BindingAPI (already created above)
        binding_api.CreateJointIndicesPrimvar(False, max_influences).Set(joint_indices)
        binding_api.CreateJointWeightsPrimvar(False, max_influences).Set(joint_weights)

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
        root_path = Sdf.Path("/twig")
        skel_root = UsdSkel.Root.Define(stage, root_path)
        skel_root_prim = stage.GetPrimAtPath(root_path)

        # Apply SkelBindingAPI to SkelRoot (required for proper binding)
        UsdSkel.BindingAPI.Apply(skel_root_prim)

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # Twigs are referenced into Nanite Assemblies via PointInstancer.
        # Only the assembly root should have NaniteAssemblyRootAPI.
        #
        # NOTE: Do NOT set skel:skeleton or skel:animationSource on SkelRoot
        # These relationships should ONLY exist on the Mesh prim to avoid confusion

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

        # Verify mesh is at expected location (Blender already exports it at /Twig/Mesh)
        expected_mesh_path = root_path.AppendChild("Mesh")
        if mesh_prim.GetPath() != expected_mesh_path:
            # If mesh is at wrong location, move it
            old_mesh_path = mesh_prim.GetPath()
            Sdf.CopySpec(
                stage.GetRootLayer(),
                old_mesh_path,
                stage.GetRootLayer(),
                expected_mesh_path,
            )
            stage.RemovePrim(old_mesh_path)
            mesh_prim = stage.GetPrimAtPath(expected_mesh_path)
            if not mesh_prim or not mesh_prim.IsValid():
                print(f"Error: Failed to get mesh at {expected_mesh_path} after move")
                return False

        mesh = UsdGeom.Mesh(mesh_prim)

        # Clear any existing Blender-generated skinning attributes BEFORE binding
        # (they use elementSize=1, we need elementSize=2)
        if mesh_prim.HasProperty("primvars:skel:jointIndices"):
            mesh_prim.RemoveProperty("primvars:skel:jointIndices")
            print(f"  Removed existing jointIndices primvar")
        if mesh_prim.HasProperty("primvars:skel:jointWeights"):
            mesh_prim.RemoveProperty("primvars:skel:jointWeights")
            print(f"  Removed existing jointWeights primvar")

        # Bind mesh to skeleton
        binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Set skinning data - all vertices bound to root joint
        points = mesh.GetPointsAttr().Get()
        num_points = len(points)

        # All vertices use joint 0 (root) with full weight
        # CRITICAL: Use elementSize=2 to match tree skeleton format
        # Each vertex needs 2 joint influences (even if second is padded with 0/0.0)
        joint_indices = []
        joint_weights = []
        for _ in range(num_points):
            joint_indices.extend(
                [0, 0]
            )  # First joint is root (0), second is padding (0)
            joint_weights.extend([1.0, 0.0])  # First weight is 1.0, second is 0.0

        # Create primvars with elementSize=2 using the UsdGeom API
        mesh_geom = UsdGeom.Mesh(mesh_prim)
        primvarsAPI = UsdGeom.PrimvarsAPI(mesh_prim)

        # Create joint indices primvar
        joint_indices_primvar = primvarsAPI.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(2)
        print(
            f"  Created jointIndices primvar with elementSize=2, array length={len(joint_indices)}"
        )

        # Create joint weights primvar
        joint_weights_primvar = primvarsAPI.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(2)
        print(
            f"  Created jointWeights primvar with elementSize=2, array length={len(joint_weights)}"
        )

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


def _extract_face_joint_mapping(tree_usd_path):
    """
    Extract mapping from face indices to their dominant joint indices.

    Uses the mesh's existing skinning data (jointIndices and jointWeights primvars)
    to determine which joint has the most influence on each face. This is more
    accurate than spatial proximity search because it uses the actual skeletal
    binding information.

    Args:
        tree_usd_path: Path to USD file containing skeletal tree mesh

    Returns:
        Dict mapping face_index (int) to joint_index (int), or empty dict if data unavailable
    """
    from pxr import Usd, UsdGeom, UsdSkel

    try:
        stage = Usd.Stage.Open(tree_usd_path)
        if not stage:
            return {}

        # Find the tree mesh (typically named "tree_mesh" or similar)
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            return {}

        mesh = UsdGeom.Mesh(mesh_prim)

        # Get face structure
        face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

        if not face_vertex_counts or not face_vertex_indices:
            return {}

        # Get skinning data primvars
        joint_indices_primvar = UsdGeom.Primvar(
            mesh_prim.GetAttribute("primvars:skel:jointIndices")
        )
        joint_weights_primvar = UsdGeom.Primvar(
            mesh_prim.GetAttribute("primvars:skel:jointWeights")
        )

        if not joint_indices_primvar.HasValue() or not joint_weights_primvar.HasValue():
            return {}

        joint_indices = joint_indices_primvar.Get()
        joint_weights = joint_weights_primvar.Get()
        element_size = joint_indices_primvar.GetElementSize()

        if not joint_indices or not joint_weights or not element_size:
            return {}

        # Build face-to-joint mapping
        face_joint_map = {}
        vertex_offset = 0

        for face_idx, vertex_count in enumerate(face_vertex_counts):
            if vertex_count == 0:
                continue

            # Get first vertex of this face
            first_vertex_idx = face_vertex_indices[vertex_offset]

            # Get joint influences for this vertex
            # jointIndices and jointWeights are flattened arrays with elementSize influences per vertex
            start_idx = first_vertex_idx * element_size
            end_idx = start_idx + element_size

            if end_idx <= len(joint_indices) and end_idx <= len(joint_weights):
                vertex_joint_indices = joint_indices[start_idx:end_idx]
                vertex_joint_weights = joint_weights[start_idx:end_idx]

                # Find joint with highest weight (dominant joint)
                max_weight = -1
                dominant_joint_idx = 0

                for ji, jw in zip(vertex_joint_indices, vertex_joint_weights):
                    if jw > max_weight:
                        max_weight = jw
                        dominant_joint_idx = ji

                face_joint_map[face_idx] = dominant_joint_idx

            vertex_offset += vertex_count

        return face_joint_map

    except Exception as e:
        print(f"Warning: Could not extract face-joint mapping: {e}")
        return {}


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
            /tree_mesh (SkelRoot, references external tree_skel.usda)
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

        tree_skel_root.GetReferences().AddReference(tree_ref_path, "/tree")

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

            # Add reference to external twig USD (static or skeletal)
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

            # Reference skeletal twig with explicit /Twig prim path (capital T)
            # Skeletal twigs have SkelRoot "Twig" with single root joint skeleton
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

        # Build prototype index map
        proto_list = list(twig_prototype_paths.values())

        for placement in twig_placements:
            twig_type = placement.get("twig_type", "twig_long")
            position = placement.get("position", (0, 0, 0))
            orientation = placement.get("orientation", (1, 0, 0, 0))  # (w, x, y, z)
            scale = placement.get("scale", (1, 1, 1))

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

        # Set instancer attributes
        instancer.CreatePositionsAttr(positions)
        instancer.CreateOrientationsAttr(orientations)
        instancer.CreateScalesAttr(scales)
        instancer.CreateProtoIndicesAttr(proto_indices)

        # Set prototype relationships
        instancer.CreatePrototypesRel().SetTargets(proto_list)

        # CRITICAL: Set bindJoints/bindJointWeights on PointInstancer
        #
        # bindJoints controls INSTANCE PLACEMENT (not vertex deformation):
        # - Tree skeleton twig mount bones (e.g., "root/joint_1/twig_0") move instances
        # - Each twig's internal skeleton (e.g., "root") deforms its own mesh vertices
        # - NO cross-skeleton binding: tree skeleton doesn't deform twig vertices
        #
        # This is REQUIRED for Unreal to recognize and import the skeletal assembly correctly.

        # Extract skeleton joints and joint mapping from tree USD
        from .unreal_nanite_assembly import _extract_skeleton_joints_from_usd

        skeleton_joints = _extract_skeleton_joints_from_usd(tree_skel_usd_path)
        joint_names = list(skeleton_joints.keys()) if skeleton_joints else []

        # Extract face-to-joint mapping from tree mesh
        face_joint_map = _extract_face_joint_mapping(tree_skel_usd_path)

        # Build bindJoints array - each twig instance binds to the joint
        # that influences the face where the twig is placed
        # These control INSTANCE transforms, not vertex deformation
        bind_joints = []
        bind_weights = []

        for placement in twig_placements:
            face_idx = placement.get("face_index")

            # Try to get joint from face mapping first (most accurate)
            if face_idx is not None and face_joint_map and face_idx in face_joint_map:
                joint_idx = face_joint_map[face_idx]
                if 0 <= joint_idx < len(joint_names):
                    bind_joints.append(joint_names[joint_idx])
                    bind_weights.append(1.0)
                else:
                    # Fallback to root
                    bind_joints.append("joint_0")
                    bind_weights.append(1.0)
            else:
                # Fallback to root if no face mapping available
                bind_joints.append("joint_0")
                bind_weights.append(1.0)

        # Create bindJoints primvar with uniform variability and interpolation
        bind_joints_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            False,  # custom (not built-in)
            Sdf.VariabilityUniform,  # uniform variability
        )
        bind_joints_attr.Set(bind_joints)

        # Set interpolation and elementSize metadata
        bind_joints_attr.SetMetadata("interpolation", "uniform")
        bind_joints_attr.SetMetadata("elementSize", 1)

        # Create bindJointWeights primvar with uniform variability and interpolation
        bind_weights_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
            False,  # custom (not built-in)
            Sdf.VariabilityUniform,  # uniform variability
        )
        bind_weights_attr.Set(bind_weights)

        # Set interpolation and elementSize metadata
        bind_weights_attr.SetMetadata("interpolation", "uniform")
        bind_weights_attr.SetMetadata("elementSize", 1)

        print(
            f"    [OK] Bound {len(bind_joints)} twig instances to tree skeleton joints"
        )
        print(
            f"    [OK] bindJoints controls instance placement (not vertex deformation)"
        )

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

        traceback.print_exc()
        return False
