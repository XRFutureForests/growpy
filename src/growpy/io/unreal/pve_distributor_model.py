"""PVE's parametric foliage distributor, reimplemented offline.

WHY THIS EXISTS
---------------

Every leaf-area figure in the PVE calibration used to be ``instances x
prototype_leaf_area_m2``, which silently assumes every instance sits at scale
1.0. It does not. ``ComputeAttachmentScale`` multiplies by
``ScaleRamp.Eval(lookup) * BaseScale``, and leaf area goes as scale squared.

Both obvious ways to measure leaf area are blind to this. Instance count times
prototype area is blind by construction; foliage triangles times area per
triangle is blind because scaling a mesh does not change its triangle count.
Three export arms differing *only* in the scale ramp produced **byte-identical**
instance and triangle counts while their meshes were visibly different sizes
(a beech went 3.82 m to 4.09 m wide). Under the engine's default 1.0 -> 0.1
ramp the correction factor is **0.087 to 0.141**, so fifteen trees measured
exactly on their Forrester target while carrying about an eighth of the leaf
they were credited with.

This module computes the scale of every placed instance without an Export
click, so :func:`measure_leaf_area` can report the truth.

VALIDATION
----------

The loop is reimplemented from the plugin source and checked against instance
counts actually logged from the editor. Across 14 logged (tree, density) pairs
spanning 281 to 11,587 instances, both species and five tree sizes, it
reproduces **13 exactly and one within a single instance** (fir r05_h25m at
density 158: 5,789 predicted against 5,788 measured). A loop that lands the
count that precisely is trustworthy for the scale distribution it produces
along the way.

Source of truth, all under ``ProceduralVegetationEditor/Source/
ProceduralVegetation/Private/Helpers/``:

===================================  ============================================
``PVAttributesHelper.cpp:280-319``   ``PointLengthFromRoot`` (cumulative, cm->m)
``PVAttributesHelper.cpp:568-607``   ``PointPlantGradient`` (1 at seed, 0 at tips)
``PVParametricDistributionHelper``   ``ComputeAttachmentScale`` (95-131),
``.cpp``                             the placement loop (221-452),
                                     ``FindPointByNormalizedLengthFromRoot``
                                     (709-755), ``SampleVectorByFloat`` /
                                     ``SampleFloatByFloat`` (615-707)
``PVPhyllotaxyHelper.h:71-89``       Spiral leaves MinBuds=MaxBuds=1, so one
                                     instance per accepted placement
===================================  ============================================

KNOWN GAP
---------

``spacing_basis = "PLANT"`` is **+32.4 % out** against the one logged Plant-basis
case. No calibration graph uses that path -- they are all ``BRANCH``, which
reproduces exactly -- so it is refused rather than quoted. See
:func:`simulate_placements`.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from growpy.io.unreal.pve_graph_builder import (
        ConditionSpec,
        DistributorSpec,
        PaletteEntry,
    )

logger = logging.getLogger(__name__)

__all__ = [
    "ENGINE_DEFAULT_RAMP",
    "FLAT_RAMP",
    "LeafAreaMeasurement",
    "MaskedCount",
    "expected_instances",
    "expected_palette_mix",
    "expected_scale_squared_factor",
    "pick_candidates",
    "Placement",
    "measure_leaf_area",
    "ramp_eval",
    "simulate_placements",
]

# What the engine ships, in DistributorSpec's two-endpoint form. Under
# ScaleRampBasis = Plant the lookup is the INVERTED plant gradient -- roughly 1
# on the outer branches where foliage actually lives -- so this places twigs at
# about a tenth of natural size.
ENGINE_DEFAULT_RAMP = (1.0, 0.1)

# What the shipped graphs use: every twig at the size Grove grew it.
FLAT_RAMP = (1.0, 1.0)

_RAMP_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Placement:
    """One placed foliage instance.

    ``generation`` is the branch's generation as the distributor reads it
    (``GetBranchGeneration``: the last point's ``budDevelopment[0]``, +1 for a
    one-point side branch). ``branch_scale`` and ``height`` are the point's
    Scale / Height condition samples: radius and Z, min-max normalised the way
    ``RemapPScalesToGradientRange`` / ``BuildNormalizedPointCaches`` do, then
    lerped between the bracketing points. ``tip`` is the Tip sample.
    """

    scale: float
    branch: int
    along_branch: float
    generation: int = 1
    branch_scale: float = 0.0
    height: float = 0.0
    tip: bool = False


@dataclass(frozen=True)
class MaskedCount:
    """Instances a masked palette spawns from ``points`` attachment points.

    The picker chooses uniformly over every entry when no condition is
    active, and a ``use_as_mask`` pick spawns nothing, so the spawned count is
    binomial: mean ``points * (1 - f)``, sd ``sqrt(points * f * (1 - f))``.
    ``expected`` is the rounded mean; ``band`` is the 2-sigma half-width the
    click should land inside.
    """

    points: int
    mask_fraction: float

    @property
    def mean(self) -> float:
        return self.points * (1.0 - self.mask_fraction)

    @property
    def expected(self) -> int:
        return round(self.mean)

    @property
    def sd(self) -> float:
        return math.sqrt(self.points * self.mask_fraction * (1.0 - self.mask_fraction))

    @property
    def band(self) -> int:
        return math.ceil(2.0 * self.sd)


def expected_instances(points: int, mask_fraction: float = 0.0) -> MaskedCount:
    """Spawned-instance statistics for ``points`` placements under a mask."""
    if points < 0:
        raise ValueError(f"points must be >= 0, got {points}")
    if not 0.0 <= mask_fraction < 1.0:
        raise ValueError(f"mask_fraction must be in [0, 1), got {mask_fraction}")
    return MaskedCount(points=points, mask_fraction=mask_fraction)


@dataclass(frozen=True)
class LeafAreaMeasurement:
    """Leaf area for one tree, with the scale correction made visible.

    ``instances`` is what the export spawns: the attachment-point count times
    ``1 - mask_fraction``, rounded. ``points`` keeps the unmasked count.
    """

    instances: int
    mean_scale: float
    mean_scale_squared: float
    prototype_leaf_area_m2: float
    mask_fraction: float = 0.0
    points: int | None = None

    @property
    def area_m2(self) -> float:
        """True leaf area: ``mean(scale^2) x instances x prototype area``."""
        return (
            self.mean_scale_squared * self.instances * self.prototype_leaf_area_m2
        )

    @property
    def count_based_area_m2(self) -> float:
        """What a count-based measurement would report -- scale-blind."""
        return self.instances * self.prototype_leaf_area_m2

    @property
    def correction_factor(self) -> float:
        """``mean(scale^2)``. 1.0 for a flat ramp at 1.0; 0.087-0.141 for the
        engine default. Report it alongside the area so a value far from 1.0 is
        visible rather than folded invisibly into a total."""
        return self.mean_scale_squared

    def describe(self) -> str:
        return (
            f"{self.instances:,} instances x {self.prototype_leaf_area_m2:.6f} m2 "
            f"x {self.correction_factor:.4f} (scale^2) = {self.area_m2:.2f} m2 "
            f"[count-based would say {self.count_based_area_m2:.2f} m2]"
        )


def ramp_eval(keys, x: float) -> float:
    """Linear ``FRichCurve`` with clamped constant extrapolation."""
    if x <= keys[0][0]:
        return keys[0][1]
    if x >= keys[-1][0]:
        return keys[-1][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:], strict=False):
        if t0 <= x <= t1:
            alpha = 0.0 if t1 == t0 else (x - t0) / (t1 - t0)
            return v0 + (v1 - v0) * alpha
    return keys[-1][1]


def _normalise_ramp(ramp) -> tuple[tuple[float, float], ...]:
    """Accept a two-value ``scale_ramp`` or an explicit key list."""
    keys = tuple(ramp)
    if len(keys) == 2 and all(isinstance(k, (int, float)) for k in keys):
        return ((0.0, float(keys[0])), (1.0, float(keys[1])))
    return tuple((float(t), float(v)) for t, v in keys)


def expected_scale_squared_factor(distributor) -> float:
    """``E[U^2]`` for the distributor's ``randomize_scale`` multiplier.

    ``ComputeAttachmentScale`` multiplies the ramp value by a uniform draw in
    ``[min, max]``, and leaf area goes as scale squared, so a tree's area is
    scaled by ``E[U^2] = (a^2 + ab + b^2) / 3`` -- NOT by the mean ``(a+b)/2``.
    At the identity ``(1.0, 1.0)`` this is exactly 1.0, so a solve that folds
    it in is unchanged for every graph built before XRFF-467.

    Turning randomisation on therefore makes each instance carry MORE area on
    average than its prototype (E[U^2] >= mean^2 for any spread), which the
    offline solve has to correct for or every randomised tree lands over its
    Forrester target.
    """
    lo, hi = getattr(distributor, "randomize_scale", (1.0, 1.0))
    return (lo * lo + lo * hi + hi * hi) / 3.0


def _load(path: Path):
    data = json.loads(Path(path).read_text())
    positions = data["points"]["positions"]
    branch_points = data["primitives"]["points"]
    attributes = data["primitives"]["attributes"]
    point_attrs = data["points"].get("attributes", {})
    meristem = point_attrs.get("budLateralMeristem", {}).get("values")
    development = point_attrs.get("budDevelopment", {}).get("values")
    return (
        positions,
        branch_points,
        attributes["branchParentNumber"]["values"],
        attributes["branchNumber"]["values"],
        # PointScale = LateralMeristem * 100 (AddGrowthMissingData), i.e. cm.
        [m[0] * 100.0 for m in meristem] if meristem else None,
        [d[0] for d in development] if development else None,
    )


def _branch_generations(branch_points, parent, number, order, generation_of_point):
    """Per-branch generation as ``GetBranchGeneration`` reads it.

    From the last point's ``budDevelopment[0]``, +1 for a one-point side
    branch; a JSON without ``budDevelopment`` gets the topological depth
    (trunk = 1), which is what the exporter writes.
    """
    num_to_idx = {n: i for i, n in enumerate(number)}

    def parent_index(b):
        pi = num_to_idx.get(parent[b], -1)
        return -1 if (parent[b] is None or pi < 0 or pi == b) else pi

    depth = [1] * len(branch_points)
    for b in order:
        pi = parent_index(b)
        depth[b] = 1 if pi < 0 else depth[pi] + 1
    if generation_of_point is None:
        return depth
    out = []
    for b, pts in enumerate(branch_points):
        if not pts:
            out.append(depth[b])
            continue
        g = generation_of_point[pts[-1]]
        if len(pts) == 1 and parent_index(b) >= 0:
            g += 1
        out.append(int(g))
    return out


def _normalised_point_scales(
    branch_points, lfr, radii_cm, relative_start, relative_end
):
    """``RemapPScalesToGradientRange``: radius min-max normalised over the
    points inside the placement span of every branch that has a length."""
    if radii_cm is None:
        return None
    lo, hi = math.inf, -math.inf
    for pts in branch_points:
        if len(pts) < 2:
            continue
        root, tip = lfr[pts[0]], lfr[pts[-1]]
        if tip <= root + 1e-4:
            continue
        for p in pts:
            gradient = min(max((lfr[p] - root) / (tip - root), 0.0), 1.0)
            if relative_start <= gradient <= relative_end:
                lo = min(lo, radii_cm[p])
                hi = max(hi, radii_cm[p])
    if not hi > lo:
        return [0.0] * len(radii_cm)
    return [
        (min(max(r, lo), hi) - lo) / (hi - lo) for r in radii_cm
    ]


def _normalised_heights(positions):
    """``BuildNormalizedPointCaches`` Height: UE Z (JSON y) min-max over points."""
    zs = [p[1] for p in positions]
    lo, hi = min(zs), max(zs)
    if not hi > lo + 1e-4:
        return [0.0] * len(zs)
    return [(z - lo) / (hi - lo) for z in zs]


def _walk_order(parent, number):
    """Parents before children, as ``RecursiveWalkBranches`` visits them."""
    num_to_idx = {n: i for i, n in enumerate(number)}
    children: dict[int, list[int]] = {i: [] for i in range(len(number))}
    roots: list[int] = []
    for i, p in enumerate(parent):
        pi = num_to_idx.get(p, -1)
        if p is None or pi < 0 or pi == i:
            roots.append(i)
        else:
            children[pi].append(i)
    order, stack = [], list(reversed(roots))
    while stack:
        branch = stack.pop()
        order.append(branch)
        stack.extend(reversed(children[branch]))
    return order, roots


def _dist(a, b) -> float:
    return math.sqrt(
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    )


def _sample_by_float(sample, pts, pg, arr, is_vec):
    """``SampleVectorByFloat`` / ``SampleFloatByFloat``.

    Both walk the WHOLE branch and keep the LAST bracketing hit, and both fall
    back to a branch that returns a gradient value rather than a sample.
    Reproduced as written, not corrected: the point is to match the engine.
    """
    first, last = pts[0], pts[-1]
    v0 = 1.0 - pg[first]
    v1 = 1.0 - pg[last]
    out = [v0, v0, v0] if is_vec else v0
    lo, hi = (v0, v1) if v0 <= v1 else (v1, v0)
    if lo <= sample <= hi:
        for i in range(1, len(pts)):
            v1 = 1.0 - pg[pts[i]]
            a, b = (v0, v1) if v0 <= v1 else (v1, v0)
            if a <= sample <= b:
                den = v1 - v0
                blend = 0.0 if abs(den) < 1e-12 else (sample - v0) / den
                blend = min(max(blend, 0.0), 1.0)
                p0, p1 = arr[pts[i - 1]], arr[pts[i]]
                if is_vec:
                    out = [p0[k] + (p1[k] - p0[k]) * blend for k in range(3)]
                else:
                    out = p0 + (p1 - p0) * blend
            v0 = v1
    elif abs((1.0 - pg[first]) - sample) > abs((1.0 - pg[last]) - sample):
        out = [v1, v1, v1] if is_vec else v1
    return out


def simulate_placements(
    growth_json: Path | str,
    distributor: DistributorSpec,
    *,
    allow_plant_spacing: bool = False,
) -> list[Placement]:
    """Every instance the distributor will place, with its scale.

    Args:
        growth_json: The skeleton PVE will mesh and distribute over.
        distributor: The graph's own settings. Passing the spec the graph was
            built from is what keeps the model and the graph in agreement.
        allow_plant_spacing: Permit ``spacing_basis = "PLANT"``, which this
            model reproduces **+32.4 % out**. Off by default so the model
            cannot be quoted on a path it does not reproduce.

    Raises:
        ValueError: On ``spacing_basis = "PLANT"`` without the opt-in.
    """
    spacing_basis = distributor.spacing_basis.upper()
    if spacing_basis == "PLANT" and not allow_plant_spacing:
        raise ValueError(
            "spacing_basis = 'PLANT' is reproduced +32.4 % out by this model "
            "and no calibration graph uses it. Fix the Plant path before "
            "quoting a number from it, or pass allow_plant_spacing=True if you "
            "knowingly want the approximation"
        )

    scale_ramp = _normalise_ramp(distributor.scale_ramp)
    # SpacingRamp is evaluated on the even loop value BEFORE the relative
    # remap (PVParametricDistributionHelper.cpp:322-332), so it redistributes
    # the samples along the branch without changing how many there are.
    spacing_ramp = (
        _normalise_ramp(distributor.spacing_ramp)
        if getattr(distributor, "spacing_ramp", None) is not None
        else None
    )
    # Only Whorled reads the node-bud range; ResolvePhyllotaxy pins it to 1
    # under Spiral and to 2 under Opposite/Decussate.
    node_bud_range = (
        tuple(getattr(distributor, "node_buds", (1, 1)))
        if distributor.phyllotaxy_type.upper() == "WHORLED"
        else None
    )
    if node_bud_range == (1, 1):
        node_bud_range = None
    ramp_basis = distributor.scale_ramp_basis.upper()
    density = distributor.branch_density
    relative_start = distributor.relative_start
    relative_end = distributor.relative_end
    base_scale = distributor.base_scale

    positions, branch_points, parent, number, radii_cm, gen_of_point = _load(
        growth_json
    )
    order, roots = _walk_order(parent, number)
    root_set = set(roots)

    # Cumulative length from the root, in metres.
    lfr = [0.0] * len(positions)
    for branch in order:
        pts = branch_points[branch]
        if not pts:
            continue
        if branch in root_set:
            lfr[pts[0]] = 0.0
        for i in range(1, len(pts)):
            lfr[pts[i]] = lfr[pts[i - 1]] + _dist(
                positions[pts[i]], positions[pts[i - 1]]
            ) * 0.01

    # Plant gradient: 1 at the seed, 0 at every tip.
    pg = [0.0] * len(positions)
    for branch in order:
        pts = branch_points[branch]
        if not pts:
            continue
        is_trunk = branch in root_set
        base = 1.0 if is_trunk else pg[pts[0]]
        count = len(pts)
        for i in range(0 if is_trunk else 1, count):
            alpha = (i / (count - 1)) if count > 1 else 0.0
            pg[pts[i]] = base + (0.0 - base) * alpha

    lengths = {}
    for branch in range(len(branch_points)):
        pts = branch_points[branch]
        lengths[branch] = 0.0 if len(pts) < 2 else lfr[pts[-1]] - lfr[pts[0]]
    max_length = max(lengths.values()) if lengths else 0.0
    if max_length <= 1e-4:
        raise ValueError(f"{growth_json}: degenerate tree, no branch has length")
    avg_length = sum(lengths.values()) / len(lengths)
    avg_length = avg_length + (max_length - avg_length) * 0.33

    generations = _branch_generations(
        branch_points, parent, number, order, gen_of_point
    )
    band = distributor.generation_band
    point_scales = _normalised_point_scales(
        branch_points, lfr, radii_cm, relative_start, relative_end
    )
    heights = _normalised_heights(positions)

    placements: list[Placement] = []
    for branch in range(len(branch_points)):
        pts = branch_points[branch]
        length_ratio = lengths[branch] / max_length
        if spacing_basis == "BRANCH":
            loops = int(density * length_ratio)
        else:
            loops = int(density * (avg_length / max_length))
        # LoopNumber = max(loops, 1): every branch always yields at least one
        # sample. At relative_start 0.0 that sample lands on the branch root
        # and is discarded, which is why the count response near this floor is
        # a staircase rather than a slope.
        loops = max(loops, 1)
        if band is not None:
            # LimitStart/EndGeneration: the whole branch is skipped.
            gen = generations[branch]
            if (band[0] is not None and gen < band[0]) or (
                band[1] is not None and gen > band[1]
            ):
                continue
        if len(pts) < 2:
            continue

        lfr_root, lfr_tip = lfr[pts[0]], lfr[pts[-1]]
        previous = positions[pts[0]]
        for j in range(loops):
            base_value = j / max(loops - 1, 1)
            # SpacingRamp's default is the identity 0->1 linear.
            along = base_value if spacing_ramp is None else ramp_eval(
                spacing_ramp, base_value
            )
            # RelativeStart/End remap the placement span into a sub-range of
            # the branch. It moves WHERE instances go, never how many -- which
            # is why an early test saw identical counts at 0.6 and 0.8 and
            # wrongly concluded the setting was inert.
            along = relative_start + (relative_end - relative_start) * along
            if spacing_basis == "PLANT":
                plant_ratio = base_value
                if plant_ratio < 1.0 - pg[pts[0]]:
                    continue
                sampled = _sample_by_float(plant_ratio, pts, pg, lfr, False)
                den = lfr_tip - lfr_root
                along = 0.0 if abs(den) < 1e-12 else (sampled - lfr_root) / den
                along = min(max(along, 0.0), 1.0)
            elif density == 1:
                along = 1.0

            sample_lfr = lfr_root + (lfr_tip - lfr_root) * min(max(along, 0.0), 1.0)
            index_a = index_b = None
            alpha = 0.0
            for i in range(len(pts) - 1):
                l0, l1 = lfr[pts[i]], lfr[pts[i + 1]]
                if (l0 <= sample_lfr <= l1) or (l1 <= sample_lfr <= l0):
                    den = l1 - l0
                    alpha = 0.0 if abs(den) <= 1e-4 else (sample_lfr - l0) / den
                    alpha = min(max(alpha, 0.0), 1.0)
                    index_a, index_b = i, i + 1
                    break
            if index_a is None:
                index_a, index_b = 0, len(pts) - 1
                alpha = 0.0 if along < 0.5 else 1.0
            if index_a == 0 and abs(alpha) < 1e-8:
                # bSampleIsOnBranchRoot: skipped, but the phase still advances.
                continue

            point_a, point_b = pts[index_a], pts[index_b]
            if spacing_basis == "PLANT":
                position = _sample_by_float(base_value, pts, pg, positions, True)
            else:
                position = [
                    positions[point_a][k]
                    + (positions[point_b][k] - positions[point_a][k]) * alpha
                    for k in range(3)
                ]
            if _dist(position, previous) < 0.001:
                continue
            previous = position

            plant_gradient = (1.0 - pg[point_a]) + (
                (1.0 - pg[point_b]) - (1.0 - pg[point_a])
            ) * alpha
            lookup = plant_gradient if ramp_basis == "PLANT" else along
            placements.append(
                Placement(
                    scale=ramp_eval(scale_ramp, lookup) * base_scale,
                    branch=branch,
                    along_branch=along,
                    generation=generations[branch],
                    branch_scale=(
                        point_scales[point_a]
                        + (point_scales[point_b] - point_scales[point_a]) * alpha
                        if point_scales is not None
                        else 0.0
                    ),
                    height=heights[point_a]
                    + (heights[point_b] - heights[point_a]) * alpha,
                    # bIsTipInstance: the sample sits on the branch tip.
                    tip=abs(sample_lfr - lfr_tip) < 0.001
                    and (along >= 0.999 or abs(along - relative_end) < 0.001),
                )
            )
            # Whorled places NumBuds instances at this node, drawn uniformly
            # from [MinimumNodeBuds, MaximumNodeBuds] (the engine's
            # IndexedRandomIntInclusive), except on a tip under
            # bSingleBudTip. Every other phyllotaxy is pinned to one bud by
            # ResolvePhyllotaxy, so this loop is a no-op there.
            extra = 0
            if node_bud_range is not None and not (
                placements[-1].tip and distributor.single_bud_tip
            ):
                lo, hi = node_bud_range
                # The draw is per (branch, loop, seed); the model is not
                # seed-faithful, so it spreads the range evenly instead.
                extra = int((lo + hi) / 2.0 + 0.5) - 1
            for _ in range(max(extra, 0)):
                placements.append(placements[-1])
    return placements


def measure_leaf_area(
    growth_json: Path | str,
    distributor: DistributorSpec,
    prototype_leaf_area_m2: float,
    *,
    graph_scale_ramp=None,
    allow_plant_spacing: bool = False,
    mask_fraction: float = 0.0,
) -> LeafAreaMeasurement:
    """Leaf area for one tree, corrected for instance scale.

    Args:
        growth_json: The skeleton being distributed over.
        distributor: The graph's settings, including its scale ramp.
        prototype_leaf_area_m2: Leaf area of one twig prototype at scale 1.0.
        graph_scale_ramp: The ramp read back from the graph actually being
            measured. When given it must equal the distributor's, and a
            mismatch raises -- a measurement taken against a different ramp
            than the graph carries reproduces the original bug exactly.
        allow_plant_spacing: See :func:`simulate_placements`.
        mask_fraction: Share of ``use_as_mask`` entries in the palette; the
            spawned count is the placement count times ``1 - mask_fraction``
            (see :class:`MaskedCount`).

    Raises:
        ValueError: On a ramp mismatch, or an empty placement set.
    """
    if graph_scale_ramp is not None:
        wanted = _normalise_ramp(distributor.scale_ramp)
        found = _normalise_ramp(graph_scale_ramp)
        if len(wanted) != len(found) or any(
            abs(a[0] - b[0]) > _RAMP_TOLERANCE or abs(a[1] - b[1]) > _RAMP_TOLERANCE
            for a, b in zip(wanted, found, strict=True)
        ):
            raise ValueError(
                f"scale ramp mismatch: measuring with {wanted} but the graph "
                f"carries {found}. Leaf area goes as scale squared, so a "
                f"measurement against the wrong ramp is exactly the bug this "
                f"check exists to prevent -- read the ramp from the graph, or "
                f"rebuild the graph from this spec"
            )

    placements = simulate_placements(
        growth_json, distributor, allow_plant_spacing=allow_plant_spacing
    )
    if not placements:
        raise ValueError(
            f"{growth_json}: the distributor places no instances at density "
            f"{distributor.branch_density}, so there is no leaf area to report"
        )

    points = len(placements)
    # Placement.scale is the deterministic ramp x base_scale; the per-instance
    # randomize_scale draw multiplies it, and it enters the area as its second
    # moment. Both factors are 1.0 at the identity range.
    lo, hi = getattr(distributor, "randomize_scale", (1.0, 1.0))
    mean_scale = sum(p.scale for p in placements) / points * (lo + hi) / 2.0
    mean_scale_squared = (
        sum(p.scale * p.scale for p in placements)
        / points
        * expected_scale_squared_factor(distributor)
    )
    return LeafAreaMeasurement(
        instances=expected_instances(points, mask_fraction).expected,
        mean_scale=mean_scale,
        mean_scale_squared=mean_scale_squared,
        prototype_leaf_area_m2=prototype_leaf_area_m2,
        mask_fraction=mask_fraction,
        points=points,
    )


# The seven condition axes in TEnumRange order; the picker sums them in
# this order, which only matters for float ties.
_CONDITION_AXES = (
    "light",
    "scale",
    "up_alignment",
    "health",
    "tip",
    "height",
    "generation",
)


def pick_candidates(
    sample: dict[str, float],
    entries: Sequence[PaletteEntry],
    conditions: ConditionSpec | None,
) -> list[int]:
    """Palette indices the picker draws from, uniformly, for one placement.

    ``PickCandidateIndex`` (``PVDistributionHelper.cpp:251-356``): no active
    condition -> every entry. Otherwise each entry's weight is the sum over
    active conditions of ``|entry.attr - (sample.attr + offset)| * weight``,
    min-max normalised across entries; entries under ``cutoff_threshold`` are
    candidates, padded to ``minimum_candidates`` with the next-lowest. Equal
    weights are shuffled by the engine before the sort, so a tie at the
    boundary is order-independent only in expectation; they are kept here in
    palette order.
    """
    if not entries:
        return []
    active = conditions.active() if conditions is not None else {}
    if not active:
        return list(range(len(entries)))
    weights = []
    for entry in entries:
        total = 0.0
        for axis in _CONDITION_AXES:
            influence = active.get(axis)
            if influence is None:
                continue
            target = float(sample.get(axis, 0.0)) + influence.offset
            value = float(getattr(entry.attributes, axis))
            total += abs(value - target) * influence.weight
        weights.append(total)
    lo, hi = min(weights), max(weights)
    has_range = hi > lo + 1e-4
    normalised = [
        (min(max(w, lo), hi) - lo) / (hi - lo) if has_range else 0.0 for w in weights
    ]
    ranked = sorted(range(len(entries)), key=lambda i: normalised[i])
    minimum = min(max(conditions.minimum_candidates, 1), len(entries))
    picked: list[int] = []
    for i in ranked:
        if normalised[i] < conditions.cutoff_threshold or len(picked) < minimum:
            picked.append(i)
        else:
            break
    return picked or [ranked[0]]


def expected_palette_mix(
    placements: Sequence[Placement],
    entries: Sequence[PaletteEntry],
    conditions: ConditionSpec | None,
) -> list[float]:
    """Expected picks per palette entry over ``placements``.

    Each placement contributes ``1 / len(candidates)`` to every candidate the
    picker would draw from, so the sum is the placement count; a mask entry's
    share is what spawns nothing. Multiply by each entry's leaf area for the
    expected leaf area of a graded palette.
    """
    mix = [0.0] * len(entries)
    for p in placements:
        sample = {
            "scale": p.branch_scale,
            "height": p.height,
            "tip": 1.0 if p.tip else 0.0,
        }
        candidates = pick_candidates(sample, entries, conditions)
        share = 1.0 / len(candidates)
        for i in candidates:
            mix[i] += share
    return mix
