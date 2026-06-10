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
