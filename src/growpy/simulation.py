"""
Forest growth simulation module.

This module provides atomic functions for forest simulation including:
- CSV data loading and validation
- Height curve generation and age prediction
- Grove creation and tree growth simulation
- Data processing utilities

For high-level forest creation workflows, see generate_forest.py.
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
        index=species_list, columns=range(config.height_model_cycles)
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
        for _ in range(config.height_model_cycles):
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


def create_cycle_prediction_models(
    height_curves: pd.DataFrame, output_dir: Path
) -> Dict[str, LinearRegression]:
    """
    Create linear regression models to predict required cycles from target height for each species.

    Args:
        height_curves: DataFrame containing height curves for each species
        output_dir: Directory to save the models

    Returns:
        Dictionary mapping species names to trained LinearRegression models
    """
    height_to_cycle_models = {}

    for species_name in height_curves.index:
        heights = np.array(height_curves.loc[species_name].values)
        cycles = np.array(range(1, height_curves.shape[1] + 1))
        model = LinearRegression()
        model.fit(heights.reshape(-1, 1), cycles.reshape(-1, 1))
        height_to_cycle_models[species_name] = model

    models_path = output_dir / "height_to_cycle_models.pkl"
    with open(models_path, "wb") as f:
        pickle.dump(height_to_cycle_models, f)

    return height_to_cycle_models


def predict_cycles_from_height(
    species_name: str, height: float, models: Dict[str, LinearRegression]
) -> int:
    """
    Predict required cycles from height using the linear model for the given species.

    Args:
        species_name: Name of the species
        height: Tree height
        models: Dictionary of trained models

    Returns:
        Predicted cycles needed as integer
        
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
            
        predicted_cycles = prediction[0][0]
        
        # Validate prediction result
        if not np.isfinite(predicted_cycles):
            raise ValidationError(f"Model prediction is not finite: {predicted_cycles}")
            
        return max(1, int(predicted_cycles))  # Ensure at least 1 cycle
        
    except Exception as e:
        raise ValidationError(f"Prediction failed for species {species_name}, height {height}: {e}")


def add_predicted_cycles_to_data(
    data: pd.DataFrame, models: Dict[str, LinearRegression]
) -> pd.DataFrame:
    """
    Add predicted required cycles to forest data based on height and species.

    Args:
        data: Original forest data DataFrame
        models: Dictionary of trained cycle prediction models

    Returns:
        DataFrame with added 'required_cycles' column
    """
    data_with_cycles = data.copy()
    data_with_cycles["required_cycles"] = data_with_cycles.apply(
        lambda row: predict_cycles_from_height(row["species"], row["height"], models),
        axis=1,
    )
    return data_with_cycles


def load_and_validate_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate CSV forest data.
    
    Args:
        csv_path: Path to CSV file containing tree data
        
    Returns:
        Validated DataFrame with forest data
        
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

    return data


def generate_height_curves_and_models(
    data: pd.DataFrame, csv_path: Path, config: GrowPyConfig
) -> Tuple[pd.DataFrame, Dict[str, LinearRegression]]:
    """
    Generate height curves and cycle prediction models for all species.
    
    Args:
        data: Validated forest data
        csv_path: Original CSV path (for naming output files)
        config: Configuration object
        
    Returns:
        Tuple of (height_curves DataFrame, prediction models dict)
    """
    # Get unique species for model generation
    species_list = data["species"].unique().tolist()

    # Set up output directory for intermediate files with input-specific structure
    input_name = csv_path.stem  # e.g., "demo_forest"
    input_output_dir = config.output_dir / input_name / "analysis"
    input_output_dir.mkdir(parents=True, exist_ok=True)

    # Generate height curves and cycle prediction models
    height_curves = generate_height_curves(species_list, config, input_output_dir)
    models = create_cycle_prediction_models(height_curves, input_output_dir)
    
    return height_curves, models


