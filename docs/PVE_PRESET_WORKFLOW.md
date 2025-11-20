# PVE Preset Generation and Import Workflow

This guide explains how to generate PVE (Procedural Vegetation Editor) preset JSON files from GrowPy and import them into Unreal Engine's Procedural Vegetation Editor.

## Overview

The Procedural Vegetation Editor (PVE) in Unreal Engine allows parametric control over tree generation using JSON presets. GrowPy can export trees in the PVE preset format, enabling you to use GrowPy-generated trees as parametric vegetation in Unreal.

## Prerequisites

- Unreal Engine 5.x with Procedural Vegetation Editor plugin
- GrowPy environment activated (`conda activate the-grove`)
- Tree species configured in GrowPy

## Generating PVE Preset JSON Files

### Option 1: Generate from Forest Export

Generate PVE presets alongside tree exports:

```bash
# Generate forest with PVE presets
python src/growpy/cli/generate_forest.py --generate-pve-json --quality high

# Custom CSV with PVE presets
python src/growpy/cli/generate_forest.py my_forest.csv --generate-pve-json --output-dir data/output/my_forest
```

Output structure:

```
data/output/forest/
├── european_beech/
│   ├── european_beech_tree_0000_skeletal_nanite_assembly.usda
│   ├── european_beech_tree_0000_static_nanite_assembly.usda
│   └── ...
├── scots_pine/
│   └── ...
└── pve_presets/
    ├── european_beech/
    │   ├── european_beech_tree_0000.json
    │   ├── european_beech_tree_0001.json
    │   └── ...
    └── scots_pine/
        └── ...
```

### Option 2: Generate Variations for a Single Species

Create a simple CSV with variations of one species:

```csv
x,y,species,height
0,0,European Beech,18
1,0,European Beech,20
2,0,European Beech,22
3,0,European Beech,19
4,0,European Beech,21
```

Then generate:

```bash
# Generate variations with PVE presets
python src/growpy/cli/generate_forest.py species_variations.csv --generate-pve-json --quality high
```

### Option 3: Programmatic Generation

Use the Python API directly for custom workflows:

```python
from pathlib import Path
from growpy.io.pve_preset_json import generate_pve_preset_for_species

# Generate 5 variations of European Beech
generated = generate_pve_preset_for_species(
    species_name="European Beech",
    output_dir=Path("data/output/pve_presets/european_beech"),
    num_variations=5,
    growth_cycles=12,
    resolution=24,
)
```

## PVE Preset JSON Structure

The generated JSON follows the Quixel Megaplants format with three main sections:

### 1. globalAttributes

Growth simulation parameters that control tree behavior:

```json
{
  "globalAttributes": {
    "cycle": {"isArray": false, "size": 1, "type": "int", "value": 12},
    "cycleTime": {"isArray": false, "size": 1, "type": "float", "value": 1.25},
    "phototropism": {"isArray": true, "size": 1, "type": "float", "value": [0.5, 0.0, 1.0, ...]},
    "phyllotaxy": {"isArray": true, "size": 1, "type": "float", "value": [137.5, 0.0, ...]},
    "gravitationalForce": {"isArray": false, "size": 1, "type": "float", "value": 2.0},
    ...
  }
}
```

Key parameters:

- **cycle**: Number of growth iterations
- **cycleTime**: Time per growth cycle
- **phototropism**: Light-seeking behavior curve
- **phyllotaxy**: Branching angle patterns
- **gravitationalForce**: Branch drooping strength

### 2. points

Point cloud data with botanical attributes:

```json
{
  "points": {
    "attributes": {
      "pscale": {"isArray": false, "size": 1, "type": "float", "values": [...]},
      "generation": {"isArray": false, "size": 1, "type": "int", "values": [...]},
      "branchGradient": {"isArray": false, "size": 1, "type": "float", "values": [...]},
      ...
    },
    "positions": [[0.0, 0.0, 0.0], [0.99, 1.99, 1.0], ...]
  }
}
```

Attributes:

- **positions**: 3D coordinates of branch points
- **pscale**: Thickness at each point
- **generation**: Hierarchy level (trunk=0, main branches=1, etc.)
- **branchGradient**: Position along branch (0=base, 1=tip)

### 3. primitives

Branch connectivity defining tree structure:

```json
{
  "primitives": {
    "attributes": {
      "branchNumber": {"isArray": false, "size": 1, "type": "int", "values": [...]},
      "branchGeneration": {"isArray": false, "size": 1, "type": "int", "values": [...]},
      "branchParentNumber": {"isArray": false, "size": 1, "type": "int", "values": [...]}
    },
    "points": [[0, 1, 2, 3, ...], [1, 10, 11, 12], ...]
  }
}
```

## Importing to Unreal Engine

### Required Folder Structure in Unreal

