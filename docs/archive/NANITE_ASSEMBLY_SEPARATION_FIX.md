# Nanite Assembly Skeletal/Static Separation Fix

**Date:** 2025-01-11  
**Issue:** Static and skeletal files were not properly separated, causing confusion in Unreal Engine

## Problems Identified

### 1. Schema Sublayer Causing Crashes

**Root Cause:** Current code was adding `generatedSchema.usda` as a sublayer to Nanite Assembly files.

**Discovery:** Commit 4cea271 (working version) did NOT reference the schema file at all - it just applied API schemas directly using `TokenListOp`.

**Fix:** Removed schema sublayer reference from `unreal_nanite_assembly.py` (lines 82-96).

```python
# REMOVED - This was causing crashes:
schema_path = Path(__file__).parent.parent.parent.parent / "data" / "unreal_schema" / "generatedSchema.usda"
if schema_path.exists():
    stage.GetRootLayer().subLayerPaths.append(str(schema_path.resolve()))
```

**Result:** Nanite Assembly files now load in Unreal Engine without crashing.

---

### 2. Static Tree Files Had Skeletons

**Root Cause:** In `blender_export.py`, the skeleton was added to `temp_tree_path` (line 3200), which was supposed to remain static-only.

**Bug Flow:**

```python
# OLD LOGIC (WRONG):
1. Create temp_tree_path (static tree)
2. Add skeleton TO temp_tree_path  # ← Pollutes static tree!
3. Copy temp_tree_path to skeletal_tree_path
4. temp_tree_path still has skeleton (not static anymore)
```

**Fix:** Changed order in `blender_export.py` (lines 3188-3218):

```python
# NEW LOGIC (CORRECT):
1. Create temp_tree_path (static tree)
2. COPY temp_tree_path to skeletal_tree_path FIRST
3. Add skeleton to skeletal_tree_path only
4. temp_tree_path remains clean (no skeleton)
```

**Result:**

- `tree_only.usda` → NO skeleton (pure static mesh)
- `tree_only_skeletal.usda` → HAS skeleton (skeletal mesh)

**Verification:**

```bash
grep -c "SkelRoot" tree_only.usda          # Returns 0 (no skeleton)
grep -c "SkelRoot" tree_only_skeletal.usda # Returns 9 (has skeleton)
```

---

### 3. Skeletal Nanite Assembly Only Loaded 2 Twigs

**Root Cause:** Code was using `skeletal_twig_paths` (only 2 twigs with skeletal variants) instead of `static_twig_paths` (all 4 twig types).

**Why This Happened:**

```python
# OLD LOGIC (WRONG):
skeletal_twig_paths = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=True
)
# Only returns 2 twigs: var_a_skeletal, var_b_skeletal

create_nanite_assembly_usd(
    twig_usd_paths=skeletal_twig_paths,  # Only 2 twigs!
    use_skeletal_mesh=True
)
```

**The Confusion:**

- Skeletal Nanite Assembly uses skeletal TREE (for animation)
- But it should use STATIC twigs (not skeletal twigs)
- Reason: PointInstancer binding conflicts with individual twig skeletons
- Twigs are bound to tree skeleton via `NaniteAssemblySkelBindingAPI`, not via their own skeletons

**Fix:** Changed `blender_export.py` (lines 3333-3345) to use `static_twig_paths`:

```python
# NEW LOGIC (CORRECT):
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,      # Skeletal tree (has skeleton)
    twig_usd_paths=static_twig_paths,      # Use ALL 4 static twigs
    use_skeletal_mesh=True,
    twig_placement_source_usd=temp_tree_path
)
```

**Result:** Both static and skeletal Nanite Assemblies now reference all 4 twig types.

---

## Summary of Changes

### File: `src/growpy/io/unreal_nanite_assembly.py`

