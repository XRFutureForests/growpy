"""
Build parent/child hierarchy arrays for PVE preset primitives.

Extracts branch relationship data from Grove skeleton structure.
"""

from typing import Any, Dict, List


def build_hierarchy_arrays(skeleton: Any) -> Dict[str, Dict]:
    """
    Build parent and children arrays from Grove skeleton.

    Args:
        skeleton: Grove skeleton object with poly_lines

    Returns:
        Dictionary with "parents" and "children" attribute structures
    """
    num_branches = len(skeleton.poly_lines)

    # Build parents array (simple - each branch has one parent)
    parents_values = []
    children_arrays = [[] for _ in range(num_branches)]

    for branch_idx, poly_line in enumerate(skeleton.poly_lines):
        parent_idx = poly_line.parent_index

        if parent_idx == -1:
            # Root branch - no parent
            parents_values.append([-1])
        else:
            # Has parent
            parents_values.append([parent_idx])
            # Add this branch as child of parent
            children_arrays[parent_idx].append(branch_idx)

    return {
        "parents": {
            "isArray": True,
            "size": 1,
            "type": "int",
            "value": parents_values,
        },
        "children": {
            "isArray": True,
            "size": 1,
            "type": "int",
            "value": children_arrays,
        },
    }


def get_branch_generation(skeleton: Any) -> List[int]:
    """
    Calculate generation number for each branch.

    Generation 0 = trunk, 1 = primary branches, 2 = secondary, etc.

    Args:
        skeleton: Grove skeleton object

    Returns:
        List of generation numbers per branch
    """
    num_branches = len(skeleton.poly_lines)
    generations = [0] * num_branches

    # Build generation by traversing from roots
    for branch_idx, poly_line in enumerate(skeleton.poly_lines):
        parent_idx = poly_line.parent_index
        if parent_idx == -1:
            generations[branch_idx] = 0  # Root
        else:
            # Generation is parent's generation + 1
            generations[branch_idx] = generations[parent_idx] + 1

    return generations
