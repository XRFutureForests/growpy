"""Atomic forest simulation functions for multi-species groves."""

from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd
import the_grove_22_core as gc

from .grove import create_grove, add_tree_to_grove, calculate_shared_shade
# Type alias for cleaner code
ForestGroves = List[Tuple[gc.Grove, str, int]]


def create_forest_groves(forest_data: pd.DataFrame, random_seed: Optional[int] = None) -> ForestGroves:
    """Create groves for each species in forest data."""
    forest_groves = []
    
    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name), random_seed)
        
        # Add all trees of this species to the grove
        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay=delay)
        
        forest_groves.append((grove, str(species_name), len(species_data)))
    
    return forest_groves


def simulate_forest_growth(forest_groves: ForestGroves, cycles: int) -> None:
    """Simulate forest growth with optional light competition."""
    groves = [grove for grove, _, _ in forest_groves]
    
    for _ in range(cycles):
        # Calculate shared light competition if enabled
        if len(groves) > 1:
            calculate_shared_shade(groves)
        
        # Simulate one growth cycle for each grove
        for grove, _, _ in forest_groves:
            grove.simulate(1)

