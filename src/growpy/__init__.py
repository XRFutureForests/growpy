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
    from growpy import GrowPyConfig, load_forest_csv, create_forest_groves, simulate_forest_growth
    from growpy.models import export_forest_groves_json, export_forest_usd_models
    
    # Simple atomic workflow
    config = GrowPyConfig()
    forest_data = load_forest_csv("forest.csv")
    forest_groves = create_forest_groves(forest_data)
    simulate_forest_growth(forest_groves, cycles=20)
    # Export using Grove's native capabilities
"""

from .cycle_prediction import calculate_growth_cycles_from_height
from .config import GrowPyConfig
from .forest import (
    create_forest_groves,
    get_forest_summary,
    load_forest_csv,
    simulate_forest_growth,
)
from .grove import (
    add_tree_to_grove,
    apply_species_preset,
    build_grove_models,
    calculate_shared_shade,
    create_grove,
    list_species,
    load_grove_from_json,
    save_grove_to_json,
    save_model_to_usd,
    simulate_grove,
)
from .validate import validate_csv_data

__all__ = [
    # Core Grove operations
    "list_species", "create_grove", "apply_species_preset", "add_tree_to_grove",
    "simulate_grove", "build_grove_models", "calculate_shared_shade",
    "save_grove_to_json", "load_grove_from_json", "save_model_to_usd",
    
    # Configuration
    "GrowPyConfig",
    
    # Validation
    "validate_csv_data",
    
    # Forest operations
    "load_forest_csv", "create_forest_groves", "simulate_forest_growth", "get_forest_summary",
    
    # Cycle prediction
    "calculate_growth_cycles_from_height"
]