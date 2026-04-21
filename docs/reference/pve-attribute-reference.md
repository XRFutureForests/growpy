# PVE JSON Attribute Reference

This document provides a comprehensive reference for all attributes in the Procedural Vegetation Editor (PVE) JSON format, based on reverse-engineering the Unreal Engine PVE plugin source code.

## Overview

PVE JSON files consist of three main sections:

- **globalAttributes**: Tree-wide simulation parameters
- **points**: Per-point (vertex) data for the tree skeleton
- **primitives**: Per-branch data defining the tree structure

---

## Global Attributes

Global attributes control tree-wide simulation and rendering parameters.

### Growth Simulation Parameters

| Attribute | Type | Description | Usage |
|-----------|------|-------------|-------|
| `cycle` | int | Number of growth simulation iterations | Informational - indicates tree maturity |
| `cycleTime` | float | Time per growth cycle (0.333 = seasonal) | Informational |
| `randomSeed` | int | Random seed for procedural generation | Ensures reproducibility |
| `gravitationalForce` | float | Strength of gravitational effect on branches | Used by Gravity node for branch drooping |
| `maxBranchNumber` | int | Highest branch index in the tree | Metadata - not used in mesh building |
| `maxBudNumber` | int | Highest bud number in the tree | Metadata - not used in mesh building |
| `maxPscale` | float | Maximum point scale (radius) in the tree | Metadata - actual max computed from points |
| `minPscale` | float | Minimum point scale (radius) | Metadata |
| `max_curve_length` | float | Maximum branch curve length | Metadata |

### Phyllotaxy Parameters (Leaf/Branch Arrangement)

| Attribute | Type | Array Size | Description |
|-----------|------|------------|-------------|
| `phyllotaxyLeaf` | float[] | 10 | Leaf arrangement parameters |

**phyllotaxyLeaf Array Indices:**

- `[0]`: Unknown (reserved)
- `[1]`: PhyllotaxyFormation - angle between leaves (e.g., 137.5 for spiral)
- `[2]`: Unknown
- `[3]`: MinBudsLeaf - minimum buds per node
- `[4]`: MaxBudsLeaf - maximum buds per node
- `[5]`: Unknown
- `[6]`: ResetPhyllotaxy - whether to reset angle at branch start (0 or 1)
- `[7]`: PhyllotaxyOffset - initial rotation offset

**Phyllotaxy Types (derived from code):**

- **Alternate**: 180 degrees - leaves on opposite sides
- **Opposite**: 0 degrees - leaves in pairs
- **Decussate**: 90 degrees - pairs rotated 90 degrees
- **Whorled**: 90 degrees - multiple leaves per node
- **Spiral Patterns**:
  - Distichous: 180 degrees
  - Tristichous: 120 degrees
  - Pentastichous: 144 degrees
  - Octastichous: 135 degrees

### Plant Profile Arrays (Crown Shape)

| Attribute | Type | Array Size | Description |
|-----------|------|------------|-------------|
| `plantProfile_1` to `plantProfile_5` | float[] | 100 | Radial crown envelope definitions |

**Profile Structure:**

- 100 float values representing crown radius at 3.6-degree intervals around the tree
- Values typically range 0.75-1.0 (normalized radius)
- Used by Mesh Builder to scale trunk cross-section
- Multiple profiles provide variation between tree instances

**Usage in Mesh Building:**

```cpp
// PVMeshBuilder.cpp - applies profile to trunk radius
const float ProfileMultiplier = GetProfileMultiplier(ProfilePoints, ProfileUV_U);
FVector3f RadialPoint = PointPosition + (Direction * PointScale * ProfileMultiplier);
```

---

## Point Attributes

Point attributes store per-vertex data for the tree skeleton. All arrays must have exactly `num_points` elements.

### Position and Scale

| Attribute | Type | Description | Required |
|-----------|------|-------------|----------|
| `Position` | float[3][] | XYZ position in centimeters (Unreal units) | **CRITICAL** |
| `Scale` (pscale) | float[] | Radius at each point in meters | **CRITICAL** - max must be > 0 |

**Position Coordinate System:**

- Unreal uses left-handed Y-up coordinate system
- Positions are in centimeters (multiply meters by 100)
- Grove uses Z-up: swap Y and Z when exporting

