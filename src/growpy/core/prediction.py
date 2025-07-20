"""
Age prediction and modeling functions.
"""

import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


def create_prediction_model(height_curve: List[float]) -> LinearRegression:
    """
    Create a linear regression model to predict cycles from height.
    
    Args:
        height_curve: List of heights for each cycle
        
    Returns:
        Trained LinearRegression model
    """
    if len(height_curve) < 2:
        raise ValueError("Height curve must have at least 2 points")
    
    # Prepare data for linear regression
    cycles = np.array(range(len(height_curve))).reshape(-1, 1)
    heights = np.array(height_curve)
    
    # Create and train model
    model = LinearRegression()
    model.fit(heights.reshape(-1, 1), cycles.ravel())
    
    return model


def predict_cycles_from_height(model: LinearRegression, target_height: float) -> int:
    """
    Predict required cycles to reach target height.
    
    Args:
        model: Trained LinearRegression model
        target_height: Target height to reach
        
    Returns:
        Predicted number of cycles (minimum 1)
    """
    prediction = model.predict([[target_height]])[0]
    return max(1, int(round(prediction)))


def create_species_prediction_models(height_curves: Dict[str, List[float]]) -> Dict[str, LinearRegression]:
    """
    Create prediction models for multiple species.
    
    Args:
        height_curves: Dictionary mapping species to height curves
        
    Returns:
        Dictionary mapping species to trained models
    """
    models = {}
    
    for species, curve in height_curves.items():
        try:
            models[species] = create_prediction_model(curve)
            logger.debug(f"Created prediction model for {species}")
        except ValueError as e:
            logger.warning(f"Failed to create model for {species}: {e}")
            # Create a simple fallback model
            models[species] = _create_fallback_model()
    
    return models


def predict_cycles_for_data(data: pd.DataFrame, models: Dict[str, LinearRegression]) -> pd.DataFrame:
    """
    Add cycle predictions to forest data.
    
    Args:
        data: DataFrame with 'species' and 'height' columns
        models: Dictionary of trained prediction models
        
    Returns:
        DataFrame with added 'predicted_cycles' column
    """
    result = data.copy()
    predicted_cycles = []
    
    for _, row in result.iterrows():
        species = row['species']
        height = row['height']
        
        if species in models:
            cycles = predict_cycles_from_height(models[species], height)
        else:
            logger.warning(f"No model found for species {species}, using default")
            cycles = max(1, int(height * 5))  # Simple fallback
        
        predicted_cycles.append(cycles)
    
    result['predicted_cycles'] = predicted_cycles
    return result


def _create_fallback_model() -> LinearRegression:
    """Create a simple fallback model for species without proper height curves."""
    # Simple linear model: height = 0.2 * cycles
    model = LinearRegression()
    heights = np.array([0.2, 0.4, 0.6, 0.8, 1.0]).reshape(-1, 1)
    cycles = np.array([1, 2, 3, 4, 5])
    model.fit(heights, cycles)
    return model