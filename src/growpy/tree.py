"""Tree model functions for forest generation with color support."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import gc, ensure_grove_available, pd
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


def save_tree_to_usd(
    model,
    output_path: Path,
) -> None:
    """Save tree model to USD file with proper color setup.

    Args:
        model: Grove tree model to export
        output_path: Path for the USD file
    """
    ensure_grove_available()

    # Configure model for optimal USD export
    model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
    model.set_winding_order("COUNTER_CLOCKWISE")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    usd_string = gc.io.model_to_usda_string(model)

    with open(output_path, "w") as f:
        f.write(usd_string)


def can_species_have_twigs(species_name: str, config) -> bool:
    """Check if a species has twig assets available.

    Args:
        species_name: Name of the tree species
        config: GrowPyConfig instance for twig lookup

    Returns:
        bool: True if twigs are available for this species, False otherwise
    """
    try:
        twig_name = config.get_twig_for_species(species_name)
        if twig_name:
            twig_files_by_type = config.get_twig_files_by_type(species_name)
            return bool(twig_files_by_type)
    except Exception:
        pass
    return False


def save_tree_to_usd_with_twigs(
    model,
    output_path: Path,
    species_name: str,
    config,
    base_dir: Path,
    twigs_dir: Path,
) -> Path:
    """Save tree model to USD file, placing in correct directory based on twig capability.

    This function saves base models directly to base/ and enhanced models with 
    twigs directly to twigs/, eliminating the need for intermediate file moves.

    Args:
        model: Grove tree model to export
        output_path: Base path for the USD file (filename will be preserved)
        species_name: Name of the tree species for twig lookup
        config: GrowPyConfig instance for twig assets
        base_dir: Directory for models without twigs (base models)
        twigs_dir: Directory for models with twigs (enhanced models)

    Returns:
        Path: Actual path where the file was saved (either in twigs/ or base/)
    """
    ensure_grove_available()

    # Configure model for optimal USD export
    model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
    model.set_winding_order("COUNTER_CLOCKWISE")

    filename = output_path.name
    
    # Always save base model to base directory
    base_path = base_dir / filename
    base_path.parent.mkdir(parents=True, exist_ok=True)
    
    usd_string = gc.io.model_to_usda_string(model)
    with open(base_path, "w") as f:
        f.write(usd_string)
    
    # Try to create enhanced version with twigs if species supports them
    try:
        from .twig import add_twigs_to_tree
        
        if can_species_have_twigs(species_name, config):
            # Create enhanced version directly in twigs directory from base file
            enhanced_filename = filename.replace(".usda", "_with_twigs.usda")
            enhanced_path = twigs_dir / enhanced_filename
            enhanced_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Try to add twigs using the base file as input, saving directly to twigs
            if add_twigs_to_tree(base_path, species_name, config, enhanced_path):
                return enhanced_path
            
    except ImportError:
        pass
    except Exception:
        pass
    
    # Return base model path (base model always exists in base/)
    return base_path


def build_lod_models(
    grove, lod_configs: Dict[str, Dict[str, Any]]
) -> Dict[str, List]:
    """Build multiple LOD variants of grove models with proper Grove API parameters.

    Args:
        grove: Grove instance to build models from
        lod_configs: Configuration for each LOD level

    Returns:
        Dictionary mapping LOD names to lists of models
    """
    ensure_grove_available()

    lod_models = {}
    for lod_name, config in lod_configs.items():
        # Build comprehensive Grove model parameters based on documentation
        build_options = {
            "resolution": config.get("resolution", 16),  # Cross-section sides (4-24)
            "build_end_cap": config.get("build_end_cap", True),  # Cap branch ends
            "build_cutoff_thickness": config.get("build_cutoff_thickness", 0.0),
            "build_cutoff_age": config.get("build_cutoff_age", 0),
            "build_blend": config.get("build_blend", True),
            "resolution_reduce": config.get("resolution_reduce", 0.8),
        }

        # Build models with comprehensive parameters
        models = grove.build_models(build_options)

        # Configure each model for proper export
        for model in models:
            model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
            model.set_winding_order("COUNTER_CLOCKWISE")

        lod_models[lod_name] = models

    return lod_models


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
        species_data = config.get_species_data(species_name)
        if species_data:
            # Apply bark color if specified
            if "bark_color" in species_data:
                bark_color = species_data["bark_color"]
                if hasattr(model, 'set_bark_color'):
                    model.set_bark_color(*bark_color)
            
            # Apply branch color if specified  
            if "branch_color" in species_data:
                branch_color = species_data["branch_color"]
                if hasattr(model, 'set_branch_color'):
                    model.set_branch_color(*branch_color)
                    
            # Apply leaf color if specified
            if "leaf_color" in species_data:
                leaf_color = species_data["leaf_color"]
                if hasattr(model, 'set_leaf_color'):
                    model.set_leaf_color(*leaf_color)
    except Exception:
        # Fallback to default colors - natural wood brown for bark
        if hasattr(model, 'set_bark_color'):
            model.set_bark_color(0.4, 0.3, 0.2)  # Brown bark
        if hasattr(model, 'set_branch_color'):
            model.set_branch_color(0.3, 0.2, 0.1)  # Darker brown branches


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
    ensure_grove_available()

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