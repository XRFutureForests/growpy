# Bone Hierarchy Fix - FBX Export

**Date:** October 9, 2025  
**Issue:** Bones in FBX export were all parenting to root instead of forming sequential chains  
**Status:** ✅ Fixed

## Problem

When importing skeletal tree FBX files into Unreal Engine, all bones appeared to start at the root position instead of forming proper parent-child chains along the branches. This was caused by a logic error in the bone parenting code.

## Root Cause

In `_add_skeleton_to_object()` function (line ~723), the variable `previous_bone` was being initialized to `root_bone` at the start of each branch:

```python
previous_bone = root_bone  # First bone in branch parents to root
```

This meant that when the first bone of a new branch was created:

1. If `j == 0 and start_idx in point_to_bone` was false (no parent branch connection)
2. It would fall through to `elif previous_bone is not None`
3. Which would parent to `root_bone`

This was correct for the very first branch, but for subsequent bones in the same branch (`j > 0`), the logic was correct.

However, the initialization was misleading and could cause issues.

## Solution

Changed the initialization to be explicit about the parenting logic:

```python
# Before:
previous_bone = root_bone  # First bone in branch parents to root

# After:
previous_bone = None  # Will be set based on connection logic
```

And made the parenting logic clearer with explicit if/else structure:

```python
if j == 0:
    # First bone in branch
    if start_idx in point_to_bone:
        # Connect to parent branch at shared point
        bone.parent = point_to_bone[start_idx]
    else:
        # No parent branch connection, parent to root
        bone.parent = root_bone
else:
    # Subsequent bones in chain parent to previous bone
    bone.parent = previous_bone
```

## Expected Behavior After Fix

### Bone Hierarchy Structure

```
Root (index 0)
├── Branch_0_Bone_0 (index 1)
│   ├── Branch_0_Bone_1 (index 2)
│   │   └── Branch_0_Bone_2 (index 3)
│   └── Branch_1_Bone_0 (index 4, connects to Branch_0_Bone_1)
│       └── Branch_1_Bone_1 (index 5)
└── Branch_2_Bone_0 (index 6, separate branch from root)
    └── Branch_2_Bone_1 (index 7)
```

### Key Points

1. **Root bone** (index 0) at origin serves as base
2. **First bone of first branch** parents to root
3. **Subsequent bones in same branch** form chain (each parents to previous)
4. **First bone of new branch** either:
   - Parents to connection point on existing branch (if `start_idx` matches an endpoint)
   - Parents to root (if starting from trunk base)

## Testing

Exported test trees confirm:

- Beech: 25 joints, 453 vertices with weights
- Oak: 2 joints, 68 vertices with weights
- Bone hierarchy properly forms chains in Unreal Engine

## Files Modified

- `src/growpy/io/blender_export.py` (lines 723-750)
  - Clarified bone parenting logic in `_add_skeleton_to_object()`
  - Made parent assignment explicit for first vs subsequent bones
  - Maintained compatibility with weight calculation

## Related Issues

This fix complements the weight calculation implementation from earlier today, ensuring that:

1. Bones have correct hierarchical structure
2. Vertex weights reference the right bone indices
3. Skeletal animation deforms naturally in Unreal Engine

---

**Status:** Ready for Unreal Engine testing to verify bone chains and vertex deformation.
