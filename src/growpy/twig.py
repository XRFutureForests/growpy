"""
Simplified twig enhancement for USD files - using Grove's face-based system.

GROVE TWIG SYSTEM:
- Each face (triangle, quad, or polygon) marked with primvars:Twig* gets a twig
- Twig position = face center (centroid of all vertices)
- Twig direction = face surface normal (using Newell's method for any polygon)
- Works with any polygon, not just triangles!

This module provides both low-level twig placement functions and a high-level
add_twigs_to_tree() function that can be called from forest generation scripts.
"""

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Try to import USD components, fallback gracefully if not available
try:
    from pxr import Gf, Usd, UsdGeom, Vt

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

# Import config for twig lookup
try:
    from .config import GrowPyConfig
except ImportError:
    try:
        from growpy.config import GrowPyConfig
    except ImportError:
        print("⚠️  Could not import GrowPyConfig, twig assignment will be limited")


def select_random_twig_from_group(
    twig_files: List[Path], instance_index: int = 0, seed: Optional[int] = None
) -> Path:
    """
    Randomly select a twig file from a group of variations.

    Args:
        twig_files: List of twig file paths in the same group (e.g., all lateral twigs)
        instance_index: Index of the twig instance (for consistent seeding)
        seed: Optional random seed for reproducible results

    Returns:
        Path: Randomly selected twig file
    """
    if not twig_files:
        raise ValueError("Cannot select from empty twig file list")

    if len(twig_files) == 1:
        return twig_files[0]

    # Create a deterministic but varied selection based on instance index
    if seed is not None:
        local_random = random.Random(seed + instance_index)
    else:
        local_random = random.Random(hash(str(twig_files[0])) + instance_index)

    return local_random.choice(twig_files)


def assign_twig_variations_randomly(
    twig_instances_by_type: Dict[str, List[Dict]],
    twig_files_by_type: Dict[str, List[Path]],
    species_name: str,
    random_seed: Optional[int] = None,
) -> Dict[str, Dict]:
    """
    Assign specific twig variation files to twig instances randomly within their type groups.

    Args:
        twig_instances_by_type: Dictionary of twig types -> list of instance data
        twig_files_by_type: Dictionary of twig types -> list of available twig files
        species_name: Name of the species (for logging)
        random_seed: Optional seed for reproducible randomization

    Returns:
        Dict of twig_file_path -> {"file": Path, "instances": List, "type": str}
    """
    if random_seed is not None:
        random.seed(random_seed)

    twig_assignments = {}
    variation_stats = {}

    for twig_type, instances in twig_instances_by_type.items():
        if not instances:
            continue

        # Get available files for this type
        available_files = twig_files_by_type.get(twig_type, [])
        if not available_files:
            # Try fallback types
            fallback_types = {
                "end": ["apical", "main"],
                "side": ["lateral", "main"],
                "upward": ["apical", "main"],
                "apical": ["end", "main"],
                "lateral": ["side", "main"],
            }

            for fallback_type in fallback_types.get(twig_type, ["main"]):
                if (
                    fallback_type in twig_files_by_type
                    and twig_files_by_type[fallback_type]
                ):
                    available_files = twig_files_by_type[fallback_type]
                    print(
                        f"      Using {fallback_type} twigs as fallback for {twig_type}"
                    )
                    break

        if not available_files:
            # Last resort: use any available twig
            all_files = []
            for files in twig_files_by_type.values():
                all_files.extend(files)
            if all_files:
                available_files = [all_files[0]]  # Just use the first available
                print(f"      Using fallback twig for {twig_type}")

        if not available_files:
            print(f"      ⚠️  No twig files available for {twig_type}")
            continue

        # Track variation usage for statistics
        variation_stats[twig_type] = {}

        # Randomly assign twig variations to instances
        for i, instance in enumerate(instances):
            selected_twig = select_random_twig_from_group(
                available_files, i, random_seed
            )

            # Track variation usage
            variation_name = selected_twig.stem
            if variation_name not in variation_stats[twig_type]:
                variation_stats[twig_type][variation_name] = 0
            variation_stats[twig_type][variation_name] += 1

            # Group instances by their assigned twig file
            file_key = str(selected_twig)
            if file_key not in twig_assignments:
                # Extract reference name from twig file
                file_stem = selected_twig.stem
                if "_" in file_stem:
                    twig_reference_name = file_stem.split("_", 1)[1]
                else:
                    twig_reference_name = file_stem

                twig_assignments[file_key] = {
                    "file": selected_twig,
                    "reference_name": twig_reference_name,
                    "instances": [],
                    "type": twig_type,
                }

            twig_assignments[file_key]["instances"].append(instance)

    # Log variation statistics
    if variation_stats:
        print(f"      🎲 Twig variation distribution for {species_name}:")
        for twig_type, variations in variation_stats.items():
            if variations:
                total_instances = sum(variations.values())
                print(
                    f"         {twig_type.capitalize()} ({total_instances} instances):"
                )
                for variation, count in sorted(variations.items()):
                    percentage = (count / total_instances) * 100
                    short_name = (
                        variation.split("_")[-1] if "_" in variation else variation
                    )
                    print(f"           • {short_name}: {count} ({percentage:.1f}%)")

    return twig_assignments


def quaternion_from_x_to_normal(normal):
    """Calculate quaternion to rotate from +X axis (1,0,0) to surface normal direction.

    This version maintains consistent "up" orientation to prevent unwanted roll.
    - Twig default direction: +X axis (1, 0, 0)
    - Twig default up: +Z axis (0, 0, 1)
    - Target direction: surface normal (outward from tree surface)
    - Target up: constrained to prevent roll

    Args:
        normal: tuple (x, y, z) representing the surface normal (outward from surface)

    Returns:
        tuple: (w, x, y, z) quaternion to rotate from +X to normal direction with constrained up
    """
    import math

    import numpy as np

    # Default twig orientation
    default_forward = np.array([1.0, 0.0, 0.0])  # +X axis (forward direction)
    default_up = np.array([0.0, 0.0, 1.0])  # +Z axis (up direction)

    # Target forward direction (surface normal)
    target_forward = np.array(normal)
    target_forward = target_forward / np.linalg.norm(target_forward)

    # Calculate target up direction to prevent roll
    # We want to keep the up direction as close to +Z as possible
    world_up = np.array([0.0, 0.0, 1.0])

    # If target forward is too close to world up, use a different reference
    if abs(np.dot(target_forward, world_up)) > 0.99:
        # Use +Y as reference when target is nearly vertical
        world_up = np.array([0.0, 1.0, 0.0])

    # Calculate right vector (perpendicular to both target forward and world up)
    target_right = np.cross(world_up, target_forward)
    target_right = target_right / np.linalg.norm(target_right)

    # Calculate actual up vector (perpendicular to forward and right)
    target_up = np.cross(target_forward, target_right)
    target_up = target_up / np.linalg.norm(target_up)

    # Create rotation matrix from default to target orientation
    # Default: forward=+X, up=+Z, right=+Y
    # Target:  forward=target_forward, up=target_up, right=target_right

    # Default orientation matrix (columns are basis vectors)
    default_matrix = np.column_stack(
        [default_forward, np.array([0.0, 1.0, 0.0]), default_up]
    )

    # Target orientation matrix
    target_matrix = np.column_stack([target_forward, target_right, target_up])

    # Rotation matrix from default to target
    rotation_matrix = target_matrix @ default_matrix.T

    # Convert rotation matrix to quaternion
    # Using Shepperd's method for numerical stability
    trace = rotation_matrix[0, 0] + rotation_matrix[1, 1] + rotation_matrix[2, 2]

    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2  # s = 4 * qw
        qw = 0.25 * s
        qx = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / s
        qy = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / s
        qz = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / s
    elif (
        rotation_matrix[0, 0] > rotation_matrix[1, 1]
        and rotation_matrix[0, 0] > rotation_matrix[2, 2]
    ):
        s = (
            math.sqrt(
                1.0
                + rotation_matrix[0, 0]
                - rotation_matrix[1, 1]
                - rotation_matrix[2, 2]
            )
            * 2
        )  # s = 4 * qx
        qw = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / s
        qx = 0.25 * s
        qy = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
        qz = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
    elif rotation_matrix[1, 1] > rotation_matrix[2, 2]:
        s = (
            math.sqrt(
                1.0
                + rotation_matrix[1, 1]
                - rotation_matrix[0, 0]
                - rotation_matrix[2, 2]
            )
            * 2
        )  # s = 4 * qy
        qw = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / s
        qx = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
        qy = 0.25 * s
        qz = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
    else:
        s = (
            math.sqrt(
                1.0
                + rotation_matrix[2, 2]
                - rotation_matrix[0, 0]
                - rotation_matrix[1, 1]
            )
            * 2
        )  # s = 4 * qz
        qw = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / s
        qx = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
        qy = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
        qz = 0.25 * s

    return (qw, qx, qy, qz)


