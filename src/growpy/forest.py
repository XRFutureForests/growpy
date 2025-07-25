"""Minimal forest simulation functions."""

from typing import List, Tuple

import pandas as pd

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available")
    gc = None

from .grove import add_tree_to_grove, create_grove


def create_forest(forest_data: pd.DataFrame) -> List[Tuple]:
    """Create groves for each species in forest data."""
    forest = []

    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)

        forest.append((grove, str(species_name), len(species_data)))

    return forest


def simulate_forest_growth(forest: List[Tuple], cycles: int) -> None:
    """Simulate forest growth with light competition."""
    if gc is None:
        raise ImportError("Grove core not available")

    groves = [grove for grove, _, _ in forest]

    for cycle in range(cycles):
        # Calculate shared light competition between species
        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                all_coords.extend(grove.create_shade_geometry_coords())

            for grove in groves:
                grove.calculate_shade_together(all_coords)

        # Simulate one growth cycle for each grove
        for grove, _, _ in forest:
            grove.weigh_and_bend()
            grove.simulate(1)
