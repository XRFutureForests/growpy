# BudDevelopment Missing Data - Root Cause & Solution

## Executive Summary

The beech JSON crash occurs because **budDevelopment arrays contain only 1 element** (`[0]`) when the PVE plugin requires **at least 3 elements** (`[gen, ?, age, ?, ?, ?]`).

Root cause: The GrowPy forest generation pipeline is populating budDevelopment with **hardcoded zeros** instead of extracting actual growth data from the Grove tree simulation.

---

## The Problem in Detail

### Crash Signature
```
Assertion failed: BudDevelopment.Num() > 2
PVMaterialSettings.cpp:71
```

### What's Required
[PVMaterialSettings.cpp:66-79](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L66-L79) needs to access:

```cpp
TArray<int> BudDevelopment = PointFacade.GetBudDevelopment(PointIndex);
check(BudDevelopment.Num() > 2);  // CRASHES - Array has only 1 element!
MinGeneration = FMath::Min(MinGeneration, BudDevelopment[0]);  // Generation
MinAge = FMath::Min(MinAge, BudDevelopment[2]);                // Age
```

### What's Currently in Beech JSON
```json
"budDevelopment": {
  "values": [
    [0],     // ❌ Only 1 element (needs 3+)
    [0],
    [0],
    ...
  ]
}
```

### What's Expected (Hazel Reference)
```json
"budDevelopment": {
  "values": [
    [1, 17, 17, 0, 0, 16],    // ✓ 6 elements
    [1, 17, 17, 0, 0, 16],
    ...
  ]
}
```

---

## Data Flow Analysis

### Current GrowPy Pipeline

**File: [pve_grove_mapper.py](src/growpy/io/pve_grove_mapper.py)**

**Location: Line 363-374 (Default population logic)**

```python
if attr_data.get("isArray", False):
    # Array attributes with size>1: variable-length arrays of size-element groups
    attr_size = attr_data.get("size", 1)
    if attr_data.get("type") == "int":
        points_data["attributes"][attr_name][value_key] = [
            [0] * attr_size for _ in range(num_points)  # ❌ Fills with zeros!
        ]
```

This code **fills budDevelopment with zeros** because:
1. The schema defines `size: 1` (should be `size: 6`)
2. There's no Grove API call to extract actual bud development data
3. It falls through to the default zero-filling logic

### Schema Definition

**File: [pve_schema.py](src/growpy/io/pve_schema.py:90)**

```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

Issues:
- `"isArray": False` - Should be `True` for per-point arrays
- `"size": 1` - Should be `6` to match Hazel reference
- `"type": "float"` - Should be `"int"`

### Comparison with Working Attributes

**Attributes correctly populated:**
- `lengthFromRoot` - Extracted from skeleton (lines 337-345)
- `plantGradient` - Extracted from skeleton (lines 346-360)

These have explicit mappings in the code because they're available from the Grove skeleton.

**Attributes with missing extraction:**
- `budDevelopment` - No Grove API call to get this data
- Other attributes - Filled with defaults

---

## Solution Approach

### Step 1: Fix Schema Definition

**File: [pve_schema.py](src/growpy/io/pve_schema.py)**

Change:
```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

To:
```python
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

### Step 2: Extract Grove Growth Data

**File: [pve_grove_mapper.py](src/growpy/io/pve_grove_mapper.py)**

In the `_map_points_from_skeleton()` function, add explicit extraction logic for budDevelopment:

**Location: After line 360 (after plantGradient mapping)**

Need to:
1. Query Grove API for bud development state at each skeleton point
2. Extract 6-value array: `[generation, ?, age, ?, ?, ?]`
3. Map to PVE format

Example structure (need to verify actual Grove API):
```python
# After plantGradient mapping, around line 360
elif attr_name == "budDevelopment":
    # Extract bud development from Grove tree nodes
    bud_dev_list = []
    for point in skeleton_points:
        # Query Grove for bud state (generation, age, etc.)
        bud_generation = point.generation  # or similar Grove API
        bud_age = point.age                # or similar
        bud_dev_list.append([bud_generation, 0, bud_age, 0, 0, 0])

    points_data["attributes"][attr_name]["values"] = bud_dev_list
```

### Step 3: Understand Grove Bud Development Structure

Need to investigate:
1. How Grove represents bud development internally
2. What the 6 elements in budDevelopment array represent
3. How to extract these from the simulated tree

**Key questions:**
- Does Grove track generation number per bud?
- Does Grove track age/cycle per bud?
- What do indices [1], [3], [4], [5] represent in budDevelopment[6]?

---

## Data Element Reference

Based on PVMaterialSettings.cpp code usage:

| Index | Field Name | Usage | Value Range |
|-------|-----------|-------|-------------|
| 0 | Generation | Material ID selection | 0-N (tree depth) |
| 1 | Unknown1 | Not accessed in crash path | Unknown |
| 2 | Age/Cycle | Material blend/selection | 0-N (growth cycles) |
| 3 | Unknown3 | Not accessed in crash path | Unknown |
| 4 | Unknown4 | Not accessed in crash path | Unknown |
| 5 | Unknown5 | Not accessed in crash path | Unknown |

Hazel reference shows values like: `[1, 17, 17, 0, 0, 16]`

---

## Files Requiring Changes

1. **[src/growpy/io/pve_schema.py](src/growpy/io/pve_schema.py:90)**
   - Fix budDevelopment schema definition
   - Change size from 1 to 6
   - Change isArray from False to True
   - Change type from "float" to "int"

2. **[src/growpy/io/pve_grove_mapper.py](src/growpy/io/pve_grove_mapper.py:337-374)**
   - Add budDevelopment extraction logic similar to lengthFromRoot/plantGradient
   - Query Grove API for bud development per skeleton point
   - Populate with 6-element arrays instead of default zeros

3. **[src/growpy/cli/generate_forest.py](src/growpy/cli/generate_forest.py)**
   - May need to ensure Grove simulation exports necessary data
   - Verify tree instance has access to bud development states

---

## Verification Checklist

- [ ] Schema updated: budDevelopment `size: 6`, `isArray: True`, `type: "int"`
- [ ] Grove API investigated: How to query bud generation/age per point
- [ ] Extraction logic added: budDevelopment populated with actual values
- [ ] Test JSON validates: budDevelopment arrays have 6 elements each
- [ ] Hazel comparison: Values match expected ranges
- [ ] PVE import test: Preset imports without crashes
- [ ] Generate mesh test: Mesh generation completes without budDevelopment assertion

---

## References

- **Crash**: [PVMaterialSettings.cpp:71](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L71)
- **Schema**: [pve_schema.py:90](src/growpy/io/pve_schema.py#L90)
- **Population logic**: [pve_grove_mapper.py:363-374](src/growpy/io/pve_grove_mapper.py#L363-L374)
- **Reference data**: [Broadleaf_Hazel_04.json](data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json)
