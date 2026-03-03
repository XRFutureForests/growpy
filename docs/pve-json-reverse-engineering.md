# PVE JSON Format - Reverse Engineering Analysis

Analysis of the Procedural Vegetation Editor (PVE) JSON format based on C++ source code
(`ProceduralVegetationEditor/Source/`) and the reference `Broadleaf_Hazel_04.json`.

---

## 1. Top-Level JSON Structure

```json
{
  "globalAttributes": { ... },
  "points": { "attributes": { ... }, "positions": [ ... ] },
  "primitives": { "attributes": { ... }, "points": [ ... ] }
}
```

Three sections: **globalAttributes** (plant-wide settings/growth curves),
**points** (skeleton vertices), **primitives** (branches + foliage instancers).

---

## 2. Attribute Format Conventions

### globalAttributes: uses `"value"` (singular)

```json
"cycle": { "isArray": false, "size": 1, "type": "int", "value": 8 }
"leafGrowth": { "isArray": true, "size": 1, "type": "float", "value": [0.14, 0.10, ...] }
```

Parsed by `FillDetailsAttributes()` which reads `"value"` key. For `isArray: true`,
`"value"` is a flat array of floats stored as a **single** `TArray<float>` in element
index 0 of the Details group.

### points.attributes and primitives.attributes: uses `"values"` (plural)

```json
"pscale": { "isArray": false, "size": 1, "type": "float", "values": [0.013, 0.012, ...] }
"budDirection": { "isArray": true, "size": 3, "type": "float", "values": [[...18 floats...], [...], ...] }
```

Parsed by `FillAttributes()` which reads `"values"` key. One entry per point (or per branch).

### Key: `isArray` + `size` determines how data is interpreted

| isArray | size | C++ Type | JSON Values Format |
|---------|------|----------|--------------------|
| false | 1 | `int32` / `float` / `FString` | `[val1, val2, ...]` (one per element) |
| false | 3 | `FIntVector` / `FVector3f` | `[[x,y,z], [x,y,z], ...]` (one 3-vector per element) |
| true | 1 | `TArray<int32>` / `TArray<float>` | `[[a,b,...], [c,d,...], ...]` (variable-length array per element) |
| true | 3 | `TArray<FIntVector>` / `TArray<FVector3f>` | `[[x,y,z,x,y,z,...], ...]` (interleaved 3-vectors per element) |

---

## 3. Coordinate System Transformation

- **Houdini/Grove convention**: X-right, Y-forward, Z-up (meters)
- **Unreal convention**: X-right, Y-forward, Z-up (centimeters) -- BUT PVE swaps Y/Z during import

```cpp
// C++ transformation applied on load:
Position = FVector3f(json[0], json[2], json[1]) * 100.0f;  // swap Y<->Z, scale to cm
Scale = json_pscale * 100.0f;  // meters to centimeters
// LFR (lengthFromRoot) is NOT scaled (relative values only)
```

This means **JSON coordinates should be in Houdini format** (Y-forward, Z-up, in meters).
The C++ swaps Y/Z and multiplies by 100.

---

## 4. Required JSON Paths (Validated Before Load)

The C++ `LoadMegaPlantsJsonToCollection()` checks these paths before proceeding.
**Missing any of these causes a load failure with error message (not crash):**

```
points.attributes.pscale
points.positions
points.attributes.lengthFromRoot.values
points.attributes.LOD_totalPscaleGradient.values
points.attributes.budDirection.values
primitives.points
primitives.attributes.instancer_name.values
primitives.attributes.instancer_pivot.values
primitives.attributes.instancer_UP.values
primitives.attributes.instancer_scale.values
primitives.attributes.instancer_LFR.values
primitives.attributes.parents.values
primitives.attributes.children.values
primitives.attributes.branchNumber.values
globalAttributes.phyllotaxyLeaf.value
```

---

## 5. globalAttributes - Detailed Breakdown

All globalAttributes are stored in a "Details" group with exactly **1 element**.
Array attributes become `TArray<float>` in element [0]. Scalar attributes
become `int32` or `float` in element [0].

### 5.1 Simulation Controls

| Attribute | Type | Description |
|-----------|------|-------------|
| `cycle` | int | Number of growth simulation steps (age of tree) |
| `cycleTime` | float | Time per cycle (fraction of year, e.g., 0.333 = 4 months) |
| `randomSeed` | int | Random seed for reproducible growth |
| `gravitationalForce` | float | Strength of gravity effect on branch drooping |

