"""
GrowPy - Lightweight CSV to tree generation using The Grove 2.2
==============================================================

Simplified interface for generating procedural trees from CSV data.
Leverages Grove 2.2's existing functionality with minimal overhead.

Key Features:
- Automatic age prediction pipeline from height data only
- Direct use of Grove's build_models() for individual tree generation
- Leverages Grove's built-in preset system for species
- Implements Grove's recommended approach for mixed species forests
- Single CSV input (demo_forest.csv) with only essential data: x, y, z, species, height

Example Usage:
    from growpy import GrowPyConfig, ModelFormat
    from growpy.simulation import create_forest_from_csv, simulate_forest_growth
    from growpy.exporters import export_grove_json_files, export_individual_tree_models

    # Complete pipeline from demo_forest.csv (no age column needed)
    config = GrowPyConfig()
    forest = create_forest_from_csv(csv_path, config)  # Automatically predicts ages from heights
    simulate_forest_growth(forest, config)
    export_grove_json_files(forest, config.output_dir)
    export_individual_tree_models(forest, config.output_dir, config.get_lod_configs())
"""

from .config import GrowPyConfig
from .exporters import ModelFormat

__version__ = "2.1.0"
__author__ = "GrowPy Team"

__all__ = [
    # Configuration
    "GrowPyConfig",
    "ModelFormat",
]