**Scale (pscale) Warning:**

```cpp
// PVMeshBuilder.cpp line 748-749
const float MaxPointScale = *Algo::MaxElement(PointScales);
const float MaxScaleRatio = 1.0f / (MaxPointScale * UE_TWO_PI);
```

**If max pscale is 0, this causes a division by zero crash!**

### Distance Metrics

| Attribute | Type | Description | Usage |
|-----------|------|-------------|-------|
| `lengthFromRoot` | float[] | Distance from branch root point | UV mapping, foliage placement, **child branch matching** |
| `lengthFromSeed` | float[] | Distance from seed point | Alternative distance metric |

**CRITICAL: Child Branch Matching via lengthFromRoot**

The `lengthFromRoot` value for **child branch first points** is critical for Slope and Gravity node propagation. The PVE system matches child branches to their parent segment using `lengthFromRoot` comparison:

```cpp
// From PVSlope.cpp - GetBranchSegmentChildren()
const float ChildLengthFromRoot = PointFacade.GetLengthFromRoot(FirstChildPointIndex);
if (ChildLengthFromRoot > BranchPointLengthFromRoot || ChildLengthFromRoot <= PreviousBranchPointLengthFromRoot)
{
    continue;  // Child is NOT matched to this segment
}
```

**Matching Logic:**

- Child branch's first point must have `PreviousParentPointLFR < ChildFirstPointLFR <= CurrentParentPointLFR`
- If a child branch first point has LFR=0.0 but connects to a parent at LFR=0.9, the child will NOT be found
- Child first point LFR should equal the parent branch-off point LFR

**Example:**

```
Trunk points:        LFR: 0.0, 0.3, 0.6, 0.9, 1.2, 1.4, 1.6, 1.7
Child branch at trunk point 3 (LFR=0.9):
  - Child first point LFR should be 0.9 (NOT 0.0!)
  - This allows: 0.6 < 0.9 <= 0.9 = TRUE (child found)
```

**Usage:**

- Used for UV texture coordinate calculation
- Foliage distribution based on distance from trunk
- LOD calculations
- **Child branch matching in Slope/Gravity recursive traversal**

### LOD Gradients (Level of Detail)

| Attribute | Type | Range | Description |
|-----------|------|-------|-------------|
| `LOD_totalPscaleGradient` | float[] | 0-1 | Overall scale gradient for LOD |
| `LOD_hullGradient` | float[] | 0-1 | Distance from outer crown hull |
| `LOD_mainTrunkGradient` | float[] | 0-1 | Proximity to main trunk |
| `LOD_groundGradient` | float[] | 0-1 | Height from ground |

**Usage in Mesh Building:**

```cpp
// PVMeshBuilder.cpp - gradients control mesh detail retention
const float HullGradient = PointFacade.GetHullGradient(PointIndex);
const float PointHullGradient = 
    HullRetentionGradient.Eval(1.0f - HullGradient) * HullRetention;
```

These gradients control:

- Mesh density (more polygons near important features)
- Path simplification (remove points in less visible areas)
- Texture detail allocation

### Bud Information

| Attribute | Type | Array Size Per Point | Description |
|-----------|------|---------------------|-------------|
| `budNumber` | int[] | 1 | Sequential bud identifier (1-based) |
| `budDirection` | float[][] | 18 | Bud growth directions (6 buds x 3D vector) |
| `budDevelopment` | int[][] | 6 | Bud development state |
| `budHormoneLevels` | float[][] | 6 | Plant hormone levels |
| `budLightDetected` | float[][] | 4 | Light detection per bud |
| `budStatus` | int[][] | 10 | Bud status flags |

#### budNumber

Sequential identifier for each bud/point. Used for:

- Njord pixel ID assignment
- Branch source identification

#### budDirection (CRITICAL)

**Array Structure:** 18 floats = 6 buds x 3 components (XYZ direction vector)

```cpp
// PVMeshBuilder.cpp lines 806-807
const auto& PointBudDirections = PointFacade.GetBudDirections(PointIndex);
const FVector3f MainBudDirection = FVector3f(PointBudDirections[0], PointBudDirections[1], PointBudDirections[2]);
// Also accesses [5] (index 15-17) for secondary direction
```