def add_growth_predictions_to_data(
    data: pd.DataFrame, models: Dict[str, LinearRegression], csv_path: Path, config: GrowPyConfig
) -> Tuple[pd.DataFrame, int]:
    """
    Add growth cycle predictions to forest data and calculate total growth cycles needed.
    
    Args:
        data: Original forest data
        models: Cycle prediction models
        csv_path: Original CSV path (for naming output files)
        config: Configuration object
        
    Returns:
        Tuple of (enhanced data with predictions, growth cycles needed)
    """
    # Add predicted cycles to the data
    enhanced_data = add_predicted_cycles_to_data(data, models)

    # Save the enhanced data for future use
    input_name = csv_path.stem
    input_output_dir = config.output_dir / input_name / "analysis"
    enhanced_csv_path = input_output_dir / f"{input_name}_with_predicted_cycles.csv"
    enhanced_data.to_csv(enhanced_csv_path, index=False)

    # Set growth cycles based on maximum required cycles
    max_cycles = int(enhanced_data["required_cycles"].max()) + 1
    growth_cycles = max_cycles
    
    return enhanced_data, growth_cycles


def create_groves_from_data(
    data: pd.DataFrame, growth_cycles: int, config: GrowPyConfig
) -> ForestData:
    """
    Create grove objects from enhanced forest data.
    
    Args:
        data: Enhanced forest data with cycle predictions
        growth_cycles: Total growth cycles needed
        config: Configuration object
        
    Returns:
        List of (grove, species_name, tree_count) tuples
    """
    forest_data = []
    for species_name, species_group in data.groupby("species"):
        grove = _create_grove_for_species(
            str(species_name), species_group, growth_cycles, config
        )
        forest_data.append((grove, str(species_name), len(species_group)))

    return forest_data




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

    for _ in tqdm(range(growth_cycles), desc="Growing forest", unit="cycle"):
        # Collect shade geometry from all groves for light competition
        shade_coordinates = _collect_shade_geometry(grove_objects)

        # Calculate shade and simulate growth for each grove
        _simulate_growth_cycle(grove_objects, shade_coordinates)




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
    max_cycles: int,
    config: GrowPyConfig,
) -> gc.Grove:
    """Create and populate a grove for a single species."""
    grove = gc.Grove()
    grove.clear_trees()  # Clear default tree as recommended

    if config.random_seed:
        grove.set_random_seed(config.random_seed)

    apply_species_preset(grove, species_name)
    _add_trees_to_grove(grove, species_data, max_cycles, config)

    return grove


def _add_trees_to_grove(
    grove: gc.Grove, species_data: pd.DataFrame, max_cycles: int, config: GrowPyConfig
) -> None:
    """
    Add trees to a grove based on CSV data with pre-computed required cycles.

    The delay system ensures all trees finish growing at their CSV heights simultaneously:
    - Trees needing fewer cycles get longer delays (start later)
    - Trees needing more cycles get shorter delays (start earlier)
    """
    for _, tree_row in species_data.iterrows():
        position = _create_tree_position(tree_row)
        direction = _create_default_direction()
        delay = _calculate_simple_delay(tree_row, max_cycles, config)
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
    tree_row: pd.Series, max_cycles: int, config: GrowPyConfig
) -> int:
    """
    Calculate growth delay for a tree based on its required cycles.
    
    Args:
        tree_row: Row containing tree data including 'required_cycles'
        max_cycles: Maximum cycles needed across all trees
        config: Configuration object (unused but kept for API consistency)
    
    Returns:
        Delay in growth cycles (non-negative integer)
    """
    _ = config  # Unused parameter for API consistency
    required_cycles = tree_row["required_cycles"]
    
    # Delay = total_cycles - cycles_needed
    # Trees that need fewer cycles get longer delays
    # Trees that need more cycles get shorter delays
    delay = max_cycles - required_cycles
    
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
        grove.simulate(1)  # One cycle at a time as documented

