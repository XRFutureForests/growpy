# Grove to PVE Attribute Mapping Guide

Comprehensive mapping between Grove 2.2 seed.json parameters and PVE (Procedural Vegetation Editor) globalAttributes, explaining semantic equivalence, value compatibility, and conversion requirements.

## Overview

**Key Challenge**: Grove uses **simple scalar parameters** while PVE uses **curve-based arrays** for most growth attributes.

- **Grove**: Single values (e.g., `turn_to_light: 0.25`)
- **PVE**: Multi-value curves (e.g., `phototropism: [0.0, 0.407, 0.0, 0.533]`)

This means we cannot do direct 1:1 mapping - PVE attributes often represent **parametric curves** that define how a value changes over time, generation, or other gradients.

---

## Direct Mappings (Scalar to Scalar)

These attributes have straightforward correspondence:

### cycle

**PVE**: `"cycle": {"type": "int", "value": 8}`  
**Grove**: Derived from **simulation execution**, not seed.json  
**Extraction**: Count of `grove.simulate(flushes)` calls  
**Compatibility**: ✓ Direct - number of growth cycles simulated

### cycleTime  

**PVE**: `"cycleTime": {"type": "float", "value": 0.333}`  
**Grove**: Not in seed.json (internal parameter)  
**Extraction**: Fixed value (Grove uses 1.0 year per cycle typically)  
**Compatibility**: ✓ Direct - time duration per growth cycle  
**Typical Values**: 0.25-1.0 (fraction of year per cycle)

### gravitationalForce

**PVE**: `"gravitationalForce": {"type": "float", "value": 1.297}`  
**Grove**: `"bend_reaction": 0.27` (gravity response strength)  
**Semantic Match**: ⚠️ **Partial** - related concepts  

- Grove's `bend_reaction` controls how branches droop under weight  
- PVE's `gravitationalForce` is absolute gravitational pull  
**Conversion**: May need scaling (Grove 0.0-1.0 → PVE 0.5-3.0)

### randomSeed

**PVE**: `"randomSeed": {"type": "int", "value": 0}`  
**Grove**: `random_seed` parameter in Grove initialization (not in seed.json)  
**Extraction**: From `grove.set_random_seed(seed)`  
**Compatibility**: ✓ Direct - random number generator seed

---

## Curve-Based Mappings (Scalar to Array)

These require conversion from Grove's single value to PVE's curve array:

### phototropism (Light-Seeking Behavior)

**PVE**: `"phototropism": {"isArray": true, "value": [0.0, 0.407, 0.0, 0.533]}`  
**Grove**: `"turn_to_light": 0.25`, `"favor_bright": 0.48`  
**Semantic Match**: ✓ **Strong**  

- Grove: Simple strength (0.0-1.0)  
- PVE: Curve with multiple control points  

**PVE Curve Format** (4 values):

```text
[base_strength, curve_shape, min_value, max_value]
Example: [0.0, 0.407, 0.0, 0.533]
  - base_strength: 0.0 (starting value)
  - curve_shape: 0.407 (phototropism strength ~ turn_to_light)
  - min_value: 0.0 (lower bound)
  - max_value: 0.533 (upper bound ~ favor_bright)
```

**Conversion Formula**:

```python
grove_turn_to_light = 0.25
grove_favor_bright = 0.48

pve_phototropism = [
    0.0,                    # base (always 0)
    grove_turn_to_light,    # strength
    0.0,                    # min (always 0)
    grove_favor_bright      # max intensity
]
```

**Compatibility**: ⚠️ **Requires conversion** - Grove single value → PVE curve

---

### phyllotaxy (Branching Angle Pattern)

**PVE**: `"phyllotaxy": {"isArray": true, "value": [137.5, 0.0, 1.0, 0.0, ...15 values]}`  
**Grove**: `"add_angle": 0.96`, `"add_horizontal": 0.2`  
**Semantic Match**: ⚠️ **Partial**  

- Grove: Angle offset and horizontal bias  
- PVE: Golden angle (137.5°) + modulation curve  

**PVE Curve Format** (15 values):

