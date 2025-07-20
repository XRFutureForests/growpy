"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.
"""

import configparser
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Set up logging
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised when configuration is invalid."""
    pass


@dataclass
class GrowPyConfig:
    """Lightweight configuration for GrowPy tree generation."""

    # Core simulation settings
    height_model_cycles: int = 75  # Number of cycles for height curve generation
    random_seed: Optional[int] = 42

    # Output settings
    output_dir: Path = Path("output")

    # LOD selection (which LOD levels to generate)
    lod_levels: List[str] = field(default_factory=lambda: ["all"])

    # Age prediction settings
    # Note: age_to_cycle_ratio removed to avoid timing issues

    @classmethod
    def from_config_file(cls, config_path: Path) -> "GrowPyConfig":
        """
        Create a GrowPyConfig instance from a config.ini file.

        Args:
            config_path: Path to the config.ini file

        Returns:
            GrowPyConfig instance with settings from the file
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ConfigurationError: If config file is malformed or has invalid values
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        config = configparser.ConfigParser()
        try:
            config.read(config_path)
        except configparser.Error as e:
            raise ConfigurationError(f"Invalid configuration file format: {e}")

        # Start with defaults
        kwargs = {}

        # Parse [simulation] section
        if config.has_section("simulation"):
            simulation = config["simulation"]

            try:
                if "height_model_cycles" in simulation:
                    cycles = simulation.getint("height_model_cycles")
                    if cycles <= 0:
                        raise ConfigurationError("height_model_cycles must be positive")
                    kwargs["height_model_cycles"] = cycles
                        
                if "random_seed" in simulation:
                    seed_val = simulation.get("random_seed", "")
                    if seed_val.lower() == "none":
                        kwargs["random_seed"] = None
                    else:
                        seed = int(seed_val)
                        if seed < 0:
                            raise ConfigurationError("random_seed must be non-negative")
                        kwargs["random_seed"] = seed
                        
                # age_to_cycle_ratio removed - was causing timing issues
                    
            except (ValueError, configparser.Error) as e:
                raise ConfigurationError(f"Invalid value in simulation section: {e}")

        # Parse [output] section
        if config.has_section("output"):
            output = config["output"]

            try:
                if "output_dir" in output:
                    output_dir = output.get("output_dir")
                    if output_dir:
                        kwargs["output_dir"] = Path(output_dir)
            except Exception as e:
                raise ConfigurationError(f"Invalid value in output section: {e}")

        # Parse [build] section
        if config.has_section("build"):
            build = config["build"]

            try:
                if "lod_levels" in build:
                    lod_levels_str = build.get("lod_levels", "all")
                    if lod_levels_str.lower().strip() == "all":
                        kwargs["lod_levels"] = ["all"]
                    else:
                        # Parse comma-separated LOD levels
                        lod_levels = [level.strip() for level in lod_levels_str.split(",")]
                        
                        # Validate LOD levels
                        available_lods = set(cls.get_lod_configs().keys())
                        for lod in lod_levels:
                            if lod not in available_lods:
                                raise ConfigurationError(
                                    f"Invalid LOD level: {lod}. Available: {list(available_lods)}"
                                )
                        kwargs["lod_levels"] = lod_levels
                    
            except (ValueError, configparser.Error) as e:
                raise ConfigurationError(f"Invalid value in build section: {e}")

        return cls(**kwargs)

    def to_config_file(self, config_path: Path) -> None:
        """
        Save current configuration to a config.ini file.

        Args:
            config_path: Path where to save the config.ini file
        """
        config = configparser.ConfigParser()

        # [simulation] section
        config["simulation"] = {
            "height_model_cycles": str(self.height_model_cycles),
            "random_seed": (
                str(self.random_seed) if self.random_seed is not None else "none"
            ),
            # age_to_cycle_ratio removed
        }

        # [output] section
        config["output"] = {
            "output_dir": str(self.output_dir),
        }

        # [build] section
        config["build"] = {
            "lod_levels": "all" if self.lod_levels == ["all"] else ", ".join(self.lod_levels),
        }

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            config.write(f)

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

    @classmethod
    def create_lod_config(cls, lod_level: str, **kwargs) -> "GrowPyConfig":
        """
        Create a GrowPyConfig instance with specified LOD settings.

        Args:
            lod_level: One of LOD0_Ultra, LOD1_High, LOD2_Medium, LOD3_Low, LOD4_VeryLow, LOD5_Minimal
            **kwargs: Additional config overrides

        Returns:
            GrowPyConfig instance with LOD settings applied
        """
        lod_configs = cls.get_lod_configs()

        if lod_level not in lod_configs:
            raise ValueError(
                f"Invalid LOD level: {lod_level}. Available: {list(lod_configs.keys())}"
            )

        # Create base config
        config = cls(**kwargs)

        # Apply LOD-specific build options
        lod_settings = lod_configs[lod_level]
        for key, value in lod_settings.items():
            setattr(config, key, value)

        return config


    def get_selected_lod_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get the LOD configurations selected by the user."""
        all_lod_configs = self.get_lod_configs()
        
        if self.lod_levels == ["all"]:
            return all_lod_configs
        
        selected_configs = {}
        for lod_level in self.lod_levels:
            if lod_level in all_lod_configs:
                selected_configs[lod_level] = all_lod_configs[lod_level]
        
        return selected_configs



# Module constants
DEFAULT_HEIGHT_MODEL_CYCLES = 75
DEFAULT_RANDOM_SEED = 42
DEFAULT_OUTPUT_DIR = Path("output")


def create_sample_config_ini(path: Path) -> None:
    """
    Create a sample config.ini file with documentation.

    Args:
        path: Path where to create the sample config file
    """
    config = GrowPyConfig()
    config.to_config_file(path)