### 5.2 Growth Curve Arrays (isArray: true)

These are packed parameter arrays where each float at a specific index controls a
different aspect. They come from The Grove's growth preset system.

#### `leafGrowth` (9 floats)

Controls leaf/twig appearance and growth behavior:

```
[0] = leaf_scale_base        (base size of leaves, e.g., 0.141)
[1] = leaf_density            (density parameter, e.g., 0.10)
[2] = leaf_scale_variation    (size randomization, e.g., 0.167)
[3] = leaf_growth_rate        (speed of growth, e.g., 0.15)
[4] = leaf_type               (leaf type selector, e.g., 2.0)
[5] = unknown                 (e.g., 0.0)
[6] = leaf_angle              (leaf attachment angle, e.g., 0.18)
[7] = leaf_curvature          (leaf bending, e.g., 0.04)
[8] = unknown                 (e.g., 0.0)
```

#### `axialElongation` / `axialElongationChild` (6 floats)

Controls branch extension along its axis:

```
[0] = elongation_rate         (growth speed, e.g., 0.0447)
[1-5] = curve control points  (0.0, 0.0, 0.0, 0.0, 1.0) - ramp modulation
```

The "Child" variant applies to child branches (sub-branches).

#### `lateralElongation` / `lateralElongationChild` (9 floats)

Controls side branching growth:

```
[0] = base_rate              (lateral growth rate)
[1] = age_influence          (how age affects growth)
[2] = light_influence        (light-dependency factor)
[3] = curve_param_1          (ramp control, e.g., 7000.0)
[4] = curve_param_2          (ramp control, e.g., 10000.0)
[5] = growth_bias            (directional bias)
[6] = max_iterations         (computation limit)
[7] = vigor_threshold        (minimum energy for growth)
[8] = unused                 (e.g., 0.0)
```

#### `branchingCondition` / `branchingConditionChild` (8 floats)

Controls when and where new branches form:

```
[0] = branch_angle           (branching departure angle)
[1] = branch_spread          (angular spread)
[2] = light_threshold        (minimum light for branching)
[3] = age_threshold_start    (earliest branching age, normalized)
[4] = age_threshold_end      (latest branching age, normalized)
[5-7] = curve modulation     (additional controls)
```

#### `phototropism` / `phototropismChild` (4 floats)

Controls growth toward light:

```
[0] = strength               (phototropism force)
[1] = sensitivity            (reaction speed to light gradient)
[2] = unused
[3] = max_angle              (maximum bending angle toward light)
```

#### `phyllotaxy` / `phyllotaxyChild` (14 floats)

Controls branch/bud arrangement pattern around the stem:

```
[0] = pattern_type           (0=alternate, 1=opposite, 2=whorled)
[1] = divergence_angle       (angle between successive buds, e.g., 180 for alternate)
[2] = random_angle           (randomization of arrangement, e.g., 32.5)
[3-4] = scaling factors
[5] = offset
[6] = initial_angle          (starting angle, e.g., 60)
[7-9] = additional controls
[10-11] = symmetry params
[12] = whorl_count
[13] = density_factor        (e.g., 0.435)
```

#### `phyllotaxyLeaf` (9 floats) - REQUIRED

Controls leaf arrangement pattern:

```
[0] = pattern_type
[1] = divergence_angle       (e.g., 180 for alternate)
[2] = random_angle
[3-4] = scaling
[5-6] = offsets
[7] = randomization
[8] = density
```

#### `lightDetection` (5 floats)

Controls how the tree senses light:

```
[0] = detection_distance     (how far to look for light)
[1] = sensitivity            (reaction strength)
[2] = sample_count_h         (horizontal light sampling resolution)
[3] = sample_count_v         (vertical light sampling resolution)
[4] = ambient_factor         (baseline light level)
```

#### `abscissionSenescense` (9 floats)

Controls branch shedding (self-pruning):

```
[0] = threshold              (abscission trigger level)
[1] = age_factor             (age influence on shedding)
[2-3] = rate parameters
[4] = unused
[5] = secondary_threshold
[6-8] = additional controls
```

#### `trunkGrowth` (13 floats)

Controls main trunk characteristics:

```
[0-12] = trunk diameter growth curve points
        (defines how trunk radius changes with height)
```

#### `guide` (4 floats)

Controls growth guide influence:

