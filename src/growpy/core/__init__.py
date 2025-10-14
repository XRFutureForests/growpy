"""
Core simulation logic for GrowPy.

Forest/Grove/Tree hierarchy for multi-species tree generation using The Grove 2.2 API.

Key Functions:
    create_forest()              Create forest from CSV data
    simulate_forest_growth()     Simulate growth with light competition
    create_grove()               Create single-species grove
    build_grove_with_all_attributes()  Build tree geometry
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

from .forest import create_forest, create_forest_with_attributes, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_skeletons,
    calculate_growth_cycles_from_height,
    get_model_attributes,
)

__all__ = [
    # Grove operations
    "create_grove",
    "add_tree_to_grove",
    # Tree model building
    "build_grove_with_all_attributes",
    "build_skeletons",
    "get_model_attributes",
    "apply_species_color_settings",
    "calculate_growth_cycles_from_height",
    # Forest creation and simulation
    "create_forest",
    "create_forest_with_attributes",
    "simulate_forest_growth",
]