```text
[golden_angle, variation_1, variation_2, ..., variation_14]
Example: [137.5, 0.0, 1.0, 0.0, 0.0, 0.0, ...]
  - value[0]: 137.5° (Fibonacci spiral angle - constant)
  - value[1-14]: Angle variations/modulations
```

**Botanical Context**:

- **137.5°** = Golden angle for optimal leaf spacing (Fibonacci)
- Variations allow departure from perfect spiral (natural irregularity)

**Conversion**: ❌ **Complex** - Grove uses different angle system

```python
# Grove's add_angle is relative (0.0-1.0 scale)
# PVE uses absolute degrees with modulation curve
# No direct conversion - use template and adjust

pve_phyllotaxy = [
    137.5,  # Golden angle (fixed)
    0.0,    # Base variation
    1.0,    # Primary modulation
    *([0.0] * 12)  # Additional variation terms
]
```

**Recommendation**: Use reference PVE values, don't convert from Grove

---

### axialElongation (Trunk/Main Stem Growth)

**PVE**: `"axialElongation": {"isArray": true, "value": [0.0447, 0.0, 0.0, 0.0, 0.0, 1.0]}`  
**Grove**: `"grow_length": 0.3`, `"grow_length_reduce": 0.78`  
**Semantic Match**: ✓ **Strong**  

- Grove: Growth length and reduction rate  
- PVE: Elongation curve over time/generation  

**PVE Curve Format** (6 values):

```text
[initial_rate, reduction_1, reduction_2, reduction_3, reduction_4, end_multiplier]
Example: [0.0447, 0.0, 0.0, 0.0, 0.0, 1.0]
  - value[0]: Initial growth rate (meters per cycle)
  - value[1-4]: Reduction factors per generation
  - value[5]: Final multiplier (usually 1.0)
```

**Conversion Formula**:

```python
grove_grow_length = 0.3  # Base growth length
grove_grow_length_reduce = 0.78  # Reduction per generation

# Convert to PVE format
pve_axial_elongation = [
    grove_grow_length * 0.15,  # Scale to PVE units (~0.3 * 0.15 = 0.045)
    0.0,  # No reduction terms (Grove handles differently)
    0.0,
    0.0,
    0.0,
    1.0   # End multiplier
]
```

**Compatibility**: ⚠️ **Approximate** - Different curve systems

---

### lateralElongation (Side Branch Growth)

**PVE**: `"lateralElongation": {"isArray": true, "value": [0.000529, 1.0, 0.5, 7000.0, 10000.0, 0.5, 5.0, 0.737, 0.0]}`  
**Grove**: `"grow_length": 0.3`, `"grow_length_reduce": 0.78`, `"favor_end": 0.3`  
**Semantic Match**: ⚠️ **Partial**  

- Grove: Uses same growth length for lateral branches  
- PVE: Separate curve for lateral branch behavior  

**PVE Curve Format** (9 values):

```text
[base_rate, strength, falloff, param1, param2, param3, param4, end_bias, zero]
Example: [0.000529, 1.0, 0.5, 7000.0, 10000.0, 0.5, 5.0, 0.737, 0.0]
  - value[0]: 0.000529 - Base lateral growth rate (much smaller than axial)
  - value[1]: 1.0 - Strength multiplier
  - value[2]: 0.5 - Falloff rate
  - value[3-6]: 7000.0, 10000.0, 0.5, 5.0 - Complex curve parameters
  - value[7]: 0.737 - End bias (~favor_end)
  - value[8]: 0.0 - Zero term
```

**Conversion**: ❌ **Very Complex** - PVE uses sophisticated curve
**Recommendation**: Use reference values from similar species

---

### branchingCondition (Branch Formation Rules)

**PVE**: `"branchingCondition": {"isArray": true, "value": [0.0482, 0.1084, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0]}`  
**Grove**: `"add_chance": 1.0`, `"add_chance_reduce": 0.0`, `"add_fork": 0.0`  
**Semantic Match**: ⚠️ **Partial**  

- Grove: Simple probability of adding branches  
- PVE: Complex conditional curve  

**PVE Curve Format** (8 values):

