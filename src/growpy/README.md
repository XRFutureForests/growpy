# GrowPy - Lightweight CSV to Tree Generation

A streamlined Python interface for generating procedural trees from CSV data using The Grove 2.2 Core.

## Philosophy

GrowPy is designed to be a thin wrapper around The Grove 2.2's powerful tree generation capabilities. Rather than reinventing functionality that Grove already provides, GrowPy focuses on:

- **Leveraging Grove's existing systems**: Uses Grove's built-in preset loading, mixing species approach, and export functions
- **Minimal abstraction**: Direct use of Grove's core classes like `Grove`, `Vector`, and `Properties`
- **CSV-to-forest workflow**: Simplified pipeline from tabular data to 3D tree models

## Key Features

- **Species Management**: Direct use of Grove's `.seed.json` preset files
- **Mixed Species Forests**: Implements Grove's documented approach for shared light environments
- **Multiple LOD Levels**: Generates 6 levels of detail (LOD0_Ultra through LOD5_Minimal) for optimization
- **FBX Export**: Combines LOD files into game-ready FBX format for Unity/Unreal
- **Flexible Export**: Individual trees per species or combined forest models
- **Lightweight**: Minimal code between your CSV data and Grove's tree generation

## Quick Start

```python
import growpy

# Generate trees from CSV with default settings
files = growpy.generate_trees("forest.csv")

# Custom configuration
config = growpy.GrowPyConfig(
    export_mode=growpy.ExportMode.COMBINED,
    growth_cycles=15,
    resolution=32
)
files = growpy.generate_trees("forest.csv", config)

# List available species
species = growpy.list_species()
```

## CSV Format

Your CSV file must have these columns:

- `x`, `y`, `z`: Tree positions
- `species`: Species name (must match Grove preset files)

Example:

```csv
x,y,z,species
0,0,0,Fagaceae - European oak
5,2,0,Betulaceae - Silver birch
-3,4,0,Fagaceae - European oak
```

## Export Modes

- **Individual**: Separate grove per species using `Grove.build_models()`
- **Combined**: Single forest using `Grove.build_as_one_model()`
- **LOD Levels**: Six detail levels per species (Ultra, High, Medium, Low, VeryLow, Minimal)

## LOD to FBX Conversion

After generating LOD files, use the included script to create game-ready FBX files:

```bash
# Convert all LOD files to FBX format for game engines
python combine_lods_to_fbx.py --input_dir data/output --output_dir fbx_assets

# Check what files would be processed
python combine_lods_to_fbx.py --input_dir data/output --check_only
```

**Requirements**: Blender Python API (`pip install bpy`)

See `README_LOD_TO_FBX.md` for detailed instructions.

## Dependencies

- The Grove 2.2 Core modules
- pandas (for CSV loading)

## Architecture

GrowPy's ultra-simplified structure:

```
growpy/
├── __init__.py          # Public API
├── growpy.py           # Main generation logic + species management
└── config.py           # Configuration classes
```

This minimal approach means GrowPy does exactly what it needs to do: convert CSV data to trees using Grove's proven systems, without any unnecessary abstraction layers.
