"""PVE's Carve node (radius basis) modelled on a growth JSON, for the offline solve.

The graph trims the skeleton with PVE's own Carve node (owner, 2026-11-12: shorten
the long, bendy branch ends of the conifers). This module only predicts what that
node keeps, so the leaf-area solve places twigs on the branches PVE will mesh.
It mirrors ``FPVCarve::CarveFromTop`` (UE 5.8 ``PVCarve.cpp``), radius basis:

* every point gets ``v = (r_max - r) / (r_max - r_min)`` over the whole plant
  (``r`` = point scale = ``budLateralMeristem[0] * 100``);
* each branch, walked from its base, keeps the points with ``v < 1 - carve``; the
  first point past the line is pulled back to the crossing (blend clamped to
  [0.1, 1]) and every child branch rooted beyond the last kept point goes with
  its whole subtree.

Not modelled: the re-taper of the kept point scales (``UpdatePointScales``), which
moves radius-graded tier picks but not where twigs sit.
"""

import copy
import math

from growpy.io.unreal.pve_distributor_model import _walk_order

RADIUS = 0  # budLateralMeristem[0]: radius in metres
ROOT_DISTANCE = 5  # budLateralMeristem[5]: PVE's LengthFromRoot when the JSON has none


def _meristem(data: dict) -> list[list[float]]:
    return data["points"]["attributes"]["budLateralMeristem"]["values"]


def _branches(data: dict):
    prims = data["primitives"]
    attrs = prims["attributes"]
    return (
        prims["points"],
        attrs["branchParentNumber"]["values"],
        attrs["branchNumber"]["values"],
    )


def _flat(values) -> list:
    return [v[0] if isinstance(v, list) else v for v in values]


def carve_skeleton(data: dict, carve: float) -> dict:
    """A trimmed copy of a growth JSON, as PVE's Carve (radius basis) leaves it."""
    if not 0.0 <= carve <= 1.0:
        raise ValueError(f"carve must be in [0, 1], got {carve}")
    out = copy.deepcopy(data)
    if carve == 0.0:
        return out
    positions = out["points"]["positions"]
    meristem = _meristem(out)
    branch_points, parent, number = _branches(out)
    parent, number = _flat(parent), _flat(number)
    radii = [m[RADIUS] * 100.0 for m in meristem]
    lfr = [m[ROOT_DISTANCE] for m in meristem]
    r_min, r_max = min(radii), max(radii)
    span = (r_max - r_min) or 1.0
    value = [(r_max - r) / span for r in radii]
    line = 1.0 - carve
    order, _roots = _walk_order(parent, number)
    num_to_idx = {n: i for i, n in enumerate(number)}
    children: dict[int, list[int]] = {i: [] for i in range(len(number))}
    for i, p in enumerate(parent):
        pi = num_to_idx.get(p, -1)
        if p is not None and pi >= 0 and pi != i:
            children[pi].append(i)
    removed = [False] * len(branch_points)

    def drop(branch: int) -> None:
        stack = [branch]
        while stack:
            b = stack.pop()
            removed[b] = True
            stack.extend(children[b])

    for branch in order:
        pts = branch_points[branch]
        if removed[branch] or not pts:
            continue
        n = len(pts)
        end = 1
        while end < n and value[pts[end]] < line + 1e-4:
            end += 1
        end -= 1
        if end == n - 1:
            continue
        cut_lfr = lfr[pts[end]]
        for child in children[branch]:
            cpts = branch_points[child]
            if cpts and lfr[cpts[0]] > cut_lfr:
                drop(child)
        end += 1
        last, prev = pts[end], pts[end - 1]
        lo, hi = value[prev], value[last]
        blend = (line - lo) / (hi - lo) if hi != lo else 1.0
        blend = min(max(blend, 0.1), 1.0)
        positions[last] = [
            a + (b - a) * blend
            for a, b in zip(positions[prev], positions[last], strict=True)
        ]
        meristem[last][RADIUS] = (
            meristem[prev][RADIUS]
            + (meristem[last][RADIUS] - meristem[prev][RADIUS]) * blend
        )
        branch_points[branch] = pts[: end + 1]
    for b, gone in enumerate(removed):
        if gone:
            branch_points[b] = []
    return out


def lateral_length(data: dict) -> float:
    """Summed length of every non-trunk branch, in the JSON's units."""
    positions = data["points"]["positions"]
    branch_points, parent, number = _branches(data)
    _order, roots = _walk_order(_flat(parent), _flat(number))
    root_set = set(roots)
    total = 0.0
    for b, pts in enumerate(branch_points):
        if b in root_set:
            continue
        for i in range(1, len(pts)):
            total += math.dist(positions[pts[i - 1]], positions[pts[i]])
    return total


def carve_for_trim(data: dict, trim: float, tolerance: float = 0.005) -> float:
    """The Carve value that removes ``trim`` of the lateral branch length."""
    if not 0.0 <= trim < 1.0:
        raise ValueError(f"trim must be in [0, 1), got {trim}")
    if trim == 0.0:
        return 0.0
    full = lateral_length(data)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        removed = 1.0 - lateral_length(carve_skeleton(data, mid)) / full
        if abs(removed - trim) <= tolerance:
            return round(mid, 6)
        lo, hi = (mid, hi) if removed < trim else (lo, mid)
    return round((lo + hi) / 2, 6)
