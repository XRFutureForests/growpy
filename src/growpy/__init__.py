"""
GrowPy - Grove API Integration for Unreal Engine 5 Nanite.

A Python package for generating procedural forests using The Grove 2.2 API
and exporting to FBX/USD formats optimized for Unreal Engine 5 Nanite.

Quick Start:
    from growpy import create_forest, simulate_forest_growth, get_config
    import pandas as pd

    # Create forest from CSV
    forest_data = pd.read_csv('forest.csv')  # x, y, species, height
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, max_cycles=10)

Key Features:
    - Multi-species forest simulation with light competition
    - FBX/USD export with skeleton support for wind animation
    - Nanite Assembly USD for Unreal Engine 5.7+
    - Growth models for automatic height-to-age conversion
    - Twig instancing with PointInstancer prims

Main Components:
    Core:       create_forest, simulate_forest_growth, create_grove
    Export:     export_tree_as_usd, batch_export_trees_for_unreal
    Config:     GrowPyConfig, get_config

CLI Tools:
    prepare_assets.py          - Copy assets from Grove 2.2
    convert_twigs.py           - Convert .blend twigs to FBX/USD
    create_growth_models.py    - Generate species growth models
    generate_forest.py         - Full forest generation pipeline
    generate_species_library.py - Export template trees

Documentation:
    See docs/growpy/README.md for complete documentation
    See docs/guides/cli-reference.md for CLI usage
    See docs/GETTING_STARTED.md for quick setup

Requirements:
    - The Grove 2.2 (commercial license required)
    - Python 3.8+
    - bpy module (conda install -c conda-forge bpy)
    - pandas, numpy, scikit-learn, matplotlib
"""

# Pre-import bpy if available to avoid DLL conflicts with the_grove_22_core
try:
    import bpy as _bpy_preload
except (ImportError, OSError):
    _bpy_preload = None

# Import from new structure
from .config import GrowPyConfig, get_config, set_global_config
from .core import (
    add_tree_to_grove,
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_skeletons,
    calculate_growth_cycles_from_height,
    create_forest,
    create_forest_with_attributes,
    create_grove,
    get_model_attributes,
    simulate_forest_growth,
)
from .io import (
    EXPORT_AVAILABLE,
    batch_export_tree_usd,
    batch_export_trees_for_unreal,
    create_nanite_assembly_usd,
    export_tree_as_usd,
    export_twigs_from_blend,
)

__all__ = [
    # Core configuration
    "GrowPyConfig",
    "get_config",
    "set_global_config",
    # Forest creation and simulation
    "create_forest",
    "create_forest_with_attributes",
    "simulate_forest_growth",
    # Grove operations
    "create_grove",
    "add_tree_to_grove",
    # Tree model building
    "build_grove_with_all_attributes",
    "build_skeletons",
    "get_model_attributes",
    "apply_species_color_settings",
    "calculate_growth_cycles_from_height",
    # Export functionality (if available)
    "export_tree_as_usd",
    "export_twigs_from_blend",
    "batch_export_tree_usd",
    "batch_export_trees_for_unreal",
    "create_nanite_assembly_usd",
    "EXPORT_AVAILABLE",
]
