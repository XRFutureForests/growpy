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


@dataclass
class TwigPlacement:
    """Twig instance placement data."""

    type: str  # 'twig_long', 'twig_short', 'twig_upward', 'twig_dead'
    position: tuple[float, float, float]
    normal: tuple[float, float, float]  # Facing direction (from get_twig_directions)
    orientation: tuple[float, float, float] = (
        0.0,
        0.0,
        1.0,
    )  # Up vector (from get_twig_orientations)
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
                orientation = (0.0, 0.0, 1.0)
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
                orientation = (0.0, 0.0, 1.0)
                if twig_orientations and base_idx + 2 < len(twig_orientations):
                    orientation = (
                        twig_orientations[base_idx],
                        twig_orientations[base_idx + 1],
                        twig_orientations[base_idx + 2],
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
            if (
                face_branch_ids is not None
                and face_idx < len(face_branch_ids)
            ):
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


def densify_twig_placements(
    model: Any,
    placements: dict[str, list[TwigPlacement]],
    density: float = 1.0,
    bones_info: list | None = None,
    seed: int = 42,
    youth_bias: float = 1.0,
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
        candidate_faces.append(fi)
        candidate_weights.append(youth ** youth_bias if youth_bias != 1.0 else youth)

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

    # Pre-compute vertex coords as tuples for face center calculation
    if scaled_points is not None:
        verts = scaled_points
    else:
        verts = [(p.x, p.y, p.z) if hasattr(p, "x") else (p[0], p[1], p[2]) for p in points]

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
    keys = [
        rng.random() ** (1.0 / w) if w > 1e-12 else 0.0
        for w in candidate_weights
    ]
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

        # Compute face center and normal
        center, normal = get_face_center_and_normal(verts, face)

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

        if twig_bone_id is not None and bones_info:
            local_bone = twig_bone_id - bone_id_offset
            branch_id_for_twig = bone_to_branch.get(local_bone)
            # Replace geometric face normal (radially outward from branch cylinder)
            # with bone direction (along branch axis toward tip). Face normals make
            # synthetic twigs point like spikes perpendicular to the branch, which
            # causes foliage meshes to be edge-on and nearly invisible. Bone direction
            # matches how Grove's own get_twig_directions() orients apical twigs.
            if 0 <= local_bone < len(bones_info):
                _bd = bones_info[local_bone]
                if len(_bd) >= 4:
                    _s, _e = _bd[2], _bd[3]
                    if hasattr(_s, "x"):
                        _dx, _dy, _dz = _e.x - _s.x, _e.y - _s.y, _e.z - _s.z
                    else:
                        _dx, _dy, _dz = _e[0] - _s[0], _e[1] - _s[1], _e[2] - _s[2]
                    _blen = math.sqrt(_dx * _dx + _dy * _dy + _dz * _dz)
                    if _blen > 1e-6:
                        normal = (_dx / _blen, _dy / _blen, _dz / _blen)

        # Orientation: default Z-up in Grove space
        orientation = (0.0, 0.0, 1.0)

        placement = TwigPlacement(
            type=chosen_type,
            position=center,
            normal=normal,
            orientation=orientation,
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
