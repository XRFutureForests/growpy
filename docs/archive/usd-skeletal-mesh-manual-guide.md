# USD Skeletal Mesh Manual Building Guide

## Overview

This guide explains how to manually create a USD skeletal mesh file that imports correctly into Unreal Engine. We'll break down each component of the `demo_tree_skel.usda` file and explain how it works, what each value means, and how to troubleshoot issues.

## Table of Contents

1. [File Structure Overview](#file-structure-overview)
2. [Coordinate System and Units](#coordinate-system-and-units)
3. [Building the Skeleton](#building-the-skeleton)
4. [Creating the Mesh Geometry](#creating-the-mesh-geometry)
5. [Skinning: Binding Mesh to Skeleton](#skinning-binding-mesh-to-skeleton)
6. [Common Issues and How to Fix Them](#common-issues-and-how-to-fix-them)
7. [Step-by-Step Example](#step-by-step-example)

---

## File Structure Overview

A USD skeletal mesh file consists of these key components:

```
SkelRoot (root container)
├── Skeleton (bone hierarchy)
│   ├── joints (bone names)
│   ├── restTransforms (bone local transforms)
│   └── bindTransforms (bone world transforms)
└── Mesh (geometry)
    ├── points (vertex positions)
    ├── faceVertexIndices (triangle data)
    ├── skel:jointIndices (which bones affect each vertex)
    └── skel:jointWeights (how much each bone influences)
```

---

## Coordinate System and Units

### Critical Settings

```usda
#usda 1.0
(
    defaultPrim = "Tree"      # Root object name
    metersPerUnit = 1         # 1 unit = 1 meter (100 cm in Unreal)
    upAxis = "Z"              # Z-axis points up (Unreal standard)
)
```

**Important Notes:**

- Unreal uses **Z-up** coordinate system, so always set `upAxis = "Z"`
- `metersPerUnit = 1` means 1 USD unit = 100 cm in Unreal
- If your tree looks too small/large in Unreal, adjust this value or scale your points

### Coordinate System Conversion

- **USD (Z-up)**: X=right, Y=forward, Z=up
- **Unreal (Z-up)**: X=forward, Y=right, Z=up
- When importing to Unreal, you may need to rotate -90° around Z-axis

---

## Building the Skeleton

### 1. Understanding Joint Hierarchy

Joints are defined as a **path-based hierarchy** using forward slashes:

```usda
uniform token[] joints = [
    "root",                              # Index 0 - Base of tree
    "root/joint_1",                      # Index 1 - Child of root
    "root/joint_1/branch_1",             # Index 2 - Child of joint_1
    "root/joint_1/branch_1/branch_tip"   # Index 3 - Child of branch_1
]
```

**Key Points:**

- Each joint has an **index** (0, 1, 2, 3...)
- Parent-child relationships are defined by the path structure
- The root joint is typically at the origin
- Joint indices are used later for skinning

### 2. Rest Transforms (Local Space)

`restTransforms` define each bone's transform **relative to its parent**:

```usda
uniform matrix4d[] restTransforms = [
    # root (at origin, no parent)
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) ),
    
    # root/joint_1 (1.5 meters up from root in Z)
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 1.5, 1) ),
    
    # root/joint_1/branch_1 (offset from joint_1)
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.1, 0, 0, 1) ),
    
    # root/joint_1/branch_1/branch_tip (tip of branch)
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.3, 0, 0.3, 1) )
]
```

**Matrix Format (4x4 transformation matrix):**

```
Row 1: (X-axis.x, X-axis.y, X-axis.z, 0)
Row 2: (Y-axis.x, Y-axis.y, Y-axis.z, 0)
Row 3: (Z-axis.x, Z-axis.y, Z-axis.z, 0)
Row 4: (Translation.x, Translation.y, Translation.z, 1)
```

**Identity Matrix (no rotation, no translation):**

```
( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )
```

**Translation Example:**
To move a joint 0.5 units in X, 0.3 in Y, 1.0 in Z:

```
( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.5, 0.3, 1.0, 1) )
```

### 3. Bind Transforms (World Space)

`bindTransforms` define each bone's **world space** position (accumulated from root):

```usda
uniform matrix4d[] bindTransforms = [
    # root at (0, 0, 0)
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) ),
    
    # joint_1 at (0, 0, 1.5) - root + restTransform
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 1.5, 1) ),
    
    # branch_1 at (0.1, 0, 1.0) - from root
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.1, 0, 1, 1) ),
    
    # branch_tip at (0.4, 0, 1.3) - from root
    ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.4, 0, 1.3, 1) )
]
```

**How to Calculate Bind Transforms:**

1. Root: Same as rest transform (identity at origin)
2. For each child: Multiply parent's bindTransform by child's restTransform
3. Or simply: bindTransform = accumulated world position

**Example Calculation:**

- `root` = identity at (0, 0, 0)
- `joint_1` = root + (0, 0, 1.5) = (0, 0, 1.5)
- `branch_1` = joint_1 at (0, 0, 1.5) + offset (0.1, 0, -0.5) = (0.1, 0, 1.0)

### 4. Why Both Rest and Bind Transforms?

- **restTransforms**: Define the hierarchy (parent-child relationships)
- **bindTransforms**: Define where bones are in 3D space for skinning
- **Mismatch = Problems**: If these don't match mathematically, vertices will be in wrong positions

---

## Creating the Mesh Geometry

### 1. Vertex Positions

```usda
point3f[] points = [
    # Base vertices (Z=0)
    (0, 0, 0),           # Vertex 0 - center base
    (0.1, 0, 0),         # Vertex 1 - right base
    (-0.1, 0.1, 0),      # Vertex 2 - left-forward base
    
    # Top trunk vertices (Z=1.5)
    (0, 0, 1.5),         # Vertex 3 - center top
    (0.1, 0, 1.5),       # Vertex 4 - right top
    (-0.1, 0.1, 1.5),    # Vertex 5 - left-forward top
    
    # Branch vertices
    (0.4, 0, 1.3),       # Vertex 6 - branch base
    (0.45, 0, 1.35)      # Vertex 7 - branch tip
]
```

**Current Structure:**

- 3 vertices at base forming a triangle
- 3 vertices at top forming a triangle
- 2 vertices for the branch

**Visualization:**

```
        3 (top center)
       /|\
      / | \
     /  |  \
    5---4   7 (branch tip)
    |   |  /
    |   | /
    |   |/
    2---1---6 (branch base)
    |   |
    |  /
    | /
    0 (root)
```

### 2. Face Topology

```usda
int[] faceVertexCounts = [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
```

- **12 triangular faces** (all triangles have 3 vertices)

```usda
int[] faceVertexIndices = [
    # Trunk faces (bottom section)
    0, 1, 3,    # Triangle connecting bottom and top
    1, 4, 3,    # Triangle completing quad
    0, 3, 2,    # Another side
    3, 5, 2,    # Complete that side
    0, 2, 1,    # Bottom cap
    2, 5, 4,    # Middle section
    1, 2, 4,    # Middle section
    
    # Trunk faces (top section)
    3, 4, 6,    # Side faces
    4, 7, 6,
    3, 6, 5,
    5, 7, 4
]
```

**How to Read Face Indices:**

- Each set of 3 numbers defines a triangle
- Numbers refer to vertex indices in the `points` array
- **Winding order matters**: Counter-clockwise = front-facing (in USD/OpenGL convention)

### 3. Mesh Properties

```usda
uniform bool doubleSided = 1
```

- **Double-sided**: Renders both sides of faces
- Set to `0` if you want backface culling
- Useful for trees where you see geometry from all angles

```usda
uniform token[] primvars:part = ["trunk"]
```

- **Part labeling**: Used for material assignment or organization
- Can have multiple parts like `["trunk", "branch", "leaves"]`

---

## Skinning: Binding Mesh to Skeleton

### 1. Joint Indices (Which Bones Affect Each Vertex)

```usda
int[] primvars:skel:jointIndices = [
    # Vertices 0, 1, 2 (base) - affected by joint 0 (root)
    0, 0,    # Vertex 0: primary=joint 0, secondary=joint 0
    0, 0,    # Vertex 1: primary=joint 0, secondary=joint 0
    0, 0,    # Vertex 2: primary=joint 0, secondary=joint 0
    
    # Vertices 3, 4, 5 (top trunk) - blend between root and joint_1
    1, 0,    # Vertex 3: primary=joint 1, secondary=joint 0
    1, 0,    # Vertex 4: primary=joint 1, secondary=joint 0
    1, 0,    # Vertex 5: primary=joint 1, secondary=joint 0
    
    # Vertices 6, 7 (branch) - affected by branch joints
    3, 2,    # Vertex 6: primary=branch_tip (3), secondary=branch_1 (2)
    3, 2     # Vertex 7: primary=branch_tip (3), secondary=branch_1 (2)
] (
    elementSize = 2              # Each vertex has 2 joint indices
    interpolation = "vertex"     # Per-vertex data
)
```

**Key Concepts:**

- `elementSize = 2`: Each vertex is influenced by **2 bones** (can be 1, 2, 4, etc.)
- **Joint indices** reference the joint array (0=root, 1=joint_1, etc.)
- More influences = smoother deformation but more expensive

### 2. Joint Weights (How Much Each Bone Influences)

```usda
float[] primvars:skel:jointWeights = [
    # Base vertices - 100% influenced by root
    1.0, 0.0,    # Vertex 0: 100% joint 0, 0% secondary
    1.0, 0.0,    # Vertex 1: 100% joint 0, 0% secondary
    1.0, 0.0,    # Vertex 2: 100% joint 0, 0% secondary
    
    # Top trunk - 50/50 blend
    0.5, 0.5,    # Vertex 3: 50% joint 1, 50% joint 0
    0.5, 0.5,    # Vertex 4: 50% joint 1, 50% joint 0
    0.5, 0.5,    # Vertex 5: 50% joint 1, 50% joint 0
    
    # Branch - 70% tip, 30% base
    0.7, 0.3,    # Vertex 6: 70% branch_tip, 30% branch_1
    0.7, 0.3     # Vertex 7: 70% branch_tip, 30% branch_1
] (
    elementSize = 2
    interpolation = "vertex"
)
```

**Critical Rules:**

- Weights must **sum to 1.0** for each vertex (1.0 + 0.0 = 1.0, 0.5 + 0.5 = 1.0)
- Weights are in **same order** as jointIndices
- **0.0** = no influence, **1.0** = full influence
- **Common blends**:
  - 1.0, 0.0 = rigid (100% one bone)
  - 0.5, 0.5 = smooth blend (joint in middle)
  - 0.7, 0.3 = weighted toward first bone

### 3. How Skinning Works

For each vertex, the final position is calculated as:

```
finalPosition = (bindTransform[joint0] * weight0) + (bindTransform[joint1] * weight1)
```

**Example for Vertex 3 (top trunk center):**

- jointIndices = [1, 0] → joint_1 and root
- jointWeights = [0.5, 0.5] → 50% each
- Position influenced by both trunk base and top → smooth deformation

---

## Common Issues and How to Fix Them

### Issue 1: Mesh Appears Stretched or Distorted

**Causes:**

1. **Mismatched transforms**: bindTransforms don't match accumulated restTransforms
2. **Wrong joint indices**: Pointing to non-existent joints
3. **Weights don't sum to 1.0**

**Fixes:**

```python
# Verify weights sum to 1.0
for i in range(0, len(jointWeights), 2):
    assert jointWeights[i] + jointWeights[i+1] == 1.0

# Recalculate bind transforms from rest transforms
def calculate_bind_transform(joint_idx, rest_transforms, joints):
    if parent is None:
        return rest_transforms[joint_idx]
    else:
        parent_bind = calculate_bind_transform(parent_idx, ...)
        return multiply_matrices(parent_bind, rest_transforms[joint_idx])
```

### Issue 2: Mesh is Invisible or Wrong Scale

**Causes:**

1. **Units mismatch**: `metersPerUnit` not matching your scale
2. **Coordinate system**: Using Y-up instead of Z-up
3. **Vertices at origin**: All points at (0,0,0)

**Fixes:**

- Set `upAxis = "Z"` for Unreal
- Set `metersPerUnit = 0.01` for centimeter units (or 1.0 for meter units)
- Scale your points appropriately: multiply all by 100 if switching from meters to cm

### Issue 3: Branch Detaches or Floats

**Causes:**

1. **Wrong bind transform** for branch joint
2. **Joint weights too high on parent** instead of child
3. **Branch vertices not skinned** to branch bones

**Fixes:**

```usda
# Ensure branch vertices use branch joints
# Vertex 6 should be influenced by branch_1 (index 2) or branch_tip (index 3)
int[] primvars:skel:jointIndices = [
    ...,
    3, 2,  # Correct: uses branch joints
    # NOT: 1, 0  # Wrong: uses trunk joints
]
```

### Issue 4: Mesh Looks Different in Unreal vs USD Viewer

**Causes:**

1. **Winding order**: Unreal may interpret faces differently
2. **Coordinate conversion**: Unreal converts Y-up to Z-up differently than expected
3. **Scale interpretation**: Units converted incorrectly

**Fixes:**

- Flip face winding if needed: reverse order of `faceVertexIndices`
- Apply import transform in Unreal: -90° rotation around Z
- Adjust `metersPerUnit` to match expected scale

### Issue 5: Skeleton Bones Point Wrong Direction

**Causes:**

1. **Rest transforms have rotation**: Not using identity rotation
2. **Bind transforms calculated wrong**

**Fixes:**

- Keep rotation components as identity for simple cases:

```usda
# Correct (no rotation)
( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (x, y, z, 1) )

# Avoid complex rotations unless needed
```

---

## Step-by-Step Example: Building a Simple Trunk

Let's build a minimal skeletal trunk from scratch.

### Step 1: Define File Header

```usda
#usda 1.0
(
    defaultPrim = "SimpleTrunk"
    metersPerUnit = 1
    upAxis = "Z"
)
```

### Step 2: Create Skeleton with 2 Joints

```usda
def SkelRoot "SimpleTrunk" (
    prepend apiSchemas = ["SkelBindingAPI"]
)
{
    rel skel:animationSource = </SimpleTrunk/Skel>
    rel skel:skeleton = </SimpleTrunk/Skel>

    def Skeleton "Skel"
    {
        # Two joints: root and top
        uniform token[] joints = [
            "root",
            "root/top"
        ]
        
        # Rest transforms (local space)
        uniform matrix4d[] restTransforms = [
            # root: at origin
            ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) ),
            # top: 2 meters up from root
            ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 2, 1) )
        ]
        
        # Bind transforms (world space)
        uniform matrix4d[] bindTransforms = [
            # root: at (0, 0, 0)
            ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) ),
            # top: at (0, 0, 2)
            ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 2, 1) )
        ]
    }
```

### Step 3: Create Simple Cylinder Mesh

```usda
    def Mesh "TrunkMesh" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        uniform bool doubleSided = 1
        
        # 4 vertices: 2 at bottom, 2 at top (simplified cylinder)
        point3f[] points = [
            # Bottom ring (Z=0)
            (0.1, 0, 0),      # Vertex 0
            (-0.1, 0, 0),     # Vertex 1
            # Top ring (Z=2)
            (0.1, 0, 2),      # Vertex 2
            (-0.1, 0, 2)      # Vertex 3
        ]
        
        # 4 triangular faces (2 quads = 4 triangles)
        int[] faceVertexCounts = [3, 3, 3, 3]
        int[] faceVertexIndices = [
            # Front face
            0, 2, 1,
            1, 2, 3,
            # Back face (opposite winding)
            0, 1, 2,
            1, 3, 2
        ]
        
        rel skel:skeleton = </SimpleTrunk/Skel>
        
        # Joint influences
        int[] primvars:skel:jointIndices = [
            # Bottom vertices use root (joint 0)
            0, 0,    # Vertex 0
            0, 0,    # Vertex 1
            # Top vertices use top joint (joint 1)
            1, 0,    # Vertex 2
            1, 0     # Vertex 3
        ] (
            elementSize = 2
            interpolation = "vertex"
        )
        
        float[] primvars:skel:jointWeights = [
            # Bottom: 100% root
            1.0, 0.0,    # Vertex 0
            1.0, 0.0,    # Vertex 1
            # Top: 100% top joint
            1.0, 0.0,    # Vertex 2
            1.0, 0.0     # Vertex 3
        ] (
            elementSize = 2
            interpolation = "vertex"
        )
    }
}
```

### Step 4: Test and Validate

1. **Save as** `simple_trunk.usda`
2. **View in USD viewer** (usdview) to check:
   - Skeleton hierarchy visible
   - Mesh renders correctly
   - No stretching or distortion
3. **Import to Unreal**:
   - File → Import
   - Select USD file
   - Check scale and orientation
   - Test in skeletal mesh editor

---

## Advanced Topics

### Adding a Branch

To add a branch, you need:

1. **New joint** in the hierarchy
2. **Rest transform** positioning it relative to parent
3. **Bind transform** in world space
4. **Branch vertices** with appropriate skinning

```usda
uniform token[] joints = [
    "root",
    "root/trunk",
    "root/trunk/branch",        # New branch joint
    "root/trunk/branch/tip"     # Branch tip
]

# Add vertices for branch geometry
point3f[] points = [
    ...,  # existing trunk vertices
    (0.5, 0, 1.0),   # Branch base
    (0.8, 0, 1.2)    # Branch tip
]

# Skin branch vertices to branch joints
int[] primvars:skel:jointIndices = [
    ...,  # existing skinning
    2, 1,  # Branch base: mostly branch joint, some trunk
    3, 2   # Branch tip: mostly tip, some branch base
]

float[] primvars:skel:jointWeights = [
    ...,
    0.7, 0.3,  # Branch base blending
    0.8, 0.2   # Branch tip (more rigid)
]
```

### Multiple Meshes on One Skeleton

You can have multiple meshes (trunk, leaves, bark) sharing one skeleton:

```usda
def SkelRoot "Tree" {
    def Skeleton "TreeSkel" { ... }
    
    def Mesh "TrunkMesh" {
        rel skel:skeleton = </Tree/TreeSkel>
        ...
    }
    
    def Mesh "LeavesMesh" {
        rel skel:skeleton = </Tree/TreeSkel>
        ...
    }
}
```

Both meshes can reference the same skeleton and have their own skinning weights.

---

## Debugging Checklist

When your skeletal mesh looks wrong:

- [ ] Verify `upAxis = "Z"` for Unreal
- [ ] Check `metersPerUnit` matches your scale expectations
- [ ] Ensure joint count matches between joints/restTransforms/bindTransforms
- [ ] Verify jointIndices don't reference out-of-bounds joint indices
- [ ] Confirm jointWeights sum to 1.0 for each vertex
- [ ] Check that number of points matches vertex data in skinning
- [ ] Validate face indices don't exceed point array bounds
- [ ] Test in USD viewer before importing to Unreal
- [ ] Compare bindTransforms against expected world positions
- [ ] Verify parent-child relationships in joint paths

---

## Summary

**Key Takeaways:**

1. **Skeleton = Hierarchy + Transforms**
   - Joint names define parent-child structure
   - restTransforms = local space (relative to parent)
   - bindTransforms = world space (absolute positions)

2. **Mesh = Geometry + Topology**
   - points = vertex positions
   - faceVertexIndices = triangle definitions
   - Must match coordinate system (Z-up for Unreal)

3. **Skinning = Binding Mesh to Bones**
   - jointIndices = which bones affect each vertex
   - jointWeights = how much each bone influences
   - Must sum to 1.0 and match elementSize

4. **Common Problems = Mismatched Data**
   - Transform mismatches cause stretching
   - Wrong indices cause missing geometry
   - Weight errors cause distortion

**Next Steps:**

- Experiment with the simple trunk example
- Add complexity gradually (more joints, branches)
- Test frequently in USD viewer and Unreal
- Keep backups of working versions
