"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GrowPyConfig:
    """Lightweight configuration for GrowPy tree generation."""

    # Core settings
    growth_cycles: int = 10
    random_seed: Optional[int] = 42
    output_dir: Path = Path("output")

    # Build options
    resolution: int = 16
    resolution_reduce: float = 0.8
    texture_repeat: int = 3
    build_cutoff_age: int = 0
    build_cutoff_thickness: float = 0.0
    build_blend: bool = True
    build_end_cap: bool = True

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

    def get_estimated_polygon_reduction(self, base_lod: str = "LOD1_High") -> float:
        """
        Estimate polygon reduction compared to base LOD.
        This is a rough approximation based on the parameter impacts.

        Args:
            base_lod: Reference LOD level for comparison

        Returns:
            Estimated reduction factor (e.g., 0.5 means ~50% fewer polygons)
        """
        base_config = self.get_lod_configs()[base_lod]
        current_config = {
            "resolution": self.resolution,
            "resolution_reduce": self.resolution_reduce,
            "build_cutoff_age": self.build_cutoff_age,
            "build_cutoff_thickness": self.build_cutoff_thickness,
            "build_blend": self.build_blend,
            "build_end_cap": self.build_end_cap,
        }

        # Rough estimation based on parameter impacts
        reduction_factor = 1.0

        # Resolution impact: linear relationship to base circumference
        resolution_ratio = current_config["resolution"] / base_config["resolution"]
        reduction_factor *= resolution_ratio

        # Cutoff age: each year skipped reduces polygon count significantly
        if current_config["build_cutoff_age"] > base_config["build_cutoff_age"]:
            age_reduction = 0.8 ** (
                current_config["build_cutoff_age"] - base_config["build_cutoff_age"]
            )
            reduction_factor *= age_reduction

        # Thickness cutoff: has major impact on thin branches
        if (
            current_config["build_cutoff_thickness"]
            > base_config["build_cutoff_thickness"]
        ):
            thickness_reduction = 0.7  # Rough estimate
            reduction_factor *= thickness_reduction

        # Blend and end cap: significant impact when disabled
        if base_config["build_blend"] and not current_config["build_blend"]:
            reduction_factor *= 0.7  # ~30% reduction when disabled

        if base_config["build_end_cap"] and not current_config["build_end_cap"]:
            reduction_factor *= 0.8  # ~20% reduction when disabled

        return reduction_factor

    def to_grove_build_options(self) -> Dict[str, Any]:
        """Convert to Grove build options dictionary."""
        return {
            "resolution": self.resolution,
            "resolution_reduce": self.resolution_reduce,
            "texture_repeat": self.texture_repeat,
            "build_cutoff_age": self.build_cutoff_age,
            "build_cutoff_thickness": self.build_cutoff_thickness,
            "build_blend": self.build_blend,
            "build_end_cap": self.build_end_cap,
        }


# Example usage functions
def create_lod_series() -> List[GrowPyConfig]:
    """Create a series of LOD configurations for testing."""
    lod_levels = [
        "LOD0_Ultra",
        "LOD1_High",
        "LOD2_Medium",
        "LOD3_Low",
        "LOD4_VeryLow",
        "LOD5_Minimal",
    ]
    return [GrowPyConfig.create_lod_config(lod) for lod in lod_levels]


def print_lod_comparison():
    """Print a comparison of all LOD levels."""
    configs = GrowPyConfig.get_lod_configs()

    print("LOD Comparison:")
    print("-" * 80)
    print(
        f"{'Level':<12} {'Resolution':<10} {'Reduce':<8} {'Age Cut':<8} {'Thick Cut':<10} {'Blend':<6} {'End Cap':<8}"
    )
    print("-" * 80)

    for lod_name, config in configs.items():
        print(
            f"{lod_name:<12} {config['resolution']:<10} {config['resolution_reduce']:<8.2f} "
            f"{config['build_cutoff_age']:<8} {config['build_cutoff_thickness']:<10.2f} "
            f"{str(config['build_blend']):<6} {str(config['build_end_cap']):<8}"
        )


if __name__ == "__main__":
    print_lod_comparison()

    # Example: Create medium LOD config
    medium_config = GrowPyConfig.create_lod_config("LOD2_Medium", growth_cycles=15)
    print(f"\nMedium LOD build options: {medium_config.to_grove_build_options()}")

    # Example: Estimate polygon reduction
    low_config = GrowPyConfig.create_lod_config("LOD3_Low")
    reduction = low_config.get_estimated_polygon_reduction()
    print(f"LOD3_Low estimated to have ~{reduction:.1%} of LOD1_High polygon count")
