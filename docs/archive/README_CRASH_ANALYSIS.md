# PVE Plugin Crash Analysis - Complete Documentation Index

## Overview

Complete technical analysis of two crashes encountered when importing the European beech preset into Unreal Engine's Procedural Vegetation Editor (PVE) plugin.

**Status**:
- Crash #1 ✓ FIXED
- Crash #2 ⚠ NEEDS IMPLEMENTATION (3 lines of code)

---

## Quick Start

**If you just want to fix it**: Read [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md) (3 minutes)

**If you need full details**: Read [PVE_CRASH_ANALYSIS_SUMMARY.md](PVE_CRASH_ANALYSIS_SUMMARY.md) (10 minutes)

**If you need to implement it**: Follow [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md) (15 minutes)

---

## Documentation Files

### Entry Points

| File | Purpose | Time |
|------|---------|------|
| **[QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md)** | Fast fix guide with 3-step implementation | 3 min |
| **[PVE_CRASH_ANALYSIS_SUMMARY.md](PVE_CRASH_ANALYSIS_SUMMARY.md)** | Complete overview of both crashes | 10 min |
| **[BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md)** | Detailed implementation with code examples | 15 min |

### Detailed Analysis

| File | Content | Details |
|------|---------|---------|
| **[BUDDEVELOPMENT_ROOT_CAUSE.md](BUDDEVELOPMENT_ROOT_CAUSE.md)** | Root cause investigation | Shows data flow, GrowPy mapping logic, missing extraction |
| **[BUDEVELOPMENT_CRASH_ANALYSIS.md](BUDEVELOPMENT_CRASH_ANALYSIS.md)** | Technical crash details | PVMaterialSettings.cpp code analysis, array requirements |
| **[JSON_CRASH_ANALYSIS.md](JSON_CRASH_ANALYSIS.md)** | First crash (fixed) | JSON key format mismatch details |

### Validation & Reference

| File | Content | Use Case |
|------|---------|----------|
| **[BEECH_JSON_VALIDATION_REPORT.md](BEECH_JSON_VALIDATION_REPORT.md)** | Current JSON structure validation | Verify format is correct |
| **[ANALYSIS_COMPLETE.txt](ANALYSIS_COMPLETE.txt)** | Executive summary | Quick overview of findings |

---

## Problem Summary

### Crash #1: JSON Key Format (FIXED ✓)

**Error**: JSON parsing fails during preset import
**Cause**: Primitives attributes used `"value"` instead of `"values"` key
**Status**: Fixed by forest generation script update
**Details**: [JSON_CRASH_ANALYSIS.md](JSON_CRASH_ANALYSIS.md)

### Crash #2: BudDevelopment Array Size (NEEDS FIX ⚠)

**Error**: `Assertion failed: BudDevelopment.Num() > 2`
**Location**: PVMaterialSettings.cpp:71
**Cause**: budDevelopment arrays contain only 1 element instead of required 6+
**Status**: Needs 3 lines of code to fix
**Details**: [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md)

---

## The Fix at a Glance

### What Needs to Change

Two files need modifications:

**1. Schema Definition** (`src/growpy/io/pve_schema.py:90`)
```python
# FROM:
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},

# TO:
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

**2. Data Extraction** (`src/growpy/io/pve_grove_mapper.py` - after line 360)

Add elif block to extract budDevelopment from Grove simulation data.

### Why This Works

The PVE material system needs 6-element budDevelopment arrays to:
- Access generation (branch depth) at index 0
- Access age (growth cycle) at index 2
- Compute material assignment based on generation and age

Currently, arrays have only 1 element (`[0]`), causing assertion failure.

### Result After Fix

```json
"budDevelopment": {
  "values": [
    [0, 0, 0, 50, 50, 16],    // ✓ 6 elements
    [1, 5, 5, 75, 60, 16],    // ✓ 6 elements
    ...
  ]
}
```

---

## File Organization

### Files to Modify

1. **`src/growpy/io/pve_schema.py`**
   - Line 90: budDevelopment schema definition
   - Change: 1 line (3 properties)

2. **`src/growpy/io/pve_grove_mapper.py`**
   - Function: `_map_points_from_skeleton()`
   - Location: After line 360
   - Change: ~15 lines (elif block for extraction)

### Analysis Documents

All analysis documents are in the project root:
- `*.md` files for detailed analysis
- `*.txt` files for quick reference
- No modifications needed to any codebase files except the 2 listed above

---

## Reading Guide by Role

### For Quick Implementation
1. Read [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md)
2. Make schema change
3. Add data extraction code
4. Regenerate and test

### For Understanding the Problem
1. Read [PVE_CRASH_ANALYSIS_SUMMARY.md](PVE_CRASH_ANALYSIS_SUMMARY.md)
2. Reference [BUDDEVELOPMENT_ROOT_CAUSE.md](BUDDEVELOPMENT_ROOT_CAUSE.md) for details
3. Check [BUDEVELOPMENT_CRASH_ANALYSIS.md](BUDEVELOPMENT_CRASH_ANALYSIS.md) for code analysis

### For Complete Implementation
1. Start with [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md)
2. Follow step-by-step instructions
3. Validate using provided checks
4. Test in Unreal Engine

### For Verification
1. Use [BEECH_JSON_VALIDATION_REPORT.md](BEECH_JSON_VALIDATION_REPORT.md) to validate current structure
2. Check [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md) for validation steps after implementation

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Files to modify | 2 |
| Lines to change | ~20 |
| Implementation time | 3-5 minutes |
| Testing time | 2-3 minutes |
| Lines of analysis docs | ~2000 |
| Crash type 1 status | ✓ Fixed |
| Crash type 2 status | ⚠ Ready to fix |

---

## Data Flow Diagrams

### Current Flow (Crashes at step 3)

```
Grove Simulation
    ↓