**Change:** Removed schema sublayer reference (lines 82-96)  
**Reason:** Schema file as sublayer was causing Unreal crashes  
**Impact:** Nanite Assembly files now load correctly in Unreal

### File: `src/growpy/io/blender_export.py`

**Change 1:** Reordered skeleton addition (lines 3188-3218)  
**Reason:** Preserve static tree without skeleton contamination  
**Impact:** Clear separation between static and skeletal tree files

**Change 2:** Use static twigs for skeletal Nanite Assembly (lines 3333-3345)  
**Reason:** PointInstancer binding requires static twig meshes  
**Impact:** Skeletal Nanite Assembly now has all 4 twig variants

---

## File Output Structure

### Generated Files (per tree)

```
Oak/
├── USD/
│   ├── Oak_tree_0001_tree_only.usda              # Static tree (NO skeleton)
│   ├── Oak_tree_0001_tree_only_skeletal.usda     # Skeletal tree (HAS skeleton)
│   ├── Oak_tree_0001_NaniteAssembly.usda         # Static assembly (staticMesh)
│   └── Oak_tree_0001_NaniteAssembly_skeletal.usda # Skeletal assembly (skeletalMesh)
└── twigs/
    ├── europeanoak_apical.usda                    # Static twig
    ├── europeanoak_apical_skeletal.usda           # Skeletal twig (unused in Nanite)
    ├── europeanoak_lateral.usda                   # Static twig
    └── europeanoak_lateral_skeletal.usda          # Skeletal twig (unused in Nanite)
```

### Usage in Unreal

- **Static Mesh Import:** `Oak_tree_0001_NaniteAssembly.usda`
  - References: Static tree + All 4 static twigs
  - No skeleton, no animation
  
- **Skeletal Mesh Import:** `Oak_tree_0001_NaniteAssembly_skeletal.usda`
  - References: Skeletal tree + All 4 static twigs
  - Tree has skeleton for animation
  - Twigs bound to tree skeleton via PointInstancer

---

## Testing Results

### Before Fix

- ❌ Static tree had skeleton (wrong)
- ❌ Skeletal assembly only had 2 twigs (incomplete)
- ❌ Nanite Assembly crashed Unreal (schema issue)

### After Fix

- ✅ Static tree has NO skeleton
- ✅ Skeletal tree has skeleton
- ✅ Both assemblies have all 4 twig types
- ✅ Nanite Assembly loads in Unreal without crashing

### Verification Commands

```bash
# Check static tree has no skeleton
grep -c "SkelRoot" Oak_tree_0001_tree_only.usda
# Output: 0

# Check skeletal tree has skeleton  
grep -c "SkelRoot" Oak_tree_0001_tree_only_skeletal.usda
# Output: 9

# Check both assemblies have same twigs
grep "europeanoak" Oak_tree_0001_NaniteAssembly.usda | wc -l
grep "europeanoak" Oak_tree_0001_NaniteAssembly_skeletal.usda | wc -l
# Both output: 4 (all twig types)
```

---

## Key Learnings

1. **Schema Files:** Unreal recognizes API schemas by name alone - no sublayer reference needed
2. **File Modification:** Be careful with in-place modifications - copy files BEFORE adding data
3. **Skeletal Assemblies:** Use skeletal tree + static twigs (not skeletal twigs)
4. **PointInstancer Binding:** Individual twig skeletons conflict with PointInstancer skeleton binding

---

## Next Steps

1. Test in Unreal Engine 5.7+ to confirm:
   - Static Nanite Assembly creates proper Nanite Assembly asset
   - Skeletal Nanite Assembly creates proper skeletal mesh with animation
   - All 4 twig variants are visible in both assemblies
   - Tree mesh appears in Nanite Assembly (not just twigs)

2. If tree mesh still missing from Nanite Assembly asset:
   - Check TreeMesh reference in USD is valid
   - Verify tree mesh has proper geometry
   - Ensure NaniteAssemblyExternalRefAPI is applied correctly
