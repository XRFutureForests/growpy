"""Data validation functions."""

from typing import List
import numpy as np
import pandas as pd
from .grove import list_species


def validate_csv_data(data: pd.DataFrame) -> None:
    """Validate CSV data has required columns and valid values."""
    required_columns = ["x", "y", "z", "species"]
    missing_columns = [col for col in required_columns if col not in data.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    for col in required_columns:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains null values")
    
    # Validate species names are available in Grove presets
    available_species = set(list_species())
    invalid_species = [s for s in data["species"].unique() if s not in available_species]
    if invalid_species:
        raise ValueError(f"Invalid species found: {invalid_species}")
    
    # Validate coordinate values are finite
    for col in ["x", "y", "z"]:
        values = data[col]
        if not np.isfinite(values).all():
            raise ValueError(f"Column '{col}' contains infinite or NaN values")
    
    # Validate height values if present
    if "height" in data.columns:
        if (data["height"] <= 0).any():
            raise ValueError("Heights must be positive")
