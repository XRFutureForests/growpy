# PVE Attribute Reference Guide

Comprehensive reference for PVE (Procedural Vegetation Editor) JSON preset attributes, explaining what each parameter controls and how it affects tree generation in Unreal Engine.

## Overview

PVE preset JSON files contain three main sections:

1. **globalAttributes** - Growth simulation parameters, limits, and species characteristics
2. **points** - Point cloud data with botanical attributes (positions, thickness, generation, etc.)
3. **primitives** - Branch connectivity and hierarchy

This guide focuses on the **globalAttributes** that are not directly available from the Grove 2.2 API and must be configured per-species.

## Hidden Attributes (Require Debug Mode)

These attributes are marked as `DevelopmentOnly` in Unreal and are only visible when PVE Debug Mode is enabled via console command `PV.DebugMode.Enabled 1`.

---

## Branch and Bud Limits

### maxBranchNumber

**Type**: `int`  
**Typical Range**: 10-100+  
**Example**: `17` (Hazel), `120` (large Oak)

**What It Controls**:

- Maximum number of **branches** (polylines) in the tree skeleton
- Represents the total count of distinct branch segments from trunk to twigs
- Each branch is a connected sequence of points forming one growth path

**Biological Meaning**:

- Higher values = more complex branching structure
- Broadleaf trees typically: 50-150 branches
- Coniferous trees typically: 30-100 branches
- Young trees: 10-30 branches
- Mature trees: 100-300 branches

**How GrowPy Calculates It**:

```python
def _get_num_branches(grove, skeleton):
    """Count number of polylines in skeleton"""
    return len(skeleton.poly_lines)
```

**When to Adjust**:

- Increase for older, more complex trees
- Decrease for young saplings or simple tree forms
- Match to target tree age and complexity

---

### maxBudNumber

**Type**: `int`  
**Typical Range**: 20-500+  
**Example**: `79` (Hazel), `800` (mature broadleaf)

**What It Controls**:

- Maximum number of **buds** (growth endpoints and branch tips)
- Each bud represents a potential growth point or terminal branch end
- Includes both active growing tips and dormant lateral buds

**Biological Meaning**:

- Approximate ratio: 3-5 buds per branch (on average)
- More buds = more potential for future growth and branching
- Terminal buds at branch ends + lateral buds along branches
- Dormant buds may activate when conditions change (light exposure, damage)

**How GrowPy Calculates It**:

```python
def _get_num_buds(grove, skeleton):
    """Estimate buds from branch count"""
    # Simplified: assume ~1 bud per branch endpoint
    return len(skeleton.poly_lines)
    # In reality: buds ≈ branches × 3-5
```

**When to Adjust**:

- Increase for vigorous growing species (willows, poplars)
- Decrease for slow-growing or mature static trees
- Match to species growth characteristics

**Relationship to maxBranchNumber**:

```text
Typical Ratios:
- Young trees: buds ≈ branches × 2-3
- Mature trees: buds ≈ branches × 4-6
- Very dense crown: buds ≈ branches × 8-10
```

---

## Compound Leaf Parameters

These parameters control **compound leaf** structures (leaves with multiple leaflets, like Ash, Walnut, or Hazel).

### compoundMaxBranchGeneration

**Type**: `int`  
**Typical Range**: 1-4  
**Example**: `3` (Hazel)

**What It Controls**:

- Maximum hierarchy depth for **compound leaf branches**
- Generation 0 = main leaf stem (rachis)
- Generation 1 = primary leaflets
- Generation 2 = secondary leaflets (bipinnate leaves)
- Generation 3 = tertiary leaflets (tripinnate leaves)

**Biological Meaning**:

- **Generation 1** (pinnate): Simple compound leaves (Ash, Walnut, Locust)
  - Single row of leaflets along main stem
- **Generation 2** (bipinnate): Twice-compound leaves (Honey Locust, Mimosa)
  - Each primary leaflet divides into secondary leaflets
- **Generation 3** (tripinnate): Thrice-compound leaves (rare, some ferns/acacias)
  - Each secondary leaflet divides again

**Species Examples**:

