# GrowPy Documentation

Complete documentation for the GrowPy pipeline - simplified tree generation for Unreal Engine using The Grove 2.2 with FBX export workflow.

## Quick Start

📚 **[Getting Started Guide](../GETTING_STARTED.md)** ⭐ **START HERE!**

New to GrowPy? Start here for quick setup and first steps.

## Documentation Index

### Essential Guides

- **[CLI Reference](../guides/cli-reference.md)** 🔧 **COMMAND REFERENCE**
  - Complete flag documentation for all CLI scripts
  - Usage examples and workflows
  - Quality presets reference
  - Troubleshooting common issues

- **[Getting Started](../GETTING_STARTED.md)** 🚀 **QUICK SETUP**
  - Installation and environment setup
  - Two main workflows (Forest vs Library)
  - Common commands
  - First forest generation

- **[Unreal Import Guide](UNREAL_IMPORT_GUIDE.md)** 🎮 **UNREAL ENGINE**
  - Import trees and twigs to UE5
  - PCG (Procedural Content Generation) setup
  - Foliage Tool usage
  - Material setup and Nanite configuration

### Configuration

- **[Configuration Guide](CONFIGURATION.md)** - Package configuration
  - `GrowPyConfig` class
  - Species lookup table format
  - Asset path resolution
  - Adding new species

- **[Config Override](CONFIG_OVERRIDE.md)** - Project-level overrides
  - Override hierarchy
  - Custom species configurations

### Technical Documentation

- **[Module Overview](MODULE_OVERVIEW.md)** - Code structure
  - Package organization
  - Module descriptions
  - Programmatic usage

- **[Grove Integration](GROVE_INTEGRATION.md)** - Grove API integration
  - Integration patterns
  - Best practices

- **[Texture Implementation](TEXTURE_IMPLEMENTATION.md)** - Materials & textures
  - Material system
  - Texture mapping
  - FBX export details

## Common Commands

### Forest Generation Workflow

```bash
# Complete pipeline + forest generation
python src/growpy/cli/run_pipeline.py
python src/growpy/cli/generate_forest.py data/input/forest.csv
```

### Individual Pipeline Steps

```bash
# Step 1: Prepare assets
python src/growpy/cli/prepare_assets.py

# Step 2: Convert twigs
python src/growpy/cli/convert_twigs.py data/assets/twigs

# Step 3: Create growth models
python src/growpy/cli/create_growth_models.py
```

## Project Structure

```
the-grove/
├── src/growpy/              # Core package
│   ├── cli/                # Command-line scripts
│   ├── config/             # Configuration module
│   ├── core/               # Core simulation
│   ├── io/                 # Import/Export
│   └── utils/              # Utilities
├── docs/growpy/            # This documentation
├── data/                   # Data directory
│   ├── assets/            # Assets from Grove
│   │   ├── presets/       # Species presets
│   │   ├── textures/      # Textures
│   │   ├── twigs/         # Twig files
│   │   └── growth_models/ # Generated models
│   └── input/             # User input files
└── config/                # Optional config overrides
```

## Key Features

- **Complete FBX Pipeline** - Trees and twigs with mesh, skeleton, materials, and textures
- **Smart Growth Models** - Automatic early termination when growth plateaus
- **Light Competition** - Multi-species forest simulation with realistic shading
- **Forest/Grove/Tree/Twig Hierarchy** - Logical organization maintained
- **Unreal Engine Optimized** - Nanite-ready, skeletal mesh support, organized folders

## Requirements

- **The Grove 2.2** - Commercial tree modeling software with Python API
- **Python 3.8+** - Via conda/mamba environment
- **bpy module** - Blender Python API (`conda install -c conda-forge bpy`)

## Getting Help

1. Start with **[Getting Started Guide](../GETTING_STARTED.md)**
2. Check **[User Guide](USER_GUIDE.md)** for detailed CLI reference
3. See **[Unreal Import Guide](UNREAL_IMPORT_GUIDE.md)** for Unreal workflow
4. Run script help: `python script.py --help`

## Contributing

When adding new features or documentation:

1. Update relevant docs in `docs/growpy/`
2. Keep the User Guide as the main entry point
3. Link between related documentation
4. Include code examples where appropriate

## License

This project integrates with The Grove 2.2. Please ensure you have a valid license for The Grove 2.2 before using GrowPy.
