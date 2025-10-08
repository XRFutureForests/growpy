"""Tree model functions for forest generation."""

from typing import Any, Dict, List, Optional
import pandas as pd

try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_CORE_AVAILABLE = False

from ..config import get_config


def calculate_growth_cycles_from_height(forest_data: pd.DataFrame) -> None:
    """Calculate growth cycles and delays from tree heights using pre-computed growth models.

    For each tree in the forest data, this function:
    1. Loads the species-specific growth model
    2. Predicts required growth cycles from target height
    3. Calculates growth delay to synchronize all trees (tallest trees start first)

    Modifies the forest_data DataFrame in-place by adding two columns:
    - 'growth_cycles': Number of cycles needed to reach target height
    - 'delay': Growth delay offset for synchronized growth

    Args:
        forest_data: DataFrame with 'species' and 'height' columns

    Raises:
        FileNotFoundError: If growth model not found for a species
    """
    import pickle

    config = get_config()

    forest_data["growth_cycles"] = 0
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        height = tree["height"]

        growth_model_path = config.get_growth_model_path(species)
        model_path = growth_model_path / "growth_model.pkl"
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        growth_cycles = int(model.predict([[height]])[0])

        forest_data.at[i, "growth_cycles"] = growth_cycles

    max_cycles = forest_data["growth_cycles"].max()
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]


def get_model_attributes(model) -> Dict[str, Any]:
    """Extract all available Grove model attributes for inspection.

    Args:
        model: Grove tree model

    Returns:
        Dictionary containing all available model attributes
    """
    if gc is None:
        return {}

    attributes = {}

    # Extract geometry information
    try:
        if hasattr(model, 'points'):
            attributes['geometry'] = {
                'point_count': len(model.points),
                'face_count': len(model.faces) if hasattr(model, 'faces') else 0
            }
    except Exception:
        pass

    # Extract point attributes
    try:
        point_attributes = {}
        if hasattr(model, 'point_attributes'):
            attrs = model.point_attributes()
            for attr in attrs:
                try:
                    attr_data = getattr(model, attr)
                    if attr_data is not None:
                        point_attributes[attr] = {
                            'type': type(attr_data).__name__,
                            'length': len(attr_data) if hasattr(attr_data, '__len__') else 1
                        }
                except Exception:
                    point_attributes[attr] = {'type': 'unknown', 'length': 0}
        attributes['point_attributes'] = point_attributes
    except Exception:
        attributes['point_attributes'] = {}

    # Extract face attributes  
    try:
        face_attributes = {}
        if hasattr(model, 'face_attributes'):
            attrs = model.face_attributes()
            for attr in attrs:
                try:
                    attr_data = getattr(model, attr)
                    if attr_data is not None:
                        face_attributes[attr] = {
                            'type': type(attr_data).__name__,
                            'length': len(attr_data) if hasattr(attr_data, '__len__') else 1
                        }
                except Exception:
                    face_attributes[attr] = {'type': 'unknown', 'length': 0}
        attributes['face_attributes'] = face_attributes
    except Exception:
        attributes['face_attributes'] = {}

    return attributes


def apply_species_color_settings(
    model, species_name: str, config: Optional[Any] = None
) -> None:
    """Apply species-specific color settings to a Grove model.

    Args:
        model: Grove tree model
        species_name: Name of the tree species
        config: Optional GrowPy config for species lookup
    """
    if gc is None:
        return

    if config is None:
        config = get_config()

    # Apply species-specific colors for bark and branches
    try:
        colors = config.get_species_colors(species_name)
        if colors:
            # Apply branch color if available
            branch_color = colors.get("branch_color")
            if branch_color and hasattr(model, 'set_branch_color'):
                model.set_branch_color(*branch_color)
            
            # Apply leaf color if available
            leaf_color = colors.get("leaf_color")
            if leaf_color and hasattr(model, 'set_leaf_color'):
                model.set_leaf_color(*leaf_color)
    except Exception:
        # Fallback to default colors - natural wood brown for branches
        if hasattr(model, 'set_branch_color'):
            model.set_branch_color(0.4, 0.3, 0.2)  # Brown branches
        if hasattr(model, 'set_leaf_color'):
            model.set_leaf_color(0.2, 0.5, 0.15)  # Green leaves


def build_grove_with_all_attributes(
    grove, build_params: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """Build grove models with all available Grove attributes enabled.

    Args:
        grove: Grove instance to build
        build_params: Optional build parameters, uses comprehensive defaults if None

    Returns:
        List of fully-featured Grove models with all attributes
    """
    if not GROVE_CORE_AVAILABLE:
        raise ImportError("Grove core (the_grove_22_core) not available")

    if build_params is None:
        # Comprehensive build parameters based on Grove documentation
        build_params = {
            "resolution": 16,  # Cross-section sides (4-24, default: 16)
            "build_end_cap": True,  # Cap branch ends
            "build_cutoff_thickness": 0.0,  # Minimum thickness to build
            "build_cutoff_age": 0,  # Minimum age to build
            "build_blend": True,  # Enable blending between segments
            "resolution_reduce": 0.8,  # Resolution reduction factor (0.0-1.0)
        }

    # Build models using Grove's comprehensive build system
    models = grove.build_models(build_params)

    # Configure models for optimal export
    for model in models:
        model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
        model.set_winding_order("COUNTER_CLOCKWISE")

    return models

def build_skeletons(grove) -> Any:
    """Build skeletal armatures for all trees in the grove.

    Creates skeletal animation armatures that can be used for wind animation
    or other procedural tree movement in game engines.

    Args:
        grove: Grove instance containing trees to build skeletons for

    Returns:
        List of skeleton objects, one per tree in the grove
    """
    skeletons = grove.build_skeletons()
    return skeletons
