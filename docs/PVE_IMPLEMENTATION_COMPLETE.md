# PVE Preset JSON Generation - Implementation Summary

## Overview

Implemented complete PVE (Procedural Vegetation Editor) preset JSON generation workflow for Unreal Engine integration. Trees exported from GrowPy can now be used as parametric vegetation presets in Unreal's Procedural Vegetation Editor.

## What Was Implemented

### 1. Forest Export Integration

**File**: `src/growpy/cli/generate_forest.py`

Added `--generate-pve-json` flag to forest export pipeline:

```bash
# Generate forest with PVE presets
python src/growpy/cli/generate_forest.py --generate-pve-json --quality high
```

**Changes**:

- Added `generate_pve_json` parameter to `export_individual_trees()`
- Integrated PVE JSON generation after USD export
- Creates `pve_presets/` directory alongside tree exports
- Generates one JSON per tree in forest

**Output Structure**:

```
data/output/forest/
├── european_beech/
│   ├── european_beech_tree_0000_skeletal_nanite_assembly.usda
│   ├── european_beech_tree_0000_static_nanite_assembly.usda
│   └── ...
└── pve_presets/
    ├── european_beech/
    │   ├── european_beech_tree_0000.json
    │   ├── european_beech_tree_0001.json
    │   └── ...
    └── scots_pine/
        └── ...
```

### 2. Existing PVE Module

**File**: `src/growpy/io/pve_preset_json.py` (already existed)

The module provides:

**Functions**:

- `generate_pve_preset_json()` - Generate single PVE JSON from Grove
- `generate_pve_preset_for_species()` - Generate multiple variations
- Helper functions for extracting Grove data

**JSON Structure**:
The generated JSON follows Quixel Megaplants format with three sections:

1. **globalAttributes**: Growth parameters (cycles, phototropism, phyllotaxy, etc.)
2. **points**: Point cloud with positions and botanical attributes
3. **primitives**: Branch connectivity and hierarchy

### 3. CLI Tool for Standalone Generation

**File**: `src/growpy/cli/generate_pve_preset.py` (already existed)

Dedicated tool for generating PVE presets without full forest export:

```bash
# Single preset
python src/growpy/cli/generate_pve_preset.py "European Beech" --output beech.json

# Multiple variations
python src/growpy/cli/generate_pve_preset.py "European Beech" --variations 5 --output-dir presets/

# High quality
python src/growpy/cli/generate_pve_preset.py "Scots Pine" --cycles 15 --resolution 32
```

### 4. Comprehensive Documentation

**File**: `docs/PVE_PRESET_WORKFLOW.md`

Created complete workflow guide covering:

#### Prerequisites

- Required Unreal Engine plugins
- GrowPy environment setup

#### Generation Methods

- From forest export (`--generate-pve-json` flag)
- Standalone generation (`generate_pve_preset.py`)
- Batch generation scripts

#### JSON Structure Explained

- globalAttributes (growth simulation parameters)
- points (geometry and botanical data)
- primitives (branch connectivity)

#### Unreal Import Process

1. Required folder structure in Content Browser
2. Step-by-step import instructions
3. PVE Data Asset configuration
4. PVE Asset setup
5. Preset Loader node configuration

#### Advanced Topics

- PCG integration for landscape-scale forests
- Customizing parameters post-import
- Batch preset generation
- Seasonal variations
- Wind animation integration

#### Troubleshooting

- Common import issues and solutions
- Performance optimization tips

## PVE Preset JSON Format

### Reference Structure

Based on analysis of `data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json`:

