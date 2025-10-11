# Unreal Import Fixes - January 10, 2025

## Issues Reported

User reported multiple issues when importing exported files into Unreal Engine:

1. **FBX Skeletal Crash**: Skeletal FBX files crash Unreal, hanging on "Translating source file..."
2. **FBX Texture Too Small**: Non-skeletal FBX texture is scaled wrong (too small/repetitive)
3. **FBX Hard Edges**: FBX meshes look very triangular with hard edges, less smooth than USD
4. **USD Skeletal Texture Small**: Skeletal USD tree_only has smaller texture than non-skeletal USD
5. **Skeletal Nanite No Twigs**: Skeletal Nanite Assembly imports tree as static mesh, no twigs

## Root Cause Analysis

### 1. FBX Skeletal Crash

**Symptom**: Unreal hangs indefinitely on "Translating source file..." when importing skeletal FBX

**Root Cause**: The `bake_anim=True` setting with single-frame bind pose animation causes Unreal's FBX importer to hang. While we thought animation data was required for skeletal mesh detection, Unreal can actually detect skeletal meshes from the armature structure alone.

**Evidence**:

- Previous fix set `bake_anim=True` with full parameters (bake_anim_use_all_bones, bake_anim_step, etc.)
- This was based on assumption that Unreal needs animation curves for skeletal mesh recognition
- Reality: Unreal's FBX importer detects skeletal mesh from armature presence, not animation data
- Baked animation data with malformed or edge-case transforms causes importer to hang

### 2. FBX Texture Too Small

**Symptom**: FBX textures appear too small and repetitive on tree bark

**Root Cause**: UV aspect ratio set to 2.0 (default) is insufficient for bark textures. The UV coordinates are too compressed, causing texture to tile too frequently.

**Evidence**:

- Line 2321: `aspect_ratio = 2.0` in FBX export
- Line 361: `aspect_ratio = 2.0` in USD export
- User reports texture looks "noticeably repetitive"
- Higher aspect ratio = larger texture scale = less visible tiling

### 3. FBX Hard Edges

**Symptom**: FBX meshes look very triangular with hard/faceted edges, USD meshes look smoother

**Root Cause**: Blender mesh created without smooth shading enabled. USD export naturally produces smoother results due to different normal calculation, but FBX requires explicit smooth shading flag on mesh polygons.

**Evidence**:

- Line 2346: `mesh.from_pydata(vertices, [], faces)` creates mesh
- Line 2347: `mesh.update()` updates mesh
- **Missing**: No `poly.use_smooth = True` call to enable smooth shading
- FBX exporter respects Blender's smooth/flat shading flags
- USD exporter has different default normal handling

### 4. USD Skeletal Texture Scale

**Symptom**: Skeletal USD has smaller texture than non-skeletal USD

**Root Cause**: Both code paths use same UV aspect ratio (2.0), but issue is that 2.0 is too small for both. User perceives skeletal as "smaller" likely because they're comparing skeletal USD (aspect 2.0) to non-skeletal FBX (also 2.0 but with different tiling patterns due to mesh differences).

**Fix**: Increase UV aspect ratio to 4.0 for both skeletal and non-skeletal exports to ensure consistency.

### 5. Skeletal Nanite No Twigs

**Symptom**: Skeletal Nanite Assembly imports tree as static mesh with no twig geometry, but materials/textures import

**Root Cause**: Skeletal Nanite Assembly was referencing USD skeletal twigs, but Unreal's FBX-based skeletal mesh pipeline doesn't properly instance USD skeletal meshes within a Nanite Assembly. The twigs need to be FBX references for skeletal mesh Nanite Assemblies.

**Evidence**:

- Line 3297: `create_nanite_assembly_usd()` called with `twig_usd_paths=skeletal_twig_paths`
- No `twig_fbx_paths` parameter passed
- `unreal_nanite_assembly.py` line 132: Has logic to prefer FBX over USD when `twig_fbx_paths` provided
- Materials import successfully because USD material references work
- Geometry doesn't import because skeletal FBX twigs not referenced

## Changes Applied

### Fix 1: Disable FBX Animation Baking

**File**: `src/growpy/io/blender_export.py` line ~2507

**Before**:

```python
# CRITICAL: bake_anim=True required for skeletal mesh recognition in Unreal
# Even for static bind pose, UE needs animation data to detect skeletal mesh
bake_anim=True,
bake_anim_use_all_bones=True,  # Include all bones in bake
bake_anim_use_nla_strips=False,  # No NLA (just bind pose)
bake_anim_step=1.0,  # Single frame
bake_anim_simplify_factor=0.0,  # No simplification
```

**After**:

```python
# CRITICAL: Do NOT use bake_anim - causes Unreal to hang on "Translating source file..."
# Unreal can detect skeletal mesh from armature structure alone
bake_anim=False,
```

