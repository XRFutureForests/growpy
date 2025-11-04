"""Core configuration for GrowPy."""

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_global_config: Optional["GrowPyConfig"] = None


def get_global_config() -> Optional["GrowPyConfig"]:
    """Get the currently active global config instance."""
    return _global_config


def set_global_config(config: "GrowPyConfig") -> None:
    """Set the global config instance."""
    global _global_config
    _global_config = config


def get_config() -> "GrowPyConfig":
    """Get config instance with automatic fallback."""
    if _global_config is not None:
        return _global_config
    return GrowPyConfig()


@dataclass
class GrowPyConfig:
    """Core configuration for GrowPy tree generation."""

    random_seed: Optional[int] = 42
    output_dir: Path = Path("output")
    lod_levels: List[str] = field(default_factory=lambda: ["all"])

    def __post_init__(self):
        """Automatically register this config as global if none exists."""
        global _global_config
        if _global_config is None:
            _global_config = self

    @classmethod
    def from_config_file(
        cls, config_path: Path, set_as_global: bool = True
    ) -> "GrowPyConfig":
        """Create a GrowPyConfig instance from a config.ini file.

        Args:
            config_path: Path to config.ini
            set_as_global: Whether to set as global config

        Returns:
            GrowPyConfig instance
        """
        config = configparser.ConfigParser()
        config.read(config_path)
        kwargs = {}

        if config.has_section("simulation"):
            simulation = config["simulation"]
            if "random_seed" in simulation:
                seed_val = simulation.get("random_seed", "")
                kwargs["random_seed"] = (
                    None if seed_val.lower() == "none" else int(seed_val)
                )

        if config.has_section("output"):
            output = config["output"]
            if "output_dir" in output:
                output_dir = output.get("output_dir")
                if output_dir:
                    kwargs["output_dir"] = Path(output_dir)

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

        if set_as_global:
            set_global_config(instance)

        return instance

    def to_config_file(self, config_path: Path) -> None:
        """Save current configuration to a config.ini file.

        Args:
            config_path: Path to save config.ini
        """
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

    # Delegator methods to module-level functions
    def get_preset_path(self, species: str) -> Path:
        """Get preset path for species."""
        from .paths import get_preset_path
        return get_preset_path(species)

    def get_growth_model_path(self, species: str) -> Path:
        """Get growth model path for species."""
        from .paths import get_growth_model_path
        return get_growth_model_path(species)

    @staticmethod
    def get_twig_files_by_type(species: str):
        """Get twig files organized by type."""
        from .paths import get_twig_files_by_type
        return get_twig_files_by_type(species)
