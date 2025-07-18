"""
Height curve generation and prediction models.
"""

import pickle
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import the_grove_22_core as gc
from sklearn.linear_model import LinearRegression
from tqdm import tqdm

from ..species_utils import apply_species_preset


def calculate_tree_height(grove: gc.Grove, tree_index: int = 0) -> float:
    if not grove.trees:
        raise ValueError("Grove contains no trees")
    if tree_index < 0 or tree_index >= len(grove.trees):
        raise ValueError(
            f"Invalid tree index {tree_index}. Grove has {len(grove.trees)} trees"
        )
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        if not hasattr(branch, "nodes"):
            return
        for node in branch.nodes:
            if hasattr(node, "pos") and hasattr(node.pos, "z"):
                if node.pos.z > max_z:
                    max_z = node.pos.z
            if hasattr(node, "side_branches"):
                for side_branch in node.side_branches:
                    traverse_branch(side_branch)

    traverse_branch(grove.trees[tree_index])
    return max_z


def generate_height_curves(
    species_list: List[str], config, output_dir: Path
) -> pd.DataFrame:
    height_curves = pd.DataFrame(
        index=species_list, columns=range(config.height_model_cycles)
    )
    for species_name in tqdm(
        species_list, desc="Generating height curves", unit="species"
    ):
        grove = gc.Grove()
        grove.clear_trees()
        if config.random_seed:
            grove.set_random_seed(config.random_seed)
        apply_species_preset(grove, species_name)
        position = gc.Vector(0.0, 0.0, 0.0)
        direction = gc.Vector(0.0, 0.0, 1.0)
        delay = 0
        grove.add_new_tree(position, direction, delay)
        heights = []
        for _ in range(config.height_model_cycles):
            grove.simulate(1)
            heights.append(calculate_tree_height(grove, 0))
        height_curves.loc[species_name] = heights
    height_curves_path = output_dir / "height_curves.csv"
    height_curves.to_csv(height_curves_path)
    plt.figure(figsize=(12, 6))
    for species_name in species_list:
        plt.plot(
            height_curves.columns, height_curves.loc[species_name], label=species_name
        )
    plt.title("Tree Height Curves")
    plt.xlabel("Growth Cycle")
    plt.ylabel("Height (m)")
    plt.legend()
    plt.grid()
    plt.savefig(output_dir / "height_curves.png")
    plt.close()
    return height_curves


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
