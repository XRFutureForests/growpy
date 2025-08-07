# Grove API Integration Improvements for GrowPy

This document summarizes the enhancements made to the GrowPy modules to ensure correct usage of The Grove API for exporting tree models with skeletons, textures, materials, and other advanced features.

## Overview of Changes

Based on the Grove documentation analysis, several key improvements were implemented across the GrowPy modules to leverage Grove's comprehensive 3D model building system properly.

## Key Grove API Features Integrated

### 1. Comprehensive Model Building Parameters

**Updated Function**: `build_lod_models()` in `tree.py`

**Improvements**:

- Added comprehensive Grove build parameters based on documentation:

  ```python
  build_options = {
      "resolution": config.get("resolution", 16),      # Cross-section sides (4-24)
      "build_end_cap": config.get("build_end_cap", True),  # Cap branch ends
      "build_cutoff_thickness": config.get("build_cutoff_thickness", 0.0),
      "build_cutoff_age": config.get("build_cutoff_age", 0),
      "build_blend": config.get("build_blend", True),
      "texture_repeat": config.get("texture_repeat", 1.0),
      "resolution_reduce": config.get("resolution_reduce", 0.8),
  }
  ```

**Grove API Used**: `grove.build_models(build_options)`

### 2. Proper Model Configuration for Export

**Improvements Made**:

- Automatic Z-up coordinate system: `model.set_up_axis("Z")`
- Counter-clockwise winding for Unreal/Blender: `model.set_winding_order("COUNTER_CLOCKWISE")`
- UV aspect ratio correction: `model.apply_uv_aspect_ratio(texture_aspect_ratio)`

**Functions Enhanced**:

- `save_tree_to_usd()`
- `save_tree_with_skeleton()`
- `build_lod_models()`
- `create_skeleton_lod_models()`

### 3. Enhanced Skeleton System Integration

**Updated Function**: `build_tree_skeletons()` in `tree.py`

**Grove API Used**:

- `grove.build_skeletons()` for basic skeleton generation
- Added comprehensive skeleton attribute extraction in `get_skeleton_info()`
- Proper skeleton integration in USD export

**Skeleton Attributes Extracted**:

- `skeleton.points` - Joint coordinates
- `skeleton.poly_lines` - Bone connections  
- `skeleton.location` - Skeleton origin
- `skeleton.point_attribute_age` - Joint ages
- `skeleton.point_attribute_mass` - Joint masses
- `skeleton.point_attribute_radius` - Joint radii

### 4. Face-Based Twig System Integration

**New Function**: `extract_twig_data_from_grove_model()` in `twig.py`

**Grove Face Attributes Used**:

- `face_attribute_twig_long` → TwigEnd placement
- `face_attribute_twig_short` → TwigSide placement  
- `face_attribute_twig_upward` → TwigUpward placement
- `face_attribute_twig_dead` → TwigDead placement

**Integration Method**:

```python
def extract_twig_data_from_grove_model(model):
    faces = model.faces
    points = model.get_points_as_tuples()
    
    # Extract face attribute data for twig placement
    if hasattr(model, 'face_attribute_twig_long'):
        # Process each face marked for twig placement
        for face_idx, should_have_twig in enumerate(face_attribute_twig_long):
            if should_have_twig:
                # Calculate face center and normal for twig placement
                face_center = calculate_face_center(points, faces[face_idx])
                face_normal = calculate_face_normal(points, faces[face_idx])
```

### 5. Enhanced Wind Animation System

**Updated Function**: `generate_wind_animation()` in `tree.py`

**Grove API Used**:

- `grove.build_wind_shape()` with comprehensive parameters
- Proper Grove Vector objects: `gc.Vector(x, y, z)`
- Enhanced error handling for different Grove versions

**Wind Parameters**:

```python
wind_build_params = {
    "resolution": 32,
    "resolution_reduce": 0.8,
    "texture_repeat": 1.0,
    "build_cutoff_age": 0,
    "build_blend": True,
    "build_end_cap": True,
}
```

### 6. Comprehensive Model Attribute Access

**New Function**: `get_model_attributes()` in `tree.py`

**Grove Attributes Extracted**:

**Point Attributes (Vertex-based)**:

