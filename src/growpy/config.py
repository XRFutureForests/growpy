"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.

This module provides the GrowPyConfig class which handles:
- Basic simulation configuration (random seed, output directory, LOD levels)
- Species lookup functionality from tree_asset_lookup.csv
- LOD (Level of Detail) configuration presets
- Twig asset path resolution for the new distributed USD structure

The species lookup table is automatically loaded and cached when first accessed,
providing convenient methods to get preset files, bark textures, growth models, and other
species data by common name.

Twig USD assets are now organized in a distributed structure where each twig species
has its own directory with USD files:
    data/assets/twigs/[SpeciesName]Twig/usd/
    ├── prototypes/[SpeciesName]_prototype.usda
    ├── materials/[SpeciesName]_material.usda
    └── textures/[SpeciesName]_[textureType].[ext]

Example usage:
    config = GrowPyConfig()

    # Get all available species
    species = config.get_available_species()

    # Get data for a specific species
    beech_data = config.get_species_data("European beech")

    # Get just the preset file for a species
    preset = config.get_preset_for_species("European beech")

    # Get twig USD paths for a species
    prototype_path = config.get_twig_prototype_path("European beech")
    material_path = config.get_twig_material_path("European beech")

    # Get USD catalog information
    available_usd_twigs = config.get_available_usd_twigs()
    twig_info = config.get_usd_twig_info("EuropeanBeech")
