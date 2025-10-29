# Skeletal Nanite Assembly - Root Cause Analysis

## The Problem

Mesh deformations occur when moving bones in the skeletal assembly, even after implementing face-to-joint mapping. This indicates the twig instances are binding to incorrect joints.

## Root Cause

### What We Were Doing Wrong

1. **Using face skinning weights** (primvars:skel:jointIndices) to determine twig binding
2. **Spatial nearest neighbor search** as fallback
3. Both approaches ignore the **topological structure** of the tree

### The Fundamental Issue

**Spatial proximity ≠ Topological correctness**

A twig at the tip of branch A might be spatially closer to the base of branch B, but it should bind to branch A's joint.

## The Correct Approach (From Hullabulla + References)

### Data Grove Provides

From the Grove API output (`the-grove-output-complete.py`):

```python
# Face attributes (per-face data)
face_attribute_branch_id        # Which branch each face belongs to
face_attribute_twig_long        # Boolean: face has long twig
face_attribute_twig_short       # Boolean: face has short twig
face_attribute_twig_upward      # Boolean: face has upward twig
face_attribute_twig_dead        # Boolean: face has dead twig

# Skeleton data
skeleton.poly_lines             # Polylines connecting joints
skeleton.face_attribute_branch_id  # Branch ID for each polyline
```

### Correct Mapping Pipeline

```
Twig Face → Branch ID → Skeleton Polyline → Joint Path
```

**Step by step:**

1. **Twig face index** → Look up `face_attribute_branch_id[face_idx]` → Get branch ID
2. **Branch ID** → Find skeleton polyline where `skeleton.face_attribute_branch_id == branch_id`
3. **Polyline** → Get joint indices in polyline (typically use the END joint for twigs)
4. **Joint index** → Convert to joint path (e.g., "root/joint_1/joint_2")

### Why This Works

- **Topologically correct**: Respects the tree's branching structure
- **No ambiguity**: Each face belongs to exactly one branch
- **Direct mapping**: No calculations, just lookups
- **Matches Grove's data**: Uses attributes Grove already provides

## Reference File Analysis

### From `skeletal_nanite_assembly_reference/nanite_assembly.usda`

```usda
uniform token[] primvars:unreal:naniteAssembly:bindJoints = [
    "root/joint_1",
    "root/joint_1/joint_2",
    "root/joint_1/joint_4"
] (
    interpolation = "uniform"
)
```

- **Interpolation**: `uniform` (per-instance, not per-vertex)
- **ElementSize**: Implicitly 1 (each instance binds to 1 joint)
- **Format**: Full hierarchical joint paths

### From `skeletal_nanite_assembly_reference/tree.usda`

```usda
int[] primvars:skel:jointIndices = [...] (
    elementSize = 2
    interpolation = "vertex"
)
```

- **Interpolation**: `vertex` (per-vertex skinning)
- **ElementSize**: 2 (each vertex influenced by 2 joints)
- **Purpose**: Mesh deformation, NOT instance binding

## Key Insights from Hullabulla Video

1. **Each leaf/twig needs a root bone skeleton** - even single leaves
2. **PointInstancer binding** is separate from vertex skinning
3. **bindJoints maps instance → tree skeleton** for placement
4. **Each twig's internal skeleton** deforms its own vertices
5. **No cross-skeleton binding**: Tree skeleton moves instances, twig skeleton deforms twig mesh

## Implementation Strategy

### Phase 1: Use Branch ID Mapping (Correct Approach)

```python
def map_twig_to_joint(face_idx, tree_model, skeleton):
    """Map twig face to correct joint using branch topology."""

    # 1. Get branch ID from face
    branch_id = tree_model.face_attribute_branch_id[face_idx]

    # 2. Find skeleton polyline for this branch
    polyline_idx = skeleton.face_attribute_branch_id.index(branch_id)
    polyline = skeleton.poly_lines[polyline_idx]

    # 3. Get end joint (where twigs typically attach)
    end_joint_idx = polyline[-1]

    # 4. Convert to joint path
    joint_path = skeleton_index_to_path(end_joint_idx, skeleton)

    return joint_path
```

### Phase 2: Simplify and Standardize

1. **Remove deprecated nearest neighbor code**
2. **Use camelCase naming** for all species/asset names
3. **Create single source of truth** for branch→joint mapping
4. **Add validation** to ensure mapping succeeds

## Testing Checklist

- [ ] Twig instances follow correct branch when bones move
- [ ] No mesh deformations/stretching
- [ ] Respects tree topology (not just spatial proximity)
- [ ] Works with manually created reference files
- [ ] Interpolation modes match reference exactly

## Implementation Status

✅ **COMPLETED** - Branch ID mapping has been implemented throughout the pipeline:

### Changes Made

1. **[twig_placement.py](../src/growpy/io/twig_placement.py)**
   - Extract `BranchIndex` attribute from mesh faces
   - Add `branch_id` to placement data for each twig

2. **[usd_builder.py](../src/growpy/io/usd_builder.py)**
   - Build branch_id → joint_path mapping during skeleton generation
   - Export mapping as skeleton primvars (`branchIds` and `branchJointPaths`)
   - Ensures topological data is preserved in USD

3. **[unreal_nanite_assembly.py](../src/growpy/io/unreal_nanite_assembly.py)**
   - Added `_build_branch_to_joint_mapping()` to read mapping from skeleton
   - Replaced face-to-joint approach with branch ID lookup
   - Removed duplicate `_find_nearest_joint()` function
   - Updated deprecation warnings
   - Spatial search kept only as fallback with prominent warnings

4. **[blender_export.py](../src/growpy/io/blender_export.py)**
   - Updated to use branch ID mapping instead of face-to-joint approach
   - Consistent with assembly generation pipeline

5. **[utils/strings.py](../src/growpy/utils/strings.py)**
   - Added `to_camel_case()` utility
   - Added `sanitize_species_name_camel_case()` for consistent naming
   - Available for standardizing species names throughout codebase

### Next Steps

1. Test with actual Grove tree generation
2. Verify no mesh deformations occur when moving bones
3. Create validation tests for branch-to-joint mapping
4. Consider applying camelCase naming to file outputs
