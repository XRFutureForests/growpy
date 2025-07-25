"""
GrowPy - Minimal Forest Simulation for The Grove 2.2
====================================================

Essential functions for creating forests from CSV data with multi-species
light competition, then exporting to USD with twig enhancements.

Core Workflow:
1. Load CSV with tree positions, species, heights
2. Calculate growth cycles from heights
3. Create multi-species forest (separate groves per species)
4. Simulate growth with light competition
5. Build LOD models and export to USD
6. Add twig instances

Usage:
    from growpy import *

    # Load and process CSV
    forest_data = pd.read_csv("trees.csv")
    calculate_growth_cycles_from_height(forest_data)

    # Create and simulate forest
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, cycles=20)

    # Export to USD with enhancements
    lod_configs = config.get_lod_configs()
    for grove, species_name, _ in forest:
        lod_models = build_lod_models(grove, lod_configs)
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                save_tree_to_usd(model, f"{species_name}_{lod_name}_{i:03d}.usda")

    # Add enhancements
    twig.batch_add_twig_instances_to_usd_directory(output_dir)
"""

from . import twig
from .config import GrowPyConfig, get_config
from .forest import create_forest, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    build_lod_models,
    calculate_growth_cycles_from_height,
    save_tree_to_usd,
)

__all__ = [
    "GrowPyConfig",
    "get_config",
    "create_forest",
    "simulate_forest_growth",
    "create_grove",
    "add_tree_to_grove",
    "calculate_growth_cycles_from_height",
    "build_lod_models",
    "save_tree_to_usd",
    "twig",
]
