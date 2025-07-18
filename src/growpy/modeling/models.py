"""
Prediction model utilities for forest growth cycles.
"""

import pickle
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def create_cycle_prediction_models(
    height_curves: pd.DataFrame, output_dir: Path
) -> Dict[str, LinearRegression]:
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
    if species_name not in models:
        raise ValueError(f"No model available for species: {species_name}")
    if not isinstance(height, (int, float)) or not np.isfinite(height):
        raise ValueError(f"Invalid height value: {height}")
    if height <= 0:
        raise ValueError(f"Height must be positive: {height}")
    model = models[species_name]
    prediction = model.predict(np.array([[height]]))
    if len(prediction) == 0 or len(prediction[0]) == 0:
        raise ValueError("Model returned empty prediction")
    predicted_cycles = prediction[0][0]
    if not np.isfinite(predicted_cycles):
        raise ValueError(f"Model prediction is not finite: {predicted_cycles}")
    return max(1, int(predicted_cycles))


def add_predicted_cycles_to_data(
    data: pd.DataFrame, models: Dict[str, LinearRegression]
) -> pd.DataFrame:
    data_with_cycles = data.copy()
    data_with_cycles["required_cycles"] = data_with_cycles.apply(
        lambda row: predict_cycles_from_height(row["species"], row["height"], models),
        axis=1,
    )
    return data_with_cycles