```text
[threshold_1, threshold_2, min, max, strength, param1, param2, param3]
Example: [0.0482, 0.1084, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0]
  - value[0-1]: 0.0482, 0.1084 - Branching thresholds
  - value[2-3]: 0.0, 1.0 - Min/max bounds
  - value[4]: 1.0 - Strength (~add_chance)
  - value[5-7]: 0.0, 0.0, 0.0 - Additional parameters
```

**Conversion**: ❌ **Complex** - Different branching logic
**Recommendation**: Use species-specific reference values

---

### leafGrowth (Foliage Development)

**PVE**: `"leafGrowth": {"isArray": true, "value": [0.1409, 0.1, 0.167, 0.15, 2.0, 0.0, 0.1798, 0.0401, 0.0]}`  
**Grove**: `"twig_density": 1.0`, `"twig_longevity": 4`  
**Semantic Match**: ⚠️ **Weak** - Different concepts  

- Grove: Twig count and lifespan  
- PVE: Leaf development curve (size, timing, senescence)  

**PVE Curve Format** (9 values):

```text
[spring_rate, spring_start, summer_max, autumn_start, autumn_duration, winter_min, emergence, senes, end]
Example: [0.1409, 0.1, 0.167, 0.15, 2.0, 0.0, 0.1798, 0.0401, 0.0]
  - value[0]: 0.1409 - Spring emergence rate
  - value[1]: 0.1 - Spring start time
  - value[2]: 0.167 - Summer maximum foliage
  - value[3]: 0.15 - Autumn start
  - value[4]: 2.0 - Autumn duration
  - value[5]: 0.0 - Winter minimum
  - value[6]: 0.1798 - Emergence factor
  - value[7]: 0.0401 - Senescence factor
  - value[8]: 0.0 - End term
```

**Conversion**: ❌ **No direct mapping** - Grove doesn't model seasonal leaf cycles
**Recommendation**: Use species-specific reference values

---

### lightDetection (Light Sensing Resolution)

**PVE**: `"lightDetection": {"isArray": true, "value": [3.0, 1.0, 64.0, 32.0, 1.0]}`  
**Grove**: `"shade_area": 8.0`, `"shade_area_depth": 0.5`, `"shade_alongside_diameter": 0.2`  
**Semantic Match**: ⚠️ **Partial** - Related concepts  

- Grove: Shadow casting parameters  
- PVE: Light sensing resolution/sampling  

**PVE Curve Format** (5 values):

```text
[depth_levels, strength, resolution_x, resolution_y, sampling]
Example: [3.0, 1.0, 64.0, 32.0, 1.0]
  - value[0]: 3.0 - Depth levels for light rays
  - value[1]: 1.0 - Detection strength
  - value[2]: 64.0 - Horizontal resolution (~shade_area)
  - value[3]: 32.0 - Vertical resolution
  - value[4]: 1.0 - Sampling rate
```

**Conversion**: ⚠️ **Approximate**

```python
grove_shade_area = 8.0
grove_shade_depth = 0.5

pve_light_detection = [
    3.0,                        # Depth levels (fixed)
    1.0,                        # Strength (fixed)
    grove_shade_area * 8,       # Horizontal res (8.0 * 8 = 64)
    grove_shade_area * 4,       # Vertical res (8.0 * 4 = 32)
    1.0                         # Sampling (fixed)
]
```

**Compatibility**: ⚠️ **Requires interpretation** - Different shading systems

---

## Extractable from Simulation Results

These PVE attributes should be **calculated from Grove simulation output**, not from seed.json:

### maxBranchNumber

**Source**: `len(skeleton.poly_lines)`  
**Method**: Build skeleton, count polylines  
**Current Implementation**: ✓ Correct

```python
def _get_num_branches(grove, skeleton):
    return len(skeleton.poly_lines)
```

### maxBudNumber  

**Source**: Estimate from branch count  
**Method**: Approximate as branches × 3-5  
**Current Implementation**: ⚠️ Too simple (returns branch count)

```python
# Current (too simple)
def _get_num_buds(grove, skeleton):
    return len(skeleton.poly_lines)

# Better implementation
def _get_num_buds(grove, skeleton):
    num_branches = len(skeleton.poly_lines)
    return int(num_branches * 4.5)  # Average 4-5 buds per branch
```

