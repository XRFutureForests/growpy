"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.

This module provides the GrowPyConfig class which handles:
- Basic simulation configuration (random seed, output directory, LOD levels)
- Species lookup functionality from tree_asset_lookup.csv
- LOD (Level of Detail) configuration presets

The species lookup table is automatically loaded and cached when first accessed,
providing convenient methods to get preset files, bark textures, growth models, and other
species data by common name.

Example usage:
    config = GrowPyConfig()

    # Get all available species
    species = config.get_available_species()

    # Get data for a specific species
    beech_data = config.get_species_data("European beech")

    # Get just the preset file for a species
    preset = config.get_preset_for_species("European beech")

    # Get the growth model directory for a species
    growth_model = config.get_growth_model_for_species("European beech")
"""

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# Global config registry
_global_config: Optional['GrowPyConfig'] = None


def get_global_config() -> Optional['GrowPyConfig']:
    """Get the currently active global config instance."""
    return _global_config


def set_global_config(config: 'GrowPyConfig') -> None:
    """Set the global config instance that will be used by all modules."""
    global _global_config
    _global_config = config


def get_config() -> 'GrowPyConfig':
    """
    Get config instance with automatic fallback:
    1. Global config instance (if set)
    2. New default config instance (fallback)
    """
    if _global_config is not None:
        return _global_config
        
    return GrowPyConfig()


@dataclass
class GrowPyConfig:
    """Lightweight configuration for GrowPy tree generation."""

    # Core simulation settings# Number of cycles for height curve generation
    random_seed: Optional[int] = 42

    # Output settings
    output_dir: Path = Path("output")

    # LOD selection (which LOD levels to generate)
    lod_levels: List[str] = field(default_factory=lambda: ["all"])

    # Age prediction settings
    # Note: age_to_cycle_ratio removed to avoid timing issues

    # Class variable to cache the species lookup DataFrame
    _species_df: Optional[pd.DataFrame] = None
    
    def __post_init__(self):
        """Automatically register this config as global if none exists."""
        global _global_config
        if _global_config is None:
            _global_config = self

    @classmethod
    def from_config_file(cls, config_path: Path, set_as_global: bool = True) -> "GrowPyConfig":
        """
        Create a GrowPyConfig instance from a config.ini file.
        
        Args:
            config_path: Path to the config file
            set_as_global: Whether to automatically set this as the global config
        """
        config = configparser.ConfigParser()
        config.read(config_path)
        kwargs = {}

        # Parse [simulation] section
        if config.has_section("simulation"):
            simulation = config["simulation"]
            if "random_seed" in simulation:
                seed_val = simulation.get("random_seed", "")
                kwargs["random_seed"] = (
                    None if seed_val.lower() == "none" else int(seed_val)
                )

        # Parse [output] section
        if config.has_section("output"):
            output = config["output"]
            if "output_dir" in output:
                output_dir = output.get("output_dir")
                if output_dir:
                    kwargs["output_dir"] = Path(output_dir)

        # Parse [build] section
        if config.has_section("build"):
            build = config["build"]
            if "lod_levels" in build:
                lod_levels_str = build.get("lod_levels", "all")
                if lod_levels_str.lower().strip() == "all":
                    kwargs["lod_levels"] = ["all"]
                else:
                    kwargs["lod_levels"] = [
                        level.strip() for level in lod_levels_str.split(",")
                    ]

        instance = cls(**kwargs)
        
        # Explicitly set as global config if requested
        if set_as_global:
            set_global_config(instance)
            
        return instance

    def to_config_file(self, config_path: Path) -> None:
        """Save current configuration to a config.ini file."""
        config = configparser.ConfigParser()
        config["simulation"] = {
            "random_seed": (
                str(self.random_seed) if self.random_seed is not None else "none"
            ),
        }
        config["output"] = {"output_dir": str(self.output_dir)}
        config["build"] = {
            "lod_levels": (
                "all" if self.lod_levels == ["all"] else ", ".join(self.lod_levels)
            )
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            config.write(f)

    @classmethod
    def load_species_lookup(cls, csv_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Load the species lookup table from CSV file using pandas.

        Args:
            csv_path: Path to the CSV file. If None, uses default location.

        Returns:
            DataFrame with species data.
        """
        if cls._species_df is not None:
            return cls._species_df

        if csv_path is None:
            # Default path using pathlib parents
            current_file = Path(__file__)
            project_root = current_file.parents[2]  # Go up to project root
            csv_path = project_root / "data" / "tree_asset_lookup.csv"

        cls._species_df = pd.read_csv(csv_path, encoding="utf-8")
        return cls._species_df

    @classmethod
    def get_data_directory(cls) -> Path:
        """
        Get the base data directory path.

        Returns:
            Path to the data directory.
        """
        current_file = Path(__file__)
        # Navigate from src/growpy/config.py to the project root, then to data
        project_root = current_file.parents[
            2
        ]  # Go up 2 levels: growpy -> src -> project_root
        return project_root / "data"

    @classmethod
    def get_assets_directory(cls) -> Path:
        """
        Get the assets directory path.

        Returns:
            Path to the assets directory (data/assets).
        """
        return cls.get_data_directory() / "assets"

    @classmethod
    def get_growth_model_path(cls, common_name: str) -> Path:
        """
        Get the full path to the growth model directory for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the growth model directory or None if species not found or no growth model available.
        """
        df = cls.load_species_lookup()
        growth_model = df.loc[df["Common Name"] == common_name, "Growth Model"].values[
            0
        ]

        # Default path relative to this file - now under assets
        assets_dir = cls.get_assets_directory()
        base_path = assets_dir / "growth_models"

        return base_path / growth_model

    @classmethod
    def get_bark_texture_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the bark texture file for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the bark texture file or None if species not found.
        """
        df = cls.load_species_lookup()
        bark_texture = df.loc[df["Common Name"] == common_name, "Bark Texture"].values[
            0
        ]
        assets_dir = cls.get_assets_directory()
        texture_path = assets_dir / "textures" / bark_texture
        return texture_path

    @classmethod
    def get_twig_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the twig name for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Twig name or None if species not found or no twig available.
        """
        df = cls.load_species_lookup()
        
        if df.empty:
            return None
            
        # Find the row for this species
        species_row = df[df["Common Name"] == common_name]
        
        if species_row.empty:
            return None
            
        twig = species_row.iloc[0]["Twig"]
        return str(twig) if pd.notna(twig) and str(twig) not in ["—", "", "nan"] else None

    @classmethod
    def get_twig_prototype_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig prototype file for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig prototype file or None if species not found or no twig available.
        """
        df = cls.load_species_lookup()
        twig_name = df.loc[df["Common Name"] == common_name, "Twig"].values[0]
        prototype_name = twig_name + "_prototype.usda"
        assets_dir = cls.get_assets_directory()
        prototypes_dir = assets_dir / "twigs" / "prototypes"
        prototype_path = prototypes_dir / prototype_name
        return prototype_path

    @classmethod
    def get_twig_material_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig material file for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig material file or None if species not found or no twig available.
        """
        df = cls.load_species_lookup()
        twig_name = df.loc[df["Common Name"] == common_name, "Twig"].values[0]
        material_name = twig_name + "_material.usda"
        assets_dir = cls.get_assets_directory()
        materials_dir = assets_dir / "twigs" / "materials"
        material_path = materials_dir / material_name
        return material_path

    @classmethod
    def get_preset_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the preset filename for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Preset filename or None if species not found.
        """
        df = cls.load_species_lookup()
        
        if df.empty:
            return None
            
        # Find the row for this species
        species_row = df[df["Common Name"] == common_name]
        
        if species_row.empty:
            return None
            
        preset = species_row.iloc[0]["Preset"]
        return str(preset) if pd.notna(preset) else None

    @classmethod
    def get_available_species(cls) -> List[str]:
        """
        Get list of all available species common names.

        Returns:
            List of common names from the species lookup table.
        """
        df = cls.load_species_lookup()
        
        if df.empty:
            return []
            
        return df["Common Name"].tolist()

    @classmethod
    def get_preset_path(cls, common_name: str) -> Path:
        """
        Get the full path to the preset file for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the preset file or None if species not found.
        """
        df = cls.load_species_lookup()
        preset_name = df.loc[df["Common Name"] == common_name, "Preset"].values[0]
        assets_dir = cls.get_assets_directory()
        preset_path = assets_dir / "presets" / preset_name
        return preset_path

    @classmethod
    def get_all_lod_configs(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get all available Level of Detail (LOD) build configurations.
        Each successive LOD reduces polygon count significantly.

        Returns:
            Dict containing all LOD configurations from highest to lowest detail
        """
        return {
            "LOD0_Ultra": {
                "resolution": 24,  # Very high base resolution
                "resolution_reduce": 0.7,  # Slower reduction = more detail kept
                "texture_repeat": 3,
                "build_cutoff_age": 0,  # No age cutoff
                "build_cutoff_thickness": 0.0,  # No thickness cutoff
                "build_blend": True,  # Keep smooth transitions
                "build_end_cap": True,  # Keep end caps
            },
            "LOD1_High": {
                "resolution": 16,  # Default high resolution
                "resolution_reduce": 0.8,  # Default reduction rate
                "texture_repeat": 3,
                "build_cutoff_age": 0,
                "build_cutoff_thickness": 0.0,
                "build_blend": True,
                "build_end_cap": True,
            },
            "LOD2_Medium": {
                "resolution": 12,  # Reduced base resolution
                "resolution_reduce": 0.85,  # Faster reduction
                "texture_repeat": 2,  # Fewer UV repeats
                "build_cutoff_age": 1,  # Skip last year of growth
                "build_cutoff_thickness": 0.01,  # Skip very thin branches
                "build_blend": True,  # Keep blending for now
                "build_end_cap": False,  # Remove end caps (major reduction)
            },
            "LOD3_Low": {
                "resolution": 8,  # Lower base resolution
                "resolution_reduce": 0.9,  # Aggressive reduction
                "texture_repeat": 2,
                "build_cutoff_age": 2,  # Skip last 2 years of growth
                "build_cutoff_thickness": 0.02,  # Skip thin branches
                "build_blend": False,  # Disable blending (major reduction)
                "build_end_cap": False,  # No end caps
            },
            "LOD4_VeryLow": {
                "resolution": 6,  # Minimal base resolution
                "resolution_reduce": 0.95,  # Very aggressive reduction
                "texture_repeat": 1,  # Single UV repeat
                "build_cutoff_age": 3,  # Skip last 3 years of growth
                "build_cutoff_thickness": 0.03,  # Skip more thin branches
                "build_blend": False,  # No blending
                "build_end_cap": False,  # No end caps
            },
            "LOD5_Minimal": {
                "resolution": 4,  # Absolute minimum (triangular base)
                "resolution_reduce": 0.98,  # Maximum reduction rate
                "texture_repeat": 1,
                "build_cutoff_age": 4,  # Skip last 4 years of growth
                "build_cutoff_thickness": 0.05,  # Aggressive thickness cutoff
                "build_blend": False,  # No blending
                "build_end_cap": False,  # No end caps
            },
        }

    def get_lod_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get filtered Level of Detail (LOD) build configurations based on the instance's lod_levels setting.

        Returns:
            Dict containing LOD configurations filtered by the user's selection
        """
        all_configs = self.get_all_lod_configs()
        
        # If "all" is in the lod_levels, return all configurations
        if "all" in self.lod_levels:
            return all_configs
        
        # Filter configurations based on the user's selection
        filtered_configs = {}
        for lod_level in self.lod_levels:
            if lod_level in all_configs:
                filtered_configs[lod_level] = all_configs[lod_level]
        
        return filtered_configs