```
[0] = guide_strength         (how strongly growth follows guide)
[1] = guide_type             (e.g., 3.0 = gravitropic)
[2-3] = additional params
```

#### `randomAngle` / `randomAngleChild` (3 floats)

Random angle perturbation:

```
[0] = angle_range
[1] = vertical_bias
[2] = unused
```

### 5.3 Plant Profiles (plantProfile_1 through plantProfile_5)

Each is a 101-float array representing the crown silhouette at different growth stages.
Values are normalized (0.0-1.0) representing the relative crown radius at each
height position (0=base, 100=top). Used for mesh deformation:

```cpp
// From PVMeshBuilder.cpp - profiles are read via FPlantProfileFacade
// Applied as radial modulation to branch mesh geometry
```

Five profiles allow variation across trees of the same species.
Parsed by dedicated `FillPlantProfilesData()` function.

### 5.4 Scale Parameters

| Attribute | Type | Description |
|-----------|------|-------------|
| `maxPscale` | float | Maximum point scale in the tree (meters) |
| `max_pscale` | float | Duplicate of maxPscale (legacy) |
| `minPscale` | float | Minimum point scale |
| `maxPscales` | float[] | Per-plant max scales (array for multi-plant) |
| `maxDavinciPscales` | float[] | Da Vinci pipe model max scales |
| `max_curve_length` | float | Longest branch curve length |
| `maxBranchNumber` | int | Highest branch ID in the tree |
| `maxBudNumber` | int | Highest bud ID |
| `compoundMaxBranchGeneration` | int | Max depth of compound branches |
| `compoundMaxBranchNumber` | int | Max compound branch count |
| `photogrammetryTrunk` | int | Flag: 1 if trunk from photogrammetry scan |

---

## 6. Points Section - Skeleton Vertices

### 6.1 `positions` (array of [x, y, z])

Each entry is a 3-float array in **Houdini coordinates** (meters, Z-up).
The C++ parser converts: `Unreal = (json_x, json_z, json_y) * 100`.

### 6.2 `pscale` (REQUIRED)

Branch radius at each point, in **meters**. Multiplied by 100 on load.
**CRITICAL**: Must be non-zero. The mesh builder divides by `MaxPointScale`
and individual `PointScale`. Zero causes crashes.

### 6.3 `lengthFromRoot` (REQUIRED)

Cumulative distance from the tree root along the branch path.
NOT scaled by 100 on load (used for relative comparisons only).

### 6.4 `LOD_totalPscaleGradient` (REQUIRED)

Normalized gradient (0.0-1.0) based on point scale relative to max.
Used for LOD (Level of Detail) mesh simplification decisions.
Higher values = thicker branches = more detail retained.

### 6.5 `budDirection` (REQUIRED)

```json
{
  "isArray": true,
  "size": 3,
  "type": "float",
  "values": [ [18 floats], [18 floats], ... ]
}
```

Per-point array of 6 bud direction vectors (6 x 3 = 18 floats).
Stored as interleaved x,y,z triplets in Houdini coordinates.

The C++ mesh builder specifically accesses:

- **Index [0]** (`PointBudDirections[PointIndex][0]`): Used as "AimVector" - the
  primary growth direction. This drives branch mesh orientation.
- **Index [5]** (`PointBudDirections[PointIndex][5]`): Used as "PointUpOriginal" -
  the original up direction for the point.

Since `size: 3`, the C++ parser reads them as `TArray<FVector3f>` per point,
converting `[x,y,z, x,y,z, ...]` to `[Vector(x,z,y), Vector(x,z,y), ...]`
(with Y/Z swap). So from the JSON perspective, each bud occupies 3 consecutive
floats in the inner array.

### 6.6 `branchGradient`

Normalized position along its branch (0.0 = branch start, 1.0 = branch tip).
Used for profile evaluation and material blending.

### 6.7 `LOD_*Gradient` family

| Attribute | Purpose |
|-----------|---------|
| `LOD_totalPscaleGradient` | **REQUIRED** - Overall scale-based LOD |
| `LOD_plantPscaleGradient` | Plant-level scale gradient |
| `LOD_branchPscaleGradient` | Per-branch scale gradient |
| `LOD_groundGradient` | Distance from ground (for material blending) |
| `LOD_hullGradient` | Convex hull proximity (crown silhouette) |
| `LOD_mainTrunkGradient` | Main trunk identification (1.0 = trunk, 0.0 = branch) |
| `LOD_canopyGradient` | Canopy region detection |

