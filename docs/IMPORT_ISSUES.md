# Import Issues and Solutions

This document addresses common issues when importing Grove-generated tree models into different 3D software.

## Issue 1: Y-Axis Coordinate Flipping in Blender

### Problem

When importing USD or FBX files into Blender, the Y-axis coordinates appear flipped (negative Y becomes positive Y and vice versa). This happens because:

- **Grove/USD**: Uses standard right-hand coordinate system (Y forward, Z up)
- **Blender**: Uses right-hand coordinate system with Z up, but different Y orientation

### Solution Options

#### Option A: Fix in Blender (Recommended)

1. After importing the trees, select all tree objects
2. Scale Y-axis by -1: Press `S` → `Y` → `-1` → `Enter`
3. Or use Python script in Blender:

   ```python
   import bpy
   for obj in bpy.context.selected_objects:
       obj.scale.y *= -1
   ```

#### Option B: Fix in Export (Code Change)

Modify the `_create_tree_position` function in `simulation.py` to flip Y coordinates:

```python
def _create_tree_position(tree_row: pd.Series) -> TreePosition:
    """Create a 3D position vector from CSV row data."""
    return gc.Vector(float(tree_row.x), -float(tree_row.y), float(tree_row.z))
```

**Note**: Option A is recommended because it preserves coordinate system consistency with other 3D software that uses the same coordinate system as Grove.

## Issue 2: Tree Size Discrepancy Between Species

### Problem

Coniferous trees (Fir, Scots pine) appear smaller than deciduous trees (Beech, Oak) despite having larger heights in the CSV file.

### Root Cause Analysis

The original delay system had a fundamental design flaw:

1. **Original logic**: Higher predicted age → Less delay → More growth time → Even taller trees
2. **Problem**: This made tall trees taller and short trees shorter (opposite of intended goal)
3. **Intent**: All trees should finish at their CSV heights simultaneously

### Fixed Delay System Logic

The delay calculation now properly considers **species growth speed relative to target height**:

1. **Height curves** determine how fast each species grows (flushes needed to reach height)
2. **Growth speed calculation**: For each tree, determine flushes needed to reach its CSV height
3. **Proper delays**:
   - **Fast growers** reaching **low targets** = **LONG delay** (would overgrow without delay)
   - **Slow growers** reaching **high targets** = **SHORT delay** (need maximum time)

### Example

- **Beech tree** (fast grower) targeting **30m** = needs only 20 flushes → gets 55 flush delay
- **Fir tree** (slow grower) targeting **45m** = needs 70 flushes → gets 5 flush delay
- Both finish growing at cycle 75 with correct heights

### Performance vs. Accuracy Trade-off

- **To reduce simulation time**: Lower `height_model_flushes` (affects height curve accuracy)
- **Keep `age_to_flush_ratio = 1.0`** for proper delay calculations

```ini
[simulation]
# Reduce this to speed up simulation (affects height curve accuracy)
height_model_flushes = 75

# Keep this at 1.0 for correct delay calculations  
age_to_flush_ratio = 1.0
```

## Prevention

### For Future Projects

1. **Test imports early**: Always test a small subset first
2. **Coordinate system awareness**: Know your target software's coordinate system
3. **Age ratio tuning**: Start with smaller `age_to_flush_ratio` values (0.5-1.0)
4. **Height validation**: Check that exported tree sizes match expected heights

### Recommended Workflow

1. Generate models with conservative settings
2. Import a test tree into target software
3. Verify positioning and scaling
4. Adjust settings if needed
5. Regenerate full forest

## Additional Notes

- Unity and Unreal Engine typically use the same coordinate system as USD/Grove
- The coordinate flip issue is specific to Blender's import behavior
- FBX files may have additional coordinate system transformations depending on export settings
