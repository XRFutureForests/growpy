# The Grove - Simplified Tree Generation

Clean, simplified tree generation system using The Grove 2.2 with FBX export workflow.

📖 **[Complete Documentation](docs/growpy/)** - All GrowPy documentation
📚 **[User Guide](docs/growpy/USER_GUIDE.md)** - Comprehensive step-by-step guide
⚡ **[Quick Start](GROWPY_GUIDE.md)** - Quick reference (redirects to full docs)

## Project Structure

```
the-grove/
├── src/growpy/                      # Core Python package
│   ├── __init__.py                 # Main package interface
│   ├── config/                     # Configuration management
│   │   └── settings.py            # GrowPyConfig class
│   ├── core/                       # Core simulation
│   │   ├── forest.py              # Forest-level operations
│   │   ├── grove.py               # Grove-level operations
│   │   └── tree.py                # Tree model functions
│   ├── io/                         # Import/Export
│   │   └── blender_export.py      # FBX export functionality
│   ├── utils/                      # Utilities
│   │   └── dependencies.py        # Dependency management
│   └── cli/                        # Command-line scripts
│       ├── run_pipeline.py        # Main pipeline runner
│       ├── prepare_assets.py      # Asset preparation
│       ├── export_twigs.py        # Twig FBX export
│       ├── create_growth_models.py # Growth model creation
│       ├── generate_forest.py     # Forest from CSV
│       └── export_trees.py        # Individual tree export
├── data/                           # Data directory
│   └── assets/                    # Assets from Grove
│       ├── presets/               # Species presets
│       ├── textures/              # Tree textures
│       ├── twigs/                 # Twig files
│       └── growth_models/         # Generated models
├── GROWPY_GUIDE.md                # Complete documentation
└── README.md                      # This file
```

## Core Philosophy

**Simplified & Clean**: Removed complex USD workflows, multiple LOD variants, and positioning hacks in favor of straightforward FBX export using Grove's native mesh + skeleton output.

**Four-Layer Hierarchy**: Forest → Grove → Tree → Twig structure maintained for logical organization.

**Single High-Quality Output**: One high-resolution model per species instead of multiple LOD variants.

## Quick Start

### Run Complete Pipeline

```bash
# Run the full pipeline (prepare, export twigs, create models)
python src/growpy/cli/run_pipeline.py
```

### Run Individual Steps

```bash
# Step 1: Prepare assets from The Grove 2.2
python src/growpy/cli/prepare_assets.py

# Step 2: Export twigs to FBX
python src/growpy/cli/export_twigs.py data/assets/twigs

# Step 3: Create growth models (with smart early termination)
python src/growpy/cli/create_growth_models.py

# Step 4: Generate forest from CSV
python src/growpy/cli/generate_forest.py forest_data.csv

# Step 5: Export individual tree species
python src/growpy/cli/export_trees.py
```

### Programmatic Usage

```python
from growpy import create_grove, export_tree_as_fbx
from growpy.utils.dependencies import gc

# Create and export a single tree
grove = create_grove("European beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)
export_tree_as_fbx(grove, "beech.fbx", "European beech", include_skeleton=True)
```

### See Full Documentation

📖 **[GROWPY_GUIDE.md](GROWPY_GUIDE.md)** - Complete guide with:
- Detailed CLI reference for all scripts
- CSV format specifications
- Growth model configuration
- Advanced usage examples
- Troubleshooting guide

## Requirements

- **The Grove 2.2** Python API (installed at `src/the_grove_22`)
- **Python 3.8+** with conda environment
- **Required packages**: `conda install -c conda-forge bpy pandas numpy scikit-learn matplotlib tqdm`

## Key Features

### ✅ What's Included
- **Complete FBX Pipeline** - Trees and twigs with mesh, skeleton, materials, and textures
- **Smart Growth Models** - Automatic early termination when growth plateaus
- **Light Competition** - Multi-species forest simulation with realistic shading
- **Flexible CLI** - Full argparse support with extensive options
- **Main Pipeline Script** - Run entire workflow with one command
- **Comprehensive Documentation** - Step-by-step guide with examples

### ✅ Smart Iteration (New!)
Growth model creation now features intelligent early termination:
- Monitors height increase per cycle
- Stops when growth plateaus (configurable threshold)
- Timeout protection to prevent infinite loops
- Saves computation time while maintaining accuracy

### ❌ Removed
- Complex USD/USDA export system
- Multiple LOD variants (LOD0, LOD1, LOD2)
- Positioning and texture workarounds
- Try/except approaches everywhere

## Output

All exports generate FBX files compatible with:
- **Blender** (native)
- **Unreal Engine**
- **Unity**
- **Maya/3ds Max**
- Other FBX-compatible applications

Trees include mesh geometry, skeleton/armature, and basic materials. Twigs are exported as individual FBX assets ready for instancing.

## Migration Notes

This is a simplified version of the original complex system. The old USD-based workflow has been replaced with a cleaner FBX approach that eliminates positioning issues and texture problems while maintaining the core Forest/Grove/Tree/Twig hierarchy.