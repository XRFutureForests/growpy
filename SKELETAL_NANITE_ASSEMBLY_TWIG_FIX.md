# Skeletal Nanite Assembly Twig Fix - Implementation Complete

**Date:** 2025-01-10  
**Status:** IMPLEMENTED - READY FOR TESTING  
**Priority:** CRITICAL

## Problem Summary

Skeletal Nanite Assemblies were not displaying twig meshes in Unreal Engine despite:

- Correct twig placement extraction
- Proper PointInstancer with skeleton binding
- Twig prototypes defined with NaniteAssemblyExternalRefAPI

## Root Causes Identified

### 1. Using Skeletal Twigs Instead of Static Twigs

**Problem:**

- Skeletal Nanite Assemblies were referencing skeletal twig USD files
- Skeletal twigs contain their own skeleton (single root joint)
- This conflicts with the PointInstancer skeleton binding approach

**Why This Is Wrong:**

- Skeleton binding happens at **PointInstancer level** via `NaniteAssemblySkelBindingAPI`
- Each twig instance should bind to tree skeleton joints, not have its own skeleton
- Having individual skeletons inside prototypes breaks the binding model

**Correct Approach:**

```
Tree (skeletal mesh with joints)
└── PointInstancer (binds to tree joints via NaniteAssemblySkelBindingAPI)
    ├── Prototype 1: Static twig (no skeleton)
    ├── Prototype 2: Static twig (no skeleton)
    └── Prototype 3: Static twig (no skeleton)
```

### 2. Absolute Paths in USD References

**Problem:**

- USD references used absolute file system paths
- Example: `@/Users/.../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b_skeletal.usda@`
- Absolute paths break when files are moved
- Unreal may not resolve absolute paths correctly

**Solution:**

- Use relative paths from Nanite Assembly USD location
- Example: `@../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda@`
- Relative paths are portable and more compatible

## Implementation Details

### Change 1: Use Static Twigs for Skeletal Assemblies

**File:** `src/growpy/io/unreal_nanite_assembly.py`  
**Lines:** ~170-190

```python
# CRITICAL: For skeletal assemblies, use STATIC twig meshes
# The skeleton binding happens at PointInstancer level via NaniteAssemblySkelBindingAPI
# Individual twigs should not have their own skeletons
if use_skeletal_mesh and "_skeletal" in str(twig_path):
    # Replace skeletal twig with static version
    static_twig_path = Path(str(twig_path).replace("_skeletal", ""))
    if static_twig_path.exists():
        twig_ref_path = static_twig_path
        print(f"    Using static twig for skeletal assembly: {static_twig_path.name}")
    else:
        print(f"    Warning: Static twig not found: {static_twig_path}")
        twig_ref_path = twig_path
else:
    twig_ref_path = twig_path
```

**Impact:**

- Skeletal assemblies now use `europeanbeech_var_a.usda` instead of `europeanbeech_var_a_skeletal.usda`
- Static assemblies continue using static twigs as before
- Falls back to skeletal if static not found (graceful degradation)

### Change 2: Relative Path References

**File:** `src/growpy/io/unreal_nanite_assembly.py`  
**Lines:** ~210-230

```python
# Reference twig mesh using relative path
# This allows USD files to be moved as a package
# Unreal can also better resolve relative references
try:
    # Try to make path relative to output USD location
    twig_absolute = twig_ref_path.resolve()
    output_absolute = output_path.resolve()
    twig_relative = Path(os.path.relpath(twig_absolute, output_absolute.parent))
    proto_prim.GetReferences().AddReference(str(twig_relative))
    print(f"      Using relative reference: {twig_relative}")
except (ValueError, OSError):
    # Fall back to absolute path if relative fails
    proto_prim.GetReferences().AddReference(str(twig_ref_path.resolve()))
    print(f"      Using absolute reference: {twig_ref_path.resolve()}")
```

**Impact:**

- USD references now use relative paths when possible
- Example output: `@../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda@`
- Falls back to absolute if relative path calculation fails
- Makes USD files portable across different machines/directories

### Change 3: Added OS Module Import

**File:** `src/growpy/io/unreal_nanite_assembly.py`  
**Line:** ~33

```python
import os
from pathlib import Path
from typing import Any, Dict, Optional
```

**Impact:**

- Enables `os.path.relpath()` for relative path calculation
- No other dependencies added

## Expected Output Changes

### Before Fix

```usda
def Xform "twigdead" (
    prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    instanceable = true
    prepend references = @/Users/maximiliansperlich/Developer/the-grove/data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b_skeletal.usda@
)
{
    token visibility = "invisible"
}
```

**Issues:**

- References skeletal twig (has own skeleton)
- Uses absolute path (not portable)
- Unreal may not load twigs correctly

### After Fix

```usda
def Xform "twigdead" (
    prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    instanceable = true
    prepend references = @../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda@
)
{
    token visibility = "invisible"
}
```

**Improvements:**

- References static twig (no conflicting skeleton)
- Uses relative path (portable)
- Compatible with Unreal's USD resolver

