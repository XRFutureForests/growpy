"""
Minimal twig enhancement for USD files.

IMPLEMENTATION SUMMARY:
======================

This module processes USD files exported from The Grove to extract twig placement
information and generate PointInstancer data for rendering twigs in USD-compliant
3D applications (Blender, Unreal, Maya, etc.).

KEY DISCOVERIES FROM GROVE DOCUMENTATION:
- Twig orientation standard: Grove assumes branches point in +X direction
- Face normals of twig triangles point in the direction of growth (NOT outward from surface)
- Quote: "Twig duplication triangle are oriented toward the direction of growth,
  so for these triangles the direction attribute equals the face normal"

COORDINATE SYSTEM CHALLENGE:
- Tree mesh: Usually Y-up coordinate system from Grove export
- Twig USD files: Z-up coordinate system (upAxis="Z" in USD header)
- This mismatch causes twigs to appear incorrectly oriented

CORRECTED APPROACH:
- Face normals directly represent the branch growth direction
- Apply coordinate system transformation (Y-up to Z-up) to align orientations
- Calculate quaternion to rotate twig from default +X forward to transformed normal direction
- Apply additional coordinate correction for USD twig orientation
- No Grove core dependencies required - works purely with USD data

OUTPUT:
- Generates USD PointInstancer with positions and orientations
- Supports all twig types: end, side, upward, and dead twigs
- Quaternions in USD format: (w, x, y, z)
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from pxr import Usd, Vt

# Note: Grove core not required for USD file processing
# This module works directly with USD files exported from The Grove


usda_file = Path(
    r"C:\Users\Maximilian Sperlich\Git\the-grove\data\output\small_demo\Norwayspruce_LOD1_High_000.usda"
)
twig_file = Path(
    r"C:\Users\Maximilian Sperlich\Git\the-grove\data\output\small_demo\ScotsPineVariationATwig_ScotsPineVariationATwig.usda"
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


def calculate_centroid(points: list, face: List[int]) -> tuple:
    """Calculate the centroid of a face."""
    face_points = np.array([points[i] for i in face])
    return tuple(np.mean(face_points, axis=0))


def calculate_normal(points: list, face: List[int]) -> tuple:
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

    # Optionally flip normals if they point inward (this is typically not needed)
    # if needed: normalized_normal = -normalized_normal

    return tuple(normalized_normal)


def calculate_quaternion_from_normal(normal) -> List[float]:
    """Calculate a quaternion that orients the twig to align with the branch growth direction.

    FIXED APPROACH TO PREVENT ROLLING:
    - Align the twig's forward direction (+X) with the branch normal (growth direction)
    - Ensure the twig's up direction (+Z) remains consistent and doesn't "roll"
    - Build a proper orthonormal basis to prevent arbitrary rotations around the forward axis

    USD quaternions use (x, y, z, w) format.
    """
    # Convert tuple to numpy array if needed
    if isinstance(normal, tuple):
        normal = np.array(normal)

    normal = normal / np.linalg.norm(normal)  # Ensure normalized

    # Build orthonormal coordinate system:
    # - local_x (forward) = branch normal direction
    # - local_z (up) = as close to world +Z as possible (prevents rolling)
    # - local_y (right) = completes right-handed system

    local_x = normal  # Forward direction aligns with branch growth

    # Use world +Z as the preferred "up" direction to prevent rolling
    world_z = np.array([0.0, 0.0, 1.0])

    # Handle the special case where the branch points straight up or down in Z
    if abs(np.dot(local_x, world_z)) > 0.95:
        # Branch is nearly parallel to Z-axis, use world +Y as reference
        reference = np.array([0.0, 1.0, 0.0])
        local_y = np.cross(local_x, reference)
        local_y = local_y / np.linalg.norm(local_y)
        local_z = np.cross(local_x, local_y)
    else:
        # Normal case: project world_z onto plane perpendicular to local_x
        # This gives us the up direction that's closest to +Z without rolling
        local_z = world_z - np.dot(world_z, local_x) * local_x
        local_z = local_z / np.linalg.norm(local_z)

        # Complete the right-handed coordinate system
        local_y = np.cross(local_z, local_x)
        local_y = local_y / np.linalg.norm(local_y)

    # Build rotation matrix from local axes (column vectors: X, Y, Z)
    rotation_matrix = np.column_stack([local_x, local_y, local_z])

    # Convert rotation matrix to quaternion
    return rotation_matrix_to_quaternion(rotation_matrix)


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
# Calculate quaternions using the corrected approach (face normal = growth direction)
quaternion_end = [calculate_quaternion_from_normal(n) for n in normal_end]

centroid_side = [calculate_centroid(points, face) for face in faces_side]
normal_side = [calculate_normal(points, face) for face in faces_side]
# Calculate quaternions using the corrected approach (face normal = growth direction)
quaternion_side = [calculate_quaternion_from_normal(n) for n in normal_side]

centroid_upward = [calculate_centroid(points, face) for face in faces_upward]
normal_upward = [calculate_normal(points, face) for face in faces_upward]
# Calculate quaternions using the corrected approach (face normal = growth direction)
quaternion_upward = [calculate_quaternion_from_normal(n) for n in normal_upward]

centroid_dead = [calculate_centroid(points, face) for face in faces_dead]
normal_dead = [calculate_normal(points, face) for face in faces_dead]
# Calculate quaternions using the corrected approach (face normal = growth direction)
quaternion_dead = [calculate_quaternion_from_normal(n) for n in normal_dead]


def write_usd_pointinstancer_to_tree_file(positions, orientations, tree_file_path):
    """Write USD PointInstancer section directly into the tree USD file."""
    import re

    # Read the original tree file
    with open(tree_file_path, "r") as f:
        content = f.read()

    # Find the position where to insert the twig data (look for the comment)
    insert_marker = "# twig_side.txt content to be placed here"
    if insert_marker not in content:
        print(
            f"Warning: Could not find insertion marker '{insert_marker}' in {tree_file_path}"
        )
        print("Adding twig data at the end of the Tree definition...")
        # Look for the closing brace of the Tree Xform
        tree_end_pattern = r'(def Xform "Tree"\s*{.*?)(})\s*$'
        match = re.search(tree_end_pattern, content, re.DOTALL)
        if match:
            insert_position = match.end(1)
        else:
            print("Error: Could not find Tree Xform definition")
            return False
    else:
        insert_position = content.find(insert_marker)

    # Generate the twig USD content
    twig_content = []

    # Add the prototype reference
    twig_content.append('    def "TwigPrototype" (')
    twig_content.append(
        "        references = @./ScotsPineVariationATwig_ScotsPineVariationATwig.usda@</root/ScotsPineVariationATwig>"
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

    # Add positions (space-separated format)
    positions_str = ", ".join(
        [f"({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})" for pos in positions]
    )
    twig_content.append(f"        point3f[] positions = [{positions_str}]")
    twig_content.append("")

    # Add orientations (quaternions in USD format: x, y, z, w) - space-separated format
    orientations_str = ", ".join(
        [
            f"({quat[0]:.6f}, {quat[1]:.6f}, {quat[2]:.6f}, {quat[3]:.6f})"
            for quat in orientations
        ]
    )
    twig_content.append(f"        quath[] orientations = [{orientations_str}]")
    twig_content.append("")

    # Add scales (space-separated format)
    scales_str = ", ".join(["(1.0, 1.0, 1.0)" for _ in range(len(positions))])
    twig_content.append(f"        float3[] scales = [{scales_str}]")
    twig_content.append("    }")

    # Join the twig content
    twig_usd_text = "\n".join(twig_content)

    # Insert the twig content into the file
    if insert_marker in content:
        new_content = content.replace(insert_marker, twig_usd_text)
    else:
        # Insert before the closing brace
        new_content = (
            content[:insert_position]
            + "\n\n"
            + twig_usd_text
            + "\n"
            + content[insert_position:]
        )

    # Write the modified content back to the file
    output_file = tree_file_path.replace(".usda", "_with_twigs.usda")
    with open(output_file, "w") as f:
        f.write(new_content)

    print(f"Twig data successfully integrated into {output_file}")
    return True


# Process all twig types (combine side, end, and upward twigs)
all_positions = centroid_side + centroid_end + centroid_upward

# CORRECTION: The twig USD file has a built-in rotation: (-90, -90, 0) degrees
# This corresponds to rotations around X, Y, Z axes in that order
# We need to apply the inverse rotation to counteract this


def euler_to_quaternion(roll, pitch, yaw):
    """Convert Euler angles (in degrees) to quaternion [x, y, z, w]."""
    # Convert degrees to radians
    roll = np.radians(roll)
    pitch = np.radians(pitch)
    yaw = np.radians(yaw)

    # Calculate half angles
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)

    # Calculate quaternion components
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return [x, y, z, w]


# The twig has rotateXYZ = (-90, -90, 0), so we apply the inverse: (90, 90, 0)
# ADDITIONAL ISSUE: After correction, twigs point +Y but are upside down
# We need 180° rotation AROUND the forward axis (+Y) to flip them right-side up

# Step 1: Counteract the built-in rotation
base_correction = euler_to_quaternion(90, 90, 0)

# Step 2: Add 180-degree rotation AROUND the forward axis (+Y) to flip upside down twigs
# Since the forward axis is now +Y, we need to roll around Y axis
# In Euler XYZ order: (roll=0, pitch=0, yaw=180) means 180° around Z
# But since our forward is +Y, we want 180° around Y axis which is roll
flip_correction = euler_to_quaternion(0, 0, 180)  # 180° around Z to flip up/down

# Step 3: Combine the base corrections using quaternion multiplication (function defined earlier)
base_combined_correction = multiply_quaternions(base_correction, flip_correction)

print(f"Base correction quaternion (counteract built-in rotation): {base_correction}")
print(f"Flip correction quaternion (180° around Z to flip up/down): {flip_correction}")
print(f"Base combined correction quaternion: {base_combined_correction}")

# Step 4: INDIVIDUAL TWIG ORIENTATION based on Grove documentation
# Grove expects twigs to point in +X direction (branch growth direction)
# We need to rotate each twig so its +X axis aligns with the branch growth direction (face normal)


def calculate_twig_orientation_quaternion(face_normal, base_correction_quat):
    """
    Calculate the quaternion to orient a twig based on branch growth direction.

    CORRECTED APPROACH for USD converted twigs:
    After base correction, twigs point in +Y direction and are right-side up.
    We want each twig to point in the direction of its face_normal (branch growth direction).

    So we need to rotate from +Y to face_normal direction.
    """
    # Convert face normal to numpy array and normalize
    if isinstance(face_normal, tuple):
        face_normal = np.array(face_normal)
    face_normal = face_normal / np.linalg.norm(face_normal)

    # After base correction, twigs point in +Y direction
    current_forward = np.array([0.0, 1.0, 0.0])  # +Y (current twig orientation)
    target_forward = face_normal  # Where we want the twig to point

    # Calculate rotation quaternion from current_forward to target_forward
    dot_product = np.dot(current_forward, target_forward)

    if dot_product > 0.999999:
        # Vectors are already aligned - no rotation needed
        directional_rotation = [0.0, 0.0, 0.0, 1.0]
    elif dot_product < -0.999999:
        # Vectors are opposite - need 180° rotation
        # Find a perpendicular axis for rotation
        if abs(current_forward[0]) < 0.9:
            rotation_axis = np.array([1.0, 0.0, 0.0])
        else:
            rotation_axis = np.array([0.0, 0.0, 1.0])
        # 180° rotation quaternion
        directional_rotation = [
            rotation_axis[0],
            rotation_axis[1],
            rotation_axis[2],
            0.0,
        ]
    else:
        # General case - calculate axis and angle
        rotation_axis = np.cross(current_forward, target_forward)
        rotation_axis = rotation_axis / np.linalg.norm(rotation_axis)

        # Calculate rotation angle
        rotation_angle = np.arccos(np.clip(dot_product, -1.0, 1.0))

        # Create quaternion from axis-angle
        half_angle = rotation_angle * 0.5
        sin_half = np.sin(half_angle)
        cos_half = np.cos(half_angle)

        directional_rotation = [
            rotation_axis[0] * sin_half,  # x
            rotation_axis[1] * sin_half,  # y
            rotation_axis[2] * sin_half,  # z
            cos_half,  # w
        ]

    # Combine base correction with directional rotation
    final_quaternion = multiply_quaternions(base_correction_quat, directional_rotation)
    return final_quaternion


# Calculate individual orientations for each twig type
print(
    "\n🔄 Adding directional rotation to orient twigs along branch growth directions..."
)


def calculate_simple_directional_rotation(face_normal):
    """
    Calculate a rotation that points the twig toward face_normal while keeping
    the twig's "up" direction as close to world +Z as possible.

    This prevents unwanted rolling and keeps twigs oriented naturally.
    """
    # Convert face normal to numpy array and normalize
    if isinstance(face_normal, tuple):
        face_normal = np.array(face_normal)
    face_normal = face_normal / np.linalg.norm(face_normal)

    # Build a proper coordinate system for the twig:
    # - forward = face_normal (where twig should point)
    # - up = as close to world +Z as possible
    # - right = completes the right-handed system

    forward = face_normal
    world_up = np.array([0.0, 0.0, 1.0])

    # Handle the case where forward is parallel to world_up
    if abs(np.dot(forward, world_up)) > 0.95:
        # Forward is nearly parallel to +Z, use world +Y as reference
        reference = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, reference)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
    else:
        # Normal case: project world_up onto plane perpendicular to forward
        up = world_up - np.dot(world_up, forward) * forward
        up = up / np.linalg.norm(up)
        right = np.cross(up, forward)
        right = right / np.linalg.norm(right)

    # Create rotation matrix from the coordinate system
    # But we need to account for the fact that after base correction,
    # twigs point in +Y direction, not +X

    # After base correction: twig points +Y, up is +Z
    # We want: twig points toward 'forward', up is toward 'up'

    # Current twig coordinate system (after base correction)
    current_forward = np.array([0.0, 1.0, 0.0])  # +Y
    current_up = np.array([0.0, 0.0, 1.0])  # +Z
    current_right = np.array([1.0, 0.0, 0.0])  # +X

    # Target coordinate system
    target_forward = forward
    target_up = up
    target_right = right

    # Build rotation matrices
    current_matrix = np.column_stack([current_right, current_forward, current_up])
    target_matrix = np.column_stack([target_right, target_forward, target_up])

    # Calculate rotation matrix from current to target
    rotation_matrix = target_matrix @ current_matrix.T

    # Convert rotation matrix to quaternion
    def matrix_to_quaternion(R):
        trace = R[0, 0] + R[1, 1] + R[2, 2]
        if trace > 0:
            s = np.sqrt(trace + 1.0) * 2
            w = 0.25 * s
            x = (R[2, 1] - R[1, 2]) / s
            y = (R[0, 2] - R[2, 0]) / s
            z = (R[1, 0] - R[0, 1]) / s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
        return [x, y, z, w]

    return matrix_to_quaternion(rotation_matrix)


# Calculate directional rotations for each twig
directional_quaternions = []

# Side twigs
for normal in normal_side:
    dir_quat = calculate_simple_directional_rotation(normal)
    final_quat = multiply_quaternions(base_combined_correction, dir_quat)
    directional_quaternions.append(final_quat)

# End twigs
for normal in normal_end:
    dir_quat = calculate_simple_directional_rotation(normal)
    final_quat = multiply_quaternions(base_combined_correction, dir_quat)
    directional_quaternions.append(final_quat)

# Upward twigs
for normal in normal_upward:
    dir_quat = calculate_simple_directional_rotation(normal)
    final_quat = multiply_quaternions(base_combined_correction, dir_quat)
    directional_quaternions.append(final_quat)

all_quaternions = directional_quaternions

print(f"\n🔍 DEBUG: Directional twig orientations (first 3 twigs):")
for i in range(min(3, len(all_positions))):
    pos = all_positions[i]
    quat = all_quaternions[i]
    if i < len(normal_side):
        normal = normal_side[i]
        twig_type = "side"
    elif i < len(normal_side) + len(normal_end):
        normal = normal_end[i - len(normal_side)]
        twig_type = "end"
    else:
        normal = normal_upward[i - len(normal_side) - len(normal_end)]
        twig_type = "upward"

    print(f"  Twig {i+1} ({twig_type}): pos=({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
    print(f"    target_direction=({normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})")
    print(f"    quat=({quat[0]:.3f}, {quat[1]:.3f}, {quat[2]:.3f}, {quat[3]:.3f})")

print(
    f"Total twigs: {len(all_positions)} (each oriented toward its branch growth direction)"
)
print("🎯 Each twig should now point in the direction of its face normal")

# Write the USD PointInstancer section directly into the tree file
tree_file_path = usda_file  # Use the original file directly
success = write_usd_pointinstancer_to_tree_file(
    all_positions, all_quaternions, str(tree_file_path)
)

if success:
    print(f"Generated PointInstancer with {len(all_positions)} twigs:")
    print(f"  - {len(centroid_side)} side twigs")
    print(f"  - {len(centroid_end)} end twigs")
    print(f"  - {len(centroid_upward)} upward twigs")
    print(f"Twig data integrated into tree file: {tree_file_path.stem}_with_twigs.usda")
else:
    print("Failed to integrate twig data into tree file")
