"""Age prediction functionality for forest simulation."""

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


def calculate_growth_cycles_from_height(
    forest_data: pd.DataFrame, growth_models_dir: Optional[Path] = None
) -> Tuple[pd.DataFrame, int]:
    """Calculate growth cycles using height prediction models or simple fallback."""
    if "height" not in forest_data.columns:
        return forest_data, 25  # Default fallback

    # Simple height-based calculation (can be enhanced with growth models later)
    max_height = forest_data["height"].max()

    # Rough approximation: 1 meter per growth cycle
    estimated_cycles = max(int(max_height), 10)  # Minimum 10 cycles
    estimated_cycles = min(estimated_cycles, 50)  # Maximum 50 cycles

    return forest_data, estimated_cycles


def has_height_prediction_available(growth_models_dir: Optional[Path] = None) -> bool:
    """Check if height prediction models are available."""
    # Simplified: always return False since we removed the growth models dependency
    return False