These drive the mesh builder's `ComputePointGradients()` function which uses
retention curves to decide how many radial divisions each segment gets.

### 6.8 Bud Attributes

| Attribute | Inner Size | Description |
|-----------|-----------|-------------|
| `budDevelopment` | 6 ints | `[generation, cycle, age, 0, 0, max_age]` per point |
| `budHormoneLevels` | variable | Hormone levels affecting growth vigor |
| `budLateralMeristem` | variable | Lateral meristem activity |
| `budLightDetected` | variable | Light detected per bud |
| `budStatus` | variable | Status flags per bud |
| `budNumber` | 1 int | Unique bud identifier |

### 6.9 UV/Texture Attributes

| Attribute | size | Description |
|-----------|------|-------------|
| `uv_base` | 3 | Base UV coordinates |
| `uv_base_unmodified` | 3 | Original UVs before modification |
| `uv_metric` | 3 | Metric-space UVs |
| `uv_out` | 3 | Final output UVs |

### 6.10 Other Point Attributes

| Attribute | Description |
|-----------|-------------|
| `generation` | Branch hierarchy depth (0 = trunk, 1 = primary branch, etc.) |
| `lengthFromSeed` | Distance from seed point |
| `plantGradient` | Normalized age gradient (0.0 = oldest, 1.0 = youngest) |
| `njord_pixelIdx` | Njord light simulation pixel index |

---

## 7. Primitives Section - Branches and Foliage

### 7.1 `points` (array of array of ints)

Each entry is a list of point indices forming one branch polyline:

```json
"points": [ [0,1,2,3,4,5], [3,6,7,8], [5,9,10,11], ... ]
```

Point indices reference `positions` array. Points can be shared between branches
(fork points belong to parent and child).

### 7.2 `parents` (REQUIRED) - isArray: true, size: 1, type: int

**Full ancestor chain** per branch, not just immediate parent:

```json
"values": [ [0], [0,1], [0,1,2], [0,1,3], ... ]
```

- Root branch: `[0]` (self-reference)
- Child branch: `[root_idx, ..., parent_idx, self_idx]`

The C++ uses this to traverse the hierarchy for skeleton bone generation
and branch relationship queries.

### 7.3 `children` (REQUIRED) - isArray: true, size: 1, type: int

**Direct children** per branch:

```json
"values": [ [1,2,3], [4,5], [], [], ... ]
```

Leaf branches have empty arrays.

### 7.4 `branchNumber` (REQUIRED)

Sequential branch identifiers (0, 1, 2, ...).

### 7.5 Instancer Data (Foliage/Twig Placement) - ALL REQUIRED

These are per-branch arrays containing foliage instance data.
Each branch has its own set of twig instances.

#### `instancer_name` - isArray: true, size: 1, type: string

```json
"values": [
  ["BrLeaf_020", "BrLeaf_010", "BrLeaf_004"],
  ["BrLeaf_009", "BrLeaf_010"],
  ...
]
```

Per-branch array of twig/leaf asset names. These reference meshes in the
same package directory. The C++ appends `"." + name` to form asset paths.

#### `instancer_pivot` - isArray: true, size: 3, type: float

```json
"values": [
  [x1,y1,z1, x2,y2,z2, x3,y3,z3, ...],
  [x1,y1,z1, x2,y2,z2, ...],
  ...
]
```

**Interleaved** 3D positions (in Houdini meters). For N twigs on a branch,
this is a flat array of N*3 floats. Multiplied by 100 on load.

#### `instancer_UP` - isArray: true, size: 3, type: float

Same interleaved format as pivot. Up direction vectors for each twig instance.
**NOT scaled**.

#### `instancer_N` - NOT in required list but parsed

Normal direction vectors, same interleaved format. Used for foliage orientation.

**Note**: `instancer_N` is NOT in the RequiredJSONPaths validation but IS accessed
during `FillFoliageData()`. If missing, it will crash when trying to read
`InstancerNormalVectorValues`. The validation only checks `instancer_UP` not `instancer_N`.

This is a potential crash source if the JSON has all other required fields but
lacks `instancer_N`.

#### `instancer_scale` - isArray: true, size: 1, type: float

```json
"values": [ [1.0, 0.8, 1.2], [0.9, 1.1], ... ]
```

Scale factor per twig instance.

#### `instancer_LFR` - isArray: true, size: 1, type: float