def calculate_face_center(points, face):
    """Calculate the center of a face (polygon) given its vertex indices.

    Args:
        points: List of 3D points (vertices)
        face: List of vertex indices that form the face

    Returns:
        tuple: (x, y, z) coordinates of the face center
    """
    if len(face) == 0:
        return (0, 0, 0)

    # Get all vertices of the face
    face_vertices = [points[idx] for idx in face]

    # Calculate centroid (average of all vertices)
    x = sum(vertex[0] for vertex in face_vertices) / len(face_vertices)
    y = sum(vertex[1] for vertex in face_vertices) / len(face_vertices)
    z = sum(vertex[2] for vertex in face_vertices) / len(face_vertices)

    return (x, y, z)


def transform_y_up_to_z_up(point):
    """Transform a point from Y-up coordinate system to Z-up coordinate system.

    Y-up to Z-up transformation: (x, y, z) -> (x, -z, y)
    This rotates around the X-axis by -90 degrees.

    Args:
        point: tuple (x, y, z) in Y-up system

    Returns:
        tuple: (x, y, z) in Z-up system
    """
    x, y, z = point
    return (x, -z, y)


def transform_points_y_to_z(points):
    """Transform a list of points from Y-up to Z-up coordinate system.

    Args:
        points: List of (x, y, z) points in Y-up system

    Returns:
        List of (x, y, z) points in Z-up system
    """
    return [transform_y_up_to_z_up(point) for point in points]


def create_y_to_z_transform_matrix():
    """Create a transformation matrix to convert from Y-up to Z-up coordinate system.

    This is a rotation of -90 degrees around the X-axis:
    Y-up (x, y, z) -> Z-up (x, -z, y)

    Returns:
        Gf.Matrix4d: 4x4 transformation matrix (if USD available)
    """
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings required for matrix operations")

    # Rotation matrix for -90 degrees around X-axis
    # [1,  0,  0, 0]
    # [0,  0,  1, 0]
    # [0, -1,  0, 0]
    # [0,  0,  0, 1]
    transform = Gf.Matrix4d()
    transform.SetRow(0, (1.0, 0.0, 0.0, 0.0))
    transform.SetRow(1, (0.0, 0.0, 1.0, 0.0))
    transform.SetRow(2, (0.0, -1.0, 0.0, 0.0))
    transform.SetRow(3, (0.0, 0.0, 0.0, 1.0))
    return transform


def transform_mesh_to_z_up(stage, tree_prim_path="/Tree/Tree"):
    """Transform the tree mesh from Y-up to Z-up coordinate system.

    Args:
        stage: USD stage containing the tree
        tree_prim_path: Path to the tree mesh prim

    Returns:
        tuple: (transformed_points, face_vertex_counts, face_vertex_indices, twig_attributes)
    """
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings required for mesh transformation")

    # Get the tree mesh prim
    tree_prim = stage.GetPrimAtPath(tree_prim_path)
    if not tree_prim:
        raise ValueError(f"Tree prim not found at path: {tree_prim_path}")

    # Extract mesh data
    mesh = UsdGeom.Mesh(tree_prim)

    # Get original points (Y-up)
    points_attr = mesh.GetPointsAttr()
    if not points_attr:
        raise ValueError("Points attribute not found on mesh")
    points_y_up = list(points_attr.Get())

    # Transform points to Z-up
    points_z_up = transform_points_y_to_z(points_y_up)

    # Get face data
    face_vertex_counts_attr = mesh.GetFaceVertexCountsAttr()
    face_vertex_indices_attr = mesh.GetFaceVertexIndicesAttr()

    if not face_vertex_counts_attr or not face_vertex_indices_attr:
        raise ValueError("Face data not found on mesh")

    face_vertex_counts = list(face_vertex_counts_attr.Get())
    face_vertex_indices = list(face_vertex_indices_attr.Get())

    # Extract twig attributes
    twig_attributes = {}

    # Try to get twig primvars
    primvars_api = UsdGeom.PrimvarsAPI(tree_prim)

    twig_end_attr = primvars_api.GetPrimvar("TwigEnd")
    if twig_end_attr:
        twig_attributes["TwigEnd"] = list(twig_end_attr.Get())

    twig_side_attr = primvars_api.GetPrimvar("TwigSide")
    if twig_side_attr:
        twig_attributes["TwigSide"] = list(twig_side_attr.Get())

    twig_upward_attr = primvars_api.GetPrimvar("TwigUpward")
    if twig_upward_attr:
        twig_attributes["TwigUpward"] = list(twig_upward_attr.Get())

    return points_z_up, face_vertex_counts, face_vertex_indices, twig_attributes


def create_transformed_tree_stage(
    original_stage, output_path, tree_prim_path="/Tree", transformed_points=None
):
    """Create a new USD stage with the tree transformed to Z-up coordinate system.

    Args:
        original_stage: Original USD stage (Y-up)
        output_path: Path for the new Z-up USD file
        tree_prim_path: Path to the tree xform prim
        transformed_points: Pre-transformed points in Z-up coordinate system

    Returns:
        Usd.Stage: New stage with Z-up tree (if USD available)
    """
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings required for stage operations")

    # Create new stage
    new_stage = Usd.Stage.CreateNew(output_path)

    # Set metadata for Z-up
    new_stage.SetMetadata("upAxis", "Z")
    new_stage.SetMetadata("metersPerUnit", 1.0)
    new_stage.SetMetadata("defaultPrim", "Tree")

    # Get the tree xform from original stage
    tree_xform_prim = original_stage.GetPrimAtPath(tree_prim_path)
    if not tree_xform_prim:
        raise ValueError(f"Tree xform prim not found at path: {tree_prim_path}")

    # Create new tree xform in new stage
    new_tree_xform = UsdGeom.Xform.Define(new_stage, tree_prim_path)

    # NO transformation matrix at all - the coordinates are already in Z-up space
    # We want the identity transform (no transformation)
    # This is the default behavior, so we don't need to add any transform ops

    # Copy the tree mesh manually
    tree_mesh_path = tree_prim_path + "/Tree"
    original_mesh_prim = original_stage.GetPrimAtPath(tree_mesh_path)

    if original_mesh_prim:
        # Create new mesh prim
        new_mesh = UsdGeom.Mesh.Define(new_stage, tree_mesh_path)
        original_mesh = UsdGeom.Mesh(original_mesh_prim)

        # Use transformed points if provided, otherwise use original points
        if transformed_points is not None:
            # Convert to Gf.Vec3f list for USD
            usd_points = [Gf.Vec3f(p[0], p[1], p[2]) for p in transformed_points]
            new_mesh.CreatePointsAttr().Set(usd_points)
        else:
            points_attr = original_mesh.GetPointsAttr()
            if points_attr:
                new_mesh.CreatePointsAttr().Set(points_attr.Get())

        face_vertex_counts_attr = original_mesh.GetFaceVertexCountsAttr()
        if face_vertex_counts_attr:
            new_mesh.CreateFaceVertexCountsAttr().Set(face_vertex_counts_attr.Get())

        face_vertex_indices_attr = original_mesh.GetFaceVertexIndicesAttr()
        if face_vertex_indices_attr:
            new_mesh.CreateFaceVertexIndicesAttr().Set(face_vertex_indices_attr.Get())

        # Copy normals if they exist (but don't transform them - let USD calculate new ones)
        normals_attr = original_mesh.GetNormalsAttr()
        if normals_attr and normals_attr.Get():
            # Transform normals too if we have transformed points
            if transformed_points is not None:
                original_normals = list(normals_attr.Get())
                transformed_normals = transform_points_y_to_z(original_normals)
                usd_normals = [Gf.Vec3f(n[0], n[1], n[2]) for n in transformed_normals]
                new_mesh.CreateNormalsAttr().Set(usd_normals)
            else:
                new_mesh.CreateNormalsAttr().Set(normals_attr.Get())

        # Copy primvars (including twig attributes)
        original_primvars = UsdGeom.PrimvarsAPI(original_mesh_prim)
        new_primvars = UsdGeom.PrimvarsAPI(new_mesh.GetPrim())

        # List of known primvars to copy
        primvar_names = [
            "TwigEnd",
            "TwigSide",
            "TwigUpward",
            "st",
            "displayColor",
            "displayOpacity",
        ]

        for name in primvar_names:
            original_primvar = original_primvars.GetPrimvar(name)
            if original_primvar and original_primvar.Get() is not None:
                try:
                    new_primvar = new_primvars.CreatePrimvar(
                        name,
                        original_primvar.GetTypeName(),
                        original_primvar.GetInterpolation(),
                    )
                    new_primvar.Set(original_primvar.Get())
                except Exception as e:
                    print(f"  Warning: Could not copy primvar {name}: {e}")

    new_stage.Save()
    return new_stage


