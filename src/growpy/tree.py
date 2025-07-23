"""Tree model and individual tree management functions."""

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import the_grove_22_core as gc
from sklearn.linear_model import LinearRegression

from .config import get_config


def calculate_growth_cycles_from_height(forest_data: pd.DataFrame) -> None:
    """Calculate growth cycles using height prediction models with global config."""
    # Get global config (creates default if none set)
    config = get_config()

    # Use growth models for species-specific predictions
    forest_data["growth_cycles"] = 0
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        height = tree["height"]
        growth_model_path = config.get_growth_model_path(species)

        model_path = growth_model_path / "growth_model.pkl"
        model = pickle.load(open(model_path, "rb"))
        growth_cycles = int(model.predict([[height]])[0])
        forest_data.at[i, "growth_cycles"] = growth_cycles

    max_cycles = forest_data["growth_cycles"].max()
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]


def save_tree_to_usd(model, output_path: Path) -> None:
    """Save 3D model to USD file using Grove's native USD output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    usd_string = gc.io.model_to_usda_string(model)
    with open(output_path, "w") as f:
        f.write(usd_string)


def build_lod_models(
    grove: gc.Grove, lod_configs: Dict[str, Dict[str, Any]]
) -> Dict[str, List]:
    """Build multiple LOD variants of grove models."""
    lod_models = {}
    for lod_name, config in lod_configs.items():
        lod_models[lod_name] = grove.build_models(config)
    return lod_models
