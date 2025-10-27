# Skeletal Assembly Reference Guide

**Purpose**: This document describes the complete structure and insights for creating USD skeletal assemblies compatible with Unreal Engine's Nanite system, based on validated working demos.

**Date**: October 27, 2025  
**Status**: Validated and Working ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Critical Architectural Insights](#critical-architectural-insights)
3. [File Structure](#file-structure)
4. [Skeleton Setup](#skeleton-setup)
5. [Mesh Structure](#mesh-structure)
6. [Skinning Configuration](#skinning-configuration)
7. [Branch Integration](#branch-integration)
8. [PointInstancer for Twigs](#pointinstancer-for-twigs)
9. [Nanite Assembly Configuration](#nanite-assembly-configuration)
10. [Implementation Checklist](#implementation-checklist)

---

## Overview

This reference describes the working skeletal assembly structure validated through iterative development. The demos represent the correct architecture for converting Grove tree exports into Unreal-compatible skeletal meshes with Nanite support.

**Key Files**:

- `demo_tree_skel.usda` - Main tree with trunk, branches, and skeleton
- `demo_twig_skel.usda` - Instanced twig prototype
- `demo_assembly_external_ref.usda` - Nanite assembly root with PointInstancer

**Validation**: Structure confirmed to match actual Grove exports (all 13 tested exports use single merged mesh architecture).

---

## Critical Architectural Insights

### 1. Single Merged Mesh Architecture

**Grove exports ALL geometry in a single TreeMesh** - branches are NOT separate meshes.

```
✅ CORRECT: Single TreeMesh with trunk + branch vertices
❌ INCORRECT: Separate BranchMesh and TreeMesh
```

**Why This Matters**:

- Branches connect seamlessly to trunk (shared vertices)
- No visual gaps during skeletal deformation
- Matches actual Grove export structure (verified across 13 files)
- Simplifies skinning (single weight array for entire tree)

**Implementation**: Branch base vertices reference the same indices as trunk connection vertices.

### 2. Multi-Joint Skinning (elementSize = 2)

Each vertex is influenced by **exactly 2 joints** for smooth deformation.

```python
elementSize = 2  # Each vertex has 2 joint influences
interpolation = "vertex"
```

**Weight Distribution Pattern**:

- Base vertices (z=0): `[1.0, 0.0]` - 100% root joint
- Connection vertices: `[0.5, 0.5]` - Blend between parent and child joints
- Tip vertices: `[0.5, 0.5]` or `[0.7, 0.3]` - Weighted toward primary joint

**Example**:

```python
# Vertex 3 (first connection ring at z=1)
jointIndices = [1, 0]    # Bound to joint_1 and root
jointWeights = [0.5, 0.5]  # 50/50 blend
```

### 3. Hierarchical Joint Naming

Joint paths define parent-child relationships through naming convention.

```python
joints = [
    "root",                                    # Joint 0
    "root/joint_1",                           # Joint 1 (child of 0)
    "root/joint_1/joint_2",                   # Joint 2 (child of 1)
    "root/joint_1/joint_2/joint_3",          # Joint 3 (child of 2)
    "root/joint_1/branch_1",                  # Joint 4 (branch from 1)
    "root/joint_1/branch_1/branch_tip",      # Joint 5 (child of 4)
]
```

**Behavior**: Rotating `joint_1` affects joints 2, 3, 4, and 5 (all descendants).

### 4. Shared Vertices for Branch Connection

Branch base vertices MUST share indices with trunk connection vertices.

**Trunk vertices** (indices 0-11):

```python
points = [
    (0, 0, 0), (0.1, 0, 0), (-0.05, 0.087, 0),      # Ring 0 (z=0)
    (0, 0, 1), (0.1, 0, 1), (-0.05, 0.087, 1),      # Ring 1 (z=1) ← Connection
    (0, 0, 2), (0.1, 0, 2), (-0.05, 0.087, 2),      # Ring 2 (z=2)
    (0, 0, 3), (0.1, 0, 3), (-0.05, 0.087, 3),      # Ring 3 (z=3)
]
```

**Branch vertices** (indices 12-14):

```python
# Branch extends from connection ring (indices 3, 4, 5)
(0.4, 0, 1.3), (0.45, 0.05, 1.3), (0.45, -0.05, 1.3)  # Branch tip
```

**Branch faces** reference both trunk and branch vertices:

```python
faceVertexIndices = [
    # Branch faces use connection vertices (3,4,5) and branch tip (12,13,14)
    3, 4, 12,    # Triangle connecting trunk to branch
    4, 13, 12,
    3, 12, 5,
    12, 14, 5,
    3, 5, 4,     # Cap faces
    5, 14, 13
]
```

**Result**: Physically impossible for gap to appear between branch and trunk.

### 5. Twig Bones in Main Skeleton

Twigs are instanced via PointInstancer but require bones in the main tree skeleton.

```python
joints = [
    # ... trunk and branch joints ...
    "root/joint_1/twig_1",                           # Joint 6
    "root/joint_1/joint_2/twig_2",                   # Joint 7
    "root/joint_1/branch_1/branch_tip/twig_3"       # Joint 8
]
```

**PointInstancer Binding**:

```python
primvars:unreal:naniteAssembly:bindJoints = [
    "root/joint_1/twig_1",                     # Instance 0 follows joint 6
    "root/joint_1/joint_2/twig_2",            # Instance 1 follows joint 7
    "root/joint_1/branch_1/branch_tip/twig_3" # Instance 2 follows joint 8
]
```

**Important**: Twig bones are in the tree skeleton for reference only - they don't deform the tree mesh.

---

## File Structure

### demo_tree_skel.usda

Main tree file with complete skeleton and merged trunk+branch geometry.

```
SkelRoot "Tree"
├── Skeleton "TreeSkel"
│   ├── joints [9 joints: root, trunk×3, branch×2, twig×3]
│   ├── bindTransforms [9 matrices in world space]
│   └── restTransforms [9 matrices in local space]
└── Mesh "TreeMesh"
    ├── points [15 vertices: trunk×12, branch_tip×3]
    ├── faceVertexIndices [24 triangles: trunk×18, branch×6]
    ├── primvars:skel:jointIndices [elementSize=2]
    └── primvars:skel:jointWeights [elementSize=2]
```

### demo_twig_skel.usda

Simple skeletal mesh for instancing (leaf/twig prototype).

```
SkelRoot "Twig"
├── Skeleton "Skel"
│   ├── joints ["root"]
│   ├── bindTransforms [1 identity matrix]
│   └── restTransforms [1 identity matrix]
└── Mesh "Mesh"
    ├── points [4 vertices forming quad]
    ├── faceVertexIndices [1 quad face]
    ├── primvars:skel:jointIndices [all bound to joint 0]
    └── primvars:skel:jointWeights [all 1.0]
```

### demo_assembly_external_ref.usda

Nanite Assembly root that composes tree and twig instances.

```
Xform "DemoAssemblyExternal" [NaniteAssemblyRootAPI]
├── unreal:naniteAssembly:meshType = "skeletalMesh"
├── unreal:naniteAssembly:skeleton → TreeSkel
├── SkelRoot "TreeMesh" [references demo_tree_skel.usda]
├── Scope "TwigPrototypes"
│   └── Xform "twig" [instanceable=true]
│       └── SkelRoot "TwigSkelRoot" [references demo_twig_skel.usda]
└── PointInstancer "TwigInstances" [NaniteAssemblySkelBindingAPI]
    ├── positions [3 locations]
    ├── orientations [3 quaternions]
    ├── primvars:unreal:naniteAssembly:bindJoints [3 joint paths]
    └── prototypes → /TwigPrototypes/twig
```

---

## Skeleton Setup

### Joint Array Structure

```python
joints = [
    "root",                                        # 0: Base joint
    "root/joint_1",                               # 1: First trunk segment
    "root/joint_1/joint_2",                       # 2: Second trunk segment
    "root/joint_1/joint_2/joint_3",              # 3: Third trunk segment
    "root/joint_1/branch_1",                      # 4: Branch base
    "root/joint_1/branch_1/branch_tip",          # 5: Branch tip
    "root/joint_1/twig_1",                        # 6: Twig mount 1
    "root/joint_1/joint_2/twig_2",               # 7: Twig mount 2
    "root/joint_1/branch_1/branch_tip/twig_3"    # 8: Twig mount 3
]
```

**Total**: 9 joints (4 trunk + 2 branch + 3 twig mounts)

### Transform Matrices

**bindTransforms** - World space positions of joints (inverse bind pose):

```python
bindTransforms = [
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1) ),        # Joint 0 at origin
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,1,1) ),        # Joint 1 at z=1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,2,1) ),        # Joint 2 at z=2
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,3,1) ),        # Joint 3 at z=3
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.1,0,1,1) ),      # Branch base
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.4,0,1.3,1) ),    # Branch tip
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.1,0.05,1.5,1) ), # Twig 1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (-0.05,0.087,2.5,1) ), # Twig 2
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.45,0,1.3,1) )    # Twig 3
]
```

**restTransforms** - Local space offsets from parent joint:

```python
restTransforms = [
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1) ),        # Root (no parent)
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,1,1) ),        # +1 in Z from root
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,1,1) ),        # +1 in Z from joint_1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,1,1) ),        # +1 in Z from joint_2
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.1,0,0,1) ),      # +0.1 in X from joint_1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.3,0,0.3,1) ),    # Offset from branch_1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.1,0.05,0.5,1) ), # Offset from joint_1
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (-0.05,0.087,0.5,1) ), # Offset from joint_2
    ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.05,0,0,1) )      # Offset from branch_tip
]
```

---

## Mesh Structure

### Vertex Layout

**Trunk vertices** (12 total: 4 rings × 3 vertices per ring):

```python
# Ring 0 (base, z=0) - Indices 0-2
(0, 0, 0), (0.1, 0, 0), (-0.05, 0.087, 0)

# Ring 1 (connection point, z=1) - Indices 3-5 ← CRITICAL
(0, 0, 1), (0.1, 0, 1), (-0.05, 0.087, 1)

# Ring 2 (z=2) - Indices 6-8
(0, 0, 2), (0.1, 0, 2), (-0.05, 0.087, 2)

# Ring 3 (top, z=3) - Indices 9-11
(0, 0, 3), (0.1, 0, 3), (-0.05, 0.087, 3)
```

**Branch vertices** (3 total: tip ring):

```python
# Branch tip (z=1.3) - Indices 12-14
(0.4, 0, 1.3), (0.45, 0.05, 1.3), (0.45, -0.05, 1.3)
```

### Face Indices

**Trunk faces** (18 triangles from 3 cylindrical segments):

```python
# Segment 0-1 (rings 0→1)
0,1,3, 1,4,3, 0,3,2, 3,5,2, 0,2,1, 2,5,4, 1,2,4

# Segment 1-2 (rings 1→2)
3,4,6, 4,7,6, 3,6,5, 6,8,5, 3,5,4, 5,8,7, 4,5,7

# Segment 2-3 (rings 2→3)
6,7,9, 7,10,9, 6,9,8, 9,11,8, 6,8,7, 8,11,10, 7,8,10
```

**Branch faces** (6 triangles connecting to trunk):

```python
# Branch connects ring 1 (3,4,5) to branch tip (12,13,14)
3,4,12,    # Side face 1
4,13,12,   # Side face 2
3,12,5,    # Side face 3
12,14,5,   # Side face 4
3,5,4,     # Cap face 1
5,14,13    # Cap face 2
```

**Key**: Branch faces reference trunk vertices (3,4,5) ensuring seamless connection.

---

## Skinning Configuration

### Joint Indices (elementSize = 2)

Each vertex bound to 2 joints for smooth blending:

```python
primvars:skel:jointIndices = [
    # Ring 0 (vertices 0-2): Fully bound to root
    0,0, 0,0, 0,0,
    
    # Ring 1 (vertices 3-5): Blend root and joint_1
    1,0, 1,0, 1,0,
    
    # Ring 2 (vertices 6-8): Blend joint_1 and joint_2
    2,1, 2,1, 2,1,
    
    # Ring 3 (vertices 9-11): Blend joint_2 and joint_3
    3,2, 3,2, 3,2,
    
    # Branch tip (vertices 12-14): Blend branch_tip and branch_1
    5,4, 5,4, 5,4
] (
    elementSize = 2
    interpolation = "vertex"
)
```

### Joint Weights (elementSize = 2)

Corresponding weight values:

```python
primvars:skel:jointWeights = [
    # Ring 0: 100% root, 0% secondary
    1.0,0.0, 1.0,0.0, 1.0,0.0,
    
    # Ring 1: 50% joint_1, 50% root (smooth blend)
    0.5,0.5, 0.5,0.5, 0.5,0.5,
    
    # Ring 2: 50% joint_2, 50% joint_1
    0.5,0.5, 0.5,0.5, 0.5,0.5,
    
    # Ring 3: 50% joint_3, 50% joint_2
    0.5,0.5, 0.5,0.5, 0.5,0.5,
    
    # Branch tip: 70% branch_tip, 30% branch_1 (stronger tip influence)
    0.7,0.3, 0.7,0.3, 0.7,0.3
] (
    elementSize = 2
    interpolation = "vertex"
)
```

**Weight Tuning**:

- Equal weights (0.5/0.5): Maximum smoothness at joints
- Biased weights (0.7/0.3): More control from primary joint
- Connection vertices should always blend parent and child joints

---

## Branch Integration

### Critical Implementation Steps

1. **Identify Connection Point**:
   - Determine which trunk ring the branch should connect to
   - In demo: Ring 1 at z=1 (vertices 3, 4, 5)

2. **Extend Point Array**:

   ```python
   # Original trunk points (0-11)
   points = [trunk_vertices...]
   
   # Add branch tip vertices (12-14)
   points.extend([
       (0.4, 0, 1.3),      # Branch tip vertex 0
       (0.45, 0.05, 1.3),  # Branch tip vertex 1
       (0.45, -0.05, 1.3)  # Branch tip vertex 2
   ])
   ```

3. **Create Branch Faces Using Shared Vertices**:

   ```python
   # Branch faces MUST reference trunk connection vertices
   branch_faces = [
       3,4,12,    # Use trunk vertex 3,4 + branch vertex 12
       4,13,12,
       3,12,5,    # Use trunk vertex 3,5 + branch vertex 12
       12,14,5,
       3,5,4,
       5,14,13
   ]
   ```

4. **Add Branch Joints to Skeleton**:

   ```python
   joints.extend([
       "root/joint_1/branch_1",              # Branch base
       "root/joint_1/branch_1/branch_tip"    # Branch tip
   ])
   ```

5. **Skin Branch Vertices**:

   ```python
   # Branch tip vertices (12-14)
   jointIndices.extend([5,4, 5,4, 5,4])      # Bound to branch_tip + branch_1
   jointWeights.extend([0.7,0.3, 0.7,0.3, 0.7,0.3])  # 70% tip, 30% base
   ```

**Result**: Branch geometry fully integrated into single mesh, sharing vertices with trunk at connection point.

---

## PointInstancer for Twigs

### Configuration

Twigs use PointInstancer for efficient instancing without geometry duplication.

```python
def PointInstancer "TwigInstances" (
    prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
)
{
    # Instance transforms
    point3f[] positions = [
        (0.1, 0.05, 1.5),    # Twig 1 position
        (-0.05, 0.087, 2.5), # Twig 2 position
        (0.45, 0, 1.3)       # Twig 3 position (on branch tip)
    ]
    quath[] orientations = [(1,0,0,0), (1,0,0,0), (1,0,0,0)]
    float3[] scales = [(1,1,1), (1,1,1), (1,1,1)]
    
    # Instance-to-prototype mapping
    int[] protoIndices = [0, 0, 0]  # All use same prototype
    rel prototypes = </DemoAssemblyExternal/TwigPrototypes/twig>
    
    # Skeletal binding
    uniform token[] primvars:unreal:naniteAssembly:bindJoints = [
        "root/joint_1/twig_1",                    # Instance 0 → Joint 6
        "root/joint_1/joint_2/twig_2",           # Instance 1 → Joint 7
        "root/joint_1/branch_1/branch_tip/twig_3" # Instance 2 → Joint 8
    ] (
        interpolation = "uniform"
    )
    uniform float[] primvars:unreal:naniteAssembly:bindJointWeights = [1,1,1] (
        interpolation = "uniform"
    )
}
```

### Twig Prototype Structure

```python
def Scope "TwigPrototypes"
{
    def Xform "twig" (
        instanceable = true  # ← CRITICAL: Marks as instanceable
    )
    {
        def SkelRoot "TwigSkelRoot" (
            prepend references = @./demo_twig_skel.usda@</Twig>
        )
        {
        }
    }
}
```

**Key Points**:

- Prototype MUST be marked `instanceable = true`
- Twig bones (joints 6,7,8) exist in main tree skeleton
- Each instance binds to specific twig bone via `bindJoints`
- PointInstancer handles transforms, not geometry duplication

---

## Nanite Assembly Configuration

### Root Xform Setup

```python
def Xform "DemoAssemblyExternal" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
    kind = "assembly"
)
{
    # Specify skeletal mesh type
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    
    # Reference to main skeleton
    rel unreal:naniteAssembly:skeleton = </DemoAssemblyExternal/TreeMesh/TreeSkel>
    
    # ... child prims ...
}
```

**Required APIs**:

- `NaniteAssemblyRootAPI` - Marks assembly root
- `GeomModelAPI` - Defines model hierarchy
- `kind = "assembly"` - USD kind for assemblies

**Critical Attributes**:

- `meshType = "skeletalMesh"` - Tells Unreal to import as skeletal mesh
- `skeleton` relationship - Points to main skeleton (tree skeleton, not twig)

### External References

```python
def SkelRoot "TreeMesh" (
    prepend references = @./demo_tree_skel.usda@</Tree>
)
{
}
```

**Best Practice**: Use external references for modularity:

- Tree mesh in separate file
- Twig prototype in separate file
- Assembly composes them with PointInstancer

---

## Implementation Checklist

### For GrowPy USD Export

- [ ] **Mesh Architecture**
  - [ ] Export all trunk + branch geometry in single TreeMesh
  - [ ] Ensure branch base vertices share indices with trunk connection ring
  - [ ] Create branch faces that reference trunk vertices

- [ ] **Skeleton Setup**
  - [ ] Generate hierarchical joint paths (e.g., `root/trunk_1/trunk_2/branch_1`)
  - [ ] Include twig mount bones in main skeleton
  - [ ] Calculate bindTransforms (world space positions)
  - [ ] Calculate restTransforms (local offsets from parent)

- [ ] **Skinning**
  - [ ] Set `elementSize = 2` for multi-joint skinning
  - [ ] Bind each vertex to 2 joints (primary + parent or child)
  - [ ] Use smooth weight distribution (typically 0.5/0.5 or 0.7/0.3)
  - [ ] Ensure connection vertices blend parent and child joints

- [ ] **Branch Handling**
  - [ ] Identify branch connection points (which trunk vertices)
  - [ ] Add branch tip vertices to main point array
  - [ ] Create branch faces using shared trunk connection vertices
  - [ ] Add branch joints to skeleton with correct hierarchy
  - [ ] Skin branch vertices to branch joints

- [ ] **Twig Integration**
  - [ ] Add twig mount bones to tree skeleton at appropriate locations
  - [ ] Create twig prototype with SkelRoot and simple geometry
  - [ ] Mark twig prototype as `instanceable = true`
  - [ ] Setup PointInstancer with positions and orientations
  - [ ] Bind instances to twig bones via `bindJoints` primvar

- [ ] **Nanite Assembly**
  - [ ] Create root Xform with NaniteAssemblyRootAPI
  - [ ] Set `meshType = "skeletalMesh"`
  - [ ] Link skeleton via `unreal:naniteAssembly:skeleton` relationship
  - [ ] Use external references for tree and twig files
  - [ ] Configure PointInstancer with NaniteAssemblySkelBindingAPI

- [ ] **Validation**
  - [ ] Check that Grove exports use single merged mesh (grep -c "def Mesh" = 1)
  - [ ] Verify branch faces reference trunk vertices
  - [ ] Confirm all joints have both bind and rest transforms
  - [ ] Test skeletal deformation (no gaps between trunk and branches)
  - [ ] Import to Unreal and verify skeleton structure

---

## Key Takeaways

1. **Single Mesh**: All trunk and branch geometry MUST be in one TreeMesh
2. **Shared Vertices**: Branch bases MUST share vertex indices with trunk
3. **Multi-Joint Skinning**: Use elementSize=2 with smooth weight blending
4. **Hierarchical Joints**: Joint paths define parent-child relationships
5. **Twig Bones**: Include twig mount bones in main skeleton for PointInstancer binding
6. **Validated Structure**: This architecture matches actual Grove exports (13/13 files confirmed)

---

**End of Reference Document**