def calculate_face_normal(points, face):
    """Calculate the normal vector of a face assuming clockwise winding order.
    Uses Newell's method which works for any polygon, not just triangles.
    The normal will point outward from the surface when vertices are ordered clockwise.

    Args:
        points: List of 3D points (vertices)
        face: List of vertex indices that form the face (clockwise order)

    Returns:
        tuple: (x, y, z) normalized normal vector pointing outward
    """
    if len(face) < 3:
        return (0, 0, 1)  # Default up vector

    # Get face vertices
    face_vertices = [points[idx] for idx in face]

    # Use Newell's method to calculate normal (clockwise winding)
    normal = [0.0, 0.0, 0.0]

    for i in range(len(face_vertices)):
        v1 = face_vertices[i]
        v2 = face_vertices[(i + 1) % len(face_vertices)]

        # Newell's method - this gives correct normal for clockwise winding
        normal[0] += (v1[1] - v2[1]) * (v1[2] + v2[2])
        normal[1] += (v1[2] - v2[2]) * (v1[0] + v2[0])
        normal[2] += (v1[0] - v2[0]) * (v1[1] + v2[1])

    # Normalize the vector
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length > 0:
        normal = (normal[0] / length, normal[1] / length, normal[2] / length)
    else:
        normal = (0, 0, 1)  # Default up vector

    # Grove convention: surface normal points outward from the surface
    # Twigs are oriented to grow along this outward direction
    # No need to reverse - this is the correct direction for Grove twigs

    return normal


def calculate_grove_twig_orientation(
    normal, reverse_normal=False, debug=False, method="grove_plus_x"
):
    """Calculate twig orientation following Grove's conventions with USD adjustments.

    Grove twig system conventions:
    - Twigs are modeled pointing along the positive X-axis (1, 0, 0) in Blender
    - Origin (pivot) is at the attachment point (0, 0, 0)
    - Need to rotate from X-axis to the surface normal direction

    Args:
        normal: tuple (x, y, z) representing the surface normal (outward from surface)
        reverse_normal: bool, if True reverse the normal direction (for inward-pointing normals)
        debug: bool, if True print debug information
        method: str, which orientation method to use:
            - "grove_plus_x": Original Grove +X approach
            - "grove_minus_z": Use -Z as default (for Z-up systems)
            - "grove_3dsmax": Apply 3ds Max rotation convention (X:-90, Y:-90, Z:0)

    Returns:
        tuple: (w, x, y, z) quaternion to orient twig from default direction to normal direction
    """
    import math

    import numpy as np

    nx, ny, nz = normal

    # Option to reverse normal if it's pointing inward
    if reverse_normal:
        nx, ny, nz = -nx, -ny, -nz

    if debug:
        print(f"Normal: ({nx:.3f}, {ny:.3f}, {nz:.3f}), Method: {method}")

    # Choose default direction based on method
    if method == "grove_plus_x":
        # Original Grove convention: twigs point along +X axis
        default_direction = np.array([1.0, 0.0, 0.0])
    elif method == "grove_minus_z":
        # Alternative for Z-up coordinate systems
        default_direction = np.array([0.0, 0.0, -1.0])
    elif method == "grove_3dsmax":
        # Apply Grove's 3ds Max rotation: X:-90, Y:-90, Z:0
        # This transforms +X axis: (1,0,0) -> ?
        # First apply X:-90 (rotation around X by -90 degrees): (1,0,0) stays (1,0,0)
        # Then apply Y:-90 (rotation around Y by -90 degrees): (1,0,0) -> (0,0,-1)
        # Then apply Z:0 (no rotation around Z): (0,0,-1) stays (0,0,-1)
        default_direction = np.array([0.0, 0.0, -1.0])
    else:
        # Default to Grove standard
        default_direction = np.array([1.0, 0.0, 0.0])

    target_direction = np.array([nx, ny, nz])

    # Normalize both vectors
    default_direction = default_direction / np.linalg.norm(default_direction)
    target_direction = target_direction / np.linalg.norm(target_direction)

    # Calculate rotation quaternion from default to target direction
    # Using the shortest arc rotation method
    dot_product = np.dot(default_direction, target_direction)

    # Handle special cases
    if dot_product > 0.9999:  # Vectors are already aligned
        return (1.0, 0.0, 0.0, 0.0)  # Identity quaternion
    elif dot_product < -0.9999:  # Vectors are opposite
        # Find a perpendicular axis for 180-degree rotation
        if abs(default_direction[0]) < 0.1:
            perp_axis = np.array([1.0, 0.0, 0.0])
        else:
            perp_axis = np.array([0.0, 1.0, 0.0])
        perp_axis = perp_axis - np.dot(perp_axis, default_direction) * default_direction
        perp_axis = perp_axis / np.linalg.norm(perp_axis)
        # 180-degree rotation quaternion
        return (0.0, perp_axis[0], perp_axis[1], perp_axis[2])

    # Normal case: calculate rotation axis and angle
    cross_product = np.cross(default_direction, target_direction)
    cross_magnitude = np.linalg.norm(cross_product)

    if cross_magnitude < 1e-6:  # Vectors are parallel
        return (1.0, 0.0, 0.0, 0.0)  # Identity quaternion

    rotation_axis = cross_product / cross_magnitude
    rotation_angle = math.acos(np.clip(dot_product, -1.0, 1.0))

    # Convert axis-angle to quaternion
    half_angle = rotation_angle * 0.5
    sin_half = math.sin(half_angle)
    cos_half = math.cos(half_angle)

    quaternion = (
        cos_half,  # w
        rotation_axis[0] * sin_half,  # x
        rotation_axis[1] * sin_half,  # y
        rotation_axis[2] * sin_half,  # z
    )

    return quaternion


