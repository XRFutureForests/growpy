# PVE JSON Issues Analysis and Fixes

**Date:** 2026-01-09
**Analysis:** Comparison between working Hazel reference JSON and generated European Beech JSON

## Executive Summary

Generated JSON files are **missing critical bud-related data** that causes:

1. **Slope Node Distortion**: All `budDirection` vectors are zeros, causing vertices to move incorrectly
2. **Mesh Builder Crashes**: Missing or incorrect LOD gradients and bud metadata

## Critical Issues Found

### 1. budDirection - CRITICAL (Causes Slope Node Failure)

**Issue:**

- **Reference (Hazel)**: All 1371 points have non-zero 3D direction vectors
  - Example: `[0.0, 1.0, 0.0, 0.9451, 0.0072, -0.3267, ...]` (18 floats per point = 6 buds x 3D vector)
- **Generated (Beech)**: All 3825 points have ZERO vectors
  - Example: `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ...]`

**Root Cause:**

- File: `src/growpy/io/pve_grove_mapper.py` lines 460-466
- Code initializes budDirection with zeros but never populates with actual bud data from Grove

**Impact:**

- Slope node uses budDirection to determine branch growth orientation
- Without proper vectors, slope transformations apply incorrectly to vertices
- Results in visual distortion with some vertices moving while others don't

**Fix Required:**
Extract actual bud direction vectors from Grove API and populate the budDirection array

---

### 2. budNumber - WARNING

**Issue:**

- **Reference (Hazel)**: Sequential bud IDs starting from 1
  - Values: `1, 2, 3, 4, ...`
- **Generated (Beech)**: All zeros
  - Values: `0, 0, 0, 0, ...`

**Root Cause:**

- Same as budDirection - not extracted from Grove

**Impact:**

- May affect bud identification in PVE nodes
- Could contribute to mesh builder issues

**Fix Required:**
Assign unique sequential IDs to each point/bud

---

### 3. budStatus - WARNING

**Issue:**

- **Reference (Hazel)**: Status arrays with meaningful values
  - Example: `[0, 0, 1, 1, 1, 0, 0, 0, 0, 0]` (10 status flags per point)
- **Generated (Beech)**: All zeros
  - Example: `[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]`

**Root Cause:**

- Not extracted from Grove simulation

**Impact:**

- Bud state information missing (active/dormant/etc)
- May affect how PVE nodes process the tree

**Fix Required:**
Extract bud status from Grove and map to PVE status flags

---

### 4. budHormoneLevels - WARNING

**Issue:**

- **Reference (Hazel)**: Hormone level data
  - Example: `[1.0, 0.1853, 0.0, 0.0, 0.4304, 0.0]` (6 values per point)
- **Generated (Beech)**: All zeros
  - Example: `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]`

**Root Cause:**

- Not extracted from Grove

**Impact:**

- Missing auxin/cytokinin hormone data
- May affect parametric regrowth in PVE

**Fix Required:**
Extract hormone levels from Grove simulation state

---

### 5. budDevelopment - PARTIAL

**Issue:**

- **Reference (Hazel)**: Development stage data
  - Example: `[1, 17, 17, 0, 0, 16]` (generation, cycle, age, 0, 0, max_age)
- **Generated (Beech)**: Has values but potentially incorrect
  - Example: `[0, 7, 7, 0, 0, 7]`

**Impact:**

- Development stage data exists but may not match actual simulation state

**Status:**
Needs validation - currently populated with simulation cycle data

---

### 6. parents Array - CRITICAL (Causes Hierarchy Traversal Failure)

**Issue:**

- **Reference (Hazel)**: `parents` array contains valid branch numbers as ancestry chain
  - Trunk: `[]` (empty - has no parent)
  - Child branches: `[1]` (parent is branch number 1 = trunk)
- **Generated (Beech)**: `parents` array contains invalid branch number 0
  - Trunk: `[0]` (WRONG - 0 is not a valid branch number!)
  - Child branches: `[1, 0]` (ends with invalid 0)

**Root Cause:**
Code was incorrectly using branch index (0-based) instead of branch number (1-based) in the `parents` array.

**Impact:**

- `GetParentBranchIndex()` in PVE uses `Parents[BranchIndex].Last()` to find parent branch number
- It then calls `BranchNumbers.Find(ParentBranchNumber)` to convert to index
- If parent number is 0 but branch numbers are `[1, 2, 3, ...]`, `Find(0)` returns `INDEX_NONE`
- Result: All parent lookups fail, hierarchy traversal breaks completely
- Slope/Gravity nodes can't find children because `GetParentIndex()` returns invalid results

**Relevant PVE Code:**