## Console Output During Export

Expected messages:

```
Creating Skeletal Nanite Assembly...
  Extracting placements from: tree.usda
  Found 150 twig_long placements
  Found 80 twig_short placements
  Found 40 twig_dead placements
    Using static twig for skeletal assembly: europeanbeech_var_a.usda
      Using relative reference: ../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_a.usda
    Using static twig for skeletal assembly: europeanbeech_var_b.usda
      Using relative reference: ../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda
  Binding twig instances to skeleton joints...
  ✓ Bound 270 twigs to skeleton (root joint)
  ✓ Added 270 twig instances (3 types)
  ✓ Applied Nanite Assembly Root API
✓ Skeletal Nanite Assembly saved: Beech_tree_0000_NaniteAssembly_skeletal.usda
```

## Testing Instructions

### Step 1: Export New Skeletal Nanite Assembly

```bash
cd /Users/maximiliansperlich/Developer/the-grove
conda activate the-grove

python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/twig_fix_test \
    --quality high \
    --formats usda
```

### Step 2: Inspect Generated USD

```bash
# Check what twig references are used
grep "references = @" ./data/output/twig_fix_test/Beech/USD/Beech_tree_0000_NaniteAssembly_skeletal.usda

# Expected: relative paths to .usda files (not _skeletal.usda)
# ../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_a.usda
# ../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda
```

### Step 3: Import into Unreal Engine

1. Open Unreal Engine 5.7+
2. Import `Beech_tree_0000_NaniteAssembly_skeletal.usda`
3. Open in Skeletal Mesh Editor
4. **Verify twigs are visible!**
5. Apply animation to skeleton
6. **Verify twigs follow skeleton movement!**

### Step 4: Verify in usdview (Optional)

```bash
usdview ./data/output/twig_fix_test/Beech/USD/Beech_tree_0000_NaniteAssembly_skeletal.usda
```

Expected:

- Tree mesh visible
- Twig instances visible (as point clouds or simple geometry)
- PointInstancer present with correct proto indices

## Files Modified

1. **`src/growpy/io/unreal_nanite_assembly.py`**
   - Added logic to use static twigs for skeletal assemblies
   - Changed USD references from absolute to relative paths
   - Added `os` module import
   - Added debug print statements

2. **Documentation Created:**
   - `NANITE_ASSEMBLY_TWIG_REFERENCE_FIX.md` - Root cause analysis
   - `SKELETAL_NANITE_ASSEMBLY_TWIG_FIX.md` - This implementation summary

## Rollback Plan

If this fix causes issues:

```bash
git diff src/growpy/io/unreal_nanite_assembly.py
git checkout src/growpy/io/unreal_nanite_assembly.py
```

The changes are isolated to twig prototype creation logic and can be easily reverted.

## Success Criteria

✅ **Fixed if:**

1. Skeletal Nanite Assembly shows twigs in Unreal Engine
2. Twigs follow skeleton animation (wind, physics)
3. USD references use relative paths
4. Static twig USD files are used for skeletal assemblies
5. No errors during import

❌ **Still broken if:**

1. Twigs still not visible in Unreal
2. Twigs don't follow animation
3. Import errors related to twig references
4. Skeleton conflicts or warnings

## Next Steps if Still Not Working

If twigs still don't load after this fix:

1. **Check if static twig USD files exist:**

   ```bash
   ls data/assets/twigs/*/europeanbeech_var_*.usda | grep -v skeletal
   ```

2. **Verify USD references resolve:**

   ```bash
   usdcat --flatten data/output/.../Beech_tree_0000_NaniteAssembly_skeletal.usda
   ```

3. **Try meshAssetPath approach:**
   - Pre-import twigs into Unreal
   - Set `unreal:naniteAssembly:meshAssetPath` to Unreal package paths
   - See `NANITE_ASSEMBLY_TWIG_REFERENCE_FIX.md` for details

## Related Issues

- Original issue: Missing skeletal twigs in Nanite Assembly
- Related: Schema path warning (fixed)
- Related: Tiny texture on skeletal tree (fixed)
- Related: Skeleton binding implementation (completed)

## Commit Message

```
fix: use static twigs and relative paths for skeletal Nanite Assembly

- Use static twig USD files for skeletal assemblies instead of skeletal twigs
- Change USD references from absolute to relative paths for portability
- Skeleton binding happens at PointInstancer level via NaniteAssemblySkelBindingAPI
- Individual twigs should not have their own skeletons

This fixes the issue where skeletal twigs were not loading in Unreal Engine.
The problem was that skeletal twigs contained their own skeleton which conflicted
with the PointInstancer binding approach. Static twigs are the correct geometry
to use with per-instance skeleton binding.

Fixes #N/A - skeletal Nanite Assembly twig loading issue
```

---

**Status:** IMPLEMENTED - Ready for testing in Unreal Engine  
**Estimated Impact:** HIGH - Should fix missing twig issue  
**Testing Required:** YES - Import into Unreal and verify twigs appear with animation
