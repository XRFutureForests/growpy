"""
GrowPy - Grove API Integration for The Grove 2.2

Grove API integration for creating forests with base model creation, twig placement,
and color integration for natural-looking tree models.

See individual module documentation for detailed usage examples.
"""

from .config import GrowPyConfig, get_config, set_global_config
from .forest import create_forest, create_forest_with_attributes, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_lod_models,
    calculate_growth_cycles_from_height,
    can_species_have_twigs,
    get_model_attributes,
    save_tree_to_usd,
    save_tree_to_usd_with_twigs,
)

# Import Grove twig integration if available
try:
    from .twig import (
        add_twigs_to_grove_model,
        create_grove_compatible_twig_usd,
        extract_twig_data_from_grove_model,
    )

    GROVE_TWIG_AVAILABLE = True
except ImportError:
    GROVE_TWIG_AVAILABLE = False
    add_twigs_to_grove_model = None
    extract_twig_data_from_grove_model = None
    create_grove_compatible_twig_usd = None


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
    # Tree model building and export
    "calculate_growth_cycles_from_height",
    "build_lod_models",
    "build_grove_with_all_attributes",
    "can_species_have_twigs",
    "get_model_attributes",
    "save_tree_to_usd",
    "save_tree_to_usd_with_twigs",
    "apply_species_color_settings",
    # Grove twig integration (if available)
    "add_twigs_to_grove_model",
    "extract_twig_data_from_grove_model",
    "create_grove_compatible_twig_usd",
    "GROVE_TWIG_AVAILABLE",
]
