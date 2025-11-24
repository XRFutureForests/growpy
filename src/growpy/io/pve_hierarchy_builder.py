"""
Build parent/child hierarchy arrays for PVE preset primitives.

Extracts branch relationship data from Grove model face attributes.
"""

from typing import Any, Dict, List


def build_hierarchy_arrays(model: Any, num_branches: int) -> Dict[str, Dict]:
    """
    Build parent and children arrays from Grove model branch IDs.

    Args:
        model: Grove model object with face_attribute_branch_id and face_attribute_branch_id_parent
        num_branches: Total number of branches in the tree

    Returns:
        Dictionary with "parents" and "children" attribute structures
    """
    # Extract branch parent relationships from model face attributes
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping
    branch_to_parent = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent:
            branch_to_parent[branch_id] = parent_id

    # Build parents array and children tracking
    parents_values = []
    children_arrays = [[] for _ in range(num_branches)]

    for branch_idx in range(num_branches):
        parent_idx = branch_to_parent.get(branch_idx, -1)

        if parent_idx == -1:
            # Root branch - no parent
            parents_values.append([-1])
        else:
            # Has parent
            parents_values.append([parent_idx])
            # Add this branch as child of parent
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


def get_branch_generation(model: Any, num_branches: int) -> List[int]:
    """
    Calculate generation number for each branch.

    Generation 0 = trunk, 1 = primary branches, 2 = secondary, etc.

    Args:
        model: Grove model object with face_attribute_branch_id_parent
        num_branches: Total number of branches

    Returns:
        List of generation numbers per branch
    """
    # Extract branch parent relationships from model
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping
    branch_to_parent = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent:
            branch_to_parent[branch_id] = parent_id

    # Calculate generations
    generations = [0] * num_branches

    # Iteratively calculate generations (handle cycles safely)
    max_iterations = num_branches
    for _ in range(max_iterations):
        changed = False
        for branch_idx in range(num_branches):
            parent_idx = branch_to_parent.get(branch_idx, -1)
            if parent_idx == -1:
                generations[branch_idx] = 0  # Root
            elif 0 <= parent_idx < num_branches:
                # Generation is parent's generation + 1
                new_gen = generations[parent_idx] + 1
                if new_gen != generations[branch_idx]:
                    generations[branch_idx] = new_gen
                    changed = True

        if not changed:
            break

    return generations
