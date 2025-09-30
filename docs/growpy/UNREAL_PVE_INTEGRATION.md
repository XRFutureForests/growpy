# Unreal Engine Procedural Vegetation Editor (PVE) Integration

## Overview

This document describes how to work with Unreal Engine's Procedural Vegetation Editor exported JSON files and potentially use them to inform Grove tree generation.

## PVE JSON Structure

Unreal PVE exports tree definitions as JSON files containing:

1. **globalAttributes**: High-level parameters controlling tree growth behavior
2. **points**: 3D point cloud data with per-point attributes
3. **primitives**: Geometric primitives (branches, leaves, etc.)

### Sample Analysis

From the Hazel tree samples in `data/SampleAssets/Tree_Common_Hazel_01/Instances`:

| File | Size (MB) | Cycles | Global Attrs | Point Attrs |
|------|-----------|--------|--------------|-------------|
| Broadleaf_Hazel_01.json | 19.49 | 30 | 40 | 28 |
| Broadleaf_Hazel_02.json | 6.88 | 30 | 40 | 28 |
| Broadleaf_Hazel_03.json | 3.45 | 17 | 40 | 28 |
| Broadleaf_Hazel_04.json | 1.81 | 8 | 38 | 28 |

## Key PVE Parameters

### Growth Control
- **cycle**: Number of growth iterations (maps to Grove's growth_cycles)
- **cycleTime**: Time per growth cycle (Grove doesn't have direct equivalent)
- **compoundMaxBranchGeneration**: Maximum branching depth (maps to Grove's max_order)
- **compoundMaxBranchNumber**: Maximum branches per node

### Physical Forces
- **gravitationalForce**: Branch drooping under gravity (maps to Grove's gravity_force)
- **phototropism**: Light-seeking behavior (maps to Grove's phototropism)
- **gravitropism**: Gravity response behavior (maps to Grove's gravitropism)

### Elongation
- **axialElongation**: Primary growth direction elongation
- **lateralElongation**: Side branch elongation
- **branchingCondition**: Threshold for branch formation

### Leaf Growth
- **leafGrowth**: Leaf development parameters
- **abscissionSenescense**: Leaf drop/aging parameters
- **phyllotaxy**: Leaf arrangement pattern

### Light Detection
- **lightDetection**: Light sensing parameters for phototropism

## PVE to Grove Parameter Mapping

| PVE Parameter | Grove Equivalent | Notes |
|---------------|------------------|-------|
| cycle | growth_cycles | Direct 1:1 mapping |
| gravitationalForce | gravity_force | Controls branch drooping |
| phototropism | phototropism | Light-seeking behavior |
| gravitropism | gravitropism | Gravity response |
| axialElongation | elongation | Primary growth direction |
| branchingCondition | branching_threshold | When branches form |
| compoundMaxBranchGeneration | max_order | Max branch depth |
| compoundMaxBranchNumber | - | Grove uses probability instead |
| cycleTime | - | PVE-specific timing |
| leafGrowth | - | Grove uses twig system |
| abscissionSenescense | - | PVE-specific |
| randomSeed | random_seed | 1:1 mapping |

## Grove-Only Parameters

Grove has additional parameters not present in PVE:
- **apical_dominance**: Controls branch suppression
- **thickness**: Branch thickness control
- **resolution**: Mesh resolution
- **build_cutoff_age**: LOD control
- **build_cutoff_thickness**: LOD control

## Usage

### Analyze PVE JSON Files

```bash
# Analyze a single file
./.conda/python.exe src/growpy/utils/unreal_pve_analyzer.py data/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json

# Analyze all files in a directory
./.conda/python.exe src/growpy/utils/unreal_pve_analyzer.py data/SampleAssets/Tree_Common_Hazel_01/Instances
```

### Extract Grove Hints

```python
from pathlib import Path
from growpy.utils.unreal_pve_analyzer import extract_grove_preset_hints

hints = extract_grove_preset_hints(
    Path("data/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json")
)

print(hints)
# Output:
# {
#   'species_name': 'Broadleaf_Hazel_04',
#   'source': 'Unreal PVE Export',
#   'suggested_parameters': {
#     'growth_cycles': 8,
#     'gravity_force': 1.297,
#     'phototropism': 0.407,
#     ...
#   }
# }
```

## Limitations

### Why Not Full Conversion?

1. **Different Growth Models**: PVE and Grove use fundamentally different procedural algorithms
2. **Geometric Data**: PVE exports contain baked point clouds and geometry that can't be "un-baked"
3. **Leaf Systems**: PVE has integrated leaf generation; Grove uses separate twig assets
4. **Time-based vs Flush-based**: PVE uses time-based cycles; Grove uses discrete growth flushes

### What Can Be Used?

- **Parameter Inspiration**: PVE parameters can inform Grove preset creation
- **Visual Reference**: PVE geometry can serve as reference for Grove tree appearance
- **Growth Behavior**: Understanding PVE growth patterns can help tune Grove parameters
- **Species Characteristics**: PVE captures species-specific traits (drooping, branching angles, etc.)

## Best Approach

1. **Use PVE as Reference**: Analyze PVE exports to understand target tree characteristics
2. **Manual Grove Tuning**: Create Grove presets manually, informed by PVE parameters
3. **Iterative Refinement**: Adjust Grove parameters to match PVE visual results
4. **Hybrid Workflow**: Use PVE for hero trees; Grove for procedural forests

## Sample Trees Available

From `data/SampleAssets`:
- **Tree_Common_Hazel_01**: Hazel tree with 4 growth variants
- **Tree_European_Beech_01**: European Beech with branches and leaves
- **Tree_European_QuakingAspen_01**: Quaking Aspen
- **Tree_Norway_Maple_01**: Norway Maple

Each contains:
- PVE data asset (`PVE_*.uasset`)
- Skeletal meshes (`SK_*.uasset`)
- Instance definitions (branches, leaves)
- Materials and textures
- JSON exports (Hazel only in this sample)

## Future Enhancements

Potential improvements to the integration:
1. **Visual Comparison Tool**: Compare Grove outputs to PVE geometry
2. **Parameter Suggestion Engine**: ML-based Grove parameter suggestions from PVE data
3. **Automated Preset Generation**: Best-effort Grove preset creation from PVE parameters
4. **Reverse Engineering**: Analyze PVE point attributes to infer growth patterns