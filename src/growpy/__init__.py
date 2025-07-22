"""
GrowPy - Simplified atomic functions for The Grove 2.2
======================================================

Clean, atomic procedural tree generation using Grove's core functionality.

Key Features:
- Atomic, single-purpose functions for easy composition
- Direct Grove core integration without abstraction layers
- Native USD export using Grove's built-in capabilities
- Minimal API focused on essential functionality
- Performance-optimized with minimal overhead

Quick Start:
    from growpy import GrowPyConfig, create_forest_groves, simulate_forest_growth
    from growpy.models import save_forest_groves_json, save_forest_usd_models

    # Simple atomic workflow
    config = GrowPyConfig()
    forest_groves = create_forest_groves(forest_data)
    simulate_forest_growth(forest_groves, cycles=20)
    # Export using Grove's native capabilities
"""

from .config import GrowPyConfig
from .forest import create_forest_groves, simulate_forest_growth
from .grove import (
    add_tree_to_grove,
    apply_species_preset,
    calculate_shared_shade,
    create_grove,
    list_species,
    load_grove_from_json,
    save_grove_to_json,
)
from .growth_model import calculate_growth_cycles_from_height
from .models import (
    save_forest_groves_json,
    save_forest_usd_models,
    save_model_to_usd,
    save_model_usd,
)
from .twigs import (
    add_twigs_to_model_usd,
    generate_forest_with_twigs,
    get_species_twig_mapping,
    get_twig_for_species,
    get_twig_usd_paths,
    list_available_twigs,
    load_twig_conversion_report,
    load_twig_lookup_table,
    save_model_with_twigs_to_usd,
)

__all__ = [
    # Core Grove operations
    "list_species",
    "create_grove",
    "apply_species_preset",
    "add_tree_to_grove",
    "calculate_shared_shade",
    "save_grove_to_json",
    "load_grove_from_json",
    # Model operations
    "save_model_to_usd",
    "save_model_usd",
    "save_forest_groves_json",
    "save_forest_usd_models",
    # Configuration
    "GrowPyConfig",
    # Forest operations
    "create_forest_groves",
    "simulate_forest_growth",
    # Cycle prediction
    "calculate_growth_cycles_from_height",
    # Twig operations
    "add_twigs_to_model_usd",
    "generate_forest_with_twigs",
    "get_species_twig_mapping",
    "get_twig_for_species",
    "get_twig_usd_paths",
    "list_available_twigs",
    "load_twig_conversion_report",
    "load_twig_lookup_table",
    "save_model_with_twigs_to_usd",
]
