"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

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
