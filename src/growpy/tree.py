"""Tree model and individual tree management functions."""

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import the_grove_22_core as gc
from sklearn.linear_model import LinearRegression

from .twig import add_twigs_to_model_usd


def calculate_growth_cycles_from_height(
    forest_data: pd.DataFrame, growth_models_dir: Optional[Path] = None
) -> None:
    """Calculate growth cycles using height prediction models or simple fallback."""

    if growth_models_dir is None:
        growth_models_dir = (
            Path(__file__).parent.parent.parent / "data" / "growth_models"
        )

    # Use growth models for species-specific predictions
    forest_data["growth_cycles"] = 0
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        height = tree["height"]

        # Get predicted cycles for this tree
        model_path = (
            growth_models_dir
            / f"{species.replace(' ', '').replace('-', '_')}"
            / "growth_model.pkl"
        )
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


def save_tree_model_with_twigs(
    model: Any,
    species_model: str,
    output_path: Path,
    tree_idx: int = 0,
    twig_density: float = 1.0,
    twig_scale: float = 1.0,
    min_radius: float = 0.001,
) -> None:
    """
    Save a single tree model to USD with twig instances and optional scaling.

    Args:
        model: Grove 3D model
        species_model: Species model name for twig lookup
        output_path: Path for output USD file
        tree_idx: Index of tree for filename generation
        twig_density: Density factor for twig placement (0.0-1.0)
        twig_scale: Scale factor for twigs
        min_radius: Minimum branch radius for twig placement

    Returns:
        True if successful, False otherwise
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model.set_up_axis("Z")  # Ensure correct orientation

    # Get base USD content for the model
    base_usd = gc.io.model_to_usda_string(model)

    # Add twig instances to the USD
    usd_with_twigs = add_twigs_to_model_usd(
        base_usd,
        model,
        species_model,
        twig_density=twig_density,
        twig_scale=twig_scale,
        min_radius=min_radius,
    )

    # Write to file
    with open(output_path, "w") as f:
        f.write(usd_with_twigs)


def save_tree_models(
    grove: gc.Grove,
    species_name: str,
    output_dir: Path,
    lod_configs: Dict[str, Dict[str, Any]],
    species_csv: Optional[pd.DataFrame] = None,
) -> List[Path]:
    """
    Export individual tree models from a grove to USD files.

    Args:
        grove: Grove containing the tree models
        species_name: Name of the species for directory organization
        output_dir: Base output directory
        lod_configs: LOD configuration dictionary
        species_csv: CSV data with height information for scaling

    Returns:
        List of exported file paths
    """
    species_dir = output_dir / species_name.replace(" ", "_")
    species_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    # Build all LOD models for this species
    lod_models = build_lod_models(grove, lod_configs)

    tree_count = len(grove.trees)

    # Export each tree with all LOD variants
    for tree_idx in range(tree_count):
        # Get the best available LOD model
        base_model = None
        for lod_name in ["LOD0_Ultra", "LOD1_High", "LOD2_Medium", "LOD3_Low"]:
            if lod_name in lod_models and tree_idx < len(lod_models[lod_name]):
                base_model = lod_models[lod_name][tree_idx]
                break

        if base_model is None:
            continue

        # Export the model
        filename = f"{species_name.replace(' ', '_')}_tree_{tree_idx:03d}.usda"
        file_path = species_dir / filename

        save_tree_model_with_twigs(
            base_model,
            f"{species_name}.seed.json",
            file_path,
            tree_idx=tree_idx,
        )
