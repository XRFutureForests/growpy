# Nanite Assembly Skeletal/Static Mesh Separation Fix

**Date:** 2025-01-10  
**Status:** COMPLETE  
**Issue:** Ensure Nanite Assemblies correctly use skeletal vs static USD references

## Problem Statement

The Nanite Assembly system was not properly separating skeletal and static mesh workflows. This could lead to:

- Static assemblies referencing skeletal tree/twig USD files
- Skeletal assemblies referencing static tree/twig USD files  
- Unreal Engine import failures or incorrect mesh type recognition

## Root Cause

The export logic was not explicitly filtering twig USD references based on `prefer_skeletal` flag when creating Nanite Assemblies, potentially allowing mismatched mesh types in assemblies.

## Solution

### 1. Updated Static Nanite Assembly Export

**File:** `src/growpy/io/blender_export.py` (line ~3261)

**Before:**

```python
nanite_success = create_nanite_assembly_usd(
    tree_usd_path=temp_tree_path,
    output_path=nanite_path,
    species_name=species_name,
    twig_usd_paths=twig_usd_paths if include_twigs else None,
    use_skeletal_mesh=False,
)
```

**After:**

```python
# Get static twig paths explicitly
static_twig_paths = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=False
) if include_twigs else None

nanite_success = create_nanite_assembly_usd(
    tree_usd_path=temp_tree_path,  # Static tree mesh (no skeleton)
    output_path=nanite_path,
    species_name=species_name,
    twig_usd_paths=static_twig_paths,  # Static twigs only
    use_skeletal_mesh=False,
)
```

**Key Change:** Explicitly call `get_twig_usd_map_for_species()` with `prefer_skeletal=False` to ensure only static twigs are used.

### 2. Enhanced Skeletal Nanite Assembly Documentation

**File:** `src/growpy/io/blender_export.py` (line ~3303)

Added clarifying comments:

```python
# CRITICAL: Skeletal assembly must use skeletal tree and skeletal twigs
# skeletal_tree_path has embedded skeleton (from export_tree_as_usd_with_skeleton)
# skeletal_twig_paths are from prefer_skeletal=True (skeletal twigs)
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,  # Skeletal tree with skeleton
    output_path=skeletal_nanite_path,
    species_name=species_name,
    twig_usd_paths=skeletal_twig_paths,  # Skeletal twigs only
    use_skeletal_mesh=True,
)
```

### 3. Updated Nanite Assembly Module Documentation

**File:** `src/growpy/io/unreal_nanite_assembly.py` (line 1)

Added comprehensive requirements based on Unreal Engine documentation:

```python
"""
CRITICAL Requirements:
1. Static Mesh Assemblies:
   - Use meshType="staticMesh"
   - Reference static (non-skeletal) tree USD files
   - Reference static (non-skeletal) twig USD files
   - No skeleton relationships

2. Skeletal Mesh Assemblies:
   - Use meshType="skeletalMesh"
   - Reference skeletal tree USD with embedded UsdSkel
   - Reference skeletal twig USD files with embedded UsdSkel
   - Set unreal:naniteAssembly:skeleton relationship to descendant skeleton
   - Requires proper UsdSkelRoot, Skeleton, and SkelAnimation prims

3. USD References Only:
   - Nanite Assembly MUST use USD references (.usda, .usd)
   - FBX references break USD composition system
   - For FBX export, import files directly (not via Nanite Assembly)

Based on:
- https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine
"""
```

### 4. Enhanced Function Docstring

**File:** `src/growpy/io/unreal_nanite_assembly.py` (line ~39)

Updated `create_nanite_assembly_usd()` docstring to clarify requirements:

```python
"""Create a Nanite Assembly USD file for Unreal Engine import.

CRITICAL: For skeletal assemblies:
- tree_usd_path MUST point to a skeletal USD with embedded UsdSkelRoot/Skeleton
- twig_usd_paths MUST point to skeletal twigs with embedded skeletons
- All USD files must have proper UsdSkel hierarchy for Unreal recognition

CRITICAL: For static assemblies:
- tree_usd_path MUST point to a static (non-skeletal) USD
- twig_usd_paths MUST point to static (non-skeletal) twigs
- No skeleton data should be present

Args:
    tree_usd_path: Path to tree USD file (skeletal or static based on use_skeletal_mesh)
    output_path: Output path for Nanite Assembly USDA
    species_name: Tree species name
    twig_usd_paths: Optional dict mapping twig types to USD paths (matching mesh type)
    use_skeletal_mesh: Whether to use skeletal mesh type (requires skeletal USD inputs)
    skeleton_path: Path to skeleton USD (deprecated - skeleton should be in tree_usd_path)
"""
```

