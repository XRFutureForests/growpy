# Skeleton Bone Positioning Fix

**Date**: October 15, 2025  
**Issue**: Skeleton bones have incorrect positioning in USD exports and improper parent-child connectivity in FBX exports

## Problem Description

### USD Skeleton Issue

In the USD skeletal mesh exports, bones had correct length and orientation but all bones appeared to originate from the root position. When viewing the skeleton in Unreal Engine or other USD viewers, bones would display with proper relative transforms but the accumulated chain position was wrong.

**Root Cause**: In `_add_skeleton_only_to_usd()` and `_add_skeleton_and_materials_to_usd()`, the code was storing bone START positions in `joint_positions[joint_idx]` instead of bone END positions. This caused child bones to calculate their offset from the wrong point in the parent chain.

```python
# BEFORE (incorrect):
joint_positions[joint_idx] = Gf.Vec3d(start_pos[0], start_pos[1], start_pos[2])

# AFTER (correct):
joint_positions[joint_idx] = Gf.Vec3d(end_pos[0], end_pos[1], end_pos[2])
```

### FBX Skeleton Issue

In the FBX skeletal mesh exports, when moving a parent bone, child branches would not move with it. They would stay in place and become disconnected from the stem.

**Root Cause**: In `_add_skeleton_to_object()`, bones were being parented but not properly connected. Blender has two concepts:

1. **Parenting**: Establishes hierarchy (child transforms relative to parent)
2. **Connection**: `use_connect=True` makes the child bone's head locked to the parent's tail

Without proper connection, moving a parent bone would move its direct children but not enforce the physical connectivity.

```python
# BEFORE (incorrect):
bone.parent = previous_bone

# AFTER (correct):
bone.parent = previous_bone
if (bone.head - previous_bone.tail).length < 0.001:
    bone.use_connect = True
```

## Solution

### USD Export Fix

Modified both `_add_skeleton_only_to_usd()` and `_add_skeleton_and_materials_to_usd()`:

1. Changed `joint_positions` to store bone **END positions** (tail) instead of start positions
2. This ensures child bones calculate their offset from the parent's tail, creating proper chain accumulation
3. Transform hierarchy now correctly represents the physical bone chain

**Location**: `src/growpy/io/blender_export.py`

- Lines ~1470-1479 in `_add_skeleton_only_to_usd()`
- Lines ~1770-1780 in `_add_skeleton_and_materials_to_usd()`

### FBX Export Fix

Modified `_add_skeleton_to_object()`:

1. Added `use_connect=True` for bones that are adjacent in the chain (head matches parent's tail within 0.001 tolerance)
2. This creates proper bone connectivity where moving a parent physically moves connected children
3. Maintains proper deformation during animation and manual posing

**Location**: `src/growpy/io/blender_export.py`

- Lines ~770-795

## Technical Details

### USD Skeleton Hierarchy

USD skeletons use a parent-child hierarchy where each bone's transform is relative to its parent:

```
Root (0,0,0)
  └─ Bone_1 (relative to Root's tail)
      └─ Bone_2 (relative to Bone_1's tail)
          └─ Bone_3 (relative to Bone_2's tail)
```

The `bind_transforms` and `rest_transforms` arrays contain the relative transforms. When accumulated through the hierarchy, they produce the world-space bone positions.

### FBX/Blender Bone Connection

Blender's armature system has two relationship types:

1. **Parent-Child** (`.parent`): Defines hierarchy and transform inheritance
2. **Connected** (`.use_connect`): Physically locks child head to parent tail

For proper deformation:

- **Connected bones**: Move together as a rigid chain (e.g., spine, limbs)
- **Unconnected bones**: Can rotate independently at attachment point (e.g., branch splits)

The fix adds `use_connect=True` for bones that are part of the same polyline (continuous branch), ensuring proper chain behavior.

## Testing

### Verification Steps

1. **USD Export Test**:

   ```bash
   conda activate the-grove
   python test_skeleton_fix.py
   ```

   Check that bone chain positions accumulate properly through hierarchy.

2. **FBX Export Test**:
   - Export a tree with skeleton to FBX
   - Open in Blender
   - Select a base/trunk bone in pose mode
   - Move it and verify branches move with it (stay connected)

3. **Unreal Engine Import**:
   - Import USD skeletal mesh into UE5
   - View skeleton in Skeleton Editor
   - Bones should be positioned along the tree structure, not all at root

### Expected Results

- **USD**: Bones properly positioned along tree branches, forming visual hierarchy
- **FBX**: Moving parent bones moves connected child bones, maintaining tree structure
- **Both**: Vertex deformation works correctly when bones are moved

## Impact

This fix affects all skeletal mesh exports:

- `export_tree_as_usd()` with `include_skeleton=True`
- FBX exports (internal skeleton creation)
- Any code using `_add_skeleton_to_object()` or `_add_skeleton_only_to_usd()`

**Breaking Changes**: None - this is a bug fix that makes skeletons work correctly. Existing exports with incorrect bone positioning should be re-exported.

## Related Code

- `_calculate_vertex_weights()`: Uses Grove's bone tagging system to assign vertices to bones
- `_add_skeleton_only_to_usd()`: Creates USD skeleton structure
- `_add_skeleton_and_materials_to_usd()`: Creates USD skeleton with materials  
- `_add_skeleton_to_object()`: Creates Blender armature for FBX export

## References

- USD Skeleton Documentation: <https://openusd.org/release/api/usd_skel_page_front.html>
- Blender Armature API: <https://docs.blender.org/api/current/bpy.types.EditBone.html>
- UE5 USD Skeletal Mesh Import: <https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-import-in-unreal-engine>