```cpp
// PVBranchFacade.cpp - GetParentBranchIndex()
int32 FBranchFacade::GetParentBranchIndex(const int32 BranchIndex) const {
    if (TArray<int32> ParentsBranchNumbers = Parents[BranchIndex];
        ParentsBranchNumbers.Num() > 0) {
        const int32 ParentBranchNumber = ParentsBranchNumbers.Last();
        return BranchNumbers.Get().Find(ParentBranchNumber);  // Returns INDEX_NONE if 0!
    }
    return INDEX_NONE;
}
```

**Fix Required:**

- Trunk `parents` array must be empty: `[]`
- Child branch `parents` array must contain only valid branch numbers (1-based)
- Example: If trunk is branch number 1, children should have `parents: [1]`, not `parents: [1, 0]`

**Example Fix (Y-shaped tree):**

```json
// WRONG:
"parents": [[0], [1, 0], [1, 0]]  // 0 is invalid

// CORRECT:
"parents": [[], [1], [1]]  // Trunk empty, children have parent branch #1
```

---

### 7. lengthFromRoot - CRITICAL (Causes Slope/Gravity Cascade Failure)

**Issue:**

- **Reference (Hazel)**: Child branch first points have LFR matching parent branch-off point
  - Child connects at parent trunk point with LFR=0.9 -> Child first point LFR=0.9
- **Generated (Beech)**: Child branch first points have LFR=0.0
  - Child connects at parent trunk point with LFR=0.9 -> Child first point LFR=0.0 (WRONG!)

**Root Cause:**
The `lengthFromRoot` for child branch points was calculated as distance within the child branch, not as the accumulated distance from the trunk root.

**Impact:**

- Slope and Gravity nodes traverse the branch hierarchy recursively
- They match child branches to parent segments using `lengthFromRoot` comparison:

  ```cpp
  // PVSlope.cpp - GetBranchSegmentChildren()
  if (ChildLengthFromRoot > BranchPointLengthFromRoot || 
      ChildLengthFromRoot <= PreviousBranchPointLengthFromRoot)
  {
      continue;  // Child is NOT found for this segment
  }
  ```

- If child first point LFR=0.0 but parent segment is LFR 0.6-0.9, child is never matched
- Result: Slope/Gravity only affect the trunk, not child branches

**Fix Required:**
Child branch first point `lengthFromRoot` must equal the parent branch-off point's `lengthFromRoot`, then continue accumulating from there for subsequent child points.

**Example (Y-shaped tree):**

```
Trunk:  Point 0 (LFR=0.0) -> Point 1 (LFR=0.3) -> Point 2 (LFR=0.6) -> Point 3 (LFR=0.9)
                                                                        |
Child:                                                    First point (LFR=0.9!) -> Point (LFR=1.05) -> Point (LFR=1.2)
```

---

### 8. LOD_totalPscaleGradient - CRITICAL

**Issue:**

- **Reference (Hazel)**: Gradient values around 0.95 at base
  - First value: `0.9542`
- **Generated (Beech)**: Starts at ZERO
  - First value: `0.0`

**Root Cause:**

- Gradient calculation may be incorrect
- File: `src/growpy/io/pve_grove_mapper.py` gradient computation

**Impact:**

- LOD (Level of Detail) gradients control mesh density
- Incorrect gradients can cause mesh builder to crash or produce invalid geometry
- Zero at base means PVE thinks trunk has no thickness

**Fix Required:**
Review and fix gradient calculation to produce proper 0-1 values

---

## Data Statistics Comparison

| Metric | Reference (Hazel) | Generated (Beech) |
|--------|-------------------|-------------------|
| Points | 1,371 | 3,825 |
| Primitives (Branches) | 33 | 1,258 |
| Foliage Instances | 4 types, all branches | 3 types, only 12/1258 branches |
| Non-zero budDirection | 1,371 (100%) | 0 (0%) |
| Non-zero budNumber | 1,371 (100%) | 0 (0%) |
| Non-zero budStatus | 1,371 (100%) | 0 (0%) |
| Non-zero budHormoneLevels | 1,371 (100%) | 0 (0%) |

---

## Implementation Analysis

### Current Code Location

**File:** `src/growpy/io/pve_grove_mapper.py`

**Function:** `_map_points_from_skeleton()` (lines 289-503)

**Current Behavior:**

```python
# Lines 298-308: Defines expected bud attribute sizes
BUD_ATTR_INNER_SIZES = {
    "budDirection": 18,  # 6 buds x 3 floats (xyz direction per bud)
    "budHormoneLevels": 6,  # Per-bud hormone levels
    "budLateralMeristem": 7,  # Per-bud lateral meristem data
    "budLightDetected": 4,  # Per-bud light detection
    "budStatus": 10,  # Per-bud status flags
    "budDevelopment": 6,  # Per-bud development
}

# Lines 460-466: Initializes with ZEROS but never populates
points_data["attributes"][attr_name][value_key] = [
    [0.0] * inner_size for _ in range(num_points)
]
```

