# GrowPy Skeleton Support

GrowPy now includes comprehensive skeleton generation and animation support for creating rigged tree models suitable for use in Blender, Unreal Engine, and other 3D applications.

## Features

- **Optimized Bone Hierarchies**: Configurable skeleton generation with bone count optimization
- **USD Export**: Full skeleton data embedded in USD files
- **Animation Ready**: Skeletons compatible with wind animation and manual posing
- **Grove Metadata**: Joint attributes include age, mass, and radius information
- **Cross-Platform**: Works with Blender, Unreal Engine, Houdini, and other USD-compatible tools

## Quick Start

### Basic Skeleton Generation

```python
from growpy import *
import pandas as pd

# Load and process forest data
forest_data = pd.read_csv("trees.csv")
calculate_growth_cycles_from_height(forest_data)

# Create and simulate forest
forest = create_forest(forest_data)
simulate_forest_growth(forest, cycles=20)

# Generate skeletons for all trees
for grove, species_name, tree_count in forest:
    skeletons = build_tree_skeletons(grove, optimize_bones=True)
    print(f"Generated {len(skeletons)} skeletons for {species_name}")
```

### Export with Skeletons

```python
# Export entire forest with skeletons
from pathlib import Path

output_dir = Path("output/skeletal_trees")
lod_configs = {
    "LOD0_Ultra": {"resolution": 64, "build_cutoff_thickness": 0.001},
    "LOD1_High": {"resolution": 32, "build_cutoff_thickness": 0.005}
}

# Export with skeleton optimization
skeleton_options = {
    'length_factor': 2.0,      # Longer bones (fewer joints)
    'reduce_threshold': 0.4,   # Remove thin branches
    'bias_factor': 0.3,        # Favor trunk over branches
    'connected': True          # Connected bone chains for IK
}

stats = export_forest_with_skeletons(
    forest, output_dir, lod_configs, skeleton_options
)

print(f"Exported {stats['total_exported']} models with {stats['skeletons_created']} skeletons")
```

### Convert to FBX with Textures

```python
# Use the enhanced USD to FBX converter
# Run: python 06_simple_usd_to_fbx.py

# This will automatically:
# 1. Find USD files with skeletons
# 2. Apply species-specific bark textures  
# 3. Apply twig textures
# 4. Export as FBX with armatures for Unreal Engine
```

## Skeleton Configuration Options

### Bone Optimization Parameters

- **`length_factor`** (0.0-5.0): Minimum bone length multiplier
  - Higher values = fewer, longer bones
  - Good for animation: 2.0-3.0

- **`reduce_threshold`** (0.0-1.0): Thickness threshold for bone removal
  - Removes branches below this thickness ratio
  - Recommended: 0.3-0.5 for clean rigs

- **`bias_factor`** (0.0-1.0): Distribution bias
  - 0.0 = favor trunk bones
  - 1.0 = favor branch bones  
  - Balanced: 0.3-0.5

- **`connected`** (bool): Whether bones form connected chains
  - True = better for IK systems
  - False = more flexible individual bones

### Example Configurations

```python
# For animation (fewer bones)
animation_config = {
    'length_factor': 2.5,
    'reduce_threshold': 0.5,
    'bias_factor': 0.2,
    'connected': True
}

# For detailed rigging (more bones)
detailed_config = {
    'length_factor': 1.0,
    'reduce_threshold': 0.2,
    'bias_factor': 0.8,
    'connected': False
}

# Balanced (default)
balanced_config = {
    'length_factor': 2.0,
    'reduce_threshold': 0.4,
    'bias_factor': 0.3,
    'connected': True
}
```

## Wind Animation

Generate skeletal wind animation:

```python
# Generate wind shapes for animation
wind_vector = (0.5, 0.0, 0.0)  # Wind direction (x, y, z)
frame_count = 50                # Number of animation frames
turbulence = 1.0               # Wind strength

for grove, species_name, _ in forest:
    wind_shapes = generate_wind_animation(
        grove, wind_vector, frame_count, turbulence
    )
    print(f"Generated {len(wind_shapes)} wind animation frames for {species_name}")
```

## USD File Structure

Skeletal USD files contain:

```
/TreeN (UsdGeomXform)
├── /TreeN/Geometry (UsdGeomMesh)
│   ├── Mesh with UV coordinates
│   ├── Skinning weights (skel:jointIndices, skel:jointWeights)
│   └── Grove attributes (TwigEnd, TwigSide, etc.)
├── /TreeN/Skeleton (UsdSkelSkeleton) 
│   ├── Joint hierarchy with transforms
│   ├── Bind and rest poses
│   └── Grove metadata (age, mass, radius)
└── /TreeN/TwigInstances (UsdGeomPointInstancer)
    └── Twig instances with orientations
```

## Blender Integration

1. **Import USD**: `File > Import > USD`
   - Skeletons automatically become armatures
   - Mesh gets armature modifier
   - Vertex groups created from joint weights

2. **Animation Setup**:
   - Select armature in Pose Mode
   - Bones are ready for keyframing
   - Use for wind animation or manual posing

3. **Twig Animation**:
   - Twig instances can be converted to mesh objects
   - Parent to bone deformers for secondary animation

## Unreal Engine Integration

1. **Import FBX**: Use the enhanced FBX files from the converter
   - Skeletal mesh with armature
   - Materials automatically applied
   - Ready for animation blueprints

2. **Animation**:
   - Import as Skeletal Mesh
   - Create Animation Blueprints
   - Use for wind systems or cutscenes

## Performance Considerations

- **Bone Count**: Optimize for target platform
  - Unreal: ~100-200 bones max per tree
  - Blender: Can handle more bones
  
- **LOD Integration**: Use different skeleton complexity per LOD
  - LOD0: Full skeleton detail
  - LOD1: Reduced bone count
  - LOD2: Trunk only

- **Instancing**: For forests, use mesh instancing with shared skeletons

## Troubleshooting

### Import Issues
- Ensure USD Python bindings are installed
- Check file paths for spaces or special characters
- Verify Grove core is available

### Animation Problems  
- Check bone hierarchy is connected
- Verify joint weights are properly assigned
- Ensure coordinate system is Z-up for Blender/Unreal

### Performance Issues
- Reduce bone count with higher `reduce_threshold`
- Use lower resolution models for distant trees
- Consider mesh instancing for large forests

## Scripts Overview

- **`07_generate_forest_with_skeletons.py`**: Generate forests with skeletal rigs
- **`06_simple_usd_to_fbx.py`**: Convert USD to FBX with skeletons and textures
- **`convert_to_fbx.py`**: Wrapper script for easy FBX conversion

## Next Steps

1. Run `07_generate_forest_with_skeletons.py` to create skeletal trees
2. Use `06_simple_usd_to_fbx.py` to convert to Unreal-ready FBX
3. Import into your 3D application and start animating!

The skeleton system provides a solid foundation for tree animation while maintaining compatibility with The Grove's existing workflow and USD pipeline.