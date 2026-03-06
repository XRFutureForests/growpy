# PVE Preset Generation and Import Workflow

This guide explains how to generate PVE (Procedural Vegetation Editor) preset JSON files from GrowPy and import them into Unreal Engine's Procedural Vegetation Editor.

## Overview

The Procedural Vegetation Editor (PVE) in Unreal Engine allows parametric control over tree generation using JSON presets. GrowPy can export trees in the PVE preset format, enabling you to use GrowPy-generated trees as parametric vegetation in Unreal.

## Prerequisites

- Unreal Engine 5.x with Procedural Vegetation Editor plugin
- GrowPy environment activated (`conda activate the-grove`)
- Tree species configured in GrowPy

## Generating PVE Preset JSON Files

### Option 1: Generate from Forest Export (Default)

PVE preset JSON files are generated automatically during forest generation. No special flag is needed:

```bash
# Generate forest - PVE presets are included by default
python src/growpy/cli/generate_forest.py data/input/test.csv --quality high

# Custom CSV with custom output directory
python src/growpy/cli/generate_forest.py my_forest.csv --output-dir data/output/my_forest

# Skip PVE preset generation if not needed (saves ~3% export time)
python src/growpy/cli/generate_forest.py data/input/test.csv --skip-pve-json
```

Output structure (PVE JSON files are co-located with each tree):

```text
data/output/forest/
├── european_beech/
│   ├── tree_0001/
│   │   ├── european_beech.usda                       # Nanite assembly
│   │   ├── european_beech_0001_skeletal.usda          # Tree mesh with skeleton
│   │   ├── european_beech_0001_DynamicWind.json       # Wind animation data
│   │   ├── european_beech_0001.json                   # PVE preset JSON
│   │   └── twigs/                                     # Twig USD files
│   └── tree_0002/
│       └── ...
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
# Generate variations (PVE presets included by default)
python src/growpy/cli/generate_forest.py species_variations.csv --quality high
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

The generated JSON follows the Quixel Megaplants format with three main sections.

**For detailed attribute documentation, see [PVE Attribute Reference](pve-attribute-reference.md).**

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
    "plantProfile_1": {"isArray": true, "size": 1, "type": "float", "value": [0.85, 0.87, ...]},
    "plantProfile_2": {"isArray": true, "size": 1, "type": "float", "value": [0.82, 0.84, ...]},
    "plantProfile_3": {"isArray": true, "size": 1, "type": "float", "value": [0.88, 0.90, ...]},
    "plantProfile_4": {"isArray": true, "size": 1, "type": "float", "value": [0.81, 0.83, ...]},
    "plantProfile_5": {"isArray": true, "size": 1, "type": "float", "value": [0.86, 0.88, ...]},
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
- **plantProfile_1-5**: Radial crown envelope profiles (see detailed section below)

#### PlantProfile Arrays - Crown Envelope Definition

The `plantProfile_1` through `plantProfile_5` attributes define the radial crown envelope of the tree. These are critical for controlling tree shape and procedural foliage placement.

**Structure:**

- Each plantProfile is an array of exactly 100 float values
- Values typically range from 0.75 to 1.0 (normalized radii)
- The 100 values represent samples around a full 360° circle (3.6° per sample)
- Arrays are cyclic: the first value equals the last value for smooth wrapping

**What They Represent:**

- Each value defines the crown radius at a specific angle when viewed from above
- Think of it as a top-down outline of the tree's crown shape
- Value of 1.0 = maximum crown extent at that angle
- Value of 0.75 = 75% of maximum extent (creating indentations/irregularities)
- The variation creates natural, irregular crown shapes rather than perfect circles

**Example Profile Pattern:**

```json
"plantProfile_1": {
  "value": [
    0.8525,  // 0° (north)
    0.8631,  // 3.6°
    0.8738,  // 7.2°
    ...      // continues around circle
    0.9750,  // 352.8°
    0.8525   // 356.4° (back to start)
  ]
}
```

**How PVE Uses Multiple Profiles:**

- **5 profiles provide natural variation** between tree instances
- When spawning multiple trees, PVE randomly selects from profiles 1-5
- This creates diversity without needing separate preset files
- Each profile should have different irregularities for maximum variation

**Species-Specific Guidelines:**

*Broadleaf Trees* (Oak, Beech, Hazel, Maple):

- Use 5 varied profiles with values ranging 0.80-1.0
- Create irregular patterns mimicking natural crown asymmetry
- Include 10-15 local maxima per profile (simulating major branches)
- Variation should be gradual (avoid sharp peaks)

*Coniferous Trees* (Pine, Spruce, Fir):

- Use more uniform profiles with values 0.90-1.0
- Create smoother, more conical patterns
- Fewer local maxima (3-5 per profile)
- Lower branches can have smaller radii (tapering effect)

**Creating Custom Profiles:**

To generate biologically accurate profiles:

```python
import numpy as np
import json

