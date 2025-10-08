# Twig Nanite Assembly Fix - 2025-10-08

## Problem

Beech tree USD files were crashing Unreal Engine 5.7 on import, while Oak trees imported successfully. The issue was traced to **Nanite Assembly twig references**.

### Symptoms

- `Beech_var1_tree_only.usda` → ✅ Imports successfully (skeletal mesh only, no twigs)
- `Beech_var1.usda` → ❌ Crashes on import (tree + twigs)
- `Beech_var1_NaniteAssembly.usda` → ❌ Crashes on import (Nanite Assembly)
- `Oak_var1.usda` → ✅ Imports successfully (tree + twigs)

### Root Cause

The `get_twig_usd_map_for_species()` function was selecting **Nanite Assembly USD files** for twig references:

**Beech (crashed):**

```usd
def Xform "twig_dead" (
    prepend references = @europeanbeech_var_b_NaniteAssembly.usda@  ❌ CRASH
)
```

**Oak (worked):**

```usd
def Xform "twig_dead" (
    prepend references = @europeanoak_lateral.usda@  ✅ WORKS
)
```

## Why This Matters

### Nanite Assembly Architecture

Nanite Assemblies in USD should only be used at the **top level**, not for individual component references:

```
✅ CORRECT Structure:
TreeAssembly (top-level)
├─ Tree mesh (regular USD reference)
└─ Twigs (regular USD references via PointInstancer)
   ├─ twig_a.usda
   └─ twig_b.usda

❌ INCORRECT Structure:
TreeAssembly
├─ Tree mesh
└─ Twigs
   ├─ twig_a_NaniteAssembly.usda  ← Causes crash!
   └─ twig_b_NaniteAssembly.usda  ← Causes crash!
```

### Why Nanite Assembly Twigs Don't Work

1. **Skeletal Mesh Incompatibility**: Nanite Assembly metadata conflicts with skeletal mesh binding
2. **Nested Assembly Problem**: Unreal's importer doesn't handle nested Nanite Assemblies (tree + twigs)
3. **Reference Complexity**: Nanite Assembly USD files are wrappers that add complexity to scene graph traversal
4. **Material Duplication**: Each Nanite Assembly creates its own material context, causing conflicts

## Solution

Modified `get_twig_usd_map_for_species()` to **always skip Nanite Assembly files** when selecting twig USD references.

### Code Changes

**File:** `src/growpy/io/blender_export.py`

**Before:**

```python
for ext in [".usda", ".usd"]:
    usd_file = twig_file.with_suffix(ext)
    if usd_file.exists():  # ❌ Would pick _NaniteAssembly.usda
        twig_usd_map[grove_type] = usd_file
```

**After:**

```python
for ext in [".usda", ".usd"]:
    usd_file = twig_file.with_suffix(ext)
    # CRITICAL: Skip Nanite Assembly files for twigs
    if "_NaniteAssembly" not in usd_file.name and usd_file.exists():
        twig_usd_map[grove_type] = usd_file
```

This was applied in **two locations**:

1. Keyword-based twig mapping (line ~2349)
2. Generic fallback twig mapping (line ~2393)

## Result

### Before Fix

```
Beech/USD/
├── Beech_var1.usda                     ❌ Crashed (Nanite Assembly twigs)
│   └── references:
│       ├── europeanbeech_var_b_NaniteAssembly.usda
│       └── europeanbeech_var_a_NaniteAssembly.usda
```

### After Fix

```
Beech/USD/
├── Beech_var1.usda                     ✅ Works (regular USD twigs)
│   └── references:
│       ├── europeanbeech_var_b.usda
│       └── europeanbeech_var_a.usda
```

## Import Workflow

### For Static Meshes (Most Common)

```bash
Import: Beech_var1_NaniteAssembly.usda
Result: Static mesh + instanced twigs + Nanite optimization
Use for: Background trees, forests, static foliage
```

### For Skeletal Meshes (Animation)

```bash
Import: Beech_var1.usda
Result: Skeletal mesh + skeleton + materials + instanced twigs
Use for: Hero trees, wind animation, procedural growth
Note: Twigs now reference regular USD (not Nanite Assembly)
```

### Individual Components

```bash
Import: Beech_var1_tree_only.usda
Result: Just the tree mesh (trunk/branches)

Import: europeanbeech_var_a.usda
Result: Individual twig mesh (leaf cluster)
```

## Technical Details

### File Size Comparison

```bash
europeanbeech_var_a.usda              38K  # Full mesh data
europeanbeech_var_a_NaniteAssembly.usda 438B  # Wrapper reference

# Nanite Assembly is lightweight wrapper, NOT needed for references
```

### Why Oak Worked Before

Oak's twig files were being matched by keyword algorithm:

- "apical" → matched "long" keyword → `europeanoak_apical.usda` ✅
- "lateral" → matched "short" keyword → `europeanoak_lateral.usda` ✅

Beech's twig files had no keyword matches:

- "var_a", "var_b" → no keyword match → generic fallback
- Generic fallback picked first `.usda` it found → got `_NaniteAssembly.usda` ❌

## Implications

### For Users

✅ **Beech trees now import successfully** into Unreal Engine 5.7
✅ **All skeletal meshes with twigs** work correctly
✅ **FBX export still works** (independent of USD twig references)
✅ **Nanite Assembly at tree level** still works for static meshes

### For Developers

⚠️ **Never use Nanite Assembly USD files as references** in other USD files
⚠️ **Nanite Assembly is for top-level import only**, not composition
✅ **Regular USD files are the correct format** for scene references
✅ **PointInstancer works with regular USD** twig references

## Related Issues

- Initial report: "i can import the beech tree only, the other usd crashes unreal"
- Discovery: Oak worked because it wasn't using Nanite Assembly twigs
- Insight: "maybe the nanite assembly twigs are not required at all" ✅ CORRECT

## Related Documentation

- `docs/archive/SKELETAL_NANITE_ASSEMBLY_ISSUE.md` - Tree-level Nanite Assembly issue
- `docs/growpy/TWIG_CONVERSION_V2.md` - Twig USD export process
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import workflows

## Conclusion

**Nanite Assembly USD files should NEVER be used as references within other USD files.**

They are meant to be **top-level import targets** only. For composition (references, sublayers, payloads), always use regular USD files.

This fix ensures all tree species use regular USD twig references, making them compatible with both static and skeletal mesh imports in Unreal Engine.
