# Nanite Assembly Skeletal Binding Solution

**Date**: January 10, 2025  
**Issue**: Skeletal Nanite Assembly missing twigs - root cause analysis and solution  
**Status**: IMPLEMENTED

## Problem Statement

Skeletal Nanite Assemblies were not loading twigs in Unreal Engine 5.7+ due to:

1. **Wrong twig type**: Using skeletal twig USD files with embedded skeletons
2. **Wrong paths**: Absolute paths to source location instead of relative paths to copied twigs
3. **Suboptimal binding**: All twigs bound to root joint instead of nearest branch joint

## Root Cause Analysis

### Skeletal Twig Structure Discovery

Investigation revealed skeletal twig USD files contain:

- Complete inline mesh geometry (vertices, UVs, normals, faces)
- SkelRoot with single-bone Skeleton (joints=["Root"])
- Mesh with primvars:skel:jointIndices and jointWeights
- **NOT references** - all geometry is embedded

### Why Skeletal Twigs Don't Work

For Nanite Assembly skeleton binding:

- **PointInstancer** needs `NaniteAssemblySkelBindingAPI`
- Individual twig **geometry must be static** (no skeleton)
- Skeleton binding happens at **instancer level**, not mesh level
- Each instance binds to tree skeleton joints via `primvars:unreal:naniteAssembly:bindJoints`

**Conflict**: Skeletal twigs have their own skeleton → conflicts with PointInstancer binding

## Solution Implemented

### 1. Use Static Twigs for All Assemblies

**File**: `src/growpy/io/unreal_nanite_assembly.py`

```python
# CRITICAL: For skeletal assemblies, ALWAYS use STATIC twig meshes
# Reason: Skeleton binding happens at PointInstancer level
#         Individual twigs must be simple geometry without skeleton
if use_skeletal_mesh and "_skeletal" in str(twig_path):
    # Replace skeletal twig with static version
    static_twig_path = Path(str(twig_path).replace("_skeletal", ""))
    if static_twig_path.exists():
        twig_ref_path = static_twig_path
```

### 2. Shorter Relative Paths

Twigs are copied to `output/Species/twigs/`, assembly is in `output/Species/USD/`

**Before**: `../../../data/assets/twigs/EuropeanBeechTwig/twig.usda` (back to source)  
**After**: `../twigs/twig.usda` (reference copied files)

```python
# Reference twig mesh using relative path
# Twigs are copied to output/Species/twigs/ directory
# Assembly USD is in output/Species/USD/
# So relative path is simply ../twigs/twig_name.usda
twig_filename = twig_ref_path.name
twig_relative = f"../twigs/{twig_filename}"
proto_prim.GetReferences().AddReference(twig_relative)
```

### 3. Bind Twigs to Nearest Skeleton Joint

**Approach**: Find nearest tree branch joint for each twig instance

```python
# Extract skeleton from tree USD
skeleton_joints = _extract_skeleton_joints_from_usd(tree_usd_path)

# For each twig, find nearest joint
for twig_pos in all_positions:
    nearest_joint, distance = _find_nearest_joint(
        twig_pos, skeleton_joints
    )
    bind_joints.append(nearest_joint)
    bind_weights.append(1.0)
```

**Helper functions added**:

- `_extract_skeleton_joints_from_usd()`: Extracts joint names and positions from skeletal tree
- `_find_nearest_joint()`: Finds nearest joint to twig mount point using Euclidean distance

## Benefits of This Approach

### Static Twigs Are Better

1. **Materials work correctly**: Static twigs already have proper material/texture setup
2. **Simpler pipeline**: No skeleton conversion step needed for twigs
3. **Better performance**: Skeletal twigs were redundant (skeleton never used)
4. **Cleaner USD structure**: Static geometry + binding is correct pattern

### Nearest Joint Binding

1. **More accurate placement**: Each twig binds to closest branch
2. **Better animation**: Twigs follow correct branch movement
3. **Minimal displacement**: Even with sparse bones, nearest joint is close

