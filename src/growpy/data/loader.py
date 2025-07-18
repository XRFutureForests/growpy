"""
CSV data loading and validation functions.
"""

import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from ..species_utils import list_species

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when input validation fails."""
    pass


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """
    Load CSV forest data from file.
    
    Args:
        csv_path: Path to CSV file containing tree data
        
    Returns:
        DataFrame with forest data
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV cannot be parsed
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        data = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(data)} trees from {csv_path}")
        return data
    except Exception as e:
        raise ValueError(f"Failed to load CSV data: {e}")


def validate_forest_data(data: pd.DataFrame) -> None:
    """
    Validate forest data has required columns and valid values.
    
    Args:
        data: DataFrame containing forest data
        
    Raises:
        ValueError: If data is invalid
        ValidationError: If data contains invalid values
    """
    # Check required columns
    required = ["x", "y", "z", "species", "height"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Check for missing values
    for col in required:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains missing values")
            
    # Validate numerical data ranges
    _validate_numerical_data(data)

    # Validate species
    _validate_species_data(data)


def _validate_numerical_data(data: pd.DataFrame) -> None:
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


def _validate_species_data(data: pd.DataFrame) -> None:
    """
    Validate species data against available presets.
    
    Args:
        data: DataFrame containing forest data
        
    Raises:
        ValueError: If invalid species are found
    """
    unique_species = data["species"].unique()
    available_species = list_species()
    invalid_species = [s for s in unique_species if s not in available_species]
    
    if invalid_species:
        raise ValueError(
            f"Invalid species found in CSV: {invalid_species}. "
            f"Available species: {available_species}"
        )
    
    logger.info(f"Validated {len(unique_species)} species: {list(unique_species)}")