PVE presets must follow this structure in your Unreal project:

```
Content/
└── Trees/
    └── Tree_Species_Name/
        ├── PVE_Species_Name.uasset              # Main PVE asset
        ├── PVE_Species_Data.uasset              # PVE data asset
        ├── SK_Species_01.uasset                 # Skeletal mesh instance 1
        ├── SK_Species_01_Skeleton.uasset
        ├── SK_Species_01_Physics.uasset
        ├── SK_Species_02.uasset                 # Additional variations
        ├── SK_Species_02_Skeleton.uasset
        ├── SK_Species_02_Physics.uasset
        ├── Instances/
        │   ├── Species_01.json                  # PVE preset JSON
        │   ├── Species_02.json
        │   └── ...
        ├── Materials/
        │   ├── M_Bark.uasset
        │   ├── M_Leaves.uasset
        │   └── ...
        └── Textures/
            ├── T_Bark_D.uasset
            ├── T_Bark_N.uasset
            ├── T_Leaves_D.uasset
            └── ...
```

### Step-by-Step Import Process

#### 1. Prepare Folder Structure

Create the species folder in Content Browser:

```
Right-click in Content Browser > New Folder > "Tree_European_Beech"
```

Inside the species folder, create:

- `Instances/` folder for JSON presets
- `Materials/` folder for PBR materials
- `Textures/` folder for texture assets

#### 2. Import JSON Presets

Copy generated JSON files into the `Instances/` folder:

```bash
# From Windows Explorer:
# 1. Navigate to data/output/forest/pve_presets/european_beech/
# 2. Copy all .json files
# 3. Paste into Content/Trees/Tree_European_Beech/Instances/
```

Or use a script to automate:

```python
# Copy PVE JSONs to Unreal project
import shutil
from pathlib import Path

source = Path("data/output/forest/pve_presets/european_beech")
dest = Path("C:/UnrealProjects/MyProject/Content/Trees/Tree_European_Beech/Instances")

dest.mkdir(parents=True, exist_ok=True)
for json_file in source.glob("*.json"):
    shutil.copy(json_file, dest / json_file.name)
```

#### 3. Import Skeletal Meshes

Import the USD skeletal meshes generated by GrowPy:

1. In Content Browser, navigate to species folder
2. Right-click > Import to /Game/Trees/Tree_European_Beech/
3. Select the skeletal Nanite assembly USD files:
   - `european_beech_tree_0000_skeletal_nanite_assembly.usda`
   - `european_beech_tree_0001_skeletal_nanite_assembly.usda`
   - etc.

4. USD Import Settings:
   - Import Geometry: Checked
   - Import Skeletal Animations: Checked
   - Import Materials: Checked (if using static assemblies)
   - Create Physics Asset: Checked

#### 4. Create PVE Data Asset

In the species folder:

1. Right-click > Procedural Vegetation > Procedural Vegetation Data
2. Name it `PVE_EuropeanBeech_Data`
3. Open and configure:
   - **Preset Directory**: Point to `Instances/` folder
   - **Skeletal Meshes**: Add imported SK_Species_XX assets
   - **Materials**: Assign bark and leaf materials

#### 5. Create PVE Asset

1. Right-click > Procedural Vegetation > Procedural Vegetation
2. Name it `PVE_European_Beech`
3. Open the asset
4. In Details panel:
   - **Data Asset**: Select `PVE_EuropeanBeech_Data`
   - **Preset Loader**: Will auto-populate from Instances folder

#### 6. Configure PVE Preset Loader Node

In the PVE graph:

1. Add **PVE Preset Loader** node
2. Connect to output
3. Configure:
   - **Preset Path**: Select JSON from Instances folder
   - **Skeletal Mesh**: Choose variation (SK_Species_01, etc.)
   - **Random Seed**: For variation

#### 7. Test in Level

Place PVE asset in level:

1. Drag `PVE_European_Beech` from Content Browser to viewport
2. Adjust parameters in Details panel
3. Click **Generate** to create tree

## Using PVE Presets with PCG (Procedural Content Generation)

PVE presets integrate with Unreal's PCG system for landscape-scale forests:

```
1. Create PCG Graph
2. Add PCG Spawn Actor node
3. Set Actor Class to PVE asset
4. Connect to PCG inputs (density, distribution, etc.)
5. Generate forest
```

## Customizing PVE Parameters

After import, you can adjust tree behavior by modifying preset parameters:

### In PVE Editor

1. Open PVE asset
2. Select Preset Loader node
3. Adjust parameters in Details panel:
   - **Growth Cycles**: More cycles = larger trees
   - **Branch Density**: Controls branching frequency
   - **Phototropism**: Light-seeking behavior
   - **Gravitational Force**: Branch drooping

### Editing JSON Directly

For batch modifications, edit JSON files:

