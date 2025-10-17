"""Configuration management for GrowPy.

Provides species lookup, asset path resolution, and project configuration.
"""

from .core import GrowPyConfig, get_config, get_global_config, set_global_config
from .species import (
    load_species_lookup,
    find_species_match,
    get_available_species,
    get_species_colors,
    get_bark_texture,
    get_species_data,
)
from .paths import (
    get_data_directory,
    get_assets_directory,
    get_preset_path,
    get_growth_model_path,
    get_bark_texture_path,
    get_twig_directory_path,
    get_twig_usd_directory_path,
    get_twig_textures_path,
    get_twig_prototype_path,
    get_twig_material_path,
    get_available_twig_usd_files,
    get_twig_files_by_type,
    get_best_twig_file_for_type,
)
from .quality import get_all_lod_configs, get_lod_configs

__all__ = [
    # Core config
    "GrowPyConfig",
    "get_config",
    "get_global_config",
    "set_global_config",
    # Species
    "load_species_lookup",
    "find_species_match",
    "get_available_species",
    "get_species_colors",
    "get_bark_texture",
    "get_species_data",
    # Paths
    "get_data_directory",
    "get_assets_directory",
    "get_preset_path",
    "get_growth_model_path",
    "get_bark_texture_path",
    "get_twig_directory_path",
    "get_twig_usd_directory_path",
    "get_twig_textures_path",
    "get_twig_prototype_path",
    "get_twig_material_path",
    "get_available_twig_usd_files",
    "get_twig_files_by_type",
    "get_best_twig_file_for_type",
    # Quality
    "get_all_lod_configs",
    "get_lod_configs",
]