```text
Generation 1 (Pinnate):
- Ash (Fraxinus): 7-13 leaflets
- Walnut (Juglans): 15-23 leaflets
- Mountain Ash (Sorbus): 11-15 leaflets

Generation 2 (Bipinnate):
- Honey Locust: 20-30 leaflets per pinnae
- Mimosa: 10-25 leaflets per pinnae
- Kentucky Coffee Tree: 7-15 leaflets per pinnae

Generation 3 (Tripinnate):
- Rare in trees, more common in ferns
```

**How GrowPy Calculates It**:

```python
def _get_max_generation(grove, skeleton):
    """Estimate max hierarchy depth from branch count"""
    import math
    # Use log2 as rough depth estimate
    return max(1, int(math.log2(len(poly_lines) + 1)))
```

**When to Adjust**:

- Set to 1-2 for simple pinnate leaves (most compound leaf trees)
- Set to 2-3 for bipinnate species
- Set to 0 for simple leaves (non-compound)

---

### compoundMaxBranchNumber

**Type**: `int`  
**Typical Range**: 5-30  
**Example**: `16` (Hazel)

**What It Controls**:

- Maximum number of **leaflets** on a compound leaf structure
- Total count of leaf branches within one compound leaf
- Includes all sub-branches across all generations

**Biological Meaning**:

- Directly correlates to visual leaflet count per leaf
- Odd-pinnate leaves: odd number (7, 9, 11, 13, 15)
- Even-pinnate leaves: even number (8, 10, 12, 14, 16)
- Terminal leaflet adds 1 to count

**Species-Specific Values**:

```text
Low Count (5-11):
- Black Locust: 7-11 leaflets
- Elderberry: 5-7 leaflets
- Box Elder: 3-5 leaflets

Medium Count (11-19):
- Ash: 9-13 leaflets
- Walnut: 15-23 leaflets
- Mountain Ash: 11-15 leaflets

High Count (20+):
- Honey Locust (bipinnate): 20-30 per pinnae
- Tree of Heaven: 11-25 leaflets
- Black Walnut: 15-23 leaflets
```

**Relationship to compoundMaxBranchGeneration**:

```text
Generation 1 (pinnate): compoundMaxBranchNumber = total leaflets
Generation 2 (bipinnate): compoundMaxBranchNumber = leaflets × pinnae
Example: 10 leaflets × 5 pinnae = 50 total leaf segments
```

**When to Adjust**:

- Match to species leaf morphology
- Increase for species with many leaflets
- Consider impact on rendering performance (more leaflets = more geometry)

---

## Photogrammetry Parameters

### photogrammetryTrunk

**Type**: `int` (boolean: 0 or 1)  
**Values**: `0` = procedural, `1` = photogrammetry  
**Example**: `0` (procedural generation)

**What It Controls**:

- Whether to use **photogrammetry-scanned mesh** for trunk instead of procedural generation
- When `1`: PVE looks for photogrammetry mesh assets
- When `0`: PVE generates trunk procedurally from growth simulation

**Use Cases**:

**Photogrammetry Mode (value = 1)**:

- High-fidelity hero trees requiring realistic bark detail
- Close-up cinematics or architectural visualization
- Trees where trunk character is critical (ancient oaks, gnarled pines)
- When you have scanned trunk meshes available

**Procedural Mode (value = 0)** - Recommended for GrowPy:

- Procedurally generated forests (no scan data available)
- Medium-to-far viewing distances
- Parametric control over trunk shape and growth
- Consistent visual style across many tree instances
- Better performance (no high-poly photogrammetry meshes)

**Related JSON Attributes** (when photogrammetryTrunk = 1):

```json
{
  "photogrammetryTrunk": {"value": 1},
  "photogrammetryMeshNames": {
    "value": ["/Game/Trees/Oak_Scans/Oak_Trunk_01"]
  },
  "photogrammetryMeshes": {
    "value": [
      {"mesh": "/Game/Trees/Oak_Scans/Oak_Trunk_01_Mesh", "transform": {...}}
    ]
  }
}
```

**For GrowPy Workflow**:

- Always set to `0` (procedural)
- GrowPy generates trunk from growth simulation
- No photogrammetry mesh assets available

---

## Scale and Size Parameters

These parameters define **dimensional limits** and **thickness values** for the tree geometry.

### maxPscale

**Type**: `float`  
**Typical Range**: 0.005 - 0.05 (meters)  
**Example**: `0.0073267` (Hazel, ~7mm radius at base)

**What It Controls**:

- Maximum **point scale** (radius) in the tree skeleton
- Represents the thickest branch segment in the tree
- Typically the trunk base radius
- Units: meters (in Unreal/USD coordinate system)

**Biological Meaning**:

- Trunk diameter at base = `maxPscale × 2`
- Example values:
  - Young sapling: 0.005-0.01 (5-10mm radius, 1-2cm diameter)
  - Mature small tree: 0.01-0.03 (1-3cm radius, 2-6cm diameter)
  - Large mature tree: 0.03-0.10 (3-10cm radius, 6-20cm diameter)
  - Ancient tree: 0.10-0.50 (10-50cm radius, 20cm-1m diameter)

**Hazel Example**:

```text
maxPscale = 0.0073267 meters
Trunk radius = 7.3mm
Trunk diameter = 14.7mm (1.47cm)
→ Young hazel shrub
```

**How GrowPy Calculates It**:

```python
def _get_max_pscale(grove):
    """Get maximum branch radius from Grove skeleton"""
    # Currently returns placeholder
    # Should extract: max(skeleton.point_attribute_radius)
    return 0.02  # Default ~2cm radius
```

**When to Adjust**:

- Scale proportionally with tree height
- Match to species typical trunk thickness
- Consider tree age (young vs mature vs ancient)
- Affects visual weight and realism

**Relationship to Tree Height**:

```text
Typical Ratios (trunk diameter : tree height):
- Conifers: 1:40 to 1:60 (slender)
- Broadleaf: 1:20 to 1:40 (medium)
- Short/thick trees: 1:10 to 1:20 (stout)

Example: 15m tall Oak
  Height:Diameter = 1:30
  Diameter = 15m / 30 = 0.5m
  Radius = 0.25m
  maxPscale = 0.25
```

---

### minPscale

**Type**: `float`  
**Typical Range**: 0.0 - 0.002 (meters)  
**Example**: `0.0` (zero - thinnest twigs taper to point)

**What It Controls**:

- Minimum **point scale** (radius) for smallest branches
- Thinnest twig/branch tip radius
- Setting to 0.0 allows branches to taper to a point

**Biological Meaning**:

- Natural branches taper to very thin tips
- `minPscale = 0.0`: Full taper to point (most realistic)
- `minPscale > 0`: Maintains minimum thickness (stylized look)

**Visual Effects**:

```text
minPscale = 0.0:
  ✓ Natural tapering to points
  ✓ Realistic branch tips
  ✓ Smooth silhouettes
  
minPscale = 0.001 (1mm):
  • Prevents ultra-thin geometry
  • Useful for rendering issues with near-zero thickness
  • Slight stylized look

minPscale = 0.002-0.005:
  • Noticeably stubby branch ends
  • Stylized/artistic look
  • Better for low-poly or distant LODs
```

**Recommendation for GrowPy**:

- Use `0.0` for realistic natural trees
- Use `0.001-0.002` only if encountering rendering artifacts

---

### max_pscale

**Type**: `float`  
**Typical Range**: 0.01 - 0.05 (meters)  
**Example**: `0.0136115` (Hazel)

**What It Controls**:

- Alternative/redundant parameter for maximum branch radius
- Appears to be duplicate of `maxPscale` in some implementations
- May be legacy parameter from older PVE versions

**Usage**:

- Often has same value as `maxPscale`
- Keep synchronized with `maxPscale` for consistency
- If different from `maxPscale`, may represent trunk-specific max vs branch max

**Example from Hazel**:

```json
{
  "maxPscale": {"value": 0.0073267},   // 7.3mm
  "max_pscale": {"value": 0.0136115}   // 13.6mm (nearly 2× larger)
}
```

**Interpretation**:

- `maxPscale` = thickest **branch** radius
- `max_pscale` = thickest **trunk** radius (at base)
- Allows trunk to be thicker than branches

**Recommendation**:

- Set `max_pscale` ≈ 1.5-2× `maxPscale` for realistic trunk/branch ratio
- Or keep identical for uniform scaling

---

### max_curve_length

**Type**: `float`  
**Typical Range**: 0.5 - 5.0 (meters)  
**Example**: `0.9716332` (Hazel, ~97cm longest branch)

**What It Controls**:

- Maximum **branch segment length** in the tree
- Longest single branch polyline from base to tip
- Not total tree height, but longest individual branch path

**Biological Meaning**:

- Typically the main trunk length (root to apex)
- Can also be a long horizontal branch
- Influences overall tree proportions

**Example Values**:

```text
Young trees (0.5-2.0m):
  Sapling: 0.5-1.0m
  Young tree: 1.0-2.0m

Mature trees (2.0-10.0m):
  Small mature: 2.0-4.0m
  Standard mature: 4.0-8.0m
  Large mature: 8.0-15.0m

Ancient/Large trees (10.0-30.0m):
  Large oak: 15.0-25.0m
  Sequoia: 30.0-80.0m
```

**Hazel Example**:

```text
max_curve_length = 0.9716332m
→ ~97cm tall hazel shrub
→ Matches typical hazel growth form (multi-stem shrub, not tall tree)
```

**How GrowPy Calculates It**:

```python
def _get_max_curve_length(grove):
    """Get maximum branch length from Grove skeleton"""
    # Currently returns placeholder
    # Should extract: max(length(polyline) for all branches)
    return 3.0  # Default 3m
```

**When to Adjust**:

- Scale with target tree height
- Match species growth form (shrub vs tree)
- Coordinate with `maxPscale` for proper proportions

**Relationship to maxPscale**:

```text
Slenderness Ratio = max_curve_length / (maxPscale × 2)

Example: Hazel
  Length = 0.97m
  Diameter = 0.0073 × 2 = 0.0146m (1.46cm)
  Slenderness = 0.97 / 0.0146 = 66.4
  → Very slender shrub form (realistic for hazel)

Example: Mature Oak
  Length = 15m
  Diameter = 0.25 × 2 = 0.50m (50cm)
  Slenderness = 15 / 0.50 = 30
  → Moderate proportions (realistic for oak)
```

---

## Deprecated/Legacy Parameters

These may appear in reference JSONs but are less commonly used in modern PVE versions:

### maxDavinciPscales

**Type**: `float array`  
**Status**: Legacy parameter (possibly from DaVinci Tree tool integration)

### maxPscales

**Type**: `float array`  
**Status**: Array version of maxPscale (may support per-LOD scaling)

---

## Species-Specific Configuration Examples

### Small Shrub (Common Hazel)

```json
{
  "maxBranchNumber": {"value": 17},
  "maxBudNumber": {"value": 79},
  "compoundMaxBranchGeneration": {"value": 3},
  "compoundMaxBranchNumber": {"value": 16},
  "photogrammetryTrunk": {"value": 0},
  "maxPscale": {"value": 0.0073267},
  "minPscale": {"value": 0.0},
  "max_curve_length": {"value": 0.9716332},
  "max_pscale": {"value": 0.0136115}
}
```

**Analysis**: Multi-stem shrub form, compound leaves, ~1m tall

---

### Mature Broadleaf Tree (European Beech)

```json
{
  "maxBranchNumber": {"value": 120},
  "maxBudNumber": {"value": 600},
  "compoundMaxBranchGeneration": {"value": 1},
  "compoundMaxBranchNumber": {"value": 1},
  "photogrammetryTrunk": {"value": 0},
  "maxPscale": {"value": 0.045},
  "minPscale": {"value": 0.0},
  "max_curve_length": {"value": 18.0},
  "max_pscale": {"value": 0.075}
}
```

**Analysis**: Large tree, simple leaves, ~18m tall, 15cm trunk diameter

---

### Large Compound Leaf Tree (Black Walnut)

