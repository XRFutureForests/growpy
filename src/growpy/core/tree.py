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
    """Find the maximum height (z coordinate) in a branch hierarchy.

    Iterative rather than recursive, and every Grove attribute is read exactly
    once per object. Both matter: ``branch.nodes``, ``node.pos`` and
    ``node.side_branches`` are compiled properties on the Grove ``.pyd`` whose
    cost is O(subtree), so the original ``hasattr(x, "a") and x.a`` ... ``x.a``
    idiom paid for the same rebuild three times per object. Measured on a 21 m
    European beech (50 cycles, 88,686 branches) the original cost 4,438 ms per
    call -- and the milestone loop calls it once per cycle per grove.

    Args:
        branch: Grove branch object with nodes and side_branches

    Returns:
        Maximum height found in this branch and all sub-branches
    """
    local_max = 0.0
    stack = [branch]
    while stack:
        current = stack.pop()
        nodes = getattr(current, "nodes", None)
        if not nodes:
            continue
        for node in nodes:
            pos = getattr(node, "pos", None)
            if pos is not None and pos.z > local_max:
                local_max = pos.z
            side_branches = getattr(node, "side_branches", None)
            if side_branches:
                stack.extend(side_branches)
    return local_max


def calculate_tree_height(tree) -> float:
    """Calculate the maximum height of a tree.

    Walks the branch hierarchy. When the caller holds the grove and that grove
    has exactly one tree, prefer :func:`extract_tree_heights`, which reads
    Grove's own ``grove.height`` instead -- same value, ~6 orders of magnitude
    cheaper.

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
    # One read each: tree.nodes is a compiled Grove property whose cost is
    # O(subtree), so the old hasattr()/truthiness/iterate idiom rebuilt it three
    # times (measured 560 ms on a 21 m beech, for ~160 trunk nodes).
    nodes = getattr(tree, "nodes", None)
    if not nodes:
        return 0.0

    trunk_nodes = []
    for node in nodes:
        pos = getattr(node, "pos", None)
        radius = getattr(node, "radius", None)
        if pos is not None and radius is not None:
            trunk_nodes.append((pos.z, radius))

    if not trunk_nodes:
        return 0.0

    trunk_nodes.sort()
    max_height = trunk_nodes[-1][0]

    if max_height < target_height:
        return 0.0

    node_below = None
    node_above = None

    for trunk_node in trunk_nodes:
        if trunk_node[0] <= target_height:
            node_below = trunk_node
        elif trunk_node[0] > target_height and node_above is None:
            node_above = trunk_node
            break

    if node_below and node_below[0] == target_height:
        return node_below[1] * 2.0

    if node_below is None:
        if trunk_nodes[0][0] >= target_height * 0.95:
            return trunk_nodes[0][1] * 2.0
        else:
            return 0.0

    if node_above is None:
        return node_below[1] * 2.0

    height_ratio = (target_height - node_below[0]) / (node_above[0] - node_below[0])
    interpolated_radius = node_below[1] + height_ratio * (node_above[1] - node_below[1])

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


def extract_tree_heights(grove: gc.Grove, tree_count: int | None = None) -> list[float]:
    """Extract just the heights of every tree in a grove.

    The height-milestone simulation loop needs heights every cycle and never
    uses DBH, so this exists to avoid paying for one. Three savings over
    :func:`extract_tree_measurements`, measured on a 21 m European beech
    (50 cycles, 88,686 branches):

    * ``grove.height`` is a native Grove attribute returning the same value as
      walking the branch hierarchy (verified equal at 30 and 50 cycles) for
      ~0.002 ms instead of ~4,438 ms. It is grove-level, so it can only stand
      in for a per-tree walk when the grove holds a single tree -- which is
      exactly the dataset case, where each (species, surround_radius) pair gets
      its own one-tree grove.
    * DBH is skipped entirely (a further ~560 ms per call).
    * ``grove.trees`` is itself an O(subtree) compiled property costing ~338 ms
      per read, so pass *tree_count* when the caller already knows it (the
      simulation loop does, from its ``GroveEntry``) and the grove is never
      touched at all on the single-tree path.

    Args:
        grove: Grove instance with simulated trees
        tree_count: Number of trees in the grove when already known. Avoids
            reading ``grove.trees``. None = read it.

    Returns:
        List of heights in meters, one per tree, in ``grove.trees`` order
    """
    if tree_count == 1:
        native = getattr(grove, "height", None)
        if native is not None:
            return [float(native)]

    trees = grove.trees
    if not trees:
        return []
    if len(trees) == 1:
        native = getattr(grove, "height", None)
        if native is not None:
            return [float(native)]
    return [calculate_tree_height(tree) for tree in trees]


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