### compoundMaxBranchGeneration

**Source**: Calculate max hierarchy depth from skeleton  
**Method**: Traverse skeleton hierarchy  
**Current Implementation**: ⚠️ Uses log2 approximation (too crude)

```python
# Current (approximation)
def _get_max_generation(grove, skeleton):
    import math
    return max(1, int(math.log2(len(poly_lines) + 1)))

# Better implementation would traverse actual parent-child relationships
```

### maxPscale (Maximum Branch Radius)

**Source**: `max(skeleton.point_attribute_radius)`  
**Method**: Extract from skeleton geometry  
**Current Implementation**: ❌ Returns placeholder (0.02)

```python
# Current (placeholder)
def _get_max_pscale(grove):
    return 0.02

# Correct implementation
def _get_max_pscale(grove, skeleton):
    if skeleton and hasattr(skeleton, 'point_attribute_radius'):
        return max(skeleton.point_attribute_radius)
    return 0.02  # Fallback
```

### max_curve_length (Longest Branch)

**Source**: Calculate from skeleton polyline lengths  
**Method**: Measure each branch, return max  
**Current Implementation**: ❌ Returns placeholder (3.0)

```python
# Current (placeholder)
def _get_max_curve_length(grove):
    return 3.0

# Correct implementation
def _get_max_curve_length(grove, skeleton):
    if skeleton and skeleton.poly_lines:
        max_length = 0.0
        for polyline in skeleton.poly_lines:
            # Calculate polyline length by summing segment distances
            length = calculate_polyline_length(polyline)
            max_length = max(max_length, length)
        return max_length
    return 3.0  # Fallback
```

---

## No Grove Equivalent (Require Config Files)

These PVE attributes have **no Grove equivalent** and must come from species-specific config files:

### plantProfile_1 through plantProfile_5

**Reason**: Grove doesn't generate top-down crown envelopes  
**Solution**: Species-specific JSON configs  
**Current Implementation**: ✓ Config system in place

### Compound Leaf Parameters

- `compoundMaxBranchNumber`: Leaflet count (species-specific)  
**Reason**: Grove doesn't model compound leaf morphology  
**Solution**: Species botanical data in configs

### photogrammetryTrunk

**Reason**: Grove generates procedural trees only  
**Solution**: Always set to 0 (procedural)

### Deprecated Scale Parameters

- `minPscale`, `max_pscale`, `maxDavinciPscales`, `maxPscales`  
**Reason**: Legacy parameters, can derive from Grove geometry  
**Solution**: Use config files or calculate from skeleton

---

## Recommended Implementation Strategy

### Phase 1: Currently Implemented ✓

- Extract simple scalars (cycle, randomSeed)
- Use config files for plantProfiles and compound leaf params
- Calculate maxBranchNumber from skeleton

### Phase 2: Improve Simulation Extraction

- Fix `_get_num_buds()` to use realistic multiplier
- Implement proper `_get_max_pscale()` from skeleton radius
- Implement `_get_max_curve_length()` from polyline lengths
- Improve `_get_max_generation()` with real hierarchy traversal

### Phase 3: Curve Conversion (Optional)

- Convert `turn_to_light` → `phototropism` curve
- Convert `grow_length` → `axialElongation` curve
- Convert `shade_area` → `lightDetection` parameters

### Phase 4: Species-Specific Calibration

- Create reference curve libraries for common species
- Validate PVE tree behavior matches Grove simulation
- Fine-tune curve parameters for biological accuracy

---

## Compatibility Matrix