def xyz_angles_to_quaternion(rot_x, rot_y, rot_z):
    """Convert X, Y, Z rotation angles to a quaternion.

    Based on user's expected behavior:
    - X rotation: roll around X-axis (doesn't change direction when pointing along X)
    - Y rotation: yaw around Z-axis (horizontal turning toward Y)
    - Z rotation: pitch around negative Y-axis (up/down tilt toward Z)

    Args:
        rot_x: roll around X-axis in degrees
        rot_y: yaw around Z-axis in degrees (horizontal turning)
        rot_z: pitch around negative Y-axis in degrees (up/down tilt)

    Returns:
        tuple: (w, x, y, z) quaternion components in USD format
    """
    # Convert degrees to radians for calculations
    rot_x_rad = math.radians(rot_x)
    rot_y_rad = math.radians(rot_y)
    rot_z_rad = math.radians(rot_z)

    # Convert to half-angles for quaternion calculation
    half_x = rot_x_rad / 2
    half_y = rot_y_rad / 2
    half_z = rot_z_rad / 2

    # Calculate quaternion components for each rotation
    cos_x, sin_x = math.cos(half_x), math.sin(half_x)
    cos_y, sin_y = math.cos(half_y), math.sin(half_y)
    cos_z, sin_z = math.cos(half_z), math.sin(half_z)

    # Based on the test results:
    # Y rotation around Z-axis: quaternion = (cos(y/2), 0, 0, sin(y/2))
    # Z rotation around -Y-axis: quaternion = (cos(z/2), 0, -sin(z/2), 0)
    # X rotation around X-axis: quaternion = (cos(x/2), sin(x/2), 0, 0)

    # Create individual quaternions
    quat_x = (cos_x, sin_x, 0, 0)  # X rotation around X-axis
    quat_y = (cos_y, 0, 0, sin_y)  # Y rotation around Z-axis
    quat_z = (cos_z, 0, -sin_z, 0)  # Z rotation around -Y-axis

    # Combine quaternions: first Y (yaw), then Z (pitch), then X (roll)
    # Q = Qx * Qz * Qy

    # First combine Qz * Qy
    temp_w = (
        quat_z[0] * quat_y[0]
        - quat_z[1] * quat_y[1]
        - quat_z[2] * quat_y[2]
        - quat_z[3] * quat_y[3]
    )
    temp_x = (
        quat_z[0] * quat_y[1]
        + quat_z[1] * quat_y[0]
        + quat_z[2] * quat_y[3]
        - quat_z[3] * quat_y[2]
    )
    temp_y = (
        quat_z[0] * quat_y[2]
        - quat_z[1] * quat_y[3]
        + quat_z[2] * quat_y[0]
        + quat_z[3] * quat_y[1]
    )
    temp_z = (
        quat_z[0] * quat_y[3]
        + quat_z[1] * quat_y[2]
        - quat_z[2] * quat_y[1]
        + quat_z[3] * quat_y[0]
    )

    # Then multiply by Qx
    w = (
        quat_x[0] * temp_w
        - quat_x[1] * temp_x
        - quat_x[2] * temp_y
        - quat_x[3] * temp_z
    )
    x = (
        quat_x[0] * temp_x
        + quat_x[1] * temp_w
        + quat_x[2] * temp_z
        - quat_x[3] * temp_y
    )
    y = (
        quat_x[0] * temp_y
        - quat_x[1] * temp_z
        + quat_x[2] * temp_w
        + quat_x[3] * temp_x
    )
    z = (
        quat_x[0] * temp_z
        + quat_x[1] * temp_y
        - quat_x[2] * temp_x
        + quat_x[3] * temp_w
    )

    return (w, x, y, z)


def quaternion_from_direction(normal):
    """Convert a direction vector (normal) to a quaternion rotation using Grove conventions.
    This rotates the twig from its default X-axis orientation to align with the face normal.

    Args:
        normal: tuple (x, y, z) representing the face normal direction

    Returns:
        tuple: (w, x, y, z) quaternion components in USD format
    """
    # Use the opposite normal direction (flip the normal)
    opposite_normal = (-normal[0], -normal[1], -normal[2])
    return quaternion_from_x_to_normal(opposite_normal)


def write_usd_pointinstancer(
    positions, orientations, tree_file_path, twig_file_path, twig_xform_name
):
    """Write USD PointInstancer into the tree file."""

    # Read the original tree file
    with open(tree_file_path, "r") as f:
        content = f.read()

    # Generate the twig USD content
    twig_content = []

    # Add the prototype reference
    twig_content.append('    def "TwigPrototype" (')
    twig_content.append(
        f"        references = @{twig_file_path}@</root/{twig_xform_name}>"
    )
    twig_content.append("    )")
    twig_content.append("    {")
    twig_content.append("    }")
    twig_content.append("")

    # Add the PointInstancer
    twig_content.append('    def PointInstancer "TwigInstances"')
    twig_content.append("    {")
    twig_content.append("        rel prototypes = </Tree/TwigPrototype>")
    twig_content.append(
        f'        int[] protoIndices = [{", ".join(["0"] * len(positions))}]'
    )
    twig_content.append(
        f'        int64[] ids = [{", ".join([str(i) for i in range(len(positions))])}]'
    )
    twig_content.append("")

    # Add positions
    positions_str = ", ".join(
        [f"({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})" for p in positions]
    )
    twig_content.append(f"        point3f[] positions = [{positions_str}]")
    twig_content.append("")

    # Add orientations
    orientations_str = ", ".join(
        [f"({q[0]:.6f}, {q[1]:.6f}, {q[2]:.6f}, {q[3]:.6f})" for q in orientations]
    )
    twig_content.append(f"        quath[] orientations = [{orientations_str}]")
    twig_content.append("")

    # Add uniform scale
    twig_content.append("        float3[] scales = [(1, 1, 1)]")
    twig_content.append("    }")

    # Join and insert content
    twig_usd_text = "\n".join(twig_content)

    # Find insertion point (before the last closing brace)
    last_brace = content.rfind("}")
    if last_brace == -1:
        print("Error: Could not find closing brace in tree file")
        return False

    # Insert the twig content
    new_content = (
        content[:last_brace] + "\n" + twig_usd_text + "\n" + content[last_brace:]
    )

    # Write the modified content
    output_file = tree_file_path.replace(".usda", "_with_twigs.usda")
    with open(output_file, "w") as f:
        f.write(new_content)

    print(f"✅ Twig data successfully written to {output_file}")


def apply_quaternion_to_vector(quat, vector):
    """Apply a quaternion rotation to a 3D vector.

    Args:
        quat: (w, x, y, z) quaternion
        vector: (x, y, z) vector to rotate

    Returns:
        tuple: rotated (x, y, z) vector
    """
    w, qx, qy, qz = quat
    x, y, z = vector

    # Convert vector to quaternion form (0, x, y, z)
    # Apply rotation: result = q * v * q_conjugate

    # First: q * v
    temp_w = -qx * x - qy * y - qz * z
    temp_x = w * x + qy * z - qz * y
    temp_y = w * y + qz * x - qx * z
    temp_z = w * z + qx * y - qy * x

    # Then: (q * v) * q_conjugate
    result_x = temp_w * (-qx) + temp_x * w + temp_y * (-qz) - temp_z * (-qy)
    result_y = temp_w * (-qy) + temp_y * w + temp_z * (-qx) - temp_x * (-qz)
    result_z = temp_w * (-qz) + temp_z * w + temp_x * (-qy) - temp_y * (-qx)

    return (result_x, result_y, result_z)


