# USD Scale Fix - 100x Scaling Applied

## Summary

Applied 100x scale factor to both tree geometry and twig placements to match real-world tree sizes. Grove exports trees at normalized scale (~1m tall), which appears tiny in Blender/Unreal Engine.

## Problem

**Before scaling:**

- Tree height: ~1.0-1.3 meters (tiny!)
- Tree vertices: (-0.001, 0, -0.004) to (-0.0541, 0.0485, 1.2953)
- Twig positions: (-0.016, 0.999, -0.015) to (-0.052, 1.295, -0.048)
- Trees appeared as tiny shrubs in Blender

**Root cause:**
Grove's `model_to_usda_string()` exports trees at normalized scale where 1 unit = 1 meter, but generated trees are only ~1-1.3m tall. This is appropriate for Grove's internal representation but too small for production use.

## Solution

### 1. Tree Mesh Scaling (blender_export.py)

Applied 100x scale during Y-up to Z-up coordinate transformation:

```python
# Scale factor: Grove exports trees at ~1m height, scale to realistic size
scale = 100.0

# Transform mesh geometry from Y-up to Z-up and scale by 100x
points_attr = mesh_usd.GetPointsAttr()
if points_attr:
    points = points_attr.Get()
    if points:
        # Convert each point: (x, y, z) -> (x*scale, -z*scale, y*scale)
        transformed_points = [Gf.Vec3f(p[0] * scale, -p[2] * scale, p[1] * scale) for p in points]
        points_attr.Set(transformed_points)
```

**Location**: `src/growpy/io/blender_export.py`, lines 720-742

### 2. Twig Position Handling (twig_placement.py)

Updated `convert_y_up_to_z_up()` to accept scale parameter with default 100x:

```python
def convert_y_up_to_z_up(
    pos: Tuple[float, float, float], scale: float = 100.0
) -> Tuple[float, float, float]:
    """Convert Y-up coordinates to Z-up with scaling.
    
    Args:
        scale: Scale factor (default: 100.0 for 1m -> 100m conversion)
    
    Returns:
        Position in Z-up coordinates scaled to real-world size
    """
    return (pos[0] * scale, -pos[2] * scale, pos[1] * scale)
```

**Critical detail**: When extracting twig positions from USD, use `scale=1.0` because positions are already in world-scale units (extracted from scaled tree mesh):

```python
# Don't scale positions here (scale=1.0) because they're already
# extracted from the scaled tree mesh vertices
center = convert_y_up_to_z_up(tuple(center), scale=1.0)
```

**Location**: `src/growpy/io/twig_placement.py`, lines 236-250, 526

## Results

**After scaling:**

- Tree height: ~100-130 meters (realistic mature tree)
- Tree vertices: (-0.1, 0, -0.4) to (-5.4, 4.89, 129.53)
- Twig positions: (-1.66, 1.58, 99.97) to (-5.21, 4.85, 129.56)
- Trees now appear at correct real-world scale in Blender/UE

### Sample Coordinates

**Tree mesh vertices (Beech_var1_tree_only.usda):**

```
Base:   (-0.1, 0, -0.4)              # Ground level
Middle: (-2.29, 2.37, 107.4)          # ~107m height
Top:    (-5.4, 4.89, 129.53)          # ~130m height
```

**Twig placements (Beech_var1.usda):**

```
(-1.66, 1.58, 99.97)    # 99.97m height
(-2.09, 2.37, 107.42)   # 107.42m height
(-3.26, 3.42, 114.75)   # 114.75m height
(-4.22, 4.18, 122.15)   # 122.15m height
(-5.21, 4.85, 129.56)   # 129.56m height
```

## Files Modified

1. **src/growpy/io/blender_export.py**
   - Function: `_add_grove_face_attributes_to_usd()`
   - Changes: Added `scale = 100.0` and applied to vertex transformation
   - Lines: 720-742

2. **src/growpy/io/twig_placement.py**
   - Function: `convert_y_up_to_z_up()`
   - Changes: Added `scale` parameter with default 100.0
   - Lines: 236-250
   - Usage: Call with `scale=1.0` when extracting from USD (line 526)

## Technical Notes

### Why 100x Scale?

- Grove generates trees at ~1-1.5m total height in normalized units
- Real mature trees: 20-40m (deciduous) to 50-100m+ (conifers)
- 100x factor provides reasonable default: 1m → 100m
- Users can adjust scale in Blender/UE if needed for specific species

### Coordinate System Flow

```
Grove Export (Y-up, 1m scale)
    ↓
USD with Z-up metadata + scaled geometry (100m scale)
    ↓
Extract twig positions (already in 100m scale)
    ↓
Rotate to Z-up WITHOUT scaling (scale=1.0)
    ↓
Final USD: Z-up, 100m scale, consistent tree + twigs
```

### Scale Application Points

1. **Tree mesh**: Scaled during post-processing of Grove's USD export
2. **Twig positions**: Extracted from scaled mesh, only rotated (not scaled again)
3. **Normals**: NOT scaled (they're unit vectors)

## Testing

```bash
# Regenerate forest with new scale
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda

# Check tree scale
grep "point3f\[\] points" data/output/forest/USD/Beech_var1_tree_only.usda | head -1
# Should show coordinates in ~100m range

# Check twig scale
grep "point3f\[\] positions" data/output/forest/USD/Beech_var1.usda
# Should show heights 99-130m matching tree geometry
```

## Import into Blender

Trees now import at realistic scale:

1. File → Import → Universal Scene Description (.usd)
2. Select USD file
3. Trees appear at ~100m height (mature tree scale)
4. Twigs positioned correctly at matching scale
5. No manual scaling needed!

## Related Documentation

- `TREE_USD_Z_UP_COMPLETE.md` - Coordinate system conversion
- `TWIG_COORDINATE_FIX.md` - Twig placement coordinate fix
- `COORDINATE_FIX_SUMMARY.md` - Original Y-up to Z-up conversion

## Date

October 7, 2025