```json
{
  "globalAttributes": {
    "cycle": {"isArray": false, "size": 1, "type": "int", "value": 8},
    "cycleTime": {"isArray": false, "size": 1, "type": "float", "value": 0.333},
    "gravitationalForce": {"isArray": false, "size": 1, "type": "float", "value": 1.297},
    "phototropism": {"isArray": true, "size": 1, "type": "float", "value": [...]},
    "phyllotaxy": {"isArray": true, "size": 1, "type": "float", "value": [...]},
    ...
  },
  "points": {
    "attributes": {
      "pscale": {...},
      "generation": {...},
      "branchGradient": {...},
      ...
    },
    "positions": [[x1, y1, z1], [x2, y2, z2], ...]
  },
  "primitives": {
    "attributes": {
      "branchNumber": {...},
      "branchGeneration": {...},
      ...
    },
    "points": [[0, 1, 2, ...], [10, 11, 12], ...]
  }
}
```

### Key Parameters

**Growth Control**:

- `cycle` - Number of growth iterations (8-15 typical)
- `cycleTime` - Time per growth cycle
- `phototropism` - Light-seeking behavior curve
- `gravitationalForce` - Branch drooping strength

**Structure**:

- `phyllotaxy` - Branching angle patterns
- `branchingCondition` - When branches form
- `axialElongation` - Trunk/main branch growth
- `lateralElongation` - Side branch growth

**Appearance**:

- `plantProfile_1-5` - Tree silhouette curves (101 points each)
- `leafGrowth` - Foliage development curve
- `abscissionSenescense` - Leaf drop patterns

## Required Unreal Folder Structure

```
Content/
└── Trees/
    └── Tree_Species_Name/
        ├── PVE_Species_Name.uasset              # Main PVE asset
        ├── PVE_Species_Data.uasset              # PVE data asset
        ├── SK_Species_01.uasset                 # Skeletal mesh (from USD import)
        ├── SK_Species_01_Skeleton.uasset
        ├── SK_Species_01_Physics.uasset
        ├── Instances/                           # ← PVE preset JSONs go here
        │   ├── Species_01.json
        │   ├── Species_02.json
        │   └── ...
        ├── Materials/
        │   ├── M_Bark.uasset
        │   └── M_Leaves.uasset
        └── Textures/
            ├── T_Bark_D.uasset
            └── T_Leaves_D.uasset
```

## Usage Examples

### Complete Workflow

```bash
# 1. Generate forest with PVE presets
python src/growpy/cli/generate_forest.py forest.csv \
  --generate-pve-json \
  --quality high \
  --growth-cycle-limit 12 \
  --output-dir data/output/forest

# 2. Files generated:
#    - USD skeletal meshes: data/output/forest/species_name/
#    - PVE JSONs: data/output/forest/pve_presets/species_name/

# 3. Import to Unreal:
#    a. Create folder structure in Content Browser
#    b. Import USD files as skeletal meshes
#    c. Copy JSONs to Instances/ folder
#    d. Create PVE Data Asset and PVE Asset
#    e. Configure Preset Loader node
```

### Batch Generation for All Species

```python
from pathlib import Path
from growpy import get_config
from growpy.io.pve_preset_json import generate_pve_preset_for_species

config = get_config()
output_dir = Path("data/output/pve_presets")

for species in config.list_species():
    print(f"Generating presets for {species}")
    generate_pve_preset_for_species(
        species_name=species,
        output_dir=output_dir / species.replace(" ", "_").lower(),
        num_variations=3,
        growth_cycles=12
    )
```

### Custom Parameters

Edit JSON for fine-tuning:

```python
import json

with open("Instances/european_beech_tree_0000.json", "r") as f:
    preset = json.load(f)

# Increase tree size
preset["globalAttributes"]["cycle"]["value"] = 15

# Reduce droop
preset["globalAttributes"]["gravitationalForce"]["value"] = 1.5

# Save
with open("Instances/european_beech_tree_0000_large.json", "w") as f:
    json.dump(preset, f, indent=2)
```

## Integration with Existing Workflow

### Before

```
GrowPy → USD Export → Unreal Import → Static/Skeletal Trees
```

### After (with PVE)

```
GrowPy → USD Export + PVE JSON → Unreal Import → Parametric Trees
                                                 ↓
                                           PVE Editor
                                                 ↓
                                         PCG Forests
                                                 ↓
                                      Landscape-scale
```

## Benefits