```json
{
  "maxBranchNumber": {"value": 150},
  "maxBudNumber": {"value": 750},
  "compoundMaxBranchGeneration": {"value": 1},
  "compoundMaxBranchNumber": {"value": 19},
  "photogrammetryTrunk": {"value": 0},
  "maxPscale": {"value": 0.060},
  "minPscale": {"value": 0.0},
  "max_curve_length": {"value": 22.0},
  "max_pscale": {"value": 0.100}
}
```

**Analysis**: Large tree, pinnate leaves (15-23 leaflets), ~22m tall

---

### Coniferous Tree (Scots Pine)

```json
{
  "maxBranchNumber": {"value": 80},
  "maxBudNumber": {"value": 320},
  "compoundMaxBranchGeneration": {"value": 0},
  "compoundMaxBranchNumber": {"value": 0},
  "photogrammetryTrunk": {"value": 0},
  "maxPscale": {"value": 0.035},
  "minPscale": {"value": 0.0},
  "max_curve_length": {"value": 25.0},
  "max_pscale": {"value": 0.055}
}
```

**Analysis**: Coniferous, needle clusters (not compound leaves), ~25m tall

---

## Best Practices for Configuration

### Starting from Reference Data

1. **Extract from Quixel Megaplants**:

   ```bash
   python src/growpy/utils/extract_pve_config.py
   ```

2. **Copy and modify** for your species:

   ```bash
   cp data/assets/pve_configs/common_hazel_pve.json \
      data/assets/pve_configs/my_species_pve.json
   ```

3. **Adjust parameters** based on species characteristics

### Scaling for Tree Size

When scaling a tree from reference size to target size:

```python
# Example: Scale Hazel from 1m to 3m
scale_factor = 3.0 / 0.97  # target_height / reference_height

# Scale all dimensional parameters
config["maxPscale"]["value"] *= scale_factor
config["max_pscale"]["value"] *= scale_factor
config["max_curve_length"]["value"] *= scale_factor
# minPscale stays 0.0 (tapers to point regardless of scale)

# Branch/bud counts increase non-linearly (approximately square)
scale_complexity = scale_factor ** 1.5  # ~1.5 to 2.0 power
config["maxBranchNumber"]["value"] = int(17 * scale_complexity)
config["maxBudNumber"]["value"] = int(79 * scale_complexity)
```

### Validation Checklist

Before using a config:

- [ ] `maxBranchNumber` reasonable for tree size and age
- [ ] `maxBudNumber` ≈ 3-6× `maxBranchNumber`
- [ ] `compoundMaxBranchGeneration` matches leaf type (0=simple, 1-2=compound)
- [ ] `compoundMaxBranchNumber` matches species leaflet count
- [ ] `photogrammetryTrunk = 0` for procedural workflow
- [ ] `maxPscale` and `max_pscale` proportional to tree height
- [ ] `minPscale = 0.0` for natural tapering
- [ ] `max_curve_length` matches target tree height
- [ ] Slenderness ratio (height/diameter) realistic for species

---

## Integration with GrowPy

### Configuration File Structure

Store per-species configs in: `data/assets/pve_configs/<species_name>_pve.json`

```json
{
  "_comment": "PVE overrides for <species>",
  "_species": "<species_name>",
  "globalAttributes": {
    "maxBranchNumber": {...},
    "maxBudNumber": {...},
    "compoundMaxBranchGeneration": {...},
    "compoundMaxBranchNumber": {...},
    "photogrammetryTrunk": {...},
    "maxPscale": {...},
    "minPscale": {...},
    "max_curve_length": {...},
    "max_pscale": {...},
    "plantProfile_1": {...},
    "plantProfile_2": {...},
    "plantProfile_3": {...},
    "plantProfile_4": {...},
    "plantProfile_5": {...}
  }
}
```

### Automatic Application

When generating forest with PVE JSON:

```bash
python src/growpy/cli/generate_forest.py --generate-pve-json --quality high
```

GrowPy automatically:

1. Generates base PVE JSON from Grove simulation
2. Loads species-specific config from `data/assets/pve_configs/`
3. Applies overrides to globalAttributes
4. Exports complete PVE-compatible JSON

