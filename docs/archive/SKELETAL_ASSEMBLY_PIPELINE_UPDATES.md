# Skeletal Assembly Pipeline Updates

**Date**: October 27, 2025
**Status**: Complete ✅

## Overview

The GrowPy processing pipeline has been updated to generate skeletal nanite mesh assemblies that match the structure of the working demo files in [`data/working_assemblies_working_skel/`](data/working_assemblies_working_skel/).

## Key Changes

### 1. Twig Mount Bones Added to Tree Skeleton

**File**: `src/growpy/io/usd_builder.py`

**What Changed**:
- Added `add_twig_bones` parameter to `add_skeleton_to_usd()` function (default: True)
- Modified `_build_usdskel_from_bones()` to accept twig placement data
- After building the main skeleton (trunk + branches), the pipeline now:
  1. Extracts twig placements from the mesh face attributes
  2. Creates dedicated twig mount bones for each twig placement
  3. Attaches twig bones to nearest trunk/branch joint using hierarchical naming
  4. Stores twig-to-joint mapping in USD stage metadata

**Example Joint Structure**:
```
root
├── joint_1
│   ├── joint_2
│   │   ├── joint_3
│   │   └── twig_1         ← Dedicated twig mount bone
│   ├── branch_1
│   │   ├── branch_tip
│   │   └── twig_2         ← Dedicated twig mount bone
│   └── twig_0             ← Dedicated twig mount bone
```

**Benefits**:
- Each twig instance can be bound to a specific skeleton joint
- Enables proper skeletal animation in Unreal Engine
- Matches the working demo structure exactly

### 2. Nanite Assembly Twig Binding Updated

**File**: `src/growpy/io/unreal_nanite_assembly.py`

**What Changed**:
- Added `_extract_twig_joint_mapping_from_usd()` helper function
- Modified twig binding logic in `create_nanite_assembly_usd()` to:
  1. Extract twig joint mapping from tree USD metadata
  2. Bind each twig instance to its dedicated twig mount bone
  3. Fall back to nearest joint binding if mapping not found (legacy behavior)

**Binding Strategy**:
```python
# OLD: Bind to nearest existing joint
bind_joints.append(nearest_joint)

# NEW: Bind to dedicated twig mount bone
bind_joints.append(twig_joint_mapping[twig_key])  # e.g., "root/joint_1/twig_0"
```

**Benefits**:
- Exact twig positioning (no approximation error)
- Better skeletal animation behavior
- Matches working demo PointInstancer format

### 3. Test Script Created

**File**: `src/growpy/cli/test_skeletal_assembly.py`

**What It Does**:
- Creates a simple tree with 2 growth cycles (fast for testing)
- Exports tree mesh to USD
- Adds skeleton with twig mount bones
- Validates skeletal structure against working demo format
- Creates Nanite Assembly with bound twigs

**Run Test**:
```bash
# Make sure you're in the-grove conda environment
conda activate the-grove

# Run test
python src/growpy/cli/test_skeletal_assembly.py --output-dir data/output/test_assembly
```

## Technical Details

### Hierarchical Joint Naming

The pipeline now uses hierarchical joint paths that match the working demo:

```
Working Demo Format:
- root/joint_1/joint_2/joint_3
- root/joint_1/branch_1/branch_tip
- root/joint_1/twig_1

Current Pipeline (UPDATED):
- root/joint_0/joint_1/joint_2
- root/joint_0/branch_0/branch_tip
- root/joint_0/twig_0
```

### Multi-Joint Skinning

Both the demo and updated pipeline use `elementSize=2` for smooth deformation:

```python
primvars:skel:jointIndices = [1,0, 2,1, 3,2, ...]  # Each vertex bound to 2 joints
primvars:skel:jointWeights = [0.5,0.5, 0.5,0.5, ...]  # Blend weights
```

### Twig Metadata Storage

Twig joint mapping is stored in USD stage metadata:

```python
stage.SetMetadata("customLayerData", {
    "twig_joint_names": {
        "twig_long_0": "root/joint_1/twig_0",
        "twig_long_1": "root/joint_2/twig_1",
        "twig_short_0": "root/joint_1/branch_1/twig_2",
    }
})
```

## Usage

### Basic Workflow

1. **Convert Twigs** (if needed):
   ```bash
   python src/growpy/cli/convert_twigs.py \
       path/to/twigs.blend \
       --output-dir data/output/twigs \
       --species "Tree Species"
   ```

2. **Generate Tree with Skeleton**:
   ```python
   from growpy.io.usd_builder import build_tree_usd, add_skeleton_to_usd

   # Build and export tree mesh
   build_tree_usd(model, tree_usd_path, up_axis="Z")

   # Add skeleton with twig mount bones
   add_skeleton_to_usd(tree_usd_path, grove, add_twig_bones=True)
   ```

3. **Create Nanite Assembly**:
   ```python
   from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd

   create_nanite_assembly_usd(
       tree_usd_path=tree_usd_path,
       output_path=assembly_path,
       species_name="TreeSpecies",
       twig_usd_paths=twig_usd_map,
       use_skeletal_mesh=True,
   )
   ```

### Using Existing CLI Commands

The existing forest generation command now automatically uses the updated pipeline:

```bash
python src/growpy/cli/generate_forest.py \
    data/input/forest.csv \
    --quality high \
    --growth-cycle-limit 3 \
    --output-dir data/output/forest
```

**Note**: Use `--growth-cycle-limit 1-3` for test files to avoid large file sizes.

## Validation

Compare your generated files with the working demo:

**Working Demo Files**:
- `data/working_assemblies_working_skel/demo_tree_skel.usda`
- `data/working_assemblies_working_skel/demo_twig_skel.usda`
- `data/working_assemblies_working_skel/demo_assembly_external_ref.usda`

**Generated Files** (from test script):
- `data/output/test_assembly/test_tree.usda`
- `data/output/test_assembly/test_tree_assembly.usda`

**What to Check**:
1. ✅ Hierarchical joint names (root/joint_X/joint_Y)
2. ✅ Twig mount bones in skeleton (root/joint_X/twig_Y)
3. ✅ Multi-joint skinning (elementSize=2)
4. ✅ PointInstancer binds to twig bones
5. ✅ Uniform variability for bindJoints attribute

## Backward Compatibility

The changes are **backward compatible**:
- If `add_twig_bones=False`, the old behavior is preserved
- If twig joint mapping is not found, falls back to nearest joint binding
- Existing USD files without twig bones will still work (legacy mode)

## Known Limitations

1. **Growth Cycles**: For testing, use 1-3 growth cycles to avoid large files
2. **Twig Placement**: Requires face attributes (TwigLong, TwigShort, etc.) on tree mesh
3. **Coordinate System**: Currently assumes Z-up coordinate system

## References

- Working Demo: [`data/working_assemblies_working_skel/SKELETAL_ASSEMBLY_REFERENCE.md`](data/working_assemblies_working_skel/SKELETAL_ASSEMBLY_REFERENCE.md)
- USD Skeletal Schema: https://openusd.org/release/api/usd_skel_page_front.html
- Unreal Nanite Assemblies: https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine

## Next Steps

1. Test the pipeline with real tree species
2. Add texture and material support (currently bare bones)
3. Optimize skeleton bone count for large trees
4. Add support for animated skeletons (wind, growth)

---

**Questions or Issues?**
See the reference documentation or open an issue on the repository.