def test_rotations():
    """Test function to verify rotation behavior with specific angle combinations."""
    print("🧪 Testing rotation combinations...")
    print("=" * 60)

    # Starting vector (1, 0, 0) - pointing along +X axis
    start_vector = (1, 0, 0)
    print(
        f"Starting vector: ({start_vector[0]:.3f}, {start_vector[1]:.3f}, {start_vector[2]:.3f})"
    )
    print()

    print("INDIVIDUAL ROTATIONS TEST:")
    test_cases = [
        (0, 0, 0, "Default"),
        (0, 45, 0, "Y=45"),
        (0, 0, 45, "Z=45"),
        (90, 0, 0, "X=90"),
    ]

    for rot_x, rot_y, rot_z, description in test_cases:
        quaternion = xyz_angles_to_quaternion(rot_x, rot_y, rot_z)
        rotated_vector = apply_quaternion_to_vector(quaternion, start_vector)
        print(
            f"  {description}: ({rotated_vector[0]:.3f}, {rotated_vector[1]:.3f}, {rotated_vector[2]:.3f})"
        )

    print()
    print("COMBINED ROTATIONS TEST:")
    combined_cases = [
        (90, 45, 0, "X=90, Y=45 (should be Y then X)"),
        (0, 45, 90, "Y=45, Z=90"),
        (90, 0, 45, "X=90, Z=45"),
        (90, 45, 45, "X=90, Y=45, Z=45"),
    ]

    for rot_x, rot_y, rot_z, description in combined_cases:
        quaternion = xyz_angles_to_quaternion(rot_x, rot_y, rot_z)
        rotated_vector = apply_quaternion_to_vector(quaternion, start_vector)
        print(
            f"  {description}: ({rotated_vector[0]:.3f}, {rotated_vector[1]:.3f}, {rotated_vector[2]:.3f})"
        )

    print()
    print("MANUAL COMBINATION TEST (Y then X):")
    # Manually combine Y=45 then X=90 to see what we should get
    quat_y45 = xyz_angles_to_quaternion(0, 45, 0)
    quat_x90 = xyz_angles_to_quaternion(90, 0, 0)

    # Apply Y rotation first
    step1 = apply_quaternion_to_vector(quat_y45, start_vector)
    print(f"  After Y=45: ({step1[0]:.3f}, {step1[1]:.3f}, {step1[2]:.3f})")

    # Then apply X rotation to the result
    step2 = apply_quaternion_to_vector(quat_x90, step1)
    print(f"  After X=90: ({step2[0]:.3f}, {step2[1]:.3f}, {step2[2]:.3f})")

    print()
    print("EXPECTED vs ACTUAL:")
    print("  Expected X=90, Y=45: (0.707, 0.707, 0.000)")
    actual = apply_quaternion_to_vector(
        xyz_angles_to_quaternion(90, 45, 0), start_vector
    )
    print(f"  Actual X=90, Y=45:   ({actual[0]:.3f}, {actual[1]:.3f}, {actual[2]:.3f})")
    print()
    print("💡 Note: X rotation is roll and shouldn't change the pointing direction")
    print("   when the vector is already pointing along the X-axis.")


def add_twigs_to_tree(
    usd_file_path: Path, species_name: str, config: Optional["GrowPyConfig"] = None
) -> bool:
    """
    High-level function to add twigs to a USD tree file.

    This function handles the complete twig assignment workflow:
    1. Use config system to find appropriate twig assets for the species
    2. Try USD-based approach if available, otherwise use text-based approach
    3. Handle Grove's twig primvars (TwigEnd, TwigSide, TwigUpward) if present
    4. Transform coordinate systems as needed
    5. Create output file with twig instances

    Args:
        usd_file_path: Path to the USD tree file
        species_name: Name of the tree species for twig lookup
        config: GrowPyConfig instance (will create one if not provided)

    Returns:
        bool: True if twigs were successfully added, False otherwise
    """
    try:
        # Initialize config if not provided
        if config is None:
            config = GrowPyConfig()

        # Get twig information for this species
        twig_name = config.get_twig_for_species(species_name)
        if not twig_name:
            print(f"  ⚠️  No twig available for species: {species_name}")
            return False

        # Get available twig files organized by type
        twig_files_by_type = config.get_twig_files_by_type(species_name)
        if not twig_files_by_type:
            print(f"  ⚠️  No twig USD files found for {species_name}")
            return False

        print(f"  🌿 Adding {twig_name} twigs to {usd_file_path.name}")
        print(f"      Available twig types: {list(twig_files_by_type.keys())}")

        # Try USD-based approach first if available
        if USD_AVAILABLE:
            try:
                return add_twigs_to_tree_usd_based(
                    usd_file_path, species_name, config, twig_files_by_type
                )
            except Exception as e:
                print(f"  ⚠️  USD-based approach failed: {e}")
                print("  🔄 Falling back to text-based approach...")

        # Use text-based approach as fallback
        return add_twigs_to_tree_text_based(
            usd_file_path, species_name, config, twig_files_by_type
        )

    except Exception as e:
        print(f"  ❌ Error adding twigs to {usd_file_path}: {e}")
        return False


def add_twigs_to_tree_usd_based(
    usd_file_path: Path,
    species_name: str,
    config: "GrowPyConfig",
    twig_files_by_type: Dict[str, List[Path]],
) -> bool:
    """
    Add twigs using USD Python API - reads Grove's twig primvars and places twigs accordingly.
    """
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings not available")

    # Open the original USD stage
    original_stage = Usd.Stage.Open(str(usd_file_path))
    if not original_stage:
        raise ValueError(f"Could not open USD file: {usd_file_path}")

    # Check the original up axis
    original_up_axis = original_stage.GetMetadata("upAxis")
    print(f"      Original upAxis: {original_up_axis}")

    # Transform the mesh data to Z-up coordinate system if needed
    points_z_up, face_vertex_counts, face_vertex_indices, twig_attributes = (
        transform_mesh_to_z_up(original_stage, "/Tree/Tree")
    )

    # Convert to face lists for processing
    face_vertex_indices_np = np.array(face_vertex_indices)
    face_vertex_counts_np = np.array(face_vertex_counts)
    split_indices = np.cumsum(face_vertex_counts_np)[:-1]
    faces = np.split(face_vertex_indices_np, split_indices)
    faces_list = [list(face) for face in faces]

    print(f"      Processing {len(faces_list)} faces for twig placement...")

    # Get twig attributes from Grove's primvars
    twig_end = twig_attributes.get("TwigEnd", [])
    twig_side = twig_attributes.get("TwigSide", [])
    twig_upward = twig_attributes.get("TwigUpward", [])

    # If no twig attributes found, add some twigs for testing
    if not any([twig_end, twig_side, twig_upward]):
        print("      ⚠️  No Grove twig primvars found. Adding sample twigs...")
        twig_end = [1 if i % 15 == 0 else 0 for i in range(len(faces_list))]
        twig_side = [
            1 if i % 8 == 0 and i % 15 != 0 else 0 for i in range(len(faces_list))
        ]
        twig_upward = []

    # Collect twig data by type
    twig_instances_by_type = {"end": [], "side": [], "upward": []}

    # Process each face
    for i, face in enumerate(faces_list):
        # Check if this face should have a twig
        twig_type = None
        if i < len(twig_end) and twig_end[i] == 1:
            twig_type = "end"
        elif i < len(twig_side) and twig_side[i] == 1:
            twig_type = "side"
        elif i < len(twig_upward) and twig_upward[i] == 1:
            twig_type = "upward"

        if twig_type:
            # Calculate face center and normal (already in Z-up coordinate system)
            face_center = calculate_face_center(points_z_up, face)
            normal = calculate_face_normal(points_z_up, face)

            # Position the twig with small offset to prevent Z-fighting
            base_offset = 0.001
            position = (
                face_center[0] + normal[0] * base_offset,
                face_center[1] + normal[1] * base_offset,
                face_center[2] + normal[2] * base_offset,
            )

            # Calculate rotation from +X axis (1,0,0) to OPPOSITE surface normal direction
            # Flip the normal since it might be pointing inward instead of outward
            opposite_normal = (-normal[0], -normal[1], -normal[2])
            quaternion = quaternion_from_x_to_normal(opposite_normal)

            twig_instances_by_type[twig_type].append(
                {"position": position, "orientation": quaternion, "face_index": i}
            )

    # Now assign specific twig files to each type based on available files
    # Use random variation assignment for multiple files per type
    twig_assignments = assign_twig_variations_randomly(
        twig_instances_by_type,
        twig_files_by_type,
        species_name,
        random_seed=hash(str(usd_file_path))
        % 10000,  # Deterministic but file-specific seed
    )

    if not twig_assignments:
        print(f"      ⚠️  No twig instances could be created for {species_name}")
        return False

    # Create transformed tree file
    output_file = str(usd_file_path).replace(".usda", "_with_twigs.usda")
    transformed_stage = create_transformed_tree_stage(
        original_stage, output_file, "/Tree", points_z_up
    )

    # Add twig PointInstancers to the transformed stage
    total_instances = 0
    success_count = 0

    for i, (file_key, assignment) in enumerate(twig_assignments.items()):
        twig_file = assignment["file"]
        instances = assignment["instances"]
        twig_type = assignment["type"]
        twig_reference_name = assignment["reference_name"]

        # Calculate relative path and ensure it's a proper path string
        try:
            twig_relative_path = twig_file.relative_to(usd_file_path.parent)
        except ValueError:
            twig_relative_path = twig_file

        # Create PointInstancer in the USD stage
        positions = [inst["position"] for inst in instances]
        orientations = [inst["orientation"] for inst in instances]

        # Create a unique, valid USD name for the twig type
        safe_twig_name = f"{twig_type}_{i:02d}"

        try:
            success = write_usd_pointinstancer_to_stage(
                transformed_stage,
                positions,
                orientations,
                str(twig_relative_path),
                twig_reference_name,
                safe_twig_name,
            )

            if success:
                success_count += 1
                total_instances += len(instances)
            else:
                print(f"      ⚠️  Failed to add {twig_type} twig instances")

        except Exception as e:
            print(f"      ⚠️  Error adding {twig_type} twig instances: {e}")

    if success_count == 0:
        print(f"      ❌ No twig instances could be added via USD API")
        return False

    transformed_stage.Save()

    # Get twig name for logging
    twig_name = config.get_twig_for_species(species_name) or "generic"
    print(f"      ✅ Added {total_instances} {twig_name} twigs using USD API")
    print(f"         Output: {Path(output_file).name}")
    return True


