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
    records: list[BranchRecord], metrics: dict[str, list], root: int
) -> dict[str, float]:
    """Descriptors for the subtree hanging off `root`."""
    base = records[root]
    return {
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
    """
    return [
        math.log1p(stats["tips"]),
        math.log1p(stats["total_length"]),
        math.log1p(stats["span"]),
        stats["up_alignment"],
        stats["max_depth"] / 5.0,
    ]


def cluster_prototypes(
    records: list[BranchRecord],
    metrics: dict[str, list],
    cut: list[int],
    k: int,
    seed: int = 42,
    sample_size: int = 1500,
) -> tuple[list[int], list[int], list[dict[str, float]]]:
    """k-medoids over the cut set. Returns (medoid branch ids, assignment, stats).

    Medoids rather than centroids: a prototype has to be an actual harvestable
    subtree, not an average of several.
    """
    import random

    stats = [subtree_stats(records, metrics, idx) for idx in cut]
    vectors = [_descriptor(s) for s in stats]

    # Standardise so no single descriptor dominates the distance.
    dims = len(vectors[0])
    means = [sum(v[d] for v in vectors) / len(vectors) for d in range(dims)]
    devs = []
    for d in range(dims):
        var = sum((v[d] - means[d]) ** 2 for v in vectors) / len(vectors)
        devs.append(math.sqrt(var) or 1.0)
    normed = [[(v[d] - means[d]) / devs[d] for d in range(dims)] for v in vectors]

    def dist(a: list[float], b: list[float]) -> float:
        return sum((x - y) ** 2 for x, y in zip(a, b))

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


def bake_prototypes(
    model: Any,
    records: list[BranchRecord],
    metrics: dict[str, list],
    medoids: list[int],
    twig_usd: Path,
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
    twig_index = 0
    for i in range(face_count):
        if long_[i] or short[i] or upward[i]:
            twig_index_of_face[i] = twig_index
            twig_index += 1

    children = [rec.children for rec in records]
    leaf = load_prototype_mesh(twig_usd)
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
        for i in range(face_count):
            if face_branch_ids[i] not in ids:
                continue
            index = twig_index_of_face.get(i)
            if index is None:
                continue
            base = index * 3
            quat = index * 4
            merge_mesh(
                part,
                leaf,
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

        rec = records[branch]
        quat = normalise_part_frame(part, rec.base_pos, rec.base_dir)
        name = f"{species}_compound_p{slot:02d}"
        path = write_compound_part_usd(
            part,
            output_dir / f"{name}_static.usda",
            part_name=name,
            material_source=twig_usd,
        )
        lo, hi = part.bounds()
        stats = subtree_stats(records, metrics, branch)
        report.append(
            {
                "prototype": slot,
                "name": name,
                "branch": branch,
                "file": str(path),
                "file_bytes": path.stat().st_size,
                "points": len(part.points),
                "faces": len(part.faces),
                "woody_faces": woody_faces,
                "welded_twigs": welded,
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    adaptive = not args.no_adaptive
    grove = grow_grove(args.species, args.cycles, args.seed)
    tree = grove.trees[0]
    records = flatten_branches(tree)
    metrics = precompute_subtrees(records)

    # The twig band needs a built model, so it is only available when baking.
    model = None
    twig_totals = None
    if args.bake:
        if args.twig_usd is None:
            raise SystemExit("--bake requires --twig-usd")
        if not args.twig_usd.is_file():
            raise SystemExit(f"twig USD not found: {args.twig_usd}")
        model = build_reference_model(grove)
        twig_totals = count_subtree_twigs(model, records)
        logger.info(
            "reference model: %d living twigs across %d branches",
            twig_totals[0],
            len(records),
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

    medoids, assignment, stats = cluster_prototypes(
        records, metrics, cut, args.clusters
    )
    in_parts = sum(metrics["branches"][idx] for idx in cut)
    logger.info(
        "cut diameter %.3f m -> %d instances, %d prototypes, "
        "%d branches left in the base mesh",
        args.cut_diameter,
        len(cut),
        len(medoids),
        len(records) - in_parts,
    )
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
            "prototypes": [
                {
                    "id": c,
                    "branch": branch_id,
                    "members": sum(1 for a in assignment if a == c),
                    "stats": subtree_stats(records, metrics, branch_id),
                }
                for c, branch_id in enumerate(medoids)
            ],
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

    if args.bake:
        report = bake_prototypes(
            model,
            records,
            metrics,
            medoids,
            args.twig_usd,
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
                    "twig_usd": str(args.twig_usd),
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


if __name__ == "__main__":
    main()
