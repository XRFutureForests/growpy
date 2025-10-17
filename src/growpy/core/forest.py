"""Forest simulation functions with Grove API integration."""

from typing import List, Tuple, Dict, Any
import pandas as pd
from tqdm import tqdm
import the_grove_22_core as gc

from .grove import add_tree_to_grove, create_grove


def create_forest(forest_data: pd.DataFrame) -> List[Tuple[gc.Grove, str, int]]:
    """Create groves for each species in forest data.

    Args:
        forest_data: DataFrame with columns: x, y, species, z (optional), delay (optional)

    Returns:
        List of tuples: (grove_instance, species_name, tree_count)
    """
    if 'z' not in forest_data.columns:
        forest_data['z'] = 0.0

    forest = []
    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)

        forest.append((grove, str(species_name), len(species_data)))

    return forest


def simulate_forest_growth(forest: List[Tuple[gc.Grove, str, int]], cycles: int) -> None:
    """Simulate forest growth with inter-species light competition.

    Args:
        forest: List of (grove, species_name, tree_count) tuples from create_forest()
        cycles: Number of growth cycles to simulate
    """
    groves = [grove for grove, _, _ in forest]

    for cycle in tqdm(range(cycles), desc="Simulating growth cycles", unit="cycle"):
        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                coords = grove.create_shade_geometry_coords()
                all_coords.extend(coords)

            for grove in groves:
                grove.calculate_shade_together(all_coords)

        for grove, species_name, tree_count in forest:
            grove.weigh_and_bend()
            grove.simulate(1)


def create_forest_with_attributes(forest_data: pd.DataFrame) -> List[Tuple[gc.Grove, str, int, Dict[str, Any]]]:
    """Create groves for each species with enhanced attribute tracking.

    Args:
        forest_data: DataFrame with columns: x, y, species, z (optional), height (optional), delay (optional)

    Returns:
        List of tuples: (grove_instance, species_name, tree_count, attributes_dict)
    """
    if 'z' not in forest_data.columns:
        forest_data['z'] = 0.0

    forest = []
    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

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
