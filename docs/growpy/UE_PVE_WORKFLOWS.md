# Unreal Engine PVE Integration Workflows

## Overview

GrowPy provides bidirectional workflow support between Grove and Unreal Engine's Procedural Vegetation Editor (PVE):

1. **PVE → Grove**: Analyze UE exports to inform Grove parameters
2. **Grove → PVE**: Export Grove trees for import into Unreal

## Quick Reference

### Workflow 1: PVE to Grove (Analysis)

**Use when**: You have UE PVE trees and want to understand their parameters or recreate similar trees in Grove.

```bash
# Analyze PVE JSON
./.conda/python.exe src/growpy/utils/unreal_pve_analyzer.py \
  data/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json

# Convert to Grove preset suggestion
./.conda/python.exe src/growpy/utils/pve_to_grove_converter.py \
  data/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json \
  output/hazel_grove_preset.json
```

**Output**: Grove parameter suggestions based on PVE settings

**Limitations**:
- Not a direct conversion
- Parameters are starting points requiring tuning
- Can't extract geometry (it's baked)

### Workflow 2: Grove to PVE (Export)

**Use when**: You want to use Grove's procedural generation and bring results into Unreal.

```bash
# Export Grove tree to PVE JSON
./.conda/python.exe src/growpy/cli/export_grove_to_pve.py \
  --species "Hazel" \
  --cycles 8 \
  --output output/pve_exports/hazel.json
```

**Output**: PVE-compatible JSON with skeleton structure

**What you get**:
- Branch skeleton (curves/polylines)
- Point positions
- Growth parameters
- Hierarchy information

**What you add in UE**:
- Leaf/twig instances
- Materials
- Branch thickness
- Mesh generation

## Detailed Workflows

### Analysis Workflow (PVE → Grove)

```mermaid
graph LR
    A[UE PVE Export] --> B[PVE JSON]
    B --> C[Analyzer Tool]
    C --> D[Grove Preset Hints]
    D --> E[Manual Grove Tuning]
    E --> F[Grove Tree]
```

**Steps**:
1. Export tree from UE PVE as JSON
2. Run analyzer to extract parameters
3. Convert to Grove preset suggestions
4. Create Grove tree with suggested params
5. Manually tune until visual match
6. Save as Grove preset

**Tools**:
- `unreal_pve_analyzer.py`: Analyze structure
- `pve_to_grove_converter.py`: Generate suggestions

**See**: [UNREAL_PVE_INTEGRATION.md](UNREAL_PVE_INTEGRATION.md)

### Export Workflow (Grove → PVE)

```mermaid
graph LR
    A[Grove Preset] --> B[Simulate Growth]
    B --> C[Build Skeleton]
    C --> D[Grove to PVE Converter]
    D --> E[PVE JSON]
    E --> F[Import to UE]
    F --> G[Add Details in UE]
```

**Steps**:
1. Create/load Grove tree (preset or custom)
2. Simulate growth to desired size
3. Export skeleton to PVE JSON
4. Import JSON into Unreal Engine
5. Add leaves/twigs in PVE editor
6. Configure materials and thickness
7. Generate final mesh in UE

**Tools**:
- `export_grove_to_pve.py`: CLI export
- `grove_to_pve_converter.py`: Python API

**See**: [GROVE_TO_UE_PVE.md](GROVE_TO_UE_PVE.md)

## Comparison Matrix

| Feature | PVE → Grove | Grove → PVE |
|---------|-------------|-------------|
| **Purpose** | Analyze/learn from UE | Export to UE |
| **Input** | PVE JSON | Grove instance |
| **Output** | Parameter hints | PVE JSON |
| **Geometry** | ❌ Can't extract | ✅ Skeleton only |
| **Parameters** | ✅ Extracted | ✅ Exported |
| **Leaves** | ❌ Not used | ❌ Add in UE |
| **Materials** | ❌ Not used | ❌ Add in UE |
| **Use Case** | Reference/inspiration | Production pipeline |

