"""
GrowPy - Enhanced Hierarchical Interface for The Grove 2.2
==========================================================

Clean, production-ready procedural tree generation using Grove's core functionality with
comprehensive configuration management, multi-species simulation, and advanced features
discovered from The Grove's Blender addon.

Module Structure:
- config: Configuration management with LOD presets and species lookup
- forest: Multi-species forest simulation with light competition
- grove: Grove-level operations with advanced serialization and physics
- tree: Model building with full attribute access and animation support
- twig: Twig handling and USD integration
- properties: Advanced property management (optional)

Enhanced Features (from Blender addon analysis):
- Multi-grove light competition simulation
- Compressed grove serialization with fallback support
- Advanced model building with spring shapes for animation
- Complete model attribute access (age, thickness, photosynthesis, etc.)
- Physics-aware simulation with property synchronization
- Platform-specific core import with graceful fallbacks
- Production-level error handling and validation

Core Features:
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
    simulate_forest_growth(forest, cycles=20, enable_light_competition=True)

    # Advanced property management (optional)
    from growpy import properties
    properties.modify_grove_properties(grove, favor_bright=0.9, turn_to_light=0.3)
"""

from .config import GrowPyConfig, get_global_config, set_global_config
from .forest import (
    calculate_shared_shade, 
    create_forest, 
    simulate_forest_growth,
    save_forest_state,
)
from .grove import (
    add_tree_to_grove,
    apply_species_preset,
    create_grove,
    save_grove_to_json,
    load_grove_from_file,
    get_grove_properties,
    set_grove_properties,
    update_physics,
    simulate_grove_growth,
)
from .tree import (
    build_lod_models,
    build_spring_models,
    calculate_growth_cycles_from_height,
    get_model_attributes,
    save_tree_to_usd,
)

# Optional advanced modules - import on demand to maintain minimalistic approach
try:
    from . import properties  # Advanced property management
except ImportError:
    properties = None
