# Grove to Unreal Engine PVE Export

## Overview

This guide explains how to export Grove-generated trees to Unreal Engine's Procedural Vegetation Editor (PVE) JSON format.

## What Gets Exported

### Grove → PVE Conversion

The converter extracts:

1. **Skeleton Structure**
   - Branch polylines (curves) as PVE primitives
   - 3D point positions for all skeleton nodes
   - Branch hierarchy information

2. **Global Attributes**
   - Growth cycles
   - Physical forces (gravity, phototropism)
   - Random seed
   - Branch generation limits

3. **PVE-Compatible JSON**
   - Standard PVE JSON structure
   - Compatible with UE5 import workflow

## Export Process

### Basic Export

```python
from growpy import create_grove
from growpy.utils.grove_to_pve_converter import export_grove_to_pve

# Create and simulate a Grove tree
grove = create_grove("European beech")
grove.simulate(flushes=10)

# Export to PVE JSON
export_grove_to_pve(
    grove=grove,
    species_name="European_Beech",
    output_path="output/beech_pve.json",
    grove_properties={
        'growth_cycles': 10,
        'gravity_force': 0.5,
        'phototropism': 0.4,
        'random_seed': 42
    }
)
```

### Command Line Export

```bash
# Export single species
./.conda/python.exe src/growpy/cli/export_grove_to_pve.py \
  --species "European beech" \
  --cycles 10 \
  --output output/beech_pve.json

# With custom parameters
./.conda/python.exe src/growpy/cli/export_grove_to_pve.py \
  --species "Hazel" \
  --cycles 8 \
  --gravity 1.3 \
  --phototropism 0.4 \
  --random-seed 42 \
  --output output/hazel_pve.json
```

### Batch Forest Export

```python
from growpy import create_forest, simulate_forest_growth
from growpy.utils.grove_to_pve_converter import export_grove_forest_to_pve
import pandas as pd

# Create forest data
forest_data = pd.DataFrame({
    'x': [0, 10, 20],
    'y': [0, 0, 0],
    'species': ['European beech', 'European oak', 'Silver fir'],
    'height': [15, 18, 20]
})

# Generate forest
forest = create_forest(forest_data)
simulate_forest_growth(forest, cycles=10)

# Export all trees
exported_files = export_grove_forest_to_pve(
    forest_data=forest,
    output_dir="output/forest_pve",
    grove_properties={'growth_cycles': 10}
)
```

## PVE JSON Structure

### Exported Data Format

```json
{
  "globalAttributes": {
    "cycle": {
      "type": "int",
      "size": 1,
      "isArray": false,
      "value": 10
    },
    "gravitationalForce": {
      "type": "float",
      "size": 1,
      "isArray": false,
      "value": 0.5
    },
    "randomSeed": {
      "type": "int",
      "size": 1,
      "isArray": false,
      "value": 42
    }
  },
  "points": {
    "attributes": {
      "P": { "type": "float", "size": 3, "isArray": true, "value": [] },
      "pscale": { "type": "float", "size": 1, "isArray": true, "value": [] },
      "generation": { "type": "int", "size": 1, "isArray": true, "value": [] }
    },
    "positions": [
      [0.0, 0.0, 0.0],
      [0.1, 0.0, 0.5],
      [0.2, 0.0, 1.0],
      ...
    ]
  },
  "primitives": {
    "attributes": {},
    "points": [
      [0, 1, 2, 3, 4, 5],      // Main trunk
      [6, 7, 8, 9],            // Branch 1
      [10, 11, 12, 13, 14],    // Branch 2
      ...
    ]
  }
}
```

### Data Mapping

| Grove Data | PVE JSON Location | Description |
|------------|-------------------|-------------|
| Skeleton points | `points.positions` | 3D coordinates of skeleton nodes |
| Skeleton polylines | `primitives.points` | Branch curves as point index lists |
| Growth cycles | `globalAttributes.cycle` | Number of growth iterations |
| Gravity force | `globalAttributes.gravitationalForce` | Branch droop amount |
| Random seed | `globalAttributes.randomSeed` | Seed for reproducibility |
| Max order | `globalAttributes.compoundMaxBranchGeneration` | Branch depth limit |

## Importing into Unreal Engine

### Method 1: Direct JSON Import (if supported)

1. Open Unreal Engine 5
2. Navigate to Content Browser
3. Right-click → Import
4. Select the exported JSON file
5. Configure import settings
6. Click Import

### Method 2: Via PVE Asset

1. Create new PVE asset in Unreal
2. Open the PVE editor
3. Use "Import" or "Load JSON" function
4. Select the Grove-exported JSON
5. Adjust materials and instances as needed

### Method 3: Python Script (Unreal Python API)

```python
# In Unreal Editor Python console
import unreal
import json

# Load JSON
with open("C:/path/to/beech_pve.json") as f:
    pve_data = json.load(f)

# Create PVE asset programmatically
# (Specific API calls depend on UE version)
```

