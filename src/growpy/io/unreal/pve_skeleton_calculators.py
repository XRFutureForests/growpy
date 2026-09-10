"""Pure skeleton-derived calculators for PVE preset mapping.

Extracted from ``pve_grove_mapper.py`` to separate the pure
skeleton-topology computations (generation, length-from-root,
branch gradients, bud directions, LOD gradients) from the PVE
mapping logic that consumes them.

Every function here takes a Grove skeleton object and returns a
plain Python list/dict, with no PVE-specific dependencies. This
makes them independently testable and reusable.
"""

from __future__ import annotations

import math
from typing import Any


def calculate_generation_from_polylines(skeleton: Any) -> list[int]:
    """Calculate generation (hierarchy depth) for each point based on poly_lines.

    Points in the main trunk poly_line are generation 0, branches from it are 1, etc.
    """
    num_points = len(skeleton.points)
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)

    if num_poly_lines == 0:
        return [0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    # Initialize generation array for rebased indices
    generation = [-1] * num_points

    # Assume first poly_line is main trunk (generation 0)
    main_trunk = poly_lines[0]
    for pt_idx in main_trunk:
        rebased_idx = pt_idx - index_offset
        if 0 <= rebased_idx < num_points:
            generation[rebased_idx] = 0

    # Process remaining poly_lines
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]
        if len(poly_line) > 0:
            # First point connects to parent, check its generation
            first_point = poly_line[0]
            rebased_first = first_point - index_offset
            parent_gen = (
                generation[rebased_first] if 0 <= rebased_first < num_points else 0
            )

            # All points in this poly_line are parent_gen + 1
            for pt_idx in poly_line:
                rebased_idx = pt_idx - index_offset
                if 0 <= rebased_idx < num_points:
                    generation[rebased_idx] = max(
                        generation[rebased_idx], parent_gen + 1
                    )

    # Fill any remaining -1 with 0
    return [max(0, g) for g in generation]


