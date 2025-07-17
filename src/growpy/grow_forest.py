from pathlib import Path
from typing import List, Tuple

import pandas as pd
import the_grove_22_core as gc
from config import GrowPyConfig
from export_forest import ModelFormat, export_complete_forest
from helper import apply_species_preset, validate_csv_data
from tqdm import tqdm

# Data paths
DEFAULT_DATA_PATH = Path(__file__).parent.parent.parent / "data"


def add_trees(
    forest: List, csv_path: Path, config: GrowPyConfig
) -> List[Tuple[gc.Grove, str, int]]:
    data = pd.read_csv(
        csv_path
    )  # TODO: add support for other formats like dict or string
    validate_csv_data(data)
    max_flushes = data["predicted_age"].max() // 3 + 1  # Ensure at least one flush
    config.growth_cycles = max_flushes
    # Create grove for each species
    for species, group in data.groupby("species"):
        species = str(
            species
        )  # TODO: implement a species map, which allows to use species names that are not in the Grove presets and map them to Grove presets
        grove = gc.Grove()

        # Clear default tree as recommended in Grove documentation
        grove.clear_trees()

        if config.random_seed:
            grove.set_random_seed(config.random_seed)

        # Apply species preset using Grove's built-in system
        apply_species_preset(grove, species)

        # Add trees at positions using Grove's add_new_tree
        positions = []
        for _, row in group.iterrows():
            positions.append(gc.Vector(float(row.x), float(row.y), float(row.z)))

        # Default directions and no delays
        directions = [gc.Vector(0.0, 0.0, 1.0)] * len(positions)
        # Determine delays based on height_curves and target heights in data
        delays = []
        for _, row in group.iterrows():
            required_flushes = (
                row["predicted_age"] // 3 + 1
            )  # Ensure at least one flush
            delays.append(max_flushes - required_flushes)

        # Add trees to grove
        for position, direction, delay in zip(positions, directions, delays):
            grove.add_new_tree(position, direction, delay)

        forest.append((grove, species, len(group)))

    return forest


def grow_forest(forest: List[Tuple[gc.Grove, str, int]], config: GrowPyConfig) -> None:
    # Simulate all groves together with shared light environment (per Grove docs)
    grove_objects = [g[0] for g in forest]

    for cycle in tqdm(range(config.growth_cycles), desc="Growing forest", unit="cycle"):
        # Step 1: Collect shade geometry from all groves
        coords = []
        for grove in grove_objects:
            coords.extend(grove.create_shade_geometry_coords())

        # Step 2: Calculate shade and simulate each grove
        for grove in grove_objects:
            grove.calculate_shade_together(coords)
            grove.simulate(1)  # One flush at a time as documented

    return None


if __name__ == "__main__":
    # Example usage
    config = GrowPyConfig()
    config.output_dir = Path(DEFAULT_DATA_PATH / "output")

    csv_path = Path(DEFAULT_DATA_PATH / "demo_forest_with_predicted_age.csv")

    forest = []
    forest = add_trees(forest, csv_path, config)

    grow_forest(forest, config)

    # Export complete forest data with all formats
    export_complete_forest(
        forest=forest,
        config=config,
        include_json=True,
        include_grove_models=True,
        include_individual_trees=False,  # Set to True if individual tree exports are needed
        model_format=ModelFormat.OBJ,  # Can be changed to ModelFormat.USD
    )
