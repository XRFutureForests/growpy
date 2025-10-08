"""Twig placement functionality for Grove tree meshes.

This module provides functionality to place twig meshes at positions defined by
twig attributes on tree meshes. The Grove exports tree meshes with tiny triangles
marked with twig attributes (twig_long, twig_short, twig_upward, twig_dead) that
indicate where twig instances should be placed.

The orientation of each twig is determined by the face normal of these triangles,
with twigs expected to be modeled along the X-axis (base at origin, growing in +X).
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    bpy = None
    BPY_AVAILABLE = False

# USD imports moved to function level to avoid DLL issues on Windows
USD_AVAILABLE = None  # Will be checked lazily when needed


def _setup_usd_path():
    """Add USD DLLs to PATH on Windows to fix import issues.

    USD Python bindings on Windows require DLLs to be in PATH before import.
    This function locates the USD installation and adds necessary paths.
    """
    import os
    import site
    import sys

    if sys.platform != "win32":
        return True  # No setup needed on non-Windows

    # Get all site-packages directories
    site_packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        site_packages_dirs.append(site.getusersitepackages())

    paths_added = []
    for sp in site_packages_dirs:
        # Add both the pxr directory and the bin directory if they exist
        pxr_path = os.path.join(sp, "pxr")
        if os.path.exists(pxr_path):
            if pxr_path not in os.environ.get("PATH", ""):
                os.environ["PATH"] = pxr_path + os.pathsep + os.environ.get("PATH", "")
                paths_added.append(pxr_path)

        # Also try usd-core package structure
        usd_bin = os.path.join(sp, "usd", "bin")
        if os.path.exists(usd_bin):
            if usd_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = usd_bin + os.pathsep + os.environ.get("PATH", "")
                paths_added.append(usd_bin)

    return len(paths_added) > 0


def _check_usd_available():
    """Check if USD Python is available and provide helpful error message.

    Returns:
        tuple: (success: bool, error_msg: str or None)
    """
    # Try to setup USD path first
    _setup_usd_path()

    try:
        from pxr import Usd

        return (True, None)
    except ImportError as e:
        error_msg = (
            f"USD Python (pxr) not available: {e}\n"
            "\nTo fix this issue:\n"
            "1. Uninstall existing USD package: pip uninstall usd-core\n"
            "2. Reinstall with conda: conda install -c conda-forge usd-core\n"
            "   OR\n"
            "   Install pre-built wheel from: https://github.com/PixarAnimationStudios/OpenUSD\n"
            "\nNote: On Windows, USD requires Visual C++ Redistributables.\n"
        )
        return (False, error_msg)


def get_face_center_and_normal(
    vertices: List[Tuple[float, float, float]], face: List[int]
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Calculate face center and normal vector.

    Args:
        vertices: List of vertex coordinates
        face: List of vertex indices forming the face

    Returns:
        Tuple of (center, normal) where both are (x, y, z) tuples
    """
    # Calculate center
    face_verts = [vertices[i] for i in face]
    center = (
        sum(v[0] for v in face_verts) / len(face_verts),
        sum(v[1] for v in face_verts) / len(face_verts),
        sum(v[2] for v in face_verts) / len(face_verts),
    )

    # Calculate normal using Newell's method for robustness
    normal = [0.0, 0.0, 0.0]
    for i in range(len(face_verts)):
        v1 = face_verts[i]
        v2 = face_verts[(i + 1) % len(face_verts)]
        normal[0] += (v1[1] - v2[1]) * (v1[2] + v2[2])
        normal[1] += (v1[2] - v2[2]) * (v1[0] + v2[0])
        normal[2] += (v1[0] - v2[0]) * (v1[1] + v2[1])

    # Normalize
    length = math.sqrt(sum(n * n for n in normal))
    if length > 0:
        normal = tuple(n / length for n in normal)
    else:
        normal = (0.0, 0.0, 1.0)

    return center, normal


