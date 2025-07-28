"""Minimal twig enhancement for USD files."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Configuration
APPLY_Z_TO_Y_TRANSFORM = (
    False  # Set to False since twig geometry is now properly Z-up oriented
)
FLIP_FACE_NORMALS = (
    False  # Set to True if face normals point inward and should be flipped outward
)

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available")
    gc = None

from pxr import Usd, Vt

usda_file = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/output/small_demo/Norwayspruce_LOD1_High_000.usda"
)
twig_file = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/assets/twigs/ScotsPineTwig/ScotsPineVariationATwig.usda"
)

stage = Usd.Stage.Open(str(usda_file))
[x for x in stage.Traverse()]
tree = stage.GetPrimAtPath("/Tree/Tree")
tree.GetPropertyNames()

# Extract attributes from the tree
face_vertex_counts = list(
    tree.GetAttribute("faceVertexCounts").Get()
)  # Number of vertices per face
face_vertex_indices = list(
    tree.GetAttribute("faceVertexIndices").Get()
)  # Indices of vertices for each face

# Extract points and other attributes
points = list(tree.GetAttribute("points").Get())
uv = list(tree.GetAttribute("primvars:st").Get())  # UV
age = list(tree.GetAttribute("primvars:Age").Get())
dead = list(tree.GetAttribute("primvars:Dead").Get())
thickness = list(tree.GetAttribute("primvars:Thickness").Get())
twig_end = list(tree.GetAttribute("primvars:TwigEnd").Get())  # Long / Apical
twig_side = list(tree.GetAttribute("primvars:TwigSide").Get())  # Short / Lateral
twig_upward = list(tree.GetAttribute("primvars:TwigUpward").Get())  # Upward
twig_dead = list(tree.GetAttribute("primvars:TwigDead").Get())  # Dead

# Convert attributes to numpy arrays
face_vertex_indices_np = np.array(face_vertex_indices)
face_vertex_counts_np = np.array(face_vertex_counts)
split_indices = np.cumsum(face_vertex_counts_np)[:-1]
faces_numpy = np.split(face_vertex_indices_np, split_indices)
faces_tuples = [list(face) for face in faces_numpy]

# Filter faces based on twig attributes
faces_end = [face for (face, end) in zip(faces_tuples, twig_end) if end == 1]
faces_side = [face for (face, side) in zip(faces_tuples, twig_side) if side == 1]
faces_upward = [
    face for (face, upward) in zip(faces_tuples, twig_upward) if upward == 1
]
faces_dead = [face for (face, dead) in zip(faces_tuples, twig_dead) if dead == 1]


def calculate_centroid(points: Vt.Vec3fArray, face: List[int]) -> tuple:
    """Calculate the centroid of a face."""
    face_points = np.array([points[i] for i in face])
    return tuple(np.mean(face_points, axis=0))


def calculate_normal(points: Vt.Vec3fArray, face: List[int]) -> tuple:
    """Calculate the normal vector of a face with improved robustness."""
    face_points = np.array([points[i] for i in face])

    # Need at least 3 points to calculate a normal
    if len(face) < 3:
        print(f"Warning: face has fewer than 3 vertices: {face}")
        return (0.0, 1.0, 0.0)  # Default to up

    # Use first 3 points to calculate normal (works for triangles and quads)
    v1 = face_points[1] - face_points[0]
    v2 = face_points[2] - face_points[0]
    normal = np.cross(v1, v2)

    # Check for degenerate faces (zero or near-zero normal)
    norm_length = np.linalg.norm(normal)
    if norm_length < 1e-10:
        print(f"Warning: degenerate face with points {face_points[:3]}")
        return (0.0, 1.0, 0.0)  # Default to up

    # Normalize the normal
    normalized_normal = normal / norm_length

    # Optionally flip normals if they point inward
    if FLIP_FACE_NORMALS:
        normalized_normal = -normalized_normal

    return tuple(normalized_normal)


def calculate_quaternion_from_normal(
    normal, apply_z_to_y_transform=True
) -> List[float]:
    """Calculate a quaternion that rotates from the default X-forward direction to the normal vector.
    
    Since the twig is now properly Z-up oriented, most adjustments should be rotations on a 
    horizontal plane. Only twigs pointing strongly upward should show strong vertical rotation.
    
    The twig's natural orientation:
    - Forward: +X axis
    - Up: +Z axis (preserved for most orientations)
    - Right: +Y axis

    According to Grove documentation: "the Grove assumes the branch is pointing in the direction
    of the X-axis. This means that when you are in top view, the base of the branch should be
    on the left, and it should be growing out to the right."

    Args:
        normal: The surface normal vector to align the twig to
        apply_z_to_y_transform: Legacy parameter, now ignored since twig is Z-up

    USD quaternions use (x, y, z, w) format, not (w, x, y, z) format.
    """
    # Convert tuple to numpy array if needed
    if isinstance(normal, tuple):
        normal = np.array(normal)

    normal = normal / np.linalg.norm(normal)  # Ensure normalized

    # Default forward direction for twigs (Grove standard: +X axis)
    default_forward = np.array([1.0, 0.0, 0.0])
    
    # Default up direction for Z-up twig
    default_up = np.array([0.0, 0.0, 1.0])

    # Target forward direction is the surface normal
    target_forward = normal
    
    # For most face normals, we want to keep the twig's up direction close to +Z
    # Only for strongly vertical normals do we allow significant vertical rotation
    
    # Check if the normal is pointing strongly upward or downward
    vertical_component = abs(target_forward[2])  # |Z component|
    
    if vertical_component > 0.8:  # Normal is strongly vertical
        # For vertical surfaces, allow the twig to rotate into vertical orientation
        # Use Y axis as reference for the twig's up direction
        if abs(target_forward[1]) < 0.9:  # Not parallel to Y
            reference = np.array([0.0, 1.0, 0.0])  # Y axis
        else:  # Parallel to Y, use X axis
            reference = np.array([1.0, 0.0, 0.0])  # X axis
            
        twig_right = np.cross(target_forward, reference)
        twig_right = twig_right / np.linalg.norm(twig_right)
        twig_up = np.cross(twig_right, target_forward)
        twig_up = twig_up / np.linalg.norm(twig_up)
        
    else:  # Normal is mostly horizontal
        # For horizontal surfaces, keep the twig's up direction close to +Z
        # This means mostly rotating in the horizontal plane
        
        # Project the default up vector (+Z) onto the plane perpendicular to target_forward
        projected_up = default_up - np.dot(default_up, target_forward) * target_forward
        projected_up_length = np.linalg.norm(projected_up)
        
        if projected_up_length > 0.1:  # Good projection
            twig_up = projected_up / projected_up_length
        else:  # Bad projection, use fallback
            # If +Z is too parallel to normal, use +Y as reference
            reference = np.array([0.0, 1.0, 0.0])
            twig_right = np.cross(target_forward, reference)
            twig_right = twig_right / np.linalg.norm(twig_right)
            twig_up = np.cross(twig_right, target_forward)
            twig_up = twig_up / np.linalg.norm(twig_up)
        
        # Calculate right vector
        twig_right = np.cross(target_forward, twig_up)
        twig_right = twig_right / np.linalg.norm(twig_right)
    
    # Create rotation matrix from default orientation to target orientation
    # Default: +X forward, +Z up, +Y right
    # Target: target_forward, twig_up, twig_right
    rotation_matrix = np.array([
        [target_forward[0], twig_up[0], twig_right[0]],
        [target_forward[1], twig_up[1], twig_right[1]], 
        [target_forward[2], twig_up[2], twig_right[2]]
    ])
    
    # Convert rotation matrix to quaternion
    quat = rotation_matrix_to_quaternion(rotation_matrix)

    return quat


def rotation_matrix_to_quaternion(R):
    """Convert a 3x3 rotation matrix to quaternion in [x, y, z, w] format."""
    trace = R[0, 0] + R[1, 1] + R[2, 2]

    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2  # s = 4 * qw
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2  # s = 4 * qx
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2  # s = 4 * qy
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2  # s = 4 * qz
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s

    return [x, y, z, w]


def multiply_quaternions(q1, q2):
    """Multiply two quaternions in (x, y, z, w) format."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2

    return [
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,  # x
        w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2,  # y
        w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2,  # z
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,  # w
    ]


