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
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    # Class variable to cache the species lookup table
    _species_lookup: Optional[Dict[str, Dict[str, str]]] = None

    @classmethod
    def from_config_file(cls, config_path: Path) -> "GrowPyConfig":
        """Create a GrowPyConfig instance from a config.ini file."""
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

        return cls(**kwargs)

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
    def load_species_lookup(
        cls, csv_path: Optional[Path] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Load the species lookup table from CSV file.

        Args:
            csv_path: Path to the CSV file. If None, uses default location.

        Returns:
            Dictionary with common names as keys and species data as values.
        """
        if cls._species_lookup is not None:
            return cls._species_lookup

        if csv_path is None:
            # Default path relative to this file
            current_dir = Path(__file__).parent
            csv_path = current_dir / "../../data/tree_asset_lookup.csv"

        species_lookup = {}

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    common_name = row["Common Name"].strip()
                    species_lookup[common_name] = {
                        "scientific_name": row["Scientific Name"].strip(),
                        "preset": row["Preset"].strip(),
                        "twig": row["Twig"].strip(),
                        "bark_texture": row["Bark Texture"].strip(),
                        "growth_model": (
                            row["Growth Model"].strip()
                            if row["Growth Model"].strip()
                            else None
                        ),
                    }
        except FileNotFoundError:
            print(f"Warning: Species lookup CSV not found at {csv_path}")
            species_lookup = {}
        except Exception as e:
            print(f"Warning: Error loading species lookup CSV: {e}")
            species_lookup = {}

        cls._species_lookup = species_lookup
        return species_lookup

    @classmethod
    def get_species_data(cls, common_name: str) -> Optional[Dict[str, str]]:
        """
        Get species data for a given common name.

        Args:
            common_name: The common name of the species.

        Returns:
            Dictionary with species data or None if not found.
        """
        lookup_table = cls.load_species_lookup()
        return lookup_table.get(common_name)

    @classmethod
    def get_available_species(cls) -> List[str]:
        """
        Get list of all available species common names.

        Returns:
            List of common names from the species lookup table.
        """
        lookup_table = cls.load_species_lookup()
        return list(lookup_table.keys())

    @classmethod
    def get_preset_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the preset filename for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Preset filename or None if species not found.
        """
        species_data = cls.get_species_data(common_name)
        return species_data["preset"] if species_data else None

    @classmethod
    def get_growth_model_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the growth model directory name for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Growth model directory name or None if species not found or no growth model available.
        """
        species_data = cls.get_species_data(common_name)
        return species_data["growth_model"] if species_data else None

    @classmethod
    def get_bark_texture_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the bark texture filename for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Bark texture filename or None if species not found.
        """
        species_data = cls.get_species_data(common_name)
        return species_data["bark_texture"] if species_data else None

    @classmethod
    def get_twig_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the twig type for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Twig type or None if species not found.
        """
        species_data = cls.get_species_data(common_name)
        return species_data["twig"] if species_data else None

    @classmethod
    def get_growth_model_path(
        cls, common_name: str, base_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Get the full path to the growth model directory for a given species.

        Args:
            common_name: The common name of the species.
            base_path: Base path to the growth_models directory. If None, uses default location.

        Returns:
            Path to the growth model directory or None if species not found or no growth model available.
        """
        growth_model = cls.get_growth_model_for_species(common_name)
        if not growth_model:
            return None

        if base_path is None:
            # Default path relative to this file
            current_dir = Path(__file__).parent
            base_path = current_dir / "../../data/growth_models"

            return base_path / growth_model

    @classmethod
    def get_species_by_family(cls, family_prefix: str) -> List[str]:
        """
        Get all species that belong to a specific botanical family.

        Args:
            family_prefix: The family prefix to search for (e.g., 'Fagaceae', 'Pinaceae').

        Returns:
            List of common names for species in that family.
        """
        lookup_table = cls.load_species_lookup()
        matching_species = []

        for common_name, data in lookup_table.items():
            if data["preset"].startswith(family_prefix):
                matching_species.append(common_name)

        return sorted(matching_species)

    @classmethod
    def get_available_families(cls) -> List[str]:
        """
        Get list of all available botanical families.

        Returns:
            List of family names extracted from preset filenames.
        """
        lookup_table = cls.load_species_lookup()
        families = set()

        for data in lookup_table.values():
            preset = data["preset"]
            if " - " in preset:
                family = preset.split(" - ")[0]
                families.add(family)

        return sorted(families)

    @classmethod
    def get_species_with_growth_models(cls) -> List[str]:
        """
        Get all species that have growth models available.

        Returns:
            List of common names for species with growth models.
        """
        lookup_table = cls.load_species_lookup()
        return [name for name, data in lookup_table.items() if data["growth_model"]]

    @classmethod
    def get_scientific_name_for_species(cls, common_name: str) -> Optional[str]:
        """
        Get the scientific name for a given species.

        Args:
            common_name: The common name of the species.

        Returns:
            Scientific name or None if species not found.
        """
        species_data = cls.get_species_data(common_name)
        return species_data["scientific_name"] if species_data else None

    @classmethod
    def get_lod_configs(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get different Level of Detail (LOD) build configurations.
        Each successive LOD reduces polygon count significantly.

        Returns:
            Dict containing LOD configurations from highest to lowest detail
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
