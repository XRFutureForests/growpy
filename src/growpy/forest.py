"""Atomic forest simulation functions for multi-species groves."""

from pathlib import Path
from typing import List, Tuple

import pandas as pd
from tqdm import tqdm

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available, some functions may not work")
    gc = None

# No direct config import needed - grove functions handle config internally
from .grove import add_tree_to_grove, create_grove, update_physics

# Type alias for cleaner code
ForestGroves = List[Tuple["gc.Grove", str, int]]


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


def calculate_shared_shade(groves: List, update_properties: bool = True) -> None:
    """Calculate shared light competition between groves using Grove's core shade system.
    
    Args:
        groves: List of Grove objects
        update_properties: Whether to update grove properties before shade calculation
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    if len(groves) <= 1:
        return

    # Update properties for each grove before shade calculation (as per Blender addon)
    if update_properties:
        for grove in groves:
            # Get current properties and reapply them to ensure consistency
            props = grove.get_properties()
            grove.set_properties(props)

    # Collect shade geometry from all groves (performance-optimized coordinate approach)
    all_coords = []
    for grove in groves:
        all_coords.extend(grove.create_shade_geometry_coords())

    # Apply shared shade calculation to each grove
    for grove in groves:
        grove.calculate_shade_together(all_coords)


def simulate_forest_growth(forest: ForestGroves, cycles: int, 
                           enable_light_competition: bool = True,
                           update_physics: bool = True) -> None:
    """Simulate forest growth with optional light competition.
    
    Args:
        forest: List of (grove, species_name, tree_count) tuples
        cycles: Number of growth cycles to simulate
        enable_light_competition: Whether to enable multi-species light competition
        update_physics: Whether to update physics calculations during simulation
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    groves = [grove for grove, _, _ in forest]

    for cycle in tqdm(range(cycles), desc="Simulating forest growth"):
        # Calculate shared light competition if enabled (as per Blender addon pattern)
        if enable_light_competition and len(groves) > 1:
            calculate_shared_shade(groves, update_properties=True)

        # Simulate one growth cycle for each grove
        for grove, _, _ in forest:
            if update_physics:
                # Update physics before each simulation step for accuracy
                grove.weigh_and_bend()
            grove.simulate(1)


def save_forest_state(forest: ForestGroves, output_dir: Path, 
                     compress: bool = True) -> None:
    """Save the current state of all groves in the forest.
    
    Args:
        forest: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save grove files
        compress: Whether to use compression
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    from .grove import save_grove_to_json
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for grove, species_name, _ in forest:
        filename = f"{species_name.replace(' ', '_')}.grove" if compress else f"{species_name.replace(' ', '_')}.json"
        output_path = output_dir / filename
        save_grove_to_json(grove, output_path, compress=compress)
