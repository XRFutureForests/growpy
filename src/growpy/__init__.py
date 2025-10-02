"""GrowPy - Grove API Integration for Unreal Engine 5 Nanite"""

# Pre-import bpy if available to avoid DLL conflicts with the_grove_22_core
try:
    import bpy as _bpy_preload
except (ImportError, OSError):
    _bpy_preload = None

# Import from new structure
from .config import GrowPyConfig, get_config, set_global_config
from .core import (
    create_forest,
    create_forest_with_attributes,
    simulate_forest_growth,
    add_tree_to_grove,
    create_grove,
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_skeletons,
    get_model_attributes,
    calculate_growth_cycles_from_height,
)
from .io import (
    export_tree_as_usd,
    export_twigs_from_blend,
    batch_export_tree_usd,
    batch_export_trees_for_unreal,
    create_nanite_assembly_usd,
    EXPORT_AVAILABLE,
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
