"""Pure twig placement computation without USD dependencies.

This module contains core twig placement logic - extracting twig data from
Grove models and calculating transforms - as pure Python functions without
any USD or Blender I/O dependencies.
"""

import logging
import math
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Grove's twig frame quaternion, (w, x, y, z). Rotating +X by it reproduces
# get_twig_directions() exactly, so it carries the growth direction AND the
# phyllotactic roll Grove derives from the species preset.
IDENTITY_QUAT = (1.0, 0.0, 0.0, 0.0)


@dataclass
class TwigPlacement:
    """Twig instance placement data."""

    type: str  # 'twig_long', 'twig_short', 'twig_upward', 'twig_dead'
    position: tuple[float, float, float]
    normal: tuple[float, float, float]  # Facing direction (from get_twig_directions)
    orientation: tuple[float, float, float, float] = IDENTITY_QUAT
    # Grove's twig frame quaternion (w, x, y, z) from get_twig_orientations()
    scale: float = 1.0
    bone_id: int | None = None  # Direct bone ID from point_attribute_bone_id
    branch_id: int | None = None  # Branch ID for binding to branch_X joints

    def to_dict(self) -> dict[str, Any]:
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
    vertices: list[tuple[float, float, float]], face: list[int]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
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


def normal_to_rotation_matrix(normal: tuple[float, float, float]) -> list[list[float]]:
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
    matrix: list[list[float]],
) -> tuple[float, float, float, float]:
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


# Angle between a twig's growth direction and its parent branch axis. 0 deg lays
# the twig flat along the bark, so its leaves fan straight into the branch mesh;
# 90 deg stands it edge-on. Real twigs leave the branch somewhere in between.
DEFAULT_TWIG_BRANCH_ANGLE_RAD = math.radians(50.0)