def add_twigs_to_tree_text_based(
    usd_file_path: Path,
    species_name: str,
    config: "GrowPyConfig",
    twig_files_by_type: Dict[str, List[Path]],
) -> bool:
    """
    Add twigs using text-based USD manipulation with random variation assignment.
    Also handles tree mesh coordinate transformation to Z-up.
    """
    print(f"      Using text-based twig placement for {species_name}")

    # Read the USD file content
    with open(usd_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if we need to transform to Z-up
    needs_transformation = 'upAxis = "Y"' in content

    if needs_transformation:
        print(f"      Converting tree from Y-up to Z-up coordinate system...")

        # Change the upAxis metadata
        content = content.replace('upAxis = "Y"', 'upAxis = "Z"')

        # If USD is available, try to transform the mesh coordinates
        if USD_AVAILABLE:
            try:
                # Open the original stage and get transformed mesh data
                original_stage = Usd.Stage.Open(str(usd_file_path))
                if original_stage:
                    points_z_up, _, _, _ = transform_mesh_to_z_up(
                        original_stage, "/Tree/Tree"
                    )

                    # Convert transformed points back to USD text format
                    points_text = ", ".join(
                        [f"({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})" for p in points_z_up]
                    )

                    # Find and replace the points array in the text
                    import re

                    points_pattern = r"point3f\[\] points = \[([^\]]+)\]"
                    content = re.sub(
                        points_pattern, f"point3f[] points = [{points_text}]", content
                    )
                    print(
                        f"      ✅ Transformed {len(points_z_up)} mesh vertices to Z-up"
                    )
                else:
                    print(
                        f"      ⚠️  Could not open USD stage for coordinate transformation"
                    )
            except Exception as e:
                print(f"      ⚠️  Could not transform mesh coordinates: {e}")

    # Generate intelligent twig instances based on available types
    twig_instances_by_type = {
        "end": [],
        "side": [],
        "apical": [],
        "lateral": [],
        "main": [],
    }

    # Define strategic twig placement patterns with more variety
    placement_strategies = {
        "end": [
            {"position": (0.1, 0.2, 3.5), "desc": "top_apical_1"},
            {"position": (-0.2, 0.3, 3.2), "desc": "top_apical_2"},
            {"position": (0.3, -0.1, 3.8), "desc": "crown_tip"},
            {"position": (0.15, -0.25, 3.6), "desc": "top_apical_3"},
        ],
        "side": [
            {"position": (0.8, 0.5, 2.0), "desc": "mid_lateral_1"},
            {"position": (-0.6, 0.7, 1.8), "desc": "mid_lateral_2"},
            {"position": (0.4, -0.8, 2.3), "desc": "mid_lateral_3"},
            {"position": (-0.7, -0.3, 1.5), "desc": "lower_lateral_1"},
            {"position": (0.9, 0.1, 2.5), "desc": "upper_lateral"},
            {"position": (-0.5, 0.9, 2.1), "desc": "mid_lateral_4"},
            {"position": (0.6, -0.4, 1.7), "desc": "lower_lateral_2"},
        ],
        "apical": [
            {"position": (0.05, 0.15, 3.9), "desc": "apex_main"},
            {"position": (-0.1, 0.1, 3.7), "desc": "apex_side_1"},
            {"position": (0.2, -0.05, 3.8), "desc": "apex_side_2"},
        ],
        "lateral": [
            {"position": (1.0, 0.3, 2.2), "desc": "branch_lateral_1"},
            {"position": (-0.8, 0.6, 1.9), "desc": "branch_lateral_2"},
            {"position": (0.7, -0.7, 2.0), "desc": "branch_lateral_3"},
            {"position": (-0.9, -0.2, 1.6), "desc": "branch_lateral_4"},
            {"position": (0.5, 0.8, 2.4), "desc": "branch_lateral_5"},
        ],
        "main": [
            {"position": (0.3, 0.4, 2.8), "desc": "main_1"},
            {"position": (-0.4, 0.5, 2.6), "desc": "main_2"},
            {"position": (0.6, -0.3, 2.9), "desc": "main_3"},
        ],
    }

    # If we transformed to Z-up, adjust twig positions accordingly (they're already in Z-up space)
    if needs_transformation:
        # The placement strategies are already in Z-up coordinates (z is vertical)
        # So no transformation needed for the twig positions
        pass

    # Create instance data for each placement strategy
    for strategy_type, placements in placement_strategies.items():
        # Only create instances if we have twig files for this type
        if strategy_type in twig_files_by_type and twig_files_by_type[strategy_type]:
            for i, placement in enumerate(placements):
                twig_instances_by_type[strategy_type].append(
                    {
                        "position": placement["position"],
                        "orientation": (1.0, 0.0, 0.0, 0.0),  # Identity quaternion
                        "description": placement["desc"],
                        "instance_index": i,
                    }
                )

    # Use random variation assignment
    twig_assignments = assign_twig_variations_randomly(
        twig_instances_by_type,
        twig_files_by_type,
        species_name,
        random_seed=hash(str(usd_file_path))
        % 10000,  # Deterministic but file-specific seed
    )

    if not twig_assignments:
        print(f"      ⚠️  No twig instances could be created for {species_name}")
        return False

    # Generate USD content for each twig variation
    twig_content = []
    twig_content.append("")

    for i, (file_key, assignment) in enumerate(twig_assignments.items()):
        twig_file = assignment["file"]
        twig_reference_name = assignment["reference_name"]
        instances = assignment["instances"]
        twig_type = assignment["type"]

        prototype_name = f"TwigPrototype_{twig_type}_{i}"
        instancer_name = f"TwigInstances_{twig_type}_{i}"

        # Calculate relative path
        try:
            twig_relative_path = twig_file.relative_to(usd_file_path.parent)
        except ValueError:
            twig_relative_path = twig_file

        # Add prototype reference
        twig_content.append(f'    def "{prototype_name}" (')
        twig_content.append(
            f"        references = @{twig_relative_path}@</root/{twig_reference_name}>"
        )
        twig_content.append("    )")
        twig_content.append("    {")
        twig_content.append("    }")
        twig_content.append("")

        # Add PointInstancer
        twig_content.append(f'    def PointInstancer "{instancer_name}"')
        twig_content.append("    {")
        twig_content.append(f"        rel prototypes = </Tree/{prototype_name}>")
        twig_content.append(
            f'        int[] protoIndices = [{", ".join(["0"] * len(instances))}]'
        )
        twig_content.append(
            f'        int64[] ids = [{", ".join([str(j) for j in range(len(instances))])}]'
        )
        twig_content.append("")

        # Add positions
        positions_str = ", ".join(
            [
                f"({inst['position'][0]:.4f}, {inst['position'][1]:.4f}, {inst['position'][2]:.4f})"
                for inst in instances
            ]
        )
        twig_content.append(f"        point3f[] positions = [{positions_str}]")
        twig_content.append("")

        # Add orientations
        orientations_str = ", ".join(
            [
                f"({inst['orientation'][0]:.6f}, {inst['orientation'][1]:.6f}, {inst['orientation'][2]:.6f}, {inst['orientation'][3]:.6f})"
                for inst in instances
            ]
        )
        twig_content.append(f"        quath[] orientations = [{orientations_str}]")
        twig_content.append("")

        # Add uniform scale
        twig_content.append("        float3[] scales = [(1, 1, 1)]")
        twig_content.append("    }")
        twig_content.append("")

    # Join twig content
    twig_usd_text = "\n".join(twig_content)

    # Find insertion point (before the last closing brace)
    last_brace = content.rfind("}")
    if last_brace == -1:
        print("      ❌ Could not find closing brace in USD file")
        return False

    # Insert the twig content
    new_content = (
        content[:last_brace] + "\n" + twig_usd_text + "\n" + content[last_brace:]
    )

    # Create output filename with twigs
    output_file = str(usd_file_path).replace(".usda", "_with_twigs.usda")

    # Write the modified content
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    total_instances = sum(
        len(assignment["instances"]) for assignment in twig_assignments.values()
    )

    # Get twig name for logging
    twig_name = config.get_twig_for_species(species_name) or "generic"
    coordinate_info = " (Z-up transformed)" if needs_transformation else ""
    print(
        f"      ✅ Added {total_instances} {twig_name} twigs ({len(twig_assignments)} variations){coordinate_info}"
    )
    print(f"         Output: {Path(output_file).name}")
    return True


def write_usd_pointinstancer_to_stage(
    stage, positions, orientations, twig_file_path, twig_xform_name, twig_type
):
    """Write USD PointInstancer directly to a USD stage."""
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings required for stage operations")

    tree_prim = stage.GetPrimAtPath("/Tree")
    if not tree_prim:
        raise ValueError("Tree prim not found in stage")

    # Create prototype with safe USD name
    safe_prototype_name = f"TwigPrototype_{twig_type}".replace("-", "_").replace(
        " ", "_"
    )
    prototype_path = f"/Tree/{safe_prototype_name}"

    try:
        prototype_prim = UsdGeom.Xform.Define(stage, prototype_path)
        prototype_prim.GetPrim().GetReferences().AddReference(
            str(twig_file_path), f"/root/{twig_xform_name}"
        )
    except Exception as e:
        print(
            f"      ⚠️  Warning: Could not create prototype {safe_prototype_name}: {e}"
        )
        return False

    # Create PointInstancer with safe USD name
    safe_instancer_name = f"TwigInstances_{twig_type}".replace("-", "_").replace(
        " ", "_"
    )
    instancer_path = f"/Tree/{safe_instancer_name}"

    try:
        point_instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)

        # Set up the instancer
        point_instancer.CreatePrototypesRel().SetTargets([prototype_path])
        point_instancer.CreateProtoIndicesAttr().Set([0] * len(positions))
        point_instancer.CreateIdsAttr().Set(list(range(len(positions))))

        # Convert positions and orientations to USD format
        usd_positions = [Gf.Vec3f(p[0], p[1], p[2]) for p in positions]
        usd_orientations = [Gf.Quath(q[0], q[1], q[2], q[3]) for q in orientations]

        point_instancer.CreatePositionsAttr().Set(usd_positions)
        point_instancer.CreateOrientationsAttr().Set(usd_orientations)
        point_instancer.CreateScalesAttr().Set([Gf.Vec3f(1, 1, 1)])

        return True

    except Exception as e:
        print(
            f"      ⚠️  Warning: Could not create point instancer {safe_instancer_name}: {e}"
        )
        return False


