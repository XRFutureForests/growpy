"""Minimal tree model functions."""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available")
    gc = None

from .config import get_config


def calculate_growth_cycles_from_height(forest_data: pd.DataFrame) -> None:
    """Calculate growth cycles using pre-computed growth models."""
    import pickle

    config = get_config()

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
    """Save tree model to USD file."""
    if gc is None:
        raise ImportError("Grove core not available")
    model.set_up_axis("Z")  # Ensure Z-up for USD compatibility
    model.set_winding_order("CLOCKWISE")
    model.triangulate()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    usd_string = gc.io.model_to_usda_string(model)

    with open(output_path, "w") as f:
        f.write(usd_string)


def build_lod_models(grove, lod_configs: Dict[str, Dict[str, Any]]) -> Dict[str, List]:
    """Build multiple LOD variants of grove models."""
    if gc is None:
        raise ImportError("Grove core not available")

    lod_models = {}
    for lod_name, config in lod_configs.items():
        # Build models with LOD-specific options
        build_options = {}
        if "resolution" in config:
            build_options["resolution"] = config["resolution"]
        if "build_cutoff_thickness" in config:
            build_options["build_cutoff_thickness"] = config["build_cutoff_thickness"]

        models = grove.build_models(build_options)
        lod_models[lod_name] = models

    return lod_models