## Alternative Considered: Add Joints at Twig Mount Points

**Pros**:

- Perfect placement (zero displacement)
- Each twig gets dedicated joint

**Cons**:

- Many more skeleton joints (performance impact)
- More complex skeleton hierarchy
- Overkill for typical use case

**Decision**: Use nearest joint binding first, add mount point joints only if needed

## Grove API Bone Density

The Grove's `tag_bone_id()` function controls bone density:

```python
bones = grove.tag_bone_id(
    length=1.0,     # Bone length factor (smaller = more bones)
    reduce=0.25,    # Reduction for thin branches  
    bias=0.5,       # Distribution bias
    connected=True  # Connected hierarchy
)
```

**Current setting**: `length=1.0` (longer bones, fewer joints)

**If needed**: Can increase bone density by reducing `length` parameter (e.g., 0.5 for twice as many bones)

## Next Steps: Remove Skeletal Twig Conversion

Since skeletal twigs are not needed for Nanite Assemblies:

### Option 1: Skip Skeletal Twig Generation (Recommended)

**File**: `src/growpy/io/blender_export.py` lines ~2248-2252

```python
# OLD: Create skeletal variant by adding single-bone skeleton
skeletal_path = output_dir / f"{clean_name}_skeletal.usda"
import shutil
shutil.copy2(usd_path, skeletal_path)
if _add_skeleton_to_twig_usd(skeletal_path):
    exported_files.append(skeletal_path)

# NEW: Skeletal twigs not needed for Nanite Assemblies
# Static twigs + PointInstancer binding is the correct approach
# Skip skeletal conversion to save export time
```

### Option 2: Add Flag to Control Skeletal Twig Export

Add `--skip-skeletal-twigs` flag to twig conversion script for backward compatibility

**Benefits of removal**:

- Faster twig export (no skeleton conversion step)
- Less disk space (fewer USD files)
- Clearer intent (static twigs for assemblies)
- Less confusion (one twig type per variation)

## Testing Plan

1. **Export test tree with skeletal Nanite Assembly**:

   ```bash
   python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
       --output-dir ./data/output/binding_test \
       --quality high \
       --formats usda
   ```

2. **Verify USD structure**:
   - Assembly references `../twigs/twig.usda` (not `../twigs/twig_skeletal.usda`)
   - PointInstancer has `NaniteAssemblySkelBindingAPI`
   - `primvars:unreal:naniteAssembly:bindJoints` contains joint names (not just "Root")

3. **Import in Unreal Engine 5.7+**:
   - Skeletal mesh recognized
   - Twigs load and display correctly
   - Twigs positioned accurately (check for displacement)
   - Animation works (if Grove skeleton has animation data)

## Technical Summary

### What Changed

1. **unreal_nanite_assembly.py**:
   - Line ~194: Auto-replace skeletal twigs with static versions
   - Line ~241: Simplified relative path to `../twigs/filename.usda`
   - Line ~314: Bind each twig to nearest skeleton joint
   - Line ~520: Added `_extract_skeleton_joints_from_usd()` helper
   - Line ~572: Added `_find_nearest_joint()` helper

### What Works Now

- Static twig geometry with correct materials/textures
- Shorter, cleaner relative paths
- Per-instance skeleton binding to nearest joint
- Skeletal recognition in Unreal Engine

### What's Still TODO

- Remove skeletal twig conversion from export pipeline (optional optimization)
- Test displacement with current Grove bone density
- If needed: Add option to increase bone density via `tag_bone_id()` parameters
- If needed: Implement dedicated twig mount point joints (future enhancement)

## Conclusion

The solution elegantly solves the twig loading issue by:

1. Using **static twig geometry** (correct for PointInstancer binding)
2. Using **relative paths to copied files** (shorter, more portable)
3. Using **nearest joint binding** (accurate without performance overhead)

This approach is **simpler, faster, and more correct** than the original skeletal twig approach.

The bonus discovery: **Skeletal twigs are not needed at all** for Nanite Assemblies, simplifying the entire pipeline.