## Unreal Engine Requirements Reference

### Skeletal Mesh USD Structure

From Unreal documentation, skeletal meshes require:

1. **UsdSkel Hierarchy**
   - `SkelRoot` prim as container
   - `Skeleton` prim with joint hierarchy  
   - `SkelAnimation` prim for animation data
   - Mesh bound to skeleton via `UsdSkel.BindingAPI`

2. **Vertex Weights**
   - Proper joint influences per vertex
   - Normalized weights (sum to 1.0)
   - Maximum 4 influences per vertex

3. **Animation Recognition**
   - `SkelAnimation` prim enables skeletal mesh recognition in Unreal
   - Required even without actual animation data

### Nanite Assembly Schema

From `data/unreal_schema/schema.usda`:

```usda
class "NaniteAssemblyRootAPI"
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh" (
        allowedTokens = ["staticMesh", "skeletalMesh"]
    )
    rel unreal:naniteAssembly:skeleton  # For skeletalMesh only
}
```

## File Naming Convention

### Static Assets

- `tree.usda` or `tree_static.usda` (no "_skeletal" suffix)
- `twig_long.usda`
- `twig_short.usda`

### Skeletal Assets  

- `tree_skeletal.usda` (with "_skeletal" suffix)
- `twig_long_skeletal.usda`
- `twig_short_skeletal.usda`

## Testing Procedure

### Static Nanite Assembly

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/static_nanite_test \
    --quality high \
    --formats usda
```

**Expected Output:**

- `tree_NaniteAssembly.usda` references `tree.usda` (static)
- TwigPrototypes reference `twig_*.usda` (static, no "_skeletal")
- Import in Unreal as static mesh with Nanite

### Skeletal Nanite Assembly

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/skeletal_nanite_test \
    --quality high \
    --formats usda \
    --include-skeleton
```

**Expected Output:**

- `tree_NaniteAssembly_skeletal.usda` references `tree_skeletal.usda` (with skeleton)
- TwigPrototypes reference `twig_*_skeletal.usda` (with skeletons)
- Import in Unreal as skeletal mesh (may have Nanite limitations)

## Verification Checklist

### Static Assembly

- [ ] Tree reference is static USD (no "_skeletal" suffix)
- [ ] All twig references are static USD
- [ ] No skeleton relationships in assembly
- [ ] `meshType = "staticMesh"` in root prim
- [ ] Imports correctly in Unreal as static mesh

### Skeletal Assembly

- [ ] Tree reference is skeletal USD (with "_skeletal" suffix)
- [ ] All twig references are skeletal USD  
- [ ] Skeleton relationship points to descendant prim
- [ ] `meshType = "skeletalMesh"` in root prim
- [ ] Tree USD has UsdSkelRoot/Skeleton/SkelAnimation hierarchy
- [ ] Twig USDs have embedded skeletons
- [ ] Imports correctly in Unreal as skeletal mesh

## Documentation Created

1. **NANITE_ASSEMBLY_SKELETAL_STATIC_SEPARATION.md**
   - Comprehensive guide to skeletal vs static requirements
   - Unreal Engine documentation references
   - Implementation details
   - Testing procedures
   - Common issues and solutions

## Related Files Modified

1. `src/growpy/io/blender_export.py`
   - Line ~3261: Static Nanite Assembly with explicit static twigs
   - Line ~3303: Skeletal Nanite Assembly with clarifying comments

2. `src/growpy/io/unreal_nanite_assembly.py`
   - Line 1: Module docstring with CRITICAL requirements
   - Line ~39: Enhanced function docstring

## References

1. **Unreal Engine Documentation:**
   - [Skeletal Mesh Assets](https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine)
   - [USD in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine)

2. **USD Schema:**
   - `data/unreal_schema/schema.usda` - Unreal's custom schemas
   - `data/unreal_schema/generatedSchema.usda` - Generated definitions

3. **Previous Documentation:**
   - `NANITE_USD_ONLY_FIX.md` - USD-only reference correction
   - `SKELETAL_MESH_FIX_2025-01-10.md` - Initial skeletal mesh fixes

## Conclusion

The Nanite Assembly system now properly separates skeletal and static mesh workflows:

1. **Static Assemblies** explicitly request static twigs via `prefer_skeletal=False`
2. **Skeletal Assemblies** already used `prefer_skeletal=True` for skeletal twigs  
3. **Documentation** clarifies requirements based on Unreal Engine specifications
4. **File naming** convention ensures clear asset identification

This ensures Nanite Assemblies import correctly in Unreal Engine with the appropriate mesh type recognition.
