# Branch Binding Analysis - Skeletal Mesh Issues

## Problem Description

Branch geometry disconnects from the stem during skeletal animation, particularly when:

1. Branch root joint is positioned away from the actual branch-stem connection point
2. All branch vertices are rigidly bound (weight=1.0) to only the branch root joint
3. No smooth weight transition exists between parent stem bones and child branch bones

## Root Cause

Current implementation in `src/growpy/core/skeleton.py::calculate_vertex_weights()`:

```python
def calculate_vertex_weights(model, bone_to_joint_map, element_size=2):
    """CURRENT: Single-bone rigid binding per vertex."""
    
    for bone_id, weight in zip(bone_ids, weights):
        joint_idx = bone_to_joint_map.get(bone_id, 0)
        
        # Problem: Each vertex gets only ONE joint influence
        joint_indices_array.append(joint_idx)
        joint_weights_array.append(weight)  # Usually 1.0
        
        # Padding filled with zeros - no secondary influences
        for _ in range(element_size - 1):
            joint_indices_array.append(0)
            joint_weights_array.append(0.0)
```

**Key Issues:**

1. **Rigid binding only** - `weight` from Grove is usually 1.0 (single bone assignment)
2. **No multi-bone influences** - Branch junction vertices only bound to branch bone
3. **Unused Grove data** - Critical information from `bones_info` not utilized:
   - Index 6: `is_branch_root` - identifies branch root bones
   - Index 7: `branch_id` - associates bones with branches
   - `face_attribute_branch_id` - maps mesh faces to branches

## Critical Finding: Grove Uses Single-Bone Rigid Binding

**IMPORTANT:** Grove does NOT use multi-bone weighting. Investigation of Grove's official Blender addon and Houdini documentation reveals that **Grove uses the exact same single-bone rigid binding approach we currently implement**.

### Evidence from Grove's Official Implementations

**1. Blender Addon (`OperatorBuildSkeleton.py`, line 505):**

```python
vertex_group.add(indices.tolist(), 1.0, 'REPLACE')
```

- All vertices assigned weight = 1.0 to single bone
- No multi-bone influences

**2. Houdini Documentation (`Skeleton.html`, Weights section):**

```vex
export int @boneCapture_index[];
i[]@boneCapture_index = array(i@gr_skeleton_joint_id);  // Single bone ID

export float @boneCapture_data[];
f[]@boneCapture_data = array(1.0);  // Always weight = 1.0
```

- Explicitly shows single-bone assignment
- Weight hardcoded to 1.0

### Why Does It Work in Blender?

Blender's armature deformation system automatically provides smooth transitions at branch junctions through:

1. **Connected bone hierarchy**: Child bones share points with parent bones
2. **Envelope-based deformation**: Blender interpolates between nearby bones based on their radius/envelope
3. **Automatic weight blending**: Armature modifier handles multi-bone influences even with rigid vertex group weights

**This is a Blender-specific feature that USD skeletal mesh does NOT replicate.**

### 1. Grove API Provides Required Data

**From `grove.tag_bone_id()` - Bone tuple structure:**

```python
bone_tuple = (
    is_tree_root,      # Index 0: bool
    parent_bone_id,    # Index 1: int (-1 if root)
    start_point,       # Index 2: Vector - bone start position
    end_point,         # Index 3: Vector - bone end position
    radius,            # Index 4: float
    mass,              # Index 5: float
    is_branch_root,    # Index 6: bool - CRITICAL for junction binding
    branch_id          # Index 7: int - CRITICAL for branch-to-bone mapping
)
```

### 2. Branch-to-Bone Topology

Using `is_branch_root` and `branch_id`, we can identify:

- **Branch root bones**: Where child branches connect to parent stem
- **Branch hierarchy**: Parent-child relationships via `parent_bone_id`
- **Mesh-to-bone mapping**: Via `model.face_attribute_branch_id`

Example structure:

```python
# Build branch root bone mapping
branch_root_bones = {}  # {branch_id: bone_idx}
for bone_idx, bone in enumerate(bones_info):
    is_branch_root = bone[6]
    branch_id = int(bone[7])
    if is_branch_root:
        branch_root_bones[branch_id] = bone_idx

# Map mesh faces to their branch's root bone
face_branch_ids = model.face_attribute_branch_id
for face_idx, face_branch_id in enumerate(face_branch_ids):
    root_bone = branch_root_bones.get(face_branch_id)
    parent_bone = bones_info[root_bone][1]  # Parent bone index
    # Vertices in this face need weights for BOTH root_bone AND parent_bone
```

### 3. Grove's `weigh_and_bend()` Method

**From `docs/archive/GROVE_API_ATTRIBUTES.md`:**

- `grove.weigh_and_bend()` - Physics weight calculation

