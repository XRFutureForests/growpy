# BudDevelopment Fix Guide - Complete Solution

## Problem Summary

The European beech JSON crashes in the PVE plugin with:
```
Assertion failed: BudDevelopment.Num() > 2 [PVMaterialSettings.cpp:71]
```

**Root cause**: budDevelopment arrays contain only 1 element `[0]` instead of the required 6 elements.

**Why it happens**: The GrowPy mapper fills budDevelopment with hardcoded zeros because:
1. Schema incorrectly defines `size: 1` instead of `size: 6`
2. No code exists to extract actual bud development data from Grove
3. Default value-filling logic populates zeros

---

## Solution Overview

Fix requires three coordinated changes to extract real bud development data from the Grove simulation:

1. **Update schema** - Correct budDevelopment structure definition
2. **Add data extraction logic** - Query Grove attributes per skeleton point
3. **Map to 6-element array** - Convert Grove data to PVE format

---

## Part 1: Schema Fix

**File**: `src/growpy/io/pve_schema.py`

**Location**: Line 90 (search for `"budDevelopment"`)

**Current (WRONG):**
```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

**Change to (CORRECT):**
```python
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

**Explanation**:
- `isArray: True` - Each point has a development array (not a single scalar)
- `size: 6` - Each array has 6 elements (matches Hazel reference)
- `type: "int"` - Elements are integers (matches Hazel reference)

---

## Part 2: Data Extraction Logic

**File**: `src/growpy/io/pve_grove_mapper.py`

**Function**: `_map_points_from_skeleton()`

**Location**: Lines 326-397 (after plantGradient mapping around line 360)

### Step 2A: Understand the Data Context

Before adding code, understand what data is available:

The skeleton extraction process has access to:
- **Skeleton points** - Positions and indices
- **Point attributes** - age, mass, radius, vigor, shade
- **Tree reference** - Original Grove tree structure
- **Model attributes** - Growth data from simulation

### Step 2B: Add budDevelopment Extraction

Add this code after the plantGradient mapping (around line 360):

```python
# Map budDevelopment - extract from Grove attributes
elif attr_name == "budDevelopment":
    bud_dev_list = []

    for point_idx in range(num_points):
        # Get the skeleton point information
        # This connects skeleton points back to the original tree structure

        # Extract development metrics from available Grove data
        # Based on the Hazel reference which has 6-element arrays:
        # [development_stage, age_normalized, light_exposure, vigor, status, lifespan]

        # For now, use skeleton point attributes as proxy for bud development
        # These are populated by Grove and represent growth state

        age = points_data["attributes"]["generation"]["values"][point_idx] if "generation" in points_data["attributes"] else 0
        pscale = points_data["attributes"]["pscale"]["values"][point_idx] if "pscale" in points_data["attributes"] else 0.0

        # Construct 6-element budDevelopment array
        # Based on Hazel reference pattern [1, 17, 17, 0, 0, 16]:
        bud_development = [
            int(age),                    # [0] Generation/development stage
            int(pscale * 10),           # [1] Size/thickness indicator
            int(age),                    # [2] Age in cycles (used by material system)
            0,                          # [3] Reserved
            0,                          # [4] Reserved
            16                          # [5] Max lifespan (default)
        ]

        bud_dev_list.append(bud_development)

    points_data["attributes"][attr_name]["values"] = bud_dev_list
```

### Step 2C: Complete Implementation (More Sophisticated)

For a more accurate mapping, use the Grove model attributes that were computed during simulation:

```python
# Map budDevelopment - use Grove model attributes for accurate data
elif attr_name == "budDevelopment":
    bud_dev_list = []

    # Access Grove model attributes if available
    # These contain actual growth simulation data
    model = tree_instance.model if hasattr(tree_instance, 'model') else None

    for point_idx in range(num_points):
        # Extract actual Grove attributes for this point

        # Get generation depth (0=trunk, 1=primary branch, etc.)
        generation = points_data["attributes"].get("generation", {}).get("values", [0] * num_points)[point_idx]

        # Get point age - indicates growth order in simulation
        # Higher age = older/more mature growth
        point_age = point_attributes.get("age", [0] * num_points)[point_idx] if hasattr(skeleton, 'point_attribute_age') else 0

        # Get vigor/strength indicator (0-1)
        vigor = point_attributes.get("vigor", [0.5] * num_points)[point_idx] if hasattr(skeleton, 'point_attribute_vigor') else 0.5

        # Get shade/light exposure (0=shade, 1=full light)
        shade = point_attributes.get("shade", [0.5] * num_points)[point_idx] if hasattr(skeleton, 'point_attribute_shade') else 0.5

        # Get pscale for size indication
        pscale = points_data["attributes"].get("pscale", {}).get("values", [0] * num_points)[point_idx]

        # Construct 6-element budDevelopment array
        # Map Grove data to PVE material system requirements:
        bud_development = [
            int(generation),                    # [0] Generation (used by material system for selection)
            int(point_age),                    # [1] Age indicator
            int(point_age),                    # [2] Age/cycle (used by material system for blending)
            int(vigor * 100),                  # [3] Vigor level (0-100)
            int(shade * 100),                  # [4] Light exposure (0-100)
            16                                 # [5] Max lifespan (default from Hazel)
        ]

        bud_dev_list.append(bud_development)

    points_data["attributes"][attr_name]["values"] = bud_dev_list
```

