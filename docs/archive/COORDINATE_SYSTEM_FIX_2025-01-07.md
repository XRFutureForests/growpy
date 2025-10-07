# Coordinate System Fix - January 7, 2025

## Issue

When opening both the tree_only USD and the assembly USD:

- Tree_only file pointed upward towards +Z (correct Z-up orientation)
- Assembly file pointed towards -Y and was approximately 10x smaller

## Root Cause

The coordinate conversion logic was applying transformations incorrectly:

1. **Grove's USD Export**: The Grove 2.2 exports trees in Y-up coordinates, but the USD file header declares `upAxis = "Z"`
2. **First Conversion**: The extraction code correctly converts Y-up to Z-up when extracting twig placements
3. **Second Conversion (Bug)**: The code then applied ANOTHER coordinate conversion (`convert_to_ue=True`) which:
   - Was intended for Blender-to-UE conversion
   - Had an incorrect formula: `(pos[0], pos[2], -pos[1])` which swapped Y↔Z and negated Y
   - Created a coordinate system mismatch between tree and twigs

## Solution

### 1. Fixed Coordinate Conversion Functions

Updated `convert_blender_to_ue_coords()` and `convert_blender_normal_to_ue()` in `src/growpy/io/twig_placement.py`:

**Before (incorrect):**

```python
# Swap Y and Z, then negate Y for handedness conversion
return (pos[0], pos[2], -pos[1])
```

**After (correct but not used):**

```python
# Swap X and Y, negate new Y for left-handed system
# Blender (X, Y, Z) -> UE (Y, -X, Z)
return (pos[1], -pos[0], pos[2])
```

### 2. Disabled Double Conversion

The key fix was to **NOT** apply the UE conversion when exporting USD assemblies:

- **Tree mesh**: No transformation applied to the tree reference in the assembly
- **Twig instances**: No coordinate conversion applied to positions/orientations extracted from USD

Both tree and twigs now use the same coordinate system (Z-up from Grove's Y-up conversion).

### 3. Code Changes

Modified `_export_with_point_instancer()` and `_export_with_xforms()` in `src/growpy/io/twig_placement.py`:

```python
# NOTE: Coordinate conversion NOT needed here!
# The placements are already extracted from the tree USD which has been
# converted from Grove's Y-up to Z-up. The twigs should match the tree's
# coordinate system exactly. Both tree and twigs are in Z-up Blender coords.
# UE will import Z-up correctly without additional conversion.
```

## Results

### Before Fix

- Assembly tree: Rotated 90° and scaled incorrectly
- Twig positions: `(-0.9997333, 0.016633334, 0.015866667)` - Y↔Z swapped
- Visual: Tree pointing sideways, twigs in wrong locations

### After Fix

- Assembly tree: Same orientation as tree_only (Z-up)
- Twig positions: `(-0.016633334, -0.9997333, 0.015866667)` - Correct Z-up coords
- Visual: Tree and twigs both pointing upward with consistent scale

## Coordinate Systems Reference

### Grove 2.2

- **Coordinate System**: Y-up, Right-handed
- **Export**: Y-up (despite USD header claiming Z-up)

### Blender

- **Coordinate System**: Z-up, Right-handed
- **Used As**: Intermediate format (X right, Y forward, Z up)

### Unreal Engine

- **Coordinate System**: Z-up, Left-handed
- **Convention**: X forward, Y right, Z up

### Conversion Path (Corrected)

1. Grove Y-up → Z-up (via `convert_y_up_to_z_up`)
2. Tree and twigs both exported in Z-up
3. No additional conversion for USD assembly
4. Unreal imports Z-up correctly

## Testing

Regenerated forest with corrected coordinate system:

```bash
conda run -n the-grove python ./src/growpy/cli/generate_forest.py \
    data/input/mini_tree_inventory_32632.csv --formats usda --quality ultra
```

Verified in output USD files:

- Tree_only: Z-up orientation maintained
- Assembly: Tree and twigs in same coordinate system
- Positions: Consistent between tree vertices and twig instances

## Impact

- **Tree USD exports**: Now maintain consistent coordinate systems
- **Unreal Engine imports**: Trees import correctly oriented (Z-up)
- **Twig placement**: Twigs properly aligned with tree branches
- **Scale**: Correct 1:1 scale between tree and assembly

## Related Files

- `src/growpy/io/twig_placement.py`: Coordinate conversion and USD assembly
- `src/growpy/io/blender_export.py`: Tree export functions
- `src/growpy/cli/generate_forest.py`: Forest generation pipeline