# Distance (m) beyond which a twig orphaned by build_cutoff_thickness is pulled
# back onto the surviving surface instead of left where Grove placed it. Most
# orphans sit ~1 mm out; long-shoot species such as Scots pine strand a third
# of theirs 10-100 mm out, which reads as floating foliage.
DEFAULT_TWIG_REATTACH_THRESHOLD = 0.01


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Return the unit vector, or None when the input is degenerate."""
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-12:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)


def _face_area(vertices: list, face: list[int]) -> float:
    """Area of a polygon face via fan triangulation."""
    if len(face) < 3:
        return 0.0
    v0 = vertices[face[0]]
    total = 0.0
    for k in range(1, len(face) - 1):
        a = vertices[face[k]]
        b = vertices[face[k + 1]]
        ux, uy, uz = a[0] - v0[0], a[1] - v0[1], a[2] - v0[2]
        wx, wy, wz = b[0] - v0[0], b[1] - v0[1], b[2] - v0[2]
        cx = uy * wz - uz * wy
        cy = uz * wx - ux * wz
        cz = ux * wy - uy * wx
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def direction_to_quaternion(
    direction: tuple[float, float, float],
    reference: tuple[float, float, float] | None = None,
) -> tuple[float, float, float, float]:
    """Quaternion (w, x, y, z) rotating +X onto ``direction``.

    Grove twig assets grow along +X from their pivot, so the growth direction is
    the frame's X axis. ``reference`` (normally the parent branch axis) resolves
    the roll about that axis, keeping the leaf plane oriented relative to the
    branch instead of to an arbitrary world axis.
    """
    x_axis = _normalize(direction)
    if x_axis is None:
        return IDENTITY_QUAT
    ref = _normalize(reference) if reference is not None else None
    if ref is None:
        ref = (0.0, 0.0, 1.0)
    d = ref[0] * x_axis[0] + ref[1] * x_axis[1] + ref[2] * x_axis[2]
    z_axis = _normalize(
        (ref[0] - d * x_axis[0], ref[1] - d * x_axis[1], ref[2] - d * x_axis[2])
    )
    if z_axis is None:
        alt = (1.0, 0.0, 0.0) if abs(x_axis[0]) < 0.9 else (0.0, 1.0, 0.0)
        d = alt[0] * x_axis[0] + alt[1] * x_axis[1] + alt[2] * x_axis[2]
        z_axis = _normalize(
            (alt[0] - d * x_axis[0], alt[1] - d * x_axis[1], alt[2] - d * x_axis[2])
        ) or (0.0, 0.0, 1.0)
    y_axis = (
        z_axis[1] * x_axis[2] - z_axis[2] * x_axis[1],
        z_axis[2] * x_axis[0] - z_axis[0] * x_axis[2],
        z_axis[0] * x_axis[1] - z_axis[1] * x_axis[0],
    )
    return rotation_matrix_to_quaternion(
        [
            [x_axis[0], y_axis[0], z_axis[0]],
            [x_axis[1], y_axis[1], z_axis[1]],
            [x_axis[2], y_axis[2], z_axis[2]],
        ]
    )


def extract_twig_placements_from_model(
    model: Any,
    twig_types: list[str] | None = None,
    bones_info: list | None = None,
    verbose: bool = False,
    scaled_points: list[tuple[float, float, float]] | None = None,
) -> dict[str, list[TwigPlacement]]:
    """Extract twig placement data from Grove model.

    Args:
        model: Grove model with twig location/orientation/direction methods
        twig_types: List of twig types to extract (default: living twig types only)
        bones_info: Optional skeleton bones list for branch-based binding
        verbose: If True, print debug information during extraction
        scaled_points: Optional list of (x, y, z) vertex positions from the
            radially-scaled mesh (from build_tree_mesh). When provided, twig
            positions are computed as face centroids of the scaled mesh instead
            of using Grove's get_twig_locations(). This keeps twigs attached to
            the scaled branches without a separate transform pass.

    Returns:
        Dictionary mapping twig type to list of TwigPlacement objects
    """
    if twig_types is None:
        twig_types = ["twig_long", "twig_short", "twig_upward", "twig_dead"]

    placements = {twig_type: [] for twig_type in twig_types}

    # Grove twig arrays. Locations and directions hold 3 floats per twig;
    # orientations hold a unit QUATERNION -- 4 floats per twig, (w, x, y, z).
    twig_locations = model.get_twig_locations()  # [x1, y1, z1, x2, y2, z2, ...]
    twig_directions = model.get_twig_directions()  # [dx1, dy1, dz1, dx2, dy2, dz2, ...]
    twig_orientations = model.get_twig_orientations()  # [w1, x1, y1, z1, w2, ...]

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

    # Orientations are quaternions (stride 4). Reading them at stride 3 yields
    # non-unit garbage, so verify the stride rather than trusting it.
    num_orientations = len(twig_orientations) // 4
    if twig_orientations and num_orientations != num_twigs:
        raise ValueError(
            f"Twig array length mismatch: twig_locations has {num_twigs} twigs "
            f"but twig_orientations has {num_orientations} quaternions "
            f"({len(twig_orientations)} floats). Grove API returned inconsistent data."
        )

    if verbose:
        logger.debug("TWIG EXTRACTION: %d twigs in Grove API arrays", num_twigs)
        logger.debug(
            "  twig_locations=%d  twig_directions=%d  twig_orientations=%d",
            len(twig_locations) // 3,
            len(twig_directions) // 3,
            len(twig_orientations) // 4,
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
            is_dead = current_twig_type == "twig_dead"

            # Dead twigs have face attributes but NO entries in Grove's
            # twig location/direction/orientation arrays (those only hold
            # living twigs).  Use face centroid + default vectors instead.
            if is_dead:
                cx, cy, cz = 0.0, 0.0, 0.0
                n = len(face)
                if scaled_points is not None:
                    for vi in face:
                        sp = scaled_points[vi]
                        cx += sp[0]
                        cy += sp[1]
                        cz += sp[2]
                else:
                    pts = model.points
                    for vi in face:
                        p = pts[vi]
                        if hasattr(p, "x"):
                            cx += p.x
                            cy += p.y
                            cz += p.z
                        else:
                            cx += p[0]
                            cy += p[1]
                            cz += p[2]
                inv_n = 1.0 / n
                position = (cx * inv_n, cy * inv_n, cz * inv_n)
                normal = (0.0, 0.0, 1.0)
                orientation = IDENTITY_QUAT
            else:
                # Living twig — index into Grove arrays
                if twig_idx >= num_twigs:
                    break

                base_idx = twig_idx * 3
                if scaled_points is not None:
                    cx, cy, cz = 0.0, 0.0, 0.0
                    n = len(face)
                    for vi in face:
                        sp = scaled_points[vi]
                        cx += sp[0]
                        cy += sp[1]
                        cz += sp[2]
                    inv_n = 1.0 / n
                    position = (cx * inv_n, cy * inv_n, cz * inv_n)
                else:
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
                orientation = IDENTITY_QUAT
                quat_idx = twig_idx * 4
                if twig_orientations and quat_idx + 3 < len(twig_orientations):
                    orientation = (
                        twig_orientations[quat_idx],
                        twig_orientations[quat_idx + 1],
                        twig_orientations[quat_idx + 2],
                        twig_orientations[quat_idx + 3],
                    )

            # BONE & BRANCH ASSIGNMENT:
            # - bone_id: from vertex voting (needed for skeletal binding)
            # - branch_id: from face_attribute_branch_id (direct, covers all
            #   branches), with bone_to_branch as fallback
            twig_bone_id = None
            branch_id_for_twig = None

            # Bone ID via vertex voting (for skeletal mesh binding)
            if bone_ids:
                face_vert_indices = face
                bone_counts = {}
                for vert_idx in face_vert_indices:
                    if vert_idx < len(bone_ids):
                        bid = bone_ids[vert_idx]
                        bone_counts[bid] = bone_counts.get(bid, 0) + 1

                if bone_counts:
                    global_bone_id = max(bone_counts, key=bone_counts.get)
                    twig_bone_id = global_bone_id

            # Branch ID: prefer face_attribute_branch_id (covers all branches)
            if face_branch_ids is not None and face_idx < len(face_branch_ids):
                global_branch_id = face_branch_ids[face_idx]
                branch_id_for_twig = global_branch_id - branch_id_offset

                # Also resolve bone_id from branch if vertex voting failed
                if twig_bone_id is None and branch_id_for_twig in branch_root_bones:
                    local_bone_idx = branch_root_bones[branch_id_for_twig]
                    twig_bone_id = local_bone_idx + bone_id_offset

            # Fallback: derive branch_id from bone_id if face attr unavailable
            if twig_bone_id is not None and branch_id_for_twig is None:
                local_bone_id = twig_bone_id - bone_id_offset
                branch_id_for_twig = bone_to_branch.get(local_bone_id)

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

            # Only increment twig_idx for living twigs — dead twigs have
            # no entries in Grove's twig arrays.
            if not is_dead:
                twig_idx += 1

    # Report results
    total_extracted = sum(len(p) for p in placements.values())
    for twig_type in twig_types:
        logger.debug("  %s: %d placements", twig_type, len(placements[twig_type]))
    logger.info(
        "Twig extraction: %d total (%d/%d array slots used)",
        total_extracted,
        twig_idx,
        num_twigs,
    )

    # Density-match dead twigs to Grove's living-twig scatter density.
    # Grove exposes ground-truth arrays (get_twig_locations) only for LIVING
    # twigs, so their counts already reflect how densely Grove scatters twigs.
    # Dead twigs have no such array — every face_attribute_twig_dead face was
    # turned into a placement above (1:1), which populates far more dead tips
    # than Grove actually renders. Derive Grove's effective scatter fraction
    # from the living twigs (placed / candidate faces) and keep only that
    # fraction of dead placements, so dead twigs appear only where Grove would.
    dead_list = placements.get("twig_dead")
    if dead_list:
        living_candidate_faces = 0
        for _lt in ("twig_long", "twig_short", "twig_upward"):
            _attr = twig_type_attrs.get(_lt)
            if _attr:
                living_candidate_faces += sum(1 for _v in _attr if _v > 0)
        living_placed = sum(
            len(placements.get(_lt, []))
            for _lt in ("twig_long", "twig_short", "twig_upward")
        )
        if living_candidate_faces > 0:
            scatter_ratio = min(1.0, living_placed / living_candidate_faces)
            keep = int(len(dead_list) * scatter_ratio + 0.5)
            if keep < len(dead_list):
                random.Random(42).shuffle(dead_list)
                removed = len(dead_list) - keep
                placements["twig_dead"] = dead_list[:keep]
                logger.info(
                    "Dead-twig density match: kept %d/%d (Grove living scatter %.2f)",
                    keep,
                    keep + removed,
                    scatter_ratio,
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
            len(all_bone_ids),
            min(all_bone_ids),
            max(all_bone_ids),
        )
    else:
        logger.warning("No twigs have bone_id set")

    return placements


def _quat_multiply(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Hamilton product of two (w, x, y, z) quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def shortest_arc_quaternion(
    from_vec: tuple[float, float, float], to_vec: tuple[float, float, float]
) -> tuple[float, float, float, float]:
    """Quaternion rotating ``from_vec`` onto ``to_vec`` by the shortest arc.

    Used to re-aim a recovered twig without discarding the roll Grove gave it:
    applying this to the twig's own quaternion turns the growth direction while
    carrying the leaf plane along with it.
    """
    a = _normalize(from_vec)
    b = _normalize(to_vec)
    if a is None or b is None:
        return IDENTITY_QUAT
    d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    if d >= 1.0 - 1e-9:
        return IDENTITY_QUAT
    if d <= -1.0 + 1e-9:
        # Antiparallel: any perpendicular axis gives a valid 180 deg rotation.
        axis = _normalize((a[1], -a[0], 0.0)) or _normalize((0.0, a[2], -a[1]))
        if axis is None:
            return IDENTITY_QUAT
        return (0.0, axis[0], axis[1], axis[2])
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    s = math.sqrt((1.0 + d) * 2.0)
    inv_s = 1.0 / s
    q = (s * 0.5, cross[0] * inv_s, cross[1] * inv_s, cross[2] * inv_s)
    length = math.sqrt(sum(c * c for c in q))
    if length < 1e-12:
        return IDENTITY_QUAT
    return (q[0] / length, q[1] / length, q[2] / length, q[3] / length)


def _closest_points_on_triangles(p, a, b, c):
    """Vectorised closest point on a triangle (Ericson). All arrays (N, 3)."""
    import numpy as np

    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = 1.0 / np.maximum(va + vb + vc, 1e-30)
    out = a + ab * (vb * denom)[:, None] + ac * (vc * denom)[:, None]
    edge_bc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    t = ((d4 - d3) / np.maximum((d4 - d3) + (d5 - d6), 1e-30))[:, None]
    out = np.where(edge_bc[:, None], b + t * (c - b), out)
    edge_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    t = (d2 / np.maximum(d2 - d6, 1e-30))[:, None]
    out = np.where(edge_ac[:, None], a + t * ac, out)
    edge_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    t = (d1 / np.maximum(d1 - d3, 1e-30))[:, None]
    out = np.where(edge_ab[:, None], a + t * ab, out)
    out = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, out)
    out = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, out)
    out = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, out)
    return out


def _barycentric(p, a, b, c):
    """Barycentric weights of p within triangle (a, b, c). All arrays (N, 3)."""
    import numpy as np

    v0, v1, v2 = b - a, c - a, p - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    denom = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    return 1.0 - v - w, v, w


def _triangulate_faces(faces):
    """Fan-triangulate polygon faces, keeping a map back to the source face."""
    tris = []
    owner = []
    for face_idx, face in enumerate(faces):
        for k in range(1, len(face) - 1):
            tris.append((face[0], face[k], face[k + 1]))
            owner.append(face_idx)
    return tris, owner


def recover_cutoff_twig_placements(
    precut_placements: dict[str, list[TwigPlacement]],
    cut_twig_positions: list[tuple[float, float, float]],
    cut_model: Any,
    bones_info: list | None = None,
    scaled_points: list[tuple[float, float, float]] | None = None,
    reattach_threshold: float = DEFAULT_TWIG_REATTACH_THRESHOLD,
    match_tolerance: float = 1e-6,
    candidate_faces: int = 16,
) -> dict[str, list[TwigPlacement]]:
    """Return the twigs that ``build_cutoff_thickness`` deleted, reattached.

    ``build_cutoff_thickness`` drops branches thinner than the threshold, and
    Grove does not redistribute the twigs that were sitting on them -- so the
    crown silently loses foliage (measured: 52% of a 20-cycle oak's twigs, 82%
    of a beech's). Rather than synthesising replacements, this recovers the
    exact twigs Grove computed, with their own positions, directions and
    phyllotactic quaternions.

    The post-cutoff twig set is a strict positional subset of the pre-cutoff
    set, so the lost twigs are an exact diff rather than a heuristic match.

    Most orphans sit within ~1 mm of the surviving surface, because the branch
    that was removed was thinner than the cutoff. Species with long, sparse
    side shoots are the exception -- on Scots pine 30% of orphans end up more
    than 10 mm out (max ~100 mm), left hanging where the deleted shoot used to
    reach. Those are pulled back onto the surviving surface and re-aimed along
    the direction the removed shoot ran, so the twig asset stands in for the
    shoot instead of floating past its tip.

    Args:
        precut_placements: Placements extracted from a cutoff=0 build. Their
            positions must be Grove's raw twig locations (no scaled_points),
            so they can be matched against cut_twig_positions.
        cut_twig_positions: Raw Grove twig locations surviving the cutoff.
        cut_model: The production (post-cutoff) model, supplying the surviving
            surface and the bone/branch attributes to bind against.
        bones_info: Optional bone list for branch_id fallback.
        scaled_points: Optional radially-scaled vertex positions for cut_model.
            When given, recovered twigs are displaced by the same amount the
            local surface moved, so they stay attached after DBH scaling.
        reattach_threshold: Distance (m) beyond which an orphan is pulled back
            onto the surface and re-aimed instead of kept in place.
        match_tolerance: Distance (m) below which a pre-cutoff twig counts as
            having survived.
        candidate_faces: Nearest faces examined per orphan when finding the
            closest surface point.

    Returns:
        Dict of twig type to the recovered TwigPlacement objects. Empty when
        nothing was lost.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    lost: list[TwigPlacement] = []
    survived_count = 0
    if cut_twig_positions:
        cut_tree = cKDTree(np.asarray(cut_twig_positions, dtype=np.float64))
        for plist in precut_placements.values():
            if not plist:
                continue
            pts = np.asarray([p.position for p in plist], dtype=np.float64)
            dist, _ = cut_tree.query(pts, k=1)
            for placement, d in zip(plist, dist):
                if d <= match_tolerance:
                    survived_count += 1
                else:
                    lost.append(placement)
    else:
        for plist in precut_placements.values():
            lost.extend(plist)

    recovered: dict[str, list[TwigPlacement]] = {}
    if not lost:
        logger.info(
            "Twig recovery: nothing lost to cutoff (%d twigs survived)", survived_count
        )
        return recovered

    verts = np.asarray(
        [
            (p.x, p.y, p.z) if hasattr(p, "x") else (p[0], p[1], p[2])
            for p in cut_model.points
        ],
        dtype=np.float64,
    )
    if len(verts) == 0:
        logger.warning("Twig recovery: cut model has no vertices, skipping")
        return recovered

    tris, tri_owner = _triangulate_faces(cut_model.faces)
    if not tris:
        logger.warning("Twig recovery: cut model has no faces, skipping")
        return recovered
    tri_idx = np.asarray(tris, dtype=np.int64)
    tri_owner_arr = np.asarray(tri_owner, dtype=np.int64)
    centroids = verts[tri_idx].mean(axis=1)

    scaled_verts = (
        np.asarray(scaled_points, dtype=np.float64)
        if scaled_points is not None
        else None
    )
    if scaled_verts is not None and len(scaled_verts) != len(verts):
        logger.warning(
            "Twig recovery: scaled_points has %d entries but the model has %d "
            "vertices; ignoring the scaled positions",
            len(scaled_verts),
            len(verts),
        )
        scaled_verts = None

    lost_pos = np.asarray([p.position for p in lost], dtype=np.float64)
    k = min(candidate_faces, len(centroids))
    _, cand = cKDTree(centroids).query(lost_pos, k=k)
    cand = cand.reshape(len(lost_pos), k)

    rows = np.repeat(np.arange(len(lost_pos)), k)
    flat = cand.ravel()
    ftri = tri_idx[flat]
    closest = _closest_points_on_triangles(
        lost_pos[rows], verts[ftri[:, 0]], verts[ftri[:, 1]], verts[ftri[:, 2]]
    )
    dists = np.linalg.norm(lost_pos[rows] - closest, axis=1).reshape(-1, k)
    best = np.argmin(dists, axis=1)
    best_flat = np.arange(len(lost_pos)) * k + best
    best_tri = flat[best_flat]
    best_dist = dists[np.arange(len(lost_pos)), best]
    best_point = closest[best_flat]

    bt = tri_idx[best_tri]
    u, v, w = _barycentric(
        best_point, verts[bt[:, 0]], verts[bt[:, 1]], verts[bt[:, 2]]
    )
    if scaled_verts is not None:
        surface_scaled = (
            scaled_verts[bt[:, 0]] * u[:, None]
            + scaled_verts[bt[:, 1]] * v[:, None]
            + scaled_verts[bt[:, 2]] * w[:, None]
        )
    else:
        surface_scaled = best_point
    surface_shift = surface_scaled - best_point

    bone_ids = getattr(cut_model, "point_attribute_bone_id", None)
    face_branch_ids = getattr(cut_model, "face_attribute_branch_id", None)
    branch_id_offset = 0
    if bones_info and len(bones_info) > 0 and len(bones_info[0]) >= 8:
        branch_id_offset = int(bones_info[0][7])

    reattached = 0
    for i, placement in enumerate(lost):
        face_idx = int(tri_owner_arr[best_tri[i]])
        face = cut_model.faces[face_idx]

        twig_bone_id = None
        if bone_ids:
            counts: dict[int, int] = {}
            for vi in face:
                if vi < len(bone_ids):
                    bid = bone_ids[vi]
                    counts[bid] = counts.get(bid, 0) + 1
            if counts:
                twig_bone_id = max(counts, key=counts.get)

        branch_id = None
        if face_branch_ids is not None and face_idx < len(face_branch_ids):
            branch_id = face_branch_ids[face_idx] - branch_id_offset

        if best_dist[i] <= reattach_threshold:
            # Close enough to the surviving bark to stay where Grove put it;
            # only follow whatever displacement radial scaling applied locally.
            position = (
                placement.position[0] + surface_shift[i][0],
                placement.position[1] + surface_shift[i][1],
                placement.position[2] + surface_shift[i][2],
            )
            normal = placement.normal
            orientation = placement.orientation
        else:
            # Orphaned far out where a long shoot was deleted. Pull it back to
            # the bark and re-aim it along the shoot, preserving Grove's roll.
            position = (
                float(surface_scaled[i][0]),
                float(surface_scaled[i][1]),
                float(surface_scaled[i][2]),
            )
            outward = _normalize(
                (
                    float(placement.position[0] - best_point[i][0]),
                    float(placement.position[1] - best_point[i][1]),
                    float(placement.position[2] - best_point[i][2]),
                )
            )
            if outward is None:
                normal = placement.normal
                orientation = placement.orientation
            else:
                normal = outward
                orientation = _quat_multiply(
                    shortest_arc_quaternion(placement.normal, outward),
                    placement.orientation,
                )
            reattached += 1

        recovered.setdefault(placement.type, []).append(
            TwigPlacement(
                type=placement.type,
                position=position,
                normal=normal,
                orientation=orientation,
                scale=placement.scale,
                bone_id=twig_bone_id,
                branch_id=branch_id,
            )
        )

    logger.info(
        "Twig recovery: restored %d twigs lost to cutoff (%d survived, "
        "%d re-aimed onto the surface beyond %.0f mm): %s",
        len(lost),
        survived_count,
        reattached,
        reattach_threshold * 1000.0,
        {t: len(p) for t, p in recovered.items()},
    )
    return recovered


def densify_twig_placements(
    model: Any,
    placements: dict[str, list[TwigPlacement]],
    density: float = 1.0,
    bones_info: list | None = None,
    seed: int = 42,
    youth_bias: float = 1.0,
    branch_angle: float = DEFAULT_TWIG_BRANCH_ANGLE_RAD,
    scaled_points: list[tuple[float, float, float]] | None = None,
) -> dict[str, list[TwigPlacement]]:
    """Adjust twig placement count to match a target density multiplier.

    density > 1.0: adds synthetic twigs on non-twig faces, weighted by branch
    youth (younger branches get more twigs).
    density < 1.0: randomly removes existing placements to thin the canopy.
    density == 1.0: no change.

    Args:
        model: Grove model with faces, points, and per-vertex attributes.
        placements: Existing Grove placements from extract_twig_placements_from_model.
        density: Target multiplier relative to the surviving post-cutoff twig count.
            1.0 = keep Grove's surviving placement count unchanged.
            Set to (pre_cutoff / post_cutoff) to restore natural density when a
            build_cutoff_thickness is active (e.g. 4.6 for cutoff=0.005).
        bones_info: Optional bone list for bone/branch assignment.
        seed: Random seed for reproducibility.
        branch_angle: Angle in radians between a synthetic twig's growth
            direction and its parent branch axis.
        scaled_points: Optional list of (x, y, z) tuples from the radially-scaled
            mesh. When provided, face centroids for synthetic placements are
            computed from these instead of model.points.

    Returns:
        The same placements dict, modified in-place.
    """
    if density == 1.0:
        return placements

    total_existing = sum(len(p) for p in placements.values())
    if total_existing == 0:
        return placements

    # Thin existing placements when density < 1.0
    if density < 1.0:
        keep_ratio = max(0.0, density)
        rng = random.Random(seed)
        removed = 0
        for twig_type, plist in placements.items():
            if not plist:
                continue
            keep_count = max(0, int(len(plist) * keep_ratio + 0.5))
            if keep_count >= len(plist):
                continue
            rng.shuffle(plist)
            removed += len(plist) - keep_count
            placements[twig_type] = plist[:keep_count]
        logger.info(
            "Twig thinning: removed %d placements (density=%.2f, remaining=%d)",
            removed,
            density,
            total_existing - removed,
        )
        return placements

    target_total = int(total_existing * density)

    num_to_add = target_total - total_existing
    if num_to_add <= 0:
        return placements

    rng = random.Random(seed)

    faces = model.faces
    points = model.points
    num_faces = len(faces)

    # Build set of faces that already carry a Grove twig
    existing_twig_faces = set()
    twig_type_attrs = {}
    for twig_type in ["twig_long", "twig_short", "twig_upward", "twig_dead"]:
        attr = getattr(model, f"face_attribute_{twig_type}", None)
        if attr:
            twig_type_attrs[twig_type] = attr
            for fi in range(min(len(attr), num_faces)):
                if attr[fi] > 0:
                    existing_twig_faces.add(fi)

    # Per-vertex age (lower = younger)
    vertex_ages = getattr(model, "point_attribute_age", None)

    # Compute per-face youth weight: mean(max_age - vertex_age) for the face
    max_age = max(vertex_ages) if vertex_ages else 1.0
    if max_age < 1e-6:
        max_age = 1.0

    # Vertex coords as tuples, for face centre/area/normal maths below.
    if scaled_points is not None:
        verts = scaled_points
    else:
        verts = [
            (p.x, p.y, p.z) if hasattr(p, "x") else (p[0], p[1], p[2]) for p in points
        ]

    candidate_faces = []
    candidate_weights = []
    for fi in range(num_faces):
        if fi in existing_twig_faces:
            continue
        face = faces[fi]
        if vertex_ages:
            ages = [vertex_ages[vi] for vi in face if vi < len(vertex_ages)]
            if ages:
                mean_age = sum(ages) / len(ages)
                youth = (max_age - mean_age) / max_age  # 0..1, 1 = youngest
            else:
                youth = 0.0
        else:
            youth = 0.5
        # Skip very old faces (trunk base, etc.)
        if youth < 0.01:
            continue
        # Weight by face AREA as well as youth. Sampling faces uniformly makes
        # twig density track TESSELLATION density rather than bark area:
        # junction blend geometry and thin branches carry many tiny faces and
        # would otherwise collect a hugely disproportionate share of twigs.
        area = _face_area(verts, face)
        if area <= 0.0:
            continue
        youth_weight = youth**youth_bias if youth_bias != 1.0 else youth
        candidate_faces.append(fi)
        candidate_weights.append(area * youth_weight)

    if not candidate_faces:
        logger.debug("densify: no candidate faces available")
        return placements

    # Guard against degenerate weight vectors
    total_weight = sum(candidate_weights)
    if total_weight < 1e-12:
        return placements

    # Twig type distribution from existing placements
    living_types = ["twig_long", "twig_short", "twig_upward"]
    type_counts = {t: len(placements.get(t, [])) for t in living_types}
    total_living = sum(type_counts.values())
    if total_living == 0:
        type_dist = {t: 1.0 / len(living_types) for t in living_types}
    else:
        type_dist = {t: type_counts[t] / total_living for t in living_types}

    # Bone assignment helpers
    bone_ids = getattr(model, "point_attribute_bone_id", None)
    bone_id_offset = 0
    bone_to_branch = {}
    if bones_info:
        if bone_ids:
            bone_id_offset = min(bone_ids)
        branch_id_offset = int(bones_info[0][7]) if len(bones_info[0]) >= 8 else 0
        for bone_idx, bone in enumerate(bones_info):
            if len(bone) >= 8:
                bone_to_branch[bone_idx] = int(bone[7]) - branch_id_offset

    # Weighted sampling WITHOUT replacement so each candidate face hosts at most
    # one synthetic twig. Uses the Efraimidis-Spirakis key trick: assign each
    # face a key of U^(1/w) and take the top-k by key — equivalent to weighted
    # sampling without replacement in O(n log n).
    n_sample = min(num_to_add, len(candidate_faces))
    if n_sample < num_to_add:
        logger.debug(
            "densify: only %d candidate faces available for %d requested twigs; "
            "capped to one twig per face",
            n_sample,
            num_to_add,
        )
    keys = [rng.random() ** (1.0 / w) if w > 1e-12 else 0.0 for w in candidate_weights]
    order = sorted(range(len(candidate_faces)), key=lambda i: -keys[i])
    chosen_faces = [candidate_faces[i] for i in order[:n_sample]]

    added = 0
    for fi in chosen_faces:
        face = faces[fi]

        # Choose twig type following existing distribution
        r = rng.random()
        cumulative = 0.0
        chosen_type = living_types[-1]
        for t in living_types:
            cumulative += type_dist[t]
            if r <= cumulative:
                chosen_type = t
                break

        # Compute face center and outward normal
        center, face_normal = get_face_center_and_normal(verts, face)

        # Bone assignment via vertex voting (same as extract_twig_placements_from_model)
        twig_bone_id = None
        branch_id_for_twig = None
        if bone_ids:
            bone_counts: dict[int, int] = {}
            for vi in face:
                if vi < len(bone_ids):
                    bid = bone_ids[vi]
                    bone_counts[bid] = bone_counts.get(bid, 0) + 1
            if bone_counts:
                twig_bone_id = max(bone_counts, key=bone_counts.get)

        bone_axis = None
        if twig_bone_id is not None and bones_info:
            local_bone = twig_bone_id - bone_id_offset
            branch_id_for_twig = bone_to_branch.get(local_bone)
            if 0 <= local_bone < len(bones_info):
                _bd = bones_info[local_bone]
                if len(_bd) >= 4:
                    _s, _e = _bd[2], _bd[3]
                    if hasattr(_s, "x"):
                        _delta = (_e.x - _s.x, _e.y - _s.y, _e.z - _s.z)
                    else:
                        _delta = (_e[0] - _s[0], _e[1] - _s[1], _e[2] - _s[2])
                    bone_axis = _normalize(_delta)

        # Emergence direction. The face normal alone points straight out of the
        # bark, leaving foliage edge-on; the bone axis alone is TANGENT to the
        # bark, which buries half of each twig's leaves inside the branch. Tilt
        # the face's own outward normal toward the branch axis instead, so the
        # twig leaves the surface at a natural angle from where it is attached.
        normal = face_normal
        if bone_axis is not None:
            axial = (
                face_normal[0] * bone_axis[0]
                + face_normal[1] * bone_axis[1]
                + face_normal[2] * bone_axis[2]
            )
            radial = _normalize(
                (
                    face_normal[0] - axial * bone_axis[0],
                    face_normal[1] - axial * bone_axis[1],
                    face_normal[2] - axial * bone_axis[2],
                )
            )
            if radial is not None:
                cos_t = math.cos(branch_angle)
                sin_t = math.sin(branch_angle)
                normal = (
                    _normalize(
                        (
                            cos_t * bone_axis[0] + sin_t * radial[0],
                            cos_t * bone_axis[1] + sin_t * radial[1],
                            cos_t * bone_axis[2] + sin_t * radial[2],
                        )
                    )
                    or face_normal
                )

        placement = TwigPlacement(
            type=chosen_type,
            position=center,
            normal=normal,
            orientation=direction_to_quaternion(normal, bone_axis),
            scale=1.0,
            bone_id=twig_bone_id,
            branch_id=branch_id_for_twig,
        )
        placements[chosen_type].append(placement)
        added += 1

    logger.info(
        "Twig densification: added %d synthetic twigs (density=%.1f, total=%d)",
        added,
        density,
        total_existing + added,
    )
    return placements
