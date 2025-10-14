"""
Configuration management for GrowPy.

Species lookup, asset path resolution, and project configuration.

Key Classes:
    GrowPyConfig  Main configuration class with species lookup

Key Functions:
    get_config()              Get or create global config
    set_global_config()       Set custom global config

Configuration Sources:
    1. tree_asset_lookup.csv  Maps species to Grove presets
    2. environment.yml        Sets PYTHONPATH for Grove API
    3. Optional config/       Project-specific overrides

Example:
    from growpy import get_config

    config = get_config()

    # Get all species
    species_list = config.get_all_species()

    # Get species preset path
    preset = config.get_species_preset("Quaking Aspen")

    # Get asset paths
    twigs_path = config.twigs_path
    textures_path = config.textures_path

Asset Paths:
    config.presets_path       Species .seed.json files
    config.textures_path      Bark and leaf textures
    config.twigs_path         Twig .blend files
    config.growth_models_path Generated prediction models
"""

from .settings import GrowPyConfig, get_config, get_global_config, set_global_config

__all__ = [
    "GrowPyConfig",
    "get_config",
    "get_global_config",
    "set_global_config",
]
