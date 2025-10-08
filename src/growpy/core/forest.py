"""Forest simulation functions with Grove API integration."""

from typing import List, Tuple
import pandas as pd
from tqdm import tqdm

try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_CORE_AVAILABLE = False

from .grove import add_tree_to_grove, create_grove


def create_forest(forest_data: pd.DataFrame) -> List[Tuple]:
    """Create groves for each species in forest data.

    Groups trees by species and creates a separate Grove instance for each species.
    Trees are placed at specified coordinates with optional growth delays.

    Args:
        forest_data: DataFrame with required columns: x, y, species.
                     Optional columns: z (defaults to 0), height, delay

    Returns:
        List of tuples: (grove_instance, species_name, tree_count)
    """
    forest = []

    # Ensure z column exists (default to 0 if not provided)
    if 'z' not in forest_data.columns:
        forest_data['z'] = 0.0

    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)

        forest.append((grove, str(species_name), len(species_data)))

    return forest


def simulate_forest_growth(forest: List[Tuple], cycles: int) -> None:
    """Simulate forest growth with inter-species light competition.

    Simulates realistic forest growth where trees compete for light across
    species boundaries. Uses Grove's shade geometry system to calculate
    light occlusion from neighboring trees.

    Args:
        forest: List of (grove, species_name, tree_count) tuples from create_forest()
        cycles: Number of growth cycles to simulate

    Raises:
        ImportError: If Grove core (the_grove_22_core) is not available
    """
    if not GROVE_CORE_AVAILABLE:
        raise ImportError("Grove core (the_grove_22_core) not available")

    groves = [grove for grove, _, _ in forest]

    for cycle in tqdm(range(cycles), desc="Simulating growth cycles", unit="cycle"):
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

    Similar to create_forest() but includes additional metadata tracking for
    analysis and debugging purposes.

    Args:
        forest_data: DataFrame with required columns: x, y, species.
                     Optional columns: z (defaults to 0), height, delay

    Returns:
        List of tuples: (grove_instance, species_name, tree_count, attributes_dict)
        where attributes_dict contains: tree_count, avg_height, positions, delays
    """
    forest = []

    # Ensure z column exists (default to 0 if not provided)
    if 'z' not in forest_data.columns:
        forest_data['z'] = 0.0

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