**Required Indices:**

- `[0-2]`: Primary bud direction vector - **MUST NOT BE ZERO**
- `[15-17]`: Secondary/sixth bud direction - accessed for calculations

**If these are zero, mesh building may produce incorrect geometry!**

#### budDevelopment

**Array Structure:** 6 integers per point

| Index | Meaning | Usage |
|-------|---------|-------|
| 0 | Generation | Branch hierarchy level (trunk=0, first branch=1, etc.) |
| 1 | Cycle | Growth cycle when bud was created |
| 2 | Age | Age of the bud in cycles |
| 3 | Reserved | Not currently used |
| 4 | Reserved | Not currently used |
| 5 | Max Age | Maximum age reference |

**Usage in Material Settings:**

```cpp
// PVMaterialSettings.cpp
static constexpr int BudDevelopmentGenerationIndex = 0;
static constexpr int BudDevelopmentAgeIndex = 2;

BudDevelopment = PointFacade.GetBudDevelopment(PointIndex);
MinGeneration = FMath::Min(MinGeneration, BudDevelopment[0]);  // Generation
MinAge = FMath::Min(MinAge, BudDevelopment[2]);  // Age
```

**Used for:**

- Material assignment based on branch generation
- Age-based branch removal
- LOD decisions

#### budHormoneLevels

**Array Structure:** 6 floats per point

| Index | Meaning | Usage |
|-------|---------|-------|
| 0 | Auxin level | Branch dominance |
| 1 | Reserved | |
| 2 | Reserved | |
| 3 | Reserved | |
| 4 | Ethylene level | **CRITICAL** - Controls leaf abscission |
| 5 | Reserved | |

**Ethylene Usage (Critical):**

```cpp
// PVFoliage.cpp line 167
float EthyleneLevelAtCurrentPoint = BudHormoneLevels[CurrentPointIndex][4];

// Line 187 - controls foliage placement
if ((EthyleneLevel - 0.001f) >= DistributionSettings.EthyleneThreshold)
{
    continue;  // Skip foliage at this point
}
```

**Ethylene values:**

- 0.0 = Full foliage allowed
- 1.0 = Complete leaf drop (senescence)
- Threshold comparison determines foliage density

#### budLightDetected

**Array Structure:** 4 floats per point

| Index | Meaning | Usage |
|-------|---------|-------|
| 0 | Light value 1 | |
| 1 | Reserved | |
| 2 | Branch light detected | **Used for light-based branch removal** |
| 3 | Reserved | |

**Usage:**

```cpp
// PVRemoveBranches.cpp
static constexpr int BranchBudLightDetectedIndex = 2;
OutRemovalData[BranchIndex] = PointBudLightDetected[BranchBudLightDetectedIndex];
```

Used by the Remove Branches node with "Light" basis to cull poorly-lit branches.

### Other Point Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `branchGradient` | float[] | 0-1 gradient along branch (0=root, 1=tip) |
| `plantGradient` | float[] | 0-1 gradient for entire plant |
| `njord_pixelIdx` | float[] | Njord shader pixel index |
| `uv_v` | float[] | V texture coordinate |
| `uv_uOffset` | float[] | U texture coordinate offset |
| `uv_uRange` | float[] | U texture coordinate range |

---

## Primitive (Branch) Attributes

Branch/primitive attributes define the tree structure and hierarchy.

### Hierarchy

| Attribute | Type | Description | Required |
|-----------|------|-------------|----------|
| `parents` | int[][] | Parent branch numbers for hierarchy | **Yes** |
| `children` | int[][] | Child branch numbers | **Yes** |
| `branchNumber` | int[] | Unique branch identifier (1-based) | **Yes** |
| `branchParentNumber` | int[] | Parent branch number | **Yes** |
| `branchHierarchyNumber` | int[] | Hierarchy generation level | Used for LOD |

#### parents Array

Contains the full parent hierarchy path from current branch to root.

**Example:**

```json
// Branch 3 with parent branch 2, which has parent branch 1 (trunk)
"parents": [[1, 0], [1, 0], [2, 1, 0]]
```

