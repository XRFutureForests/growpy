#!/usr/bin/env python3
"""Harvest compound foliage part candidates from a Grove tree (XRFF-357 prototype).

MegaPlants does not instance single twigs. Its foliage parts are branch
complexes carrying several generations of woody structure plus their leaves --
`CH_Branch_Up_A`, `Leaf_Twig_03`, and so on -- and every shipped preset caps
`compoundMaxBranchGeneration` at 2 or 3 with roughly 1000 instances per tree.
growpy places Grove twigs 1:1: a 25-cycle european_beech carries 74,886 twig
placements, and `forest.toml` records ~52k on a 10 m oak.

This tool answers the question that decides whether the approach is viable:
at what cut does a species reach the ~1000-instance budget, and how many
distinct prototypes are needed to cover the candidates at that cut?

The cut is by branch base diameter rather than generation count. Crown
periphery sits at different hierarchy depths in different parts of a tree --
on a 25 m beech, generation 6 in places and generation 3 in others -- so a
fixed generation cut removes a large low limb and a tiny apical twiglet
alike. Diameter is the quantity `build_cutoff_thickness` already uses.

Diameter alone is not sufficient, though: a branch's base radius does not
bound its subtree size. A plain diameter cut on beech yields a strongly
bimodal set -- roughly 40% single-tip stubs alongside parts spanning 2.8 m,
which would be both repetitive and (parts being unskinned) rigid under wind.
The cut is therefore adaptive: a subtree becomes a part only once it also
fits a tip-count and span band, and oversized candidates are descended into.

Usage:
    python src/growpy/tools/harvest_compound_parts.py european_beech --sweep
    python src/growpy/tools/harvest_compound_parts.py european_beech --cut-diameter 0.02 --clusters 7
    python src/growpy/tools/harvest_compound_parts.py european_beech --no-adaptive --sweep
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Diameters (m) swept by --sweep. Spans single-twig scale up to small limbs.
DEFAULT_SWEEP = (0.004, 0.006, 0.008, 0.010, 0.012, 0.016, 0.020, 0.030, 0.040)

# MegaPlants lands every shipped preset near this instance count per tree.
TARGET_INSTANCES = 1000

# Grove's living twig types, in the order the CLI resolves their assets. Grove
# carries NO per-twig scale -- these four types (the fourth, twig_dead, has no
# asset) are its only size signal, and it places them by position: measured on
# an 18-cycle silver_fir, twig_long sits at the branch TIPS (median position
# along the parent branch 1.00) and is 89.9% of the twigs in the top quarter of
# the crown, while twig_short sits mid-branch (median 0.27) and twig_upward is
# the single apex twig. So a size ladder is applied through the TYPE.
LIVING_TWIG_TYPES = ("twig_long", "twig_short", "twig_upward")

# Size band for one compound part. A part is instanced rigidly, so an
# oversized one reads as a stiff limb in wind and repeats visibly.
DEFAULT_MAX_TIPS = 40
DEFAULT_MAX_SPAN = 1.0

# Living twigs a part may carry. This, not tips or span, is what decides its
# face count: every twig is a whole twig asset welded in, ~7,565 faces at the
# close-range conversion profile. Measured on a 25-cycle european_beech at cut
# diameter 0.030 with tips<=60/span<=2.0, the distribution is heavily skewed --
# median 3 twigs, mean 19, p95 101, max 361 -- so a handful of parts carry most
# of the crown. Unbounded, the largest part is 2.73M faces; at 150 it is 1.13M
# and the instance count only rises from 3,826 to 4,621 (19.6x -> 16.2x). Below
# roughly 80 the trade turns bad: 40 costs 8,813 instances for 8.5x.
DEFAULT_MAX_TWIGS = 150

# Faces in one exported european_beech twig at the close-range profile, used
# only to report an estimated part size before anything is baked.
TWIG_FACE_ESTIMATE = 7565


@dataclass
class BranchRecord:
    """One Grove branch, flattened out of the recursive node structure."""

    index: int
    parent: int
    depth: int
    base_radius: float
    tip_radius: float
    length: float
    base_pos: tuple[float, float, float]
    base_dir: tuple[float, float, float]
    node_count: int
    children: list[int] = field(default_factory=list)


def flatten_branches(tree: Any) -> list[BranchRecord]:
    """Walk `tree.nodes` / `node.side_branches` into a flat branch list.

    Grove exposes a tree as a trunk node list where each node carries
    `side_branches`, a list of `Branch` objects with their own `nodes`. The
    recursion is cheap (0.2 s for 26k branches) but `.nodes` is a property,
    so it is read exactly once per branch here.

    A parent is always appended before its children, so the returned list is
    in topological order -- which `precompute_subtrees` relies on.
    """
    records: list[BranchRecord] = []

    def _add(nodes: list, parent: int, depth: int) -> int:
        if not nodes:
            return -1

        index = len(records)
        positions = [(n.pos.x, n.pos.y, n.pos.z) for n in nodes]
        radii = [n.radius for n in nodes]

        length = 0.0
        for a, b in zip(positions, positions[1:]):
            length += math.dist(a, b)

        if len(positions) > 1:
            dx = positions[1][0] - positions[0][0]
            dy = positions[1][1] - positions[0][1]
            dz = positions[1][2] - positions[0][2]
            norm = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            base_dir = (dx / norm, dy / norm, dz / norm)
        else:
            base_dir = (0.0, 0.0, 1.0)

        records.append(
            BranchRecord(
                index=index,
                parent=parent,
                depth=depth,
                base_radius=radii[0],
                tip_radius=radii[-1],
                length=length,
                base_pos=positions[0],
                base_dir=base_dir,
                node_count=len(nodes),
            )
        )
        if parent >= 0:
            records[parent].children.append(index)

        for node in nodes:
            for child in getattr(node, "side_branches", None) or []:
                _add(child.nodes, index, depth + 1)

        return index

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 100_000))
    _add(tree.nodes, -1, 0)
    return records


def precompute_subtrees(records: list[BranchRecord]) -> dict[str, list]:
    """Aggregate every subtree bottom-up in one pass.

    `flatten_branches` appends parents before children, so iterating the list
    in reverse visits every child before its parent.

    `tips` (childless branches) is a *relative* leaf-mass descriptor, not a twig
    count -- Grove places twigs along a branch rather than only at its end, so
    tips run about 4x under the true placement count (measured on european_beech:
    17,706 tips against 74,886 twig faces). Clustering and the size band only
    need the relative measure, and the reported instance and base-branch counts
    are exact, so the offset does not affect either.
    """
    n = len(records)
    branches = [1] * n
    nodes = [0] * n
    tips = [0] * n
    total_length = [0.0] * n
    max_depth = [0] * n
    lo = [[0.0, 0.0, 0.0] for _ in range(n)]
    hi = [[0.0, 0.0, 0.0] for _ in range(n)]

    for idx in range(n - 1, -1, -1):
        rec = records[idx]
        nodes[idx] += rec.node_count
        total_length[idx] += rec.length
        if not rec.children:
            tips[idx] = 1
        for axis in range(3):
            lo[idx][axis] = hi[idx][axis] = rec.base_pos[axis]

        for child in rec.children:
            branches[idx] += branches[child]
            nodes[idx] += nodes[child]
            tips[idx] += tips[child]
            total_length[idx] += total_length[child]
            max_depth[idx] = max(max_depth[idx], max_depth[child] + 1)
            for axis in range(3):
                lo[idx][axis] = min(lo[idx][axis], lo[child][axis])
                hi[idx][axis] = max(hi[idx][axis], hi[child][axis])

    span = [
        math.sqrt(sum((hi[i][a] - lo[i][a]) ** 2 for a in range(3))) for i in range(n)
    ]

    return {
        "branches": branches,
        "nodes": nodes,
        "tips": tips,
        "total_length": total_length,
        "max_depth": max_depth,
        "span": span,
    }


def find_cut_set(records: list[BranchRecord], cut_radius: float) -> list[int]:
    """Branches that first fall below `cut_radius`, with an above-threshold parent.

    The plain diameter cut, kept for comparison against the adaptive one.
    """
    cut: list[int] = []
    for rec in records:
        if rec.base_radius >= cut_radius:
            continue
        if rec.parent < 0:
            continue
        if records[rec.parent].base_radius >= cut_radius:
            cut.append(rec.index)
    return cut


def count_subtree_twigs(model: Any, records: list[BranchRecord]) -> list[int]:
    """Living twig placements in each branch's subtree.

    Grove marks one face per living twig (verified: 35,847 twig-marked faces
    against 35,847 entries in `get_twig_locations()`), and that face carries
    its host branch's `face_attribute_branch_id`, which is `walker_index + 1`.

    Dead twigs are excluded: they have no entry in Grove's twig arrays at all
    and are reconstructed from face centroids elsewhere, and a species only
    ships dead-twig geometry if someone made it.

    `.faces` and the face attributes are properties that rebuild the whole list
    per access, so each is read exactly once here.
    """
    branch_ids = model.face_attribute_branch_id
    long_ = model.face_attribute_twig_long
    short = model.face_attribute_twig_short
    upward = model.face_attribute_twig_upward

    per_branch: dict[int, int] = {}
    for index in range(len(branch_ids)):
        if long_[index] or short[index] or upward[index]:
            key = branch_ids[index]
            per_branch[key] = per_branch.get(key, 0) + 1

    # Bottom-up: flatten_branches appends parents before children.
    totals = [0] * len(records)
    for index in range(len(records) - 1, -1, -1):
        totals[index] = per_branch.get(index + 1, 0) + sum(
            totals[child] for child in records[index].children
        )
    return totals


def find_cut_set_adaptive(
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut_radius: float,
    max_tips: int = DEFAULT_MAX_TIPS,
    max_span: float = DEFAULT_MAX_SPAN,
    twig_totals: list[int] | None = None,
    max_twigs: int = DEFAULT_MAX_TWIGS,
) -> list[int]:
    """Diameter cut bounded by a part size band.

    A subtree is emitted as a part once it is below the cut diameter *and*
    fits the band. An oversized subtree is descended into instead, so its own
    woody axis stays in the base mesh and its children become the parts. This
    lets the base mesh follow a big limb as far down as it needs to while
    still cutting aggressively in the fine crown.

    `twig_totals` (from `count_subtree_twigs`) adds the twig-count bound. It is
    optional so the sizing sweeps can run without building a model, but for
    baking it is the bound that matters -- see DEFAULT_MAX_TWIGS.
    """
    parts: list[int] = []
    stack = [0]

    while stack:
        idx = stack.pop()
        rec = records[idx]

        if rec.parent >= 0 and rec.base_radius < cut_radius:
            fits = metrics["tips"][idx] <= max_tips and metrics["span"][idx] <= max_span
            if fits and twig_totals is not None:
                fits = twig_totals[idx] <= max_twigs
            # A childless branch cannot be subdivided further, so it is taken
            # whether or not it fits rather than being dropped.
            if fits or not rec.children:
                parts.append(idx)
                continue

        stack.extend(rec.children)

    return parts


def subtree_stats(
    records: list[BranchRecord],
    metrics: dict[str, list],
    root: int,
    twig_totals: list[int] | None = None,
) -> dict[str, float]:
    """Descriptors for the subtree hanging off `root`.

    `twig_totals` (from `count_subtree_twigs`) adds the foliage load. Without it
    the descriptor is pure branch geometry, and clustering cannot tell a leafy
    subtree from a bare stub of the same shape (XRFF-386).
    """
    base = records[root]
    return {
        "twigs": float(twig_totals[root]) if twig_totals is not None else 0.0,
        "branches": metrics["branches"][root],
        "nodes": metrics["nodes"][root],
        "tips": metrics["tips"][root],
        "total_length": metrics["total_length"][root],
        "max_depth": metrics["max_depth"][root],
        "span": metrics["span"][root],
        "base_radius": base.base_radius,
        "length": base.length,
        # Up-alignment: MegaPlants conditions foliage placement on it, and it
        # separates CH_Branch_Up_* from CH_Branch_* in the hazel palette.
        "up_alignment": base.base_dir[2],
        "height": base.base_pos[2],
    }


def sweep_cut_diameters(
    records: list[BranchRecord],
    metrics: dict[str, list],
    diameters: tuple[float, ...] = DEFAULT_SWEEP,
    adaptive: bool = True,
    max_tips: int = DEFAULT_MAX_TIPS,
    max_span: float = DEFAULT_MAX_SPAN,
) -> list[dict[str, float]]:
    """Instance count and part size for each candidate cut diameter."""
    rows = []
    for diameter in diameters:
        if adaptive:
            cut = find_cut_set_adaptive(
                records, metrics, diameter / 2.0, max_tips, max_span
            )
        else:
            cut = find_cut_set(records, diameter / 2.0)

        if not cut:
            rows.append({"diameter": diameter, "instances": 0})
            continue

        stats = [subtree_stats(records, metrics, idx) for idx in cut]
        tips = sorted(s["tips"] for s in stats)
        spans = sorted(s["span"] for s in stats)
        # Branches the base mesh must still carry: everything not inside a part.
        in_parts = sum(metrics["branches"][idx] for idx in cut)
        rows.append(
            {
                "diameter": diameter,
                "instances": len(cut),
                "base_branches": len(records) - in_parts,
                "tips_median": tips[len(tips) // 2],
                "tips_mean": sum(tips) / len(tips),
                "tips_max": tips[-1],
                "span_median": spans[len(spans) // 2],
                "span_max": spans[-1],
                "max_depth": max(s["max_depth"] for s in stats),
            }
        )
    return rows


def _descriptor(stats: dict[str, float]) -> list[float]:
    """Normalised shape descriptor used for prototype clustering.

    Log-scales the count and length terms because subtree sizes span orders of
    magnitude; up-alignment is already in [-1, 1].

    `twigs` is load-bearing, not decorative. A prototype is a SHARED mesh, so an
    instance renders its medoid's welded twigs rather than its own -- and without
    a foliage term the medoid search cannot separate a leafy subtree from a bare
    stub of the same shape. On a conifer, where 56.5% of cut subtrees carry no
    twigs at all, that put 5 of 7 medoids on bare stubs and left 88.7% of the
    crown rendering no needles (XRFF-386). Beech masked it: its stubs bear leaves.
    """
    return [
        math.log1p(stats.get("twigs", 0.0)),
        math.log1p(stats["tips"]),
        math.log1p(stats["total_length"]),
        math.log1p(stats["span"]),
        stats["up_alignment"],
        stats["max_depth"] / 5.0,
    ]

# The descriptor terms, in order, recorded in a stored library so a manifest
# read back later is self-describing.
DESCRIPTOR_TERMS = (
    "log1p(twigs)",
    "log1p(tips)",
    "log1p(total_length)",
    "log1p(span)",
    "up_alignment",
    "max_depth/5",
)


def descriptor_vectors(
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut: list[int],
    twig_totals: list[int] | None = None,
) -> tuple[list[dict[str, float]], list[list[float]]]:
    """Raw (un-normalised) descriptors for every cut point, with their stats."""
    stats = [subtree_stats(records, metrics, idx, twig_totals) for idx in cut]
    return stats, [_descriptor(s) for s in stats]


def apply_normalisation(
    vectors: list[list[float]], means: list[float], devs: list[float]
) -> list[list[float]]:
    return [[(v[d] - means[d]) / devs[d] for d in range(len(means))] for v in vectors]


def normalise_descriptors(
    vectors: list[list[float]],
) -> tuple[list[list[float]], list[float], list[float]]:
    """Standardise so no single descriptor term dominates the distance.

    The means and devs come back out because a stored part library has to
    record them: a tree assigned against a library must normalise with the
    BAKE-TIME statistics, not its own, or the same subtree lands on a different
    prototype depending only on which tree it was measured in (XRFF-389).
    """
    dims = len(vectors[0])
    means = [sum(v[d] for v in vectors) / len(vectors) for d in range(dims)]
    devs = []
    for d in range(dims):
        var = sum((v[d] - means[d]) ** 2 for v in vectors) / len(vectors)
        devs.append(math.sqrt(var) or 1.0)
    return apply_normalisation(vectors, means, devs), means, devs


def descriptor_distance(a: list[float], b: list[float]) -> float:
    """Squared euclidean distance -- only the ordering is ever used."""
    return sum((x - y) ** 2 for x, y in zip(a, b))


def cluster_prototypes(
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut: list[int],
    k: int,
    seed: int = 42,
    sample_size: int = 1500,
    twig_totals: list[int] | None = None,
) -> tuple[list[int], list[int], list[dict[str, float]]]:
    """k-medoids over the cut set. Returns (medoid branch ids, assignment, stats).

    Medoids rather than centroids: a prototype has to be an actual harvestable
    subtree, not an average of several.
    """
    import random

    stats, vectors = descriptor_vectors(records, metrics, cut, twig_totals)
    normed = normalise_descriptors(vectors)[0]

    dist = descriptor_distance

    k = min(k, len(normed))
    rng = random.Random(seed)

    # CLARA-style subsample: the medoid search is quadratic in the candidate
    # count, and a crown yields thousands of cut points. Medoids are searched
    # within a bounded sample; every candidate is still assigned to one.
    if len(normed) > sample_size:
        sample = rng.sample(range(len(normed)), sample_size)
    else:
        sample = list(range(len(normed)))
    pool = [normed[i] for i in sample]

    # k-means++ style seeding, then Voronoi iteration on medoids.
    #
    # The termination guard is load-bearing, not defensive. A crown's cut set is
    # dominated by near-identical single-tip stubs -- 60% of a beech's candidates
    # at cut 0.030 -- so the descriptor set routinely holds fewer distinct shapes
    # than the requested cluster count. Once every candidate coincides with a
    # chosen medoid, every weight is zero, no index ever satisfies `acc >= pick`,
    # and the loop spins forever with no output.
    medoids = [rng.randrange(len(pool))]
    while len(medoids) < k:
        far = [min(dist(v, pool[m]) for m in medoids) for v in pool]
        total = sum(far)
        if total <= 0.0:
            # Fewer distinct shapes than clusters asked for: returning the
            # distinct ones is the honest answer.
            break
        pick = rng.random() * total
        acc = 0.0
        for i, weight in enumerate(far):
            acc += weight
            if acc >= pick:
                medoids.append(i)
                break
        else:
            # Floating-point shortfall: `pick` landed past the accumulated sum.
            medoids.append(max(range(len(far)), key=lambda i: far[i]))

    pool_assignment = [0] * len(pool)
    for _ in range(50):
        for i, vec in enumerate(pool):
            pool_assignment[i] = min(
                range(len(medoids)), key=lambda c: dist(vec, pool[medoids[c]])
            )

        moved = False
        for c in range(len(medoids)):
            members = [i for i, a in enumerate(pool_assignment) if a == c]
            if not members:
                continue
            best = min(
                members,
                key=lambda m: sum(dist(pool[m], pool[o]) for o in members),
            )
            if best != medoids[c]:
                medoids[c] = best
                moved = True
        if not moved:
            break

    # Assign the full cut set against the chosen medoids.
    medoid_vectors = [pool[m] for m in medoids]
    assignment = [
        min(range(len(medoid_vectors)), key=lambda c: dist(vec, medoid_vectors[c]))
        for vec in normed
    ]

    # A leafy subtree must never take a twigless prototype, whatever the
    # descriptor distance says. The foliage term makes that rare, but it cannot
    # make it impossible: a conifer's cut set is bimodal -- 56.5% of a silver_fir's
    # subtrees carry no twigs at all -- so several medoids are legitimately bare,
    # and a lightly-foliaged subtree can still sit nearest one of them. Measured
    # before this guard, the four topmost cut points on a silver_fir all carried
    # twigs and all rendered bare, leaving the leader tip visibly naked while the
    # crown-wide average looked acceptable. Nearest LEAFY medoid instead: the
    # shape match degrades slightly, rendering nothing does not degrade, it fails.
    if twig_totals is not None:
        leafy = [c for c, m in enumerate(medoids) if twig_totals[cut[sample[m]]] > 0]
        if leafy:
            for i, branch in enumerate(cut):
                if (
                    twig_totals[branch] > 0
                    and not twig_totals[cut[sample[medoids[assignment[i]]]]]
                ):
                    assignment[i] = min(
                        leafy, key=lambda c: dist(normed[i], medoid_vectors[c])
                    )

    return [cut[sample[m]] for m in medoids], assignment, stats


def build_reference_model(grove: Any, quality: dict[str, Any] | None = None) -> Any:
    """Build the full-resolution model the bake cuts from.

    No `build_cutoff_thickness`: the harvester needs every branch and every
    twig present, because the cut it applies is its own.
    """
    options = {
        "resolution": 16,
        "resolution_reduce": 0.78,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.0,
        "build_blend": True,
        "build_end_cap": True,
    }
    options.update(quality or {})
    models = grove.build_models(options)
    if not models:
        raise SystemExit("build_models produced no models")
    return models[0]


def prepare_skeleton(
    grove: Any, quality: dict[str, Any] | None = None
) -> tuple[Any, list]:
    """Build skeletons and tag bone ids, in the order Grove requires.

    `build_skeletons` -> `tag_bone_id` -> `build_models`. Called out of line
    because the ordering is load-bearing: `point_attribute_bone_id` only
    carries real bone ids on a model built *after* tagging, and the compound
    base mesh needs them to export skeletal (XRFF-366).
    """
    params = quality or {}
    connected = params.get("skeleton_connected", True)
    skeletons = grove.build_skeletons(connected)
    bones = grove.tag_bone_id(
        params.get("skeleton_length", 2.0),
        params.get("skeleton_reduce", 0.4) ** 2,  # squared, as Grove's UI does
        params.get("skeleton_bias", 0.5),
        connected,
    )
    return (skeletons[0] if skeletons else None), bones


def export_base_mesh(
    model: Any,
    records: list[BranchRecord],
    cut: list[int],
    output_path: Path,
    species: str,
    skeleton: Any = None,
    bones_info: list | None = None,
    tree_id: str = "compound",
) -> dict[str, Any]:
    """Write the stems USD as the exact complement of the harvested parts.

    XRFF-362. Deriving it from `build_cutoff_thickness` instead leaves two
    meshes describing different trees -- at cut diameter 0.030 Grove's cutoff
    keeps 19 branches of 11,685, so 96.2% of parts land more than 2 cm from any
    surviving geometry and visibly float. The inverse face mask is complementary
    by construction.
    """
    from growpy.core.skeleton import filter_bones_for_mesh
    from growpy.io.usd.compound_part_export import (
        ComplementModel,
        harvested_branch_ids,
    )
    from growpy.io.usd.tree_export import build_tree_mesh

    children = [rec.children for rec in records]
    part_ids = harvested_branch_ids(children, cut)
    base = ComplementModel(model, part_ids)
    base.triangulate()

    # `build_tree_mesh` drops bones no base-mesh vertex references and RENUMBERS
    # the survivors, so a raw Grove bone id is not an index into the authored
    # joint list. Recompute the same map here and hand it back: the assembly's
    # bindJoints are indices into exactly this list, and an id past its end makes
    # UE discard the whole PointInstancer (XRFF-384/385).
    bone_map: dict[int, int] = {}
    if bones_info:
        _, bone_map = filter_bones_for_mesh(base, bones_info, 0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok = build_tree_mesh(
        model=base,
        skeleton=skeleton,
        bones_info=bones_info,
        output_path=output_path,
        up_axis="Z",
        include_skeleton=skeleton is not None,
        species_name=species,
        tree_id=tree_id,
    )
    if not ok:
        raise SystemExit(f"base mesh export failed: {output_path}")

    return {
        "file": str(output_path),
        "file_bytes": output_path.stat().st_size,
        "points": len(base.points),
        "faces": len(base.faces),
        "dropped_faces": base.dropped_faces,
        "branches_in_parts": len(part_ids),
        "branches_in_base": len(set(base.face_attribute_branch_id)),
        "skeletal": skeleton is not None,
        "bone_map": bone_map,
        "joints": len(bone_map),
    }


def cut_point_bone_ids(
    model: Any, cut: list[int], bone_map: dict[int, int] | None = None
) -> dict[int, int]:
    """Majority-vote a bone id for each cut branch from its own vertices.

    `assembly_export` uses `TwigPlacement.bone_id` as a direct index into the
    stems skeleton's joint names, and that is what puts an instance on a bone
    the wind system drives (XRFF-366). `extract_twig_placements_from_model`
    derives it for an ordinary twig by voting `point_attribute_bone_id` over the
    twig marker face's vertices; a compound part replaces a whole subtree, so
    the vote runs over the cut branch's own faces instead.

    Requires a model built AFTER `tag_bone_id` -- see `prepare_skeleton`.

    `bone_map` is `export_base_mesh`'s old-to-new bone map. It is not optional in
    practice: the vote runs over the FULL model, but the joint list is authored
    from the BASE mesh, which drops every bone no surviving vertex references and
    renumbers the rest. On an 18-cycle silver_fir that is one bone of 31, and
    passing the raw ids through puts 15 of 708 placements past the end of a
    30-joint list -- enough for UE to discard the entire PointInstancer and build
    no assembly at all (XRFF-384/385). Where the winning bone did not survive,
    fall back to the best-voted bone that did rather than dropping the placement.
    """
    bone_ids = getattr(model, "point_attribute_bone_id", None)
    if not bone_ids:
        return {}

    wanted = {branch + 1: branch for branch in cut}
    faces = model.faces
    face_branch_ids = model.face_attribute_branch_id

    votes: dict[int, dict[int, int]] = {branch: {} for branch in cut}
    for face_index, face in enumerate(faces):
        branch = wanted.get(face_branch_ids[face_index])
        if branch is None:
            continue
        tally = votes[branch]
        for index in face:
            if index < len(bone_ids):
                bone = bone_ids[index]
                tally[bone] = tally.get(bone, 0) + 1

    if bone_map is None:
        return {
            branch: max(tally, key=tally.get)
            for branch, tally in votes.items()
            if tally
        }

    resolved: dict[int, int] = {}
    for branch, tally in votes.items():
        survivors = {b: n for b, n in tally.items() if b in bone_map}
        if survivors:
            resolved[branch] = bone_map[max(survivors, key=survivors.get)]
    return resolved


def residual_twig_placements(
    model: Any,
    records: list[BranchRecord],
    cut: list[int],
    bones_info: list | None = None,
    bone_map: dict[int, int] | None = None,
) -> dict[str, list]:
    """Grove's own twigs on the branches the base mesh KEEPS (XRFF-392).

    A compound part renders the foliage of the subtree it replaces, so a twig
    whose branch was never harvested is rendered by NOTHING: the base mesh drops
    every twig marker face -- a surviving marker quad reads as a stray flat quad
    under a real part -- and no part covers it.

    Measured on an 18-cycle silver_fir that is 58 of 3,204 living twigs. 1.8%
    sounds ignorable, and is not: they sit on the trunk and the leader, which
    `find_cut_set_adaptive` can never harvest because it requires
    ``rec.parent >= 0`` and a Grove trunk is ONE branch record. Eleven of the 58
    are in the top metre and one is the single upward twig, which is the bare
    apex you can see on every compound fir.

    They are placed 1:1 from the ordinary twig prototype, at Grove's own
    positions and orientations -- the same asset and the same frames the
    non-compound path uses.

    Dead twigs are left out: `create_assembly` has no dead-twig asset to place
    them with and skips them on the 1:1 path too.
    """
    from growpy.core.twig import extract_twig_placements_from_model
    from growpy.io.usd.compound_part_export import harvested_branch_ids

    twig_types = list(LIVING_TWIG_TYPES)
    children = [rec.children for rec in records]
    in_parts = harvested_branch_ids(children, cut)

    # Filter on the RAW `face_attribute_branch_id`, never on
    # `TwigPlacement.branch_id`. `harvested_branch_ids` speaks Grove's face
    # attribute, which is `walker_index + 1`; a placement's `branch_id` has had
    # `bones_info[0][7]` subtracted from that to turn forest-global ids into
    # per-tree local ones. The harvester grows one tree, so today that offset
    # is zero and the two happen to coincide -- which is exactly what makes the
    # substitution attractive and wrong. `subtree_branch_ids` warns against it
    # in its own docstring.
    branch_of_face = model.face_attribute_branch_id
    attrs = {t: getattr(model, f"face_attribute_{t}") for t in twig_types}
    branch_by_type: dict[str, list[int]] = {t: [] for t in twig_types}
    for face_idx in range(len(branch_of_face)):
        for twig_type in twig_types:
            if attrs[twig_type][face_idx]:
                # One type per face, the same assumption the extractor makes.
                branch_by_type[twig_type].append(branch_of_face[face_idx])
                break

    everything = extract_twig_placements_from_model(
        model,
        twig_types=twig_types,
        bones_info=bones_info,
    )

    residual: dict[str, list] = {}
    for twig_type, items in everything.items():
        branches = branch_by_type[twig_type]
        if len(branches) != len(items):
            # Both walk the faces in the same order for the same types, so a
            # mismatch means that assumption broke. Placing on a shifted
            # correspondence would scatter twigs across the wrong branches.
            raise SystemExit(
                f"{twig_type}: {len(branches)} marker faces against "
                f"{len(items)} extracted placements -- face order no longer "
                "lines up, so residual twigs cannot be matched to branches"
            )
        kept = []
        for placement, branch in zip(items, branches, strict=True):
            if branch in in_parts:
                continue
            # One prototype per type, so index 0 -- and it must be explicit or
            # `assembly_export` draws at random (XRFF-365).
            placement.prototype = 0
            if bone_map is not None:
                placement.bone_id = (
                    bone_map.get(placement.bone_id)
                    if placement.bone_id is not None
                    else None
                )
            kept.append(placement)
        if kept:
            residual[twig_type] = kept

    return residual


def residual_twig_asset(twig_usd: Path, skeletal: bool) -> Path:
    """The twig prototype variant a compound assembly of this kind can place.

    `--twig-usd` names the STATIC twig, because that is what `bake_prototypes`
    welds. A skeletal assembly handed a static prototype does not fail: UE logs
    "Failed to find Skeletal Mesh asset for PointInstancer prototype" and
    silently builds no assembly at all (F2, XRFF-366). So resolve the sibling
    rather than pass the static one through.
    """
    if not skeletal or "_skeletal" in twig_usd.stem:
        return twig_usd
    sibling = twig_usd.with_name(twig_usd.name.replace("_static", "_skeletal"))
    if not sibling.is_file():
        raise SystemExit(
            f"a skeletal assembly needs a skeletal twig prototype for the "
            f"residual twigs, and {sibling.name} is not beside {twig_usd.name}"
        )
    return sibling


def export_compound_assembly(
    stems_usd: Path,
    output_path: Path,
    records: list[BranchRecord],
    cut: list[int],
    assignment: list[int],
    prototype_paths: list[Path],
    species: str,
    bone_ids: dict[int, int] | None = None,
    tree_id: str = "compound",
    use_skeletal_mesh: bool = True,
    instances_dir: Path | None = None,
    max_instances: int = 0,
    residual_twig_usd: dict[str, Path] | None = None,
    model: Any = None,
    bones_info: list | None = None,
    bone_map: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Place one baked part per cut point and write the assembly USD.

    The part is authored base-at-origin along +X, the same frame Grove's twig
    quaternion assumes, so the placement quaternion is built from the cut
    branch's own direction.

    Each placement carries its cluster assignment rather than letting
    `assembly_export` draw a prototype at random: compound prototypes span 51 to
    139,500 faces, so a random draw both mismatches the branch and inflates the
    flattened fallback total to instances x MEAN (XRFF-365).

    With `residual_twig_usd` and `model` the assembly is HYBRID, which is what
    it was always meant to be: compound parts stand in for the subtrees the base
    mesh gave up, and Grove's own twigs are placed 1:1 wherever the base mesh
    kept the branch they grew on. Without them the crown is missing every twig
    on the trunk and the leader -- see `residual_twig_placements`.
    """
    from growpy.core.twig import TwigPlacement
    from growpy.io.usd.assembly_export import create_assembly
    from growpy.io.usd.compound_part_export import placement_quat_for_direction

    bone_ids = bone_ids or {}
    placed = list(range(len(cut)))
    if max_instances and len(cut) > max_instances:
        # An even subsample rather than a prefix: the cut set is in walker
        # order, so a prefix would take one side of the crown.
        step = len(cut) / max_instances
        placed = [int(i * step) for i in range(max_instances)]

    # Keyed by what they are, not by a grove twig type: these are compound
    # parts, and the residual twigs below keep their real types alongside them.
    twig_usd_paths: dict[str, list[Path]] = {"compound_part": list(prototype_paths)}
    placements: dict[str, list] = {
        "compound_part": [
            TwigPlacement(
                type="compound_part",
                position=records[cut[i]].base_pos,
                normal=records[cut[i]].base_dir,
                orientation=placement_quat_for_direction(records[cut[i]].base_dir),
                scale=1.0,
                bone_id=bone_ids.get(cut[i]),
                prototype=assignment[i],
            )
            for i in placed
        ]
    }

    residual_total = 0
    if residual_twig_usd and model is not None:
        assets = {
            twig_type: residual_twig_asset(path, use_skeletal_mesh)
            for twig_type, path in residual_twig_usd.items()
        }
        for twig_type, items in residual_twig_placements(
            model, records, cut, bones_info, bone_map
        ).items():
            asset = assets.get(twig_type)
            if asset is None:
                continue
            # One asset per type, and `create_assembly` dedups prototypes by
            # filename, so types sharing a variant share one prototype index.
            twig_usd_paths[twig_type] = [asset]
            placements[twig_type] = items
            residual_total += len(items)
        logger.info(
            "residual twigs: %d placed 1:1 across %d type(s): %s",
            residual_total,
            len(placements) - 1,
            ", ".join(
                f"{twig_type}={twig_usd_paths[twig_type][0].name}"
                for twig_type in LIVING_TWIG_TYPES
                if twig_type in placements
            ),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok = create_assembly(
        stems_usd,
        output_path,
        species,
        tree_id=tree_id,
        twig_usd_paths=twig_usd_paths,
        use_skeletal_mesh=use_skeletal_mesh,
        twig_placements=placements,
        validate=False,
        instances_dir=instances_dir,
    )
    if not ok:
        raise SystemExit(f"assembly export failed: {output_path}")

    # Preflight before the file can reach UE: a dangling reference writes fine,
    # opens fine in pxr, and then crashes the editor inside the Nanite
    # hierarchy encoder (XRFF-367).
    from growpy.tools.preflight_assembly import check_assembly, log_report

    report = check_assembly(output_path)
    log_report(report)
    if report["errors"]:
        raise SystemExit(
            f"{output_path.name}: {len(report['errors'])} unresolved "
            "reference(s) -- do NOT import this, it will crash the editor"
        )

    return {
        "flattened_triangles": report["flattened_triangles"],
        "file": str(output_path),
        "file_bytes": output_path.stat().st_size,
        "instances": len(placed) + residual_total,
        "parts": len(placed),
        "residual_twigs": residual_total,
        "prototypes": len(prototype_paths),
        "skeletal": use_skeletal_mesh,
        "bound_instances": sum(1 for i in placed if bone_ids.get(cut[i]) is not None),
    }


def bake_prototypes(
    model: Any,
    records: list[BranchRecord],
    metrics: dict[str, list],
    medoids: list[int],
    twig_usd: dict[str, Path],
    output_dir: Path,
    species: str,
    include_twig_marker_faces: bool = False,
) -> list[dict[str, Any]]:
    """Bake each medoid subtree into one welded USD prototype.

    Steps 5-7 of XRFF-357: normalise, weld woody mesh + leaves into a single
    mesh (Nanite Assemblies cannot nest), and emit into the prototype slot so
    downstream naming and material wiring are unchanged.

    The leaves come from the ALREADY-CONVERTED twig USD -- densified, alpha
    contour cut and planar dissolved by `growpy-convert-twigs`. That ordering
    is required, not incidental: the contour cut needs each leaf's own alpha
    texture and UVs, and once N twigs share one welded mesh that association is
    gone. Welding is strictly the last step. See XRFF-359 for the coarser
    conversion profile a compound-bound twig should be converted at.

    `twig_usd` maps each of Grove's living twig types to the variant welded at
    its placements, so a size ladder reaches the crown the way Grove itself
    varies foliage -- twig_long at the branch tips and through the upper crown,
    twig_short mid-branch, twig_upward at the apex (see LIVING_TWIG_TYPES).
    Every variant of one twig asset shares its textures, so the material comes
    from a single member of the map.
    """
    # Absolute, not relative: this tool is run as a script
    # (`python src/growpy/tools/harvest_compound_parts.py`), where a relative
    # import has no parent package.
    from growpy.io.usd.compound_part_export import (
        extract_subtree_mesh,
        load_prototype_mesh,
        merge_mesh,
        normalise_part_frame,
        subtree_branch_ids,
        write_compound_part_usd,
    )

    # Every one of these is a property that rebuilds its whole list per access.
    faces = model.faces
    points = model.points
    uvs = model.uvs
    face_branch_ids = model.face_attribute_branch_id
    long_ = model.face_attribute_twig_long
    short = model.face_attribute_twig_short
    upward = model.face_attribute_twig_upward
    dead = model.face_attribute_twig_dead
    twig_locations = model.get_twig_locations()
    twig_orientations = model.get_twig_orientations()

    face_count = len(faces)
    twig_mask = [
        bool(long_[i] or short[i] or upward[i] or dead[i]) for i in range(face_count)
    ]

    # Grove's living-twig arrays are indexed by position in face order, the
    # same coupling `extract_twig_placements_from_model` relies on.
    twig_index_of_face: dict[int, int] = {}
    twig_type_of_face: dict[int, str] = {}
    twig_index = 0
    for i in range(face_count):
        if long_[i] or short[i] or upward[i]:
            twig_index_of_face[i] = twig_index
            twig_type_of_face[i] = (
                "twig_long" if long_[i] else "twig_short" if short[i] else "twig_upward"
            )
            twig_index += 1

    children = [rec.children for rec in records]
    # One load per DISTINCT file: several types usually name the same variant.
    meshes: dict[Path, Any] = {}
    for path in twig_usd.values():
        if path not in meshes:
            meshes[path] = load_prototype_mesh(path)
    leaves = {twig_type: meshes[path] for twig_type, path in twig_usd.items()}
    material_source = twig_usd[LIVING_TWIG_TYPES[0]]
    output_dir.mkdir(parents=True, exist_ok=True)

    report: list[dict[str, Any]] = []
    for slot, branch in enumerate(medoids):
        ids = subtree_branch_ids(children, branch)
        part = extract_subtree_mesh(
            faces,
            points,
            uvs,
            face_branch_ids,
            ids,
            twig_face_mask=None if include_twig_marker_faces else twig_mask,
            material=f"{species}_bark",
        )
        woody_faces = len(part.faces)

        welded = 0
        welded_by_type: dict[str, int] = {}
        for i in range(face_count):
            if face_branch_ids[i] not in ids:
                continue
            index = twig_index_of_face.get(i)
            if index is None:
                continue
            twig_type = twig_type_of_face[i]
            base = index * 3
            quat = index * 4
            merge_mesh(
                part,
                leaves[twig_type],
                translation=(
                    twig_locations[base],
                    twig_locations[base + 1],
                    twig_locations[base + 2],
                ),
                rotation=(
                    twig_orientations[quat],
                    twig_orientations[quat + 1],
                    twig_orientations[quat + 2],
                    twig_orientations[quat + 3],
                ),
            )
            welded += 1
            welded_by_type[twig_type] = welded_by_type.get(twig_type, 0) + 1

        rec = records[branch]
        quat = normalise_part_frame(part, rec.base_pos, rec.base_dir)
        name = f"{species}_compound_p{slot:02d}"
        path = write_compound_part_usd(
            part,
            output_dir / f"{name}_static.usda",
            part_name=name,
            material_source=material_source,
            bark_species=species,
        )
        # Both variants, as the twig pipeline ships: a SKELETAL assembly needs
        # skeletal prototypes -- handed static ones UE logs "Failed to find
        # Skeletal Mesh asset for PointInstancer prototype" and builds no
        # assembly at all -- while the static one is what OBJ/Helios export and
        # a static assembly consume (XRFF-366).
        skeletal_path = write_compound_part_usd(
            part,
            output_dir / f"{name}_skeletal.usda",
            part_name=name,
            material_source=material_source,
            bark_species=species,
            skeletal=True,
        )
        lo, hi = part.bounds()
        stats = subtree_stats(records, metrics, branch)
        report.append(
            {
                "prototype": slot,
                "name": name,
                "branch": branch,
                "file": str(path),
                "skeletal_file": str(skeletal_path),
                "file_bytes": path.stat().st_size,
                "points": len(part.points),
                "faces": len(part.faces),
                "woody_faces": woody_faces,
                "welded_twigs": welded,
                "welded_twigs_by_type": welded_by_type,
                "materials": list(part.materials),
                "normalise_quat_wxyz": list(quat),
                "local_extent": [hi[a] - lo[a] for a in range(3)],
                "tips": stats["tips"],
                "span": stats["span"],
                "total_length": stats["total_length"],
                "up_alignment": stats["up_alignment"],
            }
        )

    return report


# Bumped when the descriptor or the manifest layout changes in a way that would
# make an older library.json assign a tree WRONGLY rather than merely
# differently -- an assignment computed against stale means/devs is silently
# plausible, so the mismatch has to be refused rather than tolerated.
LIBRARY_SCHEMA = 2


def write_part_library(
    output_dir: Path,
    species: str,
    report: list[dict[str, Any]],
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut: list[int],
    twig_totals: list[int] | None,
    package_root: str,
    source: dict[str, Any],
    skeletal: bool = True,
    residual_twig_usd: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Bake the species part library and the manifest later trees assign against.

    Two artefacts, both required by XRFF-389:

    * ONE USD stage referencing every part, because parts imported as separate
      tasks do not share materials -- four separately-imported parts produced
      five material slots where the single stage produced two (F24);
    * ``<species>_library.json``, recording each prototype's UE package path,
      the foliage it actually carries and its NORMALISED descriptor, alongside
      the bake-time ``means``/``devs``. All three are load-bearing: the
      descriptor's first term is a twig count (XRFF-386), the leafy-prototype
      guard needs the foliage (XRFF-387), and a tree that normalised against
      its own cut set would land the same subtree on a different prototype.

    The recorded foliage is ``welded_twigs`` -- what the baked part actually
    holds -- not the source subtree's twig total. They usually agree, and where
    they do not it is the part that renders.

    `residual_twig_usd` maps each living twig type to the variant its residual
    1:1 twigs are placed from, and every DISTINCT variant joins the library as
    an ordinary member. A hybrid assembly instances those twigs alongside the
    compound parts, so each needs a package path exactly as they do, and they
    belong in the same stage for the same material-sharing reason.
    """
    import shutil

    from growpy.io.usd.extref_assembly import (
        library_package_path,
        write_part_library_usd,
    )

    key = "skeletal_file" if skeletal else "file"
    members = [(row["name"], Path(row[key])) for row in report]

    residual: list[dict[str, Any]] = []
    if residual_twig_usd:
        for twig_type in LIVING_TWIG_TYPES:
            path = residual_twig_usd.get(twig_type)
            if path is None:
                continue
            twig_source = residual_twig_asset(path, skeletal)
            # The library references its members relatively, so the twig has to
            # sit beside it. Its textures are already staged: `bake_prototypes`
            # copies the whole `textures/` of this same twig next to the parts.
            twig_local = output_dir / twig_source.name
            if not twig_local.exists():
                shutil.copy2(twig_source, twig_local)
            if any(entry["file"] == twig_local.name for entry in residual):
                # Types sharing a variant share one library member.
                continue
            twig_name = twig_local.stem.replace("_skeletal", "").replace("_static", "")
            members.append((twig_name, twig_local))
            residual.append(
                {
                    "name": twig_name,
                    "file": twig_local.name,
                    "package_path": "",
                }
            )

    library_usd = write_part_library_usd(
        members, output_dir / f"{species}_library.usda"
    )
    for entry in residual:
        entry["package_path"] = library_package_path(
            package_root, library_usd.stem, entry["name"]
        )

    # Recomputed rather than threaded out of `cluster_prototypes`: the inputs
    # are identical and the computation deterministic, and widening a 3-tuple
    # that a dozen call sites already unpack is not worth it for this.
    vectors = descriptor_vectors(records, metrics, cut, twig_totals)[1]
    normed, means, devs = normalise_descriptors(vectors)
    position = {branch: i for i, branch in enumerate(cut)}

    prototypes = [
        {
            "id": row["prototype"],
            "name": row["name"],
            "branch": row["branch"],
            "package_path": library_package_path(
                package_root, library_usd.stem, row["name"]
            ),
            # The variant the assembly actually references, which is what an
            # external-ref rewrite keys its package paths by.
            "file": Path(row[key]).name,
            "skeletal_file": Path(row["skeletal_file"]).name,
            "static_file": Path(row["file"]).name,
            "twigs": row["welded_twigs"],
            "faces": row["faces"],
            "descriptor": normed[position[row["branch"]]],
        }
        for row in report
    ]

    library = {
        "schema": LIBRARY_SCHEMA,
        "species": species,
        "source": source,
        "library_usd": library_usd.name,
        "package_root": package_root.rstrip("/"),
        "skeletal": skeletal,
        "descriptor": {
            "terms": list(DESCRIPTOR_TERMS),
            "means": means,
            "devs": devs,
            "cut_points": len(cut),
        },
        "prototypes": prototypes,
        "residual_twigs": residual,
    }
    manifest_path = output_dir / f"{species}_library.json"
    manifest_path.write_text(json.dumps(library, indent=2))
    logger.info(
        "part library: %d prototypes%s under %s -> %s",
        len(prototypes),
        f" + {len(residual)} 1:1 twig variant(s)" if residual else "",
        library["package_root"],
        manifest_path.name,
    )
    library["path"] = str(manifest_path)
    return library


def library_asset_paths(library: dict[str, Any]) -> dict[str, str]:
    """Prototype filename -> UE package path, for an external-ref rewrite."""
    paths = {p["file"]: p["package_path"] for p in library["prototypes"]}
    for entry in library.get("residual_twigs") or []:
        paths[entry["file"]] = entry["package_path"]
    return paths


def load_part_library(path: Path) -> dict[str, Any]:
    library = json.loads(path.read_text())
    if library.get("schema") != LIBRARY_SCHEMA:
        raise SystemExit(
            f"{path}: library schema {library.get('schema')!r}, "
            f"expected {LIBRARY_SCHEMA} -- re-bake it"
        )
    library["path"] = str(path)
    return library


def assign_against_library(
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut: list[int],
    twig_totals: list[int] | None,
    library: dict[str, Any],
) -> list[int]:
    """Nearest stored prototype for every cut point (XRFF-358, XRFF-389).

    `cluster_prototypes` derives medoids and assignment together from one tree.
    This is the other half, and the half that makes a library shareable: a tree
    assigned against prototypes baked from a DIFFERENT tree. It normalises with
    the library's bake-time statistics, never its own.
    """
    means = library["descriptor"]["means"]
    devs = library["descriptor"]["devs"]
    prototypes = library["prototypes"]
    medoids = [p["descriptor"] for p in prototypes]

    vectors = descriptor_vectors(records, metrics, cut, twig_totals)[1]
    normed = apply_normalisation(vectors, means, devs)
    assignment = [
        min(range(len(medoids)), key=lambda c: descriptor_distance(vec, medoids[c]))
        for vec in normed
    ]

    # The same guard `cluster_prototypes` applies, but against the prototype's
    # MEASURED foliage rather than its source subtree's: a part with no welded
    # twigs renders nothing whatever its descriptor promised (XRFF-387).
    if twig_totals is not None:
        leafy = [c for c, p in enumerate(prototypes) if p["twigs"] > 0]
        if leafy:
            for i, branch in enumerate(cut):
                if twig_totals[branch] > 0 and not prototypes[assignment[i]]["twigs"]:
                    assignment[i] = min(
                        leafy,
                        key=lambda c: descriptor_distance(normed[i], medoids[c]),
                    )
    return assignment


def grow_grove(species: str, cycles: int, seed: int) -> Any:
    """Simulate one reference tree headless via the_grove_23_core."""
    import the_grove_23_core as gc

    preset_path = Path("data/assets/presets") / f"{species}.seed.json"
    if not preset_path.is_file():
        raise SystemExit(f"preset not found: {preset_path}")

    preset = json.loads(preset_path.read_text())
    grove = gc.Grove()
    grove.clear_trees()
    grove.set_random_seed(seed)
    grove.set_properties(gc.io.properties_from_json_string(json.dumps(preset)))
    grove.clear_trees()
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    grove.simulate(cycles)

    if not grove.trees:
        raise SystemExit(f"{species}: simulation produced no trees")
    return grove


def grow_tree(species: str, cycles: int, seed: int) -> Any:
    """Grow one reference tree headless via the_grove_23_core."""
    return grow_grove(species, cycles, seed).trees[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harvest compound foliage part candidates from a Grove tree."
    )
    parser.add_argument("species", help="preset stem, e.g. european_beech")
    parser.add_argument("--cycles", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="report instance count per cut diameter instead of clustering",
    )
    parser.add_argument(
        "--sweep-band",
        action="store_true",
        help="sweep the part size band at a fixed cut diameter",
    )
    parser.add_argument(
        "--cut-diameter",
        type=float,
        default=0.020,
        help="branch base diameter (m) at which to cut (default 0.020)",
    )
    parser.add_argument("--max-tips", type=int, default=DEFAULT_MAX_TIPS)
    parser.add_argument("--max-span", type=float, default=DEFAULT_MAX_SPAN)
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="use the plain diameter cut, ignoring the part size band",
    )
    parser.add_argument("--clusters", type=int, default=7)
    parser.add_argument("--json", type=Path, help="write the part manifest here")
    parser.add_argument(
        "--max-twigs",
        type=int,
        default=DEFAULT_MAX_TWIGS,
        help=(
            "living twigs one part may carry -- the bound that actually decides "
            f"its face count (default {DEFAULT_MAX_TWIGS}). Requires a built "
            "model, so it is applied for --bake and ignored by the sweeps."
        ),
    )
    parser.add_argument(
        "--bake",
        type=Path,
        help="bake the prototype medoids into welded USD parts in this directory",
    )
    parser.add_argument(
        "--twig-usd",
        type=Path,
        help=(
            "already-converted static twig USD to weld as the leaves "
            "(e.g. data/output/forest/Instances/european_beech_foliage_a_static.usda)"
        ),
    )
    for twig_type in LIVING_TWIG_TYPES:
        parser.add_argument(
            f"--twig-usd-{twig_type.removeprefix('twig_')}",
            type=Path,
            help=(
                f"twig USD for Grove's {twig_type} placements, overriding "
                "--twig-usd. Grove carries no per-twig scale, so its types are "
                "where a size ladder is applied: twig_long sits at the branch "
                "TIPS and dominates the upper crown, twig_short mid-branch, "
                "twig_upward at the apex"
            ),
        )
    parser.add_argument(
        "--base-mesh",
        type=Path,
        help=(
            "write the stems USD as the complement of the harvested parts "
            "(XRFF-362) -- every branch NOT inside a part, not a "
            "build_cutoff_thickness product"
        ),
    )
    parser.add_argument(
        "--skeletal",
        action="store_true",
        help="export the base mesh and assembly skeletal, not static (XRFF-366)",
    )
    parser.add_argument(
        "--assembly",
        type=Path,
        help=(
            "write the Nanite Assembly here, placing one baked part per cut "
            "point. Requires --base-mesh, plus --bake or --assign-from-library."
        ),
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        default=0,
        help=(
            "cap the assembly's instance count by even subsample. UE flattens "
            "instances x part triangles to build the Nanite fallback, and that "
            "total is what governs import time (XRFF-364). 0 places them all."
        ),
    )
    parser.add_argument(
        "--library",
        action="store_true",
        help=(
            "also bake the one-stage part library and its manifest into the "
            "--bake directory, so other trees can name the parts by UE package "
            "path instead of embedding a copy each (XRFF-389). The parts must "
            "sit beside the library stage, which is why this is a flag on "
            "--bake rather than its own directory."
        ),
    )
    parser.add_argument(
        "--library-package",
        default="/Game/CompoundLib",
        help=(
            "UE content folder the library stage will be imported into. The "
            "part package paths in an external-ref assembly are derived from "
            "it, and a wrong one yields an assembly with no parts and an "
            "import that still reports success (default /Game/CompoundLib)"
        ),
    )
    parser.add_argument(
        "--extref-assembly",
        type=Path,
        help=(
            "also write the assembly in external-ref form, naming the parts by "
            "UE package path instead of embedding them. Requires --assembly "
            "and a library (--library or --assign-from-library), and must be "
            "written to the same directory as --assembly."
        ),
    )
    parser.add_argument(
        "--assign-from-library",
        type=Path,
        help=(
            "assign this tree's cut set against an already-baked "
            "<species>_library.json and take the prototypes from there, "
            "instead of clustering and baking this tree's own. Replaces --bake."
        ),
    )
    parser.add_argument(
        "--no-residual-twigs",
        action="store_true",
        help=(
            "place ONLY compound parts. By default the assembly is hybrid: "
            "Grove's own twigs are also placed 1:1 wherever the base mesh kept "
            "the branch they grew on, because a compound part renders only the "
            "foliage of the subtree it replaced and the trunk and the leader "
            "are never harvested (XRFF-392)."
        ),
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Grove's living twig types map to the variant welded into a part and
    # placed at that type's residual 1:1 positions. Without an override every
    # type takes --twig-usd, which is the single-asset behaviour this tool had.
    twig_usd_by_type: dict[str, Path] = {}
    for twig_type in LIVING_TWIG_TYPES:
        override = getattr(args, f"twig_usd_{twig_type.removeprefix('twig_')}")
        path = override or args.twig_usd
        if path is not None:
            twig_usd_by_type[twig_type] = path
    if len(set(twig_usd_by_type.values())) > 1:
        logger.info(
            "twig ladder: %s",
            ", ".join(f"{t}={p.name}" for t, p in twig_usd_by_type.items()),
        )

    adaptive = not args.no_adaptive
    grove = grow_grove(args.species, args.cycles, args.seed)
    tree = grove.trees[0]
    records = flatten_branches(tree)
    metrics = precompute_subtrees(records)

    # The twig band and the base mesh both need a built model.
    model = None
    twig_totals = None
    skeleton = None
    bones_info = None
    if args.assign_from_library and args.bake:
        raise SystemExit("--assign-from-library replaces --bake, it does not add to it")
    if args.assembly and not args.base_mesh:
        raise SystemExit("--assembly requires --base-mesh")
    if args.assembly and not (args.bake or args.assign_from_library):
        raise SystemExit("--assembly requires --bake or --assign-from-library")
    if args.extref_assembly:
        if not args.assembly:
            raise SystemExit("--extref-assembly requires --assembly")
        if not (args.library or args.assign_from_library):
            raise SystemExit(
                "--extref-assembly names parts by package path, so it requires "
                "--library (bake one) or --assign-from-library (reuse one)"
            )
    if args.library and not args.bake:
        raise SystemExit("--library requires --bake")
    if args.bake or args.base_mesh or args.assign_from_library:
        if args.bake and args.twig_usd is None:
            raise SystemExit("--bake requires --twig-usd")
        for path in dict.fromkeys(twig_usd_by_type.values()):
            if not path.is_file():
                raise SystemExit(f"twig USD not found: {path}")
        if args.skeletal:
            # Before build_models, or point_attribute_bone_id carries nothing.
            skeleton, bones_info = prepare_skeleton(grove)
            logger.info("skeleton: %d bones tagged", len(bones_info))
        model = build_reference_model(grove)
        twig_totals = count_subtree_twigs(model, records)
        logger.info(
            "reference model: %d living twigs across %d branches",
            twig_totals[0],
            len(records),
        )

    residual_twig_usd = None if args.no_residual_twigs else twig_usd_by_type
    if args.assembly and not residual_twig_usd:
        raise SystemExit(
            "--assembly needs --twig-usd for the residual 1:1 twigs, or "
            "--no-residual-twigs to place compound parts alone"
        )
    height = max(r.base_pos[2] for r in records)
    logger.info(
        "%s: %d cycles -> %d branches, %d nodes, %.1f m tall (dbh proxy %.0f mm)",
        args.species,
        args.cycles,
        len(records),
        sum(r.node_count for r in records),
        height,
        records[0].base_radius * 2000,
    )
    if adaptive:
        logger.info(
            "adaptive cut: part band <= %d tips, <= %.2f m span",
            args.max_tips,
            args.max_span,
        )

    if args.sweep_band:
        logger.info(
            "\n%-10s %-10s %-10s %-9s %-10s %-9s %s",
            "max span",
            "max tips",
            "instances",
            "base br.",
            "tips/part",
            "span med",
            "depth",
        )
        for max_span in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
            row = sweep_cut_diameters(
                records,
                metrics,
                (args.cut_diameter,),
                True,
                args.max_tips,
                max_span,
            )[0]
            if not row.get("instances"):
                continue
            logger.info(
                "%-10.1f %-10d %-10d %-9d %-10.1f %-9.2f %d",
                max_span,
                args.max_tips,
                row["instances"],
                row["base_branches"],
                row["tips_mean"],
                row["span_median"],
                row["max_depth"],
            )
        return

    if args.sweep:
        rows = sweep_cut_diameters(
            records, metrics, DEFAULT_SWEEP, adaptive, args.max_tips, args.max_span
        )
        logger.info(
            "\n%-9s %-10s %-9s %-10s %-9s %-10s %-9s %s",
            "cut d(m)",
            "instances",
            "base br.",
            "tips/part",
            "max tips",
            "span med",
            "span max",
            "depth",
        )
        for row in rows:
            if not row.get("instances"):
                continue
            logger.info(
                "%-9.3f %-10d %-9d %-10.1f %-9d %-10.2f %-9.2f %d",
                row["diameter"],
                row["instances"],
                row["base_branches"],
                row["tips_mean"],
                row["tips_max"],
                row["span_median"],
                row["span_max"],
                row["max_depth"],
            )
        best = min(
            (r for r in rows if r.get("instances")),
            key=lambda r: abs(r["instances"] - TARGET_INSTANCES),
            default=None,
        )
        if best:
            logger.info(
                "\nclosest to the %d-instance MegaPlants budget: "
                "cut diameter %.3f m -> %d instances carrying ~%.0f tips each, "
                "leaving %d branches in the base mesh",
                TARGET_INSTANCES,
                best["diameter"],
                best["instances"],
                best["tips_mean"],
                best["base_branches"],
            )
        return

    if adaptive:
        cut = find_cut_set_adaptive(
            records,
            metrics,
            args.cut_diameter / 2.0,
            args.max_tips,
            args.max_span,
            twig_totals,
            args.max_twigs,
        )
    else:
        cut = find_cut_set(records, args.cut_diameter / 2.0)
    if not cut:
        raise SystemExit(f"no branches cross a {args.cut_diameter} m cut diameter")

    library: dict[str, Any] | None = None
    if args.assign_from_library:
        library = load_part_library(args.assign_from_library)
        if library["species"] != args.species:
            raise SystemExit(
                f"{args.assign_from_library.name} was baked for "
                f"{library['species']}, not {args.species}"
            )
        assignment = assign_against_library(
            records, metrics, cut, twig_totals, library
        )
        medoids = []
        stats = descriptor_vectors(records, metrics, cut, twig_totals)[0]
    else:
        medoids, assignment, stats = cluster_prototypes(
            records, metrics, cut, args.clusters, twig_totals=twig_totals
        )
    in_parts = sum(metrics["branches"][idx] for idx in cut)
    prototype_count = len(library["prototypes"]) if library else len(medoids)
    logger.info(
        "cut diameter %.3f m -> %d instances, %d prototypes, "
        "%d branches left in the base mesh",
        args.cut_diameter,
        len(cut),
        prototype_count,
        len(records) - in_parts,
    )
    if library:
        # The medoids' own branch ids index the tree the LIBRARY was baked
        # from, not this one, so nothing local can be reported about them.
        logger.info("\n%-6s %-30s %-9s %s", "proto", "name", "members", "twigs")
        for c, proto in enumerate(library["prototypes"]):
            logger.info(
                "%-6d %-30s %-9d %d",
                c,
                proto["name"],
                sum(1 for a in assignment if a == c),
                proto["twigs"],
            )
    else:
        logger.info(
            "\n%-6s %-8s %-7s %-8s %-8s %-8s %s",
            "proto",
            "members",
            "tips",
            "len(m)",
            "span(m)",
            "up",
            "branch",
        )
        for c, branch_id in enumerate(medoids):
            members = sum(1 for a in assignment if a == c)
            s = subtree_stats(records, metrics, branch_id)
            logger.info(
                "%-6d %-8d %-7d %-8.2f %-8.2f %-8.2f %d",
                c,
                members,
                s["tips"],
                s["total_length"],
                s["span"],
                s["up_alignment"],
                branch_id,
            )

    total_tips = sum(s["tips"] for s in stats)
    logger.info(
        "\n%d instances carry %d tips total (%.1f per part); "
        "the un-cut tree has %d branches",
        len(cut),
        total_tips,
        total_tips / len(cut),
        len(records),
    )

    if args.json:
        manifest = {
            "species": args.species,
            "cycles": args.cycles,
            "seed": args.seed,
            "cut_diameter": args.cut_diameter,
            "adaptive": adaptive,
            "max_tips": args.max_tips,
            "max_span": args.max_span,
            "instances": len(cut),
            "base_branches": len(records) - in_parts,
            "prototypes": (
                library["prototypes"]
                if library
                else [
                    {
                        "id": c,
                        "branch": branch_id,
                        "members": sum(1 for a in assignment if a == c),
                        "stats": subtree_stats(records, metrics, branch_id),
                    }
                    for c, branch_id in enumerate(medoids)
                ]
            ),
            "placements": [
                {
                    "branch": branch_id,
                    "prototype": assignment[i],
                    "position": records[branch_id].base_pos,
                    "direction": records[branch_id].base_dir,
                    "base_radius": records[branch_id].base_radius,
                }
                for i, branch_id in enumerate(cut)
            ],
        }
        args.json.write_text(json.dumps(manifest, indent=2))
        logger.info("manifest written to %s", args.json)

    base: dict[str, Any] = {}
    if args.base_mesh:
        base = export_base_mesh(
            model,
            records,
            cut,
            args.base_mesh,
            args.species,
            skeleton=skeleton,
            bones_info=bones_info,
        )
        logger.info(
            "base mesh (%s): %d points, %d faces across %d branches, "
            "%d source faces dropped, %.1f MB -> %s",
            "skeletal" if base["skeletal"] else "static",
            base["points"],
            base["faces"],
            base["branches_in_base"],
            base["dropped_faces"],
            base["file_bytes"] / 1e6,
            Path(base["file"]).name,
        )

    report: list[dict[str, Any]] = []
    if args.bake:
        report = bake_prototypes(
            model,
            records,
            metrics,
            medoids,
            twig_usd_by_type,
            args.bake,
            args.species,
        )
        logger.info(
            "\n%-6s %-9s %-9s %-9s %-8s %-9s %s",
            "proto",
            "twigs",
            "faces",
            "woody",
            "MB",
            "span(m)",
            "file",
        )
        for row in report:
            logger.info(
                "%-6d %-9d %-9d %-9d %-8.2f %-9.2f %s",
                row["prototype"],
                row["welded_twigs"],
                row["faces"],
                row["woody_faces"],
                row["file_bytes"] / 1e6,
                row["span"],
                Path(row["file"]).name,
            )
        total_faces = sum(r["faces"] for r in report)
        logger.info(
            "\n%d prototypes, %d faces total, %.1f MB on disk",
            len(report),
            total_faces,
            sum(r["file_bytes"] for r in report) / 1e6,
        )
        report_path = args.bake / f"{args.species}_compound_parts.json"
        report_path.write_text(
            json.dumps(
                {
                    "species": args.species,
                    "cycles": args.cycles,
                    "seed": args.seed,
                    "cut_diameter": args.cut_diameter,
                    "max_tips": args.max_tips,
                    "max_span": args.max_span,
                    "max_twigs": args.max_twigs,
                    "twig_usd": {t: str(p) for t, p in twig_usd_by_type.items()},
                    "instances": len(cut),
                    "base_branches": len(records) - in_parts,
                    "forward_axis": "+X (the PointInstancer quaternion rotates +X, "
                    "see core.twig._quat_forward)",
                    "prototypes": report,
                },
                indent=2,
            )
        )
        logger.info("size report written to %s", report_path)

        if args.library:
            library = write_part_library(
                args.bake,
                args.species,
                report,
                records,
                metrics,
                cut,
                twig_totals,
                args.library_package,
                source={
                    "cycles": args.cycles,
                    "seed": args.seed,
                    "cut_diameter": args.cut_diameter,
                    "adaptive": adaptive,
                    "max_tips": args.max_tips,
                    "max_span": args.max_span,
                    "max_twigs": args.max_twigs,
                    "twig_usd": {t: str(p) for t, p in twig_usd_by_type.items()},
                    "clusters": args.clusters,
                },
                skeletal=args.skeletal,
                residual_twig_usd=residual_twig_usd,
            )

    if args.assembly:
        # In library mode the parts already sit beside the library manifest;
        # otherwise they are the ones just baked.
        parts_dir = (
            Path(library["path"]).parent if args.assign_from_library else args.bake
        )
        if library:
            if library.get("skeletal", True) != args.skeletal:
                raise SystemExit(
                    f"{Path(library['path']).name} was baked "
                    f"{'skeletal' if library.get('skeletal', True) else 'static'}; "
                    f"this assembly is "
                    f"{'skeletal' if args.skeletal else 'static'}"
                )
            key = "skeletal_file" if args.skeletal else "static_file"
            prototype_files = [parts_dir / p[key] for p in library["prototypes"]]
        else:
            prototype_files = [
                Path(r["skeletal_file" if args.skeletal else "file"]) for r in report
            ]

        asm = export_compound_assembly(
            args.base_mesh,
            args.assembly,
            records,
            cut,
            assignment,
            prototype_files,
            args.species,
            bone_ids=(
                cut_point_bone_ids(model, cut, base.get("bone_map"))
                if args.skeletal
                else None
            ),
            use_skeletal_mesh=args.skeletal,
            instances_dir=parts_dir,
            max_instances=args.max_instances,
            residual_twig_usd=residual_twig_usd,
            model=model,
            bones_info=bones_info,
            bone_map=base.get("bone_map") if args.skeletal else None,
        )
        logger.info(
            "assembly (%s): %d instances (%d compound parts + %d 1:1 twigs) "
            "over %d prototypes, %d parts bound to a bone, "
            "%.1fM flattened triangles, %.2f MB -> %s",
            "skeletal" if asm["skeletal"] else "static",
            asm["instances"],
            asm["parts"],
            asm["residual_twigs"],
            asm["prototypes"],
            asm["bound_instances"],
            asm["flattened_triangles"] / 1e6,
            asm["file_bytes"] / 1e6,
            Path(asm["file"]).name,
        )

        if args.extref_assembly:
            from growpy.io.usd.extref_assembly import (
                convert_assembly_to_external_refs,
            )

            ext = convert_assembly_to_external_refs(
                args.assembly,
                args.extref_assembly,
                library_asset_paths(library),
            )
            # No ratio against the embedded form: the embedded assembly is
            # small too, and its cost is the part FILES it drags along, which
            # this one does not have at all.
            logger.info(
                "external-ref assembly: %.2f MB, referencing NO part files -- "
                "its %d prototypes come from %s, imported once per species",
                ext["file_bytes"] / 1e6,
                ext["prototypes"],
                library["package_root"],
            )


if __name__ == "__main__":
    main()
