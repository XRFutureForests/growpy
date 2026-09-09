"""
Growth Data JSON exporter for PVE's Growth Data JSON Importer node (UE 5.8).

Bypasses the deprecated Preset Loader and the full Megaplants-style recipe
(``pve_grove_mapper.generate_pve_from_grove``) entirely, and feeds
``UPVGrowthDataJsonImporterSettings`` -- which reads a growth JSON straight from
a file path, needs no data asset and no ``Update Data Asset`` button, and is
fully Python-drivable. Export is then the only manual click in the whole route.

VALIDATED END TO END 2026-09-09 against a live UE 5.8 editor (this is the
validation the previous docstring said was still outstanding). Height survives
to +0.4 % and the trunk radius passes through the mesher untouched.

--------------------------------------------------------------------------
WHAT THE IMPORTER ACTUALLY REQUIRES
--------------------------------------------------------------------------
``PVJSONHelper::LoadGrowthDataJsonToCollection()`` validates only six paths, but
that list is badly misleading: ``PV::Utilities::IsValidGrowthData`` -- the gate
that rejects bad data on the *data-asset* path -- is NOT applied by the importer
node. So a file that satisfies the six paths and nothing else is not rejected;
it reaches the mesher and **crashes the editor on an assert**. Six editor
crashes were paid for establishing the real contract. Everything emitted below
is required by ``FPointFacade::IsValid`` / ``FBranchFacade::IsValid``, by a
checked ``GetAttribute()`` call site, or by a hard width assert.

Descriptor rules, all three of which cost a crash:

* ``size`` is the TUPLE WIDTH, not the array length. ``FillAttributes`` branches
  only on 1 and 3; any other value silently drops the attribute. ``values`` is a
  flat list of numbers either way -- ``size`` only sets the stride.
* ``isArray`` must match the C++ type. ``parents``/``children``/``Points`` are
  ``TArray<int32>``, so ``parents`` needs ``isArray: true`` even though a branch
  has exactly one parent.
* Fixed-width structured attributes are read through a CONST view, and
  ``TFixedSizeArrayHelper``'s const overload does NOT pad a short array -- it
  discards it and returns all-zero DefaultData. A short ``budLateralMeristem``
  is therefore not "partly filled", it is ZERO RADIUS.

--------------------------------------------------------------------------
UP AXIS -- Grove is Z-up, the JSON must be Y-up, so we DO pre-swap
--------------------------------------------------------------------------
The loader does ``FVector3f(P[0], P[2], P[1]) * 100``, i.e.

    UE X = json[0]      UE Y = json[2]      UE Z (UP) = json[1]

so the height must sit at json index **1**. Grove is Z-up and puts height at
index 2, so writing Grove's native order unconverted lands the height in UE's Y
and the tree falls on its side. This module's previous docstring claimed the
opposite and left positions unconverted; that was wrong. Every size-3 attribute
gets the same swap on load, so ``budDirection`` is pre-swapped too.

Positions are in METRES (the ``* 100`` is the m->cm conversion).

--------------------------------------------------------------------------
RADIUS, AND WHY IT IS DIVIDED BY A PROFILE MEAN
--------------------------------------------------------------------------
``Scale[i] = budLateralMeristem[i][0] * 100`` -- element 0 is the point radius
in metres -- and with the four BranchRadius knobs at their defaults
(``DaVinciRuleStrength`` 0, ``MinRadius`` 0, empty ``GenerationRamps`` and
``GenerationScales``) it reaches the mesh untouched.

But it becomes the cross-section's MAXIMUM radius, not its mean. A PVE trunk
profile is 100 radial multipliers that always peak at exactly 1.0 and carve
inward from there, so a tape-measured DBH on the export reads
``mean(profile)`` times the radius asked for. Measured on two independent
skeletons: 0.775 (synthetic trunk) and 0.784-0.793 (Epic's Beech_01), against
``plantProfile_2``'s own mean of 0.7795.

``profile_mean`` divides that out, so the exported trunk carries the measured
DBH whatever profile is chosen and profile choice stays purely cosmetic.
Epic's ten profiles have means 0.599-0.822 -- a 37 % swing, larger than any
other knob found -- so this is not optional if DBH is to mean anything.
Pass 1.0 to disable.

--------------------------------------------------------------------------
DECIMATION -- why the raw skeleton is unusable here
--------------------------------------------------------------------------
Grove's skeleton is far denser than anything PVE is meant to consume. A
26-cycle beech gives **275,818 points across 46,515 branches** (a 394 MB JSON),
against Epic's own Beech_01 at 5,145 points / 195 branches. The point SPACING is
fine -- 0.067 m along the trunk, finer than Beech_01's 0.072 m -- the problem is
branch COUNT: ~5.9 points per branch means most are twig-scale stubs.

That matters beyond file size. Foliage density is set per branch
(``BranchDensity``), so 46,515 branches against a Forrester target of ~13,400
instances would need a density below 1, which the knob cannot express.

``min_branch_radius`` drops every branch whose thickest point is below the
threshold, together with its whole subtree, then renumbers the hierarchy. It is
a PVE-route concern only and touches neither the USD route nor Grove's config,
so the calibration Path A owns is unaffected.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .pve_grove_mapper import (
    _calculate_branch_parents_from_skeleton,
    _calculate_bud_directions,
)
from .pve_hierarchy_builder import build_hierarchy_arrays

logger = logging.getLogger(__name__)

# Widths of the fixed-size structured point attributes. A value shorter than
# these is discarded wholesale by the const view, not padded.
_BUD_DIRECTION_FLOATS = 18  # 6 vectors: Apical Axillary LightOptimal
#                             LightSubOptimal GuideCurve UpVector
_MERISTEM_FLOATS = 7  # LateralMeristem Multiplier Inactive Davinci
#                       ParentDot RootDistance Degredation
_HORMONE_FLOATS = 6  # Apical Axillary AxillaryInhibition Radical
#                      Ethylene Cytokinin
_LIGHT_FLOATS = 4  # Availible Resource Branch Collision
_DEVELOPMENT_INTS = 6  # Generation BudAge BranchAge AgeSenescense
#                        LightSenescense RelativeBudAge
_STATUS_INTS = 10  # ApicalMeristem Codominant Axillary Seed Dormant Triggered
#                    NumTriggered Inactive BrokenTip Broken


def _attr(type_: str, size: int, is_array: bool, values: list) -> dict:
    return {"isArray": is_array, "size": size, "type": type_, "values": values}


def _swap_zup_to_yup(vec: list[float]) -> list[float]:
    """Grove (x, y, z_up) -> JSON (x, z_up, y), so the loader lands height in UE Z."""
    return [vec[0], vec[2], vec[1]]


def _swap_flat_vectors(flat: list[float]) -> list[float]:
    """Apply the Z-up->Y-up swap to every 3-tuple in a flattened vector list."""
    out: list[float] = []
    for i in range(0, len(flat) - 2, 3):
        out.extend((flat[i], flat[i + 2], flat[i + 1]))
    return out


def _empty_growth_data() -> dict:
    """Same shape as a populated file, so downstream schema checks still hold."""
    return {
        "points": {
            "positions": [],
            "attributes": {
                "budDirection": _attr("float", 3, True, []),
                "budLateralMeristem": _attr("float", 1, True, []),
                "budHormoneLevels": _attr("float", 1, True, []),
                "budLightDetected": _attr("float", 1, True, []),
                "budDevelopment": _attr("int", 1, True, []),
                "budStatus": _attr("int", 1, True, []),
                "budNumber": _attr("int", 1, False, []),
                "plantGradient": _attr("float", 1, False, []),
                "LOD_hullGradient": _attr("float", 1, False, []),
                "LOD_mainTrunkGradient": _attr("float", 1, False, []),
                "LOD_groundGradient": _attr("float", 1, False, []),
                "LOD_totalPscaleGradient": _attr("float", 1, False, []),
            },
        },
        "primitives": {
            "points": [],
            "attributes": {
                "parents": _attr("int", 1, True, []),
                "children": _attr("int", 1, True, []),
                "branchNumber": _attr("int", 1, False, []),
                "branchSourceBudNumber": _attr("int", 1, False, []),
                "branchParentNumber": _attr("int", 1, False, []),
                "branchHierarchyNumber": _attr("int", 1, False, []),
                "plantNumber": _attr("int", 1, False, []),
            },
        },
    }


def _ancestor_chains(
    parent_of: list[int], num_branches: int
) -> list[list[int]]:
    """``parents`` is the ancestor CHAIN of branchNumbers starting at 0.

    Beech_01 has ``[0]`` for the trunk and ``[0, 1]`` for a child of it -- not
    the immediate parent, which is what this module used to emit.
    ``branchParentNumber`` carries the immediate parent instead.
    """
    chains: list[list[int]] = []
    for b in range(num_branches):
        chain: list[int] = []
        seen: set[int] = set()
        cur = b
        # Grove marks a root by self-reference; stop there and on any cycle.
        while cur not in seen:
            seen.add(cur)
            nxt = parent_of[cur] if cur < len(parent_of) else cur
            if nxt == cur or nxt < 0 or nxt >= num_branches:
                break
            chain.append(nxt + 1)  # branchNumber is 1-based
            cur = nxt
        chains.append([0] + list(reversed(chain)))
    return chains


def _decimate_growth_data(data: dict, min_branch_radius: float) -> dict:
    """Drop branches thinner than ``min_branch_radius`` and renumber.

    Operates on the finished JSON rather than on the skeleton, so every derived
    attribute (bud directions, ancestor chains, gradients) is already computed
    and this stays pure filter-and-renumber -- far harder to get subtly wrong
    than recomputing the hierarchy on a mutated skeleton.

    A branch survives only if its thickest point reaches the threshold AND every
    ancestor survives, so what remains is always connected. The trunk is kept
    unconditionally.
    """
    prims = data["primitives"]
    pts = data["points"]
    branch_points = prims["points"]
    num_branches = len(branch_points)
    if num_branches == 0 or min_branch_radius <= 0.0:
        return data

    blm = pts["attributes"]["budLateralMeristem"]["values"]
    parent_no = prims["attributes"]["branchParentNumber"]["values"]
    hier = prims["attributes"]["branchHierarchyNumber"]["values"]

    def thickest(bi):
        best = 0.0
        for pi in branch_points[bi]:
            if 0 <= pi < len(blm) and blm[pi]:
                best = max(best, float(blm[pi][0]))
        return best

    # Root-first, so an ancestor's verdict is always already known.
    keep = [False] * num_branches
    for bi in sorted(range(num_branches), key=lambda b: hier[b]):
        if thickest(bi) < min_branch_radius:
            continue
        par = parent_no[bi]            # 1-based; 0 means no parent (trunk)
        keep[bi] = True if par == 0 else keep[par - 1]
    if not any(keep):
        keep[0] = True                 # never return an empty tree

    kept = [b for b in range(num_branches) if keep[b]]
    new_of_branch = {b: i for i, b in enumerate(kept)}

    seen = set()
    kept_points = []
    for b in kept:
        for pi in branch_points[b]:
            if pi not in seen:
                seen.add(pi)
                kept_points.append(pi)
    new_of_point = {pi: i for i, pi in enumerate(kept_points)}

    def take(seq, idx):
        return [seq[i] for i in idx]

    out_points = {
        "positions": take(pts["positions"], kept_points),
        "attributes": {
            k: dict(v, values=take(v["values"], kept_points))
            for k, v in pts["attributes"].items()
        },
    }

    def renumber(old_1based):
        """Old 1-based branchNumber -> new one; 0 if that branch was dropped."""
        if old_1based <= 0:
            return 0
        ob = old_1based - 1
        return new_of_branch[ob] + 1 if ob in new_of_branch else 0

    new_parents, new_children, new_parent_no, new_hier = [], [], [], []
    for b in kept:
        chain = [c for c in (renumber(x) for x in prims["attributes"]["parents"]["values"][b]) if c]
        new_parents.append([0] + chain)
        new_children.append(
            [c for c in (renumber(x) for x in prims["attributes"]["children"]["values"][b]) if c]
        )
        new_parent_no.append(renumber(parent_no[b]))
        new_hier.append(len(new_parents[-1]))

    n = len(kept)
    out_prims = {
        "points": [[new_of_point[pi] for pi in branch_points[b]] for b in kept],
        "attributes": {
            "parents": _attr("int", 1, True, new_parents),
            "children": _attr("int", 1, True, new_children),
            "branchNumber": _attr("int", 1, False, list(range(1, n + 1))),
            "branchSourceBudNumber": _attr("int", 1, False, [0] * n),
            "branchParentNumber": _attr("int", 1, False, new_parent_no),
            "branchHierarchyNumber": _attr("int", 1, False, new_hier),
            "plantNumber": _attr("int", 1, False, [1] * n),
        },
    }

    logger.info(
        "decimated at min_branch_radius=%.4f m: %d -> %d branches, %d -> %d points",
        min_branch_radius, num_branches,
        n, len(pts["positions"]), len(kept_points),
    )
    return {"points": out_points, "primitives": out_prims}


def build_growth_data_json(
    skeleton: Any,
    profile_mean: float = 1.0,
    radial_scale: float = 1.0,
    min_branch_radius: float = 0.0,
) -> dict:
    """
    Build the growth-data JSON for PVE's Growth Data JSON Importer.

    Args:
        skeleton: Grove skeleton object (``points`` + ``poly_lines``),
            pre-built by the export phase -- same object passed to
            ``map_grove_to_pve()``.
        profile_mean: Mean radial multiplier of the PVE trunk profile this tree
            will be meshed with. Emitted radii are divided by it so the exported
            trunk carries the measured DBH; see the module docstring. 1.0
            disables the correction.
        radial_scale: ``target_dbh_m / grove_dbh`` for this tree. **Not
            optional in practice.** Grove's raw ``point_attribute_radius`` is
            NOT the calibrated diameter -- growpy realises DBH at export from
            the yield-table height-DBH allometry, and the USD path applies this
            factor (``forest_stages.compute_radial_scale``). Passing 1.0 here
            emits Grove's uncalibrated geometry: measured on an 11.4 m beech
            that is a 0.30 m base radius, i.e. DBH 0.60 m. 1.0 is the right
            value only for a skeleton whose radii are already calibrated.
        min_branch_radius: Drop branches whose thickest point is below this
            radius, in metres, along with their subtrees. 0.0 keeps everything,
            which for a real Grove skeleton means ~46k branches -- see the
            module docstring. Applied AFTER radial_scale and profile_mean, so
            the threshold is in the same units as the emitted radii.

    Returns:
        Dict matching the validated contract (see module docstring).
    """
    if not 0.0 < profile_mean <= 1.0:
        raise ValueError(
            "profile_mean must be in (0, 1]; PVE profiles peak at 1.0 so their "
            f"mean cannot exceed it (got {profile_mean!r})"
        )
    if radial_scale <= 0.0:
        raise ValueError(f"radial_scale must be > 0 (got {radial_scale!r})")

    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines
    num_branches = len(poly_lines)

    if num_points == 0 or num_branches == 0:
        return _empty_growth_data()

    # Local positions, Grove Z-up swapped to the Y-up the loader expects.
    origin = skeleton_points[0]
    positions = [
        _swap_zup_to_yup(
            [p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]]
        )
        for p in skeleton_points
    ]

    # 18 floats/point already; swap each 3-tuple to match the positions.
    bud_directions = [
        _swap_flat_vectors(list(d)) for d in _calculate_bud_directions(skeleton)
    ]

    # Radius -> budLateralMeristem[0], in metres, corrected for the profile.
    radii = list(getattr(skeleton, "point_attribute_radius", []) or [])
    if len(radii) < num_points:
        radii = radii + [0.0] * (num_points - len(radii))
    meristem = [
        [
            # radius (m): Grove raw -> calibrated DBH -> profile-corrected
            float(radii[i]) * radial_scale / profile_mean,  # 0 LateralMeristem
            1.0,  # 1 Multiplier
            0.0,  # 2 Inactive
            0.0,  # 3 Davinci
            1.0,  # 4 ParentDot
            0.0,  # 5 RootDistance -- overwritten below
            0.0,  # 6 Degredation
        ]
        for i in range(num_points)
    ]

    # RootDistance is metre-scale in Epic's own data (17.3 near the top of a
    # 23.5 m tree) and feeds lengthFromRoot/lengthFromSeed unscaled.
    for i, pos in enumerate(positions):
        meristem[i][5] = float(pos[1])  # height above the tree origin, metres

    hormones = [[1.0, 0.0, 0.0, 0.0, 1.0, 0.0] for _ in range(num_points)]
    light = [[1.0, 0.0, 1.0, 0.0] for _ in range(num_points)]
    development = [[1, 40, 40, 0, 0, 40] for _ in range(num_points)]
    # (0,0,1,0,1,0,0,0,0,0) is the commonest budStatus in Beech_01. The width is
    # hard-asserted at PVUtilities.cpp:331, check(BudStatus.Num() == 10).
    status = [[0, 0, 1, 0, 1, 0, 0, 0, 0, 0] for _ in range(num_points)]
    # budNumber must EXIST -- ComputeBudNumbers uses FindAttribute, not
    # AddAttribute, so it only overwrites a value that is already there.
    bud_number = [1] * num_points
    gradient = [1.0] * num_points

    # Rebase poly_line point indices to 0 (Grove uses global indices across
    # all skeletons in a grove; this skeleton's points array is 0-indexed).
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0
    primitive_points = [[idx - index_offset for idx in pl] for pl in poly_lines]

    hierarchy = build_hierarchy_arrays(None, num_branches, skeleton)
    children_immediate = hierarchy["children"]["values"]
    # NOT hierarchy["parents"]: that is growpy's own chain convention,
    # self-first back to the root in 0-based indices ([[0], [1, 0], [2, 1, 0]]).
    # Epic's is the mirror image -- root-first in 1-based branchNumbers with a
    # virtual 0 at the head -- so build it from the immediate parents instead.
    parent_of = _calculate_branch_parents_from_skeleton(skeleton, num_branches)

    # branchNumber is 1-based, and children/parents are expressed in it.
    branch_numbers = list(range(1, num_branches + 1))
    parents = _ancestor_chains(parent_of, num_branches)
    children = [[c + 1 for c in kids] for kids in children_immediate]
    branch_parent_number = [
        (parent_of[b] + 1) if (b < len(parent_of) and parent_of[b] != b) else 0
        for b in range(num_branches)
    ]
    branch_hierarchy = [len(chain) for chain in parents]

    built = {
        "points": {
            "positions": positions,
            "attributes": {
                "budDirection": _attr("float", 3, True, bud_directions),
                "budLateralMeristem": _attr("float", 1, True, meristem),
                "budHormoneLevels": _attr("float", 1, True, hormones),
                "budLightDetected": _attr("float", 1, True, light),
                "budDevelopment": _attr("int", 1, True, development),
                "budStatus": _attr("int", 1, True, status),
                "budNumber": _attr("int", 1, False, bud_number),
                "plantGradient": _attr("float", 1, False, gradient),
                "LOD_hullGradient": _attr("float", 1, False, gradient),
                "LOD_mainTrunkGradient": _attr("float", 1, False, gradient),
                "LOD_groundGradient": _attr("float", 1, False, gradient),
                "LOD_totalPscaleGradient": _attr("float", 1, False, gradient),
            },
        },
        "primitives": {
            "points": primitive_points,
            "attributes": {
                "parents": _attr("int", 1, True, parents),
                "children": _attr("int", 1, True, children),
                "branchNumber": _attr("int", 1, False, branch_numbers),
                "branchSourceBudNumber": _attr("int", 1, False, [0] * num_branches),
                "branchParentNumber": _attr("int", 1, False, branch_parent_number),
                "branchHierarchyNumber": _attr("int", 1, False, branch_hierarchy),
                "plantNumber": _attr("int", 1, False, [1] * num_branches),
            },
        },
    }
    return _decimate_growth_data(built, min_branch_radius)


def generate_growth_data_from_grove(
    grove: Any,
    output_path: Path,
    tree_index: int = 0,
    skeleton: Any | None = None,
    verbose: bool = True,
    profile_mean: float = 1.0,
    radial_scale: float = 1.0,
    min_branch_radius: float = 0.0,
) -> dict:
    """
    Build the growth-data JSON from a Grove simulation and write it to disk.

    Args:
        grove: Grove object after simulation.
        output_path: Path to save the generated JSON.
        tree_index: Index of tree in grove (used only if skeleton not given).
        skeleton: Pre-built skeleton from the export phase. If None, builds
            one from ``grove`` (matches ``map_grove_to_pve``'s fallback).
        verbose: Whether to log progress.
        profile_mean: Mean radial multiplier of the trunk profile this tree will
            be meshed with; emitted radii are divided by it. See the module
            docstring.
        radial_scale: ``target_dbh_m / grove_dbh``. Grove's raw radii are not
            the calibrated diameter -- see ``build_growth_data_json``.
        min_branch_radius: Drop branches thinner than this (metres) with their
            subtrees. See ``build_growth_data_json``.

    Returns:
        The generated growth-data dictionary.
    """
    if skeleton is None:
        skeletons = grove.build_skeletons(True)
        if tree_index < len(skeletons):
            skeleton = skeletons[tree_index]

    data = build_growth_data_json(
        skeleton,
        profile_mean=profile_mean,
        radial_scale=radial_scale,
        min_branch_radius=min_branch_radius,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    if verbose:
        logger.info(
            "[OK] Growth Data JSON: %s (radial_scale %.4f, profile_mean %.4f)",
            output_path.name,
            radial_scale,
            profile_mean,
        )
    return data