- First element is immediate parent's branchNumber
- Continues up the hierarchy to trunk (which has parent 0)
- Trunk branch has `parents: [[0]]`

#### children Array

Contains the branchNumber values of child branches.

**Example:**

```json
// Branch 1 (trunk) has children branches 2 and 3
"children": [[2, 3], [], []]
```

### Branch Identification

| Attribute | Type | Description |
|-----------|------|-------------|
| `plantNumber` | int[] | Plant/tree identifier (1-based for single tree) |
| `branchSourceBudNumber` | int[] | Bud number that spawned this branch |

### Points Mapping

| Attribute | Type | Description |
|-----------|------|-------------|
| `Points` | int[][] | Point indices belonging to each branch |

**Example:**

```json
"Points": [[0, 1, 2, 3, 4], [5, 6, 7], [8, 9, 10]]
```

Branch 0 contains points 0-4, Branch 1 contains points 5-7, etc.

---

## Indexing Conventions

### 1-Based vs 0-Based Indexing

| Attribute | Indexing | Notes |
|-----------|----------|-------|
| Point array indices | 0-based | Standard array indexing |
| `branchNumber` | 1-based | Trunk is branch 1 |
| `plantNumber` | 1-based | Single tree is plant 1 |
| `budNumber` | 1-based | First bud is 1 |
| `branchHierarchyNumber` | 1-based | Trunk is hierarchy 1 |
| `parents` array values | Mixed | Contains branchNumbers (1-based) plus 0 for root |
| `children` array values | 1-based | Contains branchNumbers |
| `Points` array values | 0-based | Point indices |

---

## Crash Prevention Checklist

Based on source code analysis, these conditions will cause "Array index out of bounds" crashes in Unreal:

### Critical Array Sizes (Per Point)

| Attribute | Required Size | Indices Accessed | Source Location |
|-----------|---------------|------------------|-----------------|
| `budDirection` | **18 floats** | [0-2], [3-5], [15-17] (6 bud vectors) | PVMeshBuilder.cpp L782, L806; PVFoliage.cpp L141-143 |
| `budDevelopment` | **6 integers** | [0] (generation), [2] (age) | PVMaterialSettings.cpp L72-73; PVRemoveBranches.cpp L89 |
| `budHormoneLevels` | **6 floats** | [4] (ethylene level) | PVFoliage.cpp L167-168 |
| `budLightDetected` | **4 floats** | [2] (light detected) | PVRemoveBranches.cpp L82 |

### Critical Array Sizes (Global)

| Attribute | Required Size | Indices Accessed | Source Location |
|-----------|---------------|------------------|-----------------|
| `phyllotaxyLeaf` | **9 floats** | [1], [3], [4], [6], [7] | PVFoliage.cpp L41-45 |
| `plantProfile_N` | **100 floats** | [0-99] (optional) | PVMeshBuilder.cpp L658-659 |

### Other Crash Conditions

| Issue | Crash Location | Prevention |
|-------|----------------|------------|
| All pscale values = 0 | PVMeshBuilder.cpp L748-749 | Ensure max(pscale) > 0 |
| budDirection[0-2] all zero | PVSlope.cpp | Provide valid non-zero direction vectors |
| Branch with < 2 points | PVRemoveBranches.cpp L78 | Ensure each branch in primitives.points has >= 2 point indices |
| Empty Points array | Multiple locations | Ensure all branches have point indices |

### Quick Validation Checklist

Before loading a PVE JSON in Unreal, verify:

- [ ] Every point has `budDirection` with exactly 18 floats
- [ ] Every point has `budDevelopment` with exactly 6 integers  
- [ ] Every point has `budHormoneLevels` with exactly 6 floats
- [ ] Every point has `budLightDetected` with exactly 4 floats
- [ ] Global `phyllotaxyLeaf` has at least 9 floats
- [ ] At least one `pscale` value is > 0
- [ ] Each branch in `primitives.points` has at least 2 point indices
- [ ] `budDirection` vectors [0-2] are not all zeros

---

## Minimum Viable JSON Structure