## What to Expect

### What Works Well

✅ **Branch Structure**: Grove skeleton converts cleanly to PVE curves
✅ **Hierarchy**: Parent-child branch relationships preserved
✅ **Growth Parameters**: Basic growth settings transfer
✅ **Reproducibility**: Random seeds ensure consistent results

### Limitations

⚠️ **No Mesh Geometry**: Only skeleton is exported (PVE will need to rebuild mesh)
⚠️ **No Leaf Data**: Leaves/twigs must be added in Unreal
⚠️ **Simplified Attributes**: Most PVE point attributes are empty
⚠️ **Material Info**: No material/texture data exported
⚠️ **LOD Data**: No level-of-detail information

### Post-Import Steps in Unreal

After importing Grove skeleton to PVE:

1. **Add Leaf Instances**: Attach leaf/twig instances in PVE
2. **Configure Materials**: Set up bark and foliage materials
3. **Adjust Thickness**: Set branch thickness/radius values
4. **Add Detail**: Use PVE tools to add fine detail
5. **Generate Mesh**: Rebuild geometry with PVE meshing tools
6. **Test Wind**: Verify skeleton works with wind animation

## Advanced Usage

### Custom Point Attributes

To add custom attributes to the export:

```python
from growpy.utils.grove_to_pve_converter import GroveToPVEConverter

converter = GroveToPVEConverter(grove, "Species Name")
converter.convert()

# Add custom attributes
converter.pve_data['points']['attributes']['custom_attr'] = {
    'type': 'float',
    'size': 1,
    'isArray': True,
    'value': [1.0] * len(converter.pve_data['points']['positions'])
}

converter.save_json("output/custom.json")
```

### Multiple LOD Exports

Export different growth stages as LODs:

```python
from growpy import create_grove
from growpy.utils.grove_to_pve_converter import export_grove_to_pve

grove = create_grove("European beech")

# Export LOD0 (full detail)
grove.simulate(flushes=20)
export_grove_to_pve(grove, "Beech", "output/beech_lod0.json",
                   {'growth_cycles': 20})

# Export LOD1 (less detail)
grove = create_grove("European beech")  # Start fresh
grove.simulate(flushes=10)
export_grove_to_pve(grove, "Beech", "output/beech_lod1.json",
                   {'growth_cycles': 10})
```

## Comparison with UE PVE Exports

### Grove Export vs Native PVE

| Feature | Grove Export | Native PVE Export |
|---------|--------------|-------------------|
| Point count | Skeleton nodes only (~100-1000) | Full point cloud (~10k-100k+) |
| Attributes | Minimal (position, basic) | Comprehensive (40+ attributes) |
| Mesh data | No | Yes (baked) |
| Leaf data | No | Yes (integrated) |
| File size | Small (KB-MB) | Large (MB-GB) |
| Editability | High (skeleton only) | Low (baked result) |

### Use Cases

**Use Grove Export when:**
- You want a procedural skeleton for PVE to build on
- You need reproducible tree structures
- You want to use Grove's growth simulation + UE's rendering
- You need batch generation of similar trees

**Use Native PVE when:**
- You need complete tree definition
- You want to export finished trees
- You need all leaf/branch instance data
- You're sharing complete assets

## Troubleshooting

### "Not enough points" error in UE

Grove skeletons may have fewer points than PVE expects. Solutions:
- Increase growth cycles for more branches
- Subdivide skeleton in post-processing
- Add intermediate points along branches

### Branch thickness missing

Grove skeleton doesn't include thickness data. Solutions:
- Add `pscale` attribute manually
- Use PVE's thickness generation tools
- Set default thickness in PVE import settings

### No leaves appear

Leaves are not part of skeleton export. Solutions:
- Add leaf instances in PVE editor
- Use PVE's leaf generation tools
- Reference existing PVE leaf libraries

## Examples

See example exports in `output/pve_exports/` (after running examples):

```bash
# Generate example exports
./.conda/python.exe src/growpy/cli/export_grove_to_pve.py --species "Hazel" --cycles 8 --output output/pve_exports/hazel.json
./.conda/python.exe src/growpy/cli/export_grove_to_pve.py --species "European beech" --cycles 15 --output output/pve_exports/beech.json
```

## References

- [UE PVE Integration Guide](UNREAL_PVE_INTEGRATION.md)
- [Grove Documentation](https://www.thegrove3d.com)
- [Unreal Engine PVE Docs](https://docs.unrealengine.com/)

## Future Enhancements

Potential improvements:
1. **Point Attribute Generation**: Calculate branch thickness, age, etc.
2. **Leaf Position Export**: Export twig attachment points
3. **Material Data**: Export bark texture coordinates
4. **Optimization**: Simplify curves for performance
5. **Validation**: Check PVE compatibility before export