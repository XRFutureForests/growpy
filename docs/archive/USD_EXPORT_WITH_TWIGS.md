# USD Export with Twig Point Instances

This document describes how to export Grove trees as USD files with twigs added as point instances, following the Grove's native USD export format and twig placement specifications.

## Overview

The Grove can now export trees as USDA files with twigs automatically placed as USD PointInstancer prims. This approach:

1. **Uses Grove's Native USD Export**: Leverages `model_to_usda_string()` to preserve all Grove attributes
2. **Extracts Twig Placements**: Reads twig placement data from face attributes in the USD
3. **Adds Point Instances**: Creates memory-efficient PointInstancer prims for twigs
4. **Follows Grove Specs**: Orientation follows face normals as specified in Grove documentation
5. **Unreal Engine Ready**: Includes Nanite attributes and coordinate conversion

## Key Features

### Grove Native USD Export

The implementation uses The Grove's built-in USD export which provides:

- **Full Attribute Preservation**: All Grove face and point attributes are retained
- **Twig Placement Markers**: Tiny triangles marked with twig attributes (twig_long, twig_short, twig_upward, twig_dead)
- **Proper UVs and Normals**: Complete mesh data with UV mapping
- **Branch Hierarchy**: Branch indices and parent relationships

### Twig Point Instancing

Twigs are added as `UsdGeomPointInstancer` prims which provide:

- **Memory Efficiency**: Shared mesh data across millions of instances
- **GPU Performance**: Native GPU instancing support
- **Nanite Compatible**: Works with Unreal Engine 5.7+ Nanite
- **Streaming Ready**: Automatic LOD and streaming support

### Twig Orientation

Following The Grove documentation:

- Twigs are modeled along the **X-axis** (base at origin, growing in +X direction)
- Orientation is determined by the **face normal** of twig marker triangles
- Rotation matrices are converted to **half-precision quaternions** (quath) for USD
- Coordinate conversion from Blender (Z-up, right-handed) to Unreal (Z-up, left-handed)

## Usage

### Basic Example

```python
from growpy.core.grove import create_grove
from growpy.io.blender_export import (
    export_grove_tree_as_usda_native,
    get_twig_usd_map_for_species,
)
import the_grove_22_core as gc

# Create grove
grove = create_grove("European Beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Get twig USD files for this species
twig_usd_map = get_twig_usd_map_for_species("European Beech")

# Export as USDA with twigs
success = export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("beech_tree.usda"),
    species_name="European Beech",
    twig_usd_paths=twig_usd_map,
    include_twigs=True,
    use_point_instancer=True,
    convert_to_ue=True,
    resolution=24,
)
```

### CLI Tool

Use the provided CLI script for quick exports:

```bash
# Export with twigs
python src/growpy/cli/export_tree_usda.py "European Beech" --output beech.usda

# Export without twigs
python src/growpy/cli/export_tree_usda.py "Scots Pine" --no-twigs

# Adjust quality settings
python src/growpy/cli/export_tree_usda.py "European Beech" --resolution 32 --flushes 12
```

### Batch Export for Unreal

For exporting multiple species with variations:

```python
from growpy import batch_export_trees_for_unreal
import pandas as pd

# Load forest data
forest_data = pd.read_csv("forest_data.csv")

# Export with native USD export and twigs
results = batch_export_trees_for_unreal(
    forest_data=forest_data,
    output_dir=Path("data/output/unreal_vegetation"),
    num_variations=3,
    export_formats=["usda", "fbx"],
    use_native_usd_export=True,  # Use Grove's native USD export
    include_twigs_in_usd=True,   # Add twigs as point instances
    resolution=24,
)

print(f"Exported {len(results['usd'])} USD files")
```

## USD File Structure

The exported USDA file has the following structure:

