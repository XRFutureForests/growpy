"""
GrowPy - Clean interface for The Grove 2.2 with USD multi-LOD support
====================================================================

Streamlined procedural tree generation with native USD output and twig instancing.

Key Features:
- USD multi-LOD export with variants (eliminates FBX pipeline)
- Efficient twig instancing via USD prototypes
- Clean, minimal API focused on essential functionality
- Direct game engine compatibility

Quick Start:
    from growpy.core.config import GrowPyConfig
    from growpy.io.models import export_forest_models_with_twigs
    
    # Generate USD trees with all LODs and twig instances
    config = GrowPyConfig()
    forest_data = simulate_forest_from_csv("forest.csv")
    usd_files = export_forest_models_with_twigs(forest_data, output_dir, config.get_lod_configs())
"""

from .core.config import GrowPyConfig

__version__ = "4.0.0"
__author__ = "GrowPy Team"

__all__ = ["GrowPyConfig"]