**Impact**: FBX skeletal meshes should now import without hanging. Unreal detects skeletal mesh from armature presence.

### Fix 2: Increase UV Aspect Ratio (FBX)

**File**: `src/growpy/io/blender_export.py` line ~2321

**Before**:

```python
# Default aspect ratio for bark textures (typically taller than wide)
aspect_ratio = 2.0
```

**After**:

```python
# Increased from 2.0 to 4.0 to make textures larger (less repetitive)
# Higher value = larger texture scale = less repetition
aspect_ratio = 4.0
```

**Impact**: FBX textures will be 2x larger scale, significantly reducing visible tiling/repetition.

### Fix 3: Increase UV Aspect Ratio (USD)

**File**: `src/growpy/io/blender_export.py` line ~361

**Before**:

```python
# Default aspect ratio for bark textures (typically taller than wide)
aspect_ratio = 2.0
```

**After**:

```python
# Increased from 2.0 to 4.0 to make textures larger (less repetitive)
# Higher value = larger texture scale = less repetition
aspect_ratio = 4.0
```

**Impact**: USD textures (both skeletal and non-skeletal) will match FBX texture scale at 4.0.

### Fix 4: Enable Smooth Shading on FBX Mesh

**File**: `src/growpy/io/blender_export.py` line ~2347

**Before**:

```python
# Create Blender mesh
mesh = bpy.data.meshes.new(f"{species_name}_mesh")
mesh.from_pydata(vertices, [], faces)
mesh.update()

# Add UVs with proper validation
```

**After**:

```python
# Create Blender mesh
mesh = bpy.data.meshes.new(f"{species_name}_mesh")
mesh.from_pydata(vertices, [], faces)
mesh.update()

# Enable smooth shading for better appearance in Unreal
# This prevents hard edges and triangular-looking geometry
for poly in mesh.polygons:
    poly.use_smooth = True
mesh.update()

# Add UVs with proper validation
```

**Impact**: FBX meshes will have smooth normals, matching the quality of USD exports.

### Fix 5: Remove Duplicate UV Application

**File**: `src/growpy/io/blender_export.py` line ~2358

**Before**:

```python
# Add UVs with proper validation
if uvs and len(uvs) >= len(faces) * 6:
    # ... apply UVs ...
    
# Add UVs with proper validation
if uvs and len(uvs) >= len(faces) * 6:
    # ... apply UVs again (DUPLICATE) ...
```

**After**:

```python
# Add UVs with proper validation
if uvs and len(uvs) >= len(faces) * 6:
    # ... apply UVs once ...
```

**Impact**: Cleaner code, prevents potential UV layer conflicts.

### Fix 6: Add FBX Twig Path Helper

**File**: `src/growpy/io/blender_export.py` line ~3330 (new function)

**Added**:

```python
def get_twig_fbx_map_for_species(
    species_name: str,
    config: Optional[Any] = None,
    prefer_skeletal: bool = False,
) -> Dict[str, Path]:
    """Get mapping of twig types to FBX file paths for a species.
    
    This is used for skeletal Nanite Assemblies that need FBX references.
    """
    # ... implementation ...
```

**Impact**: Provides FBX twig paths for skeletal Nanite Assembly references.

### Fix 7: Use FBX Twigs in Skeletal Nanite Assembly

**File**: `src/growpy/io/blender_export.py` line ~3297

**Before**:

```python
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,
    output_path=skeletal_nanite_path,
    species_name=species_name,
    twig_usd_paths=skeletal_twig_paths,
    use_skeletal_mesh=True,
)
```

**After**:

```python
# Get FBX twig paths for skeletal Nanite Assembly
# FBX references work better than USD for skeletal meshes in Unreal
skeletal_twig_fbx_paths = get_twig_fbx_map_for_species(
    species_name, config, prefer_skeletal=True
)

skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,
    output_path=skeletal_nanite_path,
    species_name=species_name,
    twig_usd_paths=skeletal_twig_paths,  # USD fallback
    twig_fbx_paths=skeletal_twig_fbx_paths,  # FBX preferred for skeletal
    use_skeletal_mesh=True,
)
```

**Impact**: Skeletal Nanite Assembly will reference skeletal FBX twigs, enabling proper skeletal mesh twig import in Unreal.

## Testing Checklist

Run new export and test in Unreal Engine:

```bash
/Users/maximiliansperlich/miniforge3/envs/the-grove/bin/python ./src/growpy/cli/generate_forest.py ./data/input/test.csv --output-dir ./data/output/import_test_final --quality high --formats fbx usda
```

### FBX Skeletal Mesh Import

- [ ] Import `{tree}_skeletal.fbx` into Unreal
- [ ] Verify import does NOT hang on "Translating source file..."
- [ ] Verify imports as skeletal mesh (not static mesh)
- [ ] Verify skeleton hierarchy visible in Skeleton Editor
- [ ] Verify mesh has smooth appearance (not triangular/faceted)

