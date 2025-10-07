# Twig Placement Coordinate System Fix

## Problem

Twig instances were being placed along the Y-axis instead of the Z-axis when loading USD files into Blender. This made the twigs appear horizontally oriented rather than vertically along the tree's height.

## Root Cause

Grove's native USD export uses Y-up coordinate system (OpenGL convention), as indicated by `upAxis = "Y"` in the exported USD files. However, Blender and Unreal Engine use Z-up coordinate system.

The twig placement code was extracting positions directly from the Y-up USD file without converting them to Z-up, resulting in:

- **Before**: Position `(-0.016633334, -0.015866667, -0.9997333)` - height in Z (negative)
- **After**: Position `(-0.016633334, 0.9997333, -0.015866667)` - height in Y (positive)

## Solution

Added Y-up to Z-up coordinate transformation functions and applied them when extracting twig placements from Grove USD files.

### Code Changes

**File**: `src/growpy/io/twig_placement.py`

1. **Added coordinate transformation functions** (after line 230):

```python
def convert_y_up_to_z_up(
    pos: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert Y-up (Grove/OpenGL) coordinates to Z-up (Blender/USD standard).
    
    Rotate -90 degrees around X-axis: (x, y, z) -> (x, -z, y)
    """
    return (pos[0], -pos[2], pos[1])

def convert_y_up_normal_to_z_up(
    normal: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Convert Y-up normal vector to Z-up orientation.
    
    Rotate -90 degrees around X-axis: (x, y, z) -> (x, -z, y)
    """
    return (normal[0], -normal[2], normal[1])
```

2. **Applied transformation in `extract_twig_placements_from_usd()`** (around line 520):

```python
# Convert from Y-up (Grove) to Z-up (Blender/USD standard)
# Grove's USD export is in Y-up but we need Z-up for proper orientation
center = convert_y_up_to_z_up(tuple(center))
normal = convert_y_up_normal_to_z_up(tuple(normal))
```

## Coordinate System Details

### Y-up to Z-up Transformation

The transformation rotates the coordinate system -90 degrees around the X-axis:

```
Y-up (Grove):        Z-up (Blender/UE):
  Y                    Z
  |                    |
  |                    |
  +---> X              +---> X
 /                    /
Z                    Y (into screen)

Transformation: (x, y, z) -> (x, -z, y)
```

### Why This Works

- **X-axis**: Remains unchanged (horizontal)
- **Y-axis** (height in Grove) → **Z-axis** (height in Blender/UE)
- **Z-axis** (forward in Grove) → **-Y-axis** (into screen in Blender/UE)

## Testing

Run forest generation and check twig positions:

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda
head -60 data/output/forest/USD/Beech_var1.usda
```

Expected output shows positions with Y as height (positive values ~1.0 to 1.3):

```usd
point3f[] positions = [
    (-0.016633334, 0.9997333, -0.015866667),
    (-0.020966666, 1.0742333, -0.023766667),
    (-0.03266667, 1.1475, -0.0342),
    (-0.0422, 1.2215333, -0.0418),
    (-0.0521, 1.2955667, -0.048533335)
]
```

## Verification in Blender

1. Open Blender
2. File → Import → Universal Scene Description (.usd)
3. Select `data/output/forest/USD/Beech_var1.usda`
4. Verify twigs are positioned along the tree's height (Z-axis in Blender viewport)

## Related Files

- `src/growpy/io/twig_placement.py` - Twig placement extraction and USD creation
- `src/growpy/io/blender_export.py` - Tree export with twig attributes
- `TWIG_PLACEMENT_FIX.md` - Previous fix for twig attribute export

## Technical Notes

- Grove exports USD in Y-up to match its internal coordinate system
- USD standard supports both Y-up and Z-up via `upAxis` metadata
- Transformation must be applied to both positions AND normals
- Quaternion orientations are recalculated from transformed normals
- UE coordinate conversion (`convert_to_ue`) is applied AFTER Y-up to Z-up conversion

## Date

October 7, 2025
