"""
Build parent/child hierarchy arrays for PVE preset primitives.

Derives branch relationship data from Grove skeleton poly_line connectivity.
NOTE: We use skeleton (not model) because model.face_attribute_branch_id only
contains faces for branches that pass cutoff filters. Skeleton has ALL branches.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _derive_parents_from_skeleton(skeleton: Any) -> list[int]:
    """
    Derive parent branch indices from skeleton poly_line connectivity.

    Each poly_line is a branch. A branch's first point connects to its parent branch.
    We find the parent by looking for another branch that contains our first point
    (but doesn't start with it - that would be a sibling).

    Args:
        skeleton: Grove skeleton object with poly_lines attribute

    Returns:
        List of parent indices (-1 for root branches)
    """
    poly_lines = skeleton.poly_lines
    num_branches = len(poly_lines)

    if num_branches == 0:
        return []

    # Build point -> branches mapping
    point_to_branches = {}
    for branch_idx, pl in enumerate(poly_lines):
        for point_idx in pl:
            if point_idx not in point_to_branches:
                point_to_branches[point_idx] = []
            point_to_branches[point_idx].append(branch_idx)

    # Derive parent for each branch
    parents = []
    for branch_idx, pl in enumerate(poly_lines):
        if len(pl) == 0:
            parents.append(-1)
            continue

        first_point = pl[0]
        containing_branches = point_to_branches.get(first_point, [])

        # Find parent: another branch that contains this point but doesn't start with it
        parent = -1
        for other_branch in containing_branches:
            if other_branch == branch_idx:
                continue
            other_pl = poly_lines[other_branch]
            if len(other_pl) > 0 and other_pl[0] != first_point:
                # This branch contains our first point but doesn't start with it - it's the parent
                parent = other_branch
                break

        parents.append(parent)

    return parents


# UE 5.8 ships 17 MegaPlants presets; every one caps compoundMaxBranchGeneration
# at 3 (Broadleaf_Hazel_02 alone uses 2), while branchGeneration runs to 6.
DEFAULT_MAX_COMPOUND_GENERATION = 3


def _bucket_generations(
    generations: list[int], max_compound_generation: int
) -> list[int]:
    """Collapse a branch-generation range onto 1..max_compound_generation.

    Grove's generations are 0-based hierarchy depth; PVE's compound generations
    are 1-based, so everything is shifted up by one first.

    Measured against the shipped presets, compoundBranchGeneration is a monotone
    step function of branchGeneration -- verified as a pure function of it on all
    17 files. `Beech_01` maps {1:1, 2:2, 3:2, 4:3, 5:3, 6:3}: the trunk axis keeps
    a bucket to itself and the rest of the range is split into the remaining
    buckets, smaller bucket first. That rule reproduces `Beech_01` and
    `Broadleaf_Hazel_05` exactly; `Beech_04` splits its middle differently, so
    Epic's own presets are not consistent about where the rounding lands.
    """
    if not generations:
        return []

    cap = max(1, max_compound_generation)
    # Grove counts the trunk as generation 0, PVE as compound generation 1.
    axis = [g + 1 for g in generations]
    max_axis = max(axis)

    if max_axis <= cap:
        return axis

    if cap == 1:
        # Degenerate but well defined: the whole tree is one compound generation.
        return [1] * len(axis)

    # Generation 1 keeps a bucket to itself; 2..max_axis share the remaining
    # cap - 1 buckets as contiguous, as-equal-as-possible runs.
    spread = max_axis - 1
    buckets = cap - 1
    base, remainder = divmod(spread, buckets)
    # Smaller runs first: the first (buckets - remainder) take `base` generations.
    compound_of_axis = {1: 1}
    generation = 2
    for bucket in range(buckets):
        run = base + (1 if bucket >= buckets - remainder else 0)
        for _ in range(run):
            compound_of_axis[generation] = bucket + 2
            generation += 1

    return [compound_of_axis[a] for a in axis]


def build_compound_hierarchy(
    parents: list[int],
    generations: list[int],
    max_compound_generation: int = DEFAULT_MAX_COMPOUND_GENERATION,
) -> dict[str, Any]:
    """Derive PVE's compound branch layer from the branch hierarchy.

    A compound branch is a *cluster* of branches, not a branch: it collapses a
    main axis and its continuations into one unit, which is why every shipped
    MegaPlants preset caps compoundMaxBranchGeneration at 2-3 while
    branchGeneration runs to 6.

    Four laws, read off the 17 presets under UE 5.8's
    ProceduralVegetationEditor/Content/SampleAssets and verified there:

    * A cluster's generation is its parent cluster's plus one (exact on 17/17).
    * compoundBranchGeneration is constant across a cluster on 12/17. The five
      misses -- Broadleaf_Hazel_01 to _04 and NorwayMaple_04 -- each contain
      exactly ONE cluster whose members disagree, and all five are multi-stem
      forms where nearly every branch is its own cluster anyway (Hazel_01: 380
      clusters over 381 branches). Treated as authoring noise rather than a
      sixth rule.
    * A cluster is exactly a connected component of parent edges whose two ends
      share a compound generation (exact on 13/17; the four misses are the same
      degenerate multi-stem files, each differing by a single cluster).
    * compoundBranchNumber is a 0-based contiguous cluster id and a root
      cluster's compoundBranchParentNumber points at itself (17/17) -- the same
      self-reference convention growpy already uses for branchParentNumber.

    growpy emits the laws exactly, so its own output is 100% on all of them;
    the fractions above describe how consistently Epic's authored presets obey
    them, not a tolerance in this code.

    Args:
        parents: Immediate parent branch index per branch, roots self-referencing
            (the convention `calculate_branch_parents_from_skeleton` returns).
        generations: 0-based branchGeneration per branch.
        max_compound_generation: Cap on the compound generation range.

    Returns:
        Dict with per-branch ``compound_generation`` (1-based),
        ``compound_number`` and ``compound_parent_number`` lists, plus
        ``compound_count`` (the cluster count, which is PVE's
        compoundMaxBranchNumber) and ``max_compound_generation`` (the largest
        compound generation actually present).
    """
    num_branches = len(generations)
    if num_branches == 0:
        return {
            "compound_generation": [],
            "compound_number": [],
            "compound_parent_number": [],
            "compound_count": 0,
            "max_compound_generation": 0,
        }

    compound_generation = _bucket_generations(generations, max_compound_generation)

    def _parent_of(branch: int) -> int:
        """Immediate parent, or -1 for a root (self-reference or out of range)."""
        if branch >= len(parents):
            return -1
        parent = parents[branch]
        if parent < 0 or parent == branch or parent >= num_branches:
            return -1
        return parent

    # Union a branch into its parent's cluster when they share a compound
    # generation. Iterative find with path halving: crown chains run deep.
    union_parent = list(range(num_branches))

    def _find(branch: int) -> int:
        while union_parent[branch] != branch:
            union_parent[branch] = union_parent[union_parent[branch]]
            branch = union_parent[branch]
        return branch

    for branch in range(num_branches):
        parent = _parent_of(branch)
        if parent < 0:
            continue
        if compound_generation[branch] != compound_generation[parent]:
            continue
        root_a, root_b = _find(branch), _find(parent)
        if root_a != root_b:
            union_parent[root_a] = root_b

    # Number clusters in order of first appearance so the ids are deterministic
    # and 0-based contiguous, as the reference presets are.
    cluster_of_root: dict[int, int] = {}
    compound_number = [0] * num_branches
    for branch in range(num_branches):
        root = _find(branch)
        if root not in cluster_of_root:
            cluster_of_root[root] = len(cluster_of_root)
        compound_number[branch] = cluster_of_root[root]

    # A cluster's parent is the cluster of whichever ancestor edge left it.
    # Root clusters self-reference.
    cluster_count = len(cluster_of_root)
    cluster_parent = list(range(cluster_count))
    for branch in range(num_branches):
        parent = _parent_of(branch)
        if parent < 0:
            continue
        cluster = compound_number[branch]
        parent_cluster = compound_number[parent]
        if parent_cluster != cluster:
            cluster_parent[cluster] = parent_cluster

    compound_parent_number = [cluster_parent[c] for c in compound_number]

    return {
        "compound_generation": compound_generation,
        "compound_number": compound_number,
        "compound_parent_number": compound_parent_number,
        "compound_count": cluster_count,
        "max_compound_generation": max(compound_generation),
    }


def build_hierarchy_arrays(
    model: Any, num_branches: int, skeleton: Any | None = None
) -> dict[str, dict]:
    """
    Build parent and children arrays from Grove skeleton poly_line connectivity.

    PVE format expects:
    - parents: Full ancestor chain from branch back to root [[0], [1, 0], [2, 1, 0], ...]
    - children: List of direct children for each branch [[1, 2, 3], [4, 5], ...]

    The root branch (0) has parents = [0] (self-reference, not -1).

    CRITICAL: Uses skeleton (not model) for hierarchy because model only contains
    faces for branches passing cutoff filters, while skeleton has ALL branches.

    Args:
        model: Grove model (legacy, kept for compatibility but not used)
        num_branches: Total number of branches in the tree (from skeleton poly_lines)
        skeleton: Grove skeleton object - REQUIRED for hierarchy derivation

    Returns:
        Dictionary with "parents" and "children" attribute structures
    """
    if skeleton is None:
        # Fallback: return empty/self-referencing hierarchy
        logger.warning("No skeleton provided, using default hierarchy")
        parents_values = [[i] for i in range(num_branches)]
        return {
            "parents": {
                "isArray": True,
                "size": 1,
                "type": "int",
                "values": parents_values,
            },
            "children": {
                "isArray": True,
                "size": 1,
                "type": "int",
                "values": [[] for _ in range(num_branches)],
            },
        }

    # Derive immediate parents from skeleton poly_line connectivity
    immediate_parents = _derive_parents_from_skeleton(skeleton)

    # Build full parent chain and children arrays
    parents_values = []
    children_arrays = [[] for _ in range(num_branches)]

    for branch_idx in range(num_branches):
        parent_idx = (
            immediate_parents[branch_idx] if branch_idx < len(immediate_parents) else -1
        )

        if parent_idx == -1:
            # Root branch - self-reference (PVE format uses [branch_idx] not [-1])
            parents_values.append([branch_idx])
        else:
            # Build full ancestor chain: [immediate_parent, grandparent, ..., root]
            chain = []
            current = branch_idx
            visited = set()
            while (
                current >= 0
                and current < len(immediate_parents)
                and current not in visited
            ):
                parent = immediate_parents[current]
                if parent == -1:
                    # Reached root - add root (which is current) to chain
                    chain.append(current)
                    break
                chain.append(parent)
                visited.add(current)
                current = parent

            parents_values.append(chain)

            # Add this branch as child of its immediate parent
            if 0 <= parent_idx < num_branches:
                children_arrays[parent_idx].append(branch_idx)

    return {
        "parents": {
            "isArray": True,
            "size": 1,
            "type": "int",
            "values": parents_values,
        },
        "children": {
            "isArray": True,
            "size": 1,
            "type": "int",
            "values": children_arrays,
        },
    }


def get_branch_generation(
    model: Any, num_branches: int, skeleton: Any | None = None
) -> list[int]:
    """
    Calculate generation number for each branch.

    Generation 0 = trunk, 1 = primary branches, 2 = secondary, etc.

    CRITICAL: Uses skeleton (not model) because model only contains faces for
    branches passing cutoff filters, while skeleton has ALL branches.

    Args:
        model: Grove model object (legacy, kept for compatibility)
        num_branches: Total number of branches (from skeleton poly_lines)
        skeleton: Grove skeleton object - REQUIRED for generation calculation

    Returns:
        List of generation numbers per branch
    """
    if skeleton is None:
        # Fallback: all branches at generation 0
        logger.warning("No skeleton provided, using generation 0 for all")
        return [0] * num_branches

    # Derive parents from skeleton
    immediate_parents = _derive_parents_from_skeleton(skeleton)

    # Calculate generations by counting ancestors to root
    generations = [0] * num_branches

    for branch_idx in range(num_branches):
        if branch_idx >= len(immediate_parents):
            continue

        # Count depth to root
        depth = 0
        current = branch_idx
        visited = set()
        while (
            current >= 0 and current < len(immediate_parents) and current not in visited
        ):
            parent = immediate_parents[current]
            if parent == -1:
                break  # Reached root
            depth += 1
            visited.add(current)
            current = parent

        generations[branch_idx] = depth

    return generations
