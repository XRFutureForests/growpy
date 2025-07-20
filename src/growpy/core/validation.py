"""
Data validation functions.
"""

import logging
from typing import List
import pandas as pd
from ..species_utils import list_species

logger = logging.getLogger(__name__)


def validate_csv_data(data: pd.DataFrame) -> None:
    """
    Validate CSV data has required columns and valid values.
    
    Args:
        data: DataFrame to validate
        
    Raises:
        ValueError: If validation fails
    """
    # Check required columns
    required_columns = ["x", "y", "z", "species"]
    missing_columns = [col for col in required_columns if col not in data.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # Check for null values
    for col in required_columns:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains null values")
    
    # Validate species
    validate_species_names(data["species"].unique())
    
    # Validate numerical columns
    validate_coordinates(data)
    
    if "height" in data.columns:
        validate_heights(data["height"])


def validate_species_names(species_list: List[str]) -> None:
    """
    Validate that species names are available in presets.
    
    Args:
        species_list: List of species names to validate
        
    Raises:
        ValueError: If invalid species are found
    """
    available_species = set(list_species())
    invalid_species = [s for s in species_list if s not in available_species]
    
    if invalid_species:
        raise ValueError(
            f"Invalid species found: {invalid_species}. "
            f"Available species: {sorted(available_species)}"
        )


def validate_coordinates(data: pd.DataFrame) -> None:
    """
    Validate coordinate values are finite and reasonable.
    
    Args:
        data: DataFrame with x, y, z columns
        
    Raises:
        ValueError: If coordinates are invalid
    """
    for col in ["x", "y", "z"]:
        if col not in data.columns:
            continue
            
        values = data[col]
        
        # Check for infinite values
        if not pd.isfinite(values).all():
            raise ValueError(f"Column '{col}' contains infinite or NaN values")
        
        # Check for reasonable ranges (basic sanity check)
        if values.min() < -1000000 or values.max() > 1000000:
            logger.warning(f"Column '{col}' has extreme values: {values.min()} to {values.max()}")


def validate_heights(heights: pd.Series) -> None:
    """
    Validate height values are positive and reasonable.
    
    Args:
        heights: Series of height values
        
    Raises:
        ValueError: If heights are invalid
    """
    # Check for negative heights
    if (heights < 0).any():
        raise ValueError("Heights cannot be negative")
    
    # Check for zero heights
    if (heights == 0).any():
        raise ValueError("Heights cannot be zero")
    
    # Check for reasonable ranges
    if heights.max() > 200:
        logger.warning(f"Very large height found: {heights.max()}m")
    
    if heights.min() < 0.1:
        logger.warning(f"Very small height found: {heights.min()}m")


def validate_forest_data(data: pd.DataFrame) -> None:
    """
    Comprehensive validation of forest data.
    
    Args:
        data: DataFrame to validate
        
    Raises:
        ValueError: If validation fails
    """
    # Basic CSV validation
    validate_csv_data(data)
    
    # Additional forest-specific validation
    if len(data) == 0:
        raise ValueError("Forest data is empty")
    
    # Check for duplicate positions (warning only)
    duplicates = data.duplicated(subset=["x", "y", "z"]).sum()
    if duplicates > 0:
        logger.warning(f"Found {duplicates} trees with duplicate positions")
    
    # Summary statistics
    logger.info(f"Forest data validated: {len(data)} trees, {data['species'].nunique()} species")