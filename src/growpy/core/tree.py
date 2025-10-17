"""Tree model functions for forest generation."""

from typing import Any, Dict, List, Optional
import pickle
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


def get_model_attributes(model: Any) -> Dict[str, Any]:
    """Extract all available Grove model attributes for inspection.

    Args:
        model: Grove tree model

    Returns:
        Dictionary containing model attributes
    """
    attributes = {}

    if hasattr(model, 'points'):
        attributes['geometry'] = {
            'point_count': len(model.points),
            'face_count': len(model.faces) if hasattr(model, 'faces') else 0
        }

    if hasattr(model, 'point_attributes'):
        point_attributes = {}
        for attr in model.point_attributes():
            attr_data = getattr(model, attr, None)
            if attr_data is not None:
                point_attributes[attr] = {
                    'type': type(attr_data).__name__,
                    'length': len(attr_data) if hasattr(attr_data, '__len__') else 1
                }
        attributes['point_attributes'] = point_attributes

    if hasattr(model, 'face_attributes'):
        face_attributes = {}
        for attr in model.face_attributes():
            attr_data = getattr(model, attr, None)
            if attr_data is not None:
                face_attributes[attr] = {
                    'type': type(attr_data).__name__,
                    'length': len(attr_data) if hasattr(attr_data, '__len__') else 1
                }
        attributes['face_attributes'] = face_attributes

    return attributes


def apply_species_color_settings(
    model: Any, species_name: str, config: Optional[Any] = None
) -> None:
    """Apply species-specific color settings to a Grove model.

    Args:
        model: Grove tree model
        species_name: Name of the tree species
        config: Optional GrowPy config
    """
    if config is None:
        config = get_config()

    colors = config.get_species_colors(species_name)
    if colors:
        branch_color = colors.get("branch_color")
        if branch_color and hasattr(model, 'set_branch_color'):
            model.set_branch_color(*branch_color)

        leaf_color = colors.get("leaf_color")
        if leaf_color and hasattr(model, 'set_leaf_color'):
            model.set_leaf_color(*leaf_color)


def build_grove_with_all_attributes(
    grove: gc.Grove, build_params: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """Build grove models with all available Grove attributes enabled.

    Args:
        grove: Grove instance to build
        build_params: Optional build parameters

    Returns:
        List of Grove models with all attributes
    """
    if build_params is None:
        build_params = {
            "resolution": 16,
            "build_end_cap": True,
            "build_cutoff_thickness": 0.0,
            "build_cutoff_age": 0,
            "build_blend": True,
            "resolution_reduce": 0.8,
        }

    models = grove.build_models(build_params)

    for model in models:
        model.set_up_axis("Z")
        model.set_winding_order("COUNTER_CLOCKWISE")

    return models


def build_skeletons(grove: gc.Grove) -> List[Any]:
    """Build skeletal armatures for all trees in the grove.

    Args:
        grove: Grove instance containing trees

    Returns:
        List of skeleton objects
    """
    return grove.build_skeletons()