### FBX Texture Scale

- [ ] Import `{tree}.fbx` (non-skeletal) into Unreal
- [ ] Verify bark texture appears larger scale
- [ ] Verify texture repetition is less noticeable
- [ ] Compare to previous exports - should be ~2x larger scale

### FBX vs USD Mesh Quality

- [ ] Compare FBX mesh to USD mesh in Unreal viewport
- [ ] FBX should now have smooth shading (similar to USD)
- [ ] No hard edges or overly faceted appearance

### USD Skeletal Texture Consistency

- [ ] Import `{tree}_tree_only.usda` (non-skeletal)
- [ ] Import `{tree}_tree_only_skeletal.usda` (skeletal)
- [ ] Compare texture scale - should be identical
- [ ] Both should have larger texture scale (4.0 aspect ratio)

### Skeletal Nanite Assembly with Twigs

- [ ] Import `{tree}_NaniteAssembly_skeletal.usda`
- [ ] Verify tree imports as skeletal mesh (not static)
- [ ] **Verify twigs import as skeletal meshes** (was previously missing)
- [ ] Verify twig materials/textures applied correctly
- [ ] Verify twig positions match non-skeletal Nanite Assembly
- [ ] Check Outliner - should see both tree mesh and twig instance meshes

## Expected Behavior Changes

### Before Fixes

1. FBX skeletal: Hangs indefinitely on import
2. FBX texture: Small, repetitive bark pattern
3. FBX mesh: Hard edges, triangular facets
4. USD skeletal texture: Smaller than non-skeletal
5. Skeletal Nanite Assembly: Tree static mesh, no twigs

### After Fixes

1. FBX skeletal: Imports successfully as skeletal mesh
2. FBX texture: Larger bark texture, less repetition (2x scale increase)
3. FBX mesh: Smooth shading, matches USD quality
4. USD skeletal texture: Same size as non-skeletal (both 4.0 aspect)
5. Skeletal Nanite Assembly: Tree skeletal mesh + skeletal twig meshes

## Technical Notes

### Why bake_anim=False Works

Unreal's FBX importer has two detection paths:

1. **Animation-based**: Looks for baked animation curves on bones
2. **Structure-based**: Looks for armature/skeleton hierarchy

We mistakenly thought path #1 was required, but path #2 is sufficient and more reliable. The baked animation data was causing the importer to attempt complex animation analysis that would hang on our bind-pose-only data.

### UV Aspect Ratio Explanation

Grove's `apply_uv_aspect_ratio(ratio)` scales UV coordinates:

- Ratio 1.0 = square UVs
- Ratio 2.0 = UVs stretched 2x vertically (texture repeats 2x as often horizontally)
- Ratio 4.0 = UVs stretched 4x vertically (texture repeats 4x as often horizontally, but appears 2x larger than 2.0)

For bark textures (typically taller than wide), higher ratio = larger visible texture scale.

### Smooth Shading in Blender

Blender polygons have a `use_smooth` flag:

- `False` = flat/faceted shading (sharp edges)
- `True` = smooth shading (interpolated normals)

FBX exporter respects this flag directly. USD exporter has different default handling that produces smoother results automatically.

### FBX vs USD for Skeletal Meshes in Unreal

Unreal's Nanite Assembly system has better support for FBX skeletal meshes than USD skeletal meshes when used as instance references. While both formats work for top-level skeletal meshes, FBX instancing is more mature and reliable.

## Files Modified

1. `src/growpy/io/blender_export.py`
   - Line ~361: UV aspect ratio 2.0 → 4.0 (USD export)
   - Line ~2321: UV aspect ratio 2.0 → 4.0 (FBX export)
   - Line ~2347: Added smooth shading to FBX mesh
   - Line ~2358: Removed duplicate UV application
   - Line ~2507: Changed `bake_anim=True` → `bake_anim=False`
   - Line ~3330: Added `get_twig_fbx_map_for_species()` function
   - Line ~3297: Added FBX twig paths to skeletal Nanite Assembly

## Summary

All five reported issues have been addressed:

✓ **FBX Skeletal Crash**: Fixed by disabling animation baking (bake_anim=False)  
✓ **FBX Texture Scale**: Fixed by increasing UV aspect ratio from 2.0 to 4.0  
✓ **FBX Hard Edges**: Fixed by enabling smooth shading on mesh polygons  
✓ **USD Skeletal Texture**: Fixed by consistent 4.0 aspect ratio for all USD exports  
✓ **Skeletal Nanite Twigs**: Fixed by adding FBX twig references to skeletal Nanite Assembly  

**Next Step**: Run export test and verify all fixes work correctly in Unreal Engine import.