Length From Root per twig instance. Used for foliage distribution conditions.

### 7.6 Branch Hierarchy Attributes

| Attribute | Description |
|-----------|-------------|
| `branchGeneration` | Depth in tree hierarchy (0 = trunk, 1+) |
| `branchParentNumber` | Index of parent branch |
| `branchHierarchyNumber` | Hierarchy number (often same as generation) |
| `branchSourceBudNumber` | Which bud on parent spawned this branch |
| `branchSimulationGroupIndex` | Simulation group for parallel processing |
| `plantNumber` | Which plant this branch belongs to (for multi-plant files) |

### 7.7 Compound Branch Attributes

| Attribute | Description |
|-----------|-------------|
| `compoundBranchGeneration` | Generation within compound branch system |
| `compoundBranchNumber` | Number within compound branch |
| `compoundBranchParentNumber` | Parent within compound system |

### 7.8 Metadata Attributes

| Attribute | Description |
|-----------|-------------|
| `shop_materialpath` | Material path for branch rendering |
| `pivotPointLocation` | Branch origin point |
| `path` | Houdini node path (legacy) |
| `streamName` | Data stream identifier |

---

## 8. Potential Crash Sources

Based on C++ analysis, these are the known crashpoints:

### 8.1 Zero pscale (Division by Zero)

```cpp
// PVMeshBuilder.cpp - GenerateBranchMeshData()
check(MaxPointScale > 0);  // ASSERTION FAILURE if max is 0
MaxPointScaleRatio = 1.0f / (MaxPointScale * UE_TWO_PI);

// Also:
if (PointScale == 0.0f) [[unlikely]] { ... }  // Special case but after division
```

### 8.2 Missing instancer_N (Not Validated)

The RequiredJSONPaths does **not** include `instancer_N`, but `FillFoliageData()`
unconditionally accesses it:

```cpp
const auto& InstancerNormalVectorObject = PrimitiveAttributes->GetObjectField(TEXT("instancer_N"));
```

**If `instancer_N` is missing, this crashes with a null pointer dereference.**

### 8.3 Invalid budDirection Indices

```cpp
// PVMeshBuilder.cpp
AimVector = PointBudDirections[PointIndex][0];      // Index 0 required
PointUpOriginal = PointBudDirections[PointIndex][5]; // Index 5 required
```

If `budDirection` has fewer than 6 vectors (18 floats), accessing index [5] crashes.

### 8.4 Empty Branches

If a branch in `primitives.points` has 0 points, various calculations
(ring generation, triangulation) will access empty arrays.

### 8.5 Array Size Mismatches

If the number of elements in `pscale.values`, `budDirection.values`, etc.
doesn't match the number of entries in `positions`, array-out-of-bounds occurs.

---

## 9. Comparison: growpy Schema vs Actual Hazel JSON

### 9.1 Schema Mismatch in pve_schema.py -- FIXED

The growpy schema previously defined instancer attributes with `isArray: False` and
`budDirection` with `isArray: False`. These have been corrected to `isArray: True`
to match the actual Hazel JSON format. The `create_empty_pve_preset()` path also
used `"value"` key for points/primitives attributes -- corrected to `"values"`.

### 9.2 instancer_N Not Required But Mandatory

The C++ does not validate `instancer_N` in RequiredJSONPaths but crashes if absent.
growpy always generates `instancer_N` in the output.

### 9.3 instancer_UP and instancer_N Were Identical -- FIXED

The foliage extractor previously used `grove_to_pve_position()` (with 100x scaling)
for direction vectors, then normalized, producing the same vector for both UP and N.
Fixed to use `grove_to_pve_vector()` (axis swap only, no scaling) and to pipe
separate vectors:

- `instancer_N` = twig facing direction (from `model.get_twig_directions()`)
- `instancer_UP` = twig up vector (from `model.get_twig_orientations()`)

### 9.4 Point Positions: Local vs World

The Hazel reference tree positions appear to be in **local coordinates** (relative
to tree root). The growpy mapper correctly subtracts the origin to convert from
Grove world coordinates to local.

---

## 10. Why Multiple Values in Array Attributes

The `isArray: true` flag with flat `value` arrays in globalAttributes packs
multiple related parameters into a single attribute. This is an optimization from
The Grove's growth preset system (Houdini-style packed parameters):

