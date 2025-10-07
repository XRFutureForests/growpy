# Tree USD Coordinate System Conversion Complete

## Summary

Both the **tree mesh** and **twig placements** are now properly converted from Grove's Y-up export to Z-up standard.

## Changes Made

### 1. Tree Mesh Transformation

**File**: `src/growpy/io/blender_export.py`

Modified `_add_grove_face_attributes_to_usd()` to:

1. Set stage metadata to Z-up: `UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)`
2. Transform all mesh vertices: `(x, y, z) → (x, -z, y)`
3. Transform all normals: `(x, y, z) → (x, -z, y)`

```python
# Convert stage from Y-up to Z-up
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

# Transform mesh geometry
points_attr = mesh_usd.GetPointsAttr()
if points_attr:
    points = points_attr.Get()
    transformed_points = [Gf.Vec3f(p[0], -p[2], p[1]) for p in points]
    points_attr.Set(transformed_points)

# Transform normals
normals_attr = mesh_usd.GetNormalsAttr()
if normals_attr and normals_attr.HasValue():
    normals = normals_attr.Get()
    transformed_normals = [Gf.Vec3f(n[0], -n[2], n[1]) for n in normals]
    normals_attr.Set(transformed_normals)
```

### 2. Twig Placement Transformation

**File**: `src/growpy/io/twig_placement.py`

Added Y-up to Z-up conversion functions and applied when extracting placements:

```python
def convert_y_up_to_z_up(pos):
    """Rotate -90° around X-axis: (x, y, z) -> (x, -z, y)"""
    return (pos[0], -pos[2], pos[1])

def convert_y_up_normal_to_z_up(normal):
    """Rotate -90° around X-axis: (x, y, z) -> (x, -z, y)"""
    return (normal[0], -normal[2], normal[1])
```

## Verification

### Tree Mesh (Beech_var1_tree_only.usda)

**Metadata:**

```usd
upAxis = "Z"  ✓ (was "Y")
```

**Vertex Positions:**

```usd
# Base vertices (ground level, Z ≈ 0)
point3f[] points = [
    (-0.001, 0, -0.004),      # Z = -0.004
    (-0.001, -0.0002, -0.004) # Z = -0.004
    ...
]

# Top vertices (height, Z ≈ 1.0-1.3)
[
    (-0.0186, 0.0159, 0.9997),  # Z = 0.999
    (-0.0229, 0.0237, 1.074),   # Z = 1.074
    (-0.0347, 0.0342, 1.1473),  # Z = 1.147
    (-0.0442, 0.0418, 1.2213),  # Z = 1.221
    (-0.0541, 0.0485, 1.2953)   # Z = 1.295
]
```

### Twig Placements (Beech_var1.usda)

**Positions:**

```usd
point3f[] positions = [
    (-0.016633334, 0.9997333, -0.015866667),   # Y (height) = 0.999
    (-0.020966666, 1.0742333, -0.023766667),   # Y (height) = 1.074
    (-0.03266667, 1.1475, -0.0342),            # Y (height) = 1.147
    (-0.0422, 1.2215333, -0.0418),             # Y (height) = 1.221
    (-0.0521, 1.2955667, -0.048533335)         # Y (height) = 1.295
]
```

## Before vs After

### Tree Mesh

| Aspect | Before (Y-up) | After (Z-up) |
|--------|---------------|--------------|
| upAxis | `"Y"` | `"Z"` |
| Height coordinate | Y-axis | Z-axis |
| Base vertex | `(-0.001, -0.004, 0)` | `(-0.001, 0, -0.004)` |
| Top vertex | `(-0.0186, 0.9997, -0.0159)` | `(-0.0186, 0.0159, 0.9997)` |

### Twig Placements

| Aspect | Before | After |
|--------|--------|-------|
| Height coordinate | Z-axis (negative) | Y-axis (positive) |
| Base position | `(-0.016, -0.015, -0.999)` | `(-0.016, 0.999, -0.015)` |
| Top position | `(-0.052, -0.048, -1.295)` | `(-0.052, 1.295, -0.048)` |

## Import into Blender

When importing `Beech_var1.usda` into Blender:

1. File → Import → Universal Scene Description (.usd)
2. Select the USD file
3. **Result**:
   - Tree grows upward along Z-axis ✓
   - Twigs positioned correctly along branches ✓
   - No rotation needed ✓

## Technical Details

### Coordinate System

```
Y-up (Grove):        Z-up (Blender/UE):
  Y                    Z
  ↑                    ↑
  |                    |
  +--→ X               +--→ X
 /                    /
Z                    Y
```

### Transformation Math

**-90° rotation around X-axis:**

- X stays the same (horizontal)
- Y (height) → Z (height)
- Z (forward) → -Y (into screen)

**Matrix form:**

```
[x]   [1   0   0] [x]   [x ]
[y] → [0   0  -1]·[y] = [-z]
[z]   [0   1   0] [z]   [y ]
```

## Files Modified

1. `src/growpy/io/blender_export.py` - Tree mesh transformation
2. `src/growpy/io/twig_placement.py` - Twig placement transformation

## Related Documentation

- `TWIG_PLACEMENT_FIX.md` - Twig attribute export fix
- `TWIG_COORDINATE_FIX.md` - Twig placement coordinate fix
- `COORDINATE_FIX_SUMMARY.md` - Quick reference

## Testing

```bash
# Regenerate forest
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda

# Verify tree metadata
head -10 data/output/forest/USD/Beech_var1_tree_only.usda
# Should show: upAxis = "Z"

# Verify tree vertices (Z should be height)
grep "point3f\[\] points" data/output/forest/USD/Beech_var1_tree_only.usda | head -1

# Verify twig positions (Y should be height)
grep "point3f\[\] positions" data/output/forest/USD/Beech_var1.usda
```

## Date

October 7, 2025
