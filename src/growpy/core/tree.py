"""Tree model functions for forest generation."""

import json
import logging
import math
from typing import Any

import pandas as pd
import the_grove_23_core as gc

from ..config import get_config
from ..constants import BREAST_HEIGHT_METERS

logger = logging.getLogger(__name__)


def find_max_height_in_branch(branch) -> float:
    """Recursively find maximum height (z coordinate) in a branch hierarchy.

    Args:
        branch: Grove branch object with nodes and side_branches

    Returns:
        Maximum height found in this branch and all sub-branches
    """
    local_max = 0.0
    if hasattr(branch, "nodes") and branch.nodes:
        for node in branch.nodes:
            if hasattr(node, "pos") and node.pos.z > local_max:
                local_max = node.pos.z

            if hasattr(node, "side_branches") and node.side_branches:
                for side_branch in node.side_branches:
                    side_max = find_max_height_in_branch(side_branch)
                    if side_max > local_max:
                        local_max = side_max
    return local_max


def calculate_tree_height(tree) -> float:
    """Calculate the maximum height of a tree.

    Args:
        tree: Grove tree object

    Returns:
        Maximum height in meters
    """
    return find_max_height_in_branch(tree)


def calculate_dbh_at_height(tree, target_height: float = BREAST_HEIGHT_METERS) -> float:
    """Calculate diameter at breast height using linear interpolation.

    Finds the closest nodes below and above the target height and interpolates
    between them to get the exact diameter at the specified height.

    Args:
        tree: Grove tree object
        target_height: Height at which to measure diameter (default 1.3m for DBH)

    Returns:
        Diameter at the specified height in meters, or 0.0 if tree doesn't reach that height
    """
    if not hasattr(tree, "nodes") or not tree.nodes:
        return 0.0

    trunk_nodes = []
    for node in tree.nodes:
        if hasattr(node, "pos") and hasattr(node, "radius"):
            trunk_nodes.append({"height": node.pos.z, "radius": node.radius})

    if not trunk_nodes:
        return 0.0

    trunk_nodes.sort(key=lambda x: x["height"])
    max_height = trunk_nodes[-1]["height"]

    if max_height < target_height:
        return 0.0

    node_below = None
    node_above = None

    for trunk_node in trunk_nodes:
        if trunk_node["height"] <= target_height:
            node_below = trunk_node
        elif trunk_node["height"] > target_height and node_above is None:
            node_above = trunk_node
            break

    if node_below and node_below["height"] == target_height:
        return node_below["radius"] * 2.0

    if node_below is None:
        if trunk_nodes[0]["height"] >= target_height * 0.95:
            return trunk_nodes[0]["radius"] * 2.0
        else:
            return 0.0

    if node_above is None:
        return node_below["radius"] * 2.0

    height_ratio = (target_height - node_below["height"]) / (
        node_above["height"] - node_below["height"]
    )
    interpolated_radius = node_below["radius"] + height_ratio * (
        node_above["radius"] - node_below["radius"]
    )

    return interpolated_radius * 2.0


def extract_tree_measurements(grove: gc.Grove) -> list[tuple[float, float]]:
    """Extract height and DBH measurements for all trees in a grove.

    Args:
        grove: Grove instance with simulated trees

    Returns:
        List of (height, dbh) tuples for each tree in the grove
    """
    measurements = []
    if grove.trees:
        for tree in grove.trees:
            height = calculate_tree_height(tree)
            dbh = calculate_dbh_at_height(tree, target_height=BREAST_HEIGHT_METERS)
            measurements.append((height, dbh))
    return measurements


def extract_grove_attributes(grove: gc.Grove) -> dict[str, Any]:
    """Extract grove-level summary attributes after simulation.

    Wraps the grove attribute access pattern from direct Grove API usage,
    providing safe defaults when attributes are unavailable.

    Args:
        grove: Simulated Grove instance

    Returns:
        Dict with keys: total_mass, total_volume, total_surface_area,
        number_of_branches, height, age, has_roots. total_volume (m^3) and
        total_surface_area (m^2) are Grove-computed biophysical quantities
        useful for biomass / yield validation.
    """
    return {
        "total_mass": getattr(grove, "total_mass", None),
        "total_volume": getattr(grove, "total_volume", None),
        "total_surface_area": getattr(grove, "total_surface_area", None),
        "number_of_branches": getattr(grove, "number_of_branches", None),
        "height": getattr(grove, "height", None),
        "age": getattr(grove, "age", None),
        "has_roots": getattr(grove, "roots", None) is not None,
    }


def _load_growth_model(model_dir):
    """Load growth model from JSON (preferred) or pickle fallback.

    JSON avoids joblib/sklearn ABI issues across environments.
    """
    from ..utils.analysis import ChapmanRichardsModel, PiecewiseLinearModel

    json_path = model_dir / "growth_model_params.json"
    if json_path.exists():
        with open(json_path) as f:
            d = json.load(f)
        model_type = d.get("model_type", "")
        if model_type == "chapman_richards":
            return ChapmanRichardsModel.from_dict(d)
        if model_type == "piecewise_linear":
            return PiecewiseLinearModel.from_dict(d)
        logger.warning("Unknown model_type '%s' in %s, falling back to pkl", model_type, json_path)

    pkl_path = model_dir / "growth_model.pkl"
    if pkl_path.exists():
        import joblib
        return joblib.load(pkl_path)

    raise FileNotFoundError(f"No growth model found in {model_dir}")


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

    model_cache: dict[str, Any] = {}
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        if species not in model_cache:
            growth_model_path = config.get_growth_model_path(species)
            model_cache[species] = _load_growth_model(growth_model_path)

        model = model_cache[species]
        target_height = tree["height"]
        predicted = float(model.predict([[target_height]])[0])
        forest_data.at[i, "growth_cycles"] = max(1, math.ceil(predicted))

    max_cycles = forest_data["growth_cycles"].max()
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]
