"""Core simulation logic for GrowPy.

This module contains the core tree, grove, and forest simulation functionality.
"""

from .grove import create_grove, add_tree_to_grove
from .tree import (
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_skeletons,
    get_model_attributes,
    calculate_growth_cycles_from_height,
)
from .forest import (
    create_forest,
    create_forest_with_attributes,
    simulate_forest_growth,
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