def generate_crown_profile(num_major_branches=12, irregularity=0.15):
    """Generate a naturalistic crown profile with major branch lobes"""
    angles = np.linspace(0, 2*np.pi, 100)
    
    # Base circular shape
    profile = np.ones(100)
    
    # Add major branch lobes
    branch_angles = np.linspace(0, 2*np.pi, num_major_branches, endpoint=False)
    for branch_angle in branch_angles:
        # Gaussian lobe around each major branch
        lobe = irregularity * np.exp(-((angles - branch_angle)**2) / 0.5)
        profile += lobe
    
    # Add small-scale variation (minor branches, foliage clumps)
    noise = irregularity * 0.3 * np.random.randn(100)
    profile += noise
    
    # Normalize to 0.75-1.0 range
    profile = 0.75 + 0.25 * (profile - profile.min()) / (profile.max() - profile.min())
    
    # Ensure cyclic (first = last)
    profile[-1] = profile[0]
    
    return profile.tolist()

# Generate 5 variation profiles
profiles = {
    f"plantProfile_{i+1}": {
        "isArray": True,
        "size": 1,
        "type": "float",
        "value": generate_crown_profile(num_major_branches=np.random.randint(10, 15))
    }
    for i in range(5)
}

# Save to config
with open("data/assets/pve_configs/my_species_pve.json", "w") as f:
    json.dump({"plantProfile_overrides": profiles}, f, indent=2)
```

**Debugging Profiles:**

To visualize a profile:

```python
import matplotlib.pyplot as plt
import numpy as np
import json

# Load profile
with open("data/assets/pve_configs/european_beech_pve.json") as f:
    config = json.load(f)

profile = config["plantProfile_1"]["value"]

# Convert to polar coordinates
angles = np.linspace(0, 2*np.pi, len(profile))