| PVE Attribute | Grove Source | Mapping Type | Status |
|---------------|--------------|--------------|--------|
| cycle | Simulation count | Direct | ✓ Working |
| cycleTime | Fixed value | Direct | ✓ Working |
| randomSeed | grove.set_random_seed() | Direct | ✓ Working |
| gravitationalForce | bend_reaction | Approximate | ⚠️ Needs scaling |
| phototropism | turn_to_light, favor_bright | Curve conversion | ⚠️ Needs implementation |
| phyllotaxy | add_angle | Complex | ❌ Use reference |
| axialElongation | grow_length | Curve conversion | ⚠️ Needs implementation |
| lateralElongation | grow_length | Complex curve | ❌ Use reference |
| branchingCondition | add_chance | Complex curve | ❌ Use reference |
| leafGrowth | twig_density | No equivalent | ❌ Use reference |
| lightDetection | shade_area | Approximate | ⚠️ Needs implementation |
| maxBranchNumber | skeleton.poly_lines | Calculate | ✓ Working |
| maxBudNumber | skeleton estimate | Calculate | ⚠️ Needs improvement |
| compoundMaxBranchGeneration | skeleton hierarchy | Calculate | ⚠️ Needs improvement |
| compoundMaxBranchNumber | Species data | Config file | ✓ Working |
| maxPscale | skeleton.radius | Calculate | ❌ Needs implementation |
| max_curve_length | skeleton length | Calculate | ❌ Needs implementation |
| plantProfile_1-5 | None | Config file | ✓ Working |
| photogrammetryTrunk | None | Fixed (0) | ✓ Working |

**Legend**:

- ✓ Working: Implemented and functional
- ⚠️ Needs work: Implemented but needs improvement
- ❌ Missing: Not implemented, needs work

---

## Example: Converting European Beech

### Grove seed.json Values

```json
{
  "turn_to_light": 0.25,
  "favor_bright": 0.48,
  "bend_reaction": 0.27,
  "grow_length": 0.3,
  "grow_length_reduce": 0.78,
  "shade_area": 8.0,
  "shade_area_depth": 0.5
}
```

### Converted PVE Attributes

```json
{
  "gravitationalForce": {"value": 1.3},  // bend_reaction * 4.8
  "phototropism": {"value": [0.0, 0.25, 0.0, 0.48]},
  "axialElongation": {"value": [0.045, 0.0, 0.0, 0.0, 0.0, 1.0]},
  "lightDetection": {"value": [3.0, 1.0, 64.0, 32.0, 1.0]}
}
```

### From Simulation Results

```python
skeleton = grove.build_skeletons()[0]

maxBranchNumber = len(skeleton.poly_lines)  # e.g., 120
maxBudNumber = maxBranchNumber * 4.5  # e.g., 540
maxPscale = max(skeleton.point_attribute_radius)  # e.g., 0.045
max_curve_length = calculate_max_polyline_length(skeleton)  # e.g., 18.0
```

### From Config Files

```json
{
  "plantProfile_1": {"value": [0.85, 0.87, ...]},  // 100 values
  "compoundMaxBranchNumber": {"value": 1},  // Simple leaves
  "photogrammetryTrunk": {"value": 0}
}
```

---

## Validation Checklist

When mapping Grove to PVE:

- [ ] Simulation parameters (cycle, randomSeed) extracted correctly
- [ ] Skeleton-based metrics (branches, buds, thickness) calculated
- [ ] Curve conversions produce reasonable value ranges
- [ ] Species-specific configs loaded and applied
- [ ] Tree behavior in Unreal matches Grove simulation
- [ ] Growth patterns follow species characteristics
- [ ] Scale/proportions realistic for species

---

## Further Reading

- [PVE Attribute Reference](PVE_ATTRIBUTE_REFERENCE.md) - Detailed attribute explanations
- [PlantProfile Reference](PLANTPROFILE_REFERENCE.md) - Crown profile arrays
- Grove 2.2 Documentation - Parameter descriptions
- PVE User Guide - Curve system explanations

---

## Summary

**Direct Extraction**: cycle, randomSeed, maxBranchNumber  
**Needs Improvement**: maxBudNumber, maxPscale, max_curve_length, compoundMaxBranchGeneration  
**Curve Conversion Possible**: phototropism, axialElongation, lightDetection, gravitationalForce  
**Use References**: phyllotaxy, lateralElongation, branchingCondition, leafGrowth  
**Config Files Required**: plantProfiles, compoundMaxBranchNumber, photogrammetryTrunk

The current GrowPy implementation uses a **hybrid approach**: extracting what's directly available from Grove, calculating what can be derived from simulation results, and using species-specific config files for attributes with no Grove equivalent. This is the correct strategy.
