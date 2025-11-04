# Twig to Skeleton Binding - Complete Guide

**Date**: 2025-01-15
**Status**: PRODUCTION READY

## Overview

GrowPy implements sophisticated twig-to-skeleton binding using Grove's native branch tracking system. Each twig instance is bound to the exact branch root bone that controls its parent branch, ensuring proper hierarchical animation and physics simulation in Unreal Engine.

## Core Concept

### Binding Hierarchy

```
Tree Skeleton (bone hierarchy)
├── bone_0 (branch 1 root, tree trunk)
│   └── bone_9 (branch 2 root)
│       ├── twig_long_0 → BOUND to bone_9
│       ├── twig_long_1 → BOUND to bone_9
│       └── bone_12 (branch 3 root)
│           ├── twig_long_2 → BOUND to bone_12
│           └── twig_short_0 → BOUND to bone_12
```

**Key Principle**: Twigs bind to **branch root bones**, not leaf joints. This ensures twigs move with their entire branch during wind animation or physics simulation.

## How It Works

### Step 1: Grove's Authoritative Data

The Grove API provides three critical attributes for binding:

1. **`model.face_attribute_branch_id`**: Each face (triangle) has a branch ID assignment from Grove's growth simulation
2. **`bones_info[i][6]`**: `is_branch_root` flag identifying which bones are branch roots
3. **`bones_info[i][7]`**: `branch_id` associating each bone with its branch

### Step 2: Branch Root Mapping

During tree export, we build a direct mapping from branch IDs to branch root bones:

```python
# From src/growpy/core/twig.py lines 195-204
branch_root_bones = {}
if bones_info:
    for bone_idx, bone in enumerate(bones_info):
        if len(bone) >= 8:
            is_branch_root = bone[6]  # Index 6 is is_branch_root flag
            branch_id = int(bone[7])  # Index 7 is branch_id
            if is_branch_root:
                branch_root_bones[branch_id] = bone_idx
```

**Result**: Dictionary like `{1: 0, 2: 9, 3: 12, 4: 15, 5: 18, 6: 21}`

### Step 3: Twig Placement and Binding

For each twig placement face:

```python
# From src/growpy/core/twig.py lines 257-271
twig_bone_id = None

if (
    face_branch_ids
    and face_idx < len(face_branch_ids)
    and branch_root_bones
):
    # Direct mapping from face's branch_id to branch root bone
    face_branch_id = face_branch_ids[face_idx]
    twig_bone_id = branch_root_bones.get(face_branch_id)
```

**Result**: Each twig knows exactly which bone controls it via O(1) dictionary lookup.

### Step 4: USD Assembly with BindJoints

The binding is written to the USD Nanite Assembly:

```python
# From src/growpy/io/assembly_export.py lines 363-364
# Build bindJoints array using direct bone IDs from twig placements
# CRITICAL: Perfect binding - each twig bound to exact bone controlling
```

**USD Structure**:

```
def NaniteAssembly "Root"
{
    def SkelRoot "Root"
    {
        def Skeleton "Skeleton"
        {
            def "bone_0" { }
            def "bone_9" { }
            def "bone_12" { }
        }
        
        def Xform "twig_long_0" (
            prepend references = @twig_long.usda@
        )
        {
            rel skel:skeleton = </Root/Skeleton>
            int[] skel:jointIndices = [9]  # → bone_9
            float[] skel:jointWeights = [1.0]
        }
    }
}
```

## Example Binding Results

From test data in `data/output/grove_geometry_dump/tree_0/skeleton_bones.txt`:

| Branch ID | Root Bone | Bone Depth | Parent | Expected Twigs |
|-----------|-----------|------------|--------|----------------|
| 1 | bone_0 | 0 | root | Trunk twigs |
| 2 | bone_9 | 1 | bone_1 | Branch 2 twigs |
| 3 | bone_12 | 2 | bone_2 | Branch 3 twigs |
| 4 | bone_15 | 3 | bone_3 | Branch 4 twigs |
| 5 | bone_18 | 4 | bone_4 | Branch 5 twigs |
| 6 | bone_21 | 5 | bone_5 | Branch 6 twigs |

**Validation**: All twigs bind to bones at depth 0-5 (branch roots), not depth 8-10 (leaf joints).

## Why Branch Root Binding?

### Correct Behavior

- Wind animation: Entire branch sways with its twigs
- Physics simulation: Twigs follow branch movement correctly
- Hierarchical animation: Parent branch controls child branches and their twigs

### Incorrect (Old) Behavior

- Binding to leaf joints caused floating twigs
- Twigs didn't move with branch during animation
- Complex vertex voting picked wrong bones at junctions

## Implementation Files

### Core Binding Logic

**File**: `src/growpy/core/twig.py`

- Lines 195-204: Build branch root mapping
- Lines 257-271: Assign twig bone IDs via direct lookup
- Lines 290: Create TwigPlacement with bone_id

