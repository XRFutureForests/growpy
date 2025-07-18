"""
Core tree utility functions.
"""

import the_grove_22_core as gc


def calculate_tree_height(grove: gc.Grove, tree_index: int = 0) -> float:
    if not grove.trees:
        raise ValueError("Grove contains no trees")
    if tree_index < 0 or tree_index >= len(grove.trees):
        raise ValueError(
            f"Invalid tree index {tree_index}. Grove has {len(grove.trees)} trees"
        )
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        if not hasattr(branch, "nodes"):
            return
        for node in branch.nodes:
            if hasattr(node, "pos") and hasattr(node.pos, "z"):
                if node.pos.z > max_z:
                    max_z = node.pos.z
            if hasattr(node, "side_branches"):
                for side_branch in node.side_branches:
                    traverse_branch(side_branch)

    traverse_branch(grove.trees[tree_index])
    return max_z
