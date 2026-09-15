"""Solve a tree's PVE foliage layout offline, without an Export click.

The tracked calibration (``config/pve_calibration.toml``) holds measured
densities for a handful of trees. Every other tree of the catalog -- nine
species had none at all on 2026-09-15 -- gets its density from here, using the
offline distributor model (:mod:`~growpy.io.unreal.pve_distributor_model`,
exact to the instance on 13 of 14 logged exports) so the number is a
prediction of what the click will place, not a guess.

Three layouts, one per palette shape:

* **flat** -- one distributor over the whole twig palette, uniform pick. The
  density is bisected so ``instances x mean prototype area`` meets the target.
* **graded** (``LadderSpec``) -- the same distributor above the trunk with a
  Scale-graded palette (each prototype advertises a Scale target at the tree's
  own placement-radius quantiles) plus one apex spray on the leader. The
  density is bisected on the expected palette mix, the way the fir ladder was
  solved on 2026-09-15.
* **compound** (``CompoundSpec``) -- Epic's shape: a fill layer along every
  branch above the trunk at a spacing expressed against the trunk, a tip cap,
  an apex part. No leaf-area solve; the spacing is the rule and the area is
  reported.

The target is Forrester (2017) one-sided leaf area at the tree's own DBH
(re-derived from the growth JSON's trunk radii, the S7_p42 chain) times the
species' ``fullness``. Under the owner's direction of 2026-09-15 leaf area is
reported beside every tree and never the acceptance metric; ``fullness`` is
how a species' crowns are made fuller or sparser between looks.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from growpy.io.unreal.pve_graph_builder import (
    ConditionInfluence,
    ConditionSpec,
    DistributorSpec,
    FoliageLayer,
    PaletteEntry,
)

if TYPE_CHECKING:
    from growpy.config.pve_calibration import CompoundSpec, LadderSpec

logger = logging.getLogger(__name__)

__all__ = [
    "CompoundLayout",
    "SolvedDensity",
    "TreeStats",
    "compound_layout",
    "forrester_target",
    "quantile_targets",
    "solve_flat",
    "solve_graded",
    "tree_stats",
]

# Bisection bounds on the distributor's integer branch density.
_MIN_DENSITY = 1
_MAX_DENSITY = 50_000


@dataclass(frozen=True)
class TreeStats:
    """What the growth JSON says about the tree the foliage goes on."""

    dbh_cm: float
    branches: int
    points: int
    height_m: float
    longest_branch_m: float


@dataclass(frozen=True)
class SolvedDensity:
    """A density the offline model predicts to land ``area_m2`` of leaf."""

    density: int
    instances: int
    area_m2: float
    target_m2: float
    scale_targets: tuple[float, ...] | None = None
    instance_area_m2: float | None = None
    # True when an instance / triangle ceiling, not the target, chose the
    # density -- the tree is deliberately short of its leaf area.
    capped: bool = False

    @property
    def error(self) -> float:
        return self.area_m2 / self.target_m2 - 1.0 if self.target_m2 else 0.0


@dataclass(frozen=True)
class CompoundLayout:
    """The compound chain: main fill distributor + palette, layers, prediction."""

    distributor: DistributorSpec
    palette: tuple[PaletteEntry, ...]
    layers: tuple[FoliageLayer, ...]
    instances: int
    area_m2: float
    fill_instances: int
    cap_instances: int
    apex_instances: int


def tree_stats(growth_json: Path | str, profile_mean: float) -> TreeStats:
    """DBH, size and the longest branch of the skeleton a growth JSON holds.

    DBH is read off the trunk's ``budLateralMeristem`` radius interpolated at
    1.3 m above the lowest trunk point, times ``profile_mean`` (growpy divides
    emitted radii by it so the meshed trunk carries the tape DBH -- XRFF-430),
    times 2 for diameter and 100 for cm. The JSON is Y-up (index 1 is height).
    """
    import numpy as np

    data = json.loads(Path(growth_json).read_text(encoding="utf-8"))
    positions = data["points"]["positions"]
    primitives = data["primitives"]["points"]
    radii = data["points"]["attributes"]["budLateralMeristem"]["values"]
    trunk = primitives[0]
    base = min(positions[i][1] for i in trunk)
    heights = np.array([positions[i][1] - base for i in trunk], dtype=float)
    trunk_radii = np.array([radii[i][0] for i in trunk], dtype=float)
    order = np.argsort(heights)
    dbh_cm = (
        2.0
        * float(np.interp(1.3, heights[order], trunk_radii[order]))
        * profile_mean
        * 100.0
    )
    P = np.asarray(positions, dtype=float)
    lengths = [
        float(np.linalg.norm(np.diff(P[pl], axis=0), axis=1).sum())
        if len(pl) > 1
        else 0.0
        for pl in primitives
    ]
    return TreeStats(
        dbh_cm=dbh_cm,
        branches=len(primitives),
        points=len(positions),
        height_m=float(max(q[1] for q in positions) - base),
        longest_branch_m=max(lengths) if lengths else 0.0,
    )


def forrester_target(species: str, dbh_cm: float) -> tuple[float, str, bool]:
    """Forrester (2017) one-sided leaf area at ``dbh_cm`` for the species.

    Returns ``(m2, model id, extrapolated)``; the species' scientific name is
    resolved through ``tree_asset_lookup.csv`` and the pooled conifer /
    broadleaved fit stands in where no species equation covers the diameter.
    """
    from growpy.config.paths import _find_species_row
    from growpy.tools.calibrate_crown_density import forrester_leaf_area

    row = _find_species_row(species)
    scientific = str(row.get("Scientific Name") or species).strip()
    return forrester_leaf_area(scientific, dbh_cm)


def quantile_targets(samples: Sequence[float], k: int) -> tuple[float, ...]:
    """``k`` mid-quantiles of ``samples``, ascending -- one Scale target per tier."""
    ordered = sorted(samples)
    if not ordered:
        return tuple(0.0 for _ in range(k))
    return tuple(
        ordered[min(len(ordered) - 1, int(((i + 0.5) / k) * len(ordered)))]
        for i in range(k)
    )


def _bisect_density(area_at, target_m2: float) -> int:
    """Smallest-error integer density under a monotone (staircase) ``area_at``."""
    lo, hi = _MIN_DENSITY, _MIN_DENSITY
    while area_at(hi) < target_m2 and hi < _MAX_DENSITY:
        hi *= 2
    hi = min(hi, _MAX_DENSITY)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if area_at(mid) < target_m2:
            lo = mid
        else:
            hi = mid
    candidates = sorted({max(_MIN_DENSITY, lo - 1), lo, hi, min(_MAX_DENSITY, hi + 1)})
    return min(candidates, key=lambda d: abs(area_at(d) - target_m2))


def _largest_density_under(instances_at, max_instances: int) -> int:
    """The largest density whose (monotone) instance count stays under the cap."""
    lo, hi = _MIN_DENSITY, _MIN_DENSITY
    while instances_at(hi) <= max_instances and hi < _MAX_DENSITY:
        lo, hi = hi, hi * 2
    hi = min(hi, _MAX_DENSITY)
    if instances_at(hi) <= max_instances:
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if instances_at(mid) <= max_instances:
            lo = mid
        else:
            hi = mid
    return lo


def solve_flat(
    growth_json: Path,
    base: DistributorSpec,
    mean_prototype_area_m2: float,
    target_m2: float,
    max_instances: int | None = None,
) -> SolvedDensity:
    """Density for a flat palette: every instance carries the palette's mean area.

    ``max_instances`` caps the solve below the target when the target would
    need more instances than one Nanite assembly (or one click) can carry;
    the result then says ``capped`` and lands short of the target.
    """
    from growpy.io.unreal.pve_distributor_model import simulate_placements

    cache: dict[int, int] = {}

    def instances_at(density: int) -> int:
        if density not in cache:
            cache[density] = len(
                simulate_placements(
                    growth_json, dataclasses.replace(base, branch_density=density)
                )
            )
        return cache[density]

    density = _bisect_density(
        lambda d: instances_at(d) * mean_prototype_area_m2, target_m2
    )
    capped = False
    if max_instances is not None and instances_at(density) > max_instances:
        density = _largest_density_under(instances_at, max_instances)
        capped = True
    instances = instances_at(density)
    return SolvedDensity(
        density=density,
        instances=instances,
        area_m2=instances * mean_prototype_area_m2,
        target_m2=target_m2,
        instance_area_m2=mean_prototype_area_m2,
        capped=capped,
    )


def solve_graded(
    growth_json: Path,
    base: DistributorSpec,
    meshes: Sequence[str],
    areas: Sequence[float],
    ladder: LadderSpec,
    target_m2: float,
    max_instances: int | None = None,
) -> SolvedDensity:
    """Density and Scale targets for a graded ladder plus its apex spray.

    Per candidate density: simulate the main layer (gen >= the ladder's start),
    set each tier's Scale target at the placements' radius quantiles, take the
    picker's expected mix over the graded palette and sum the area; the apex
    spray (the largest prototype, density 1 on generation 1) is added on top.
    """
    from growpy.io.unreal.pve_distributor_model import (
        expected_palette_mix,
        simulate_placements,
    )
    from growpy.io.unreal.pve_graph_plan import graded_palette

    conditions = ConditionSpec(
        scale=ConditionInfluence(weight=ladder.scale_weight),
        minimum_candidates=ladder.minimum_candidates,
        cutoff_threshold=ladder.cutoff_threshold,
    )
    largest = max(range(len(areas)), key=lambda i: areas[i])
    apex_area = areas[largest] if ladder.apex else 0.0
    cache: dict[int, tuple[int, tuple[float, ...], float]] = {}

    def evaluate(density: int) -> tuple[int, tuple[float, ...], float]:
        if density not in cache:
            main = dataclasses.replace(
                base,
                branch_density=density,
                generation_band=(ladder.main_generation_start, None),
            )
            placements = simulate_placements(growth_json, main)
            targets = quantile_targets(
                [p.branch_scale for p in placements], len(meshes)
            )
            entries = graded_palette(meshes, areas, targets)
            mix = expected_palette_mix(placements, entries, conditions)
            cache[density] = (
                len(placements),
                targets,
                sum(m * a for m, a in zip(mix, areas, strict=True)),
            )
        return cache[density]

    density = _bisect_density(lambda d: evaluate(d)[2] + apex_area, target_m2)
    capped = False
    if max_instances is not None and evaluate(density)[0] + 1 > max_instances:
        density = _largest_density_under(
            lambda d: evaluate(d)[0] + (1 if ladder.apex else 0), max_instances
        )
        capped = True
    main_instances, targets, main_area = evaluate(density)
    instances = main_instances + (1 if ladder.apex else 0)
    area = main_area + apex_area
    return SolvedDensity(
        density=density,
        instances=instances,
        area_m2=area,
        target_m2=target_m2,
        scale_targets=targets,
        instance_area_m2=area / instances if instances else None,
        capped=capped,
    )


def _tier_index(names: Sequence[str], tier: str) -> int:
    matches = [i for i, n in enumerate(names) if n.endswith(tier)]
    if len(matches) != 1:
        raise ValueError(
            f"compound tier {tier!r} matches {len(matches)} prototype(s) of "
            f"{list(names)}; the bake names tiers p00, p01, ... exactly once"
        )
    return matches[0]


def compound_layout(
    growth_json: Path,
    base: DistributorSpec,
    names: Sequence[str],
    meshes: Sequence[str],
    areas: Sequence[float],
    spec: CompoundSpec,
    longest_branch_m: float,
) -> CompoundLayout:
    """Epic's fill + tip-cap + apex chain over the baked compound parts.

    The fill density is the loop count that spaces parts ``fill_spacing_m``
    apart on the LONGEST branch: PVE's loop count on a branch is
    ``int(density * L / L_max)``, so a spacing has to be expressed against
    ``L_max`` (the trunk) -- density 6 gave exactly one part per branch on a
    15 m fir (2026-09-15). Predicted counts come from the offline model, the
    area from the expected mix; neither is solved to a target.
    """
    from growpy.io.unreal.pve_distributor_model import (
        expected_palette_mix,
        simulate_placements,
    )
    from growpy.io.unreal.pve_graph_plan import graded_palette

    fill_idx = [_tier_index(names, t) for t in spec.fill_tiers]
    fill_meshes = [meshes[i] for i in fill_idx]
    fill_areas = [areas[i] for i in fill_idx]
    span = spec.fill_relative_end - spec.fill_relative_start
    density = max(2, round(longest_branch_m * span / spec.fill_spacing_m))

    pose = dataclasses.replace(base, conditions=None, generation_band=None)
    fill_probe = dataclasses.replace(
        pose,
        branch_density=density,
        relative_start=spec.fill_relative_start,
        relative_end=spec.fill_relative_end,
        generation_band=(spec.fill_generation_start, None),
    )
    fill_placements = simulate_placements(growth_json, fill_probe)
    targets = quantile_targets(
        [p.branch_scale for p in fill_placements], len(fill_meshes)
    )
    palette = graded_palette(fill_meshes, fill_areas, targets)
    conditions = ConditionSpec(
        scale=ConditionInfluence(weight=spec.scale_weight),
        minimum_candidates=spec.minimum_candidates,
        cutoff_threshold=spec.cutoff_threshold,
    )
    fill = dataclasses.replace(fill_probe, conditions=conditions)
    mix = expected_palette_mix(fill_placements, palette, conditions)
    area = sum(m * a for m, a in zip(mix, fill_areas, strict=True))

    layers: list[FoliageLayer] = []
    cap_instances = apex_instances = 0
    if spec.cap_tier:
        cap_idx = _tier_index(names, spec.cap_tier)
        cap = dataclasses.replace(
            pose, branch_density=1, generation_band=(spec.fill_generation_start, None)
        )
        cap_instances = len(simulate_placements(growth_json, cap))
        area += cap_instances * areas[cap_idx]
        layers.append(
            FoliageLayer(distributor=cap, palette=(PaletteEntry(mesh=meshes[cap_idx]),))
        )
    if spec.apex_tier:
        apex_idx = _tier_index(names, spec.apex_tier)
        apex = dataclasses.replace(pose, branch_density=1, generation_band=(1, 1))
        apex_instances = len(simulate_placements(growth_json, apex))
        area += apex_instances * areas[apex_idx]
        layers.append(
            FoliageLayer(
                distributor=apex, palette=(PaletteEntry(mesh=meshes[apex_idx]),)
            )
        )

    return CompoundLayout(
        distributor=fill,
        palette=palette,
        layers=tuple(layers),
        instances=len(fill_placements) + cap_instances + apex_instances,
        area_m2=area,
        fill_instances=len(fill_placements),
        cap_instances=cap_instances,
        apex_instances=apex_instances,
    )


def mean_triangles_per_prototype(sources: Sequence[Path]) -> float:
    """Mean triangle count over ``*_static.usda`` prototypes, off ``faceVertexCounts``.

    growpy's converter triangulates before export, so the count is the number
    of entries in each mesh's ``faceVertexCounts``. Used to size Export clicks
    (one click is one failure unit) for a species whose calibration does not
    record ``palette_flat_mean_triangles``.
    """
    counts = []
    for source in sources:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
        total = 0
        key = "faceVertexCounts = ["
        start = 0
        while True:
            at = text.find(key, start)
            if at < 0:
                break
            end = text.find("]", at)
            total += text.count(",", at, end) + 1
            start = end
        if total:
            counts.append(total)
    if not counts:
        raise ValueError("no faceVertexCounts found in the prototype USDs")
    return math.fsum(counts) / len(counts)