def normal_to_rotation_matrix(normal: Tuple[float, float, float]) -> List[List[float]]:
    """Convert normal vector to rotation matrix.

    The Grove expects twigs to be modeled along the X-axis (base at origin, growing +X).
    This creates a rotation matrix that aligns the X-axis with the given normal vector.

    Args:
        normal: Normal vector (x, y, z)

    Returns:
        3x3 rotation matrix as list of lists
    """
    nx, ny, nz = normal

    # Build orthonormal basis with X-axis aligned to normal
    # X-axis = normal direction (twig grows along this)
    x_axis = normal

    # Find perpendicular vector for Y-axis
    # Use world up (0,0,1) unless normal is too close to vertical
    if abs(nz) > 0.9:
        ref = (1.0, 0.0, 0.0)
    else:
        ref = (0.0, 0.0, 1.0)

    # Y-axis = normalize(ref cross x_axis)
    y_axis = (
        ref[1] * x_axis[2] - ref[2] * x_axis[1],
        ref[2] * x_axis[0] - ref[0] * x_axis[2],
        ref[0] * x_axis[1] - ref[1] * x_axis[0],
    )
    length = math.sqrt(sum(y * y for y in y_axis))
    if length > 0:
        y_axis = tuple(y / length for y in y_axis)
    else:
        y_axis = (0.0, 1.0, 0.0)

    # Z-axis = x_axis cross y_axis
    z_axis = (
        x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
        x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
        x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0],
    )

    # Build rotation matrix (column-major for most 3D software)
    return [
        [x_axis[0], y_axis[0], z_axis[0]],
        [x_axis[1], y_axis[1], z_axis[1]],
        [x_axis[2], y_axis[2], z_axis[2]],
    ]


def rotation_matrix_to_quaternion(
    matrix: List[List[float]],
) -> Tuple[float, float, float, float]:
    """Convert 3x3 rotation matrix to normalized quaternion (w, x, y, z).

    Uses Shepperd's method for numerical stability.

    Args:
        matrix: 3x3 rotation matrix as list of lists

    Returns:
        Normalized quaternion (w, x, y, z)
    """
    # Extract matrix elements
    m00, m01, m02 = matrix[0]
    m10, m11, m12 = matrix[1]
    m20, m21, m22 = matrix[2]

    # Compute trace
    trace = m00 + m11 + m22

    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m21 - m12) * s
        y = (m02 - m20) * s
        z = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s

    # Normalize to ensure unit length (critical for USD)
    length = math.sqrt(w * w + x * x + y * y + z * z)
    if length > 0:
        return (w / length, x / length, y / length, z / length)
    else:
        return (1.0, 0.0, 0.0, 0.0)  # Identity quaternion


def convert_y_up_to_z_up(
    pos: Tuple[float, float, float], scale: float = 1.0
) -> Tuple[float, float, float]:
    """Convert Y-up (Grove/OpenGL) coordinates to Z-up (Blender/USD standard).

    Grove exports USD in Y-up coordinate system. This function rotates to Z-up
    for proper orientation in Blender and Unreal Engine.

    Args:
        pos: Position in Y-up coordinates (x, y, z)
        scale: Scale factor to apply (default: 1.0 for no scaling)

    Returns:
        Position in Z-up coordinates (x, y, z)
    """
    # Rotate -90 degrees around X-axis: (x, y, z) -> (x, -z, y)
    return (pos[0] * scale, -pos[2] * scale, pos[1] * scale)


