"""
GrowPy - A Python module for generating forest models from CSV data using The Grove 2.2

This module provides a simple interface to The Grove's procedural tree generation system,
allowing users to create realistic 3D tree models from CSV data containing tree positions,
species, and growth parameters.

Main functions:
- grow_forest_from_csv: Generate individual tree models from CSV data
- grow_combined_forest_from_csv: Generate a single combined forest model
"""

from .growpy import (
    grow_forest_from_csv,
    grow_combined_forest_from_csv,
    list_available_species,
    validate_csv_format,
)

__version__ = "1.0.0"
__author__ = "The Grove Project"

__all__ = [
    "grow_forest_from_csv",
    "grow_combined_forest_from_csv",
    "list_available_species",
    "validate_csv_format",
]
