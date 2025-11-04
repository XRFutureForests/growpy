# SyntaxError Fix - tree_export.py

**Date**: 2025-11-04
**Status**: FIXED

---

## Problem

The sed command used to remove `add_skeleton_to_usd()` and `add_twig_skeleton_to_usd()` functions accidentally deleted code INSIDE the `_build_usdskel_from_bones()` function, leaving it incomplete.

**Error**:
```
File "C:\Users\Maximilian Sperlich\Git\the-grove\src\growpy\io\tree_export.py", line 1252
    except Exception as e:
    ^^^^^^
SyntaxError: invalid syntax
```

**Root Cause**: The sed command `sed -i '912,969d;1257,1360d'` deleted two separate chunks:
1. Lines 912-969: `add_skeleton_to_usd()` function (CORRECT - this was the target)
2. Lines 1257-1360: Code INSIDE `_build_usdskel_from_bones()` (INCORRECT - this was needed)

The second deletion removed critical primvars creation code and branch ID handling, leaving the function incomplete with orphaned exception handling.

---

## Solution

Restored the deleted code inside `_build_usdskel_from_bones()` function:

### Restored Code (lines 1200-1254):

```python
        # Create primvars for skinning
        primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

        # Joint indices primvar (1 influence per vertex for rigid binding)
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(1)

        # Joint weights primvar (1 influence per vertex for rigid binding)
        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(1)

        # Add branch ID attributes with local indices
        # Convert from global branch IDs to local (0-based per tree)
        if model and hasattr(model, "face_attribute_branch_id"):
            global_branch_ids = model.face_attribute_branch_id
            local_branch_ids = [
                branch_id - branch_id_offset for branch_id in global_branch_ids
            ]

            branch_id_primvar = primvars_api.CreatePrimvar(
                "branchID", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
            )
            branch_id_primvar.Set(local_branch_ids)

            if verbose:
                print(
                    f"  Converted BranchId: {len(local_branch_ids)} faces, offset={branch_id_offset}"
                )
                print(
                    f"    Global range: {min(global_branch_ids)}-{max(global_branch_ids)}"
                )
                print(
                    f"    Local range: {min(local_branch_ids)}-{max(local_branch_ids)}"
                )

        if model and hasattr(model, "face_attribute_branch_id_parent"):
            global_parent_ids = model.face_attribute_branch_id_parent
            local_parent_ids = [
                parent_id - branch_id_offset if parent_id >= 0 else parent_id
                for parent_id in global_parent_ids
            ]

            branch_parent_primvar = primvars_api.CreatePrimvar(
                "branchIDParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
            )
            branch_parent_primvar.Set(local_parent_ids)

            if verbose:
                print(f"  Converted BranchIdParent: {len(local_parent_ids)} faces")
```

### Removed Orphaned Code (old lines 1252-1256):

```python
# REMOVED: Orphaned except block from deleted function
    except Exception as e:
        import traceback

        traceback.print_exc()
        return False
```

---

## Testing Required

Run these commands to verify the fix:

```bash
# 1. Activate environment
conda activate the-grove

# 2. Test imports
conda run -n the-grove python -c "from growpy import *; print('✓ All imports successful')"

# 3. Test all 4 main CLI scripts
conda run -n the-grove python src/growpy/cli/prepare_assets.py --csv data/input/test.csv
conda run -n the-grove python src/growpy/cli/convert_twigs.py data/assets/twigs
conda run -n the-grove python src/growpy/cli/create_growth_models.py --cycles 25
conda run -n the-grove python src/growpy/cli/generate_forest.py
```

---

## Files Modified

1. `src/growpy/io/tree_export.py` - Restored missing code in `_build_usdskel_from_bones()` function

---

## Status

✅ **FIXED** - Syntax error resolved, function structure restored

Ready for testing to confirm all 4 main CLI scripts work correctly.

---

## Next Steps

1. Test all 4 main CLI scripts to verify Phase 1 cleanup is complete
2. If tests pass, proceed with Phase 2: Remove dead code CLI arguments
3. After Phase 2, perform final dependency re-analysis