```json
{
    "globalAttributes": {
        "cycle": {"isArray": false, "size": 1, "type": "int", "value": 3},
        "maxBranchNumber": {"isArray": false, "size": 1, "type": "int", "value": 3},
        "maxBudNumber": {"isArray": false, "size": 1, "type": "int", "value": 10}
    },
    "points": {
        "positions": [[0,0,0], [0,0,100], ...],
        "attributes": {
            "pscale": {"values": [0.05, 0.03, 0.01, ...]},
            "budDirection": {"values": [[0,1,0, 0,1,0, 0,1,0, 0,1,0, 0,1,0, 0,1,0], ...]},
            "budDevelopment": {"values": [[1,3,3,0,0,3], ...]},
            "budHormoneLevels": {"values": [[0,0,0,0,1,0], ...]},
            "budLightDetected": {"values": [[0.5,0,0.5,0], ...]},
            "lengthFromRoot": {"values": [0, 0.3, 0.6, ...]},
            "LOD_totalPscaleGradient": {"values": [1.0, 0.9, 0.8, ...]}
        }
    },
    "primitives": {
        "points": [[0,1,2,3], [4,5,6], ...],
        "attributes": {
            "branchNumber": {"values": [1, 2, 3]},
            "plantNumber": {"values": [1, 1, 1]},
            "parents": {"values": [[0], [1,0], [1,0]]},
            "children": {"values": [[2,3], [], []]},
            "branchHierarchyNumber": {"values": [1, 2, 2]}
        }
    }
}
```

---

## Source Code References

All attribute names are defined in:

- `PVAttributesNames.h` - Namespace `PV::AttributeNames`

Key implementation files:

- `PVMeshBuilder.cpp` - Mesh generation (uses most point attributes)
- `PVFoliage.cpp` - Foliage distribution (uses budHormoneLevels[4] for ethylene)
- `PVRemoveBranches.cpp` - Branch pruning (uses budDevelopment, budLightDetected)
- `PVMaterialSettings.cpp` - Material assignment (uses budDevelopment)
- `PVPointFacade.cpp` - Point data access patterns
- `PVBranchFacade.cpp` - Branch data access patterns
- `PVJSONHelper.h` - JSON parsing and required paths validation

---

## Grove to PVE Mapping

GrowPy converts Grove 2.3 seed.json parameters to PVE attributes. The key challenge is that Grove uses simple scalar parameters while PVE uses curve-based arrays.

### Compatibility Matrix

| PVE Attribute | Grove Source | Mapping Type | Status |
|---------------|--------------|--------------|--------|
| cycle | Simulation count | Direct | Working |
| cycleTime | Fixed value | Direct | Working |
| randomSeed | grove.set_random_seed() | Direct | Working |
| gravitationalForce | bend_reaction | Approximate | Needs scaling |
| phototropism | turn_to_light, favor_bright | Curve conversion | Needs implementation |
| phyllotaxy | add_angle | Complex | Use reference values |
| axialElongation | grow_length | Curve conversion | Needs implementation |
| lateralElongation | grow_length | Complex curve | Use reference values |
| branchingCondition | add_chance | Complex curve | Use reference values |
| leafGrowth | twig_density | No equivalent | Use reference values |
| lightDetection | shade_area | Approximate | Needs implementation |
| maxBranchNumber | skeleton.poly_lines | Calculate | Working |
| maxBudNumber | skeleton estimate | Calculate | Needs improvement |
| compoundMaxBranchGeneration | skeleton hierarchy | Calculate | Needs improvement |
| compoundMaxBranchNumber | Species data | Config file | Working |
| maxPscale | skeleton.radius | Calculate | Needs implementation |
| max_curve_length | skeleton length | Calculate | Needs implementation |
| plantProfile_1-5 | None | Config file | Working |
| photogrammetryTrunk | None | Fixed (0) | Working |

### Mapping Strategy

- **Direct extraction**: cycle, randomSeed, maxBranchNumber
- **Calculate from simulation**: maxBudNumber, maxPscale, max_curve_length, compoundMaxBranchGeneration
- **Curve conversion possible**: phototropism, axialElongation, lightDetection, gravitationalForce
- **Use species reference values**: phyllotaxy, lateralElongation, branchingCondition, leafGrowth
- **Config files required**: plantProfiles, compoundMaxBranchNumber, photogrammetryTrunk
