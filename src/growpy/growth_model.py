"""Age prediction functionality for forest simulation."""

import json
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def calculate_growth_cycles_from_height(
    forest_data: pd.DataFrame, growth_models_dir: Optional[Path] = None
) -> None:
    """Calculate growth cycles using height prediction models or simple fallback."""

    if growth_models_dir is None:
        growth_models_dir = Path(__file__).parent / "growth_models"

    # Use growth models for species-specific predictions
    species_cycles = {}
    max_cycles = 0
    forest_data["growth_cycles"] = 0
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        height = tree["height"]

        # Get predicted cycles for this tree
        model_path = (
            growth_models_dir
            / f"{species.replace(' ', '_').replace('_-_', '_')}_model.pkl"
        )
        model = pickle.load(open(model_path, "rb"))
        growth_cycles = model.predict([[height]])[0]
        forest_data.at[i, "growth_cycles"] = growth_cycles
