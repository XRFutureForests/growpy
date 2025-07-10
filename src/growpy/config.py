"""
Configuration for GrowPy - simplified and focused on Grove 2.2 integration.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path
from enum import Enum


class ExportFormat(Enum):
    """Export format for tree models."""

    OBJ = "obj"
    USD = "usd"


@dataclass
class GrowPyConfig:
    """Lightweight configuration for GrowPy tree generation."""

    # Core settings
    growth_cycles: int = 10
    random_seed: Optional[int] = None
    export_format: ExportFormat = ExportFormat.OBJ
    output_dir: Path = Path("output")

    # Model quality (passed directly to Grove)
    resolution: int = 16

    # Advanced options (following Grove's capabilities)
    add_position_variation: bool = False  # Use Grove's tree_math.add_variation
    position_random_shift: float = 0.5  # Random shift for tree positions
    up_axis: str = "Z"  # Coordinate system: "Y" or "Z"

    def to_grove_build_options(self) -> Dict[str, Any]:
        """Convert to Grove build options dictionary."""
        return {
            "resolution": self.resolution,
            "build_end_cap": True,
        }
