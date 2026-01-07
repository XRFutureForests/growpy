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
        num_branches: Total number of branches in the tree (from skeleton poly_lines)

    Returns:
        Dictionary with "parents" and "children" attribute structures
    """
    # Extract branch parent relationships from model face attributes
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping using raw branch IDs
    # Note: branch IDs may not be consecutive 0 to N-1
    branch_to_parent_raw = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent_raw:
            branch_to_parent_raw[branch_id] = parent_id

    # Build remapping from model branch IDs to skeleton indices (0 to num_branches-1)
    # Skeleton poly_lines are indexed 0 to num_branches-1
    # We need to map sparse model branch IDs to this dense range
    unique_branch_ids = sorted(set(branch_ids))
    branch_id_to_idx = {bid: idx for idx, bid in enumerate(unique_branch_ids)}

    # Build parents array and children tracking
    parents_values = []
    children_arrays = [[] for _ in range(num_branches)]

    for branch_idx in range(num_branches):
        # Get the original branch ID for this index if it exists
        if branch_idx < len(unique_branch_ids):
            original_branch_id = unique_branch_ids[branch_idx]
            parent_raw = branch_to_parent_raw.get(original_branch_id, -1)

            # Remap parent to index
            if parent_raw == -1 or parent_raw not in branch_id_to_idx:
                parent_idx = -1
            else:
                parent_idx = branch_id_to_idx[parent_raw]
        else:
            parent_idx = -1

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
        num_branches: Total number of branches (from skeleton poly_lines)

    Returns:
        List of generation numbers per branch
    """
    # Extract branch parent relationships from model
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping using raw branch IDs
    branch_to_parent_raw = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent_raw:
            branch_to_parent_raw[branch_id] = parent_id

    # Build remapping from model branch IDs to skeleton indices (0 to num_branches-1)
    unique_branch_ids = sorted(set(branch_ids))
    branch_id_to_idx = {bid: idx for idx, bid in enumerate(unique_branch_ids)}

    # Calculate generations
    generations = [0] * num_branches

    # Iteratively calculate generations (handle cycles safely)
    max_iterations = num_branches
    for _ in range(max_iterations):
        changed = False
        for branch_idx in range(num_branches):
            # Get original branch ID for this index
            if branch_idx < len(unique_branch_ids):
                original_branch_id = unique_branch_ids[branch_idx]
                parent_raw = branch_to_parent_raw.get(original_branch_id, -1)

                # Remap parent to index
                if parent_raw == -1 or parent_raw not in branch_id_to_idx:
                    parent_idx = -1
                else:
                    parent_idx = branch_id_to_idx[parent_raw]
            else:
                parent_idx = -1

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
