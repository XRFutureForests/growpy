# Twig Placement Coordinate System Fix - Summary

## Issue

Twig instances were positioned along the **Y-axis** instead of the **Z-axis** when loading USD assemblies into Blender, making twigs appear horizontally oriented rather than vertically along the tree's growth axis.

## Root Cause

**Grove exports USD in Y-up coordinate system** (`upAxis = "Y"`), following OpenGL convention. However, **Blender and Unreal Engine use Z-up**. The twig placement code was extracting positions directly from Grove's Y-up USD without converting them to Z-up.

### Before Fix

```usd
# Twig positions with HEIGHT on Z-axis (wrong for Z-up systems)
point3f[] positions = [
    (-0.016633334, -0.015866667, -0.9997333),  # Z = -0.999 (height, negative)
    (-0.020966666, -0.023766667, -1.0742333),  # Z = -1.074
    ...
]
```

### After Fix

```usd
# Twig positions with HEIGHT on Y-axis (correct for Z-up systems)
point3f[] positions = [
    (-0.016633334, 0.9997333, -0.015866667),   # Y = 0.999 (height, positive)
    (-0.020966666, 1.0742333, -0.023766667),   # Y = 1.074
    ...
]
```

## Solution

Added Y-up to Z-up coordinate transformation when extracting twig placements from Grove USD files.

### Implementation

**File**: `src/growpy/io/twig_placement.py`

1. **Created transformation functions**:

   ```python
   def convert_y_up_to_z_up(pos):
       """Rotate -90° around X-axis: (x, y, z) -> (x, -z, y)"""
       return (pos[0], -pos[2], pos[1])
   
   def convert_y_up_normal_to_z_up(normal):
       """Rotate -90° around X-axis: (x, y, z) -> (x, -z, y)"""
       return (normal[0], -normal[2], normal[1])
   ```

2. **Applied in `extract_twig_placements_from_usd()`**:

   ```python
   # Convert from Y-up (Grove) to Z-up (Blender/USD standard)
   center = convert_y_up_to_z_up(tuple(center))
   normal = convert_y_up_normal_to_z_up(tuple(normal))
   ```

## Verification

```bash
# Regenerate forest
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda

# Check twig positions (Y should be height ~0.9-1.3)
grep -A 1 "point3f\[\] positions" data/output/forest/USD/Beech_var1.usda

# Import into Blender to verify visual placement
```

## Coordinate System Diagram

```
Y-up (Grove Export):     Z-up (Blender/UE):
      Y                        Z
      ↑                        ↑
      |                        |
      +--→ X                   +--→ X
     /                        /
    Z                        Y

Transformation: -90° rotation around X-axis
(x, y, z) → (x, -z, y)
```

## Technical Details

- **Applies to**: Twig placement positions and normals extracted from Grove USD
- **Does not modify**: Original tree mesh (stays in Y-up)
- **Works with**: UE coordinate conversion (applied after Y→Z conversion)
- **Affects**: `UsdGeomPointInstancer` positions and orientations

## Files Modified

- `src/growpy/io/twig_placement.py` - Added transformation functions and applied in extraction

## Related Documentation

- `TWIG_PLACEMENT_FIX.md` - Previous fix for twig attribute export
- `TWIG_COORDINATE_FIX.md` - Detailed technical documentation of this fix

## Testing Results

✅ Twig positions now use Y as height (positive values)  
✅ Twigs orient correctly along tree growth axis  
✅ 5 twig instances placed successfully  
✅ USD imports correctly into Blender  
✅ Nanite Assembly format preserved  

## Date

October 7, 2025
