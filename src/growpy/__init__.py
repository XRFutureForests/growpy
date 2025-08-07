"""
GrowPy - Enhanced Grove API Integration for The Grove 2.2
=========================================================

Comprehensive Grove API integration for creating forests with full feature support:
- Proper Grove model building with comprehensive parameters
- Skeletal animation support using Grove's skeleton system
- Face-based twig placement using Grove's attribute system
- Material and texture integration with species-specific settings
- Multi-LOD export with full Grove attribute preservation
- Wind animation generation for dynamic forests

Enhanced Grove API Features:
- grove.build_models() with comprehensive build parameters
- grove.build_skeletons() for animation support
- model.set_up_axis("Z") and model.set_winding_order("COUNTER_CLOCKWISE")
- model.apply_uv_aspect_ratio() for texture correction
- gc.io.model_to_usda_string() for proper USD export
- Face attribute system for twig placement

Core Workflow:
1. Load CSV with tree positions, species, heights
2. Calculate growth cycles from heights using growth models
3. Create multi-species forest with enhanced attributes
4. Simulate growth with proper Grove light competition
5. Build comprehensive LOD models with full Grove parameters
6. Generate skeletal rigs with Grove's skeleton system
7. Export to USD with all Grove attributes and skeleton data
8. Integrate Grove's face-based twig system

Usage:
    from growpy import *

    # Enhanced configuration
    config = GrowPyConfig()
    set_global_config(config)

    # Load and process CSV with growth models
    forest_data = pd.read_csv("trees.csv")
    calculate_growth_cycles_from_height(forest_data)

    # Create enhanced forest with attributes
    forest = create_forest_with_attributes(forest_data)
    simulate_forest_growth(forest, cycles=20)

    # Build comprehensive models with Grove API
    lod_configs = config.get_lod_configs()
    for grove, species_name, tree_count, attributes in forest:
        # Build with full Grove parameters
        lod_models = build_lod_models(grove, lod_configs, texture_aspect_ratio=1.2)

        # Build skeletons for animation
        skeletons = build_tree_skeletons(grove, optimize_bones=True)

        # Export with comprehensive Grove features
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                # Apply species-specific settings
                apply_species_texture_settings(model, species_name, config)

                # Export with skeleton data
                save_tree_with_skeleton(model, skeletons[i], output_path)

                # Integrate Grove twig system
                add_twigs_to_grove_model(model, species_name, config)
"""

from .config import GrowPyConfig, get_config, set_global_config
from .forest import create_forest, create_forest_with_attributes, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    apply_species_texture_settings,
    build_grove_with_all_attributes,
    build_lod_models,
    build_tree_skeletons,
    calculate_growth_cycles_from_height,
    create_skeleton_lod_models,
    export_forest_with_skeletons,
    generate_wind_animation,
    get_model_attributes,
    get_skeleton_info,
    save_tree_to_usd,
    save_tree_with_skeleton,
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
    "build_tree_skeletons",
    "build_grove_with_all_attributes",
    "create_skeleton_lod_models",
    "export_forest_with_skeletons",
    "generate_wind_animation",
    "get_skeleton_info",
    "get_model_attributes",
    "save_tree_to_usd",
    "save_tree_with_skeleton",
    "apply_species_texture_settings",
    # Grove twig integration (if available)
    "add_twigs_to_grove_model",
    "extract_twig_data_from_grove_model",
    "create_grove_compatible_twig_usd",
    "GROVE_TWIG_AVAILABLE",
]
