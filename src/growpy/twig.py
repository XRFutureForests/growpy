"""
Simplified twig enhancement for USD files - using Grove's face-based system.

GROVE TWIG SYSTEM:
- Each face (triangle, quad, or polygon) marked with primvars:Twig* gets a twig
- Twig position = face center (centroid of all vertices)
- Twig direction = face surface normal (using Newell's method for any polygon)
- Works with any polygon, not just triangles!
"""

import math
import sys
from pathlib import Path
from typing import List

import numpy as np
from pxr import Usd, UsdGeom, Vt


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

    return normal


def calculate_xyz_rotation_angles(normal):
    """Calculate the X, Y, Z rotation angles for twig orientation.

    Based on user requirements:
    - Default orientation: pointing towards diagonal between x and -y (roughly (1, -1, 0))
    - Y rotation: yaw around Z-axis (horizontal turning)
    - X rotation: roll around the pointing direction
    - Z rotation: pitch around the perpendicular horizontal axis

    Args:
        normal: tuple (x, y, z) representing the target direction (normalized)

    Returns:
        tuple: (rot_x, rot_y, rot_z) angles in degrees
               rot_x - roll around pointing direction
               rot_y - yaw around Z-axis (horizontal turning)
               rot_z - pitch around perpendicular horizontal axis
    """
    nx, ny, nz = normal

    # Calculate Y rotation (yaw) - rotation around Z-axis
    # This determines the horizontal direction
    rot_y_rad = math.atan2(-ny, nx)  # From (1, 0, 0) to (nx, ny, 0) projection

    # Calculate Z rotation (pitch) - rotation to tilt up/down
    # After Y rotation, we need to account for the vertical component
    horizontal_length = math.sqrt(nx * nx + ny * ny)
    rot_z_rad = math.atan2(nz, horizontal_length)

    # For now, keep X rotation (roll) as 0 to avoid unwanted twisting
    # This can be adjusted later if specific roll control is needed
    rot_x_rad = 0.0

    # Convert to degrees
    rot_x = math.degrees(rot_x_rad)
    rot_y = math.degrees(rot_y_rad)
    rot_z = math.degrees(rot_z_rad)

    return (rot_x, rot_y, rot_z)


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
    """Convert a direction vector (normal) to a quaternion rotation.
    This rotates the twig from its default orientation to align with the face normal.

    Args:
        normal: tuple (x, y, z) representing the face normal direction

    Returns:
        tuple: (w, x, y, z) quaternion components in USD format
    """
    # Normalize the input vector
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length > 0:
        normal = (nx / length, ny / length, nz / length)
    else:
        return (1, 0, 0, 0)  # Identity quaternion for zero vector

    # Calculate the XYZ rotation angles needed
    rot_x, rot_y, rot_z = calculate_xyz_rotation_angles(normal)

    # Convert angles to quaternion
    quaternion = xyz_angles_to_quaternion(rot_x, rot_y, rot_z)

    return quaternion


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


def main():
    """Main function to process Grove USD and add twigs."""
    # Configuration
    usda_file = Path(__file__).parent.parent.parent / "data" / "output" / "small_demo" / "Norwayspruce_LOD2_Medium_002.usda"
    twig_file_path = "../../assets/twigs/ScotsPineTwig/ScotsPineVariationATwig_ScotsPineVariationATwig.usda"
    twig_xform_name = "ScotsPineVariationATwig"

    # Open the USD stage
    stage = Usd.Stage.Open(str(usda_file))
    tree = stage.GetPrimAtPath("/Tree/Tree")

    # Extract mesh data
    face_vertex_counts = list(tree.GetAttribute("faceVertexCounts").Get())
    face_vertex_indices = list(tree.GetAttribute("faceVertexIndices").Get())
    points = list(tree.GetAttribute("points").Get())

    # Extract twig attributes
    twig_end = list(tree.GetAttribute("primvars:TwigEnd").Get())
    twig_side = list(tree.GetAttribute("primvars:TwigSide").Get())
    twig_upward = list(tree.GetAttribute("primvars:TwigUpward").Get())

    # Convert to face lists
    face_vertex_indices_np = np.array(face_vertex_indices)
    face_vertex_counts_np = np.array(face_vertex_counts)
    split_indices = np.cumsum(face_vertex_counts_np)[:-1]
    faces = np.split(face_vertex_indices_np, split_indices)
    faces_list = [list(face) for face in faces]

    # Collect twig data
    all_positions = []
    all_orientations = []

    # Process each face
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
            # Calculate face center and normal
            face_center = calculate_face_center(points, face)
            normal = calculate_face_normal(points, face)

            # Place twig so its base (attachment point) sits on the surface
            # From twig extent: X ranges from ~0 to 0.175, so twig base is at X=0
            # Offset the position slightly outward along the normal
            base_offset = 0.001  # Very small offset to prevent Z-fighting
            position = (
                face_center[0] + normal[0] * base_offset,
                face_center[1] + normal[1] * base_offset,
                face_center[2] + normal[2] * base_offset,
            )
            all_positions.append(position)

            # Calculate orientation quaternion
            rot_x, rot_y, rot_z = calculate_xyz_rotation_angles(normal)
            quaternion = xyz_angles_to_quaternion(rot_x, rot_y, rot_z)
            all_orientations.append(quaternion)

    print(f"\n🌲 Twig placement summary:")
    print(f"  Total twigs: {len(all_positions)}")

    # Write the USD PointInstancer
    write_usd_pointinstancer(
        all_positions, all_orientations, str(usda_file), twig_file_path, twig_xform_name
    )


if __name__ == "__main__":
    print("🔧 Fixed quaternion rotation system")
    print("Individual rotations:")
    print("- Y rotation: yaw (horizontal turning)")
    print("- Z rotation: pitch (vertical tilt)")
    print("- X rotation: roll (around pointing direction)")
    print()

    # Test the fixed implementation
    # test_rotations()

    # Run the main twig processing with fixed rotations
    main()
