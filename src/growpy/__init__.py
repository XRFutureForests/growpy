"""
GrowPy - Hierarchical Modular Interface for The Grove 2.2
=========================================================

Clean, hierarchical procedural tree generation using Grove's core functionality with
comprehensive configuration management and asset handling.

Module Structure:
- config: Configuration management with LOD presets and species lookup
- forest: Forest-level operations (collections of groves)
- grove: Grove-level operations (collections of trees)
- tree: Individual tree and model management
- twig: Lowest-level twig handling and USD integration

Key Features:
- Hierarchical, modular design for clear separation of concerns
- Direct Grove core integration without abstraction layers
- Native USD export using Grove's built-in capabilities
- Comprehensive asset management via GrowPyConfig
- Species lookup and asset path resolution
- LOD (Level of Detail) configuration system
- Performance-optimized with minimal overhead

Quick Start:
    from growpy import GrowPyConfig, create_forest, simulate_forest_growth

    # Configuration-driven workflow with global config
    config = GrowPyConfig()  # Automatically becomes global config
    print(f"Available species: {config.get_available_species()}")
    
    # All functions automatically use global config
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, cycles=20)
    
    # Functions automatically use global config for LOD settings
    save_tree_models(grove, species_name, output_dir)
"""

from .config import GrowPyConfig, get_global_config, set_global_config
from .forest import calculate_shared_shade, create_forest, simulate_forest_growth
from .grove import (
    add_tree_to_grove,
    apply_species_preset,
    create_grove,
    save_grove_to_json,
)
from .tree import (
    build_lod_models,
    calculate_growth_cycles_from_height,
    save_tree_to_usd,
)
from .twig import (
    add_twigs_to_model_usd,
    generate_forest_with_twigs,
    get_species_twig_mapping,
    get_twig_for_species,
    get_twig_usd_paths,
    list_available_twigs,
    load_twig_conversion_report,
    load_twig_lookup_table,
    save_model_with_twigs_to_usd,
)
