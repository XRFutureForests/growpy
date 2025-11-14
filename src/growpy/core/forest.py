"""Forest simulation functions with Grove API integration."""

from typing import Any, Dict, List, Tuple

import pandas as pd
import the_grove_22_core as gc
from tqdm import tqdm

from .grove import add_tree_to_grove, create_grove


def create_forest(forest_data: pd.DataFrame) -> List[Tuple[gc.Grove, str, int]]:
    """Create groves for each species in forest data.

    Args:
        forest_data: DataFrame with columns: x, y, species, z (optional), delay (optional)

    Returns:
        List of tuples: (grove_instance, species_name, tree_count)
    """
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    forest = []
    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)

        forest.append((grove, str(species_name), len(species_data)))

    return forest


def simulate_forest_growth(
    forest: List[Tuple[gc.Grove, str, int]], cycles: int, smooth_iterations: int = 10
) -> None:
    """Simulate forest growth with inter-species light competition and optional smoothing.

    The smoothing workflow (applied if smooth_iterations > 0):
    1. grove.smooth_minimal() - Fixes ugly kinks on thick branches (one-time operation)
    2. grove.smooth() - Reduces sharp corner angles (called smooth_iterations times)
    3. grove.weigh_and_bend() - Re-calculates branch positions based on smoothed angles

    Without step 3 (weigh_and_bend), smoothing has no effect on the final geometry!

    Args:
        forest: List of (grove, species_name, tree_count) tuples from create_forest()
        cycles: Number of growth cycles to simulate
        smooth_iterations: Number of smoothing iterations (default: 10, recommended: 10-20)
                          Set to 0 to disable smoothing entirely
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

    # Apply smoothing AFTER simulation but BEFORE building
    # This reduces sharp branch angles for smoother geometry
    if smooth_iterations > 0:
        print(f"\n[Smoothing] Applying {smooth_iterations} smoothing iterations to {len(forest)} species")
        for grove, species_name, _ in forest:
            grove.smooth_minimal()
            # Show progress for smoothing iterations
            for i in tqdm(
                range(smooth_iterations),
                desc=f"Smoothing {species_name}",
                unit="iter",
            ):
                grove.smooth()

            # CRITICAL: Re-calculate branch bending after smoothing
            # This applies the smoothed angles to actual branch positions
            grove.weigh_and_bend()
            print(f"[Smoothing] Completed for {species_name} - grove modified in-place")
