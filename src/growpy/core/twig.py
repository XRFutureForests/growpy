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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type,
            "position": self.position,
            "normal": self.normal,
            "scale": self.scale,
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
    x_axis = normal

    # Find perpendicular vector for Y-axis
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

    # Normalize
    length = math.sqrt(w * w + x * x + y * y + z * z)
    if length > 0:
        return (w / length, x / length, y / length, z / length)
    else:
        return (1.0, 0.0, 0.0, 0.0)


def extract_twig_placements_from_model(
    model: Any, twig_types: Optional[List[str]] = None
) -> Dict[str, List[TwigPlacement]]:
    """Extract twig placement data from Grove model.

    Args:
        model: Grove model with face attributes
        twig_types: List of twig types to extract (default: all known types)

    Returns:
        Dictionary mapping twig type to list of TwigPlacement objects
    """
    if twig_types is None:
        twig_types = ["twig_long", "twig_short", "twig_upward", "twig_dead"]

    placements = {twig_type: [] for twig_type in twig_types}

    # Get geometry data
    vertices = [(v.x, v.y, v.z) for v in model.point_coordinates()]
    faces = model.face_indices()

    # Get face attributes for each twig type
    for twig_type in twig_types:
        attr_name = f"face_attribute_{twig_type}"
        if not hasattr(model, attr_name):
            continue

        twig_values = getattr(model, attr_name)

        # Group faces into triangles (assumes triangulated mesh)
        num_faces = len(faces) // 3
        for face_idx in range(num_faces):
            twig_value = twig_values[face_idx] if face_idx < len(twig_values) else 0

            if twig_value > 0:  # Face has twig placement
                # Get triangle vertex indices
                face_verts = [
                    faces[face_idx * 3],
                    faces[face_idx * 3 + 1],
                    faces[face_idx * 3 + 2],
                ]

                # Calculate center and normal
                center, normal = get_face_center_and_normal(vertices, face_verts)

                placement = TwigPlacement(
                    type=twig_type, position=center, normal=normal, scale=1.0
                )
                placements[twig_type].append(placement)

    return placements


def calculate_twig_transform(
    position: Tuple[float, float, float],
    normal: Tuple[float, float, float],
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Calculate full transform (position, rotation, scale) for twig placement.

    Args:
        position: World position (x, y, z)
        normal: Normal vector for orientation (x, y, z)
        scale: Uniform scale factor

    Returns:
        Dictionary with 'position', 'rotation_matrix', 'quaternion', 'scale'
    """
    rotation_matrix = normal_to_rotation_matrix(normal)
    quaternion = rotation_matrix_to_quaternion(rotation_matrix)

    return {
        "position": position,
        "rotation_matrix": rotation_matrix,
        "quaternion": quaternion,
        "scale": (scale, scale, scale),
    }


def convert_y_up_to_z_up(
    pos: Tuple[float, float, float], scale: float = 1.0
) -> Tuple[float, float, float]:
    """Convert Y-up (Grove/OpenGL) coordinates to Z-up (Blender/USD standard).

    Args:
        pos: Position in Y-up coordinates (x, y, z)
        scale: Scale factor to apply

    Returns:
        Position in Z-up coordinates (x, y, z)
    """
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
    return (normal[0], -normal[2], normal[1])


def group_twigs_by_type(
    placements: Dict[str, List[TwigPlacement]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group twig placements by type with full transforms.

    Args:
        placements: Dictionary of twig type to TwigPlacement list

    Returns:
        Dictionary of twig type to list of transform dictionaries
    """
    grouped = {}

    for twig_type, placement_list in placements.items():
        transforms = []
        for placement in placement_list:
            transform = calculate_twig_transform(
                placement.position, placement.normal, placement.scale
            )
            transforms.append(transform)
        grouped[twig_type] = transforms

    return grouped
