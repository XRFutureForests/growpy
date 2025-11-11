"""Pure twig placement computation without USD dependencies.

This module contains core twig placement logic - extracting twig data from
Grove models and calculating transforms - as pure Python functions without
any USD or Blender I/O dependencies.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TwigPlacement:
    """Twig instance placement data."""

    type: str  # 'twig_long', 'twig_short', 'twig_upward', 'twig_dead'
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    scale: float = 1.0
    bone_id: Optional[int] = None  # Direct bone ID from point_attribute_bone_id
    branch_id: Optional[int] = None  # Branch ID for binding to branch_X joints

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type,
            "position": self.position,
            "normal": self.normal,
            "scale": self.scale,
            "bone_id": self.bone_id,
            "branch_id": self.branch_id,
        }


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
    face_verts = [vertices[i] for i in face]
    center = (
        sum(v[0] for v in face_verts) / len(face_verts),
        sum(v[1] for v in face_verts) / len(face_verts),
        sum(v[2] for v in face_verts) / len(face_verts),
    )

    normal = [0.0, 0.0, 0.0]
    for i in range(len(face_verts)):
        v1 = face_verts[i]
        v2 = face_verts[(i + 1) % len(face_verts)]
        normal[0] += (v1[1] - v2[1]) * (v1[2] + v2[2])
        normal[1] += (v1[2] - v2[2]) * (v1[0] + v2[0])
        normal[2] += (v1[0] - v2[0]) * (v1[1] + v2[1])

    length = math.sqrt(sum(n * n for n in normal))
    if length > 0:
        normal = tuple(n / length for n in normal)
    else:
        normal = (0.0, 0.0, 1.0)

    return center, normal


def normal_to_rotation_matrix(normal: Tuple[float, float, float]) -> List[List[float]]:
    """Convert normal vector to rotation matrix.

    Args:
        normal: Normal vector (x, y, z)

    Returns:
        3x3 rotation matrix as list of lists
    """
    nx, ny, nz = normal

    x_axis = normal

    if abs(nz) > 0.9:
        ref = (1.0, 0.0, 0.0)
    else:
        ref = (0.0, 0.0, 1.0)
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

    z_axis = (
        x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
        x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
        x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0],
    )

    return [
        [x_axis[0], y_axis[0], z_axis[0]],
        [x_axis[1], y_axis[1], z_axis[1]],
        [x_axis[2], y_axis[2], z_axis[2]],
    ]


def rotation_matrix_to_quaternion(
    matrix: List[List[float]],
) -> Tuple[float, float, float, float]:
    """Convert 3x3 rotation matrix to normalized quaternion.

    Args:
        matrix: 3x3 rotation matrix as list of lists

    Returns:
        Normalized quaternion (w, x, y, z)
    """
    m00, m01, m02 = matrix[0]
    m10, m11, m12 = matrix[1]
    m20, m21, m22 = matrix[2]

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

    length = math.sqrt(w * w + x * x + y * y + z * z)
    if length > 0:
        return (w / length, x / length, y / length, z / length)
    else:
        return (1.0, 0.0, 0.0, 0.0)


def extract_twig_placements_from_model(
    model: Any,
    twig_types: Optional[List[str]] = None,
    bones_info: Optional[List] = None,
) -> Dict[str, List[TwigPlacement]]:
    """Extract twig placement data from Grove model.

    Args:
        model: Grove model with twig location/orientation/direction methods
        twig_types: List of twig types to extract (default: all known types)
        bones_info: Optional skeleton bones list for branch-based binding

    Returns:
        Dictionary mapping twig type to list of TwigPlacement objects
    """
    if twig_types is None:
        twig_types = ["twig_long", "twig_short", "twig_upward", "twig_dead"]

    placements = {twig_type: [] for twig_type in twig_types}

    # Use Grove API methods for twig data - these return flat lists with 3 floats per twig
    twig_locations = model.get_twig_locations()  # [x1, y1, z1, x2, y2, z2, ...]
    twig_directions = model.get_twig_directions()  # [dx1, dy1, dz1, dx2, dy2, dz2, ...]
    twig_orientations = (
        model.get_twig_orientations()
    )  # [ox1, oy1, oz1, ox2, oy2, oz2, ...]

    # Calculate number of twigs from flat array length
    num_twigs = len(twig_locations) // 3

    # Extract bone IDs for binding - prefer branch-based approach if available
    bone_ids = []
    if hasattr(model, "point_attribute_bone_id"):
        bone_ids = model.point_attribute_bone_id

    # Build branch_id → branch_root_bone_id mapping using is_branch_root flag
    # bones_info format: (is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)

    # Calculate bone_id_offset from first bone (needed for vertex voting fallback)
    bone_id_offset = 0
    if bones_info and len(bones_info) > 0:
        first_bone = bones_info[0]
        is_tree_root, parent_bone_id = first_bone[0], first_bone[1]

        if is_tree_root and parent_bone_id == 0:
            bone_id_offset = 0  # First tree in grove
        elif is_tree_root:
            bone_id_offset = (
                parent_bone_id  # Subsequent tree, offset by previous tree's bone count
            )
        else:
            bone_id_offset = 0

    # Calculate branch_id_offset from first bone (global branch IDs need to be converted to local)
    branch_id_offset = 0
    if bones_info and len(bones_info) > 0 and len(bones_info[0]) >= 8:
        branch_id_offset = int(bones_info[0][7])  # First bone's branch_id is the offset

    branch_root_bones = {}
    if bones_info:
        for bone_idx, bone in enumerate(bones_info):
            if len(bone) >= 8:
                is_branch_root = bone[6]  # Index 6 is is_branch_root flag
                global_branch_id = int(bone[7])  # Index 7 is branch_id (global)
                local_branch_id = (
                    global_branch_id - branch_id_offset
                )  # Convert to local
                if is_branch_root:
                    branch_root_bones[local_branch_id] = bone_idx

    faces = model.faces

    for twig_type in twig_types:
        attr_name = f"face_attribute_{twig_type}"
        if not hasattr(model, attr_name):
            continue

        twig_values = getattr(model, attr_name)

        # Track which twig index we're processing
        twig_idx = 0

        for face_idx, face in enumerate(faces):
            if face_idx >= len(twig_values):
                break

            twig_value = twig_values[face_idx]

            if twig_value > 0:
                # Check if we still have twig data available
                if twig_idx >= num_twigs:
                    break

                # Extract position and normal from flat arrays (3 floats per twig)
                base_idx = twig_idx * 3
                position = (
                    twig_locations[base_idx],
                    twig_locations[base_idx + 1],
                    twig_locations[base_idx + 2],
                )
                normal = (
                    twig_directions[base_idx],
                    twig_directions[base_idx + 1],
                    twig_directions[base_idx + 2],
                )

                # BONE-BASED BINDING: Get bone_id from vertices, then extract branch_id from that bone
                twig_bone_id = None
                branch_id_for_twig = None

                if bone_ids:
                    # Get the bone that this twig face belongs to via vertex voting
                    from collections import Counter

                    face_vert_indices = list(face)
                    face_bone_ids = []
                    for vert_idx in face_vert_indices:
                        if vert_idx < len(bone_ids):
                            face_bone_ids.append(bone_ids[vert_idx])

                    if face_bone_ids:
                        # Get most common bone ID (this is a GLOBAL bone ID)
                        global_bone_id = Counter(face_bone_ids).most_common(1)[0][0]
                        # Convert global bone ID to local bone index
                        local_bone_id = global_bone_id - bone_id_offset
                        twig_bone_id = local_bone_id

                        # Now get the branch_id from this bone
                        # bones_info is indexed by local bone_id
                        if bones_info and local_bone_id < len(bones_info):
                            bone = bones_info[local_bone_id]
                            if len(bone) >= 8:
                                global_branch_id = int(bone[7])  # Index 7 is branch_id
                                branch_id_for_twig = global_branch_id - branch_id_offset

                placement = TwigPlacement(
                    type=twig_type,
                    position=position,
                    normal=normal,
                    scale=1.0,
                    bone_id=twig_bone_id,
                    branch_id=branch_id_for_twig,
                )
                placements[twig_type].append(placement)

                twig_idx += 1

    return placements
