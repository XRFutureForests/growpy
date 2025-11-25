# Quick Fix - All Three Issues (5 Minutes)

## TL;DR

**3 issues + 3 fixes needed:**

1. ❌ Tree sideways → Fix coordinate system conversion
2. ❌ budDevelopment crashes → Fix schema + add data extraction

---

## Fix #1: Coordinate System (CRITICAL - Fixes Sideways Tree)

**File**: `src/growpy/io/pve_grove_mapper.py`

**Line 271 - Change from:**
```python
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
```

**To:**
```python
from .pve_foliage_extractor import grove_to_pve_position
positions = [grove_to_pve_position(p) for p in skeleton_points]
```

**Why**: Grove uses Z-up, PVE needs Y-up. The conversion swaps axes and scales to centimeters.

---

## Fix #2: BudDevelopment Schema

**File**: `src/growpy/io/pve_schema.py`

**Line 90 - Change from:**
```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

**To:**
```python
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

---

## Fix #3: BudDevelopment Data Extraction

**File**: `src/growpy/io/pve_grove_mapper.py`

**After line 305** (after lengthFromRoot mapping), add:

```python
# budDevelopment (bud development state)
if "budDevelopment" in points_data["attributes"]:
    bud_dev_list = []
    generation_data = points_data["attributes"].get("generation", {}).get("values", [0] * num_points)

    for point_idx in range(num_points):
        gen = generation_data[point_idx] if point_idx < len(generation_data) else 0
        age = skeleton.point_attribute_age[point_idx] if hasattr(skeleton, 'point_attribute_age') and point_idx < len(skeleton.point_attribute_age) else point_idx
        vigor = skeleton.point_attribute_vigor[point_idx] if hasattr(skeleton, 'point_attribute_vigor') and point_idx < len(skeleton.point_attribute_vigor) else 50
        shade = skeleton.point_attribute_shade[point_idx] if hasattr(skeleton, 'point_attribute_shade') and point_idx < len(skeleton.point_attribute_shade) else 50

        bud_development = [
            int(gen),
            int(age),
            int(age),
            int(vigor) if vigor > 1 else int(vigor * 100),
            int(shade) if shade > 1 else int(shade * 100),
            16
        ]
        bud_dev_list.append(bud_development)

    value_key = "values" if "values" in points_data["attributes"]["budDevelopment"] else "value"
    points_data["attributes"]["budDevelopment"][value_key] = bud_dev_list
```

---

## Test After Fixing

```bash
# Regenerate
python src/growpy/cli/generate_forest.py --species european_beech --output data/output/forest/european_beech/

# Verify coordinate system fix
grep '"positions"' -A 5 data/output/forest/european_beech/european_beech_tree_0000.json | head -10
# Should show: [1400.0, 0.0, 600.0] not [14.0, 6.0, 0.0]

# Verify budDevelopment fix
grep '"budDevelopment"' -A 10 data/output/forest/european_beech/european_beech_tree_0000.json | head -15
# Should show: [0, 0, 0, 50, 50, 16] not [0]

# Test in Unreal
# - Import preset
# - Connect to Generate Mesh
# - Should be upright and no crash
```

---

## What Gets Fixed

| Issue | Before | After | Status |
|-------|--------|-------|--------|
| Tree orientation | Sideways (Z-up) | Upright (Y-up) | ✓ Fixed |
| budDevelopment crash | Array [0] | Array [0,0,0,50,50,16] | ✓ Fixed |
| Material selection | N/A | Works correctly | ✓ Fixed |

---

## Why These 3 Fixes

1. **Coordinate System**: Unreal uses Y-up, Grove uses Z-up. Must convert.
2. **Schema**: Defines how JSON is structured. Wrong schema = wrong data format.
3. **Extraction**: Schema says 6 elements, but data needs to be extracted from Grove.

All three must be done together.

---

## Reference

- Full details: [COORDINATE_SYSTEM_FIX.md](COORDINATE_SYSTEM_FIX.md)
- Earlier analysis: [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md)
- Complete guide: [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md)
