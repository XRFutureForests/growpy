"""
Forest growth simulation module.

This module provides functions to create groves from CSV data and simulate
forest growth using The Grove's built-in light competition system.
"""

import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import the_grove_22_core as gc
from sklearn.linear_model import LinearRegression
from tqdm import tqdm

from .config import GrowPyConfig
from .exporters import (
    ModelFormat,
    export_grove_json_files,
    export_individual_tree_models,
)
from .species_utils import apply_species_preset

# Type aliases for better readability
ForestData = List[Tuple[gc.Grove, str, int]]
TreePosition = gc.Vector
TreeDirection = gc.Vector

# Data paths
DEFAULT_DATA_PATH = Path(__file__).parent.parent.parent / "data"
DEFAULT_INPUT_PATH = DEFAULT_DATA_PATH / "input"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_PATH / "output"


def calculate_tree_height(grove: gc.Grove, tree_index: int = 0) -> float:
    """Calculate tree height by finding the maximum Z-coordinate of all nodes."""
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        for node in branch.nodes:
            # node.pos is the absolute position as Vector(x, y, z)
            if node.pos.z > max_z:
                max_z = node.pos.z

            # Recursively check side branches
            for side_branch in node.side_branches:
                traverse_branch(side_branch)

    # Get the first tree (trunk branch)
    if grove.trees and len(grove.trees) > tree_index:
        traverse_branch(grove.trees[tree_index])

    return max_z


def generate_height_curves(
    species_list: List[str], config: GrowPyConfig, output_dir: Path
) -> pd.DataFrame:
    """
    Generate height curves for all species by simulating individual trees.

    Args:
        species_list: List of species names
        config: Configuration object
        output_dir: Directory to save height curves data

    Returns:
        DataFrame with height curves for each species
    """
    height_curves = pd.DataFrame(
        index=species_list, columns=range(config.height_model_flushes)
    )

    for species_name in tqdm(
        species_list, desc="Generating height curves", unit="species"
    ):
        grove = gc.Grove()
        grove.clear_trees()

        if config.random_seed:
            grove.set_random_seed(config.random_seed)

        # Apply species preset using Grove's built-in system
        apply_species_preset(grove, species_name)

        position = gc.Vector(0.0, 0.0, 0.0)
        direction = gc.Vector(0.0, 0.0, 1.0)
        delay = 0

        grove.add_new_tree(position, direction, delay)

        heights = []
        for _ in range(config.height_model_flushes):
            grove.simulate(1)
            heights.append(calculate_tree_height(grove, 0))

        # Store the height curve for the species
        height_curves.loc[species_name] = heights

    # Save the height curves to a CSV file
    height_curves_path = output_dir / "height_curves.csv"
    height_curves.to_csv(height_curves_path)

    # Create and save height curves plot
    plt.figure(figsize=(12, 6))
    for species_name in species_list:
        plt.plot(
            height_curves.columns, height_curves.loc[species_name], label=species_name
        )
    plt.title("Tree Height Curves")
    plt.xlabel("Growth Cycle")
    plt.ylabel("Height (m)")
    plt.legend()
    plt.grid()
    plt.savefig(output_dir / "height_curves.png")
    plt.close()

    return height_curves


def create_age_prediction_models(
    height_curves: pd.DataFrame, output_dir: Path
) -> Dict[str, LinearRegression]:
    """
    Create linear regression models to predict age from height for each species.

    Args:
        height_curves: DataFrame containing height curves for each species
        output_dir: Directory to save the models

    Returns:
        Dictionary mapping species names to trained LinearRegression models
    """
    height_to_age_models = {}

    for species_name in height_curves.index:
        # Get height data for this species
        heights = np.array(height_curves.loc[species_name].values)
        ages = np.array(range(1, height_curves.shape[1] + 1))

        # Create and fit linear regression model
        model = LinearRegression()
        model.fit(heights.reshape(-1, 1), ages.reshape(-1, 1))

        # Store the model
        height_to_age_models[species_name] = model

    # Save the models
    models_path = output_dir / "height_to_age_models.pkl"
    with open(models_path, "wb") as f:
        pickle.dump(height_to_age_models, f)

    return height_to_age_models


