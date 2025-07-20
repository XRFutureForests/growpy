"""
CSV input/output operations.
"""

import logging
from pathlib import Path
import pandas as pd
from ..core.validation import validate_csv_data

logger = logging.getLogger(__name__)


def load_csv(file_path: Path) -> pd.DataFrame:
    """
    Load and validate CSV file.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Validated DataFrame
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If data is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    try:
        data = pd.read_csv(file_path)
        logger.info(f"Loaded {len(data)} rows from {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to read CSV file: {e}")
    
    # Validate the data
    validate_csv_data(data)
    
    return data


def save_csv(data: pd.DataFrame, file_path: Path) -> None:
    """
    Save DataFrame to CSV file.
    
    Args:
        data: DataFrame to save
        file_path: Path to save CSV file
    """
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        data.to_csv(file_path, index=False)
        logger.info(f"Saved {len(data)} rows to {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to save CSV file: {e}")


def load_csv_with_predictions(file_path: Path) -> pd.DataFrame:
    """
    Load CSV file that should contain prediction data.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with prediction columns
        
    Raises:
        ValueError: If required prediction columns are missing
    """
    data = load_csv(file_path)
    
    # Check for prediction columns
    required_prediction_columns = ["predicted_cycles"]
    missing_columns = [col for col in required_prediction_columns if col not in data.columns]
    
    if missing_columns:
        raise ValueError(f"Missing prediction columns: {missing_columns}")
    
    return data