"""Pure twig placement computation without USD dependencies.

This module contains core twig placement logic - extracting twig data from
Grove models and calculating transforms - as pure Python functions without
any USD or Blender I/O dependencies.
"""

import logging
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TwigPlacement:
    """Twig instance placement data."""

    type: str  # 'twig_long', 'twig_short', 'twig_upward', 'twig_dead'
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]  # Facing direction (from get_twig_directions)
    orientation: Tuple[float, float, float] = (0.0, 0.0, 1.0)  # Up vector (from get_twig_orientations)
    scale: float = 1.0
    bone_id: Optional[int] = None  # Direct bone ID from point_attribute_bone_id
    branch_id: Optional[int] = None  # Branch ID for binding to branch_X joints

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type,
            "position": self.position,
            "normal": self.normal,
            "orientation": self.orientation,
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
    verbose: bool = False,
    twig_density: float = 1.0,
) -> Dict[str, List[TwigPlacement]]:
    """Extract twig placement data from Grove model.

    Args:
        model: Grove model with twig location/orientation/direction methods
        twig_types: List of twig types to extract (default: living twig types only)
        bones_info: Optional skeleton bones list for branch-based binding
        verbose: If True, print debug information during extraction
        twig_density: Fraction of twigs to keep (0.0-1.0). Matches Blender's
            Geometry Nodes density parameter. Values below 1.0 probabilistically
            cull twig instances using a deterministic seed for reproducibility.

    Returns:
        Dictionary mapping twig type to list of TwigPlacement objects
    """
    if twig_types is None:
        # Only extract living twig types - dead branches have no foliage
        # twig_dead is intentionally excluded to save memory
        twig_types = ["twig_long", "twig_short", "twig_upward"]

    placements = {twig_type: [] for twig_type in twig_types}

    # Use Grove API methods for twig data - these return flat lists with 3 floats per twig
    twig_locations = model.get_twig_locations()  # [x1, y1, z1, x2, y2, z2, ...]
    twig_directions = model.get_twig_directions()  # [dx1, dy1, dz1, dx2, dy2, dz2, ...]
    twig_orientations = (
        model.get_twig_orientations()
    )  # [ox1, oy1, oz1, ox2, oy2, oz2, ...]

    # Calculate number of twigs from flat array length
    num_twigs = len(twig_locations) // 3

    # Validate all arrays have matching lengths — a mismatch means the Grove API
    # returned inconsistent data, which would cause silent wrong placements.
    num_directions = len(twig_directions) // 3
    if num_directions != num_twigs:
        raise ValueError(
            f"Twig array length mismatch: twig_locations has {num_twigs} twigs "
            f"but twig_directions has {num_directions}. Grove API returned inconsistent data."
        )

    if verbose:
        logger.debug("TWIG EXTRACTION: %d twigs in Grove API arrays", num_twigs)
        logger.debug(
            "  twig_locations=%d  twig_directions=%d  twig_orientations=%d",
            len(twig_locations) // 3,
            len(twig_directions) // 3,
            len(twig_orientations) // 3,
        )

    # Extract bone IDs for binding - prefer branch-based approach if available
    bone_ids = []
    if hasattr(model, "point_attribute_bone_id"):
        bone_ids = model.point_attribute_bone_id

    # FAST PATH: Direct face-to-branch mapping (avoids vertex voting)
    face_branch_ids = None
    if hasattr(model, "face_attribute_branch_id"):
        face_branch_ids = model.face_attribute_branch_id
        if verbose:
            logger.debug("  Using direct face_attribute_branch_id (fast path)")
    elif verbose:
        logger.debug("  Using vertex voting fallback (slow path)")

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
    # Pre-compute global_bone_id -> local_branch_id lookup table for O(1) access
    # This avoids repeated bones_info lookups in the inner loop
    bone_to_branch = {}
    if bones_info:
        num_bones = len(bones_info)
        for bone_idx, bone in enumerate(bones_info):
            if len(bone) >= 8:
                is_branch_root = bone[6]  # Index 6 is is_branch_root flag
                global_branch_id = int(bone[7])  # Index 7 is branch_id (global)
                local_branch_id = (
                    global_branch_id - branch_id_offset
                )  # Convert to local
                # Store branch_id for every bone (not just root bones)
                bone_to_branch[bone_idx] = local_branch_id
                if is_branch_root:
                    branch_root_bones[local_branch_id] = bone_idx

    faces = model.faces

    # Get twig type attributes for all faces
    twig_type_attrs = {}
    for twig_type in twig_types:
        attr_name = f"face_attribute_{twig_type}"
        if hasattr(model, attr_name):
            twig_type_attrs[twig_type] = getattr(model, attr_name)
            if verbose:
                twig_count = sum(1 for val in getattr(model, attr_name) if val > 0)
                logger.debug("  %s: %d faces marked", twig_type, twig_count)

    # Track which twig index we're processing across ALL types
    twig_idx = 0

    # Iterate through all faces once
    for face_idx, face in enumerate(faces):
        # Check which twig type (if any) this face has
        current_twig_type = None
        for twig_type, twig_values in twig_type_attrs.items():
            if face_idx < len(twig_values) and twig_values[face_idx] > 0:
                current_twig_type = twig_type
                break  # Face can only have one twig type

        # If this face has a twig, process it
        if current_twig_type:
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

            # BONE ASSIGNMENT STRATEGY:
            # PRIMARY: Vertex voting - most reliable, uses actual vertex bone assignments
            # FALLBACK: Branch lookup - only if no vertex bone data available
            twig_bone_id = None
            branch_id_for_twig = None

            # PRIMARY METHOD: Vertex voting (most reliable)
            if bone_ids:
                face_vert_indices = face
                bone_counts = {}
                for vert_idx in face_vert_indices:
                    if vert_idx < len(bone_ids):
                        bid = bone_ids[vert_idx]
                        bone_counts[bid] = bone_counts.get(bid, 0) + 1

                if bone_counts:
                    # Get the most common bone ID among this face's vertices
                    global_bone_id = max(bone_counts, key=bone_counts.get)
                    # Store GLOBAL bone ID for assembly export to remap after filtering
                    twig_bone_id = global_bone_id

            # FALLBACK: If vertex voting failed, try branch lookup
            if twig_bone_id is None and face_branch_ids is not None and face_idx < len(face_branch_ids):
                global_branch_id = face_branch_ids[face_idx]
                branch_id_for_twig = global_branch_id - branch_id_offset

                # Try to convert branch_id to bone_id using branch_root_bones
                if branch_id_for_twig in branch_root_bones:
                    local_bone_idx = branch_root_bones[branch_id_for_twig]
                    # Convert local bone index to GLOBAL bone ID
                    twig_bone_id = local_bone_idx + bone_id_offset

            # Extract branch_id_for_twig if we have a bone_id but no branch_id yet
            if twig_bone_id is not None and branch_id_for_twig is None:
                local_bone_id = twig_bone_id - bone_id_offset
                branch_id_for_twig = bone_to_branch.get(local_bone_id)

            # Extract orientation (up vector) from twig_orientations
            orientation = (0.0, 0.0, 1.0)  # Default Z-up in Grove space
            if twig_orientations and base_idx + 2 < len(twig_orientations):
                orientation = (
                    twig_orientations[base_idx],
                    twig_orientations[base_idx + 1],
                    twig_orientations[base_idx + 2],
                )

            placement = TwigPlacement(
                type=current_twig_type,
                position=position,
                normal=normal,
                orientation=orientation,
                scale=1.0,
                bone_id=twig_bone_id,
                branch_id=branch_id_for_twig,
            )
            placements[current_twig_type].append(placement)

            # Increment twig index for ALL types (they share the same sequential array)
            twig_idx += 1

    # Apply twig density filtering (matches Blender Geometry Nodes density parameter)
    twig_density = max(0.0, min(1.0, twig_density))
    if twig_density < 1.0:
        rng = random.Random(42)  # Deterministic seed for reproducibility
        total_before = sum(len(p) for p in placements.values())
        for twig_type in list(placements.keys()):
            placements[twig_type] = [
                p for p in placements[twig_type] if rng.random() < twig_density
            ]
        total_after = sum(len(p) for p in placements.values())
        logger.info(
            "Twig density filter: %.1f%% kept %d of %d twigs",
            twig_density * 100, total_after, total_before,
        )

    # Report results
    total_extracted = sum(len(p) for p in placements.values())
    for twig_type in twig_types:
        logger.debug("  %s: %d placements", twig_type, len(placements[twig_type]))
    logger.info(
        "Twig extraction: %d total (%d/%d array slots used)",
        total_extracted, twig_idx, num_twigs,
    )

    all_bone_ids = [
        p.bone_id
        for plist in placements.values()
        for p in plist
        if p.bone_id is not None
    ]
    if all_bone_ids:
        logger.debug(
            "Bone IDs: %d twigs assigned, range %d-%d",
            len(all_bone_ids), min(all_bone_ids), max(all_bone_ids),
        )
    else:
        logger.warning("No twigs have bone_id set")

    return placements
