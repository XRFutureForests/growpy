# USD Builder - Direct Grove API Integration

## Overview

The `usd_builder.py` module replaces Grove's `model_to_usda_string()` export with direct Grove API geometry access. This eliminates coordinate transformation issues and simplifies the USD export pipeline.

## Problem Statement

### Original Workflow Issues

The previous implementation used Grove's native USD export:

```python
usda_string = gc.io.model_to_usda_string(model)
with open(output_path, "w") as f:
    f.write(usda_string)

# Required coordinate transformation
_convert_mesh_yup_to_zup(output_path)  # (x,y,z) → (x,-z,y)
```

**Problems:**

1. Grove exported in Y-up coordinates requiring transformation
2. Coordinate transformation created complexity and potential errors
3. Transformation had to be reapplied after any USD modifications
4. Difficult to integrate skeleton data without coordinate mismatches
5. Twig placement required careful coordinate system handling

### New Approach - Direct API Access

The new implementation accesses Grove geometry data directly:

```python
# Extract geometry directly from Grove model
points = model.points  # Already in correct coordinate system!
faces = model.faces
uvs = model.uvs
face_attributes = model.face_attribute_twig_long  # etc.

# Build USD directly
from growpy.io import build_tree_usd
build_tree_usd(model, output_path, up_axis="Z")
```

**Benefits:**

1. **No transformation needed** - API provides correct coordinates
2. **Simpler pipeline** - Direct USD construction
3. **Better skeleton integration** - Coordinates match perfectly
4. **Attribute preservation** - All Grove face/point attributes preserved
5. **More maintainable** - Single coordinate system throughout

## Implementation Details

### Core Functions

#### `build_tree_usd(model, output_path, up_axis="Z", triangulated=True)`

Builds USD file directly from Grove model:

```python
from growpy.io import build_tree_usd

# After building Grove model
models = grove.build_models(build_params)
model = models[0]
model.triangulate()

# Create USD with direct API
success = build_tree_usd(
    model=model,
    output_path=Path("tree.usda"),
    up_axis="Z",
    triangulated=True
)
```

**What it does:**

1. Extracts `points`, `faces`, `uvs` from Grove model
2. Converts to USD format (Gf.Vec3f, face indices)
3. Creates USD stage with proper coordinate system
4. Adds all Grove face attributes as primvars (TwigLong, TwigShort, etc.)
5. Adds all Grove point attributes as primvars (Age, Mass, Thickness, etc.)
6. Saves USD file

#### `add_skeleton_to_usd(usd_path, grove, skeleton_length, skeleton_reduce, ...)`

Adds UsdSkel skeleton using Grove's bone tagging API:

```python
from growpy.io import add_skeleton_to_usd

# Add skeleton to existing USD
skeleton_success = add_skeleton_to_usd(
    usd_path=Path("tree.usda"),
    grove=grove,
    skeleton_length=2.0,
    skeleton_reduce=0.4,
    skeleton_bias=0.5,
    skeleton_connected=True
)
```

**What it does:**

1. Calls `grove.build_skeletons()` to get skeleton data
2. Calls `grove.tag_bone_id()` to generate bones (matches Blender export)
3. Creates UsdSkel structure with joints and transforms
4. Binds skeleton to tree mesh
5. Adds skinning data (joint influences and weights)

#### `add_materials_to_usd(usd_path, species_name, textures=None)`

Adds material definitions and texture bindings:

```python
from growpy.io import add_materials_to_usd

add_materials_to_usd(
    usd_path=Path("tree.usda"),
    species_name="Beech",
    textures={
        'diffuse': 'bark_diffuse.png',
        'normal': 'bark_normal.png'
    }
)
```

### Coordinate System

**Grove API Coordinate System (the-grove-output-complete.py findings):**

- Grove API returns geometry in the **correct** coordinate system
- No transformation needed for Z-up output
- Points are accessed as: `model.points[i].x, .y, .z`
- Directly compatible with USD Z-up convention

**Comparison:**

| Method | Coordinate System | Transformation | Integration |
|--------|------------------|----------------|-------------|
| `model_to_usda_string()` | Y-up (OpenGL) | Required: `(x,y,z) → (x,-z,y)` | Complex |
| Direct API (`model.points`) | Z-up (native) | None needed | Simple |

### Attribute Preservation

All Grove attributes are preserved as USD primvars:

**Face Attributes (uniform):**

- `TwigLong` - Long twig placement triangles
- `TwigShort` - Short twig placement
- `TwigUpward` - Upward facing twigs
- `TwigDead` - Dead twigs
- `Dead` - Dead branch faces
- `End` - Branch end cap faces
- `BranchIndex` - Branch identification
- `BranchIndexParent` - Parent branch ID

**Point Attributes (vertex):**

- `Age` - Node age in flushes
- `Mass` - Branch mass
- `Thickness` - Branch diameter
- `Pitch` - Vertical angle
- `Vigor` - Growth power
- `Shade` - Ambient occlusion
- `Photosynthesis` - Light exposure

## Migration Guide

