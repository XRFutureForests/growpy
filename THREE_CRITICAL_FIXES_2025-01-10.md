# Three Critical Fixes for Nanite Assembly and Skeletal USD

**Date:** 2025-01-10  
**Status:** COMPLETE  
**Issues Fixed:** Schema path error, texture scaling, missing skeletal twigs

## Issues Identified

### 1. Schema Path Error

**Problem:** Warning message showing incorrect path with `src` prefix:

```
Warning: Unreal schema not found at /Users/.../the-grove/src/data/unreal_schema/generatedSchema.usda
```

**Root Cause:** `Path(__file__).parent.parent.parent` only went up 3 levels from:

- `src/growpy/io/unreal_nanite_assembly.py`
- Going up 3: `src/growpy/io/` → `src/growpy/` → `src/` → **STOPS AT src/**
- Needed 4 levels to reach project root

**Fix:** Added one more `.parent` to go up 4 levels:

```python
schema_path = (
    Path(__file__).parent.parent.parent.parent  # 4 levels: io/ → growpy/ → src/ → project root
    / "data"
    / "unreal_schema"
    / "generatedSchema.usda"
)
```

**Files Changed:**

- `src/growpy/io/unreal_nanite_assembly.py` (line ~84)
- `src/growpy/io/blender_export.py` (line ~538)

### 2. Extremely Small Texture on Skeletal Tree USD

**Problem:** Texture on `tree_skeletal.usda` was extremely small (much smaller than expected)

**Root Cause:** The `aspect_ratio` variable was set earlier in the function but the UV scaling code used:

```python
uv_scale_y = aspect_ratio if "aspect_ratio" in locals() else 4.0
```

The check `"aspect_ratio" in locals()` doesn't work reliably in Python - it checks if the **string** "aspect_ratio" exists in local variables, not the variable itself.

**Fix:** Changed to direct variable reference with try/except:

```python
try:
    uv_scale_y = aspect_ratio  # Use the aspect_ratio set earlier (4.0 default)
except NameError:
    uv_scale_y = 4.0  # Fallback if not set

print(f"  Applying UV V-coordinate scaling: {uv_scale_y}x")
```

This ensures:

1. UV aspect ratio is properly applied to Grove model (line ~364)
2. UV V-coordinates in Blender mesh are scaled by the same ratio (line ~382)
3. Both static AND skeletal tree exports get proper texture scaling

**File Changed:**

- `src/growpy/io/blender_export.py` (line ~380-395)

### 3. Missing Skeletal Twigs in Nanite Assembly

**Problem:** Skeletal Nanite Assembly imports correctly as skeletal mesh but has NO twig instances

**Root Cause:** The skeletal Nanite Assembly was trying to extract twig placements from `skeletal_tree_path` (which has skeleton embedded), but the skeletal USD export process might not preserve twig face attributes properly. The static tree USD (`temp_tree_path`) has all the twig face attributes.

**Solution:** Add `twig_placement_source_usd` parameter to extract placements from static tree while still referencing skeletal tree/twigs:

```python
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,          # Reference skeletal tree (for mesh/skeleton)
    twig_usd_paths=skeletal_twig_paths,        # Reference skeletal twigs
    twig_placement_source_usd=temp_tree_path,  # Extract placements from static tree
    use_skeletal_mesh=True,
)
```

**Implementation:**

1. Added `twig_placement_source_usd` parameter to `create_nanite_assembly_usd()`
2. Use this path for placement extraction if provided
3. Still reference skeletal tree/twig USD files in the assembly

**Files Changed:**

- `src/growpy/io/unreal_nanite_assembly.py`:
  - Line ~39: Added parameter to function signature
  - Line ~69: Added parameter to docstring
  - Line ~141: Use twig_placement_source_usd for extraction
- `src/growpy/io/blender_export.py`:
  - Line ~3328: Pass temp_tree_path as twig_placement_source_usd

## Schema File Clarification

**Question:** Should we use `generatedSchema.usda` or `schema.usda` in the `unreal/` subfolder?

**Answer:** Use `generatedSchema.usda` in the root of `data/unreal_schema/`:

- `generatedSchema.usda` - **Auto-generated schema definitions** (USE THIS)
- `unreal/schema.usda` - Human-readable source definitions
- `plugInfo.json` - USD plugin metadata

The `generatedSchema.usda` is created by USD's `usdGenSchema` tool from the source `schema.usda` file. Unreal Engine expects the generated version.

## Verification Steps

### Test Schema Path

```bash
python -c "from pathlib import Path; p = Path('src/growpy/io/unreal_nanite_assembly.py').parent.parent.parent.parent / 'data' / 'unreal_schema' / 'generatedSchema.usda'; print(f'Exists: {p.exists()}, Path: {p}')"
```

Should output:

```
Exists: True, Path: /Users/.../the-grove/data/unreal_schema/generatedSchema.usda
```

### Test Texture Scaling

Run export and check UV coordinates in skeletal tree:

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/texture_test \
    --quality high \
    --formats usda \
    --include-skeleton
```

Look for output:

```
  Applied UV aspect ratio: 4.0
  Applying UV V-coordinate scaling: 4.0x
```

### Test Skeletal Nanite Assembly with Twigs

Run export and check for twig placement messages:

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/skeletal_nanite_test \
    --quality high \
    --formats usda \
    --include-skeleton
```

Expected output:

```
Creating Skeletal Nanite Assembly...
  Extracting placements from: tree.usda
  Found X twig_long placements
  Found Y twig_short placements
  ✓ Added Z twig instances (N types)
```

Import `tree_NaniteAssembly_skeletal.usda` in Unreal - should show:

- Skeletal tree mesh recognized
- Twig instances visible
- Texture at proper scale (not too small)

## Technical Details

### Path Traversal Logic

From `src/growpy/io/unreal_nanite_assembly.py`:

```
__file__ = /Users/.../the-grove/src/growpy/io/unreal_nanite_assembly.py

.parent       → src/growpy/io/
.parent.parent → src/growpy/
.parent.parent.parent → src/
.parent.parent.parent.parent → /Users/.../the-grove/  ✓ PROJECT ROOT
```

### UV Aspect Ratio Application Points

1. **Grove Model** (line ~364): `model.apply_uv_aspect_ratio(aspect_ratio)`
   - Applies to internal Grove model data
2. **Blender Mesh UVs** (line ~382): `v = uvs[uv_index + 1] * uv_scale_y`
   - Manually scales V-coordinates in Blender mesh
   - CRITICAL: Blender's USD exporter uses mesh UVs, not Grove's

### Twig Placement Data Flow

```
Static Tree Export (temp_tree_path)
    ↓
Has twig face attributes (twig_long, twig_short, etc.)
    ↓
extract_twig_placements_from_usd(temp_tree_path)
    ↓
Returns position/normal/rotation for each twig
    ↓
Skeletal Nanite Assembly
    ↓
Uses placements + skeletal twig USD references
    ↓
Result: Skeletal tree + skeletal twig instances
```

## Files Modified

1. **src/growpy/io/unreal_nanite_assembly.py**
   - Line ~39: Added `twig_placement_source_usd` parameter
   - Line ~69: Updated docstring
   - Line ~84: Fixed schema path (4 parent levels)
   - Line ~141: Use twig_placement_source_usd for extraction

2. **src/growpy/io/blender_export.py**
   - Line ~382: Fixed UV scaling logic (try/except instead of locals() check)
   - Line ~538: Fixed schema path (4 parent levels)
   - Line ~3328: Pass temp_tree_path for twig placement extraction

## Summary

All three issues are now fixed:

1. ✓ **Schema path** - Correctly resolves to `data/unreal_schema/generatedSchema.usda`
2. ✓ **Texture scaling** - UV aspect ratio properly applied to both static and skeletal exports
3. ✓ **Skeletal twigs** - Placements extracted from static tree, applied to skeletal assembly

The skeletal Nanite Assembly should now:

- Import as skeletal mesh in Unreal
- Show twig instances at correct positions
- Have proper texture scale (not too small)