def calculate_length_from_root(skeleton: Any) -> list[float]:
    """Calculate cumulative distance from root for each point."""
    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [0.0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    lengths = [0.0] * num_points

    # Process each poly_line with rebased indices.
    # CRITICAL: Child branches share their first point (fork) with the parent.
    # We must inherit the parent's LFR at the fork so child LFR values are
    # tree-root-relative and monotonically increasing.  Non-monotonic LFR
    # breaks PVE Gravity/Slope recursive child matching which requires:
    #   PreviousParentPointLFR < ChildFirstPointLFR <= CurrentParentPointLFR
    for poly_line in poly_lines:
        cumulative = 0.0
        for i in range(len(poly_line)):
            point_idx = poly_line[i]
            rebased_idx = point_idx - index_offset

            if i == 0:
                # Inherit existing LFR set by parent branch processing.
                # For the trunk (first poly_line) this is 0.0.
                if 0 <= rebased_idx < num_points:
                    cumulative = lengths[rebased_idx]
            else:
                prev_idx = poly_line[i - 1]
                rebased_prev = prev_idx - index_offset
                # Bounds check for skeleton_points access with rebased indices
                if 0 <= rebased_prev < num_points and 0 <= rebased_idx < num_points:
                    p1 = skeleton_points[rebased_prev]
                    p2 = skeleton_points[rebased_idx]

                    # Euclidean distance
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    dz = p2[2] - p1[2]
                    distance = (dx * dx + dy * dy + dz * dz) ** 0.5

                    cumulative += distance

            if 0 <= rebased_idx < num_points:
                lengths[rebased_idx] = max(lengths[rebased_idx], cumulative)

    return lengths


def calculate_branch_gradients(skeleton: Any) -> list[float]:
    """Calculate normalized position (0-1) along each branch for each point."""
    num_points = len(skeleton.points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [0.0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    gradients = [0.0] * num_points

    for poly_line in poly_lines:
        num_pts_in_branch = len(poly_line)

        if num_pts_in_branch > 1:
            for i in range(num_pts_in_branch):
                point_idx = poly_line[i]
                rebased_idx = point_idx - index_offset
                gradient = i / (num_pts_in_branch - 1)
                if 0 <= rebased_idx < num_points:
                    gradients[rebased_idx] = gradient
        elif num_pts_in_branch == 1:
            # Single point branch
            point_idx = poly_line[0]
            rebased_idx = point_idx - index_offset
            if 0 <= rebased_idx < num_points:
                gradients[rebased_idx] = 0.0

    return gradients


def calculate_branch_parents(skeleton: Any) -> list[int]:
    """Calculate parent branch index for each branch.

    Returns -1 for root branch, parent index for others.
    """
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)
    parents = [-1] * num_poly_lines

    # First poly_line is root (no parent)
    if num_poly_lines > 0:
        parents[0] = -1

    # Map points to their poly_line index
    point_to_poly: dict[int, int] = {}
    for poly_idx in range(num_poly_lines):
        poly_line = poly_lines[poly_idx]
        for i in range(len(poly_line)):
            point_idx = poly_line[i]
            if point_idx not in point_to_poly:
                point_to_poly[point_idx] = poly_idx

    # Find parent for each branch
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]

        if len(poly_line) > 0:
            # First point should connect to parent branch
            first_point = poly_line[0]

            # Find which poly_line contains this point (other than current)
            parent_poly = -1
            for other_poly_idx in range(poly_idx):
                other_poly_line = poly_lines[other_poly_idx]
                if first_point in other_poly_line:
                    parent_poly = other_poly_idx
                    break

            parents[poly_idx] = parent_poly

    return parents


def calculate_branch_parents_from_skeleton(
    skeleton: Any, num_branches: int
) -> list[int]:
    """Calculate parent branch index for each branch using skeleton poly_line connectivity.

    PVE format: Root branch (0) has parent 0 (self-reference), not -1.

    Uses skeleton (not model) because model only has faces for branches passing cutoff.

    Args:
        skeleton: Grove skeleton with poly_lines
        num_branches: Total number of branches

    Returns:
        List of parent indices per branch (self-reference for roots)
    """
    from .pve_hierarchy_builder import _derive_parents_from_skeleton

    immediate_parents = _derive_parents_from_skeleton(skeleton)

    # Convert to PVE format: -1 becomes self-reference
    parents = []
    for branch_idx in range(num_branches):
        if branch_idx < len(immediate_parents):
            parent = immediate_parents[branch_idx]
            if parent == -1:
                # Root - use self-reference for PVE format
                parents.append(branch_idx)
            else:
                parents.append(parent)
        else:
            parents.append(branch_idx)

    return parents


def calculate_bud_directions(skeleton: Any) -> list[list[float]]:
    """Calculate bud direction vectors from skeleton poly_lines.

    Each point gets up to 6 bud direction vectors (18 floats total).
    Directions are computed from point-to-point connections in poly_lines.

    Args:
        skeleton: Grove skeleton with points and poly_lines

    Returns:
        List of 18-float arrays (6 buds x 3D vector) per point
    """
    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [[0.0] * 18 for _ in range(num_points)]

    # Calculate index offset for rebasing
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    # Initialize with zero vectors (6 buds per point, 3 floats per bud)
    bud_directions = [[0.0] * 18 for _ in range(num_points)]

    # Build a map from point index to all poly_lines it belongs to
    point_to_polylines: dict[int, list[tuple[int, list[int]]]] = {}
    for pl_idx, poly_line in enumerate(poly_lines):
        for pt_idx in poly_line:
            rebased_idx = pt_idx - index_offset
            if rebased_idx not in point_to_polylines:
                point_to_polylines[rebased_idx] = []
            point_to_polylines[rebased_idx].append((pl_idx, poly_line))

    # Calculate direction vectors for each point
    for point_idx in range(num_points):
        if point_idx not in point_to_polylines:
            continue

        directions: list[float] = []

        # For each poly_line containing this point
        for pl_idx, poly_line in point_to_polylines[point_idx]:
            # Find this point's position in the poly_line
            global_idx = point_idx + index_offset
            if global_idx not in poly_line:
                continue

            pos_in_line = poly_line.index(global_idx)

            # Calculate forward direction (to next point)
            if pos_in_line < len(poly_line) - 1:
                next_global_idx = poly_line[pos_in_line + 1]
                next_idx = next_global_idx - index_offset

                if 0 <= next_idx < num_points:
                    p1 = skeleton_points[point_idx]
                    p2 = skeleton_points[next_idx]

                    # Calculate direction vector (Grove Z-up coords)
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    dz = p2[2] - p1[2]

                    # Normalize
                    length = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if length > 0.0001:
                        dx /= length
                        dy /= length
                        dz /= length

                        # Keep Grove Z-up coords (no swap).
                        # C++ reads budDirection as-is (no Y/Z swap),
                        # so it must already be in UE space (Z-up).
                        directions.extend([dx, dy, dz])

        # Fill bud_directions array (up to 6 buds = 18 floats)
        for i in range(min(len(directions), 18)):
            bud_directions[point_idx][i] = directions[i]

        # CRITICAL: Ensure indices [0:3] (AimVector) and [15:18] (PointUpOriginal)
        # have valid, NON-PARALLEL vectors. Mesh Builder computes their cross product
        # to define the ring cross-section plane. Parallel vectors -> zero cross product
        # -> degenerate geometry -> no mesh output.
        if len(directions) == 0:
            # No direction data - default Z-up primary, X-right secondary
            bud_directions[point_idx][0] = 0.0
            bud_directions[point_idx][1] = 0.0
            bud_directions[point_idx][2] = 1.0  # Z-up (UE convention)
            bud_directions[point_idx][15] = 1.0  # X-right (perpendicular)
            bud_directions[point_idx][16] = 0.0
            bud_directions[point_idx][17] = 0.0

        # Ensure index [5] (indices 15-17) has a valid perpendicular vector
        if all(bud_directions[point_idx][i] == 0.0 for i in range(15, 18)):
            ax = bud_directions[point_idx][0]
            ay = bud_directions[point_idx][1]
            az = bud_directions[point_idx][2]
            # Compute perpendicular "up" reference for cross-section orientation
            if abs(az) < 0.95:
                # Reject world-up (0,0,1) from aim direction
                up_x = -az * ax
                up_y = -az * ay
                up_z = 1.0 - az * az
            else:
                # Nearly vertical branch: use (1,0,0) as reference
                up_x = 1.0 - ax * ax
                up_y = -ax * ay
                up_z = -ax * az
            up_len = math.sqrt(up_x * up_x + up_y * up_y + up_z * up_z)
            if up_len > 0.0001:
                up_x /= up_len
                up_y /= up_len
                up_z /= up_len
            else:
                up_x, up_y, up_z = 0.0, 1.0, 0.0
            bud_directions[point_idx][15] = up_x
            bud_directions[point_idx][16] = up_y
            bud_directions[point_idx][17] = up_z

    return bud_directions


def _norm3(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Unit vector, or None when the input is degenerate."""
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1e-9:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)


def _nearest_point_indices(
    points: list, targets: list[tuple[float, float, float]]
) -> list[int]:
    """Index of the nearest entry of ``points`` for each of ``targets``.

    A uniform grid keyed on the median point spacing keeps this near-linear; the
    naive form is len(points) x len(targets), which on a real skeleton is tens of
    millions of distance evaluations per tree.
    """
    if not points or not targets:
        return []

    gaps = []
    step = max(1, len(points) // 256)
    for i in range(0, len(points) - 1, step):
        a, b = points[i], points[i + 1]
        gaps.append(
            math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
        )
    gaps = [g for g in gaps if g > 1e-9]
    cell = (sorted(gaps)[len(gaps) // 2] * 4.0) if gaps else 0.1
    if cell <= 1e-9:
        cell = 0.1

    grid: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(points):
        key = (int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))
        grid.setdefault(key, []).append(i)

    out = []
    for t in targets:
        base = (int(t[0] // cell), int(t[1] // cell), int(t[2] // cell))
        best_idx, best_d2 = -1, float("inf")
        ring = 1
        while best_idx < 0 and ring <= 4:
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    for dz in range(-ring, ring + 1):
                        for i in grid.get(
                            (base[0] + dx, base[1] + dy, base[2] + dz), ()
                        ):
                            p = points[i]
                            d2 = (
                                (p[0] - t[0]) ** 2
                                + (p[1] - t[1]) ** 2
                                + (p[2] - t[2]) ** 2
                            )
                            if d2 < best_d2:
                                best_idx, best_d2 = i, d2
            ring += 1
        if best_idx < 0:
            for i, p in enumerate(points):
                d2 = (p[0] - t[0]) ** 2 + (p[1] - t[1]) ** 2 + (p[2] - t[2]) ** 2
                if d2 < best_d2:
                    best_idx, best_d2 = i, d2
        out.append(best_idx)
    return out


def assign_axillary_from_twigs(
    skeleton: Any,
    bud_directions: list[list[float]],
    twig_positions: list[tuple[float, float, float]],
    twig_directions: list[tuple[float, float, float]],
) -> dict[str, int]:
    """Seed ``budDirection[1]`` (Axillary) per BRANCH from Grove's twig frames.

    PVE's parametric distributor derives the roll of every twig on a branch from
    a single vector -- that branch's Axillary slot, read from its FIRST point
    (``PVParametricDistributionHelper.cpp``: ``InitialBudDirection =
    BranchBudDirPerPoint[0]``), then rotated ``PhyllotaxyFormation`` degrees per
    node and parallel-transported along the branch. Nothing else rolls a twig.

    **What this is NOT.** It was first written on the belief that Axillary was
    usually zero, so PVE fell back to ``FindBestAxisVectors(Apical)`` -- an
    arbitrary perpendicular. **That was wrong**, and the retraction matters
    because it was the whole justification. Measured on real exports:

        fir_r20_h25m_f060   branch-first-point Axillary populated 99.93 %
        beech_r05_h05m_f006 branch-first-point Axillary populated 99.38 %

    The earlier "27.5 % populated" figure counted ALL points; the populated ones
    are precisely the forks, and a branch's first point IS a fork, so the slot
    PVE actually reads was almost always filled. Nor was it degenerate: the angle
    between Axillary and Apical has median 73.7 deg (fir) / 52.4 deg (beech),
    with no branch within 15 deg of parallel. **The fallback was never reached.**

    **What this actually changes.** Pre-existing Axillary at a fork is the
    forward direction of the OTHER poly_line through that fork -- the sibling or
    parent branch's heading. That is a real direction, but it is a property of
    branching topology, unrelated to the phyllotactic phase Grove grew its twigs
    on. This replaces it with Grove's own answer: the twig nearest the branch
    base, projected perpendicular to the branch axis. Grove gives every twig a
    unit quaternion whose rotated +X is the growth direction
    (``core.twig._quat_forward``).

    So the argument for it is that a twig-derived phase is more principled than a
    sibling-branch-derived one -- **not** that it repairs a fallback. Whether it
    visibly improves a crown is UNVERIFIED; it needs an A/B in the PVE preview
    against the same tree exported without it.

    **Scope.** PVE takes one seed per branch and generates the rest by rotating
    it per node, so it cannot consume a per-twig orientation: this makes each
    branch's fan *start* where Grove's does, not match it twig for twig. Points
    other than a branch's first are written too -- harmless, and it keeps the
    attribute inspectable -- but only index 0 is read.

    For the seed to survive into the render the distributor needs
    ``ResetPhyllotaxy = false`` (true overwrites it with ``cross(Apical,
    UpVector)``), and to reproduce the seed direction exactly also
    ``AxilAngle = 0``, ``Rotation = 0`` and no axil randomisation.

    Args:
        skeleton: Grove skeleton (``points`` + ``poly_lines``).
        bud_directions: 18-float-per-point list from
            ``calculate_bud_directions``, in Grove Z-up. Mutated in place.
        twig_positions: Twig attachment points, Grove world space, Z-up.
        twig_directions: Matching growth directions (+X rotated by Grove's twig
            quaternion), Z-up.

    Returns:
        Counts: ``branches``, ``seeded``, ``no_twig``, ``degenerate``.
    """
    stats = {"branches": 0, "seeded": 0, "no_twig": 0, "degenerate": 0}

    points = list(skeleton.points)
    poly_lines = skeleton.poly_lines
    num_points = len(points)
    if not points or not poly_lines or not twig_positions:
        return stats
    if len(twig_directions) != len(twig_positions):
        raise ValueError(
            "twig_positions and twig_directions must be the same length "
            f"(got {len(twig_positions)} and {len(twig_directions)})"
        )

    stats["branches"] = len(poly_lines)

    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    nearest = _nearest_point_indices(points, list(twig_positions))

    point_twigs: dict[int, list[int]] = {}
    for t_idx, p_idx in enumerate(nearest):
        if 0 <= p_idx < num_points:
            point_twigs.setdefault(p_idx, []).append(t_idx)

    for poly_line in poly_lines:
        rebased = [i - index_offset for i in poly_line]
        rebased = [i for i in rebased if 0 <= i < num_points]
        if len(rebased) < 2:
            stats["no_twig"] += 1
            continue

        p0, p1 = points[rebased[0]], points[rebased[1]]
        axis = _norm3((p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]))
        if axis is None:
            stats["degenerate"] += 1
            continue

        # First twig along the branch: the earliest point that carries one.
        # Taking the MEAN would be wrong -- distichous species alternate their
        # twigs about the axis, so opposite ranks cancel to nearly zero.
        seed = None
        for pt in rebased:
            cands = point_twigs.get(pt)
            if not cands:
                continue
            base = points[pt]
            best_t, best_d2 = None, float("inf")
            for t in cands:
                q = twig_positions[t]
                d2 = (
                    (q[0] - base[0]) ** 2
                    + (q[1] - base[1]) ** 2
                    + (q[2] - base[2]) ** 2
                )
                if d2 < best_d2:
                    best_t, best_d2 = t, d2
            if best_t is not None:
                seed = twig_directions[best_t]
                break

        if seed is None:
            stats["no_twig"] += 1
            continue

        # Project perpendicular to the branch axis: PVE builds
        # AxilAxis = cross(Axillary, Apical), and a seed parallel to the axis
        # makes that zero, dropping straight back to FindBestAxisVectors.
        dot = seed[0] * axis[0] + seed[1] * axis[1] + seed[2] * axis[2]
        perp = _norm3(
            (
                seed[0] - dot * axis[0],
                seed[1] - dot * axis[1],
                seed[2] - dot * axis[2],
            )
        )
        if perp is None:
            stats["degenerate"] += 1
            continue

        for pt in rebased:
            bud_directions[pt][3] = perp[0]
            bud_directions[pt][4] = perp[1]
            bud_directions[pt][5] = perp[2]
        stats["seeded"] += 1

    return stats


def calculate_lod_gradients(
    skeleton: Any, pscales: list[float], age_values: list[int]
) -> dict[str, list[float]]:
    """Calculate LOD (Level of Detail) gradient values from skeleton data.

    PVE uses these gradients to control mesh density and material properties.
    Gradients range from ~1.0 at base to ~0.0 at tips.

    Args:
        skeleton: Grove skeleton
        pscales: Point scale (radius) values
        age_values: Point age values

    Returns:
        Dictionary with LOD gradient arrays
    """
    num_points = len(skeleton.points)

    if not pscales or not age_values:
        # Fallback if data is missing
        return {
            "LOD_totalPscaleGradient": [0.0] * num_points,
            "LOD_plantPscaleGradient": [0.0] * num_points,
            "LOD_branchPscaleGradient": [0.0] * num_points,
            "LOD_groundGradient": [0.0] * num_points,
            "LOD_hullGradient": [0.0] * num_points,
            "LOD_mainTrunkGradient": [0.0] * num_points,
            "LOD_canopyGradient": [0.0] * num_points,
        }

    # Calculate max values for normalization
    max_pscale = max(pscales) if pscales else 1.0
    max_age = max(age_values) if age_values else 1.0

    # Avoid division by zero
    if max_pscale < 0.0001:
        max_pscale = 1.0
    if max_age < 0.0001:
        max_age = 1.0

    # LOD_totalPscaleGradient: Based on pscale ratio (thick = high, thin = low)
    # Range from ~1.0 at base to ~0.0 at tips
    lod_total_pscale_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_plantPscaleGradient: Similar to total, but inverted age contribution
    # Older points (closer to base) have higher values
    lod_plant_pscale_gradient = [
        pscales[i] / max_pscale * (1.0 - age_values[i] / max_age)
        for i in range(num_points)
    ]

    # LOD_branchPscaleGradient: Per-branch thickness gradient
    lod_branch_pscale_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_groundGradient: Proximity to ground (inverse age)
    lod_ground_gradient = [1.0 - age / max_age for age in age_values]

    # LOD_hullGradient: Tree envelope/silhouette (based on pscale)
    lod_hull_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_mainTrunkGradient: Main trunk identification (highest pscale points)
    # Threshold: consider points with pscale > 50% of max as main trunk
    trunk_threshold = max_pscale * 0.5
    lod_main_trunk_gradient = [
        1.0 if pscale >= trunk_threshold else 0.0 for pscale in pscales
    ]

    # LOD_canopyGradient: Canopy/crown region (younger, thinner branches)
    # Inverse of ground gradient
    lod_canopy_gradient = [age / max_age for age in age_values]

    return {
        "LOD_totalPscaleGradient": lod_total_pscale_gradient,
        "LOD_plantPscaleGradient": lod_plant_pscale_gradient,
        "LOD_branchPscaleGradient": lod_branch_pscale_gradient,
        "LOD_groundGradient": lod_ground_gradient,
        "LOD_hullGradient": lod_hull_gradient,
        "LOD_mainTrunkGradient": lod_main_trunk_gradient,
        "LOD_canopyGradient": lod_canopy_gradient,
    }


def max_branch_generation(skeleton: Any) -> int:
    """Calculate maximum branch generation depth from skeleton topology."""
    poly_lines = skeleton.poly_lines
    if not poly_lines:
        return 0

    num_branches = len(poly_lines)

    # Build point-to-branch index: map each point to the branch(es) containing it
    point_to_branch: dict[int, int] = {}
    for j in range(num_branches):
        for pt in poly_lines[j]:
            if pt not in point_to_branch:
                point_to_branch[pt] = j

    generation = [0] * num_branches

    for i in range(num_branches):
        if len(poly_lines[i]) < 2:
            continue
        first_pt = poly_lines[i][0]
        parent = point_to_branch.get(first_pt)
        if parent is not None and parent != i:
            generation[i] = generation[parent] + 1

    return max(generation) if generation else 0