### Programmatic Access

```python
from pathlib import Path
from growpy.config.pve_species_overrides import load_species_pve_config, apply_species_overrides

# Load config
config = load_species_pve_config("European Beech", Path("data/assets/pve_configs"))

# Apply to PVE preset
pve_preset = {...}  # Base PVE JSON
apply_species_overrides(pve_preset, config, species_name="European Beech", verbose=True)
```

---

## Debugging and Troubleshooting

### Enable PVE Debug Mode

To see these attributes in Unreal Editor:

```text
# In Unreal Editor console (~ key)
PV.DebugMode.Enabled 1
```

### Validation Script

```python
import json
from pathlib import Path

def validate_pve_config(config_path: Path):
    """Validate PVE config attribute ranges"""
    with open(config_path) as f:
        config = json.load(f)
    
    attrs = config.get("globalAttributes", {})
    issues = []
    
    # Check required attributes
    required = [
        "maxBranchNumber", "maxBudNumber",
        "compoundMaxBranchGeneration", "compoundMaxBranchNumber",
        "photogrammetryTrunk", "maxPscale", "minPscale",
        "max_curve_length", "max_pscale"
    ]
    
    for attr in required:
        if attr not in attrs:
            issues.append(f"Missing required attribute: {attr}")
    
    # Validate ranges
    if "maxBranchNumber" in attrs:
        val = attrs["maxBranchNumber"]["value"]
        if not (1 <= val <= 1000):
            issues.append(f"maxBranchNumber {val} out of range (1-1000)")
    
    if "maxBudNumber" in attrs:
        val = attrs["maxBudNumber"]["value"]
        max_branch = attrs.get("maxBranchNumber", {}).get("value", 100)
        if not (max_branch <= val <= max_branch * 10):
            issues.append(f"maxBudNumber {val} suspicious (should be {max_branch}-{max_branch*10})")
    
    if "maxPscale" in attrs:
        val = attrs["maxPscale"]["value"]
        if not (0.001 <= val <= 1.0):
            issues.append(f"maxPscale {val} out of range (0.001-1.0)")
    
    if "max_curve_length" in attrs:
        val = attrs["max_curve_length"]["value"]
        if not (0.1 <= val <= 100.0):
            issues.append(f"max_curve_length {val} out of range (0.1-100.0)")
    
    if issues:
        print(f"Validation FAILED for {config_path.name}:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print(f"Validation PASSED for {config_path.name}")
        return True

# Usage
validate_pve_config(Path("data/assets/pve_configs/european_beech_pve.json"))
```

---

## Further Reading

- [PlantProfile Reference Guide](PLANTPROFILE_REFERENCE.md) - Crown envelope arrays
- [PVE Preset Workflow](PVE_PRESET_WORKFLOW.md) - Complete import guide
- [PVE Implementation Summary](PVE_IMPLEMENTATION_SUMMARY.md) - Technical details
- Grove 2.2 Documentation - Botanical simulation parameters

---

## Quick Reference Card

```text
PVE Attribute Quick Reference
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Branch/Bud Limits:
  maxBranchNumber      10-300      Total branch segments
  maxBudNumber         30-1500     Growth endpoints (≈3-5× branches)

Compound Leaves:
  compoundMaxBranchGeneration  0-3   Leaf hierarchy depth
    0 = simple leaf, 1 = pinnate, 2 = bipinnate
  compoundMaxBranchNumber      1-30  Leaflets per compound leaf

Photogrammetry:
  photogrammetryTrunk  0 or 1      0=procedural, 1=scanned mesh

Scale/Size:
  maxPscale           0.005-0.10   Trunk base radius (meters)
  minPscale           0.0          Twig tip radius (0=taper to point)
  max_pscale          0.01-0.15    Alternative max radius
  max_curve_length    0.5-30.0     Longest branch length (meters)

Typical Ratios:
  Buds:Branches       3:1 to 6:1
  Height:Diameter     20:1 to 60:1 (species-dependent)
  max_pscale:maxPscale  1.5:1 to 2:1 (trunk thicker than branches)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
