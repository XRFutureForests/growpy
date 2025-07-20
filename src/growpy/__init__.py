"""
GrowPy - Clean, modular interface for The Grove 2.2
===================================================

A streamlined, atomic approach to procedural tree generation from CSV data.
Designed for clarity, maintainability, and ease of use.

Key Features:
- Atomic, single-responsibility functions
- Clear separation of concerns across modules
- Automatic age prediction from height data
- Flexible workflows for different use cases
- Comprehensive validation and error handling

Quick Start:
    from growpy import GrowPyConfig
    from growpy.workflows import create_forest_from_csv, simulate_forest_growth
    from growpy.workflows import export_grove_jsons, export_individual_models

    # Complete pipeline
    config = GrowPyConfig()
    forest_data, data = create_forest_from_csv(csv_path)
    simulate_forest_growth(forest_data)
    export_grove_jsons(forest_data, config.output_dir)
    export_individual_models(forest_data, config.output_dir)
"""

from .core.config import GrowPyConfig

# Import key classes for convenience
from .workflows import create_forest_from_csv, simulate_forest_growth
from .workflows import export_grove_jsons, export_individual_models
from .workflows import analyze_species_heights, create_height_models

__version__ = "3.0.0"
__author__ = "GrowPy Team"

__all__ = [
    # Configuration
    "GrowPyConfig",
    # Main workflows
    "create_forest_from_csv",
    "simulate_forest_growth", 
    "export_grove_jsons",
    "export_individual_models",
    "analyze_species_heights",
    "create_height_models",
]