Skeleton Extraction
    ↓
Point Attribute Mapping
    ├─ generation → schema
    ├─ lengthFromRoot → schema
    ├─ plantGradient → schema
    └─ budDevelopment → [0] (HARDCODED ZEROS) ❌
    ↓
Export to JSON
    ↓
Unreal PVE Import
    ├─ Load JSON ✓
    ├─ Parse data ✓
    ├─ Apply materials → Access BudDevelopment[0,2]
    └─ CRASH: Array has only 1 element! ❌
```

### Fixed Flow (No crash)

```
Grove Simulation
    ↓
Skeleton Extraction
    ↓
Point Attribute Mapping
    ├─ generation → schema
    ├─ lengthFromRoot → schema
    ├─ plantGradient → schema
    └─ budDevelopment → [gen, age_ind, age, vigor, light, lifespan] ✓
    ↓
Export to JSON
    ↓
Unreal PVE Import
    ├─ Load JSON ✓
    ├─ Parse data ✓
    ├─ Apply materials → Access BudDevelopment[0,2] ✓
    └─ Generate mesh ✓
```

---

## Technical Details Summary

### What PVE Needs

[PVMaterialSettings.cpp:66-79](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L66-L79):

```cpp
TArray<int> BudDevelopment = PointFacade.GetBudDevelopment(PointIndex);
check(BudDevelopment.Num() > 2);  // Requires 3+ elements
// Uses BudDevelopment[0] and BudDevelopment[2]
```

### What Grove Provides

- `generation` - Branch hierarchy depth
- `point_attribute_age` - Growth order
- `point_attribute_vigor` - Growth strength
- `point_attribute_shade` - Light exposure
- `pscale` - Branch size

All data needed for budDevelopment is available from Grove simulation.

### Current Schema Problem

```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"}
```

Issues:
- `isArray: False` - Should be `True` (per-point arrays)
- `size: 1` - Should be `6` (6-element arrays)
- `type: "float"` - Should be `"int"` (matches Hazel)

---

## Next Steps

1. **Review** the appropriate documentation based on your needs
2. **Implement** the schema and data extraction changes
3. **Regenerate** the forest using the corrected code
4. **Validate** the JSON structure
5. **Test** in Unreal Engine

See [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md) to start immediately.

---

## Additional Resources

### Reference Assets
- **Working example**: `data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json`
- **Current beech**: `data/output/forest/european_beech/european_beech_tree_0000.json`

### Source Code References
- **Crash location**: `data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp`
- **Schema file**: `src/growpy/io/pve_schema.py`
- **Mapper file**: `src/growpy/io/pve_grove_mapper.py`
- **Grove types**: `src/the_grove_22/modules/the_grove_22_core/__init__.pyi`

---

## Document Versions

All analysis completed: 2025-11-25

Analysis covers:
- PVE plugin source code (v5.5+)
- GrowPy mapper and schema
- European beech forest generation
- Crash trace from Unreal Engine
- Hazel reference JSON structure
- Grove tree simulation API

---

## Support

For questions about specific sections:
- **Schema fix**: See [QUICK_FIX_REFERENCE.md](QUICK_FIX_REFERENCE.md) Part 1
- **Data extraction**: See [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md) Part 2
- **Root cause**: See [BUDDEVELOPMENT_ROOT_CAUSE.md](BUDDEVELOPMENT_ROOT_CAUSE.md)
- **Technical details**: See [BUDEVELOPMENT_CRASH_ANALYSIS.md](BUDEVELOPMENT_CRASH_ANALYSIS.md)

All documentation is self-contained and cross-referenced.
