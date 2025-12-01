# PVE Plugin Crash Analysis - Complete Summary

## Overview

You've encountered **two crash issues** when using the beech JSON preset in the Unreal Engine Procedural Vegetation Editor plugin:

1. **First Crash (FIXED)**: JSON key format mismatch
2. **Second Crash (NEEDS FIX)**: Missing budDevelopment data

---

## Crash #1: JSON Key Format (STATUS: FIXED ✓)

### Error
```
Failed to find field: GetArrayField("values")
```

### Root Cause
Primitives attributes used `"value"` instead of `"values"` key for array data.

### Solution Applied
Your forest generation script was updated to correctly use `"values"` for:
- `instancer_name`
- `instancer_pivot`
- `instancer_UP`
- `instancer_scale`
- `instancer_LFR`

### Verification
```bash
grep '"instancer_name"' -A 4 data/output/forest/european_beech/european_beech_tree_0000.json
# Should show: "values": [
```

✓ Verified in new beech JSON - All primitives now use `"values"` key

---

## Crash #2: BudDevelopment Array Size (STATUS: NEEDS FIX)

### Error
```
Assertion failed: BudDevelopment.Num() > 2
[File: PVMaterialSettings.cpp]
[Line: 71]
```

### Root Cause
The `budDevelopment` arrays in the JSON contain only **1 element** (`[0]`), but the PVE plugin requires **at least 3 elements** to access indices 0 and 2.

**Why this happens:**
- Schema defines `size: 1` (should be `size: 6`)
- No code extracts actual bud development data from Grove simulation
- Default zero-filling creates `[0]` arrays

### Current vs. Expected

**Current (CRASHES):**
```json
"budDevelopment": {
  "values": [
    [0],        // ❌ Only 1 element
    [0],
    [0],
    ...
  ]
}
```

**Expected (WORKS):**
```json
"budDevelopment": {
  "values": [
    [0, 0, 0, 50, 50, 16],     // ✓ 6 elements (like Hazel)
    [1, 5, 5, 75, 60, 16],
    [2, 10, 10, 90, 70, 16],
    ...
  ]
}
```

### Why PVE Plugin Needs This Data

[PVMaterialSettings.cpp:66-79](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L66-L79):

```cpp
for (int32 PointIndex = 0; PointIndex < PointFacade.GetElementCount(); PointIndex++) {
    TArray<int> BudDevelopment = PointFacade.GetBudDevelopment(PointIndex);
    check(BudDevelopment.Num() > 2);  // CRASHES HERE

    MinGeneration = FMath::Min(MinGeneration, BudDevelopment[0]);  // Generation
    MinAge = FMath::Min(MinAge, BudDevelopment[2]);                // Age
    // ... material selection based on generation and age
}
```

The material system uses:
- **BudDevelopment[0]** - Generation (branch hierarchy depth)
- **BudDevelopment[2]** - Age (growth cycle/stage)

To determine which material/texture to apply to branches.

### What Each Element Represents

Based on code analysis and Hazel reference:

| Index | Field | Purpose | Example |
|-------|-------|---------|---------|
| 0 | Generation | Branch depth (0=trunk, 1=primary, 2=secondary) | 0-10 |
| 1 | Age indicator | Secondary growth metric | 0-20 |
| 2 | Age/Cycle | Material system uses for blending | 0-20 |
| 3 | Vigor/Mass | Growth strength indicator | 0-100 |
| 4 | Light exposure | Shade level for shading decisions | 0-100 |
| 5 | Max lifespan | Bud lifespan in cycles | 16 |

---

## Solution: Three-Part Fix

### Part 1: Update Schema Definition

**File**: `src/growpy/io/pve_schema.py:90`

```python
# BEFORE
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},

# AFTER
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

### Part 2: Extract Bud Development from Grove

**File**: `src/growpy/io/pve_grove_mapper.py` (in `_map_points_from_skeleton()` function)

Add extraction logic after line 360:

```python
elif attr_name == "budDevelopment":
    bud_dev_list = []

    for point_idx in range(num_points):
        # Extract metrics from Grove simulation data
        generation = points_data["attributes"].get("generation", {}).get("values", [0])[point_idx]
        point_age = skeleton.point_attribute_age[point_idx] if hasattr(skeleton, 'point_attribute_age') else 0
        vigor = skeleton.point_attribute_vigor[point_idx] if hasattr(skeleton, 'point_attribute_vigor') else 50
        shade = skeleton.point_attribute_shade[point_idx] if hasattr(skeleton, 'point_attribute_shade') else 50

        # Create 6-element budDevelopment array
        bud_development = [
            int(generation),           # [0] Generation
            int(point_age),           # [1] Age indicator
            int(point_age),           # [2] Age (material uses this)
            int(vigor * 100) if vigor < 1 else int(vigor),  # [3] Vigor
            int(shade * 100) if shade < 1 else int(shade),  # [4] Light exposure
            16                        # [5] Max lifespan
        ]

        bud_dev_list.append(bud_development)

    points_data["attributes"][attr_name]["values"] = bud_dev_list
