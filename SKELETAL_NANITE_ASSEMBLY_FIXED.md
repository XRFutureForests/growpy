# Skeletal Nanite Assembly Fix - January 2025

## Problem Summary

After fixing the tree skeleton to use hierarchical joint names (commit fixing the tree skeleton structure), the skeletal Nanite Assembly broke because it was still referencing **flat joint names** instead of **hierarchical joint paths**.

### Symptoms

- Tree skeleton file (`*_tree_only_skeletal.usda`) worked correctly with hierarchical joint names:
  - `["joint_0", "joint_0/joint_1", "joint_0/joint_1/joint_2", "joint_0/joint_1/joint_2/joint_3", "joint_0/joint_1/joint_2/joint_3/joint_4"]`
- Skeletal Nanite Assembly (`*_NaniteAssembly_skeletal.usda`) used flat name:
  - `primvars:unreal:naniteAssembly:bindJoints = ["joint_4"]`
- **Result**: Unreal couldn't find the joint because names didn't match

## Root Cause

Two locations in the code were stripping the hierarchical path from joint names:

1. **`src/growpy/io/unreal_nanite_assembly.py` line 349**:

   ```python
   joint_name = nearest_joint.split("/")[-1]  # "joint_0/joint_1/joint_4" -> "joint_4"
   ```

2. **`src/growpy/io/blender_export.py` line 3466**:

   ```python
   joint_name = nearest_joint.split("/")[-1]  # "joint_0/joint_1/joint_4" -> "joint_4"
   ```

Both locations had comments claiming this was a "VIDEO REQUIREMENT" for flat joint names, but this contradicted the working skeleton format from commit 5eef35188df7d455fd58bb97abad740009b4c3ea.

## Solution

Changed both locations to use the **full hierarchical joint path** without stripping:

### Fix 1: unreal_nanite_assembly.py

```python
# BEFORE (line 349)
joint_name = nearest_joint.split("/")[-1]

# AFTER
joint_name = nearest_joint  # Use full hierarchical path
```

### Fix 2: blender_export.py

```python
# BEFORE (line 3466)
joint_name = nearest_joint.split("/")[-1]

# AFTER
joint_name = nearest_joint  # Use full hierarchical path
```

## Verification

After the fix, the skeletal Nanite Assembly now correctly references hierarchical joint paths:

```usd
uniform token[] primvars:unreal:naniteAssembly:bindJoints = ["joint_0/joint_1/joint_2/joint_3/joint_4"]
```

This matches the skeleton structure in the tree file:

```usd
uniform token[] joints = ["joint_0", "joint_0/joint_1", "joint_0/joint_1/joint_2", "joint_0/joint_1/joint_2/joint_3", "joint_0/joint_1/joint_2/joint_3/joint_4"]
```

## Impact

- Tree skeleton: ✅ Working (hierarchical joint names)
- Skeletal Nanite Assembly: ✅ Fixed (now uses hierarchical joint names)
- Static Nanite Assembly: ✅ Unaffected (no skeleton)
- Twig binding: ✅ Correctly binds to full joint paths

## Files Modified

1. `src/growpy/io/unreal_nanite_assembly.py` - line 349
2. `src/growpy/io/blender_export.py` - line 3466

## Testing Recommendations

To fully test the skeletal Nanite Assembly with a proper tree structure:

```bash
python src/growpy/cli/generate_forest.py data/input/test.csv \
  --quality high \
  --output-dir data/output/skeletal_test \
  --growth-cycle-limit 10 \
  --formats usda
```

Using `--growth-cycle-limit 10` will generate branches, not just a single stem, allowing you to verify:

- Multiple hierarchical joint levels
- Twigs binding to different branches
- Full skeletal hierarchy display in Unreal

## Unreal Import

Import the skeletal Nanite Assembly file in Unreal Engine 5.7+:

- File: `*_NaniteAssembly_skeletal.usda`
- Import as: Skeletal Mesh
- The skeleton hierarchy should display correctly
- Twig instances should bind to the correct branch joints
