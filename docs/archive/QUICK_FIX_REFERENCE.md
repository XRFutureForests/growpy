# Quick Reference: Skeletal Nanite Assembly Fix

**Issue Fixed**: Joint hierarchy not working in Unreal Engine  
**Root Cause**: Wrong UsdSkel attribute name (`jointParents` instead of `jointIndices`)  
**Solution**: Use standard `uniform int[] jointIndices` attribute  
**Status**: COMPLETE ✓

## The Fix (One Line)

Changed skeleton topology attribute name from `jointParents` to `jointIndices`.

## Why It Failed

UsdSkel specification requires:

```usda
uniform int[] jointIndices = [-1, 0, 1, 2, 3, ...]  # Parent index for each joint
```

We were using:

```usda
int[] jointParents = [-1, 0, 1, 2, 3, ...]  # Custom attribute (ignored by Unreal)
```

## How to Verify

```bash
# Check if file has correct attribute
grep "uniform int\[\] jointIndices" your_skeletal.usda

# Or use verification script
python src/verify_skel_simple.py your_skeletal.usda
```

## Testing in Unreal

1. **Import**: `data/output/joint_indices_fix_test/Western_redcedar/Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda`
2. **Open**: Skeleton Editor
3. **Check**: Bone hierarchy shows parent-child connections (not all flat under root)
4. **Test**: Rotate middle joint → all children should move together

## Expected Results

### Before Fix

- All bones appear as siblings of root
- No parent-child connections
- Rotating bone only moves that bone
- Mesh doesn't deform properly

### After Fix

- Proper tree hierarchy: root → trunk → branches
- Parent-child connections visible
- Rotating parent moves all children
- Mesh sections deform with their bones

## Files Changed

- `src/growpy/io/usd_builder.py` (lines ~535-545)
- `docs/archive/JOINT_INDICES_FIX.md` (detailed explanation)
- `docs/archive/SKELETAL_ASSEMBLY_COMPLETE.md` (full summary)
- `src/verify_skel_simple.py` (verification tool)

## Git Commits

- **351458f**: Main fix (attribute name change)
- **3da8acc**: Verification script
- **84b5c37**: Complete documentation

## Previous Related Fixes

This was the third and final fix for skeletal assemblies:

1. **92f8155**: Vertex-based binding (eliminated face conflicts)
2. **ea1c956**: Geodesic distance algorithm (direction-agnostic)
3. **351458f**: Correct attribute name (THIS FIX)

## Quick Commands

```bash
# Regenerate with fix
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/test.csv \
    --quality high \
    --output-dir data/output/test_with_fix \
    --growth-cycle-limit 3 \
    --formats usda \
    --clean-export

# Verify output
python src/verify_skel_simple.py \
    data/output/test_with_fix/Western_redcedar/*_skeletal.usda

# Check for correct attribute in USD file
grep "uniform int\[\] jointIndices" \
    data/output/test_with_fix/Western_redcedar/*_skeletal.usda
```

## Troubleshooting

### If Still Not Working in Unreal

1. **Verify USD has fix**:

   ```bash
   grep "jointParents\|jointIndices" your_skeletal.usda
   ```

   - Should show: `uniform int[] jointIndices`
   - Should NOT show: `jointParents`

2. **Check Unreal version**: Must be 5.7+ (skeletal Nanite requirement)

3. **Check console**: Look for warnings about skeleton topology

4. **Simplify test**: Try with growth-cycle-limit 2 (fewer joints)

### If Verification Script Fails

Common issues:

- File path wrong
- Not using skeletal file (*_skeletal.usda, not*_tree_only.usda)
- Old file generated before fix

### If Mesh Doesn't Deform

This is different from hierarchy issue. Check:

- Vertex binding (primvars:skel:jointIndices on mesh)
- Joint weights (primvars:skel:jointWeights)
- Geodesic distance algorithm working (commit ea1c956)

## Contact

If issues persist after applying this fix, provide:

1. Screenshot of Unreal's skeleton hierarchy view
2. Output of `python src/verify_skel_simple.py your_file.usda`
3. Any console errors from Unreal Engine
4. Unreal Engine version number

## Summary

**Problem**: Bones not connected to parent bones  
**Cause**: Wrong attribute name  
**Fix**: Use `uniform int[] jointIndices`  
**Result**: Proper skeletal hierarchy in Unreal ✓
