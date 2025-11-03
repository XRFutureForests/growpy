# Skeleton Building from bones_info - Implementation Improvement

**Date:** 2025-01-07  
**Status:** Completed

## Problem

The original skeleton building code reconstructed the joint hierarchy by traversing skeleton polylines, which was complex and error-prone. This involved:

- Converting polylines to joint paths
- Tracking which polylines are branches vs main trunk
- Manually building parent-child relationships
- Complex indexing logic with shared points between polylines

## Solution

Use Grove's `bones_info` data structure directly, which already contains all necessary information:

```python
# bones_info format from grove.tag_bone_id()
(is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
```

### Key Insights

1. **Parent relationships are explicit**: `parent_bone_id` directly tells us the parent bone
2. **Bone positions are direct**: `start_point` and `end_point` give exact positions
3. **Metadata included**: `is_tree_root`, `is_branch_root`, `branch_id` provide structure info
4. **Global parent references**: `parent_bone_id` uses global bone indices across all trees

### Multi-Tree Grove Handling

For groves with multiple trees, bone IDs restart at 0 for each tree, but `parent_bone_id` values remain global:

**Tree 0 (24 bones):**

```python
bone_id: 0, parent_bone_id: 0   # Root points to itself, offset = 0
bone_id: 1, parent_bone_id: 0   # Child of root
...
bone_id: 23, parent_bone_id: 22 # Last bone
```

**Tree 1 (24 bones):**

```python
bone_id: 0, parent_bone_id: 24  # Root of tree 1, offset = 24
bone_id: 1, parent_bone_id: 24  # Child of tree 1 root
...
```

**Offset calculation:**

```python
first_bone = bones_info[0]
is_tree_root, parent_bone_id = first_bone[0], first_bone[1]

if is_tree_root and parent_bone_id == 0:
    bone_id_offset = 0  # First tree
elif is_tree_root:
    bone_id_offset = parent_bone_id  # Subsequent tree
```

## Implementation

### Before (Polyline-based)

```python
# Complex polyline traversal
for polyline_idx, polyline in enumerate(skeleton_polylines):
    prev_joint_path = None
    start_idx = 1 if polyline_idx > 0 else 0
    
    for i, point_idx in enumerate(polyline[start_idx:], start=start_idx):
        # Complex logic to determine parent relationships
        if i == start_idx:
            if polyline_idx == 0:
                joint_path = joint_name
            else:
                shared_point_idx = polyline[0]
                parent_joint_path = point_to_joint_path[shared_point_idx]
                joint_path = f"{parent_joint_path}/{joint_name}"
        # ... more complex logic
```

### After (bones_info-based)

```python
for bone_idx, bone_info in enumerate(bones_info):
    is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id = bone_info
    
    # Simple offset calculation
    global_bone_id = bone_id_offset + bone_idx
    
    # Direct position extraction
    world_pos = Gf.Vec3d(start_point[0], start_point[1], start_point[2])
    local_pos = world_pos - tree_offset
    
    # Simple parent lookup using parent_bone_id
    if global_bone_id == 0:
        joint_path = "root"
    else:
        parent_path = bone_id_to_joint_path[parent_bone_id]
        joint_path = f"{parent_path}/joint_{global_bone_id}"
```

## Benefits

1. **Simpler code**: Direct data extraction vs complex traversal logic
2. **More reliable**: Uses Grove's authoritative bone structure
3. **Better multi-tree support**: Proper handling of bone ID offsets
4. **Easier debugging**: Clear bone hierarchy with metadata
5. **Branch information**: `is_branch_root` and `branch_id` available for future features

## Fallback

The polyline-based method is retained as a fallback if `bones_info` is not provided:

```python
if bones_info and len(bones_info) > 0:
    # Use bones_info (preferred)
else:
    # Fall back to polyline traversal (with warning)
    if verbose:
        print("WARNING: bones_info not provided, falling back to polyline-based skeleton")
```

## Testing

Verified with multi-tree grove:

- Tree 0: bones 0-23 (global IDs 0-23)
- Tree 1: bones 0-23 (global IDs 24-47)

Parent relationships correctly maintained across tree boundaries.

## Files Modified

- `src/growpy/io/tree_export.py`:
  - `_build_usdskel_from_bones()`: Main skeleton building function
  - Added bones_info-based implementation
  - Retained polyline fallback with warning

## References

- Grove API: `grove.tag_bone_id()` generates bones_info
- USD Skeleton: `UsdSkel.Skeleton` specification
- Multi-tree documentation: See grove geometry dumps in `data/output/grove_geometry_dump/`
