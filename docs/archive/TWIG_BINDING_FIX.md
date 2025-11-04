# Twig Binding Fix - Grove Attribute-Based Solution

**Date**: 2025-01-15
**Status**: IMPLEMENTED

## Problem Summary

Twigs bound to incorrect bones causing floating/incorrect movement when animating tree skeletons in Unreal Engine.

**Root Cause**: `Counter.most_common()` selected leaf joints instead of branch root joints at branch junctions where face vertices are weighted to multiple bones.

## Solution Implemented

Use Grove's native attribute system for direct branch root bone mapping instead of algorithmic selection.

### Key Insight

Grove provides authoritative branch assignments:

- Each bone has `is_branch_root` flag (index 6 in bones_info tuple)
- Each face has `face_attribute_branch_id` (direct branch assignment)
- Direct mapping eliminates ambiguity at branch junctions

### Code Changes

**File**: `src/growpy/core/twig.py`

#### Change 1: Build Branch Root Mapping (lines 195-204)

**Before**:

```python
# Build branch_id → bone_id mapping for proper branch isolation
branch_to_bones = {}
if bones_info:
    for bone_idx, bone in enumerate(bones_info):
        if len(bone) >= 8:
            branch_id = int(bone[7])
            if branch_id not in branch_to_bones:
                branch_to_bones[branch_id] = []
            branch_to_bones[branch_id].append(bone_idx)
```

**After**:

```python
# Build branch_id → branch_root_bone_id mapping using is_branch_root flag
# bones_info format: (is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
branch_root_bones = {}
if bones_info:
    for bone_idx, bone in enumerate(bones_info):
        if len(bone) >= 8:
            is_branch_root = bone[6]  # Index 6 is is_branch_root flag
            branch_id = int(bone[7])  # Index 7 is branch_id
            if is_branch_root:
                branch_root_bones[branch_id] = bone_idx
```

**Key Improvement**: Only stores branch root bones (where `is_branch_root=True`) instead of all bones in each branch.

#### Change 2: Direct Branch Root Binding (lines 246-258)

**Before**:

```python
# BRANCH-BASED BINDING: Use face_attribute_branch_id to restrict binding to current branch
twig_bone_id = None

if (
    face_branch_ids
    and face_idx < len(face_branch_ids)
    and branch_to_bones
):
    # PREFERRED: Use branch-based binding for perfect branch isolation
    face_branch_id = face_branch_ids[face_idx]
    branch_bones = branch_to_bones.get(face_branch_id, [])

    if branch_bones and bone_ids:
        # Within this branch, find which bone_id is most common among face vertices
        from collections import Counter

        face_vert_indices = list(face)
        face_bone_ids = []
        for vert_idx in face_vert_indices:
            if vert_idx < len(bone_ids):
                bone_id = bone_ids[vert_idx]
                # Only consider bones that belong to this branch
                if bone_id in branch_bones:
                    face_bone_ids.append(bone_id)

        if face_bone_ids:
            # Use most common bone within the branch
            twig_bone_id = Counter(face_bone_ids).most_common(1)[0][0]
        elif branch_bones:
            # Fallback: use first bone in branch (usually branch root)
            twig_bone_id = branch_bones[0]
```

**After**:

```python
# BRANCH-BASED BINDING: Direct mapping using face_attribute_branch_id → branch root bone
twig_bone_id = None

if (
    face_branch_ids
    and face_idx < len(face_branch_ids)
    and branch_root_bones
):
    # PREFERRED: Direct mapping from face's branch_id to branch root bone
    # This uses Grove's authoritative branch assignments and is_branch_root flags
    face_branch_id = face_branch_ids[face_idx]
    twig_bone_id = branch_root_bones.get(face_branch_id)
```

**Key Improvement**: Direct O(1) dictionary lookup replaces complex vertex iteration + Counter voting.

### Expected Results

Based on `data/output/grove_geometry_dump/tree_0/skeleton_bones.txt`:

| Branch ID | Branch Root Bone | Bone Parent | Expected Binding |
|-----------|------------------|-------------|------------------|
| 1 | 0 | 0 (tree root) | All branch 1 twigs → bone 0 |
| 2 | 9 | 1 | All branch 2 twigs → bone 9 |
| 3 | 12 | 2 | All branch 3 twigs → bone 12 |
| 4 | 15 | 3 | All branch 4 twigs → bone 15 |
| 5 | 18 | 4 | All branch 5 twigs → bone 18 |
| 6 | 21 | 5 | All branch 6 twigs → bone 21 |

All twigs now bind to branch root bones (depth 0-2 in hierarchy) instead of deep leaf joints (depth 8-10).

## Advantages Over Previous Approaches

1. **No Ambiguity**: Uses Grove's authoritative branch assignments instead of geometric heuristics
2. **Simpler Code**: Direct lookup eliminates Counter voting and vertex iteration
3. **Better Performance**: O(1) dictionary lookup vs O(n) vertex scanning
4. **Future-Proof**: Works regardless of tree complexity or branch junction topology
5. **Framework-Aligned**: Uses Grove's intended attribute system

## Testing Steps

1. Activate the-grove conda environment:

   ```powershell
   conda activate the-grove
   ```

2. Generate test tree with multiple branches:

   ```powershell
   python src/growpy/cli/export_trees.py
   ```

3. Inspect generated Nanite assembly:

   ```powershell
   # Check bindJoints in generated assembly
   # All twigs should bind to bones: /Root/Skeleton/bone_0, bone_9, bone_12, bone_15, bone_18, bone_21
   ```

4. Import to Unreal Engine:
   - Import tree FBX and Nanite assembly
   - Rotate individual bones in skeleton
   - Verify twigs move correctly with their branch

## Grove Attribute Reference

**bones_info tuple format** (src/growpy/io/tree_export.py:1036):

```python
(is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
# Index: 0           1              2           3          4       5     6              7
```

**Grove face attributes** (model.face_attribute_branch_id):

- Array of branch IDs, one per face
- Direct branch assignment from Grove's growth simulation

**Example data** (tree_0 with 6 branches, 24 bones):

```
Branch 1: bone 0 (root)
Branch 2: bone 9 (child of bone 1)
Branch 3: bone 12 (child of bone 2)
Branch 4: bone 15 (child of bone 3)
Branch 5: bone 18 (child of bone 4)
Branch 6: bone 21 (child of bone 5)
```

## Validation

Expected assembly structure after fix:

```
/Root
  /Skeleton (SkelRoot)
    /bone_0 (branch 1 root)
    /bone_9 (branch 2 root)
    /bone_12 (branch 3 root)
    /bone_15 (branch 4 root)
    /bone_18 (branch 5 root)
    /bone_21 (branch 6 root)
  /twig_long_0
    bindJoints: [/Root/Skeleton/bone_X]  ← where X is branch root for twig's face
    bindJointWeights: [1.0]
```

Compare with reference assembly which also uses branch root bones (bone_1, bone_3, etc. at depth 1-2).

## Files Modified

- `src/growpy/core/twig.py` (lines 195-258)

## Related Documentation

- `docs/TWIG_BINDING_DIAGNOSIS.md` - Original root cause analysis
- `data/output/grove_geometry_dump/tree_0/skeleton_bones.txt` - Bone hierarchy with is_branch_root flags
- `data/output/grove_geometry_dump/tree_0/face_attributes.txt` - Face-level branch_id assignments