**Missing:** Actual extraction of bud data from Grove API

---

## Root Cause Summary

The `pve_grove_mapper.py` module was designed to map Grove data to PVE format but:

1. **Skeleton extraction works** - positions, pscale, lengthFromRoot are correct
2. **Bud data extraction missing** - All bud-related attributes are initialized to zeros
3. **No Grove API calls for bud data** - The Grove API has bud information but it's not being queried

The code structure suggests this was **intentionally left as placeholder/TODO**:

- Infrastructure is in place (attribute definitions, array sizes)
- Initialization happens correctly
- Actual data extraction was never implemented

---

## Proposed Fixes

### Fix Priority 1: budDirection (Critical for Slope Node)

**Location:** `src/growpy/io/pve_grove_mapper.py` function `_map_points_from_skeleton()`

**Required Changes:**

1. Query Grove API for bud information per point
2. Extract bud direction vectors (growth direction)
3. Convert from Grove coordinate system to PVE coordinate system (Y-Z swap)
4. Populate budDirection array with actual vectors

**Pseudo-code:**

```python
# After extracting positions (around line 336)
if "budDirection" in points_data["attributes"]:
    bud_directions = []
    for point_idx in range(num_points):
        # TODO: Get buds for this point from Grove API
        # buds = grove.get_buds_for_point(point_idx)

        # Create 18-float array (6 buds x 3D vector)
        point_bud_dirs = []
        for bud_idx in range(6):  # Max 6 buds per point
            if bud_idx < len(buds):
                # Get bud direction from Grove
                # dir_x, dir_y, dir_z = buds[bud_idx].direction
                # Swap Y-Z for PVE coordinate system
                # point_bud_dirs.extend([dir_x, dir_z, dir_y])
                pass
            else:
                # No bud at this index, use zero vector
                point_bud_dirs.extend([0.0, 0.0, 0.0])

        bud_directions.append(point_bud_dirs)

    value_key = "values" if "values" in points_data["attributes"]["budDirection"] else "value"
    points_data["attributes"]["budDirection"][value_key] = bud_directions
```

### Fix Priority 2: LOD_totalPscaleGradient (Critical for Mesh Builder)

**Location:** Same file, gradient calculation section

**Required Changes:**

1. Review gradient calculation algorithm
2. Ensure gradients range from ~1.0 at base to ~0.0 at tips
3. Validate against reference Hazel values

### Fix Priority 3: budNumber, budStatus, budHormoneLevels

**Location:** Same file

**Required Changes:**

1. Assign sequential budNumber values (1, 2, 3, ...)
2. Extract and map budStatus from Grove bud states
3. Extract hormone levels from Grove simulation

---

## Grove API Investigation Needed

To implement the fixes, we need to identify Grove API methods for:

1. **Bud Data Access:**
   - Method to get buds associated with a skeleton point
   - Bud direction vector
   - Bud status/state
   - Hormone levels (auxin, cytokinin)

2. **Skeleton Point Metadata:**
   - Which buds are active at each point
   - Bud development stage
   - Light exposure data

**Recommended:** Search Grove C++ API documentation or Python bindings for:

- `get_buds()`, `bud.direction`, `bud.state`
- Skeleton point metadata beyond position and thickness

---

## Testing Strategy

After implementing fixes:

1. **Validation Script:** Run `validate_pve_json.py` and `compare_json_structure.py`
2. **Visual Inspection:** Import fixed JSON into PVE Importer node
3. **Slope Node Test:** Apply Slope node and verify no distortion
4. **Mesh Builder Test:** Build mesh and verify no crashes
5. **Reference Comparison:** Compare gradient patterns with Hazel reference

---

## Additional Observations

### Foliage Data

- Reference has foliage on all 33 branches
- Generated has foliage on only 12 out of 1,258 branches
- This is likely intentional (only terminal twigs have foliage meshes)
- Foliage structure appears correct, just different distribution

### Branch Hierarchy

- Both files have valid parent/child relationships
- Generated tree has more detailed branching (1,258 vs 33 branches)
- This is expected for different species and simulation parameters

### Coordinate System

- Position conversion (Y-Z swap) is working correctly
- First position in generated: `[0.0, 0.0, 0.0]` (trunk base at origin)
- Coordinate transformation logic appears sound

---

## Conclusion

**Main Issue:** Missing bud data extraction from Grove API

**Primary Impact:** Slope node failure due to zero budDirection vectors

**Secondary Impact:** Potential mesh builder crashes due to incorrect LOD gradients

**Solution Path:**

1. Investigate Grove API for bud data access
2. Implement bud data extraction in `_map_points_from_skeleton()`
3. Fix LOD gradient calculations
4. Validate against working reference

**Effort Estimate:**

- Medium complexity (requires Grove API understanding)
- Affects single file (`pve_grove_mapper.py`)
- Clear structure already in place for fixes
