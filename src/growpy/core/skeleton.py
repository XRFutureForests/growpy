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
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    if abs(dot + 1.0) < 1e-6:
        return [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]

    # Calculate rotation axis (cross product)
    axis_x = from_norm.y * to_norm.z - from_norm.z * to_norm.y
    axis_y = from_norm.z * to_norm.x - from_norm.x * to_norm.z
    axis_z = from_norm.x * to_norm.y - from_norm.y * to_norm.x

    axis = Vector3(axis_x, axis_y, axis_z)
    axis_len = axis.length()

    if axis_len < 1e-6:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    axis = axis / axis_len
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

    joints.append("root")
    joint_parents.append(-1)
    root_transform = JointTransform(translation=Vector3(0, 0, 0))
    bind_transforms.append(root_transform)
    rest_transforms.append(root_transform)

    bone_to_joint = {-1: 0}
    world_head_positions = {0: Vector3(0, 0, 0)}
    world_tail_positions = {0: Vector3(0, 0, 0)}

    for i, bone in enumerate(bones_info):
        bone_idx = i
        parent_bone_idx = int(bone[1]) if bone[1] >= 0 else -1
        head_vec = convert_grove_vector_to_vector3(bone[2])
        tail_vec = convert_grove_vector_to_vector3(bone[3])

        parent_joint_idx = bone_to_joint.get(parent_bone_idx, 0)
        joint_parents.append(parent_joint_idx)

        joint_idx = len(joints)
        # Use simple numeric names after root: joint_1, joint_2, etc.
        joint_name = f"joint_{joint_idx}"
        joints.append(joint_name)
        bone_to_joint[bone_idx] = joint_idx

        parent_pos = world_head_positions.get(parent_joint_idx, Vector3(0, 0, 0))
        relative_pos = head_vec - parent_pos
        bone_vector = tail_vec - head_vec
        bone_length = bone_vector.length()

        if bone_length > 1e-4:
            bone_dir = bone_vector / bone_length
            default_dir = Vector3(0, 0, 1)
            rotation_matrix = calculate_rotation_to_align(default_dir, bone_dir)

            transform = JointTransform(
                translation=relative_pos, rotation_matrix=rotation_matrix
            )
            bind_transforms.append(transform)
            rest_transforms.append(transform)
        else:
            transform = JointTransform(translation=relative_pos)
            bind_transforms.append(transform)
            rest_transforms.append(transform)
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
    model: Any,
    bone_to_joint_map: Dict[int, int],
    bones_info: List[Tuple],
    element_size: int = 2,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "smooth",
) -> Tuple[List[int], List[float]]:
    """Calculate vertex skinning weights with reduced branch root weights.

    Implements weight reduction at branch junctions to allow natural bone chain
    interpolation. Branch vertices near their parent connection receive weights
    between 0.5-1.0, allowing the skeletal system to blend along the bone hierarchy.

    Args:
        model: Grove model with point_attribute_bone_id and points
        bone_to_joint_map: Mapping from bone ID to joint index
        bones_info: Full bone data from grove.tag_bone_id()
        element_size: Number of weights per vertex (1 for single-bone binding)
        junction_blend_distance: Distance over which to reduce weights (meters)
        blend_mode: Falloff function - 'linear', 'smooth', or 'cosine'

    Returns:
        Tuple of (joint_indices_array, joint_weights_array) with reduced weights at junctions
    """
    if not hasattr(model, "point_attribute_bone_id") or not hasattr(model, "points"):
        return [], []

    joint_indices_array = []
    joint_weights_array = []

    bone_ids = model.point_attribute_bone_id
    vertices = [(p.x, p.y, p.z) for p in model.points]

    # Diagnostic output (can be disabled in production)
    debug_blend = False  # Set to True for detailed diagnostics

    # Build branch topology: identify branch root bones and their parents
    # Store both head (junction) and tail positions for distance-along-bone calculation
    # CRITICAL: bone_to_joint_map uses GLOBAL bone IDs as keys (from vertex bone_id attributes)
    # We need to reverse-lookup from global IDs to local indices for bones_info access
    global_to_local_bone = {}  # Reverse map: global bone ID -> local bone index
    for global_id, local_idx in bone_to_joint_map.items():
        global_to_local_bone[global_id] = local_idx

    branch_info = (
        {}
    )  # {GLOBAL_bone_id: (is_branch_root, parent_GLOBAL_bone_id, head_pos, tail_pos)}
    branch_root_count = 0
    branch_root_bones = []

    # Debug: examine first few bones
    if debug_blend and len(bones_info) > 0:
        print(f"[Junction Blending DEBUG] First 5 bones from bones_info:")
        for i in range(min(5, len(bones_info))):
            bone = bones_info[i]
            print(
                f"  Bone {i}: is_tree_root={bone[0]}, parent_idx={bone[1]}, is_branch_root={bone[6] if len(bone) > 6 else 'N/A'}"
            )

    for local_idx, bone in enumerate(bones_info):
        # Find the global bone ID for this local index
        global_bone_id = None
        for gid, lidx in bone_to_joint_map.items():
            if lidx == local_idx:
                global_bone_id = gid
                break

        if global_bone_id is None:
            continue  # Skip bones not in map

        is_branch_root = bone[6] if len(bone) > 6 else False
        parent_local_idx = int(bone[1])
        head_pos = bone[2].as_tuple() if hasattr(bone[2], "as_tuple") else (0, 0, 0)
        tail_pos = bone[3].as_tuple() if hasattr(bone[3], "as_tuple") else (0, 0, 0)

        # CRITICAL DISCOVERY: bones_info contains GLOBAL parent indices, not local!
        # parent_local_idx is actually parent_GLOBAL_idx
        # For junction blending, only process bones whose parent is within THIS tree
        parent_global_id = parent_local_idx if parent_local_idx >= 0 else -1

        # Skip bones whose parent is outside this tree (inter-tree references)
        if parent_global_id >= 0 and parent_global_id not in bone_to_joint_map:
            # Parent is in a different tree - skip for junction blending
            parent_global_id = None

        branch_info[global_bone_id] = (
            is_branch_root,
            parent_global_id,
            head_pos,
            tail_pos,
        )
        if is_branch_root:
            branch_root_count += 1
            branch_root_bones.append(global_bone_id)

    # Print diagnostics after building branch_info
    if debug_blend:
        print(
            f"[Junction Blending] Found {branch_root_count} branch root bones out of {len(bones_info)} total bones"
        )
        print(
            f"[Junction Blending] Branch root bone IDs: {branch_root_bones[:10]}{'...' if len(branch_root_bones) > 10 else ''}"
        )
        print(
            f"[Junction Blending] Blend distance: {junction_blend_distance}m, Mode: {blend_mode}"
        )
        # Show vertex bone ID range for debugging
        if len(bone_ids) > 0:
            unique_vertex_bones = set(bone_ids)
            print(
                f"[Junction Blending] Vertex bone IDs range: {min(unique_vertex_bones)} to {max(unique_vertex_bones)}, {len(unique_vertex_bones)} unique"
            )
            # Check overlap with branch_info
            overlap = unique_vertex_bones.intersection(set(branch_info.keys()))
            print(
                f"[Junction Blending] Overlap with branch_info: {len(overlap)} bone IDs"
            )

    # Process each vertex
    reduced_weight_count = 0
    full_weight_count = 0
    branch_verts_checked = 0
    branch_verts_in_range = 0

    for vert_idx, vertex_bone_id in enumerate(bone_ids):
        vertex_pos = vertices[vert_idx]

        # Check if this vertex's bone is a branch root (needs weight reduction)
        # vertex_bone_id is a GLOBAL bone ID from model.point_attribute_bone_id
        if vertex_bone_id in branch_info:
            is_branch_root, parent_global_bone_id, head_pos, tail_pos = branch_info[
                vertex_bone_id
            ]

            # Debug: Track why vertices aren't being processed
            if is_branch_root and (branch_verts_checked == 0 and vert_idx < 10):
                if debug_blend:
                    print(
                        f"  [DEBUG] Vert {vert_idx}: bone={vertex_bone_id}, is_branch={is_branch_root}, parent={parent_global_bone_id}, in_map={parent_global_bone_id in bone_to_joint_map if parent_global_bone_id is not None else 'None'}"
                    )

            if (
                is_branch_root
                and parent_global_bone_id is not None
                and parent_global_bone_id >= 0
                and parent_global_bone_id in bone_to_joint_map
            ):
                branch_verts_checked += 1

                # Calculate distance along the bone from junction (head) to vertex
                # This is more accurate than pure 3D distance as vertices follow the bone
                bone_vector = (
                    tail_pos[0] - head_pos[0],
                    tail_pos[1] - head_pos[1],
                    tail_pos[2] - head_pos[2],
                )
                bone_length = _distance_3d((0, 0, 0), bone_vector)

                if bone_length > 1e-6:
                    # Project vertex onto bone to get distance along bone axis
                    vert_from_head = (
                        vertex_pos[0] - head_pos[0],
                        vertex_pos[1] - head_pos[1],
                        vertex_pos[2] - head_pos[2],
                    )
                    # Dot product to get projection length
                    proj_length = (
                        vert_from_head[0] * bone_vector[0]
                        + vert_from_head[1] * bone_vector[1]
                        + vert_from_head[2] * bone_vector[2]
                    ) / bone_length

                    # Clamp to bone length (vertices shouldn't be beyond bone endpoints)
                    dist_along_bone = max(0.0, min(proj_length, bone_length))
                else:
                    # Zero-length bone, use direct distance
                    dist_along_bone = _distance_3d(vertex_pos, head_pos)

                if dist_along_bone < junction_blend_distance:
                    branch_verts_in_range += 1
                    # Within blend radius: use reduced weight (0.5 at junction, 1.0 at blend_distance)
                    branch_joint_idx = bone_to_joint_map.get(vertex_bone_id, 0)

                    # Calculate reduced weight using selected falloff function
                    # t ranges from 0.0 (at junction) to 1.0 (at blend_distance)
                    t = dist_along_bone / junction_blend_distance
                    weight_factor = _apply_falloff(t, blend_mode)

                    # DUAL BONE WEIGHTING for proper skeletal blending
                    # Child bone weight: 0.5 (at junction) → 1.0 (at blend_distance)
                    child_weight = 0.5 + 0.5 * weight_factor
                    # Parent bone weight: 0.5 (at junction) → 0.0 (at blend_distance)
                    parent_weight = 1.0 - child_weight

                    parent_joint_idx = bone_to_joint_map.get(parent_global_bone_id, 0)

                    # Store dual bone influences (elementSize must be 2)
                    joint_indices_array.append(branch_joint_idx)
                    joint_weights_array.append(child_weight)
                    joint_indices_array.append(parent_joint_idx)
                    joint_weights_array.append(parent_weight)

                    # Pad to element_size if needed (for elementSize > 2)
                    for _ in range(element_size - 2):
                        joint_indices_array.append(0)
                        joint_weights_array.append(0.0)

                    reduced_weight_count += 1
                    continue
        # Default case: single bone binding with full weight (dual bone format)
        joint_idx = bone_to_joint_map.get(vertex_bone_id, 0)

        # Store as dual-bone with second bone having zero weight (for elementSize=2)
        joint_indices_array.append(joint_idx)
        joint_weights_array.append(1.0)
        joint_indices_array.append(0)  # Dummy second bone (root)
        joint_weights_array.append(0.0)

        # Pad to element_size if needed (for elementSize > 2)
        for _ in range(element_size - 2):
            joint_indices_array.append(0)
            joint_weights_array.append(0.0)

        full_weight_count += 1

    if debug_blend or reduced_weight_count > 0:
        print(
            f"[Junction Blending] Branch root vertices checked: {branch_verts_checked}"
        )
        print(
            f"[Junction Blending] Branch verts with reduced weight: {branch_verts_in_range}"
        )
        print(
            f"[Junction Blending] Vertices with full weight (1.0): {full_weight_count}"
        )
        print(f"[Junction Blending] Total vertices: {len(bone_ids)}")
        if branch_verts_checked > 0:
            print(
                f"[Junction Blending] Weight reduction coverage: {100.0 * branch_verts_in_range / branch_verts_checked:.1f}% of branch root verts"
            )

    return joint_indices_array, joint_weights_array


def _distance_3d(
    p1: Tuple[float, float, float], p2: Tuple[float, float, float]
) -> float:
    """Calculate 3D Euclidean distance between two points."""
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2) ** 0.5


def _apply_falloff(t: float, mode: str) -> float:
    """Apply falloff function for weight blending.

    Args:
        t: Normalized distance (0.0 at junction, 1.0 at blend_distance)
        mode: Falloff function - 'linear', 'smooth', or 'cosine'

    Returns:
        Weight value in range [0.0, 1.0]
    """
    if mode == "smooth":
        # Smoothstep (C1 continuous)
        return t * t * (3.0 - 2.0 * t)
    elif mode == "cosine":
        # Cosine interpolation (natural curve)
        import math

        return 0.5 - 0.5 * math.cos(t * math.pi)
    else:
        # Linear (default)
        return t


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
        skeleton_reduce: Bone reduction factor
        skeleton_bias: Weight bias for skinning
        skeleton_connected: Use connected bone hierarchy

    Returns:
        List of bone tuples: [(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]
    """
    bones_info = grove.tag_bone_id(
        skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
    )

    return bones_info if bones_info else []
