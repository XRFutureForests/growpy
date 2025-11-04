# Twig Skeletal Binding Diagnosis

## Problem Description

Some twigs float in the air or move with wrong branches when tree bones are rotated, even though they're placed on different parts of the tree.

## Root Cause Analysis

### Current Binding Mechanism

The system binds each twig instance to a joint using `bone_id` from `model.point_attribute_bone_id`:

1. For each face with a twig, get the bone IDs of its vertices
2. Use the most common bone_id (via Counter) as the twig's binding target
3. Look up the joint path from the skeleton using this bone_id as an index
4. Set `primvars:unreal:naniteAssembly:bindJoints` to this joint path

**Code location:** `src/growpy/core/twig.py` lines 287-290

### The Issue

**Observed binding patterns:**

- Reference assembly uses short joint paths like `"root/joint_1"`, `"root/joint_1/joint_2"`
- Generated assembly uses ONLY leaf joints like `"root/joint_1/joint_17/.../joint_24/joint_25"`

**Why this causes floating twigs:**

Grove's `point_attribute_bone_id` returns the exact bone controlling each vertex - typically a leaf joint for detailed branch geometry. However:

1. **Face vertices may not all share the same bone** - they can span multiple bones at branch junctions
2. **Counter.most_common() may pick the wrong bone** if face vertices are weighted to different branches
3. **Leaf joints are very specific** - a twig bound to leaf joint in branch A won't follow properly when rotating the parent of branch B

### Example Scenario

```
Tree structure:
  root
    └─ joint_1 (main trunk)
         ├─ joint_2 (branch A)
         │    └─ joint_3 (leaf A)
         └─ joint_4 (branch B)
              └─ joint_5 (leaf B)

Face at joint_2/joint_4 junction:
  - Vertices: [v1(bone=3), v2(bone=3), v3(bone=5), v4(bone=5)]
  - Counter picks bone_id=3 (joint_3 in branch A)
  - Twig bound to "root/joint_1/joint_2/joint_3"
  
When rotating joint_4 (branch B):
  - Branch B moves correctly
  - Twig stays with branch A (wrong!)
  - Twig appears to "float" relative to branch B
```

## Comparison with Reference

### Reference Assembly

```usd
bindJoints = [
    "root/joint_1",           # Trunk joint
    "root/joint_1/joint_2",   # Branch joint
    "root/joint_1/joint_4"    # Another branch joint
]
```

Uses **intermediate joints** at branch points, not leaf joints.

### Generated Assembly

```usd
bindJoints = [
    "root/joint_1/joint_17/joint_18/.../joint_25",  # Deep leaf joint
    "root/joint_1/joint_17/joint_18/.../joint_30",  # Different leaf joint
    ...
]
```

Uses **only leaf joints** from vertex bone IDs.

## Twig Skeleton Structure (Correct)

All twig files (`european_beech_twig_var_*_skeletal.usda`) have minimal skeletons:

- Single joint: `["root"]`
- Identity bind/rest transforms
- Mesh fully weighted to root joint

**This is CORRECT** - twigs are rigid instances and should have minimal skeletons. The issue is not with twig skeletons but with instance binding.

## Solution Options

### Option 1: Use Parent Joint for Twig Binding (Recommended)

Instead of binding to the exact leaf joint from bone_id, walk up the hierarchy to find a more stable parent joint:

```python
def get_twig_binding_joint(bone_id: int, bones_info: List, max_depth: int = 3) -> int:
    """Get appropriate binding joint by walking up hierarchy.
    
    For leaf geometry (twigs), we want to bind to a parent joint
    that's closer to main branches, not the deepest leaf joint.
    """
    if not bones_info or bone_id >= len(bones_info):
        return 0
    
    bone = bones_info[bone_id]
    parent_id = int(bone[0]) if len(bone) > 0 else -1
    
    # Walk up max_depth levels or until we hit a branch point
    for _ in range(max_depth):
        if parent_id < 0 or parent_id >= len(bones_info):
            break
        
        # Check if parent has multiple children (branch point)
        parent_bone = bones_info[parent_id]
        # If this is a significant branch point, use it
        bone_id = parent_id
        parent_id = int(parent_bone[0]) if len(parent_bone) > 0 else -1
    
    return bone_id
```

### Option 2: Use Branch-Level Binding

Leverage `face_attribute_branch_id` to group twigs by branch and use branch-level joints:

```python
# In twig.py, around line 280:
twig_bone_id = None
if face_branch_ids and face_idx < len(face_branch_ids):
    branch_id = face_branch_ids[face_idx]
    # Find first bone in this branch
    if branch_id in branch_to_bones and branch_to_bones[branch_id]:
        twig_bone_id = branch_to_bones[branch_id][0]  # Use first bone in branch
```

### Option 3: Weighted Average of Face Vertices

Instead of most common bone, use spatial weighting:

```python
from collections import defaultdict
bone_weight = defaultdict(float)
for vert_idx in face_vert_indices:
    if vert_idx < len(bone_ids):
        # Weight by distance from face center
        bone_weight[bone_ids[vert_idx]] += 1.0
# Use bone with highest total weight
twig_bone_id = max(bone_weight.items(), key=lambda x: x[1])[0]
```

## Testing Strategy

1. Export test tree with simple 2-branch structure
2. Place twigs on both branches
3. Check bindJoints in assembly - should use branch-level joints, not leaves
4. Import to Unreal and test rotation of intermediate bones
5. Verify all twigs move with their respective branches

## Files to Modify

1. `src/growpy/core/twig.py` - Twig bone_id assignment (line 280-295)
2. `src/growpy/io/assembly_export.py` - Optional: Add validation for reasonable joint depths
3. Test with: `data/output/forest/european_beech/european_beech_tree_0000_nanite_assembly.usda`

## Next Steps

1. Implement Option 1 (parent joint walking) as it's most robust
2. Add debug logging to show bone_id → joint_path mapping
3. Test with simple tree structure first
4. Compare with reference assembly behavior