def predict_age_from_height(
    species_name: str, height: float, models: Dict[str, LinearRegression]
) -> int:
    """
    Predict tree age from height using the linear model for the given species.

    Args:
        species_name: Name of the species
        height: Tree height
        models: Dictionary of trained models

    Returns:
        Predicted age as integer
    """
    if species_name not in models:
        raise ValueError(f"No model available for species: {species_name}")

    model = models[species_name]
    predicted_age = model.predict(np.array([[height]]))[0][0]
    return max(0, int(predicted_age))  # Ensure age is not negative


def add_predicted_ages_to_data(
    data: pd.DataFrame, models: Dict[str, LinearRegression]
) -> pd.DataFrame:
    """
    Add predicted ages to forest data based on height and species.

    Args:
        data: Original forest data DataFrame
        models: Dictionary of trained age prediction models

    Returns:
        DataFrame with added 'predicted_age' column
    """
    data_with_ages = data.copy()
    data_with_ages["predicted_age"] = data_with_ages.apply(
        lambda row: predict_age_from_height(row["species"], row["height"], models),
        axis=1,
    )
    return data_with_ages


def create_forest_from_csv(csv_path: Path, config: GrowPyConfig) -> ForestData:
    """
    Create a forest from CSV data by grouping trees by species.
    This function always generates age predictions from height data.

    Args:
        csv_path: Path to CSV file containing tree data (demo_forest.csv)
                  Expected columns: x, y, z, species, height
        config: Configuration object for simulation parameters

    Returns:
        List of (grove, species_name, tree_count) tuples

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV data is invalid
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Load the original forest data
    data = pd.read_csv(csv_path)

    # Validate CSV has required columns for the basic forest data
    required = ["x", "y", "z", "species", "height"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Validate data completeness
    for col in required:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains missing values")

    # Validate species
    unique_species = data["species"].unique()
    from .species_utils import list_species

    available_species = list_species()
    invalid_species = [s for s in unique_species if s not in available_species]
    if invalid_species:
        raise ValueError(
            f"Invalid species found in CSV: {invalid_species}. "
            f"Available species: {available_species}"
        )

    # Get unique species for model generation
    species_list = data["species"].unique().tolist()

    # Set up output directory for intermediate files with input-specific structure
    input_name = csv_path.stem  # e.g., "demo_forest"
    input_output_dir = config.output_dir / input_name / "analysis"
    input_output_dir.mkdir(parents=True, exist_ok=True)

    # Always generate height curves and age prediction models
    height_curves = generate_height_curves(species_list, config, input_output_dir)

    # Create age prediction models
    models = create_age_prediction_models(height_curves, input_output_dir)

    # Add predicted ages to the data
    data = add_predicted_ages_to_data(data, models)

    # Save the enhanced data for future use
    enhanced_csv_path = input_output_dir / f"{input_name}_with_predicted_age.csv"
    data.to_csv(enhanced_csv_path, index=False)

    # Set growth cycles based on maximum predicted age if not explicitly set
    max_flushes = _calculate_max_growth_cycles(data, config)
    if config.growth_cycles is None:
        config.growth_cycles = max_flushes

    forest_data = []
    for species_name, species_group in data.groupby("species"):
        grove = _create_grove_for_species(
            str(species_name), species_group, max_flushes, config
        )
        forest_data.append((grove, str(species_name), len(species_group)))

    return forest_data


def simulate_forest_growth(forest_data: ForestData, config: GrowPyConfig) -> None:
    """
    Simulate forest growth with light competition between all trees.

    This function follows The Grove's recommended approach for multi-species
    forest simulation with shared light environment.

    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        config: Configuration object containing growth parameters
    """
    if not forest_data:
        return

    grove_objects = _extract_grove_objects(forest_data)

    # Ensure growth_cycles is set
    cycles = config.growth_cycles
    if cycles is None:
        cycles = config.height_model_flushes  # Fallback to height model flushes

    for cycle in tqdm(range(cycles), desc="Growing forest", unit="cycle"):
        # Collect shade geometry from all groves for light competition
        shade_coordinates = _collect_shade_geometry(grove_objects)

        # Calculate shade and simulate growth for each grove
        _simulate_growth_cycle(grove_objects, shade_coordinates)


def add_trees(forest: List, csv_path: Path, config: GrowPyConfig) -> ForestData:
    """
    Legacy function for backwards compatibility.

    Deprecated: Use create_forest_from_csv instead.
    """
    return create_forest_from_csv(csv_path, config)


def grow_forest(forest_data: ForestData, config: GrowPyConfig) -> None:
    """
    Legacy function for backwards compatibility.

    Deprecated: Use simulate_forest_growth instead.
    """
    simulate_forest_growth(forest_data, config)


# Private helper functions
def _calculate_max_growth_cycles(data: pd.DataFrame, config: GrowPyConfig) -> int:
    """Calculate maximum growth cycles needed based on predicted ages."""
    max_age = data["predicted_age"].max()
    return int(max_age / config.age_to_flush_ratio) + 1  # Ensure at least one flush


def _create_grove_for_species(
    species_name: str,
    species_data: pd.DataFrame,
    max_flushes: int,
    config: GrowPyConfig,
) -> gc.Grove:
    """Create and populate a grove for a single species."""
    grove = gc.Grove()
    grove.clear_trees()  # Clear default tree as recommended

    if config.random_seed:
        grove.set_random_seed(config.random_seed)

    apply_species_preset(grove, species_name)
    _add_trees_to_grove(grove, species_data, max_flushes, config)

    return grove


def _add_trees_to_grove(
    grove: gc.Grove, species_data: pd.DataFrame, max_flushes: int, config: GrowPyConfig
) -> None:
    """Add trees to a grove based on CSV data."""
    for _, tree_row in species_data.iterrows():
        position = _create_tree_position(tree_row)
        direction = _create_default_direction()
        delay = _calculate_growth_delay(tree_row, max_flushes, config)

        grove.add_new_tree(position, direction, delay)


def _create_tree_position(tree_row: pd.Series) -> TreePosition:
    """Create a 3D position vector from CSV row data."""
    return gc.Vector(float(tree_row.x), float(tree_row.y), float(tree_row.z))


def _create_default_direction() -> TreeDirection:
    """Create default upward growth direction."""
    return gc.Vector(0.0, 0.0, 1.0)


def _calculate_growth_delay(
    tree_row: pd.Series, max_flushes: int, config: GrowPyConfig
) -> int:
    """Calculate growth delay based on predicted age."""
    required_flushes = int(tree_row["predicted_age"] / config.age_to_flush_ratio) + 1
    return max_flushes - required_flushes


def _extract_grove_objects(forest_data: ForestData) -> List[gc.Grove]:
    """Extract grove objects from forest data tuples."""
    return [grove for grove, _, _ in forest_data]


def _collect_shade_geometry(grove_objects: List[gc.Grove]) -> List:
    """Collect shade geometry coordinates from all groves."""
    coordinates = []
    for grove in grove_objects:
        coordinates.extend(grove.create_shade_geometry_coords())
    return coordinates


def _simulate_growth_cycle(
    grove_objects: List[gc.Grove], shade_coordinates: List
) -> None:
    """Simulate one growth cycle for all groves with shared shade."""
    for grove in grove_objects:
        grove.calculate_shade_together(shade_coordinates)
        grove.simulate(1)  # One flush at a time as documented


def _run_example_simulation() -> None:
    """Run an example simulation for testing purposes."""
    config = GrowPyConfig()
    config.output_dir = Path(DEFAULT_OUTPUT_PATH)

    csv_path = Path(DEFAULT_INPUT_PATH / "demo_forest.csv")
    input_name = csv_path.stem  # "demo_forest"

    # Create forest and simulate growth
    forest_data = create_forest_from_csv(csv_path, config)
    simulate_forest_growth(forest_data, config)

    # Export results with organized structure
    export_grove_json_files(forest_data, config.output_dir, input_name)

    lod_configs = GrowPyConfig.get_lod_configs()
    export_individual_tree_models(
        forest_data,
        config.output_dir,
        lod_configs,
        model_format=ModelFormat.USD,
        input_name=input_name,
    )


if __name__ == "__main__":
    _run_example_simulation()
