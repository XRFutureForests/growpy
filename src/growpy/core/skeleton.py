"""Pure skeleton computation without USD dependencies.

This module contains the core skeleton building logic - bone hierarchy,
joint indices, and vertex weights - as pure Python functions without
any USD I/O dependencies.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Vector3:
    """Simple 3D vector."""

    x: float
    y: float
    z: float

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __truediv__(self, scalar: float) -> "Vector3":
        return Vector3(self.x / scalar, self.y / scalar, self.z / scalar)

    def length(self) -> float:
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class JointTransform:
    """Joint transform with translation and rotation."""

    translation: Vector3
    rotation_matrix: Optional[List[List[float]]] = None  # 3x3 rotation matrix

    def is_identity_rotation(self) -> bool:
        """Check if rotation is identity."""
        if self.rotation_matrix is None:
            return True
        # Check if matrix is identity (diagonal 1s, off-diagonal 0s)
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        return all(
            abs(self.rotation_matrix[i][j] - identity[i][j]) < 1e-6
            for i in range(3)
            for j in range(3)
        )


@dataclass
class SkeletonHierarchy:
    """Complete skeleton hierarchy data."""

    joint_names: List[str]
    joint_parents: List[int]  # Parent joint index for each joint (-1 for root)
    bind_transforms: List[JointTransform]
    rest_transforms: List[JointTransform]
    bone_to_joint_map: Dict[int, int]  # Maps bone ID to joint index


def convert_grove_vector_to_vector3(grove_vector: Any) -> Vector3:
    """Convert Grove Vector to Vector3.

    Args:
        grove_vector: Grove Vector object with as_tuple() method

    Returns:
        Vector3 representation
    """
    coords = grove_vector.as_tuple()
    return Vector3(coords[0], coords[1], coords[2])


def calculate_rotation_to_align(
    from_vec: Vector3, to_vec: Vector3
) -> Optional[List[List[float]]]:
    """Calculate rotation matrix to align from_vec to to_vec.

    Args:
        from_vec: Source direction vector
        to_vec: Target direction vector

    Returns:
        3x3 rotation matrix as list of lists, or None if vectors are parallel
    """
    # Normalize vectors
    from_len = from_vec.length()
    to_len = to_vec.length()

    if from_len < 1e-6 or to_len < 1e-6:
        return None

    from_norm = from_vec / from_len
    to_norm = to_vec / to_len

    # Check if already aligned
    dot = from_norm.x * to_norm.x + from_norm.y * to_norm.y + from_norm.z * to_norm.z
    if abs(dot - 1.0) < 1e-6:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]  # Identity
    if abs(dot + 1.0) < 1e-6:
        # 180 degree rotation - pick arbitrary perpendicular axis
        return [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]

    # Calculate rotation axis (cross product)
    axis_x = from_norm.y * to_norm.z - from_norm.z * to_norm.y
    axis_y = from_norm.z * to_norm.x - from_norm.x * to_norm.z
    axis_z = from_norm.x * to_norm.y - from_norm.y * to_norm.x

    axis = Vector3(axis_x, axis_y, axis_z)
    axis_len = axis.length()

    if axis_len < 1e-6:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]  # Identity

    axis = axis / axis_len

    # Rodrigues' rotation formula
    angle = (1 - dot**2) ** 0.5  # sin(angle) from cross product magnitude
    cos_angle = dot
    one_minus_cos = 1 - cos_angle

    # Build rotation matrix
    x, y, z = axis.x, axis.y, axis.z
    matrix = [
        [
            cos_angle + x * x * one_minus_cos,
            x * y * one_minus_cos - z * angle,
            x * z * one_minus_cos + y * angle,
        ],
        [
            y * x * one_minus_cos + z * angle,
            cos_angle + y * y * one_minus_cos,
            y * z * one_minus_cos - x * angle,
        ],
        [
            z * x * one_minus_cos - y * angle,
            z * y * one_minus_cos + x * angle,
            cos_angle + z * z * one_minus_cos,
        ],
    ]

    return matrix


def build_skeleton_hierarchy(bones_info: List[Tuple]) -> SkeletonHierarchy:
    """Build skeleton hierarchy from Grove bone data.

    Args:
        bones_info: List of bone tuples from Grove.tag_bone_id():
                   [(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]

    Returns:
        SkeletonHierarchy with joint names, parents, transforms, and mappings
    """
    joints = []
    joint_parents = []
    bind_transforms = []
    rest_transforms = []

    # Root joint at origin
    joints.append("joint_0")
    joint_parents.append(-1)
    root_transform = JointTransform(translation=Vector3(0, 0, 0))
    bind_transforms.append(root_transform)
    rest_transforms.append(root_transform)

    # Map bone indices to joint indices
    bone_to_joint = {-1: 0}  # Root bone maps to joint 0

    # Track world-space positions for calculating relative transforms
    world_head_positions = {0: Vector3(0, 0, 0)}
    world_tail_positions = {0: Vector3(0, 0, 0)}

    # Process each bone
    for i, bone in enumerate(bones_info):
        bone_idx = i
        parent_bone_idx = int(bone[1]) if bone[1] >= 0 else -1
        head_vec = convert_grove_vector_to_vector3(bone[2])
        tail_vec = convert_grove_vector_to_vector3(bone[3])

        # Find parent joint
        parent_joint_idx = bone_to_joint.get(parent_bone_idx, 0)
        joint_parents.append(parent_joint_idx)

        # Create joint
        joint_idx = len(joints)
        joint_name = f"joint_{joint_idx}"
        joints.append(joint_name)
        bone_to_joint[bone_idx] = joint_idx

        # Calculate relative position (offset from parent's head position)
        parent_pos = world_head_positions.get(parent_joint_idx, Vector3(0, 0, 0))
        relative_pos = head_vec - parent_pos

        # Calculate bone direction and rotation
        bone_vector = tail_vec - head_vec
        bone_length = bone_vector.length()

        if bone_length > 1e-4:
            bone_dir = bone_vector / bone_length
            default_dir = Vector3(0, 0, 1)  # Z-up default
            rotation_matrix = calculate_rotation_to_align(default_dir, bone_dir)

            transform = JointTransform(
                translation=relative_pos, rotation_matrix=rotation_matrix
            )
            bind_transforms.append(transform)
            rest_transforms.append(transform)
        else:
            # Zero-length bone
            transform = JointTransform(translation=relative_pos)
            bind_transforms.append(transform)
            rest_transforms.append(transform)

        # Store world positions for child bones
        world_head_positions[joint_idx] = head_vec
        world_tail_positions[joint_idx] = tail_vec

    return SkeletonHierarchy(
        joint_names=joints,
        joint_parents=joint_parents,
        bind_transforms=bind_transforms,
        rest_transforms=rest_transforms,
        bone_to_joint_map=bone_to_joint,
    )


def calculate_vertex_weights(
    model: Any, bone_to_joint_map: Dict[int, int], element_size: int = 2
) -> Tuple[List[int], List[float]]:
    """Calculate vertex skinning weights from Grove model.

    Args:
        model: Grove model with point_attribute_bone_id
        bone_to_joint_map: Mapping from bone ID to joint index
        element_size: Number of joint influences per vertex (default: 2)

    Returns:
        Tuple of (joint_indices_array, joint_weights_array)
        Arrays are flattened with element_size entries per vertex
    """
    # DEBUG BREAKPOINT 4: Converting Grove bone_id to USD jointIndices
    print(f"\n[DEBUG] PHASE 4: calculate_vertex_weights called")

    if not hasattr(model, "point_attribute_bone_id"):
        print(f"[DEBUG] ✗ Model has no bone_id - returning empty arrays")
        return [], []

    joint_indices_array = []
    joint_weights_array = []

    bone_ids = model.point_attribute_bone_id
    weights = (
        model.point_attribute_bone_weight
        if hasattr(model, "point_attribute_bone_weight")
        else [1.0] * len(bone_ids)
    )

    print(f"[DEBUG] Converting {len(bone_ids)} vertices from bone_id to joint indices")
    print(f"[DEBUG] Bone-to-joint mapping has {len(bone_to_joint_map)} entries")
    print(
        f"[DEBUG] Sample bone_to_joint_map: {dict(list(bone_to_joint_map.items())[:5])}"
    )

    # Count bone_id usage for debugging
    bone_usage = {}
    for bone_id, weight in zip(bone_ids, weights):
        joint_idx = bone_to_joint_map.get(bone_id, 0)

        # Track which bones are used
        if bone_id not in bone_usage:
            bone_usage[bone_id] = {"count": 0, "joint_idx": joint_idx}
        bone_usage[bone_id]["count"] += 1

        # Add primary joint influence
        joint_indices_array.append(joint_idx)
        joint_weights_array.append(weight)

        # Pad remaining influences with zeros
        for _ in range(element_size - 1):
            joint_indices_array.append(0)
            joint_weights_array.append(0.0)

    print(
        f"[DEBUG] Conversion complete: {len(joint_indices_array)} total entries ({len(bone_ids)} vertices × {element_size})"
    )
    print(f"[DEBUG] Bones used: {len(bone_usage)} unique bone IDs")
    print(f"[DEBUG] Sample bone usage: {dict(list(bone_usage.items())[:5])}")
    print(f"[DEBUG] Sample output joint_indices (first 20): {joint_indices_array[:20]}")
    print(
        f"[DEBUG] Sample output joint_weights (first 20): {[f'{w:.3f}' for w in joint_weights_array[:20]]}\n"
    )

    return joint_indices_array, joint_weights_array


def get_bone_data_from_grove(
    grove: Any,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> List[Tuple]:
    """Get bone data from Grove instance.

    Args:
        grove: Grove instance with tag_bone_id method
        skeleton_length: Bone length multiplier
        skeleton_reduce: Bone reduction factor (higher = fewer bones)
        skeleton_bias: Weight bias for skinning
        skeleton_connected: Use connected bone hierarchy

    Returns:
        List of bone tuples: [(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]
    """
    # DEBUG BREAKPOINT 5: Extracting bone hierarchy
    print(f"\n[DEBUG] PHASE 2B: get_bone_data_from_grove called")
    print(
        f"[DEBUG] Parameters: length={skeleton_length}, reduce={skeleton_reduce}, bias={skeleton_bias}, connected={skeleton_connected}"
    )

    bones_info = grove.tag_bone_id(
        skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
    )

    if bones_info:
        print(f"[DEBUG] ✓ tag_bone_id returned {len(bones_info)} bones")
        # Show first few bones
        for i, bone in enumerate(bones_info[:3]):
            bone_idx, parent_idx, head, tail, radius = bone
            print(
                f"[DEBUG]   Bone {i}: idx={bone_idx}, parent={parent_idx}, radius={radius:.4f}"
            )
        if len(bones_info) > 3:
            print(f"[DEBUG]   ... and {len(bones_info)-3} more bones")
    else:
        print(f"[DEBUG] ✗ tag_bone_id returned no bones!")
    print()

    return bones_info if bones_info else []