```usda
#usda 1.0

def Xform "TreeAssembly"
{
    # Main tree mesh (from Grove's native export)
    def "Tree" (
        references = @./tree_only.usda@
    )
    {
        custom token unrealNanite = "enable"
    }

    # Twig prototypes (instanceable for memory efficiency)
    def Scope "Prototypes" {
        def Xform "twig_long" (
            instanceable = true
            references = @./twigs/beech_apical.usda@
        )
        {
            custom token unrealNanite = "enable"
            custom bool unrealNanitePreserveArea = true
        }

        def Xform "twig_short" (
            instanceable = true
            references = @./twigs/beech_lateral.usda@
        )
        {
            custom token unrealNanite = "enable"
            custom bool unrealNanitePreserveArea = true
        }
    }

    # Twig instances (memory-efficient PointInstancer)
    def PointInstancer "TwigInstances"
    {
        rel prototypes = [
            </TreeAssembly/Prototypes/twig_long>,
            </TreeAssembly/Prototypes/twig_short>
        ]
        int[] protoIndices = [0, 0, 1, 1, 0, 1, ...]
        point3f[] positions = [(x, y, z), ...]
        quath[] orientations = [(w, x, y, z), ...]  # Half-precision quaternions!
        float3[] scales = [(1, 1, 1), ...]
    }
}
```

## Grove Twig Attributes

The Grove exports trees with the following twig face attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `twig_long` | bool | Apical/terminal twigs (end of branches) |
| `twig_short` | bool | Lateral twigs (side branches) |
| `twig_upward` | bool | Upward-facing twigs |
| `twig_dead` | bool | Dead/winter twigs |

Each attribute marks tiny triangles where twigs should be instanced. The normal of these triangles determines the twig orientation.

## Coordinate System Conversion

The export automatically converts between coordinate systems:

**Blender/Grove** (Z-up, Right-handed):
- X: Right
- Y: Forward
- Z: Up

**Unreal Engine** (Z-up, Left-handed):
- X: Forward
- Y: Right
- Z: Up

Conversion formula:
```python
ue_pos = (blender_pos[0], blender_pos[2], -blender_pos[1])
ue_normal = (blender_normal[0], blender_normal[2], -blender_normal[1])
```

## Twig Orientation Details

### Twig Model Requirements

Twigs must be modeled with:
- **Base at origin** (0, 0, 0)
- **Growing along +X axis**
- Leaves/foliage extending in +Y and +Z directions

### Rotation Matrix to Quaternion

The implementation uses **Shepperd's method** for numerical stability when converting rotation matrices to quaternions:

1. Calculate face center and normal from twig marker triangles
2. Build orthonormal basis with X-axis aligned to normal
3. Convert rotation matrix to quaternion
4. Normalize to unit length (critical for USD)
5. Store as **half-precision quaternion (quath)** in USD

### Half-Precision Quaternions

USD uses `GfQuath` (not `GfQuatf`) for rotations in PointInstancer:
- Provides ~0.001 radian angular precision
- Must be normalized to unit length
- Format: (w, x, y, z)
- Saves memory with large instance counts

## Nanite Settings

### Tree Mesh
```usda
custom token unrealNanite = "enable"
```

### Twig Meshes (Foliage)
```usda
custom token unrealNanite = "enable"
custom bool unrealNanitePreserveArea = true  # Critical for foliage!
```

The `unrealNanitePreserveArea` attribute is **essential for foliage** to prevent thinning at distance in Nanite.

## Performance Considerations

### PointInstancer vs Individual Xforms

**PointInstancer** (Recommended):
- ✓ Memory efficient with millions of instances
- ✓ GPU-driven culling and rendering
- ✓ Native Nanite support in UE 5.7+
- ✓ Automatic LOD and streaming
- ✗ Half-precision rotation (minor quality trade-off)

**Individual Xforms** (Fallback):
- ✓ Full-precision transforms
- ✓ Compatible with older USD implementations
- ✗ Memory intensive with many instances
- ✗ Slower scene traversal
- ✗ Less efficient in Unreal Engine

### Quality Settings

Adjust these parameters based on your needs:

```python
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=output_path,
    species_name=species_name,

    # Mesh quality
    resolution=24,              # 16=low, 24=medium, 32=high
    resolution_reduce=0.8,      # How fast to reduce detail on thin branches
    texture_repeat=3,           # Bark texture repetitions

    # Branch cutoffs (performance optimization)
    build_cutoff_age=0,         # Skip branches younger than N years
    build_cutoff_thickness=0.0, # Skip branches thinner than N meters

    # Geometry options
    build_blend=True,           # Smooth branch joints
    build_end_cap=True,         # Close branch ends
)
```

## Troubleshooting

### No Twig USD Files Found

**Problem**: `get_twig_usd_map_for_species()` returns empty dict

**Solutions**:
1. Convert twig FBX files to USD:
   ```bash
   python src/growpy/cli/convert_twigs.py data/assets/twigs/
   ```

2. Check twig paths in species lookup table:
   ```python
   from growpy.config import GrowPyConfig
   twig_files = GrowPyConfig.get_twig_files_by_type("European Beech")
   print(twig_files)
   ```

### Twigs Not Appearing in Unreal

**Problem**: USD imports but twigs are invisible

**Checks**:
1. Verify PointInstancer has data:
   ```bash
   usdview tree_assembly.usda
   ```

2. Check import settings in Unreal:
   - Enable Nanite on import
   - Use "Keep Instances" collapse mode
   - Verify materials are assigned

3. Check console for warnings about missing twig references

### Twig Orientations Wrong

**Problem**: Twigs pointing in wrong directions

**Checks**:
1. Verify twig models follow X-axis convention
2. Check coordinate conversion is enabled: `convert_to_ue=True`
3. Inspect face normals in Grove USD export

### USD Import Errors

**Problem**: USD file fails to load in Unreal/other DCCs

**Solutions**:
1. Validate USD with usdchecker:
   ```bash
   usdchecker tree_assembly.usda
   ```

2. Check for missing twig references:
   ```bash
   usdresolve tree_assembly.usda
   ```

3. Ensure all referenced USD files exist

## API Reference

### Main Functions

#### `export_grove_tree_as_usda_native()`

Export Grove tree using native USD export with optional twig point instances.

**Parameters**:
- `grove`: Grove instance with simulated trees
- `output_path`: Path for output USDA file
- `species_name`: Tree species name
- `twig_usd_paths`: Dict mapping twig types to USD paths (optional)
- `include_twigs`: Whether to add twigs as point instances (default: True)
- `use_point_instancer`: Use USD PointInstancer (default: True)
- `convert_to_ue`: Convert coordinates to Unreal Engine (default: True)
- `resolution`: Branch resolution 4-32 (default: 32)
- `resolution_reduce`: Detail reduction rate 0.0-1.0 (default: 0.8)
- `build_blend`: Smooth branch joints (default: True)
- `build_end_cap`: Close branch ends (default: True)

**Returns**: `bool` - Success status

#### `get_twig_usd_map_for_species()`

Get mapping of twig types to USD file paths for a species.

**Parameters**:
- `species_name`: Name of tree species
- `config`: GrowPy configuration (optional)

**Returns**: `Dict[str, Path]` - Mapping of twig types to USD paths

### Twig Type Mapping

The function automatically maps twig file names to Grove attributes:

| Grove Attribute | Twig File Keywords |
|----------------|-------------------|
| `twig_long` | apical, long, end, terminal |
| `twig_short` | lateral, short, side |
| `twig_upward` | upward, up |
| `twig_dead` | dead, fall, winter |

## Related Documentation

- [Grove USD Export](the_grove_core.io.md#model_to_usda_string) - Grove's native USD export
- [Twig Placement](TWIG_PLACEMENT.md) - Twig placement extraction and processing
- [USD Point Instancer](USD_POINT_INSTANCER.md) - Technical details on point instancing
- [Convert Twigs](../cli/convert_twigs.py) - Converting twig FBX to USD

## References

- [USD PointInstancer Documentation](https://openusd.org/dev/api/class_usd_geom_point_instancer.html)
- [Unreal Engine USD Import](https://docs.unrealengine.com/5.7/en-US/USD/)
- [Grove Core API](https://www.thegrove3d.com/documentation/)

## Examples

See `src/growpy/cli/export_tree_usda.py` for a complete working example.