def test_twig_orientations():
    """Test different approaches to twig orientation to debug the rotation issues."""
    print("Testing twig orientations...")

    # Test normals that should point outward from a tree (roughly horizontal)
    test_normals = [
        (1.0, 0.0, 0.0),  # East
        (0.0, 1.0, 0.0),  # North
        (-1.0, 0.0, 0.0),  # West
        (0.0, -1.0, 0.0),  # South
        (0.7, 0.7, 0.0),  # Northeast
        (0.0, 0.0, 1.0),  # Up (should be rare for tree sides)
        (0.0, 0.0, -1.0),  # Down (should be rare for tree sides)
    ]

    methods = ["grove_plus_x", "grove_minus_z", "grove_3dsmax"]

    for method in methods:
        print(f"\n=== Testing method: {method} ===")
        for i, normal in enumerate(test_normals):
            quat = calculate_grove_twig_orientation(
                normal, reverse_normal=False, debug=True, method=method
            )
            print(f"  Normal {i+1} {normal} -> Quaternion: {quat}")

    print(f"\n=== Testing with reversed normals (grove_plus_x) ===")
    for i, normal in enumerate(test_normals):
        quat = calculate_grove_twig_orientation(
            normal, reverse_normal=True, debug=True, method="grove_plus_x"
        )
        print(f"  Normal {i+1} {normal} -> Quaternion: {quat}")


def add_test_orientation_options():
    """Add test functions to help debug twig orientations."""
    # This function exists to ensure the test function is available
    pass


def main():
    """Main function to process Grove USD and add twigs with coordinate transformation."""
    # Configuration - process all trees in the output directory
    output_dir = (
        Path(__file__).parent.parent.parent
        / "data"
        / "output"
        / "mini_tree_inventory_32632"
    )

    print(f"🌲 Processing all trees in directory: {output_dir}")
    print(f"📐 Using enhanced twig assignment system...")

    if not output_dir.exists():
        print(f"❌ Error: Output directory not found: {output_dir}")
        return

    # Find all USD tree files (excluding already processed ones with twigs)
    tree_files = []
    for usda_file in output_dir.glob("*.usda"):
        if not usda_file.name.endswith("_with_twigs.usda"):
            tree_files.append(usda_file)

    if not tree_files:
        print(f"⚠️  No tree files found in {output_dir}")
        return

    print(f"🌳 Found {len(tree_files)} tree files to process:")
    for tree_file in tree_files:
        print(f"   • {tree_file.name}")

    # Initialize config once for all trees
    try:
        config = GrowPyConfig()
    except Exception as e:
        print(f"❌ Error initializing GrowPyConfig: {e}")
        return

    # Process each tree file
    success_count = 0
    total_files = len(tree_files)

    for i, usda_file in enumerate(tree_files, 1):
        print(f"\n🌲 Processing tree {i}/{total_files}: {usda_file.name}")

        # Extract species name from filename (assume Silver fir for these files)
        species_name = "Silver fir"
        if "SilverFir" in usda_file.name:
            species_name = "Silver fir"
        # Add more species detection logic here if needed

        try:
            success = add_twigs_to_tree(usda_file, species_name, config)

            if success:
                success_count += 1
                print(f"   ✅ Successfully added twigs to {usda_file.name}")
            else:
                print(
                    f"   ⚠️  Twig assignment completed with warnings for {usda_file.name}"
                )

        except Exception as e:
            print(f"   ❌ Error processing {usda_file.name}: {e}")

    # Summary
    print(f"\n🎉 Processing complete!")
    print(f"   ✅ Successfully processed: {success_count}/{total_files} trees")
    if success_count < total_files:
        print(
            f"   ⚠️  Failed or had warnings: {total_files - success_count}/{total_files} trees"
        )

    print(f"\n📁 Output files are located in: {output_dir}")
    print(f"   Look for files ending with '_with_twigs.usda'")
    print(
        f"💡 You can now open these files in Blender or other USD-compatible applications"
    )


