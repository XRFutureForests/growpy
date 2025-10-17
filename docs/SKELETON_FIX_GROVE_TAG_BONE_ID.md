# Skeleton Fix: Using Grove's tag_bone_id() Function

**Date**: 2025-01-09  
**Status**: IMPLEMENTED  
**Issue**: Skeletal mesh bones were not properly connected (all starting from root)  
**Solution**: Use Grove's `tag_bone_id()` function which returns actual bone segments with head/tail positions

## Problem Analysis

### Initial Issue

User reported: "The skeleton is not working properly" - bones were disconnected (all starting from root at (0,0,0)).

### Investigation Results

1. **Previous Implementation**: Used `skeleton.points` and `skeleton.poly_lines`
   - `skeleton.points`: List of (x,y,z) coordinates
   - `skeleton.poly_lines`: Connectivity graph
   - Required manual calculation of bone transforms from topology
   - Prone to errors in parent-child position tracking

2. **Grove's Actual API**: Has `tag_bone_id()` function
   - Returns **actual bone segments** with head/tail positions
   - Format: `[(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]`
   - This is what the Blender addon uses!
   - Much more reliable than reconstructing from points

## Solution

### New Implementation: `skeleton_from_bones.py`

Created new module that directly uses Grove's bone data:

```python
# Grove's tag_bone_id() returns actual bone segments
bones_info = grove.tag_bone_id(
    skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
)

# Each bone contains:
bone[0]  # bone index
bone[1]  # parent bone index (-1 for root)
bone[2]  # head position (Grove Vector)
bone[3]  # tail position (Grove Vector)
bone[4]  # radius

# Create joints from bones
for bone in bones_info:
    head_pos = Gf.Vec3d(*bone[2].as_tuple())
    tail_pos = Gf.Vec3d(*bone[3].as_tuple())
    
    # Calculate transform relative to parent's TAIL
    # (bones connect head-to-tail in chain)
    parent_tail = joint_tail_positions[parent_joint_idx]
    relative_pos = head_pos - parent_tail
    
    # Store tail for child connections
    joint_tail_positions[joint_idx] = tail_pos
```

### Key Differences from Old Code

| Aspect | Old (points/poly_lines) | New (tag_bone_id) |
|--------|------------------------|-------------------|
| Data Source | `skeleton.points` + `poly_lines` | `grove.tag_bone_id()` |
| Bone Segments | Reconstructed from connectivity | **Direct from Grove** |
| Head/Tail | Calculated from point indices | **Explicit in bone data** |
| Parent Tracking | Complex mapping with `point_to_joint` | **Simple bone_to_joint map** |
| Connection Logic | Tracked `end_pos` manually | **Automatic via tail positions** |
| Code Complexity | ~200 lines with nested loops | ~100 lines, single loop |
| Reference | None | **Matches Blender addon** |

## Implementation Changes

### Files Modified

1. **Created**: `src/growpy/io/skeleton_from_bones.py`
   - New function: `add_skeleton_from_grove_bones()`
   - Uses Grove's bone data directly
   - Simplified logic, easier to maintain

2. **Modified**: `src/growpy/io/blender_export.py`
   - Updated `export_grove_tree_as_usda_native()`
   - Changed skeleton call from `_add_skeleton_only_to_usd()` to `add_skeleton_from_grove_bones()`
   - Old function kept for reference but not used

### Test Results

```bash
python .\src\growpy\cli\generate_forest.py .\data\input\test.csv --quality high --growth-cycle-limit 5
```

Output:

```
Beech:
  [OK] Grove returned 11 bones with head/tail positions
  [OK] Created 12 joints from 11 bones  # 11 bones + 1 root
  [OK] Added skinning weights for 4368 vertices

Oak:
  [OK] Grove returned 17 bones with head/tail positions
  [OK] Created 18 joints from 17 bones  # 17 bones + 1 root
  [OK] Added skinning weights for 27231 vertices
```

## Technical Details

### Grove's tag_bone_id() Function

From The Grove 2.2 documentation and Blender addon code:

```python
# Function signature
bones = grove.tag_bone_id(
    length: float,      # Bone length multiplier
    reduce: float,      # Reduction factor (0.0-1.0, higher = fewer bones)
    bias: float,        # Weight bias (0.0-1.0)
    connected: bool     # Use connected hierarchy
)

# Returns list of bones where each bone is:
[
    bone_id: int,           # Unique bone identifier
    parent_id: int,         # Parent bone ID (-1 for root)
    head: Vector,           # Head position (start of bone)
    tail: Vector,           # Tail position (end of bone)
    radius: float          # Bone radius/thickness
]
```

### USD Skeleton Structure

```
SkelRoot
├── Skeleton
│   ├── joints: ["Root", "bone_0", "bone_1", ...]
│   ├── bindTransforms: [Matrix4d, ...]
│   └── restTransforms: [Matrix4d, ...]
├── Animation (SkelAnimation)
│   ├── translations: [Vec3f, ...]
│   ├── rotations: [Quatf, ...]
│   └── scales: [Vec3h, ...]
└── TreeMesh (with skinning)
    ├── jointIndices: [int, ...]
    └── jointWeights: [float, ...]
```

### Bone Connection Logic

```python
# Root joint
joints[0] = "Root"
joint_tail_positions[0] = (0, 0, 0)

# For each bone from Grove:
for bone in bones_info:
    # Get parent's tail (where this bone starts)
    parent_tail = joint_tail_positions[parent_joint_idx]
    
    # Bone head position relative to parent tail
    relative_pos = bone.head - parent_tail
    
    # Store this bone's tail for children
    joint_tail_positions[joint_idx] = bone.tail
```

This creates connected chains:

```
Root (0,0,0)
  └─ bone_0: head at (0,0,10)
      └─ bone_1: head at bone_0.tail
          └─ bone_2: head at bone_1.tail
```

## Benefits

1. **Correctness**: Uses Grove's actual bone data (not reconstruction)
2. **Simplicity**: 100 lines vs 200 lines, single loop vs nested
3. **Maintainability**: Matches Blender addon reference implementation
4. **Robustness**: No manual parent-child tracking needed
5. **Performance**: Fewer calculations, direct data access

## Reference

- **Blender Addon**: `src/the_grove_22/modules/operators/OperatorBuildSkeleton.py`
  - Line 450+: Uses `bones = grove.tag_bone_id(...)`
  - Line 477+: Creates Blender bones with `bone.head = bones[i][2].as_tuple()`
  - Line 478+: Sets `bone.tail = bones[i][3].as_tuple()`

## Next Steps

1. **Validation**: Test with various tree species and growth cycles
2. **Unreal Import**: Verify skeleton works in UE 5.7+ with Control Rig
3. **Documentation**: Update main docs with this approach
4. **Cleanup**: Consider removing old `_add_skeleton_only_to_usd()` function

## Growth Cycle Requirements

**Minimum**: 5-10 growth cycles for proper skeleton development

- 2 cycles: Degenerate skeleton (6 points, 1 poly_line)
- 5 cycles: Basic skeleton (11-17 bones depending on species)
- 10+ cycles: Full skeleton (100+ bones)

Use `--growth-cycle-limit N` to control tree development:

```bash
python generate_forest.py input.csv --growth-cycle-limit 10
```

## Conclusion

The fix was simple: **use Grove's API correctly**. Instead of trying to reconstruct bone hierarchy from topology data, we now use the actual bone segments that Grove provides via `tag_bone_id()`. This matches the Blender addon's approach and produces properly connected skeletal meshes.