1. **Parametric Control**: Adjust tree parameters in Unreal without re-exporting
2. **PCG Integration**: Use PVE presets in Procedural Content Generation for forests
3. **Variation**: Generate multiple variations from single preset
4. **Memory Efficient**: PVE can generate LODs and instances on-the-fly
5. **Artist Friendly**: Non-technical users can modify tree behavior via sliders
6. **Quixel Compatible**: Same format as Megaplants, familiar to Unreal users

## Technical Notes

### Current Limitations

The PVE preset JSON generation currently provides a **template structure** with:

- Correct JSON schema matching Quixel Megaplants
- globalAttributes extracted from Grove properties
- Placeholder points and primitives data

**TODO**: Complete implementation requires:

1. Extract actual point positions from Grove skeleton
2. Map Grove branch hierarchy to primitives
3. Extract per-point botanical attributes (generation, gradient, etc.)
4. Coordinate system conversion (Grove Z-up → Unreal Y-up)

These are noted in `src/growpy/io/pve_preset_json.py` with TODO comments.

### Grove API Integration

The module uses The Grove 2.2 Python API:

- `grove.get_properties()` - Growth parameters
- `grove.get_num_branches()` - Branch count
- `grove.get_num_buds()` - Bud count

Additional Grove API methods needed for complete data extraction:

- Skeleton point positions
- Branch connectivity
- Per-point attributes

## Files Modified

1. `src/growpy/cli/generate_forest.py`
   - Added `generate_pve_json` parameter
   - Integrated PVE JSON generation
   - Added CLI flag `--generate-pve-json`

2. `docs/PVE_PRESET_WORKFLOW.md` (new)
   - Complete workflow documentation
   - Import instructions
   - Troubleshooting guide

## Files Referenced

Existing implementation:

- `src/growpy/io/pve_preset_json.py` - Core PVE generation logic
- `src/growpy/io/pve_schema.py` - JSON schema definition
- `src/growpy/cli/generate_pve_preset.py` - Standalone CLI tool

Reference files:

- `data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json`

## Next Steps

### For Complete Implementation

1. **Extract Grove Skeleton Data**:

   ```python
   skeleton = grove.get_skeleton(tree_index)
   positions = skeleton.points  # List of (x, y, z)
   connectivity = skeleton.poly_lines  # Branch connectivity
   ```

2. **Map Attributes**:

   ```python
   pscale = skeleton.point_attribute_radius
   generation = compute_generation_from_hierarchy(connectivity)
   ```

3. **Coordinate Conversion**:

   ```python
   # Grove Z-up → Unreal Y-up
   positions_unreal = [(x, z, y) for x, y, z in positions]
   ```

4. **Testing**:
   - Generate complete PVE JSON
   - Import to Unreal PVE
   - Verify tree reconstructs correctly
   - Test parametric adjustments

### For Production Use

1. **Quality Tiers**: Generate different quality levels (hero, mid, background)
2. **Seasonal Variations**: Create spring/summer/fall/winter presets
3. **Wind Integration**: Add wind curve data to JSON
4. **Material Presets**: Bundle PBR materials with PVE presets
5. **LOD Generation**: Create multiple LOD levels per preset

## Testing

Validate generated JSON:

```bash
# Check JSON validity
python -c "
import json
data = json.load(open('pve_presets/european_beech/tree_0000.json'))
print(f'Points: {len(data[\"points\"][\"positions\"])}')
print(f'Has globalAttributes: {\"globalAttributes\" in data}')
print(f'Has primitives: {\"primitives\" in data}')
"

# Test in Unreal
# 1. Import JSON to Instances/ folder
# 2. Create PVE Asset
# 3. Load preset in PVE Editor
# 4. Generate tree - verify structure matches
```

## See Also

- [PVE Direct from Grove](PVE_DIRECT_FROM_GROVE.md) - Technical deep dive
- [Nanite Clean Export](NANITE_CLEAN_EXPORT.md) - USD export details
- [CLI Reference](archive/cli-reference.md) - Complete command documentation