"""

import configparser
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Global config registry
_global_config: Optional["GrowPyConfig"] = None


def get_global_config() -> Optional["GrowPyConfig"]:
    """Get the currently active global config instance."""
    return _global_config


def set_global_config(config: "GrowPyConfig") -> None:
    """Set the global config instance that will be used by all modules."""
    global _global_config
    _global_config = config


def get_config() -> "GrowPyConfig":
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
    def from_config_file(
        cls, config_path: Path, set_as_global: bool = True
    ) -> "GrowPyConfig":
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
    def _find_species_match(cls, input_name: str, df: pd.DataFrame) -> Optional[str]:
        """
        Find the best matching species name from the lookup table using case-insensitive
        and fuzzy matching.

        Args:
            input_name: The input species name to match
            df: The species lookup DataFrame

        Returns:
            The matched Common Name from the lookup table, or None if no match found
        """
        if df.empty:
            return None

        # Convert input to lowercase for comparison
        input_lower = input_name.lower().strip()

        # Get all common names from the lookup table
        common_names = df["Common Name"].str.lower().str.strip()

        # 1. Try exact match (case-insensitive)
        exact_match = df[common_names == input_lower]
        if not exact_match.empty:
            return exact_match.iloc[0]["Common Name"]

        # 2. Try partial match - input contains any word from species name
        for idx, species_name in enumerate(df["Common Name"]):
            species_words = species_name.lower().split()
            input_words = input_lower.split()

            # Check if any word from input matches any word from species name
            if any(input_word in species_words for input_word in input_words):
                return species_name

        # 3. Try reverse partial match - species name contains any word from input
        for idx, species_name in enumerate(df["Common Name"]):
            species_lower = species_name.lower()
            input_words = input_lower.split()

            # Check if any word from input is contained in the species name
            if any(word in species_lower for word in input_words):
                return species_name

        # 4. Special mappings for common abbreviations/variations
        species_mappings = {
            "beech": "European beech",
            "oak": "European oak",
            "fir": "Silver fir",
            "silver fir": "Silver fir",
            "douglas fir": "Silver fir",  # Fallback - adjust if you have Douglas fir in lookup
            "spruce": "Norway spruce",
            "pine": "Scots pine",
            "scots pine": "Scots pine",
            "birch": "Silver birch",
            "maple": "Field maple",
            "ash": "Common ash",
            "willow": "Willow",
            "poplar": "Grey poplar",
            "linden": "Small-leaved linden",
            "cherry": "Wild cherry",
            "chestnut": "Sweet chestnut",
            "hornbeam": "Hornbeam",
            "hazel": "Hazel",
            "elm": "Elm",
            "yew": "Yew",
        }

        # Check if input matches any of our mappings
        if input_lower in species_mappings:
            mapped_name = species_mappings[input_lower]
            # Verify the mapped name actually exists in our lookup table
            mapped_match = df[df["Common Name"].str.lower() == mapped_name.lower()]
            if not mapped_match.empty:
                return mapped_match.iloc[0]["Common Name"]

        return None

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

        # Use fuzzy matching to find the species
        matched_name = cls._find_species_match(common_name, df)
        if matched_name is None:
            raise ValueError(
                f"Species '{common_name}' not found in lookup table. Available species: {list(df['Common Name'])}"
            )

        growth_model = df.loc[df["Common Name"] == matched_name, "Growth Model"].values[
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

        # Use fuzzy matching to find the species
        matched_name = cls._find_species_match(common_name, df)
        if matched_name is None:
            return None

        bark_texture = df.loc[df["Common Name"] == matched_name, "Bark Texture"].values[
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

        # Use fuzzy matching to find the species
        matched_name = cls._find_species_match(common_name, df)
        if matched_name is None:
            return None

        # Find the row for this species
        species_row = df[df["Common Name"] == matched_name]

        if species_row.empty:
            return None

        twig = species_row.iloc[0]["Twig"]
        return (
            str(twig) if pd.notna(twig) and str(twig) not in ["—", "", "nan"] else None
        )

    @classmethod
    def get_twig_prototype_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig prototype file for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig prototype file or None if species not found or no twig available.
        """
        twig_name = cls.get_twig_for_species(common_name)
        if not twig_name:
            return None

        # New distributed structure: each twig has its own USD directory
        prototype_name = twig_name + "_prototype.usda"
        assets_dir = cls.get_assets_directory()
        twig_dir = assets_dir / "twigs" / f"{twig_name}Twig"
        prototype_path = twig_dir / "usd" / "prototypes" / prototype_name
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
        twig_name = cls.get_twig_for_species(common_name)
        if not twig_name:
            return None

        # New distributed structure: each twig has its own USD directory
        material_name = twig_name + "_material.usda"
        assets_dir = cls.get_assets_directory()
        twig_dir = assets_dir / "twigs" / f"{twig_name}Twig"
        material_path = twig_dir / "usd" / "materials" / material_name
        return material_path

    @classmethod
    def get_twig_directory_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig directory for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig directory or None if species not found or no twig available.
        """
        twig_name = cls.get_twig_for_species(common_name)
        if not twig_name:
            return None

        assets_dir = cls.get_assets_directory()
        twig_dir = assets_dir / "twigs" / twig_name
        return twig_dir

    @classmethod
    def get_available_twig_usd_files(cls, common_name: str) -> List[Path]:
        """
        Get all available USD twig files for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            List of Path objects to USD twig files, or empty list if none found.
        """
        twig_dir = cls.get_twig_directory_path(common_name)
        if not twig_dir or not twig_dir.exists():
            return []

        # Find all .usda files in the twig directory
        usd_files = list(twig_dir.glob("*.usda"))
        return sorted(usd_files)

    @classmethod
    def get_twig_files_by_type(cls, common_name: str) -> Dict[str, List[Path]]:
        """
        Get twig USD files organized by type (apical, lateral, end, side, etc.).

        Args:
            common_name: The common name of the species.

        Returns:
            Dictionary with twig types as keys and lists of Path objects as values.
        """
        usd_files = cls.get_available_twig_usd_files(common_name)
        if not usd_files:
            return {}

        twig_types = {
            "apical": [],
            "lateral": [],
            "end": [],
            "side": [],
            "main": [],
            "variation": [],
            "other": [],
        }

        for file_path in usd_files:
            filename = file_path.stem.lower()

            # Categorize by filename patterns
            if "apical" in filename:
                twig_types["apical"].append(file_path)
            elif "lateral" in filename:
                twig_types["lateral"].append(file_path)
            elif "end" in filename:
                twig_types["end"].append(file_path)
            elif "side" in filename:
                twig_types["side"].append(file_path)
            elif "variation" in filename or "var" in filename:
                twig_types["variation"].append(file_path)
            elif (
                filename.count("_") == 1
            ):  # Simple pattern like "TwigName_TwigName.usda"
                twig_types["main"].append(file_path)
            else:
                twig_types["other"].append(file_path)

        # Remove empty categories
        return {k: v for k, v in twig_types.items() if v}

    @classmethod
    def get_best_twig_file_for_type(
        cls, common_name: str, twig_type: str = "auto"
    ) -> Optional[Path]:
        """
        Get the best twig USD file for a specific twig type.

        Args:
            common_name: The common name of the species.
            twig_type: Type of twig ('apical', 'lateral', 'end', 'side', 'main', 'auto')
                      'auto' will select the best available type automatically.

        Returns:
            Path to the best matching twig file, or None if none found.
        """
        twig_files_by_type = cls.get_twig_files_by_type(common_name)
        if not twig_files_by_type:
            return None

        if twig_type == "auto":
            # Priority order for automatic selection
            priority_order = [
                "main",
                "apical",
                "lateral",
                "end",
                "side",
                "variation",
                "other",
            ]
            for preferred_type in priority_order:
                if (
                    preferred_type in twig_files_by_type
                    and twig_files_by_type[preferred_type]
                ):
                    return twig_files_by_type[preferred_type][
                        0
                    ]  # Return first file of this type
            return None
        else:
            # Return first file of the requested type
            if twig_type in twig_files_by_type and twig_files_by_type[twig_type]:
                return twig_files_by_type[twig_type][0]
            return None

    @classmethod
    def get_twig_usd_directory_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig's USD directory for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig's USD directory or None if species not found or no twig available.
        """
        twig_dir = cls.get_twig_directory_path(common_name)
        if not twig_dir:
            return None

        return twig_dir / "usd"

    @classmethod
    def get_twig_textures_path(cls, common_name: str) -> Optional[Path]:
        """
        Get the full path to the twig's USD textures directory for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Path to the twig's USD textures directory or None if species not found or no twig available.
        """
        usd_dir = cls.get_twig_usd_directory_path(common_name)
        if not usd_dir:
            return None

        return usd_dir / "textures"

    @classmethod
    def get_usd_catalog_path(cls) -> Path:
        """
        Get the path to the USD catalog file.

        Returns:
            Path to the USD catalog JSON file.
        """
        assets_dir = cls.get_assets_directory()
        return assets_dir / "twigs" / "usd_catalog.json"

    @classmethod
    def load_usd_catalog(cls) -> Optional[Dict[str, Any]]:
        """
        Load the USD catalog containing information about all converted twigs.

        Returns:
            Dictionary containing catalog data or None if catalog doesn't exist.
        """
        catalog_path = cls.get_usd_catalog_path()
        if not catalog_path.exists():
            return None

        try:
            with open(catalog_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def get_available_usd_twigs(cls) -> List[str]:
        """
        Get list of all species that have USD twig conversions available.

        Returns:
            List of species names that have USD files available.
        """
        catalog = cls.load_usd_catalog()
        if not catalog:
            return []

        return list(catalog.get("twigs", {}).keys())

    @classmethod
    def get_usd_twig_info(cls, species_name: str) -> Optional[Dict[str, Any]]:
        """
        Get USD information for a specific species from the catalog.

        Args:
            species_name: The species name (as used in USD conversion, e.g., "EuropeanBeech").

        Returns:
            Dictionary containing USD twig information or None if not found.
        """
        catalog = cls.load_usd_catalog()
        if not catalog:
            return None

        return catalog.get("twigs", {}).get(species_name)

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

        # Use fuzzy matching to find the species
        matched_name = cls._find_species_match(common_name, df)
        if matched_name is None:
            return None

        # Find the row for this species
        species_row = df[df["Common Name"] == matched_name]

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

        # Use fuzzy matching to find the species
        matched_name = cls._find_species_match(common_name, df)
        if matched_name is None:
            raise ValueError(
                f"Species '{common_name}' not found in lookup table. Available species: {list(df['Common Name'])}"
            )

        preset_name = df.loc[df["Common Name"] == matched_name, "Preset"].values[0]
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
            # "LOD4_VeryLow": {
            #     "resolution": 6,  # Minimal base resolution
            #     "resolution_reduce": 0.95,  # Very aggressive reduction
            #     "texture_repeat": 1,  # Single UV repeat
            #     "build_cutoff_age": 3,  # Skip last 3 years of growth
            #     "build_cutoff_thickness": 0.03,  # Skip more thin branches
            #     "build_blend": False,  # No blending
            #     "build_end_cap": False,  # No end caps
            # },
            # "LOD5_Minimal": {
            #     "resolution": 4,  # Absolute minimum (triangular base)
            #     "resolution_reduce": 0.98,  # Maximum reduction rate
            #     "texture_repeat": 1,
            #     "build_cutoff_age": 4,  # Skip last 4 years of growth
            #     "build_cutoff_thickness": 0.05,  # Aggressive thickness cutoff
            #     "build_blend": False,  # No blending
            #     "build_end_cap": False,  # No end caps
            # },
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
