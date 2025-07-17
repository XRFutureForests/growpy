# Data Organization Structure

The project now uses a clear and organized directory structure that separates input data from outputs and groups all output files by input source and file type.

## Directory Structure

```
data/
├── input/                           # All input files
│   └── demo_forest.csv             # Main input file (x, y, z, species, height)
└── output/                         # All output files organized by input name
    └── demo_forest/                # Output folder matching input file name
        ├── analysis/               # Analysis and intermediate files
        │   ├── demo_forest_with_predicted_age.csv
        │   ├── height_curves.csv
        │   ├── height_curves.png
        │   └── height_to_age_models.pkl
        ├── groves/                 # Grove JSON files for Blender
        │   ├── Fagaceae___Beech_grove.json
        │   ├── Fagaceae___European_oak_grove.json
        │   ├── Pinaceae___Fir_grove.json
        │   ├── Pinaceae___Grand_fir_grove.json
        │   └── Pinaceae___Scots_pine_grove.json
        ├── tree_models/            # Individual tree models by species
        │   ├── Fagaceae___Beech/
        │   │   ├── Fagaceae___Beech_tree_000_LOD0_Ultra.usd
        │   │   ├── Fagaceae___Beech_tree_000_LOD1_High.usd
        │   │   ├── Fagaceae___Beech_tree_000_LOD2_Medium.usd
        │   │   ├── Fagaceae___Beech_tree_000_LOD3_Low.usd
        │   │   ├── Fagaceae___Beech_tree_000_LOD4_VeryLow.usd
        │   │   ├── Fagaceae___Beech_tree_000_LOD5_Minimal.usd
        │   │   └── Fagaceae___Beech_Models.fbx            # FBX files alongside USD
        │   ├── Fagaceae___European_oak/
        │   │   ├── [USD LOD files for European oak]
        │   │   └── Fagaceae___European_oak_Models.fbx
        │   ├── Pinaceae___Fir/
        │   │   ├── [USD LOD files for Fir]
        │   │   └── Pinaceae___Fir_Models.fbx
        │   ├── Pinaceae___Grand_fir/
        │   │   ├── [USD LOD files for Grand fir]
        │   │   └── Pinaceae___Grand_fir_Models.fbx
        │   └── Pinaceae___Scots_pine/
        │       ├── [USD LOD files for Scots pine]
        │       └── Pinaceae___Scots_pine_Models.fbx
```

## Benefits of This Organization

### 1. **Clear Input/Output Separation**

- All input files are in `data/input/`
- All outputs are organized under `data/output/`

### 2. **Input-Specific Output Folders**

- Each input file gets its own output folder (e.g., `demo_forest/`)
- Multiple input files can be processed without conflicts
- Easy to track which outputs came from which input

### 3. **Organized by File Type and Purpose**

- `analysis/` - Intermediate analysis files and models
- `groves/` - Grove JSON files for Blender import
- `tree_models/` - Individual tree USD models organized by species, with FBX files alongside

### 4. **Species-Specific Subfolders**

- Individual tree models are organized by species
- Each species gets its own subfolder within `tree_models/`
- All LOD levels (USD) and FBX files for each species are grouped together

## Usage

### Adding New Input Files

1. Place new CSV files in `data/input/`
2. Run the generation script - outputs will be organized in `data/output/{input_name}/`

### Multiple Input Files

```
data/
├── input/
│   ├── demo_forest.csv
│   ├── oak_grove.csv
│   └── pine_plantation.csv
└── output/
    ├── demo_forest/
    ├── oak_grove/
    └── pine_plantation/
```

### File Naming Convention

- Input files: Use descriptive names like `demo_forest.csv`, `oak_grove.csv`
- Output folders: Match the input filename (without extension)
- Species names: Sanitized format `Family___Species` (e.g., `Fagaceae___Beech`)
- Tree models: Include tree index and LOD level `{species}_tree_{index:03d}_{LOD}.usd`

## Migration from Old Structure

The old flat structure where all files were mixed together in a single output folder has been replaced with this organized hierarchy. This makes it much easier to:

- Find specific files
- Manage multiple projects
- Clean up outputs for specific inputs
- Understand the relationship between input and output files