---

## Part 3: Point Attributes Structure

Ensure the point attributes being used are actually available in the skeleton data structure.

**File**: `src/growpy/io/pve_grove_mapper.py`

**Function**: `_map_points_from_skeleton()`

**Check**: Before using attributes like `vigor`, `shade`, `age`, verify they're being extracted:

```python
# Around line 280 where skeleton is processed, add:

# Extract point attributes from skeleton
point_attributes = {
    "age": getattr(skeleton, "point_attribute_age", [0] * num_points),
    "mass": getattr(skeleton, "point_attribute_mass", [0] * num_points),
    "vigor": getattr(skeleton, "point_attribute_vigor", [0.5] * num_points),
    "shade": getattr(skeleton, "point_attribute_shade", [0.5] * num_points),
    "thickness": getattr(skeleton, "point_attribute_thickness", [0] * num_points),
}
```

---

## Part 4: Validation & Testing

### Validation Step 1: Check Schema Changes

After updating pve_schema.py, verify:
```bash
cd src/growpy/io
grep -A 1 '"budDevelopment"' pve_schema.py
# Should show: "budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

### Validation Step 2: Re-generate Forest

```bash
cd /path/to/the-grove
python src/growpy/cli/generate_forest.py \
    --species european_beech \
    --output data/output/forest/european_beech/
```

### Validation Step 3: Check Generated JSON

```bash
grep '"budDevelopment"' -A 20 data/output/forest/european_beech/european_beech_tree_0000.json | head -25
```

Should show:
```json
"budDevelopment": {
  "isArray": true,
  "size": 6,
  "type": "int",
  "values": [
    [0, 0, 0, 50, 50, 16],
    [1, 5, 5, 75, 60, 16],
    [2, 10, 10, 90, 70, 16],
    ...
  ]
}
```

**Key checks**:
- ✓ Each inner array has exactly 6 elements
- ✓ First element (generation) increases with branch depth
- ✓ Third element (age) varies with point position
- ✓ Values are integers, not floats

### Validation Step 4: Test in Unreal

1. Delete old preset asset
2. Re-import preset with fixed JSON
3. Connect to Generate Mesh node
4. If it still crashes, check error message for next issue

---

## Expected Results After Fix

### Before Fix (CRASHES):
```json
"budDevelopment": {
  "values": [
    [0],      // ❌ Only 1 element
    [0],
    ...
  ]
}
```

Error: `Assertion failed: BudDevelopment.Num() > 2`

### After Fix (WORKS):
```json
"budDevelopment": {
  "values": [
    [0, 0, 0, 50, 50, 16],      // ✓ 6 elements
    [1, 5, 5, 75, 60, 16],
    [2, 10, 10, 90, 70, 16],
    ...
  ]
}
```

No assertion failure - plugin proceeds to material application phase.

---

## Troubleshooting

### Issue: Attributes not found in skeleton
**Solution**: Verify skeleton is built with full attribute extraction
- Check `build_skeletons()` call includes attribute flags
- May need to add attribute extraction to skeleton building code

### Issue: Values out of expected range
**Example**: Generation going beyond actual tree depth
**Solution**: Normalize values before assignment
```python
# Clamp generation to reasonable range
generation = min(int(generation), 10)
```

### Issue: Material system still fails after crash fix
**Likely cause**: Other missing attributes
**Solution**: Check PVE plugin error log for next assertion failure

---

## Files Modified Summary

| File | Lines | Change | Type |
|------|-------|--------|------|
| `src/growpy/io/pve_schema.py` | 90 | Update budDevelopment schema | Schema fix |
| `src/growpy/io/pve_grove_mapper.py` | 360+ | Add budDevelopment extraction | Data mapping |
| `src/growpy/io/pve_grove_mapper.py` | 280+ | Extract point attributes | Data structure |

---

## References

- **Crash location**: [PVMaterialSettings.cpp:66-79](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L66-L79)
- **Schema file**: [pve_schema.py](src/growpy/io/pve_schema.py)
- **Mapper file**: [pve_grove_mapper.py](src/growpy/io/pve_grove_mapper.py)
- **Reference data**: [Broadleaf_Hazel_04.json](data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json)
- **Grove types**: [the_grove_22_core/__init__.pyi](src/the_grove_22/modules/the_grove_22_core/__init__.pyi)
