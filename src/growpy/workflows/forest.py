"""
Forest generation workflows.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
import the_grove_22_core as gc

from ..core.grove import create_grove, add_tree_to_grove, calculate_shared_light_competition
from ..core.validate import validate_forest_data
from ..core.predict import predict_cycles_for_data
from ..io.csv import load_csv
from ..core.config import GrowPyConfig

logger = logging.getLogger(__name__)

# Type alias
ForestData = List[Tuple[gc.Grove, str, int]]


def create_forest_from_csv(csv_path: Path, height_models: Dict = None, 
                          config: GrowPyConfig = None) -> Tuple[ForestData, pd.DataFrame]:
    """
    Create forest groves from CSV data.
    
    Args:
        csv_path: Path to CSV file
        height_models: Optional height prediction models
        config: Configuration object
        
    Returns:
        Tuple of (forest_data, enhanced_data)
    """
    if config is None:
        config = GrowPyConfig()
    
    # Load and validate data
    data = load_csv(csv_path)
    validate_forest_data(data)
    
    # Add predictions if models provided
    if height_models and "height" in data.columns:
        data = predict_cycles_for_data(data, height_models)
    
    # Create groves
    forest_data = _create_groves_from_data(data, config)
    
    return forest_data, data


def simulate_forest_growth(forest_data: ForestData, max_cycles: int = None) -> None:
    """
    Simulate growth for all groves in forest.
    
    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        max_cycles: Maximum cycles to simulate (auto-calculated if None)
    """
    groves = [grove for grove, _, _ in forest_data]
    
    # Calculate max cycles if not provided
    if max_cycles is None:
        max_cycles = _calculate_max_cycles(forest_data)
    
    logger.info(f"Simulating forest growth for {max_cycles} cycles")
    
    # Simulate growth with light competition
    for cycle in range(max_cycles):
        # Calculate light competition between all groves
        calculate_shared_light_competition(groves)
        
        # Simulate one cycle for each grove
        for grove, species_name, _ in forest_data:
            grove.simulate(1)
        
        # Log progress
        if (cycle + 1) % 10 == 0:
            logger.debug(f"Completed cycle {cycle + 1}/{max_cycles}")
    
    logger.info("Forest growth simulation completed")


def _create_groves_from_data(data: pd.DataFrame, config: GrowPyConfig) -> ForestData:
    """Create groves from forest data."""
    forest_data = []
    
    # Group by species
    species_groups = data.groupby("species")
    
    for species_name, species_data in species_groups:
        logger.info(f"Creating grove for {species_name} ({len(species_data)} trees)")
        
        # Create grove
        grove = create_grove(species_name, config.random_seed)
        
        # Add trees to grove
        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = row.get("predicted_cycles", 0)
            add_tree_to_grove(grove, position, delay=delay)
        
        forest_data.append((grove, species_name, len(species_data)))
    
    return forest_data


def _calculate_max_cycles(forest_data: ForestData) -> int:
    """Calculate maximum cycles needed for forest."""
    # Simple heuristic: use 50 cycles as default
    return 50