def convert_y_up_normal_to_z_up(
    normal: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert Y-up normal vector to Z-up orientation.

    Args:
        normal: Normal in Y-up coordinates (x, y, z)

    Returns:
        Normal in Z-up coordinates (x, y, z)
    """
    # Rotate -90 degrees around X-axis: (x, y, z) -> (x, -z, y)
    return (normal[0], -normal[2], normal[1])


def convert_blender_to_ue_coords(
    pos: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert Blender (Z-up, RH) coordinates to Unreal Engine (Z-up, LH).

    Both Blender and UE use Z-up, but different handedness:
    - Blender: Right-handed (X right, Y forward, Z up)
    - Unreal: Left-handed (X forward, Y right, Z up)

    Conversion: Swap X and Y, negate Y for handedness change
    Blender (X, Y, Z) → UE (Y, -X, Z)

    This is ONLY applied when convert_to_ue=True flag is set.
    The base tree USD remains in Blender Z-up coordinates (right-handed).
    See docs/growpy/COORDINATE_SYSTEMS.md for full transformation pipeline.

    Args:
        pos: Position in Blender coordinates (x, y, z)

    Returns:
        Position in UE coordinates (x, y, z)
    """
    # Swap X and Y, negate new Y for left-handed system
    return (pos[1], -pos[0], pos[2])


def convert_blender_normal_to_ue(
    normal: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert Blender normal to Unreal Engine orientation.

    Same coordinate conversion as positions:
    Blender (X, Y, Z) -> UE (Y, -X, Z)

    Args:
        normal: Normal in Blender coordinates (x, y, z)

    Returns:
        Normal in UE coordinates (x, y, z)
    """
    return (normal[1], -normal[0], normal[2])


def extract_twig_placements_from_mesh(
    mesh: Any, model: Optional[Any] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Extract twig placement data from Grove mesh with twig attributes.

    Args:
        mesh: Blender mesh object with twig attributes
        model: Optional Grove model with face attributes

    Returns:
        Dictionary mapping twig types to lists of placement data:
        {
            'twig_long': [{'position': (x,y,z), 'normal': (x,y,z), 'rotation_matrix': [[...]]}, ...],
            'twig_short': [...],
            'twig_upward': [...],
            'twig_dead': [...]
        }
    """
    if not BPY_AVAILABLE:
        raise ImportError("bpy (Blender Python) required for mesh processing")

    placements = {"twig_long": [], "twig_short": [], "twig_upward": [], "twig_dead": []}

    # Get vertices
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]

    # Check for twig attributes
    twig_attrs = {}
    for attr_name in ["twig_long", "twig_short", "twig_upward", "twig_dead"]:
        if attr_name in mesh.attributes:
            twig_attrs[attr_name] = mesh.attributes[attr_name]

    if not twig_attrs:
        print("Warning: No twig attributes found on mesh")
        return placements

    # Iterate through polygons/faces
    for poly in mesh.polygons:
        poly_idx = poly.index

        # Check each twig attribute
        for attr_name, attr in twig_attrs.items():
            if attr.data[poly_idx].value:  # Boolean attribute is True
                # Get face vertices
                face_verts = [vertices[v] for v in poly.vertices]

                # Calculate center and normal
                center, normal = get_face_center_and_normal(
                    vertices, list(poly.vertices)
                )

                # Create rotation matrix
                rot_matrix = normal_to_rotation_matrix(normal)

                placement_data = {
                    "position": center,
                    "normal": normal,
                    "rotation_matrix": rot_matrix,
                    "face_index": poly_idx,
                }

                placements[attr_name].append(placement_data)

    # Print summary
    for twig_type, places in placements.items():
        if places:
            print(f"Found {len(places)} {twig_type} placements")

    return placements


def place_twigs_in_blender(
    tree_mesh: Any, twig_objects: Dict[str, Any], use_instances: bool = True
) -> List[Any]:
    """Place twig objects at positions defined by twig attributes on tree mesh.

    Args:
        tree_mesh: Blender mesh object with twig attributes
        twig_objects: Dictionary mapping twig types to Blender objects:
                     {'twig_long': obj, 'twig_short': obj, ...}
        use_instances: If True, use linked duplicates; if False, use copies

    Returns:
        List of created twig instance objects
    """
    if not BPY_AVAILABLE:
        raise ImportError("bpy (Blender Python) required")

    # Extract placement data
    placements = extract_twig_placements_from_mesh(tree_mesh.data)

    created_objects = []

    # Place twigs for each type
    for twig_type, placement_list in placements.items():
        if not placement_list:
            continue

        if twig_type not in twig_objects or twig_objects[twig_type] is None:
            print(f"Warning: No twig object provided for {twig_type}")
            continue

        twig_template = twig_objects[twig_type]

        for idx, placement in enumerate(placement_list):
            # Create instance or copy
            if use_instances:
                twig_instance = bpy.data.objects.new(
                    f"{twig_type}_{idx}", twig_template.data  # Share mesh data
                )
            else:
                twig_instance = twig_template.copy()
                twig_instance.data = twig_template.data.copy()
                twig_instance.name = f"{twig_type}_{idx}"

            # Link to scene
            bpy.context.collection.objects.link(twig_instance)

            # Set position
            twig_instance.location = placement["position"]

            # Set rotation from normal
            # Convert rotation matrix to Euler angles
            import mathutils

            rot_mat = mathutils.Matrix(placement["rotation_matrix"])
            twig_instance.rotation_euler = rot_mat.to_euler()

            created_objects.append(twig_instance)

    print(f"Created {len(created_objects)} twig instances")
    return created_objects


def extract_twig_placements_from_usd(
    tree_usd_path: Path,
) -> Dict[str, List[Dict[str, Any]]]:
    """Extract twig placement data directly from USD file using pxr.

    Args:
        tree_usd_path: Path to tree USD file with twig attributes

    Returns:
        Dictionary mapping twig types to placement data
    """
    # Check USD availability
    usd_ok, error_msg = _check_usd_available()
    if not usd_ok:
        print(error_msg)
        return {}

    # Import USD here to avoid DLL issues on Windows at module load time
    from pxr import Usd, UsdGeom

    placements = {"twig_long": [], "twig_short": [], "twig_upward": [], "twig_dead": []}

    try:
        # Open USD stage
        stage = Usd.Stage.Open(str(tree_usd_path))

        # Find mesh prims
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue

            mesh = UsdGeom.Mesh(prim)

            # Get mesh data
            points_attr = mesh.GetPointsAttr()
            if not points_attr:
                continue

            points = points_attr.Get()
            face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
            face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

            # Look for twig attributes
            for twig_type in ["twig_long", "twig_short", "twig_upward", "twig_dead"]:
                # Try to get primvar (USD attribute)
                # GetPrimvarsAPI() is on UsdGeomImageable (parent of Mesh)
                primvars_api = UsdGeom.PrimvarsAPI(mesh)
                primvar = primvars_api.GetPrimvar(twig_type)
                if not primvar or not primvar.HasValue():
                    continue

                twig_values = primvar.Get()
                interpolation = primvar.GetInterpolation()

                # Process faces with twig attributes
                if interpolation == UsdGeom.Tokens.uniform:  # Per-face
                    face_start = 0
                    for face_idx, face_count in enumerate(face_vertex_counts):
                        # Check if this face has twig attribute
                        if face_idx < len(twig_values) and twig_values[face_idx]:
                            # Get face vertex indices
                            face_indices = face_vertex_indices[
                                face_start : face_start + face_count
                            ]
                            face_verts = [points[i] for i in face_indices]

                            # Calculate center
                            center = [
                                sum(v[0] for v in face_verts) / len(face_verts),
                                sum(v[1] for v in face_verts) / len(face_verts),
                                sum(v[2] for v in face_verts) / len(face_verts),
                            ]

                            # Calculate normal using Newell's method
                            normal = [0.0, 0.0, 0.0]
                            for i in range(len(face_verts)):
                                v1 = face_verts[i]
                                v2 = face_verts[(i + 1) % len(face_verts)]
                                normal[0] += (v1[1] - v2[1]) * (v1[2] + v2[2])
                                normal[1] += (v1[2] - v2[2]) * (v1[0] + v2[0])
                                normal[2] += (v1[0] - v2[0]) * (v1[1] + v2[1])

                            # Normalize
                            length = math.sqrt(sum(n * n for n in normal))
                            if length > 0:
                                normal = [n / length for n in normal]
                            else:
                                normal = [0.0, 0.0, 1.0]

                            # IMPORTANT: Negate the normal to point outward from the tree surface
                            # The mesh winding order produces inward-facing normals, but twigs
                            # need to point outward away from the branch surface
                            normal = [-n for n in normal]

                            # NOTE: No coordinate conversion needed!
                            # The tree USD file is already exported in Z-up coordinates (upAxis = "Z"),
                            # so the vertex positions and normals are already in the correct coordinate
                            # system. The twigs should be placed using these coordinates directly.
                            center = tuple(center)
                            normal = tuple(normal)

                            # Create rotation matrix
                            rot_matrix = normal_to_rotation_matrix(normal)

                            placement_data = {
                                "position": center,
                                "normal": normal,
                                "rotation_matrix": rot_matrix,
                                "face_index": face_idx,
                            }

                            placements[twig_type].append(placement_data)

                        face_start += face_count

        # Print summary
        for twig_type, places in placements.items():
            if places:
                print(f"  Found {len(places)} {twig_type} placements")

    except Exception as e:
        print(f"Error extracting twig placements from USD: {e}")
        import traceback

        traceback.print_exc()

    return placements


def export_twig_placements_to_usd(
    tree_usd_path: Path,
    twig_usd_paths: Dict[str, Path],
    output_path: Path,
    tree_mesh: Optional[Any] = None,
    extract_from_usd: bool = True,
    use_point_instancer: bool = True,
    convert_to_ue: bool = True,
) -> bool:
    """Create USD file with tree and instanced twigs using UsdGeomPointInstancer.

    This creates a USD assembly with the tree mesh and twig instances placed
    according to the twig attributes on the tree mesh. Uses USD's PointInstancer
    for memory-efficient instancing compatible with Unreal Engine Nanite.

    Args:
        tree_usd_path: Path to tree mesh USD file
        twig_usd_paths: Dictionary mapping twig types to USD paths:
                       {'twig_long': Path, 'twig_short': Path, ...}
        output_path: Output path for assembly USD
        tree_mesh: Optional Blender mesh with twig attributes for placement
        extract_from_usd: If True and tree_mesh is None, extract from USD via pxr
        use_point_instancer: If True, use UsdGeomPointInstancer; if False, use individual Xforms
        convert_to_ue: If True, convert coordinates from Blender to Unreal Engine

    Returns:
        Success status
    """
    # Check USD availability early to provide good error messages
    usd_ok, error_msg = _check_usd_available()
    if not usd_ok:
        print(error_msg)
        return False

    # Import USD here to avoid DLL issues on Windows at module load time
    from pxr import Gf, Sdf, Usd, UsdGeom

    try:
        # Extract placements
        placements = None

        if tree_mesh and BPY_AVAILABLE:
            placements = extract_twig_placements_from_mesh(tree_mesh)
        elif extract_from_usd:
            # Extract directly from USD using pxr (no Blender needed)
            print(f"  Extracting twig placements from USD: {tree_usd_path.name}")
            placements = extract_twig_placements_from_usd(tree_usd_path)

        if not placements:
            print("Warning: No placement data available, creating tree-only assembly")
            placements = {}

        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata to match tree-only USD (Z-up, meters)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        # Create root
        root_prim = stage.DefinePrim("/TreeAssembly", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Reference tree mesh with absolute path
        tree_prim = stage.DefinePrim("/TreeAssembly/Tree", "Xform")
        tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))

        # Add Nanite support to tree
        tree_prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set(
            "enable"
        )

        # NOTE: Do NOT convert tree coordinates here - the tree_only USD is already
        # in Blender Z-up coordinates, and we want the assembly to maintain the same
        # coordinate system. UE will import Z-up correctly.
        # The convert_to_ue flag is only used for twig instance positions/orientations
        # when they're being placed programmatically.

        if use_point_instancer:
            # Use UsdGeomPointInstancer for memory-efficient instancing
            return _export_with_point_instancer(
                stage, placements, twig_usd_paths, convert_to_ue
            )
        else:
            # Use individual Xforms (fallback for compatibility)
            return _export_with_xforms(stage, placements, twig_usd_paths, convert_to_ue)

    except Exception as e:
        print(f"Failed to export USD with twig placements: {e}")
        import traceback

        traceback.print_exc()
        return False