- `point_attribute_age` - Vertex age
- `point_attribute_thickness` - Branch thickness
- `point_attribute_photosynthesis` - Photosynthesis efficiency
- `point_attribute_shade` - Shade level
- `point_attribute_vigor` - Growth vigor
- `point_attribute_bone_id` - Bone ID for animation

**Face Attributes (Polygon-based)**:

- `face_attribute_branch_id` - Branch identifier
- `face_attribute_branch_id_parent` - Parent branch
- `face_attribute_dead` - Dead wood indicator
- `face_attribute_twig_*` - Twig placement markers
- `face_attribute_end` - Branch end faces

### 7. Species-Specific Material Integration

**New Function**: `apply_species_texture_settings()` in `tree.py`

**Features**:

- Species-specific texture aspect ratios
- Automatic UV correction based on species data
- Integration with GrowPy config system for species lookup

### 8. Enhanced Forest Simulation

**Updated Functions** in `forest.py`:

- `simulate_forest_growth()` - Proper Grove light competition
- `create_forest_with_attributes()` - Enhanced attribute tracking

**Grove API Used**:

- `grove.create_shade_geometry_coords()` for light competition
- `grove.calculate_shade_together()` for multi-species shading
- `grove.weigh_and_bend()` for branch physics
- `grove.simulate()` for growth cycles

## New Enhanced Utility Script

**Created**: `04_enhanced_grove_forest.py`

**Features**:

- Comprehensive Grove API usage demonstration
- Proper LOD configuration with Grove parameters
- Skeleton generation and export
- Species-specific texture handling
- Grove twig system integration
- Wind animation generation
- Full attribute preservation

**LOD Configuration Example**:

```python
lod_configs = {
    "lod0": {
        "resolution": 24,              # High resolution cross-sections
        "build_end_cap": True,         # Cap branch ends
        "build_cutoff_thickness": 0.0, # Build all branches
        "build_cutoff_age": 0,         # Build all ages
        "build_blend": True,           # Smooth transitions
        "texture_repeat": 1.0,         # Standard UV repeat
        "resolution_reduce": 0.9,      # Minimal reduction
    },
    "skeletal": {
        "resolution": 8,               # Skeleton-optimized
        "build_end_cap": False,        # No end caps for animation
        "build_cutoff_thickness": 0.03,
        "build_cutoff_age": 0,
        "build_blend": True,
        "texture_repeat": 1.0,
        "resolution_reduce": 0.6,
    }
}
```

## Updated Module Exports

**Enhanced `__init__.py`**:

- Added all new Grove-integrated functions
- Proper documentation of Grove API workflow
- Conditional imports for twig integration
- Comprehensive function exports

## Key Benefits of These Improvements

1. **Proper Grove API Usage**: All functions now use Grove's comprehensive parameter system
2. **Full Attribute Preservation**: Models export with all Grove's rich attribute data
3. **Skeletal Animation Support**: Proper skeleton generation and integration
4. **Material System Integration**: Species-specific textures and UV correction
5. **Face-Based Twig System**: Integration with Grove's sophisticated twig placement
6. **Enhanced USD Export**: Proper coordinate systems and winding orders
7. **Wind Animation**: Grove's wind system for dynamic forests
8. **Multi-LOD Support**: Comprehensive LOD generation with Grove parameters

## Usage Example

```python
from growpy import *

# Enhanced configuration
config = GrowPyConfig()
set_global_config(config)

# Create forest with Grove integration
forest_data = pd.read_csv("trees.csv")
calculate_growth_cycles_from_height(forest_data)
forest = create_forest_with_attributes(forest_data)

# Simulate with Grove features
simulate_forest_growth(forest, cycles=20)

# Build with comprehensive Grove parameters
lod_configs = config.get_lod_configs()
for grove, species_name, tree_count, attributes in forest:
    lod_models = build_lod_models(grove, lod_configs, texture_aspect_ratio=1.2)
    skeletons = build_tree_skeletons(grove, optimize_bones=True)
    
    for i, model in enumerate(lod_models["lod0"]):
        # Apply Grove material system
        apply_species_texture_settings(model, species_name, config)
        
        # Export with skeleton data
        save_tree_with_skeleton(model, skeletons[i], output_path)
        
        # Integrate Grove twig system
        add_twigs_to_grove_model(model, species_name, config)
```

This comprehensive integration ensures that GrowPy leverages The Grove's full feature set for professional-quality tree model generation, animation, and export.
