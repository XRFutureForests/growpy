"""
Core simulation logic for GrowPy.

Forest/Grove/Tree hierarchy for multi-species tree generation using The Grove 2.3 API.

Key Functions:
    create_forest()              Create forest from CSV data
    simulate_forest_growth()     Simulate growth with light competition
    create_grove()               Create single-species grove
    calculate_growth_cycles_from_height()  Convert height to age

Example:
    import pandas as pd
    from growpy.core import create_forest, simulate_forest_growth

    # Load forest data
    forest_data = pd.read_csv('forest.csv')  # x, y, species, height

    # Create and simulate
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, max_cycles=10)

    # Access groves by species
    for species, grove in forest.items():
        print(f"{species}: {len(grove.all_trees)} trees")
"""

from .forest import (
    create_forest,
    simulate_forest_growth,
    simulate_forest_growth_with_snapshots,
)
from .grove import create_grove, grow_and_build_roots
from .skeleton import (
    UNREAL_MAX_BONE_INDEX,
    JointTransform,
    SkeletonHierarchy,
    Vector3,
    build_skeleton_hierarchy,
    calculate_vertex_weights,
    filter_bones_for_mesh,
    get_bone_data_from_grove,
)
from .tree import (
    calculate_dbh_at_height,
    calculate_growth_cycles_from_height,
    calculate_tree_height,
    extract_grove_attributes,
    extract_tree_measurements,
)
from .twig import (
    TwigPlacement,
    extract_twig_placements_from_model,
    get_face_center_and_normal,
    normal_to_rotation_matrix,
)

__all__ = [
    # Core functions used by CLI
    "create_grove",
    "calculate_growth_cycles_from_height",
    "create_forest",
    "simulate_forest_growth",
    "simulate_forest_growth_with_snapshots",
    # Tree measurement functions
    "calculate_tree_height",
    "calculate_dbh_at_height",
    "extract_tree_measurements",
    "extract_grove_attributes",
    # Grove helpers
    "grow_and_build_roots",
    # Skeleton
    "Vector3",
    "JointTransform",
    "SkeletonHierarchy",
    "UNREAL_MAX_BONE_INDEX",
    "build_skeleton_hierarchy",
    "calculate_vertex_weights",
    "filter_bones_for_mesh",
    "get_bone_data_from_grove",
    # Twig
    "TwigPlacement",
    "extract_twig_placements_from_model",
    "get_face_center_and_normal",
    "normal_to_rotation_matrix",
]
