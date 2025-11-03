# Vertex-to-Bone Mapping Update

## Summary

Updated GrowPy to use Grove's direct vertex-to-bone mapping via `point_attribute_bone_id` instead of distance-based calculations. This provides accurate, efficient vertex skinning based on Grove's internal branch topology.

## Key Changes

### 1. Correct Build Order (generate_forest.py)

```python
# BEFORE (incorrect order)
models = grove.build_models({...})
skeletons = grove.build_skeletons()

# AFTER (correct order)
skeletons = grove.build_skeletons()  # Step 1
bones = grove.tag_bone_id(          # Step 2
    skeleton_length=0.0,            # Max bones
    skeleton_reduce=0.0,            # No reduction
    skeleton_bias=0.5,
    skeleton_connected=True
)
models = grove.build_models({...})  # Step 3
```

**Critical**: `tag_bone_id()` MUST be called before `build_models()` to populate `point_attribute_bone_id`.

### 2. Bones List Slicing for Multi-Tree Groves

```python
# tag_bone_id() returns a single flat list for ALL trees
# Slice it using skeleton.points length to get bones per tree
tree_bones = []
bone_offset = 0
for skeleton in skeletons:
    num_skeleton_points = len(skeleton.points)
    tree_bones.append(bones[bone_offset:bone_offset + num_skeleton_points])
    bone_offset += num_skeleton_points
```

### 3. Direct Vertex-to-Bone Mapping (tree_export.py)

```python
# NEW: Direct mapping using point_attribute_bone_id
if model and hasattr(model, "point_attribute_bone_id"):
    bone_ids = model.point_attribute_bone_id
    
    for bone_id in bone_ids:
        joint_idx = min(bone_id, len(joint_tokens) - 1)
        joint_indices.extend([joint_idx, 0])
        joint_weights.extend([1.0, 0.0])
else:
    # Fallback: rigid binding (only if tag_bone_id() wasn't called)
    for _ in range(num_vertices):
        joint_indices.extend([0, 0])
        joint_weights.extend([1.0, 0.0])
```

### 4. Coordinate Space Conversion

The skeleton export already handles global-to-local space conversion:

```python
# Skeleton points are in world space, mesh is in local space
root_point = skeleton_points[root_point_idx]
tree_offset = Gf.Vec3d(root_point[0], root_point[1], root_point[2])

# Convert each skeleton point to local space
world_pos = Gf.Vec3d(point[0], point[1], point[2])
local_pos = world_pos - tree_offset
```

## Technical Details

### Why This Works

1. **Grove's Internal Mapping**: When `tag_bone_id()` is called before `build_models()`, Grove internally tags each vertex with its corresponding bone ID
2. **Topologically Correct**: Uses Grove's branch hierarchy, not spatial proximity
3. **Zero Computation**: Simple integer lookup, no distance calculations
4. **Animation Ready**: Matches how the Blender addon rigs trees

### Parameters for Maximum Bone Count

```python
bones = grove.tag_bone_id(
    skeleton_length=0.0,    # No bone merging based on length
    skeleton_reduce=0.0,    # No reduction based on thickness
    skeleton_bias=0.5,      # Default weight distribution
    skeleton_connected=True  # Connected hierarchy for animation
)
```

**Note**: Skeletal simplification should happen in Unreal Engine, not during export.

## Benefits

1. **Accurate**: Uses Grove's internal branch topology
2. **Efficient**: O(n) lookup vs O(n×m) distance calculations
3. **Predictable**: Deterministic mapping, not distance-based heuristics
4. **Maintainable**: Relies on Grove API, not custom algorithms

## Migration Notes

### Before

```python
def export_tree(grove, ...):
    models = grove.build_models({...})
    skeletons = grove.build_skeletons()
    # Distance-based vertex weights calculated during USD export
```

### After

```python
def export_tree(grove, ...):
    skeletons = grove.build_skeletons()
    bones = grove.tag_bone_id(length=0.0, reduce=0.0)
    models = grove.build_models({...})
    # Direct vertex-to-bone mapping via point_attribute_bone_id
```

## Validation

The implementation includes verbose logging to verify correct mapping:

```python
if verbose:
    print(f"Using direct vertex-to-bone mapping via point_attribute_bone_id")
    print(f"  Vertices: {len(bone_ids)}, Joints: {len(joint_tokens)}")
```

## References

- Grove API: `model.point_attribute_bone_id` - List[int] of bone IDs per vertex
- Grove Docs: `docs/the_grove/from_blender_addon/model-building-system.md`
- Blender Addon: Uses this same approach for rigging
