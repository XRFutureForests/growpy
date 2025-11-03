"""Tree model functions for forest generation."""

import pickle
from typing import Any, Dict, List, Optional

import pandas as pd
import the_grove_22_core as gc

from ..config import get_config


def calculate_growth_cycles_from_height(forest_data: pd.DataFrame) -> None:
    """Calculate growth cycles and delays from tree heights using pre-computed growth models.

    Modifies the forest_data DataFrame in-place by adding:
    - 'growth_cycles': Number of cycles needed to reach target height
    - 'delay': Growth delay offset for synchronized growth

    Args:
        forest_data: DataFrame with 'species' and 'height' columns
    """
    config = get_config()
    forest_data["growth_cycles"] = 0

    for i, tree in forest_data.iterrows():
        growth_model_path = config.get_growth_model_path(tree["species"])
        model_path = growth_model_path / "growth_model.pkl"
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        forest_data.at[i, "growth_cycles"] = int(model.predict([[tree["height"]]])[0])

    max_cycles = forest_data["growth_cycles"].max()
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]
