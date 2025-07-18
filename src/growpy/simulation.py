"""
Forest growth simulation module.

This module provides functions to create groves from CSV data and simulate
forest growth using The Grove's built-in light competition system.
"""

import logging
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

# Set up logging
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when input validation fails."""
    pass
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
    """
    Calculate tree height by finding the maximum Z-coordinate of all nodes.
    
    Args:
        grove: Grove object containing trees
        tree_index: Index of the tree to measure (default: 0)
        
    Returns:
        Tree height as float
        
    Raises:
        ValidationError: If tree index is invalid or grove is empty
    """
    if not grove.trees:
        raise ValidationError("Grove contains no trees")
        
    if tree_index < 0 or tree_index >= len(grove.trees):
        raise ValidationError(f"Invalid tree index {tree_index}. Grove has {len(grove.trees)} trees")
    
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        if not hasattr(branch, 'nodes'):
            return
            
        for node in branch.nodes:
            # node.pos is the absolute position as Vector(x, y, z)
            if hasattr(node, 'pos') and hasattr(node.pos, 'z'):
                if node.pos.z > max_z:
                    max_z = node.pos.z

            # Recursively check side branches
            if hasattr(node, 'side_branches'):
                for side_branch in node.side_branches:
                    traverse_branch(side_branch)

    # Get the specified tree (trunk branch)
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


def create_flush_prediction_models(
    height_curves: pd.DataFrame, output_dir: Path
) -> Dict[str, LinearRegression]:
    """
    Create linear regression models to predict required flushes from target height for each species.

    Args:
        height_curves: DataFrame containing height curves for each species
        output_dir: Directory to save the models

    Returns:
        Dictionary mapping species names to trained LinearRegression models
    """
    height_to_flush_models = {}

    for species_name in height_curves.index:
        heights = np.array(height_curves.loc[species_name].values)
        flushes = np.array(range(1, height_curves.shape[1] + 1))
        model = LinearRegression()
        model.fit(heights.reshape(-1, 1), flushes.reshape(-1, 1))
        height_to_flush_models[species_name] = model

    models_path = output_dir / "height_to_flush_models.pkl"
    with open(models_path, "wb") as f:
        pickle.dump(height_to_flush_models, f)

    return height_to_flush_models


def predict_flushes_from_height(
    species_name: str, height: float, models: Dict[str, LinearRegression]
) -> int:
    """
    Predict required flushes from height using the linear model for the given species.

    Args:
        species_name: Name of the species
        height: Tree height
        models: Dictionary of trained models

    Returns:
        Predicted flushes needed as integer
        
    Raises:
        ValueError: If species not found in models or height is invalid
        ValidationError: If prediction fails
    """
    if species_name not in models:
        raise ValueError(f"No model available for species: {species_name}")
    
    # Validate height input
    if not isinstance(height, (int, float)) or not np.isfinite(height):
        raise ValidationError(f"Invalid height value: {height}")
    
    if height <= 0:
        raise ValidationError(f"Height must be positive: {height}")

    try:
        model = models[species_name]
        prediction = model.predict(np.array([[height]]))
        
        # Safe array access with bounds checking
        if len(prediction) == 0 or len(prediction[0]) == 0:
            raise ValidationError("Model returned empty prediction")
            
        predicted_flushes = prediction[0][0]
        
        # Validate prediction result
        if not np.isfinite(predicted_flushes):
            raise ValidationError(f"Model prediction is not finite: {predicted_flushes}")
            
        return max(1, int(predicted_flushes))  # Ensure at least 1 flush
        
    except Exception as e:
        raise ValidationError(f"Prediction failed for species {species_name}, height {height}: {e}")


def add_predicted_flushes_to_data(
    data: pd.DataFrame, models: Dict[str, LinearRegression]
) -> pd.DataFrame:
    """
    Add predicted required flushes to forest data based on height and species.

    Args:
        data: Original forest data DataFrame
        models: Dictionary of trained flush prediction models

    Returns:
        DataFrame with added 'required_flushes' column
    """
    data_with_flushes = data.copy()
    data_with_flushes["required_flushes"] = data_with_flushes.apply(
        lambda row: predict_flushes_from_height(row["species"], row["height"], models),
        axis=1,
    )
    return data_with_flushes


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
            
    # Validate numerical data ranges
    _validate_forest_data(data)

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

    # Always generate height curves and flush prediction models
    height_curves = generate_height_curves(species_list, config, input_output_dir)

    # Create flush prediction models instead of age prediction models
    models = create_flush_prediction_models(height_curves, input_output_dir)

    # Add predicted flushes to the data
    data = add_predicted_flushes_to_data(data, models)

    # Save the enhanced data for future use
    enhanced_csv_path = input_output_dir / f"{input_name}_with_predicted_flushes.csv"
    data.to_csv(enhanced_csv_path, index=False)

    # Set growth cycles based on maximum required flushes
    max_flushes = int(data["required_flushes"].max()) + 1
    growth_cycles = max_flushes

    forest_data = []
    for species_name, species_group in data.groupby("species"):
        grove = _create_grove_for_species(
            str(species_name), species_group, growth_cycles, config
        )
        forest_data.append((grove, str(species_name), len(species_group)))

    return forest_data, growth_cycles


def simulate_forest_growth(forest_data: ForestData, config: GrowPyConfig, growth_cycles: int) -> None:
    """
    Simulate forest growth with light competition between all trees.

    This function follows The Grove's recommended approach for multi-species
    forest simulation with shared light environment.

    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        config: Configuration object containing growth parameters
        growth_cycles: Number of growth cycles to simulate
    """
    if not forest_data:
        return

    grove_objects = _extract_grove_objects(forest_data)

    for cycle in tqdm(range(growth_cycles), desc="Growing forest", unit="cycle"):
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


def grow_forest(forest_data: ForestData, config: GrowPyConfig, growth_cycles: int) -> None:
    """
    Legacy function for backwards compatibility.

    Deprecated: Use simulate_forest_growth instead.
    """
    simulate_forest_growth(forest_data, config, growth_cycles)


# Private helper functions
def _validate_forest_data(data: pd.DataFrame) -> None:
    """
    Validate numerical data in forest CSV for reasonable ranges.
    
    Args:
        data: DataFrame containing forest data
        
    Raises:
        ValidationError: If data contains invalid values
    """
    # Validate coordinates are finite
    coordinate_cols = ['x', 'y', 'z']
    for col in coordinate_cols:
        if col in data.columns:
            if not data[col].apply(lambda x: np.isfinite(x)).all():
                raise ValidationError(f"Column '{col}' contains invalid values (inf/nan)")
    
    # Validate heights are positive
    if 'height' in data.columns:
        if (data['height'] <= 0).any():
            raise ValidationError("Tree heights must be positive")
        if (data['height'] > 200).any():  # Reasonable upper bound
            logger.warning("Some trees have heights > 200m, which may be unrealistic")
    
    # Check for duplicate positions (potential data issue)
    if len(coordinate_cols) == 3 and all(col in data.columns for col in coordinate_cols):
        duplicates = data.duplicated(subset=coordinate_cols, keep=False)
        if duplicates.any():
            num_duplicates = duplicates.sum()
            logger.warning(f"Found {num_duplicates} trees with duplicate positions")



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
    """
    Add trees to a grove based on CSV data with pre-computed required flushes.

    The delay system ensures all trees finish growing at their CSV heights simultaneously:
    - Trees needing fewer flushes get longer delays (start later)
    - Trees needing more flushes get shorter delays (start earlier)
    """
    for _, tree_row in species_data.iterrows():
        position = _create_tree_position(tree_row)
        direction = _create_default_direction()
        delay = _calculate_simple_delay(tree_row, max_flushes, config)
        grove.add_new_tree(position, direction, delay)


def _create_tree_position(tree_row: pd.Series) -> TreePosition:
    """
    Create a 3D position vector from CSV row data.

    Note: Uses CSV coordinates directly (X, Y, Z as-is).
    If importing into Blender, you may need to flip Y-axis by scaling Y by -1
    after import due to coordinate system differences. See docs/IMPORT_ISSUES.md
    
    Args:
        tree_row: Pandas Series with x, y, z coordinates
        
    Returns:
        3D position vector
        
    Raises:
        ValidationError: If coordinates are invalid
    """
    try:
        x, y, z = float(tree_row.x), float(tree_row.y), float(tree_row.z)
        
        # Validate coordinates are finite
        if not all(np.isfinite([x, y, z])):
            raise ValidationError(f"Invalid coordinates: x={x}, y={y}, z={z}")
            
        return gc.Vector(x, y, z)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Failed to parse coordinates: {e}")


def _create_default_direction() -> TreeDirection:
    """Create default upward growth direction."""
    return gc.Vector(0.0, 0.0, 1.0)


def _calculate_simple_delay(
    tree_row: pd.Series, max_flushes: int, config: GrowPyConfig
) -> int:
    """
    Calculate growth delay for a tree based on its required flushes.
    
    Args:
        tree_row: Row containing tree data including 'required_flushes'
        max_flushes: Maximum flushes needed across all trees
        config: Configuration object (unused but kept for API consistency)
    
    Returns:
        Delay in growth cycles (non-negative integer)
    """
    required_flushes = tree_row["required_flushes"]
    
    # Delay = total_flushes - flushes_needed
    # Trees that need fewer flushes get longer delays
    # Trees that need more flushes get shorter delays
    delay = max_flushes - required_flushes
    
    # Ensure delay is non-negative
    return max(0, delay)




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

