"""
GrowPy - Grove API Integration for Unreal Engine 5 Nanite.

A Python package for generating procedural forests using The Grove 2.3 API
and exporting to USD/USDA formats optimized for Unreal Engine 5 Nanite.

Quick Start:
    from growpy import create_forest, simulate_forest_growth, get_config
    import pandas as pd

    # Create forest from CSV
    forest_data = pd.read_csv('forest.csv')  # x, y, species, height
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, max_cycles=10)

Key Features:
    - Multi-species forest simulation with light competition
    - USD/USDA export with skeleton support for wind animation
    - Nanite Assembly USD for Unreal Engine 5.7+
    - Growth models for automatic height-to-age conversion
    - Twig instancing with PointInstancer prims

Main Components:
    Core:       create_forest, simulate_forest_growth, create_grove
    Export:     build_tree_mesh, create_assembly
    Config:     GrowPyConfig, get_config

CLI Tools:
    prepare_assets.py          - Copy assets from Grove 2.3
    convert_twigs.py           - Convert .blend twigs to USD
    create_growth_models.py    - Generate species growth models
    generate_forest.py         - Full forest generation pipeline

Documentation:
    See docs/growpy/README.md for complete documentation
    See docs/guides/cli-reference.md for CLI usage
    See docs/GETTING_STARTED.md for quick setup

Requirements:
    - The Grove 2.3 (commercial license required)
    - Python 3.9+
    - bpy module (conda install -c conda-forge bpy)
    - pandas, numpy, joblib
"""

# Lightweight imports (no heavy dependencies)
from .config import GrowPyConfig, get_config

__all__ = [
    # Core configuration
    "GrowPyConfig",
    "get_config",
    # Forest creation and simulation (lazy)
    "create_forest",
    "simulate_forest_growth",
    # Grove operations (lazy)
    "create_grove",
    # Tree model building (lazy)
    "calculate_growth_cycles_from_height",
]


def __getattr__(name):
    """Lazy import for heavy dependencies (bpy, the_grove_23_core)."""
    if name in (
        "create_forest",
        "simulate_forest_growth",
        "create_grove",
        "calculate_growth_cycles_from_height",
    ):
        from .core import (
            calculate_growth_cycles_from_height,
            create_forest,
            create_grove,
            simulate_forest_growth,
        )

        return locals()[name]

    raise AttributeError(f"module 'growpy' has no attribute {name!r}")