## Common Use Cases

### Use Case 1: Learning from UE Trees

**Goal**: Understand how UE created a specific tree look

```bash
# Analyze UE tree
./.conda/python.exe src/growpy/utils/unreal_pve_analyzer.py \
  ue_tree.json

# Convert to Grove hints
./.conda/python.exe src/growpy/utils/pve_to_grove_converter.py \
  ue_tree.json hints.json

# Create similar tree in Grove
# (manual process using hints)
```

### Use Case 2: Grove → UE Production Pipeline

**Goal**: Use Grove for tree generation, UE for rendering

```python
from growpy import create_grove
from growpy.utils.grove_to_pve_converter import export_grove_to_pve

# Generate tree in Grove
grove = create_grove("Oak")
grove.simulate(15)

# Export to UE
export_grove_to_pve(grove, "Oak", "oak_for_ue.json")

# Import in UE and finish there
```

### Use Case 3: Batch Forest Export

**Goal**: Generate forest in Grove, use in UE

```python
from growpy import create_forest, simulate_forest_growth
from growpy.utils.grove_to_pve_converter import export_grove_forest_to_pve
import pandas as pd

# Generate forest
forest_data = pd.DataFrame({
    'x': [0, 10, 20, 30],
    'y': [0, 5, 10, 15],
    'species': ['Oak', 'Beech', 'Fir', 'Oak'],
    'height': [15, 18, 20, 12]
})

forest = create_forest(forest_data)
simulate_forest_growth(forest, 12)

# Export all to PVE
export_grove_forest_to_pve(forest, "output/forest_ue")
```

### Use Case 4: Variation Generation

**Goal**: Create tree variations for UE asset library

```bash
# Generate multiple variants with different seeds
for seed in 1 2 3 4 5; do
  ./.conda/python.exe src/growpy/cli/export_grove_to_pve.py \
    --species "Birch" \
    --cycles 10 \
    --random-seed $seed \
    --output "output/birch_var_$seed.json"
done
```

## Integration Points

### Where Grove Excels

- Procedural tree structure generation
- Scientific growth simulation
- Parametric control
- Batch generation
- Reproducibility (seeds)

### Where UE PVE Excels

- Final rendering
- Material systems
- Wind animation
- Leaf instancing
- Performance optimization
- Level integration

### Optimal Workflow

```
Grove (structure) → PVE JSON → UE (finishing) → Game/Film
```

## Tools Summary

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `unreal_pve_analyzer.py` | Analyze PVE | JSON | Statistics |
| `pve_to_grove_converter.py` | Suggest params | PVE JSON | Grove hints |
| `grove_to_pve_converter.py` | Export skeleton | Grove | PVE JSON |
| `export_grove_to_pve.py` | CLI export | Species name | PVE JSON |

## Best Practices

### For PVE → Grove

1. Use PVE parameters as starting points, not final values
2. Manually tune Grove parameters for visual match
3. Save successful conversions as presets
4. Document parameter mapping discoveries

### For Grove → PVE

1. Simulate enough cycles for desired complexity
2. Use consistent random seeds for reproducibility
3. Export at appropriate growth stage
4. Document Grove parameters used
5. Plan post-processing steps in UE

## Future Enhancements

Potential improvements:

1. **Thickness Export**: Calculate and export branch pscale
2. **Leaf Positions**: Export twig attachment points
3. **Validation**: Check PVE compatibility before export
4. **Round-trip**: Improve PVE → Grove → PVE consistency
5. **Automation**: One-click Grove → UE pipeline

## References

- [PVE Integration Details](UNREAL_PVE_INTEGRATION.md)
- [Grove to PVE Guide](GROVE_TO_UE_PVE.md)
- [Sample Assets](../../data/SampleAssets/README.md)
- [GrowPy Main Docs](../../README.md)