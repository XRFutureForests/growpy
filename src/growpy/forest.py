"""Atomic forest simulation functions for multi-species groves."""

from pathlib import Path
from typing import List, Tuple

import pandas as pd
import the_grove_22_core as gc
from tqdm import tqdm

# No direct config import needed - grove functions handle config internally
from .grove import add_tree_to_grove, create_grove

# Type alias for cleaner code
ForestGroves = List[Tuple[gc.Grove, str, int]]


def create_forest(forest_data: pd.DataFrame) -> ForestGroves:
    """Create groves for each species in forest data using global config."""
    forest = []

    for species_name, species_data in forest_data.groupby("species"):
        # create_grove will automatically use global config seed
        grove = create_grove(str(species_name))

        # Add all trees of this species to the grove
        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay=delay)

        forest.append((grove, str(species_name), len(species_data)))

    return forest


def calculate_shared_shade(groves: List[gc.Grove]) -> None:
    """Calculate shared light competition between groves using Grove's core shade system."""
    if len(groves) <= 1:
        return

    # Collect shade geometry from all groves
    all_coords = []
    for grove in groves:
        all_coords.extend(grove.create_shade_geometry_coords())

    # Apply shared shade calculation to each grove
    for grove in groves:
        grove.calculate_shade_together(all_coords)


def simulate_forest_growth(forest: ForestGroves, cycles: int) -> None:
    """Simulate forest growth with optional light competition."""
    groves = [grove for grove, _, _ in forest]

    for _ in tqdm(range(cycles), desc="Simulating forest growth"):
        # Calculate shared light competition if enabled
        if len(groves) > 1:
            calculate_shared_shade(groves)

        # Simulate one growth cycle for each grove
        for grove, _, _ in forest:
            grove.simulate(1)