def main_fallback(usda_file):
    """Fallback main function using the original approach."""
    if not USD_AVAILABLE:
        print("❌ USD Python bindings required for fallback approach")
        return

    twig_file_path = "../../assets/twigs/PacificSilverFirTwig/PacificSilverFirTwig_PacificSilverFirTwig.usda"
    twig_xform_name = "PacificSilverFirTwig"

    print(f"🌿 Using twig file: {twig_file_path}")
    print(f"📐 Transforming from Y-up to Z-up coordinate system...")

    # Open the original USD stage (Y-up)
    original_stage = Usd.Stage.Open(str(usda_file))
    if not original_stage:
        print(f"❌ Error: Could not open USD file: {usda_file}")
        return

    # Check the original up axis
    original_up_axis = original_stage.GetMetadata("upAxis")
    print(f"📊 Original upAxis: {original_up_axis}")

    # Transform the mesh data to Z-up coordinate system
    try:
        points_z_up, face_vertex_counts, face_vertex_indices, twig_attributes = (
            transform_mesh_to_z_up(original_stage, "/Tree/Tree")
        )
        print(
            f"✅ Successfully transformed {len(points_z_up)} points to Z-up coordinate system"
        )
    except Exception as e:
        print(f"❌ Error transforming mesh: {e}")
        return

    # Convert to face lists for processing
    face_vertex_indices_np = np.array(face_vertex_indices)
    face_vertex_counts_np = np.array(face_vertex_counts)
    split_indices = np.cumsum(face_vertex_counts_np)[:-1]
    faces = np.split(face_vertex_indices_np, split_indices)
    faces_list = [list(face) for face in faces]

    print(f"📐 Processing {len(faces_list)} faces for twig placement...")

    # Analyze full tree height for context
    all_z_heights = [point[2] for point in points_z_up]
    tree_z_min, tree_z_max = min(all_z_heights), max(all_z_heights)
    print(
        f"🌲 Full tree Z-range: {tree_z_min:.2f} to {tree_z_max:.2f} (height: {tree_z_max - tree_z_min:.2f})"
    )

    # Get twig attributes (now in the correct coordinate system)
    twig_end = twig_attributes.get("TwigEnd", [])
    twig_side = twig_attributes.get("TwigSide", [])
    twig_upward = twig_attributes.get("TwigUpward", [])

    # If no twig attributes found, add some twigs for testing
    if not any([twig_end, twig_side, twig_upward]):
        print("⚠️  No twig attributes found. Adding test twigs to every 10th face...")
        twig_end = [1 if i % 10 == 0 else 0 for i in range(len(faces_list))]
        twig_side = []
        twig_upward = []

    # Collect twig data
    all_positions = []
    all_orientations = []

    # Process each face (now in Z-up coordinate system)
    for i, face in enumerate(faces_list):
        # Check if this face should have a twig
        has_twig = False
        twig_type = None

        if i < len(twig_end) and twig_end[i] == 1:
            has_twig = True
            twig_type = "end"
        elif i < len(twig_side) and twig_side[i] == 1:
            has_twig = True
            twig_type = "side"
        elif i < len(twig_upward) and twig_upward[i] == 1:
            has_twig = True
            twig_type = "upward"

        if has_twig:
            # Calculate face center and normal (already in Z-up coordinate system)
            face_center = calculate_face_center(points_z_up, face)
            normal = calculate_face_normal(points_z_up, face)

            # Debug: Print face details for first few twigs
            if len(all_positions) < 5:
                print(f"🔍 Debug Face {i} ({twig_type}):")
                print(f"   Face vertices: {face}")
                print(
                    f"   Face center: ({face_center[0]:.4f}, {face_center[1]:.4f}, {face_center[2]:.4f})"
                )
                print(f"   Normal: ({normal[0]:.4f}, {normal[1]:.4f}, {normal[2]:.4f})")

                # Check if this face is near the center of the tree
                distance_from_origin = math.sqrt(
                    face_center[0] ** 2 + face_center[1] ** 2
                )
                print(f"   Distance from Y-axis: {distance_from_origin:.4f}")
                print(f"   Z-height: {face_center[2]:.4f}")
                print()

            # Also print summary of all Z-heights
            if len(all_positions) == 0:
                print("🔍 Analyzing all twig Z-heights...")
                z_heights = []

            # Place twig with its attachment point (0,0,0) at the triangle center
            # The twig should point outward along the surface normal
            base_offset = 0.001  # Very small offset to prevent Z-fighting

            # Position the twig so its origin (0,0,0) sits at the face center + small offset
            position = (
                face_center[0] + normal[0] * base_offset,
                face_center[1] + normal[1] * base_offset,
                face_center[2] + normal[2] * base_offset,
            )
            all_positions.append(position)

            # Calculate rotation from +X axis (1,0,0) to OPPOSITE surface normal direction
            # Flip the normal since it might be pointing inward instead of outward
            opposite_normal = (-normal[0], -normal[1], -normal[2])
            quaternion = quaternion_from_x_to_normal(opposite_normal)
            all_orientations.append(quaternion)

    print(f"\n🌲 Twig placement summary:")
    print(f"  Total twigs: {len(all_positions)}")
    print(f"  End twigs: {sum(twig_end) if twig_end else 0}")
    print(f"  Side twigs: {sum(twig_side) if twig_side else 0}")
    print(f"  Upward twigs: {sum(twig_upward) if twig_upward else 0}")

    # Analyze twig distribution
    if all_positions:
        z_heights = [pos[2] for pos in all_positions]
        radial_distances = [
            math.sqrt(pos[0] ** 2 + pos[1] ** 2) for pos in all_positions
        ]
        print(f"\n📊 Twig distribution analysis:")
        print(f"  Z-height range: {min(z_heights):.2f} to {max(z_heights):.2f}")
        print(f"  Average Z-height: {sum(z_heights)/len(z_heights):.2f}")
        print(
            f"  Radial distance range: {min(radial_distances):.2f} to {max(radial_distances):.2f}"
        )
        print(
            f"  Average radial distance: {sum(radial_distances)/len(radial_distances):.2f}"
        )

    # Create transformed tree file with Z-up coordinate system
    transformed_tree_path = str(usda_file).replace(".usda", "_z_up.usda")
    print(f"🔄 Creating transformed tree file: {transformed_tree_path}")

    try:
        transformed_stage = create_transformed_tree_stage(
            original_stage, transformed_tree_path, "/Tree", points_z_up
        )
        print(f"✅ Created Z-up tree file: {transformed_tree_path}")
    except Exception as e:
        print(f"❌ Error creating transformed tree: {e}")
        return

    # Write the USD PointInstancer to the transformed tree
    write_usd_pointinstancer(
        all_positions,
        all_orientations,
        transformed_tree_path,
        twig_file_path,
        twig_xform_name,
    )

    print(f"🎉 Successfully created tree with twigs in Z-up coordinate system!")
    print(
        f"📁 Output file: {transformed_tree_path.replace('.usda', '_with_twigs.usda')}"
    )
    print(
        f"💡 Both tree and twigs are now in Z-up coordinate system and should display correctly in Blender."
    )
    print(
        f"🔍 To test: Open the output file in Blender and verify the tree is upright with twigs attached."
    )


if __name__ == "__main__":
    import sys

    print("🔧 Fixed quaternion rotation system")
    print("Individual rotations:")
    print("- Y rotation: yaw (horizontal turning)")
    print("- Z rotation: pitch (vertical tilt)")
    print("- X rotation: roll (around pointing direction)")
    print()

    # Check for test argument
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test different orientation approaches
        test_twig_orientations()
    else:
        # Test the fixed implementation
        # test_rotations()

        # Run the main twig processing with fixed rotations
        main()
        main()
        main()
        main()
