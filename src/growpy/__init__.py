"""
GrowPy - Lightweight CSV to tree generation using The Grove 2.2
==============================================================

Simplified interface for generating procedural trees from CSV data.
Leverages Grove 2.2's existing functionality with minimal overhead.

Key Features:
- Direct use of Grove's build_models() for individual tree generation
- Leverages Grove's built-in preset system for species
- Implements Grove's recommended approach for mixed species forests
- Minimal abstraction layer over Grove's core functionality

Example Usage:
    import growpy

    # Simple usage
    files = growpy.generate_trees("trees.csv")

    # Custom configuration
    config = growpy.GrowPyConfig(
        growth_cycles=15,
        resolution=32
    )
    files = growpy.generate_trees("trees.csv", config)
"""

from .config import GrowPyConfig, ExportFormat
from .growpy import generate_trees, list_species, get_grove_info, GrowPyError

__version__ = "2.0.0"
__author__ = "GrowPy Team"

__all__ = [
    # Main API
    "generate_trees",
    "list_species",
    "get_grove_info",
    # Configuration
    "GrowPyConfig",
    "ExportFormat",
    # Exceptions
    "GrowPyError",
]
