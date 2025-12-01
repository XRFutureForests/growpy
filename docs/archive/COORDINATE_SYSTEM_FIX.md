# Coordinate System & BudDevelopment Fixes

## Two Issues Found

### Issue #1: Skeleton Sideways - Coordinate System Not Converted
**Symptom**: Tree appears sideways in Unreal Engine
**Root Cause**: Skeleton point positions are copied directly from Grove without converting axis system
**Location**: [pve_grove_mapper.py:271](src/growpy/io/pve_grove_mapper.py#L271)

### Issue #2: BudDevelopment Still Wrong
**Symptom**: Still crashes with `Assertion failed: BudDevelopment.Num() > 2`
**Root Cause**: Schema not updated, budDevelopment still has 1 element instead of 6
**Location**: [pve_schema.py:90](src/growpy/io/pve_schema.py#L90)

---

## Problem #1: Coordinate System Conversion

### Current Code (WRONG)
**File**: `src/growpy/io/pve_grove_mapper.py`, line 271

```python
# Get positions - WRONG: No coordinate conversion!
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
points_data["positions"] = positions
```

This copies Grove coordinates directly without converting the axis system.

### The Conversion Required

Grove uses: **(x, y, z) with Z-up, in meters**
PVE needs: **(x, z, y) with Y-up, in centimeters**

The conversion function already exists in the codebase:

```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.
    Grove uses Z-up meters, PVE uses Y-up centimeters.
    """
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]
```

### The Fix

**File**: `src/growpy/io/pve_grove_mapper.py`, line 271

Change from:
```python
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
```

To:
```python
from .pve_foliage_extractor import grove_to_pve_position

positions = [grove_to_pve_position(p) for p in skeleton_points]
```

This applies the coordinate conversion to all skeleton points.

### Why This Fixes the Sideways Issue

- **Before**: Positions use Grove's Z-up coordinate system → tree grows sideways
- **After**: Positions converted to PVE's Y-up coordinate system → tree grows upright

---

## Problem #2: BudDevelopment Schema & Data

### Current State
- **Schema**: Still defines `size: 1` (should be `6`)
- **Data**: Still fills with `[0]` (should be 6-element arrays)

### Fix Part 1: Update Schema

**File**: `src/growpy/io/pve_schema.py`, line 90

Change from:
```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

To:
```python
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

### Fix Part 2: Extract Bud Development Data

**File**: `src/growpy/io/pve_grove_mapper.py`

**Location**: After line 305 (after lengthFromRoot mapping)

Add this code:

```python
# budDevelopment (bud development state - 6 elements per point)
if "budDevelopment" in points_data["attributes"]:
    bud_dev_list = []

    # Extract generation and age data
    generation_data = points_data["attributes"].get("generation", {}).get("values", [0] * num_points)

    for point_idx in range(num_points):
        # Get generation (branch depth)
        gen = generation_data[point_idx] if point_idx < len(generation_data) else 0

        # Get point age from skeleton if available
        age = skeleton.point_attribute_age[point_idx] if hasattr(skeleton, 'point_attribute_age') and point_idx < len(skeleton.point_attribute_age) else point_idx

        # Get vigor/strength indicator (default to 50%)
        vigor = skeleton.point_attribute_vigor[point_idx] if hasattr(skeleton, 'point_attribute_vigor') and point_idx < len(skeleton.point_attribute_vigor) else 50

        # Get light exposure (default to 50%)
        shade = skeleton.point_attribute_shade[point_idx] if hasattr(skeleton, 'point_attribute_shade') and point_idx < len(skeleton.point_attribute_shade) else 50

        # Construct 6-element budDevelopment array
        # [0] Generation - branch hierarchy depth
        # [1] Age indicator - secondary growth metric
        # [2] Age/Cycle - used by material system
        # [3] Vigor - growth strength (0-100)
        # [4] Light - shade exposure (0-100)
        # [5] Lifespan - max cycles (constant)
        bud_development = [
            int(gen),
            int(age),
            int(age),
            int(vigor) if vigor > 1 else int(vigor * 100),
            int(shade) if shade > 1 else int(shade * 100),
            16  # Standard lifespan from Hazel reference
        ]

        bud_dev_list.append(bud_development)

    value_key = (
        "values"
        if "values" in points_data["attributes"]["budDevelopment"]
        else "value"
    )
    points_data["attributes"]["budDevelopment"][value_key] = bud_dev_list
```

---

## Complete Fix Checklist

### Step 1: Fix Coordinate System (CRITICAL - Fixes Sideways Issue)
- [ ] Open `src/growpy/io/pve_grove_mapper.py`
- [ ] Go to line 271
- [ ] Replace the positions mapping with coordinate conversion
- [ ] Add import for `grove_to_pve_position`

**Code to change:**
```python
# Line 271 - Change this:
positions = [[p[0], p[1], p[2]] for p in skeleton_points]

# To this:
from .pve_foliage_extractor import grove_to_pve_position
positions = [grove_to_pve_position(p) for p in skeleton_points]
```

### Step 2: Fix BudDevelopment Schema
- [ ] Open `src/growpy/io/pve_schema.py`
- [ ] Go to line 90
- [ ] Update budDevelopment definition
- [ ] Change: `isArray: False` → `True`, `size: 1` → `6`, `type: "float"` → `type: "int"`

### Step 3: Add BudDevelopment Extraction
- [ ] Open `src/growpy/io/pve_grove_mapper.py`
- [ ] Find line 305 (after lengthFromRoot)
- [ ] Add the budDevelopment extraction code block (see above)

### Step 4: Regenerate Forest
- [ ] Run: `python src/growpy/cli/generate_forest.py --species european_beech --output data/output/forest/european_beech/`

### Step 5: Validate
- [ ] Check positions are no longer Z-up coordinates
- [ ] Check budDevelopment has 6-element arrays
- [ ] Test in Unreal - tree should be upright, no crash

---

## Expected Results

### Before Fix

**Positions (Z-up Grove coordinates)**:
```json
"positions": [
  [14.0, 6.0, 0.0],
  [13.993, 5.939, 0.998],
  ...
]
```
→ Tree appears sideways in Unreal

**BudDevelopment** (1 element):
```json
"budDevelopment": {
  "values": [[0], [0], ...]
}
```
→ Crashes with assertion error

### After Fix

**Positions (Y-up PVE coordinates, in centimeters)**:
```json
"positions": [
  [1400.0, 0.0, 600.0],
  [1399.3649, 99.81, 593.93],
  ...
]
```
→ Tree upright in Unreal

**BudDevelopment** (6 elements):
```json
"budDevelopment": {
  "values": [
    [0, 0, 0, 50, 50, 16],
    [1, 5, 5, 50, 50, 16],
    [1, 10, 10, 50, 50, 16],
    ...
  ]
}
```
→ No crash, material system works

---

## Why These Fixes Are Needed

### Coordinate System Conversion
Unreal Engine documentation is clear: [Coordinate System and Spaces](https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinate-system-and-spaces-in-unreal-engine)

- **Unreal uses Y-up** (forward/backward axis is X, right/left is Y, up/down is Z in Unreal's convention)
- **Grove uses Z-up** (forward/backward is X, right/left is Y, up/down is Z)
- **PVE plugin expects Y-up centimeters** (as shown in Hazel reference)

Without conversion, coordinates are interpreted incorrectly, causing sideways trees.

### BudDevelopment Extraction
The PVE material system uses budDevelopment to determine:
- Which materials to apply (based on generation)
- How to blend materials (based on age)

Without proper data, it crashes when trying to access indices [0] and [2].

---

## Technical Details

### Coordinate Transformation Math

Grove (Z-up): (x, y, z) in meters
↓
PVE (Y-up): (x, z*100, y*100) in centimeters

**Visual explanation:**
- X-axis stays the same (forward)
- Y and Z swap (right becomes up)
- All values multiply by 100 (meters to centimeters)

**Example:**
```
Grove: (14.0, 6.0, 0.0)  // x=14m, y=6m (right), z=0m (up)
↓ Transform
PVE:   (1400.0, 0.0, 600.0)  // x=1400cm, z=0cm (up), y=600cm (right)
```

### Why the Conversion Works

The `grove_to_pve_position()` function was already written for foliage extraction but wasn't being used for skeleton points. By applying it consistently to all point positions, the coordinate system issue is resolved.

---

## Files to Modify Summary

| File | Line | Change | Type |
|------|------|--------|------|
| `src/growpy/io/pve_grove_mapper.py` | 271 | Coordinate conversion | Critical fix |
| `src/growpy/io/pve_schema.py` | 90 | Schema update | Schema fix |
| `src/growpy/io/pve_grove_mapper.py` | 305+ | Add extraction | Data fix |

**Total changes**: ~30 lines across 2 files

---

## Verification Commands

After making changes:

```bash
# Regenerate forest
python src/growpy/cli/generate_forest.py --species european_beech --output data/output/forest/european_beech/

# Check positions are converted (Y-up, centimeters)
grep '"positions"' -A 10 data/output/forest/european_beech/european_beech_tree_0000.json | head -15

# Check budDevelopment has 6 elements
grep '"budDevelopment"' -A 15 data/output/forest/european_beech/european_beech_tree_0000.json | head -20
```

Expected outputs:
- Positions: Numbers in hundreds (1400.0 instead of 14.0)
- BudDevelopment: Arrays with 6 integers: `[0, 0, 0, 50, 50, 16]`

---

## Next Steps

1. Apply coordinate system fix (line 271)
2. Apply schema fix (line 90, pve_schema.py)
3. Apply data extraction fix (after line 305, pve_grove_mapper.py)
4. Regenerate forest
5. Verify JSON structure
6. Test in Unreal Engine

All three fixes are needed to fully resolve the issues.
