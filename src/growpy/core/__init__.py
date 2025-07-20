"""
Core functionality for GrowPy - atomic, single-responsibility functions.
"""

from .grove import create_grove, add_tree_to_grove, apply_species_preset
from .height import calculate_tree_height, generate_height_curve
from .predict import create_prediction_model, predict_cycles_from_height
from .validate import validate_csv_data, validate_forest_data
from .config import GrowPyConfig
from .species import list_species, apply_species_preset
from .mapping import (
    SpeciesMapper, SpeciesAssets, get_species_mapper,
    get_species_assets, get_model_template, get_twig_name, get_bark_texture
)

__all__ = [
    # Configuration
    "GrowPyConfig",
    # Species utilities
    "list_species",
    "apply_species_preset",
    # Species mapping
    "SpeciesMapper",
    "SpeciesAssets", 
    "get_species_mapper",
    "get_species_assets",
    "get_model_template",
    "get_twig_name",
    "get_bark_texture",
    # Grove operations
    "create_grove",
    "add_tree_to_grove", 
    # Height calculations
    "calculate_tree_height",
    "generate_height_curve",
    # Prediction models
    "create_prediction_model",
    "predict_cycles_from_height",
    # Validation
    "validate_csv_data",
    "validate_forest_data",
]