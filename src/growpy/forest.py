"""Enhanced forest simulation functions with proper Grove API integration."""

from typing import List, Tuple

from .common import gc, ensure_grove_available, pd
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
    """Simulate forest growth with light competition using proper Grove API.

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        cycles: Number of growth cycles to simulate
    """
    ensure_grove_available()

    groves = [grove for grove, _, _ in forest]

    for cycle in range(cycles):
        # Calculate shared light competition between species
        if len(groves) > 1:
            # Create comprehensive shade geometry for multi-species competition
            all_coords = []
            for grove in groves:
                coords = grove.create_shade_geometry_coords()
                all_coords.extend(coords)

            # Apply calculated shade to all groves for realistic competition
            for grove in groves:
                grove.calculate_shade_together(all_coords)

        # Simulate one growth cycle for each grove with proper Grove workflow
        for grove, species_name, tree_count in forest:
            # Apply Grove's weight and bend calculations for realistic branch physics
            grove.weigh_and_bend()

            # Simulate growth for one cycle
            grove.simulate(1)


def create_forest_with_attributes(forest_data: pd.DataFrame) -> List[Tuple]:
    """Create groves for each species with enhanced attribute tracking.

    Args:
        forest_data: DataFrame with tree positions, species, and optional attributes

    Returns:
        List of (grove, species_name, tree_count, attributes) tuples
    """
    forest = []

    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        # Track additional attributes if available
        attributes = {
            "tree_count": len(species_data),
            "avg_height": species_data.get("height", pd.Series([0])).mean(),
            "positions": [],
            "delays": [],
        }

        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))

            add_tree_to_grove(grove, position, delay)

            attributes["positions"].append(position)
            attributes["delays"].append(delay)

        forest.append((grove, str(species_name), len(species_data), attributes))

    return forest