This method likely performs Grove's internal skinning calculation. However, it's not clear:

- Whether results are exposed via model attributes
- How to access the computed weights
- Whether it's compatible with our USD export workflow

## Proper Solutions

### Solution 1: Multi-Bone Weighting at Branch Junctions (Recommended)

Implement gradient weighting for vertices near branch junctions:

```python
def calculate_vertex_weights_with_junction_blending(
    model,
    bones_info,
    bone_to_joint_map,
    blend_distance=0.1,  # Distance over which to blend weights
    element_size=2
):
    """Enhanced vertex weighting with branch junction blending.
    
    Args:
        model: Grove model with point_attribute_bone_id
        bones_info: Full bone data from grove.tag_bone_id()
        bone_to_joint_map: Bone ID to joint index mapping
        blend_distance: Distance threshold for multi-bone blending
        element_size: Influences per vertex (2 for dual-bone)
    
    Returns:
        (joint_indices_array, joint_weights_array) with proper junction weights
    """
    
    # Build branch topology
    branch_root_bones = {}  # {branch_id: bone_idx}
    bone_positions = {}     # {bone_idx: (head_pos, tail_pos)}
    
    for bone_idx, bone in enumerate(bones_info):
        is_branch_root = bone[6]
        branch_id = int(bone[7])
        head_pos = bone[2].as_tuple()  # Vector to tuple
        tail_pos = bone[3].as_tuple()
        
        bone_positions[bone_idx] = (head_pos, tail_pos)
        
        if is_branch_root:
            branch_root_bones[branch_id] = bone_idx
    
    # Get vertex data
    vertices = [(p.x, p.y, p.z) for p in model.points]
    bone_ids = model.point_attribute_bone_id
    face_branch_ids = model.face_attribute_branch_id if hasattr(model, 'face_attribute_branch_id') else None
    
    joint_indices = []
    joint_weights = []
    
    for vert_idx, vertex_bone_id in enumerate(bone_ids):
        vertex_pos = vertices[vert_idx]
        joint_idx = bone_to_joint_map.get(vertex_bone_id, 0)
        
        # Check if this vertex is near a branch junction
        if vertex_bone_id in bones_info:
            bone = bones_info[vertex_bone_id]
            is_branch_root = bone[6]
            parent_bone_idx = int(bone[1])
            
            if is_branch_root and parent_bone_idx >= 0:
                # This vertex is on a branch root bone
                # Calculate distance to branch junction (head of branch bone)
                junction_pos = bone[2].as_tuple()  # Branch root bone head
                dist_to_junction = distance_3d(vertex_pos, junction_pos)
                
                if dist_to_junction < blend_distance:
                    # Blend with parent bone
                    parent_joint_idx = bone_to_joint_map.get(parent_bone_idx, 0)
                    
                    # Linear falloff: closer to junction = more parent influence
                    branch_weight = dist_to_junction / blend_distance
                    parent_weight = 1.0 - branch_weight
                    
                    # Normalize
                    total = branch_weight + parent_weight
                    branch_weight /= total
                    parent_weight /= total
                    
                    # Store dual weights
                    joint_indices.extend([joint_idx, parent_joint_idx])
                    joint_weights.extend([branch_weight, parent_weight])
                    continue
        
        # Default: single bone binding
        joint_indices.append(joint_idx)
        joint_weights.append(1.0)
        
        # Pad to element_size
        for _ in range(element_size - 1):
            joint_indices.append(0)
            joint_weights.append(0.0)
    
    return joint_indices, joint_weights


def distance_3d(p1, p2):
    """Calculate 3D Euclidean distance."""
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)**0.5
```

### Solution 2: Position Branch Root Joints at Junction Points

Modify `build_skeleton_hierarchy()` to adjust branch root joint positions:

```python
def build_skeleton_hierarchy(bones_info):
    """Build skeleton with branch root joints at junction points."""
    
    for i, bone in enumerate(bones_info):
        is_branch_root = bone[6]
        parent_bone_idx = int(bone[1])
        
        if is_branch_root and parent_bone_idx >= 0:
            # Get parent bone tail position
            parent_bone = bones_info[parent_bone_idx]
            parent_tail = parent_bone[3]  # Parent bone end
            
            # Position branch root joint at parent tail (junction point)
            adjusted_head = parent_tail
            
            # Calculate new transform relative to parent
            # ... (adjust bone transform calculation)
```

**Pros:** Simpler weight calculation, joints at intuitive locations

**Cons:** Changes bone positions from Grove's original skeleton structure

### Solution 3: Blender Envelope-Style Deformation

Implement Blender-style envelope deformation for USD:

```python
def calculate_envelope_weights(
    vertices,
    bones_info,
    bone_to_joint_map,
    envelope_distance=0.05,
    element_size=2
):
    """Calculate weights based on distance to bone envelopes (Blender-style).
    
    For each vertex, find all bones within envelope distance and blend weights.
    """
    joint_indices = []
    joint_weights = []
    
    for vertex_pos in vertices:
        # Find all bones within envelope distance
        bone_influences = []
        
        for bone_idx, bone in enumerate(bones_info):
            head_pos = bone[2].as_tuple()
            tail_pos = bone[3].as_tuple()
            radius = bone[4]
            
            # Calculate distance from vertex to bone segment
            dist = distance_point_to_segment(vertex_pos, head_pos, tail_pos)
            
            # Weight based on distance and bone radius
            envelope_radius = radius + envelope_distance
            if dist < envelope_radius:
                weight = 1.0 - (dist / envelope_radius)
                bone_influences.append((bone_idx, weight))
        
        # Sort by weight and take top N influences
        bone_influences.sort(key=lambda x: x[1], reverse=True)
        bone_influences = bone_influences[:element_size]
        
        # Normalize weights
        total_weight = sum(w for _, w in bone_influences)
        if total_weight > 0:
            for bone_idx, weight in bone_influences:
                joint_idx = bone_to_joint_map.get(bone_idx, 0)
                joint_indices.append(joint_idx)
                joint_weights.append(weight / total_weight)
        
        # Pad if needed
        while len(joint_indices) % element_size != 0:
            joint_indices.append(0)
            joint_weights.append(0.0)
    
    return joint_indices, joint_weights
```

**Pros:** Most accurate replication of Blender behavior

**Cons:** Computationally expensive, may produce unexpected influences

## Recommendations

### Understanding the Problem

The fundamental issue is that **USD skeletal mesh deformation is NOT the same as Blender's armature deformation**:

- **Blender**: Automatically blends vertex influences from multiple bones based on envelope distance and bone hierarchy
- **USD/Unreal**: Uses explicit per-vertex joint weights - no automatic blending

Grove's single-bone rigid binding works in Blender because Blender's armature system compensates. USD requires explicit multi-bone weights.

### Recommended Solution: Junction-Aware Blending (Solution 1)

Implement Solution 1 (junction blending) because:

1. **Targeted approach**: Only adds complexity where needed (branch junctions)
2. **Preserves Grove structure**: Keeps bone positions unchanged
3. **Configurable**: Blend distance can be tuned per-species
4. **Performance**: Minimal overhead compared to full envelope calculation

### Implementation Priority

1. **First: Implement junction blending** (Solution 1)
   - Focus on branch root bones (is_branch_root = True)
   - Blend with parent bone within configurable distance
   - Use linear falloff initially, can refine later

2. **Add quality parameters**:

   ```python
   --junction-blend-distance 0.1  # Blend radius in meters
   --junction-blend-mode {linear,smooth,distance}  # Falloff function
   --skip-junction-blending  # Disable for testing/comparison
   ```

3. **Optional: Envelope deformation** (Solution 3)
   - Only if junction blending insufficient
   - More expensive but more accurate to Blender behavior

### Testing Strategy

Create test cases with problematic branch angles:

```python
# Test Case 1: Wide-angle branch (> 45 degrees from stem)
# Test Case 2: Thin branch with long root bone
# Test Case 3: Multiple branches clustered near same junction
```

Compare results in Unreal Engine skeleton editor by:

1. Rotating branch root joints
2. Observing branch-stem connection deformation
3. Validating smooth transitions (no gaps/tears)

## Grove Blender Export Reference

The Grove Blender addon (`src/the_grove_22/addons/the_grove_22_in_blender/`) handles this correctly for Blender's armature system. Key files to examine:

- **`Operators/OperatorBuild.py`** - Build operators for mesh generation
- **`Operators/OperatorSkeleton.py`** (if exists) - Skeleton building
- **`File.py`** - Grove data serialization

These may reveal how Grove computes proper vertex weights for Blender.

## Conclusion

**Key Insight:** Grove uses single-bone rigid binding in all platforms (Blender, Houdini). The smooth animation in Blender comes from **Blender's armature system automatically blending influences**, not from Grove providing multi-bone weights.

**USD skeletal mesh does not have this automatic blending** - we must compute multi-bone weights explicitly.

**Solution:** Implement junction-aware blending that adds multi-bone influences at branch connection points, using Grove's `is_branch_root` and `branch_id` data to identify where blending is needed.

**Next Steps:**

1. Implement `calculate_vertex_weights_with_junction_blending()` in `skeleton.py`
2. Add `--junction-blend-distance` CLI parameter to `generate_forest.py`
3. Test with current forest exports, focusing on wide-angle branches
4. Consider envelope-based approach if junction blending proves insufficient