def _export_with_point_instancer(
    stage: Any,
    placements: Dict[str, List[Dict[str, Any]]],
    twig_usd_paths: Dict[str, Path],
    convert_to_ue: bool,
) -> bool:
    """Export twigs using UsdGeomPointInstancer."""
    from pxr import Gf, Sdf, UsdGeom

    # Create prototypes group
    prototypes_group = stage.DefinePrim("/TreeAssembly/Prototypes", "Scope")

    # Map twig types to prototype indices
    twig_type_to_proto_idx = {}
    prototype_paths = []

    for idx, (twig_type, twig_path) in enumerate(sorted(twig_usd_paths.items())):
        if not twig_path.exists():
            print(f"Warning: Twig USD not found: {twig_path}")
            continue

        twig_type_to_proto_idx[twig_type] = idx

        # Create prototype prim (instanceable for memory efficiency)
        proto_prim = stage.DefinePrim(f"/TreeAssembly/Prototypes/{twig_type}", "Xform")
        proto_prim.SetInstanceable(True)

        # Reference twig mesh
        proto_prim.GetReferences().AddReference(str(twig_path.resolve()))

        # Add Nanite support with Preserve Area for foliage
        proto_prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set(
            "enable"
        )
        proto_prim.CreateAttribute(
            "unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool
        ).Set(True)

        prototype_paths.append(Sdf.Path(proto_prim.GetPath()))

    if not prototype_paths:
        print("Warning: No valid twig prototypes found")
        stage.GetRootLayer().Save()
        return False

    # Create PointInstancer
    instancer_prim = stage.DefinePrim("/TreeAssembly/TwigInstances", "PointInstancer")
    instancer = UsdGeom.PointInstancer(instancer_prim)

    # Set prototypes relationship
    instancer.CreatePrototypesRel().SetTargets(prototype_paths)

    # Collect instance data
    all_positions = []
    all_orientations = []
    all_scales = []
    all_proto_indices = []

    total_placed = 0
    for twig_type, placement_list in placements.items():
        if not placement_list or twig_type not in twig_type_to_proto_idx:
            continue

        proto_idx = twig_type_to_proto_idx[twig_type]

        for placement in placement_list:
            pos = placement["position"]
            rot_matrix = placement["rotation_matrix"]

            # NOTE: Coordinate conversion NOT needed here!
            # The placements are already extracted from the tree USD which has been
            # converted from Grove's Y-up to Z-up. The twigs should match the tree's
            # coordinate system exactly. Both tree and twigs are in Z-up Blender coords.
            # UE will import Z-up correctly without additional conversion.
            #
            # If convert_to_ue flag is True, it's likely for a different export path
            # (direct Blender export), not for USD-extracted placements.
            pass  # Keep original position and rotation

            # Convert rotation matrix to quaternion
            quat = rotation_matrix_to_quaternion(rot_matrix)

            # Add to arrays
            all_positions.append(Gf.Vec3f(pos[0], pos[1], pos[2]))

            # Use GfQuath for half-precision quaternions (USD requirement)
            # Note: pxr uses (real, i, j, k) = (w, x, y, z)
            all_orientations.append(Gf.Quath(quat[0], quat[1], quat[2], quat[3]))

            all_scales.append(Gf.Vec3f(1.0, 1.0, 1.0))
            all_proto_indices.append(proto_idx)
            total_placed += 1

    # Set PointInstancer attributes
    instancer.CreatePositionsAttr().Set(all_positions)
    instancer.CreateOrientationsAttr().Set(all_orientations)
    instancer.CreateScalesAttr().Set(all_scales)
    instancer.CreateProtoIndicesAttr().Set(all_proto_indices)

    # Save stage
    stage.GetRootLayer().Save()
    print(f"  Created USD assembly with PointInstancer ({total_placed} twig instances)")
    print(f"    Prototypes: {len(prototype_paths)}")
    print(f"    Positions: {len(all_positions)}")
    print(f"    Using half-precision quaternions (quath) for rotations")
    return True