### Assembly Export

**File**: `src/growpy/io/assembly_export.py`

- Line 214: Twig root bone isolation
- Lines 344-346: Skeleton separation architecture
- Lines 363-364: BindJoints array construction

### Twig Data Structure

**File**: `src/growpy/core/twig.py`

```python
@dataclass
class TwigPlacement:
    location: Vector3  # World position
    rotation: Quaternion  # Orientation
    scale: float  # Uniform scale
    twig_type: str  # "twig_long", "twig_short", etc.
    bone_id: Optional[int]  # Branch root bone index
```

## Grove Attribute Reference

### bones_info Tuple Format

```python
(
    is_tree_root,      # Index 0: bool - Is this the tree's root bone?
    parent_bone_id,    # Index 1: int - Parent bone index (-1 if root)
    start_point,       # Index 2: int - Skeleton point index for bone start
    end_point,         # Index 3: int - Skeleton point index for bone end
    radius,            # Index 4: float - Bone radius
    mass,              # Index 5: float - Bone mass
    is_branch_root,    # Index 6: bool - Is this a branch root bone?
    branch_id          # Index 7: int - Branch ID from Grove simulation
)
```

### Face Attributes Used

- **`face_attribute_branch_id`**: Direct branch assignment per face
- **`face_attribute_twig_long`**: Triangles marked for long twig placement
- **`face_attribute_twig_short`**: Triangles marked for short twig placement
- **`face_attribute_twig_upward`**: Upward-facing twig placements
- **`face_attribute_twig_dead`**: Dead twig placements

## Testing and Validation

### Test Script

**File**: `test_twig_binding.py`

Generates test tree and verifies binding:

```python
python test_twig_binding.py
```

Expected output:

```
Expected: All twigs bound to bones like bone_0, bone_9, bone_12, etc.
```

### Visual Validation in Unreal Engine

1. Import tree FBX with skeleton
2. Import Nanite Assembly USD
3. Open Skeleton Editor
4. Select and rotate bone_9
5. **Verify**: All twigs on branch 2 rotate with bone_9
6. Select and rotate bone_12
7. **Verify**: All twigs on branch 3 rotate with bone_12

### Debug Output

Check skeleton bones file for branch structure:

```bash
cat data/output/grove_geometry_dump/tree_0/skeleton_bones.txt
```

Look for `is_branch_root=True` entries to identify valid binding targets.

## Advantages of This Approach

1. **Authoritative**: Uses Grove's native branch tracking instead of geometric heuristics
2. **Simple**: O(1) dictionary lookup replaces complex vertex iteration
3. **Fast**: No Counter voting or polygon scanning needed
4. **Robust**: Works for any tree complexity or branch topology
5. **Maintainable**: Clear data flow from Grove → binding → USD
6. **Framework-Aligned**: Uses Grove's intended attribute system

## Common Issues and Solutions

### Issue: Floating Twigs

**Cause**: Binding to leaf joints instead of branch roots
**Solution**: System now uses `is_branch_root` flag to identify correct bones

### Issue: Twigs Don't Move

**Cause**: BindJoints pointing to wrong skeleton or missing weights
**Solution**: Verify `skel:skeleton` relationship and `skel:jointWeights = [1.0]`

### Issue: Incorrect Branch Assignment

**Cause**: Using vertex-based voting at branch junctions
**Solution**: Use Grove's `face_attribute_branch_id` directly (authoritative)

## Related Documentation

- **`docs/TWIG_BINDING_FIX.md`**: Original implementation details and problem analysis
- **`docs/TWIG_BINDING_DIAGNOSIS.md`**: Root cause diagnosis of floating twig issue
- **`docs/GROVE_API_ATTRIBUTES.md`**: Complete Grove API attribute reference
- **`docs/growpy/SKELETAL_ANIMATION.md`**: Skeletal animation pipeline overview

## Future Enhancements

### Potential Improvements

1. **Root Skeleton Binding**: Bind roots to inverse skeleton for ground interaction
2. **Multiple Bind Joints**: Support soft binding with multiple bones and weights
3. **Procedural Weight Painting**: Distance-based falloff for smoother deformation
4. **Wind Animation Presets**: Pre-baked bone animations for common wind patterns

### Not Recommended

- Binding twigs to leaf joints (causes floating)
- Geometric heuristics for bone selection (fragile)
- Cross-skeleton binding (breaks isolation)

## Summary

GrowPy's twig binding system provides production-ready skeletal animation support for Unreal Engine Nanite assemblies. By leveraging Grove's native branch tracking and `is_branch_root` flags, each twig is bound to the exact bone controlling its parent branch, ensuring proper hierarchical animation and physics simulation.

**Key Takeaway**: Trust Grove's data. The `face_attribute_branch_id` + `is_branch_root` combination provides authoritative binding information that eliminates ambiguity and complexity.
