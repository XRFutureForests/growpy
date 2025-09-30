# GrowPy Documentation

Complete documentation for the GrowPy pipeline - a simplified tree generation system using The Grove 2.2 with FBX export workflow.

## Documentation Index

### Main Documentation
- **[User Guide](USER_GUIDE.md)** ⭐ **START HERE!**
  - Complete step-by-step guide
  - Installation and requirements
  - Quick start examples
  - All pipeline steps (1-5)
  - Complete CLI reference
  - CSV format specifications
  - Advanced usage examples
  - Troubleshooting guide

### Configuration
- **[Configuration Guide](CONFIGURATION.md)** - Package configuration system
  - `GrowPyConfig` class
  - Species lookup table format
  - Asset path resolution
  - Growth model access
  - Color settings
  - Adding new species

- **[Config Override](CONFIG_OVERRIDE.md)** - Project-level overrides
  - Override hierarchy
  - Custom species configurations
  - Migration from data/

### Technical Documentation
- **[Module Overview](MODULE_OVERVIEW.md)** - Code structure
  - Package organization
  - Module descriptions
  - Key features
  - Programmatic usage

- **[Grove Integration](GROVE_INTEGRATION.md)** - Grove API integration
  - API improvements
  - Integration patterns
  - Best practices

- **[Texture Implementation](TEXTURE_IMPLEMENTATION.md)** - Materials & textures
  - Material system
  - Texture mapping
  - FBX export details

## Quick Links

### Most Common Tasks

**Run Complete Pipeline:**
```bash
python src/growpy/cli/run_pipeline.py
```

**Generate Forest from CSV:**
```bash
python src/growpy/cli/generate_forest.py forest_data.csv
```

**Create Growth Models:**
```bash
python src/growpy/cli/create_growth_models.py
```

**Export Twigs:**
```bash
python src/growpy/cli/export_twigs.py data/assets/twigs
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

✅ **Complete FBX Pipeline** - Trees and twigs with mesh, skeleton, materials, and textures
✅ **Smart Growth Models** - Automatic early termination when growth plateaus
✅ **Light Competition** - Multi-species forest simulation with realistic shading
✅ **Flexible CLI** - Full argparse support with extensive options
✅ **Main Pipeline Script** - Run entire workflow with one command
✅ **Comprehensive Documentation** - Step-by-step guides with examples

## Requirements

- **The Grove 2.2** Python API (installed at `src/the_grove_22`)
- **Python 3.8+** with conda environment
- **Required packages**: `conda install -c conda-forge bpy pandas numpy scikit-learn matplotlib tqdm`

## Getting Help

1. Check the [User Guide](USER_GUIDE.md) for detailed instructions
2. Review the [Troubleshooting](TROUBLESHOOTING.md) guide
3. Check script help: `python script.py --help`
4. Review The Grove 2.2 documentation for advanced features

## Contributing

When adding new features or documentation:
1. Update relevant docs in `docs/growpy/`
2. Keep the User Guide as the main entry point
3. Link between related documentation
4. Include code examples where appropriate

## License

This project integrates with The Grove 2.2. Please ensure you have a valid license for The Grove 2.2 before using GrowPy.