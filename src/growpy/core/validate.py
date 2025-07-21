"""Data validation functions."""

from typing import List
import numpy as np
import pandas as pd
from .species import list_species


def validate_csv_data(data: pd.DataFrame) -> None:
    """Validate CSV data has required columns and valid values."""
    required_columns = ["x", "y", "z", "species"]
    missing_columns = [col for col in required_columns if col not in data.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    for col in required_columns:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains null values")
    
    validate_species_names(data["species"].unique().tolist())
    validate_coordinates(data)
    
    if "height" in data.columns:
        validate_heights(data["height"])


def validate_species_names(species_list: List[str]) -> None:
    """Validate that species names are available in presets."""
    available_species = set(list_species())
    invalid_species = [s for s in species_list if s not in available_species]
    
    if invalid_species:
        raise ValueError(f"Invalid species found: {invalid_species}")


def validate_coordinates(data: pd.DataFrame) -> None:
    """Validate coordinate values are finite and reasonable."""
    for col in ["x", "y", "z"]:
        if col in data.columns:
            values = data[col]
            if not np.isfinite(values).all():
                raise ValueError(f"Column '{col}' contains infinite or NaN values")


def validate_heights(heights: pd.Series) -> None:
    """Validate height values are positive."""
    if (heights <= 0).any():
        raise ValueError("Heights must be positive")