```

### Part 3: Verify Point Attributes Are Extracted

Ensure skeleton has the necessary attributes. Around line 280 in `_map_points_from_skeleton()`:

```python
# After skeleton is built, extract full attribute set
if hasattr(skeleton, 'point_attribute_age'):
    # Good - attributes are available
else:
    # May need to add attribute extraction to skeleton building
    pass
```

---

## Implementation Checklist

- [ ] **Schema Update**
  - [ ] Open `src/growpy/io/pve_schema.py`
  - [ ] Find line 90 with `"budDevelopment"`
  - [ ] Change `isArray: False` to `True`
  - [ ] Change `size: 1` to `size: 6`
  - [ ] Change `type: "float"` to `type: "int"`
  - [ ] Save file

- [ ] **Code Addition**
  - [ ] Open `src/growpy/io/pve_grove_mapper.py`
  - [ ] Find `_map_points_from_skeleton()` function
  - [ ] Locate lengthFromRoot mapping (around line 337)
  - [ ] Add budDevelopment extraction after plantGradient (line 360)
  - [ ] Implement 6-element array construction
  - [ ] Save file

- [ ] **Testing**
  - [ ] Re-run forest generation
  - [ ] Verify JSON has 6-element budDevelopment arrays
  - [ ] Import preset in Unreal
  - [ ] Connect to Generate Mesh node
  - [ ] Check if crash is resolved

---

## Detailed Comparison: Crash #1 vs Crash #2

| Aspect | Crash #1: Key Format | Crash #2: Array Size |
|--------|---------------------|----------------------|
| **Symptom** | JSON parsing fails | Assertion in material application |
| **When it happens** | During preset import | When connecting to generate mesh |
| **Root cause** | Wrong key name in JSON | Missing data in JSON |
| **Fix location** | Forest generation script | GrowPy mapper + schema |
| **Fix type** | Bug in generation | Data extraction logic |
| **Status** | ✓ Fixed | ⚠ Needs fix |
| **Impact** | Plugin can't load JSON | Plugin loads but crashes during rendering |

---

## Data Flow with Fix

```
Grove Tree Simulation
    ↓
Skeleton Extraction (with attributes)
    ↓
Point Attribute Mapping
    ├─ generation → budDevelopment[0]
    ├─ age → budDevelopment[1,2]
    ├─ vigor → budDevelopment[3]
    ├─ shade → budDevelopment[4]
    └─ constant → budDevelopment[5]
    ↓
6-Element budDevelopment Arrays ✓
    ↓
JSON Export (values: [[...], [...], ...])
    ↓
Unreal PVE Plugin
    ├─ Loads JSON ✓
    ├─ Reads budDevelopment ✓
    ├─ Accesses [0] and [2] ✓
    ├─ Applies materials ✓
    └─ Generates mesh ✓
```

---

## References & Documentation

### Code References
- **Schema definition**: [pve_schema.py:90](src/growpy/io/pve_schema.py#L90)
- **Data mapping**: [pve_grove_mapper.py:360](src/growpy/io/pve_grove_mapper.py#L360)
- **Crash location**: [PVMaterialSettings.cpp:71](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L71)

### Analysis Documents
- [BUDDEVELOPMENT_ROOT_CAUSE.md](BUDDEVELOPMENT_ROOT_CAUSE.md) - Detailed root cause analysis
- [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md) - Complete implementation guide
- [BUDEVELOPMENT_CRASH_ANALYSIS.md](BUDEVELOPMENT_CRASH_ANALYSIS.md) - Technical crash details
- [JSON_CRASH_ANALYSIS.md](JSON_CRASH_ANALYSIS.md) - First crash analysis (fixed)
- [BEECH_JSON_VALIDATION_REPORT.md](BEECH_JSON_VALIDATION_REPORT.md) - Current JSON structure validation

### Reference Assets
- **Hazel reference**: [Broadleaf_Hazel_04.json](data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json)
- **Generated beech**: [european_beech_tree_0000.json](data/output/forest/european_beech/european_beech_tree_0000.json)

---

## Next Steps

1. **Implement the 3-part fix** (schema + extraction logic)
2. **Test with new forest generation**
3. **Validate JSON structure** (6 elements per budDevelopment)
4. **Test in Unreal Engine** (import → generate mesh)
5. **Iterate on data accuracy** if material output isn't correct

The fix is straightforward - primarily a schema definition change plus adding data extraction logic where lengthFromRoot is already handled.
