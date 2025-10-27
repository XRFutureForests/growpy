# bindJoints Restoration Complete

## Summary

Successfully restored bindJoints functionality in Nanite Assembly generation after discovering they are REQUIRED (not the cause of twig distortion).

## What Was Fixed

### 1. Reversed Wrong Diagnosis

- **Previous incorrect fix**: Removed bindJoints code assuming they caused twig distortion
- **Discovery**: Working demo `demo_assembly_external_ref.usda` HAS bindJoints and works correctly
- **Root cause**: bindJoints were missing/incorrect, not problematic

### 2. Fixed Twig USD Structure (`usd_builder.py`)

**File**: `src/growpy/io/usd_builder.py` lines 1075-1085

Added SkelBindingAPI to twig SkelRoot to match working demo:

```python
root_path = Sdf.Path("/Twig")
skel_root = UsdSkel.Root.Define(stage, root_path)
skel_root_prim = stage.GetPrimAtPath(root_path)

# Apply SkelBindingAPI to SkelRoot (required for proper binding)
UsdSkel.BindingAPI.Apply(skel_root_prim)
```

### 3. Restored bindJoints Creation (`unreal_nanite_assembly.py`)

**File**: `src/growpy/io/unreal_nanite_assembly.py` lines 325-370

Fixed through multiple iterations:

1. ✅ Restored code structure
2. ✅ Fixed variable scoping (use `placements.items()`)
3. ✅ Added `primvars_api = UsdGeom.PrimvarsAPI(instancer_prim)`
4. ✅ Fixed USD API signature (use `"constant"` string instead of `Sdf.VariabilityUniform`)

### 4. Added twig_key to Placement Data (`twig_placement.py`)

**File**: `src/growpy/io/twig_placement.py`

**Problem**: Placement dicts didn't include `twig_key` needed to correlate with skeleton metadata

**Solution**:

- Added counters: `twig_counters = {"twig_long": 0, "twig_short": 0, "twig_upward": 0, "twig_dead": 0}`
- Generate keys: `twig_key = f"{twig_type}_{twig_counters[twig_type]}"`
- Include in placement dict: `"twig_key": twig_key`

This matches the skeleton metadata format (`twig_long_0`, `twig_long_1`, etc.)

## Result

### Assembly Structure (Verified)

```
✅ NaniteAssemblySkelBindingAPI applied to PointInstancer
✅ bindJoints primvar with 200 joint paths
✅ bindJointWeights primvar with 200 weights (all 1.0)
✅ Twig SkelRoot has SkelBindingAPI applied
✅ Structure matches working demo
```

### Sample bindJoints Entry

```usd
token[] primvars:unreal:naniteAssembly:bindJoints = [
    "joint_0/joint_1/joint_2/joint_3/joint_4/joint_14/joint_15/joint_16/joint_17/joint_18/joint_19/twig_0",
    "joint_0/joint_1/joint_2/joint_3/joint_4/joint_14/joint_15/joint_16/joint_20/joint_21/joint_22/twig_1",
    ...
] (
    interpolation = "constant"
)
```

## Files Modified

1. `src/growpy/io/usd_builder.py` - Added SkelBindingAPI to twig SkelRoot
2. `src/growpy/io/unreal_nanite_assembly.py` - Restored bindJoints creation with correct USD API
3. `src/growpy/io/twig_placement.py` - Added twig_key to placement data

## Next Steps

1. ✅ **COMPLETED**: Restore bindJoints in PointInstancer
2. ✅ **COMPLETED**: Fix twig USD structure (SkelBindingAPI)
3. ✅ **COMPLETED**: Regenerate assembly with correct configuration
4. ⏸️ **PENDING**: Test in Unreal Engine 5.7
   - Import `westernredcedar_assembly.usda`
   - Test skeleton animation
   - Verify twigs follow skeleton correctly
   - Confirm no twig mesh distortion

## Expected Outcome

When imported into Unreal Engine 5.7, the assembly should:

- Not show bindJoints warnings in import log
- Correctly attach twig instances to tree skeleton joints
- Animate twigs with skeleton without distortion
- Maintain twig mesh integrity (no whole-mesh deformation)

The root cause of the original twig distortion issue is likely elsewhere in the pipeline (possibly related to how twig meshes themselves are skinned to their local skeleton, not the assembly binding).
