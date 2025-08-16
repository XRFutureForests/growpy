"""Tree model functions with skeleton generation support."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    include_skeleton: bool = True,
    texture_aspect_ratio: float = 1.0,
) -> None:
    """Save tree model to USD file with optional skeleton and proper material setup.

    Args:
        model: Grove tree model to export
        output_path: Path for the USD file
        include_skeleton: Whether to include skeleton data in the USD export
        texture_aspect_ratio: Aspect ratio for bark texture UV correction
    """
    ensure_grove_available()

    # Configure model for optimal USD export
    model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
    model.set_winding_order("COUNTER_CLOCKWISE")

    # Apply UV aspect ratio correction for bark textures
    if texture_aspect_ratio != 1.0:
        model.apply_uv_aspect_ratio(texture_aspect_ratio)

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
    include_skeleton: bool = True,
    texture_aspect_ratio: float = 1.0,
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
        include_skeleton: Whether to include skeleton data in the USD export
        texture_aspect_ratio: Aspect ratio for bark texture UV correction

    Returns:
        Path: Actual path where the file was saved (either in twigs/ or base/)
    """
    ensure_grove_available()

    # Configure model for optimal USD export
    model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
    model.set_winding_order("COUNTER_CLOCKWISE")

    # Apply UV aspect ratio correction for bark textures
    if texture_aspect_ratio != 1.0:
        model.apply_uv_aspect_ratio(texture_aspect_ratio)

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
            if add_twigs_to_tree(base_path, species_name, config, output_path=enhanced_path):
                # Successfully created enhanced version
                return enhanced_path
    except Exception:
        # If twig addition fails, that's okay - we still have the base model
        pass
    
    # Return base model path (base model always exists in base/)
    return base_path