centroid_end = [calculate_centroid(points, face) for face in faces_end]
normal_end = [calculate_normal(points, face) for face in faces_end]
quaternion_end = [
    calculate_quaternion_from_normal(n, APPLY_Z_TO_Y_TRANSFORM) for n in normal_end
]

centroid_side = [calculate_centroid(points, face) for face in faces_side]
normal_side = [calculate_normal(points, face) for face in faces_side]
quaternion_side = [
    calculate_quaternion_from_normal(n, APPLY_Z_TO_Y_TRANSFORM) for n in normal_side
]

centroid_upward = [calculate_centroid(points, face) for face in faces_upward]
normal_upward = [calculate_normal(points, face) for face in faces_upward]
quaternion_upward = [
    calculate_quaternion_from_normal(n, APPLY_Z_TO_Y_TRANSFORM) for n in normal_upward
]

centroid_dead = [calculate_centroid(points, face) for face in faces_dead]
normal_dead = [calculate_normal(points, face) for face in faces_dead]
quaternion_dead = [
    calculate_quaternion_from_normal(n, APPLY_Z_TO_Y_TRANSFORM) for n in normal_dead
]


def write_usd_pointinstancer(positions, orientations, filename="twig_side.txt"):
    """Write USD PointInstancer section for twigs."""
    with open(filename, "w") as f:
        f.write('    def Scope "Prototypes"\n')
        f.write("    {\n")
        f.write('        def "TwigPrototype" (\n')
        f.write("            references = @./ScotsPineVariationATwig.usda@\n")
        f.write("        )\n")
        f.write("        {\n")
        f.write("        }\n")
        f.write("    }\n")
        f.write('    def PointInstancer "Twigs"\n')
        f.write("    {\n")
        f.write(
            "        rel prototypes = [</Tree/Prototypes/TwigPrototype/ScotsPineVariationATwig>]\n"
        )
        f.write(f"        int[] protoIndices = [{', '.join(['0'] * len(positions))}]\n")
        f.write(
            f"        int64[] ids = [{', '.join([str(i+1) for i in range(len(positions))])}]\n"
        )
        f.write("\n")
        f.write("        point3f[] positions = [")
        for i, pos in enumerate(positions):
            f.write(f"({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")
            if i < len(positions) - 1:
                f.write(", ")
        f.write("        ]\n")
        f.write("\n")
        f.write("        quath[] orientations = [")
        for i, quat in enumerate(orientations):
            f.write(f"({quat[0]:.4f}, {quat[1]:.4f}, {quat[2]:.4f}, {quat[3]:.4f})")
            if i < len(orientations) - 1:
                f.write(", ")
        f.write("        ]\n")
        f.write("\n")
        f.write("        float3[] scales = [")
        for i in range(len(positions)):
            f.write("(1.0, 1.0, 1.0)")
            if i < len(positions) - 1:
                f.write(", ")
        f.write("        ]\n")
        f.write("    }\n")


# Process all twig types (combine side, end, and upward twigs)
all_positions = centroid_side + centroid_end + centroid_upward
all_quaternions = quaternion_side + quaternion_end + quaternion_upward

# Write the USD PointInstancer section
write_usd_pointinstancer(all_positions, all_quaternions, "twig_side.txt")

print(f"Generated PointInstancer with {len(all_positions)} twigs:")
print(f"  - {len(centroid_side)} side twigs")
print(f"  - {len(centroid_end)} end twigs")
print(f"  - {len(centroid_upward)} upward twigs")
print("Output written to twig_side.txt")