### Updating Existing Code

**Before (using Grove's USDA string):**

```python
from the_grove_23_core import grove_core as gc

models = grove.build_models(build_params)
model = models[0]
model.triangulate()

# Old approach
usda_string = gc.io.model_to_usda_string(model)
with open("tree.usda", "w") as f:
    f.write(usda_string)

# Required transformation
_convert_mesh_yup_to_zup("tree.usda")
```

**After (using USD builder):**

```python
from growpy.io import build_tree_usd

models = grove.build_models(build_params)
model = models[0]
model.triangulate()

# New approach - direct API
build_tree_usd(model, Path("tree.usda"), up_axis="Z")
# No transformation needed!
```

### Integration with Existing Workflows

The new USD builder is a drop-in replacement:

**In `blender_export.py`:**

```python
# OLD
usda_string = gc.io.model_to_usda_string(model)
with open(temp_tree_path, "w") as f:
    f.write(usda_string)
_convert_mesh_yup_to_zup(temp_tree_path)

# NEW
from .usd_builder import build_tree_usd
build_tree_usd(model, temp_tree_path, up_axis="Z", triangulated=True)
```

**In `unreal_nanite_assembly.py`:**

```python
# OLD
usda_string = gc.io.model_to_usda_string(model)
with open(temp_tree_path, "w") as f:
    f.write(usda_string)

# NEW
from .usd_builder import build_tree_usd
build_tree_usd(model, temp_tree_path, up_axis="Z", triangulated=False)
```

## Testing

### Validation Script

Run the test script to verify the implementation:

```bash
conda activate growpy
python test_usd_builder.py
```

This will:

1. Generate tree using Grove API
2. Export with new USD builder
3. Add skeleton
4. Verify USD structure
5. Compare coordinates with API data

### Expected Output

```
USD Builder Test - Direct Grove API
============================================================

1. Creating grove and simulating tree growth...
   Tree simulated with 5 growth cycles

2. Building 3D model...
   Model generated:
   - Points: 9381
   - Faces: 13934
   - UVs: 55736

3. Triangulating mesh...
   Faces after triangulation: 27868

4. Testing new USD builder (direct API)...
   ✓ Successfully created: data/output/test_tree_new.usda
   - Coordinate system: Z-up
   - No transformation applied

5. Testing skeleton addition...
   ✓ Successfully added skeleton: data/output/test_tree_skeletal.usda
   - Bones created: 19

6. Verifying USD file structure...
   - Stage up axis: Z
   - USD points count: 9381
   - First point (USD): (-0.0084, -0.0002, -0.0341)
   - First point (API): (-0.0084, -0.0002, -0.0341)
   - Primvars found: 15
     st, TwigLong, TwigShort, TwigUpward, TwigDead...
   ✓ USD structure verified

Test Summary
============================================================
✓ New USD builder working: True
✓ Skeleton addition working: True
```

### Validation Checklist

- [ ] USD file created successfully
- [ ] Coordinate system is Z-up
- [ ] Point coordinates match API data (no transformation)
- [ ] All face attributes present as primvars
- [ ] All point attributes present as primvars
- [ ] Skeleton added with correct bone count
- [ ] USD imports correctly in Unreal Engine
- [ ] Mesh appears in correct orientation (not flipped/rotated)
- [ ] Skeleton bones positioned correctly

## Technical Notes

### Why Direct API Access Works

The discovery from `the-grove-output-complete.py` showed that Grove's Python API provides geometry in the native coordinate system:

```python
# Direct access to Grove model data
points = model.points  # List of Vector objects
for i, p in enumerate(points):
    print(f"{i}: {p.x}, {p.y}, {p.z}")
# Output: Already in Z-up coordinates!
```

This eliminates the need for the `(x, y, z) → (x, -z, y)` transformation that was required with `model_to_usda_string()`.

### Skeleton Integration

The skeleton system uses Grove's `tag_bone_id()` API which provides:

- Branch ID and bone ID
- Start and end points (in correct coordinates)
- Radius and mass
- Parent bone relationships

This data is directly compatible with UsdSkel without transformation.

### Future Improvements

Potential enhancements to the USD builder:

1. **Weight Painting**: Implement proper vertex weight calculation based on branch structure
2. **Texture Support**: Add full texture reference system for bark materials
3. **LOD Export**: Support multiple detail levels in single USD
4. **Animation**: Add wind animation and growth sequence support
5. **Nanite Integration**: Enhanced Nanite-specific attributes

## Related Files

- `src/growpy/io/usd_builder.py` - New USD builder implementation
- `src/growpy/io/blender_export.py` - Updated to use USD builder
- `src/growpy/io/unreal_nanite_assembly.py` - Updated to use USD builder
- `src/the-grove-output-complete.py` - Discovery script showing API data
- `test_usd_builder.py` - Validation test script
- `data/output/grove_geometry_dump/` - API data examples

## References

- Grove 2.3 API documentation
- USD (Universal Scene Description) documentation
- UsdSkel (USD Skeleton) specification
- Unreal Engine USD import guidelines