def build_lod_models(
    grove, lod_configs: Dict[str, Dict[str, Any]], texture_aspect_ratio: float = 1.0
) -> Dict[str, List]:
    """Build multiple LOD variants of grove models with proper Grove API parameters.

    Args:
        grove: Grove instance to build models from
        lod_configs: Configuration for each LOD level
        texture_aspect_ratio: Aspect ratio for bark texture UV correction

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
            "texture_repeat": config.get("texture_repeat", 1.0),
            "resolution_reduce": config.get("resolution_reduce", 0.8),
        }

        # Build models with comprehensive parameters
        models = grove.build_models(build_options)

        # Configure each model for proper export
        for model in models:
            model.set_up_axis("Z")  # Z-up for Blender/Unreal compatibility
            model.set_winding_order("COUNTER_CLOCKWISE")

            # Apply UV aspect ratio correction for bark textures
            if texture_aspect_ratio != 1.0:
                model.apply_uv_aspect_ratio(texture_aspect_ratio)

        lod_models[lod_name] = models

    return lod_models


def build_tree_skeletons(grove, optimize_bones: bool = True) -> List[Any]:
    """Build skeletons for all trees in the grove.

    Args:
        grove: Grove instance containing simulated trees
        optimize_bones: Whether to optimize bone hierarchy for animation

    Returns:
        List of skeleton objects with points, poly_lines, and attributes
    """
    ensure_grove_available()

    if optimize_bones:
        # Use basic skeleton generation for now
        # TODO: Advanced bone optimization may require newer Grove core version
        skeletons = grove.build_skeletons()
        # Note: Advanced parameters like length_factor, reduce_threshold, bias_factor
        # would need to be implemented as post-processing of basic skeletons
    else:
        # Use basic skeleton generation
        skeletons = grove.build_skeletons()

    return skeletons


def add_bone_ids_to_model(model, skeleton) -> None:
    """Add bone ID primvars to model for proper skeleton binding.
    
    This creates the gr_bone_id primvar that matches the Blender export format,
    allowing proper skeleton/mesh binding for animation.
    
    Args:
        model: Grove tree model to add bone IDs to
        skeleton: Associated Grove skeleton object
    """
    if gc is None or not hasattr(model, 'faces'):
        return
        
    try:
        # Get skeleton branch IDs if available
        if hasattr(skeleton, 'face_attribute_branch_id'):
            branch_ids = skeleton.face_attribute_branch_id
        elif hasattr(model, 'face_attribute_branch_id'):
            branch_ids = model.face_attribute_branch_id
        else:
            # Generate default bone IDs based on face index patterns
            branch_ids = []
            for i in range(len(model.faces)):
                # Simple branch ID assignment - root=0, main branches=1-7, twigs=8+
                if i < len(model.faces) * 0.1:  # First 10% = root
                    branch_ids.append(0)
                elif i < len(model.faces) * 0.8:  # Next 70% = main branches
                    branch_ids.append((i // (len(model.faces) // 7)) + 1)
                else:  # Last 20% = small branches/twigs
                    branch_ids.append(min(12, (i // (len(model.faces) // 20)) + 8))
        
        # Ensure we have the right number of bone IDs
        if len(branch_ids) < len(model.faces):
            # Pad with last available ID
            last_id = branch_ids[-1] if branch_ids else 0
            branch_ids.extend([last_id] * (len(model.faces) - len(branch_ids)))
        elif len(branch_ids) > len(model.faces):
            # Truncate to match face count
            branch_ids = branch_ids[:len(model.faces)]
        
        # Add as face attribute for USD export (similar to gr_bone_id in Blender export)
        model.face_attribute_bone_id = branch_ids
        
    except Exception as e:
        print(f"Warning: Could not add bone IDs to model: {e}")


def get_skeleton_info(skeleton) -> Dict[str, Any]:
    """Extract detailed information from a skeleton object.

    Args:
        skeleton: Grove skeleton object

    Returns:
        Dictionary containing skeleton data and attributes
    """
    info = {
        "joint_count": len(skeleton.points),
        "bone_count": len(skeleton.poly_lines),
        "location": skeleton.location,
        "points": skeleton.points,
        "poly_lines": skeleton.poly_lines,
    }

    # Add attribute data if available
    if hasattr(skeleton, "point_attribute_age"):
        info["joint_ages"] = skeleton.point_attribute_age
    if hasattr(skeleton, "point_attribute_mass"):
        info["joint_masses"] = skeleton.point_attribute_mass
    if hasattr(skeleton, "point_attribute_radius"):
        info["joint_radii"] = skeleton.point_attribute_radius
    if hasattr(skeleton, "face_attribute_branch_id"):
        info["branch_ids"] = skeleton.face_attribute_branch_id

    return info


def save_tree_with_skeleton(
    model, skeleton, output_path: Path, texture_aspect_ratio: float = 1.0
) -> None:
    """Save tree model with skeleton to USD file.

    This creates a USD file with both the tree mesh and skeleton data,
    properly configured for animation in Blender and Unreal Engine.

    Args:
        model: Grove tree model
        skeleton: Grove skeleton object
        output_path: Path for the USD file
        texture_aspect_ratio: Aspect ratio for bark texture UV correction
    """
    ensure_grove_available()

    # Configure model for USD export with proper material setup
    model.set_up_axis("Z")
    model.set_winding_order("COUNTER_CLOCKWISE")

    # Apply UV aspect ratio correction for bark textures
    if texture_aspect_ratio != 1.0:
        model.apply_uv_aspect_ratio(texture_aspect_ratio)

    # The model_to_usda_string function automatically includes skeleton data
    # when the model has been built from a grove with skeletons
    output_path.parent.mkdir(parents=True, exist_ok=True)
    usd_string = gc.io.model_to_usda_string(model)

    with open(output_path, "w") as f:
        f.write(usd_string)


def create_skeleton_lod_models(
    grove,
    lod_configs: Dict[str, Dict[str, Any]],
    skeleton_options: Optional[Dict[str, Any]] = None,
    texture_aspect_ratio: float = 1.0,
) -> Tuple[Dict[str, List], List[Any]]:
    """Build LOD models with associated skeletons using proper Grove API.

    Args:
        grove: Grove instance
        lod_configs: LOD configuration dictionary
        skeleton_options: Optional skeleton generation parameters
        texture_aspect_ratio: Aspect ratio for bark texture UV correction

    Returns:
        Tuple of (lod_models_dict, skeletons_list)
    """
    ensure_grove_available()

    # Set default skeleton options
    if skeleton_options is None:
        skeleton_options = {
            "length_factor": 2.0,
            "reduce_threshold": 0.4,
            "bias_factor": 0.3,
            "connected": True,
        }

    # Build skeletons first - using basic method for compatibility
    skeletons = grove.build_skeletons()
    # TODO: Advanced skeleton optimization would need newer Grove core version

    # Build LOD models with comprehensive parameters
    lod_models = {}
    for lod_name, config in lod_configs.items():
        build_options = {
            "resolution": config.get("resolution", 16),
            "build_end_cap": config.get("build_end_cap", True),
            "build_cutoff_thickness": config.get("build_cutoff_thickness", 0.0),
            "build_cutoff_age": config.get("build_cutoff_age", 0),
            "build_blend": config.get("build_blend", True),
            "texture_repeat": config.get("texture_repeat", 1.0),
            "resolution_reduce": config.get("resolution_reduce", 0.8),
        }

        # Configure models for skeleton compatibility and proper materials
        models = grove.build_models(build_options)
        for model in models:
            model.set_up_axis("Z")
            model.set_winding_order("COUNTER_CLOCKWISE")

            # Apply UV aspect ratio correction for bark textures
            if texture_aspect_ratio != 1.0:
                model.apply_uv_aspect_ratio(texture_aspect_ratio)

        lod_models[lod_name] = models

    return lod_models, skeletons


def export_forest_with_skeletons(
    forest,
    output_dir: Path,
    lod_configs: Dict[str, Dict[str, Any]],
    skeleton_options: Optional[Dict[str, Any]] = None,
    texture_aspect_ratio: float = 1.0,
) -> Dict[str, int]:
    """Export entire forest with skeletons for all trees using proper Grove API.

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        output_dir: Output directory for USD files
        lod_configs: LOD configuration dictionary
        skeleton_options: Optional skeleton generation parameters
        texture_aspect_ratio: Aspect ratio for bark texture UV correction

    Returns:
        Dictionary with export statistics
    """
    ensure_grove_available()

    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {"total_exported": 0, "skeletons_created": 0, "species_processed": 0}

    for grove, species_name, tree_count in forest:
        # Build models and skeletons with proper parameters
        lod_models, skeletons = create_skeleton_lod_models(
            grove, lod_configs, skeleton_options, texture_aspect_ratio
        )

        stats["skeletons_created"] += len(skeletons)
        stats["species_processed"] += 1

        species_clean = species_name.replace(" ", "").replace("-", "_")

        # Export each LOD level with comprehensive USD data
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}_with_skeleton.usda"
                filepath = output_dir / filename

                # Export model with skeleton and all Grove attributes
                usd_string = gc.io.model_to_usda_string(model)
                with open(filepath, "w") as f:
                    f.write(usd_string)

                stats["total_exported"] += 1

    return stats


def generate_wind_animation(
    grove,
    wind_vector: Tuple[float, float, float],
    frame_count: int = 50,
    turbulence: float = 1.0,
) -> List[Any]:
    """Generate wind animation shapes for skeletal animation using Grove API.

    Args:
        grove: Grove instance with simulated trees
        wind_vector: Wind direction as (x, y, z) tuple
        frame_count: Number of animation frames to generate
        turbulence: Wind strength/turbulence factor

    Returns:
        List of wind shape models for animation
    """
    ensure_grove_available()

    # Convert wind vector to Grove Vector object
    wind_vec = gc.Vector(wind_vector[0], wind_vector[1], wind_vector[2])

    # Build comprehensive wind animation parameters based on Grove documentation
    wind_build_params = {
        "resolution": 32,
        "resolution_reduce": 0.8,
        "texture_repeat": 1.0,
        "build_cutoff_age": 0,
        "build_blend": True,
        "build_end_cap": True,
    }

    # Generate wind animation shapes using proper Grove API
    try:
        wind_shapes = grove.build_wind_shape(
            wind_build_params,
            frame_count,  # shape_count
            0,  # current_shape
            wind_vec,  # wind_vector
            turbulence,  # turbulence
        )
    except AttributeError:
        # Fallback to basic wind shape generation if advanced method not available
        print(
            "Warning: Advanced wind shape generation not available, using basic method"
        )
        wind_shapes = grove.build_models(wind_build_params)

    # Configure wind shapes for proper export
    for shape in wind_shapes:
        if hasattr(shape, "set_up_axis"):
            shape.set_up_axis("Z")
            shape.set_winding_order("COUNTER_CLOCKWISE")

    return wind_shapes


def get_model_attributes(model) -> Dict[str, Any]:
    """Extract all available Grove model attributes for inspection.

    Args:
        model: Grove tree model

    Returns:
        Dictionary containing all available model attributes
    """
    if gc is None:
        return {}

    attributes = {
        "geometry": {
            "point_count": len(model.points) if hasattr(model, "points") else 0,
            "face_count": len(model.faces) if hasattr(model, "faces") else 0,
            "location": (
                (model.location.x, model.location.y, model.location.z)
                if hasattr(model, "location")
                else (0, 0, 0)
            ),
        },
        "point_attributes": {},
        "face_attributes": {},
    }

    # Collect point attributes (vertex-based data)
    point_attrs = [
        "point_attribute_age",
        "point_attribute_thickness",
        "point_attribute_pitch",
        "point_attribute_photosynthesis",
        "point_attribute_shade",
        "point_attribute_vigor",
        "point_attribute_bone_id",
        "point_attribute_mass",
        "point_attribute_radius",
    ]

    for attr_name in point_attrs:
        if hasattr(model, attr_name):
            attributes["point_attributes"][attr_name] = getattr(model, attr_name)

    # Collect face attributes (polygon-based data)
    face_attrs = [
        "face_attribute_branch_id",
        "face_attribute_branch_id_parent",
        "face_attribute_dead",
        "face_attribute_twig_long",
        "face_attribute_twig_short",
        "face_attribute_twig_upward",
        "face_attribute_twig_dead",
        "face_attribute_end",
        "face_attribute_tree_index",
    ]

    for attr_name in face_attrs:
        if hasattr(model, attr_name):
            attributes["face_attributes"][attr_name] = getattr(model, attr_name)

    return attributes


def apply_species_texture_settings(
    model, species_name: str, config: Optional[Any] = None
) -> None:
    """Apply species-specific texture and material settings to a Grove model.

    Args:
        model: Grove tree model
        species_name: Name of the tree species
        config: Optional GrowPy config for species lookup
    """
    if gc is None:
        return

    if config is None:
        config = get_config()

    # Get species-specific texture aspect ratio
    try:
        species_data = config.get_species_data(species_name)
        if species_data and "texture_aspect_ratio" in species_data:
            aspect_ratio = float(species_data["texture_aspect_ratio"])
            model.apply_uv_aspect_ratio(aspect_ratio)
        else:
            # Default bark texture aspect ratio (slightly taller than wide)
            model.apply_uv_aspect_ratio(1.2)
    except Exception:
        # Fallback to default aspect ratio
        model.apply_uv_aspect_ratio(1.2)


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
            "build_blend": True,  # Smooth transitions between sections
            "texture_repeat": 1.0,  # UV texture repeat factor
            "resolution_reduce": 0.8,  # Resolution reduction for smaller branches
        }

    # Build models with comprehensive parameters
    models = grove.build_models(build_params)

    # Configure each model for proper export with Z-up and counter-clockwise winding
    for model in models:
        model.set_up_axis("Z")
        model.set_winding_order("COUNTER_CLOCKWISE")

    return models