```python
import json

# Load preset
with open("Instances/european_beech_tree_0000.json", "r") as f:
    preset = json.load(f)

# Modify parameters
preset["globalAttributes"]["cycle"]["value"] = 15  # More growth cycles
preset["globalAttributes"]["gravitationalForce"]["value"] = 1.5  # Less droop

# Save
with open("Instances/european_beech_tree_0000.json", "w") as f:
    json.dump(preset, f, indent=2)
```

## Complete Example Workflow

### 1. Generate Forest with PVE Presets

```bash
# Generate multi-species forest with PVE JSON
python src/growpy/cli/generate_forest.py forest.csv \
  --generate-pve-json \
  --quality high \
  --growth-cycle-limit 12 \
  --output-dir data/output/forest
```

### 2. Organize Unreal Project

Create folder structure in Content Browser:

```
Content/
└── GrowPy/
    └── Trees/
        ├── Tree_European_Beech/
        │   ├── Instances/
        │   ├── Materials/
        │   └── Textures/
        └── Tree_Scots_Pine/
            ├── Instances/
            ├── Materials/
            └── Textures/
```

### 3. Copy Files

```bash
# Copy PVE JSONs
cp data/output/forest/pve_presets/european_beech/*.json \
   "C:/UnrealProjects/MyProject/Content/GrowPy/Trees/Tree_European_Beech/Instances/"

# USD meshes imported via Content Browser import dialog
```

### 4. Create PVE Assets

For each species:

1. Create PVE Data Asset
2. Create PVE Asset
3. Link skeletal meshes and presets
4. Test in level

### 5. Build PCG Forest

1. Create PCG Graph
2. Add PVE Spawn nodes for each species
3. Configure distribution (Poisson, random, etc.)
4. Generate landscape-scale forest

## Troubleshooting

### JSON Not Recognized

- Check file location: Must be in `Instances/` subfolder
- Verify JSON structure: Compare with reference Megaplants preset
- File extension: Must be `.json`

### Skeletal Mesh Import Fails

- Ensure USD Importer plugin is enabled
- Check USD file is skeletal (not static)
- Verify skeleton hierarchy matches PVE expectations

### Tree Doesn't Generate

- Check PVE Data Asset has presets and meshes assigned
- Verify Preset Loader node is connected
- Ensure `cycle` value in JSON is reasonable (8-15)

### Performance Issues

- Use LOD system for distant trees
- Reduce `cycle` count in presets
- Use lower quality presets for background vegetation
- Enable Nanite for skeletal meshes in project settings

## Reference Files

Example PVE preset from Quixel:

- `data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json`

GrowPy PVE module:

- `src/growpy/io/pve_preset_json.py`

CLI tools:

- `src/growpy/cli/generate_pve_preset.py`
- `src/growpy/cli/generate_forest.py`

## Advanced Topics

### Batch Preset Generation

Generate presets for all species:

```python
from pathlib import Path
from growpy import get_config

config = get_config()
output_dir = Path("data/output/pve_presets")

for species in config.list_species():
    print(f"Generating presets for {species}")
    # Generate 3 variations per species
    from growpy.io.pve_preset_json import generate_pve_preset_for_species
    generate_pve_preset_for_species(
        species_name=species,
        output_dir=output_dir / species.replace(" ", "_").lower(),
        num_variations=3,
        growth_cycles=12
    )
```

### Seasonal Variations

Create multiple presets with different leaf states:

```python
# Spring - young leaves
preset["globalAttributes"]["leafGrowth"]["value"][0] = 0.5

# Summer - full foliage
preset["globalAttributes"]["leafGrowth"]["value"][0] = 1.0

# Fall - senescence
preset["globalAttributes"]["abscissionSenescense"]["value"][0] = 0.8
```

### Wind Animation Integration

PVE presets can work with Dynamic Wind in Unreal:

1. Import skeletal mesh with wind animation
2. Enable wind in PVE Data Asset
3. Wind parameters controlled via skeleton hierarchy
4. Wind curve data stored in JSON (future feature)

## Best Practices

1. **Organize by Species**: Keep one species per folder
2. **Use Variations**: Generate 3-5 variations per species for diversity
3. **Quality Tiers**: High quality for hero trees, medium for mid-ground, low for background
4. **Material Sharing**: Reuse materials across variations within species
5. **LOD Strategy**: Use PVE LOD system for performance
6. **Version Control**: Track JSON presets in source control for reproducibility
7. **Naming Convention**: Use consistent naming (Species_XX.json)

## See Also

- [PVE Direct from Grove](PVE_DIRECT_FROM_GROVE.md) - Technical implementation details
- [Nanite Assembly Export](NANITE_CLEAN_EXPORT.md) - USD export workflow
- [CLI Reference](archive/cli-reference.md) - Complete command reference