- Each position in the array has a specific meaning (parameter index)
- The array length varies per attribute (leafGrowth: 9, phyllotaxy: 14, etc.)
- They are NOT per-point arrays -- they are parameter packs for the entire tree
- Child variants (e.g., axialElongationChild) allow different parameters for
  sub-branches vs the main trunk

The C++ side stores these as `TArray<float>` in the Details group and accesses
individual elements by index for growth simulation replay.

---

## 11. globalAttributes Origin and Species Variability

### 11.1 Are globalAttributes Species-Constant?

**No.** Comparison of all 4 Hazel reference files (Broadleaf_Hazel_01 through _04,
representing different growth stages: cycle 8, 17, 30, 30) shows:

- **Only 9 out of 40 attributes are identical** across all instances:
  `guide`, `lightDetection`, `photogrammetryTrunk`, `plantProfile_1` through
  `plantProfile_5`, `randomSeed`
- **31 attributes differ** between instances, including all growth curves
  (`phototropism`, `axialElongation`, `phyllotaxy`, etc.) and computed metadata
  (`maxBranchNumber`, `maxPscale`, `cycle`, etc.)

### 11.2 Three Categories of globalAttributes

| Category | Examples | Source | Per-instance? |
|----------|---------|--------|---------------|
| **Species constants** | `plantProfile_1-5`, `lightDetection`, `guide` | Species definition | No -- same across all instances |
| **Simulation metadata** | `maxBranchNumber`, `maxPscale`, `max_curve_length`, `cycle` | Computed from actual tree | Yes -- varies per tree |
| **Growth curves** | `phototropism`, `axialElongation`, `leafGrowth`, etc. | Quixel/Houdini pipeline | Yes -- varies per simulation |

### 11.3 Mapping Between Grove Properties and PVE globalAttributes

There is **no direct 1:1 mapping**. The two systems use completely different
parameterizations:

- **Grove seed.json**: 57 scalar parameters in snake_case (e.g., `grow_length=0.5`,
  `turn_to_light=1.0`, `add_angle=0.79`)
- **PVE globalAttributes**: Packed multi-value arrays in camelCase (e.g.,
  `axialElongation=[0.0447, 0.0, 0.0, 0.0, 0.0, 1.0]`)

Comparison for Hazel (PVE youngest instance vs seed.json):

| PVE Attribute | PVE Value | Grove Property | Grove Value |
|---------------|-----------|----------------|-------------|
| `phototropism[0]` | 0.0 | `turn_to_light` | 1.0 |
| `phyllotaxy[1]` | 180.0 | `add_angle` | 0.79 |
| `axialElongation[0]` | 0.0447 | `grow_length` | 0.5 |
| `gravitationalForce` | 1.297 | `bend_mass` | 0.5 |
| `randomAngle[0]` | 9.51 | `turn_random` | 0.12 |

The PVE growth curves originate from the Quixel/Houdini pipeline's internal
representation -- a separate growth simulation system that is not part of
The Grove API. There is no known algorithmic conversion.

### 11.4 Can These Attributes Be Obtained from Grove?

| What | Available from Grove? | How |
|------|----------------------|-----|
| Simulation params (`cycle`, `cycleTime`, `randomSeed`) | YES | `properties.simulation_steps`, `.cycle_time`, `.random_seed` |
| `gravitationalForce` | YES | `properties.gravity` |
| Computed metadata (`maxBranchNumber`, `maxPscale`, etc.) | YES | Computed from skeleton data (now implemented) |
| `plantProfile_1-5` (crown silhouettes) | NO | Species-specific, must come from reference files |
| Growth curves (`phototropism`, `axialElongation`, etc.) | NO | Quixel pipeline internal format, no Grove equivalent |
| `lightDetection`, `guide` | NO | Species-specific constants from reference files |

### 11.5 Practical Approach for New Species

For species without PVE reference files:

1. **Computed attributes**: `maxBranchNumber`, `maxPscale`, `max_curve_length`, etc.
   are now computed from actual skeleton data automatically.

2. **Species-constant attributes**: `plantProfile_1-5`, `lightDetection`, `guide`
   must be sourced per species. Options:
   - Use Hazel defaults as approximation (current approach)
   - Create species-specific PVE config files in `data/assets/pve_configs/`
   - Compute `plantProfile` from tree crown geometry (future work)

