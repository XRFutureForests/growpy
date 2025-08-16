"""
GrowPy - Enhanced Grove API Integration for The Grove 2.2

Comprehensive Grove API integration for creating forests with full feature support including
proper Grove model building, skeletal animation, face-based twig placement, material and
texture integration, multi-LOD export, and wind animation generation.

See individual module documentation for detailed usage examples.
"""

from .config import GrowPyConfig, get_config, set_global_config
from .forest import create_forest, create_forest_with_attributes, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    add_bone_ids_to_model,
    apply_species_texture_settings,
    build_grove_with_all_attributes,
    build_lod_models,
    build_tree_skeletons,
    calculate_growth_cycles_from_height,
    can_species_have_twigs,
    create_skeleton_lod_models,
    export_forest_with_skeletons,
    generate_wind_animation,
    get_model_attributes,
    get_skeleton_info,
    save_tree_to_usd,
    save_tree_to_usd_with_twigs,
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

# Import root system generation
try:
    from .roots import (
        RootArchitecture,
        create_root_system,
        get_species_root_type,
        get_species_root_examples,
        print_root_architecture_guide,
        build_root_models,
        save_root_system_to_usd,
        create_combined_tree_with_roots,
        add_roots_to_forest,
    )

    GROVE_ROOTS_AVAILABLE = True
except ImportError:
    GROVE_ROOTS_AVAILABLE = False
    RootArchitecture = None
    create_root_system = None
    get_species_root_type = None
    get_species_root_examples = None
    print_root_architecture_guide = None
    build_root_models = None
    save_root_system_to_usd = None
    create_combined_tree_with_roots = None
    add_roots_to_forest = None

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
    "add_bone_ids_to_model",
    "calculate_growth_cycles_from_height",
    "build_lod_models",
    "build_tree_skeletons",
    "build_grove_with_all_attributes",
    "can_species_have_twigs",
    "create_skeleton_lod_models",
    "export_forest_with_skeletons",
    "generate_wind_animation",
    "get_skeleton_info",
    "get_model_attributes",
    "save_tree_to_usd",
    "save_tree_to_usd_with_twigs",
    "save_tree_with_skeleton",
    "apply_species_texture_settings",
    # Grove twig integration (if available)
    "add_twigs_to_grove_model",
    "extract_twig_data_from_grove_model",
    "create_grove_compatible_twig_usd",
    "GROVE_TWIG_AVAILABLE",
    # Root system generation (if available)
    "RootArchitecture",
    "create_root_system",
    "get_species_root_type",
    "get_species_root_examples",
    "print_root_architecture_guide",
    "build_root_models",
    "save_root_system_to_usd",
    "create_combined_tree_with_roots",
    "add_roots_to_forest",
    "GROVE_ROOTS_AVAILABLE",
]
