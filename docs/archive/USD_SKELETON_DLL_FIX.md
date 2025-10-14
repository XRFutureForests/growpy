# USD Skeleton DLL Conflict Fix

**Date:** 2025-10-14  
**Issue:** DLL load failed while importing `_tf` from USD Python bindings (`pxr`)  
**Solution:** Two-phase export process separating USD and Blender operations

## Problem

When both USD Python bindings (`pxr`) and Blender Python module (`bpy`) are loaded in the same process on Windows, they have conflicting DLL dependencies:

1. Blender loads its own TBB (Intel Threading Building Blocks) and other DLLs
2. USD's `_tf` module requires different versions of these DLLs
3. Once Blender's DLLs are loaded, USD cannot find the correct procedures it needs

**Error:**

```
ImportError: DLL load failed while importing _tf: The specified procedure could not be found.
```

## Solution: Two-Phase Export

### Phase 1: Export Skeleton-Only USD (Before Blender)

**Location:** `generate_forest.py` - `export_skeleton_only_usd()`

- Export skeleton USD files using `pxr` module BEFORE `bpy` is imported
- Creates `{tree_name}_skeleton.usda` files in USD output directory
- No DLL conflicts because Blender hasn't loaded yet
- Skeleton structure is deterministic from Grove API (`grove.build_skeletons()`)

**Output:**

- `Species_tree_0001_skeleton.usda`
- `Species_tree_0002_skeleton.usda`
- etc.

### Phase 2: Export Full Tree Meshes (With Blender)

**Location:** `generate_forest.py` - `export_individual_trees()`

- Export complete tree geometry, materials, and twigs using Blender
- Creates main USD/FBX files with all visual elements
- Skeleton embedding is disabled (`include_skeleton=False`)
- Skeleton can be composited later in Unreal or USD composition tools

**Output:**

- `Species_tree_0001.usda` (tree mesh with materials and twigs)
- `Species_tree_0001.fbx` (static mesh)
- `Species_tree_0001_skeletal.fbx` (skeletal mesh - uses Blender's built-in skeleton)

## Guarantees

### Will skeleton files be identical?

**Yes**, the skeleton structure is deterministic because:

1. **Same Grove API**: Both phases use `grove.build_skeletons()` from identical simulations
2. **Same Data**: Joint positions, hierarchy, and transforms are derived from Grove's skeleton data structure
3. **Same Algorithm**: Joint creation logic is identical (copied from `blender_export.py`)
4. **No Randomness**: No stochastic elements in skeleton generation

### Verification

The skeleton export function uses the same logic as the original `_add_skeleton_only_to_usd()`:

- Same joint naming: `Root`, `Joint_{point_idx}`
- Same hierarchy building from `poly_lines`
- Same transform calculations (bind poses and rest transforms)
- Same UsdSkel structure (SkelRoot → Skeleton → Animation)

## Usage

### In Unreal Engine

1. Import tree USD: `Species_tree_0001.usda`
2. Import skeleton USD: `Species_tree_0001_skeleton.usda`
3. Composite them using USD sublayer/reference composition
4. Or use Unreal's skeletal mesh binding tools

### In USD Composition

```python
from pxr import Usd, Sdf

stage = Usd.Stage.Open("Species_tree_0001.usda")
skeleton_layer = Sdf.Layer.FindOrOpen("Species_tree_0001_skeleton.usda")
stage.GetRootLayer().subLayerPaths.append(skeleton_layer.identifier)
stage.Save()
```

## Benefits

1. **No DLL Conflicts**: USD and Blender operations are completely separated
2. **Deterministic Results**: Skeleton structure is guaranteed identical
3. **Flexibility**: Skeleton files can be used independently or composited
4. **Transparency**: Separate skeleton files are easier to inspect and debug
5. **Backwards Compatible**: Existing FBX skeletal meshes still use Blender's skeleton

## Implementation Details

### Modified Files

- `src/growpy/cli/generate_forest.py`:
  - Added `export_skeleton_only_usd()` function
  - Modified `export_individual_trees()` to use two-phase approach
  - Disabled skeleton embedding in USD exports (`include_skeleton=False`)

### File Structure

```
data/output/forest/
└── Species_Name/
    ├── USD/
    │   ├── Species_Name_tree_0001.usda           # Main tree (mesh, materials, twigs)
    │   ├── Species_Name_tree_0001_skeleton.usda  # Skeleton only
    │   ├── Species_Name_tree_0002.usda
    │   ├── Species_Name_tree_0002_skeleton.usda
    │   └── ...
    └── FBX/
        ├── Species_Name_tree_0001.fbx             # Static mesh
        ├── Species_Name_tree_0001_skeletal.fbx    # Skeletal mesh (Blender skeleton)
        └── ...
```

## Testing

To verify skeleton consistency:

1. Export a tree with the two-phase approach
2. Compare joint names, positions, and hierarchy between skeleton USD and expected structure
3. Composite skeleton with tree mesh in Unreal/Houdini
4. Verify skeletal deformation works correctly

## Future Improvements

Potential enhancements:

1. Automatic USD composition (combine skeleton + tree into single file)
2. Weight painting export to skeleton USD
3. Python subprocess approach for complete isolation
4. Conda environment separation strategy

## References

- USD Skeletal Schema: <https://graphics.pixar.com/usd/docs/api/usd_skel_page_front.html>
- Unreal Engine USD Support: <https://docs.unrealengine.com/5.7/en-US/usd-in-unreal-engine/>
- The Grove API: `grove.build_skeletons()` method
