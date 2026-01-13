# PVE JSON Requirements & Fixes - Implementation Summary

**Date**: 2026-01-09

**Related Documentation:**

- [PVE_ATTRIBUTE_REFERENCE.md](PVE_ATTRIBUTE_REFERENCE.md) - Complete attribute documentation with usage details
- [PVE_PRESET_WORKFLOW.md](PVE_PRESET_WORKFLOW.md) - Preset generation and import workflow

## Problem Identified

The generated PVE JSON files from Grove trees were causing Unreal Engine to crash when importing and attempting to place foliage. Analysis of the Procedural Vegetation Editor (PVE) C++ source code revealed two critical requirements:

### Critical Crash Causes

1. **Division by Zero** (`PVMeshBuilderElement.cpp` lines 218-219)
   - Code: `check(MaxPointScale > 0); MaxPointScaleRatio = 1.0f / (MaxPointScale * UE_TWO_PI);`
   - If all `pscale` values are 0, MaxPointScale becomes 0, causing immediate crash
   - **Status**: ✅ FIXED in [pve_grove_mapper.py](../src/growpy/io/pve_grove_mapper.py#L354-L368)

2. **Array Out of Bounds** (`PVMeshBuilderElement.cpp` lines 782, 806)
   - Code accesses: `PointBudDirections[PointIndex][0]` and `PointBudDirections[PointIndex][5]`
   - Requires budDirection to have 18 floats (6 vectors × 3 components) per point
   - **Status**: ⚠️ IMPROVED with fallback handling in [pve_grove_mapper.py](../src/growpy/io/pve_grove_mapper.py#L1179-L1198)

### Non-Critical Issues

- **Zero budDirection values**: Many points have all-zero budDirection arrays (see beech validation)
  - Does NOT crash but may cause rendering artifacts
  - Current implementation fills with default up vectors for completely missing data
  - **Status**: Needs better direction calculation from Grove skeleton data

### Critical Hierarchy Issues (NEW - 2026-01-09)

1. **Invalid `parents` Array Values** (`PVBranchFacade.cpp` line 179)
   - Code: `const int32 ParentBranchNumber = ParentsBranchNumbers.Last();`
   - Then: `return BranchNumbers.Get().Find(ParentBranchNumber);`
   - If `parents` array contains 0 but `branchNumber` starts at 1, `Find(0)` returns `INDEX_NONE`
   - **Result**: Hierarchy traversal fails completely - Slope/Gravity can't find children
   - **Status**: FIXED - Trunk must have empty `parents: []`, children have `parents: [1]` (parent branch number)

2. **Incorrect `lengthFromRoot` for Child Branches** (`PVSlope.cpp` lines 214-216)
   - Code uses LFR comparison to match children to parent segments:

     ```cpp
     if (ChildLengthFromRoot > BranchPointLengthFromRoot || 
         ChildLengthFromRoot <= PreviousBranchPointLengthFromRoot) continue;
     ```

   - Child first point LFR must equal parent branch-off point LFR (not 0.0!)
   - **Result**: Children never matched to parent segments, Slope/Gravity only affect trunk
   - **Status**: FIXED - Child branch first point LFR now matches parent branch-off point LFR

## Implementation Summary

### 1. Validation Tool

**File**: [src/growpy/io/validate_pve_json.py](../src/growpy/io/validate_pve_json.py)

Validates PVE JSON files against critical requirements:

- ✅ Checks for non-zero pscale values
- ✅ Checks budDirection array sizes (must be 18+ floats)
- ✅ Validates required JSON paths
- ✅ Identifies all-zero budDirection vectors (warning)

**Usage**:

```bash
python validate_pve_json_cli.py data/output/forest_quick/european_beech/tree_0003/european_beech_tree_0003.json
```

### 2. PVE Grove Mapper Fixes

**File**: [src/growpy/io/pve_grove_mapper.py](../src/growpy/io/pve_grove_mapper.py)

#### pscale Fix (lines 354-368)

```python
# Apply minimum threshold to prevent zero values
MIN_PSCALE = 0.001  # Minimum 1mm radius in meters
pscales = [max(p, MIN_PSCALE) for p in pscales]

# Validate
if max(pscales) == 0:
    print("    WARNING: All pscale values were 0, applied minimum threshold")
```

#### budDirection Fix (lines 1179-1198)

```python
# If we have fewer than 6 buds worth of directions, ensure at least
# indices [0] and [5] have valid vectors (required by PVMeshBuilderElement.cpp)
if len(directions) == 0:
    # No direction data - use default up vector (Y-up in PVE coords)
    bud_directions[point_idx][0:3] = [0.0, 1.0, 0.0]  # Index [0]
    bud_directions[point_idx][15:18] = [0.0, 1.0, 0.0]  # Index [5]
elif len(directions) < 18:
    # Ensure index [5] has a valid vector (copy from index [0])
    if all(bud_directions[point_idx][i] == 0.0 for i in range(15, 18)):
        bud_directions[point_idx][15:18] = bud_directions[point_idx][0:3]
```

### 3. Minimal Test JSON

**File**: [src/growpy/io/create_minimal_pve_test.py](../src/growpy/io/create_minimal_pve_test.py)

Creates a minimal viable PVE JSON (3 points, 2 branches, Y-shaped tree) that validates successfully:

```bash
python -m growpy.io.create_minimal_pve_test
# Output: data/output/pve_test/minimal_test_tree.json
```

**Test Results**:

- ✅ 3 points with non-zero pscale values [0.05, 0.03, 0.01]
- ✅ All points have 18-float budDirection arrays
- ✅ All required JSON paths present
- ✅ Validation PASSED

## Validation Results

### Minimal Test Tree

```
✅ VALIDATION PASSED: 3 points, 2 branches, all critical checks OK
```

### Beech Tree (european_beech_tree_0003.json)

```
⚠️ WARNINGS: ~800 points with all-zero budDirection values
✅ pscale values are non-zero (no crash risk)
✅ budDirection arrays have 18 floats each (no crash risk)
⚠️ Zero budDirection vectors may cause rendering issues
```

## Required Attributes for PVE Mesh Building

Based on source code analysis of `PVMeshBuilderElement.cpp`, `PVJSONHelper.cpp`, and related files:

### Critical (MUST NOT BE ZERO/EMPTY)

| Attribute | Requirement | Crash If Invalid |
|-----------|-------------|------------------|
| `pscale` | Must have non-zero values (max > 0) | ✅ YES - Division by zero |
| `budDirection` | Must have 18 floats (6 vectors) per point | ✅ YES - Array out of bounds |

### Required (USED IN VALIDATION)

| Attribute | Requirement | Crash If Missing |
|-----------|-------------|------------------|
| `positions` | 3D vectors per point | ✅ YES |
| `lengthFromRoot` | Distance from root per point | ❌ NO - Returns 0.0 default |
| `LOD_totalPscaleGradient` | Normalized 0-1 values | ❌ NO - Returns 0.0 default |
| `budNumber` | Sequential IDs per point | ❌ NO - Returns -1 default |
| `parents` | Hierarchy per branch | ❌ NO - Handled gracefully |
| `children` | Child branches per branch | ❌ NO - Empty arrays OK |
| `branchNumber` | Sequential IDs per branch | ❌ NO - Default values |

### Optional (HAS SAFE DEFAULTS)

All other attributes have safe defaults if missing and won't cause crashes.

## Metadata Fields (Not Used)

These fields from the comparison are **NOT** accessed during mesh building:

- `maxBranchNumber`, `maxBudNumber` - Informational only
- `maxPscale`, `minPscale`, `max_pscale` - Metadata only
- `max_curve_length` - Not referenced in code

## Next Steps

### Immediate (Prevents Crashes)

- ✅ pscale minimum threshold implemented
- ✅ budDirection fallback vectors implemented
- ✅ Validation tool created

### Recommended (Improves Quality)

1. **Improve budDirection calculation**
   - Current: Uses poly_line directions
   - Issue: Leaf points may have no forward direction
   - Solution: Calculate from parent/sibling branches or use branch tangent

2. **Add validation to export pipeline**
   - Integrate validation into `generate_forest.py`
   - Auto-validate JSON before saving
   - Warn user if issues detected

3. **Test with Unreal**
   - Import [minimal_test_tree.json](../data/output/pve_test/minimal_test_tree.json) into Unreal
   - Verify mesh builds correctly
   - Verify foliage placement works
   - Re-export beech trees with fixes and test

## Files Modified

1. ✅ [src/growpy/io/validate_pve_json.py](../src/growpy/io/validate_pve_json.py) - NEW
2. ✅ [src/growpy/io/create_minimal_pve_test.py](../src/growpy/io/create_minimal_pve_test.py) - NEW
3. ✅ [validate_pve_json_cli.py](../validate_pve_json_cli.py) - NEW (root)
4. ✅ [src/growpy/io/pve_grove_mapper.py](../src/growpy/io/pve_grove_mapper.py) - MODIFIED
   - Added pscale minimum threshold (line 354-368)
   - Added budDirection fallback handling (line 1179-1198)

## Testing

**Minimal Test JSON**:

```bash
# Create test file
python -m growpy.io.create_minimal_pve_test

# Validate
python validate_pve_json_cli.py data/output/pve_test/minimal_test_tree.json
```

**Existing Trees**:

```bash
# Validate beech tree
python validate_pve_json_cli.py "data/output/forest_quick/european_beech/tree_0003/european_beech_tree_0003.json"
```

**Re-export Trees** (applies fixes):

```bash
# Re-run forest generation to get updated JSON with fixes
python src/growpy/cli/generate_forest.py data/input/test_quick.csv
```

## References

- PVE Source: `data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/`
- Key files analyzed:
  - `Private/Nodes/PVMeshBuilderElement.cpp` - Mesh building (crash locations)
  - `Private/Helpers/PVJSONHelper.cpp` - JSON loading/validation
  - `Private/Facades/PVPointFacade.cpp` - Point attribute access
  - `Private/Facades/PVBranchFacade.cpp` - Branch attribute access
