"""
GrowPy - Simplified Grove API Integration for The Grove 2.2

Clean Grove API integration for forest creation and FBX export:
- Forest/Grove/Tree/Twig hierarchy maintained
- Single high-quality LOD (no complexity)
- FBX export with mesh + skeleton + textures
- Blender-based twig processing using bpy module

Main utilities:
- utils/export_twigs.py: FBX-optimized twig export with texture mapping
- utils/export_trees.py: Grove tree export functionality
- utils/generate_forest.py: Forest generation utilities

See individual module documentation for detailed usage examples.
"""

from .config import GrowPyConfig, get_config, set_global_config
from .forest import create_forest, create_forest_with_attributes, simulate_forest_growth
from .grove import add_tree_to_grove, create_grove
from .tree import (
    apply_species_color_settings,
    build_grove_with_all_attributes,
    build_skeletons,
    get_model_attributes,
    calculate_growth_cycles_from_height,
)

# Import export functionality
try:
    from .export import (
        export_tree_as_fbx,
        export_twigs_from_blend,
        batch_export_tree_fbx,
    )
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    export_tree_as_fbx = None
    export_twigs_from_blend = None
    batch_export_tree_fbx = None


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
    "export_tree_as_fbx",
    "export_twigs_from_blend",
    "batch_export_tree_fbx",
    "EXPORT_AVAILABLE",
]