3. **Growth curves**: `phototropism`, `axialElongation`, `leafGrowth`, etc.
   have no known derivation from Grove. Options:
   - Use Hazel defaults as reasonable starting values (current approach)
   - Create per-species growth curve templates manually or from reference data
   - Accept that these values affect PVE's re-simulation replay, not initial
     mesh rendering -- the mesh builder primarily uses skeleton geometry

---

## 12. Information Sources

The attribute descriptions in this document were derived from:

1. **PVE C++ source code** (`data/tmp/ProceduralVegetationEditor/Source/`):
   - `PVJSONHelper.h` -- JSON loading and attribute parsing
   - `PVAttributesNames.h` -- Complete attribute name registry and group assignments
   - `PVMeshBuilder.cpp` -- How attributes drive mesh generation
   - `PVBranchFacade.h`, `PVPointFacade.h` -- Typed accessors showing data types
   - `PVFoliageJSONHelper.cpp` -- Foliage instancer loading
   - `PVMaterialSettings.cpp` -- How budDevelopment drives materials

2. **Reference JSON files** (`Broadleaf_Hazel_01` through `_04`):
   - Actual working PVE presets exported from the Quixel/Houdini pipeline
   - Cross-file comparison revealed which attributes are per-instance vs per-species

3. **The Grove 2.2 API documentation** (`docs/the_grove/`):
   - `the_grove_core.Properties.md` -- Runtime property access
   - `the_grove_core.Presets.md` -- Preset serialization
   - `the_grove_core.Grove.md` -- Simulation and build API

4. **Attribute index meanings** (e.g., leafGrowth[0] = leaf_scale_base):
   These are **inferred** from C++ access patterns, Houdini naming conventions,
   and value range analysis. They should be treated as educated guesses, not
   authoritative documentation. The original meanings were defined in the
   Quixel/Houdini pipeline which is proprietary.

---

## 13. Fixes Applied to growpy

### 13.1 pve_foliage_extractor.py

- **Fixed**: `grove_to_pve_position(normal)` changed to `grove_to_pve_vector(normal)`
  for direction vectors. The position function multiplied by 100 (meters to cm);
  direction vectors should only have the Y/Z axis swap.
- **Fixed**: `instancer_UP` and `instancer_N` were both set to the same normalized
  vector. Now `instancer_N` uses `twig_directions` (facing) and `instancer_UP` uses
  `twig_orientations` (up vector) from the Grove API.

### 13.2 TwigPlacement (core/twig.py)

- **Added**: `orientation` field (Tuple[float, float, float]) to carry the up vector
  from `model.get_twig_orientations()` alongside the existing `normal` from
  `model.get_twig_directions()`.

### 13.3 pve_schema.py

- **Fixed**: `instancer_N`, `instancer_UP`, `instancer_name`, `instancer_pivot`,
  `instancer_scale`, `instancer_LFR` changed from `isArray: False` to `isArray: True`.
- **Fixed**: `instancer_scale` size from 3 to 1 (scalar per instance).
- **Fixed**: `budDirection` changed from `isArray: False` to `isArray: True`.
- **Fixed**: `create_empty_pve_preset()` uses `"values"` (plural) for points and
  primitives attributes instead of `"value"`.

### 13.4 pve_grove_mapper.py

- **Added**: `_compute_global_metadata_from_skeleton()` function that computes
  `maxBranchNumber`, `maxBudNumber`, `maxPscale`, `max_pscale`, `minPscale`,
  `maxPscales`, `maxDavinciPscales`, `max_curve_length`, `compoundMaxBranchGeneration`,
  `compoundMaxBranchNumber`, and `photogrammetryTrunk` from actual skeleton data
  instead of using template defaults.

---

## 14. Summary of Recommendations for growpy

1. **instancer_N always included** -- verified and fixed
2. **pscale never zero** -- MIN_PSCALE = 0.001m guard exists
3. **budDirection has 18 floats** per point -- verified in `_calculate_bud_directions()`
4. **Array sizes match** positions count -- ensured by per-point iteration
5. **Schema isArray flags** -- fixed for instancer and budDirection attributes
6. **instancer_UP and instancer_N are now different vectors** -- separate Grove data sources
7. **Computed metadata** now derived from actual tree rather than Hazel defaults
8. **parents array format**: Full ancestor chains, root uses self-reference [0], not [-1]
9. **instancer_pivot in meters** (Houdini format) since C++ multiplies by 100
10. **Species growth curves**: Need per-species templates for non-Hazel species
    (no automatic derivation from Grove API is possible)