def _export_with_xforms(
    stage: Any,
    placements: Dict[str, List[Dict[str, Any]]],
    twig_usd_paths: Dict[str, Path],
    convert_to_ue: bool,
) -> bool:
    """Export twigs using individual Xforms (fallback method)."""
    from pxr import Gf, Sdf, UsdGeom

    # Create twigs group
    twigs_group = stage.DefinePrim("/TreeAssembly/Twigs", "Xform")

    # Place each twig type
    total_placed = 0
    for twig_type, placement_list in placements.items():
        if not placement_list or twig_type not in twig_usd_paths:
            continue

        twig_usd_path = twig_usd_paths[twig_type]
        if not twig_usd_path or not twig_usd_path.exists():
            print(f"Warning: Twig USD not found for {twig_type}: {twig_usd_path}")
            continue

        # Create group for this twig type
        type_group = stage.DefinePrim(f"/TreeAssembly/Twigs/{twig_type}", "Xform")

        # Place instances
        for idx, placement in enumerate(placement_list):
            instance_prim = stage.DefinePrim(
                f"/TreeAssembly/Twigs/{twig_type}/instance_{idx}", "Xform"
            )

            # Reference twig mesh with absolute path
            instance_prim.GetReferences().AddReference(str(twig_usd_path.resolve()))

            # Add Nanite properties
            instance_prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set(
                "enable"
            )
            instance_prim.CreateAttribute(
                "unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool
            ).Set(True)

            # Set transform
            xform = UsdGeom.Xform(instance_prim)

            pos = placement["position"]
            rot_matrix = placement["rotation_matrix"]

            # NOTE: Coordinate conversion NOT needed - see note in _export_with_point_instancer
            # Placements from USD extraction are already in the same coordinate system as the tree

            # Set translation
            xform.AddTranslateOp().Set(Gf.Vec3d(pos[0], pos[1], pos[2]))

            # Set rotation from matrix
            gf_matrix = Gf.Matrix3d(
                rot_matrix[0][0],
                rot_matrix[0][1],
                rot_matrix[0][2],
                rot_matrix[1][0],
                rot_matrix[1][1],
                rot_matrix[1][2],
                rot_matrix[2][0],
                rot_matrix[2][1],
                rot_matrix[2][2],
            )
            rotation = Gf.Rotation(gf_matrix)
            xform.AddRotateXYZOp().Set(Gf.Vec3f(*rotation.Decompose()[0]))

            total_placed += 1

    # Save stage
    stage.GetRootLayer().Save()
    print(f"  Created USD assembly with {total_placed} twig instances (Xforms)")
    return True