# Plot
fig, ax = plt.subplots(subplot_kw=dict(projection='polar'))
ax.plot(angles, profile)
ax.fill(angles, profile, alpha=0.3)
ax.set_title("Crown Profile - Top View")
plt.savefig("crown_profile.png")
```

**Important Notes:**

- All 5 profiles are **required** for proper PVE preset functionality
- Missing profiles will cause import errors in Unreal Engine
- Profiles must have exactly 100 values (no more, no less)
- Values outside 0.5-1.2 range may cause rendering artifacts
- When in doubt, use reference profiles from Quixel Megaplants samples

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

### Enabling PVE Debug Mode (Exposing Hidden Properties)

The Procedural Vegetation Editor has internal development properties that are hidden by default. To import JSON presets and access advanced parameters, you need to enable debug mode.

**Using Console Variable (Recommended - No Recompilation Required):**

1. Open the Unreal Editor console (press `~` key)

2. Enable debug mode:

   ```text
   PV.DebugMode.Enabled 1
   ```

3. This immediately reveals all internal properties marked as `DevelopmentOnly` in the PVE preset asset

4. To hide properties again:

   ```text
   PV.DebugMode.Enabled 0
   ```

**How It Works:**

The `CVarEnablePVDebugMode` console variable is defined in `PVUtilities.cpp`:

```cpp
static TAutoConsoleVariable<bool> CVarEnablePVDebugMode(
    TEXT("PV.DebugMode.Enabled"),
    false,
    TEXT("Enables debug mode for the Procedural Vegetation Editor"), 
    FConsoleVariableDelegate::CreateLambda([](IConsoleVariable* ConsoleVariable)
    {
        UPVImporterSettings::StaticClass()->GetDefaultObject<UPVImporterSettings>()->bExposeToLibrary = ConsoleVariable->GetBool();
        UProceduralVegetationPreset::ShowHideInternalProperties(ConsoleVariable->GetBool());
    })
);
```

When you enable this console variable:

- It calls `ShowHideInternalProperties(true)` internally
- All `DevelopmentOnly` internal properties become visible in the Details panel
- No editor recompilation is required
- Changes take effect immediately via the dynamic delegate callback

**What Hidden Properties Are Exposed:**

With debug mode enabled, you can see and edit:

- `plantProfile_1` through `plantProfile_5` (crown envelope arrays)
- `maxBranchNumber` and `maxBudNumber` (growth limits)
- `compoundMaxBranchGeneration` and `compoundMaxBranchNumber` (compound leaf parameters)
- `photogrammetryTrunk` (photogrammetry flag)
- Deprecated scale parameters (`maxPscale`, `minPscale`, `max_curve_length`, `max_pscale`)
- Other internal PVE simulation parameters

**When to Use Debug Mode:**

Enable debug mode when:

- Importing JSON preset files that contain these hidden attributes
- Fine-tuning advanced tree generation parameters
- Debugging PVE preset behavior
- Comparing GrowPy-generated presets with Quixel references

Keep debug mode disabled for:

- Normal production workflows
- Preventing accidental modification of internal parameters
- Cleaner UI with only user-facing properties visible

**Persistent Configuration (Recommended):**

To keep debug mode enabled across editor sessions:

1. Locate `DefaultEditor.ini` in your project's `Config/` folder
   - Path: `<YourProject>/Config/DefaultEditor.ini`

2. Open the file in a text editor

3. Scroll to the **very bottom** of the file

4. Add these two lines at the end:

   ```ini
   [ConsoleVariables]
   PV.DebugMode.Enabled=1
   ```

5. Save the file and restart Unreal Editor

**Important**: Add these lines at the bottom, after all existing content (after the `[/Script/AdvancedPreviewScene.SharedProfiles]` section with all the `+Profiles=(...)` entries).

### Required Folder Structure in Unreal

PVE presets must follow this structure in your Unreal project:

```text
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

```text
Right-click in Content Browser > New Folder > "Tree_European_Beech"
```

Inside the species folder, create:

- `Instances/` folder for JSON presets
- `Materials/` folder for PBR materials
- `Textures/` folder for texture assets

#### 2. Import JSON Presets

Copy generated JSON files into the `Instances/` folder. PVE preset JSON files are located in each tree's output folder:

```bash
# From Windows Explorer:
# 1. Navigate to data/output/forest/european_beech/
# 2. Find .json PVE preset files in each tree_XXXX/ subfolder
# 3. Copy PVE preset .json files (not DynamicWind.json) into Content/Trees/Tree_European_Beech/Instances/
```

Or use a script to automate:

```python
# Copy PVE JSONs to Unreal project
import shutil
from pathlib import Path

source = Path("data/output/forest/european_beech")
dest = Path("C:/UnrealProjects/MyProject/Content/Trees/Tree_European_Beech/Instances")

dest.mkdir(parents=True, exist_ok=True)
for tree_dir in sorted(source.glob("tree_*")):
    for json_file in tree_dir.glob("*.json"):
        if "DynamicWind" not in json_file.name:
            shutil.copy(json_file, dest / json_file.name)
```

#### 3. Import Skeletal Meshes

Import the USD skeletal meshes generated by GrowPy:

1. In Content Browser, navigate to species folder
2. Right-click > Import to /Game/Trees/Tree_European_Beech/
3. Select the Nanite assembly USD files from each tree folder:
   - `european_beech/tree_0001/european_beech.usda`
   - `european_beech/tree_0002/european_beech.usda`
   - etc.

4. USD Import Settings:
   - Import Geometry: Checked
   - Import Skeletal Animations: Checked
   - Import Materials: Checked (if using static assemblies)
   - Create Physics Asset: Checked

#### 4. Create PVE Data Asset

In the species folder:

1. Right-click > **Procedural Vegetation > Procedural Vegetation Preset**
2. Name it `PVE_EuropeanBeech_Data`
3. Double-click to open

In the Details panel, the **Internal** category is visible (requires debug mode enabled in step above):

| Property | Value | Notes |
| --- | --- | --- |
| **JsonDirectoryPath** | `./Instances` | Folder containing PVE JSON files |
| **bOverrideFolderPaths** | checked | Must be enabled |
| **FoliageFolder** | `./SkeletalMeshes` | Where foliage meshes were imported |
| **MaterialsFolder** | `./Materials` | Where materials were imported |
| **TrunkMaterialName** | `MI_EuropeanBeech_Bark` | Base name only, no path or extension |
| **bCreateProfileDataAsset** | unchecked | Leave unchecked unless needed |

Click **"Update Data Asset"** and verify the Output Log shows:

```text
LogProceduralVegetation: Loaded variant : european_beech_tree_0000
LogProceduralVegetation: Loaded variant : european_beech_tree_0001
```

The **Preset Data** category should now show the loaded variants.

#### 5. Create PVE Asset

1. Right-click > **Procedural Vegetation > Procedural Vegetation**
2. Name it `PVE_European_Beech`
3. Open the asset and in Details panel:
   - **Data Asset**: Select `PVE_EuropeanBeech_Data`
   - **Preset Loader**: Will auto-populate from Instances folder

#### 6. Configure PVE Preset Loader Node

In the PVE graph:

1. Add **PVE Preset Loader** node and connect to output
2. Configure:
   - **Preset Path**: Select JSON from Instances folder
   - **Skeletal Mesh**: Choose variation (SK_Species_01, etc.)
   - **Random Seed**: For variation

#### 7. Test in Level

1. Drag `PVE_European_Beech` from Content Browser to viewport
2. Adjust parameters in Details panel and click **Generate**

## Using PVE Presets with PCG (Procedural Content Generation)

PVE presets integrate with Unreal's PCG system for landscape-scale forests:

```text
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
# Generate multi-species forest (PVE JSON included by default)
python src/growpy/cli/generate_forest.py forest.csv \
  --quality high \
  --growth-cycle-limit 12 \
  --output-dir data/output/forest
```

### 2. Organize Unreal Project

Create folder structure in Content Browser:

```text
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
# Copy PVE JSONs from each tree folder
cp data/output/forest/european_beech/tree_*/european_beech_*.json \
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

### JSON Import Shows Missing Properties

- **Solution**: Enable PVE Debug Mode using console command `PV.DebugMode.Enabled 1`
- Hidden properties like `plantProfile_1-5` are only visible with debug mode enabled
- See "Enabling PVE Debug Mode" section above for details

### JSON Not Recognized

- Check file location: Must be in `Instances/` subfolder
- Verify JSON structure: Compare with reference Megaplants preset
- File extension: Must be `.json`
- Enable debug mode to expose import functionality

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

- `src/growpy/cli/generate_forest.py` (PVE JSON generated by default, skip with `--skip-pve-json`)

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

- [PVE Attribute Reference](pve-attribute-reference.md) - Detailed explanation of all PVE attributes (maxBranchNumber, compound leaves, pscale, etc.)
- [Grove Preset Reference](grove-preset-reference.md) - Grove 2.3 preset parameter reference
- [GrowPy Functional Description](growpy-functional-description.md) - Complete package architecture and data flow
- [CLI Reference](cli-reference.md) - Complete command reference