def create_geometry_nodes_twig_instancer(
    tree_object: Any, twig_collections: Dict[str, Any]
) -> Any:
    """Create Blender Geometry Nodes setup for twig instancing.

    This creates a non-destructive Geometry Nodes modifier that instances
    twigs based on face attributes. This is the recommended approach for
    Blender as it's memory-efficient and non-destructive.

    Args:
        tree_object: Blender object with tree mesh and twig attributes
        twig_collections: Dict mapping twig types to Blender collections

    Returns:
        The Geometry Nodes modifier
    """
    if not BPY_AVAILABLE:
        raise ImportError("bpy required for Geometry Nodes")

    # Add Geometry Nodes modifier
    modifier = tree_object.modifiers.new(name="TwigInstancer", type="NODES")

    # Create new node tree
    node_tree = bpy.data.node_groups.new("TwigInstancerNodes", "GeometryNodeTree")
    modifier.node_group = node_tree

    # Create nodes
    nodes = node_tree.nodes
    links = node_tree.links

    # Input/Output nodes
    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")
    input_node.location = (-400, 0)
    output_node.location = (400, 0)

    # Create tree interface sockets
    node_tree.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    node_tree.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )

    # For each twig type, create instance chain
    y_offset = 0
    join_nodes = []

    for twig_type in ["twig_long", "twig_short", "twig_upward", "twig_dead"]:
        if twig_type not in twig_collections or not twig_collections[twig_type]:
            continue

        # Separate by attribute
        separate_node = nodes.new("GeometryNodeSeparateGeometry")
        separate_node.location = (-200, y_offset)
        separate_node.domain = "FACE"

        # Named Attribute node for selection
        attr_node = nodes.new("GeometryNodeInputNamedAttribute")
        attr_node.location = (-400, y_offset - 100)
        attr_node.data_type = "BOOLEAN"
        attr_node.inputs[0].default_value = twig_type

        # Mesh to Points
        to_points = nodes.new("GeometryNodeMeshToPoints")
        to_points.location = (0, y_offset)
        to_points.mode = "FACES"

        # Instance on Points
        instance_node = nodes.new("GeometryNodeInstanceOnPoints")
        instance_node.location = (200, y_offset)

        # Collection Info for twig
        collection_info = nodes.new("GeometryNodeCollectionInfo")
        collection_info.location = (0, y_offset - 200)
        collection_info.inputs[0].default_value = twig_collections[twig_type]
        collection_info.transform_space = "RELATIVE"

        # Connect nodes
        links.new(input_node.outputs[0], separate_node.inputs[0])
        links.new(attr_node.outputs[0], separate_node.inputs[1])
        links.new(separate_node.outputs[0], to_points.inputs[0])
        links.new(to_points.outputs[0], instance_node.inputs[0])
        links.new(collection_info.outputs[0], instance_node.inputs[2])

        join_nodes.append(instance_node)
        y_offset -= 400

    # Join all instances
    if len(join_nodes) > 1:
        join_geo = nodes.new("GeometryNodeJoinGeometry")
        join_geo.location = (400, 0)
        for i, node in enumerate(join_nodes):
            links.new(node.outputs[0], join_geo.inputs[0])
        links.new(join_geo.outputs[0], output_node.inputs[0])
    elif len(join_nodes) == 1:
        links.new(join_nodes[0].outputs[0], output_node.inputs[0])

    print(f"Created Geometry Nodes twig instancer with {len(join_nodes)} twig types")
    return modifier
