# The Grove - Simplified Tree Generation

Clean, simplified tree generation system using The Grove 2.2 optimized for **Unreal Engine 5 PCG workflows**.

📖 **[Complete Documentation](docs/growpy/)** - All GrowPy documentation
📚 **[User Guide](docs/growpy/USER_GUIDE.md)** - Comprehensive step-by-step guide
🎮 **[Unreal PCG Workflow](docs/growpy/UNREAL_PCG_WORKFLOW.md)** - **NEW!** Complete procedural forest guide
🌿 **[Procedural Twig Placement](docs/growpy/UNREAL_TWIG_PLACEMENT.md)** - **NEW!** Use twig attributes in Unreal
⚡ **[Quick Start](GROWPY_GUIDE.md)** - Quick reference (redirects to full docs)

## Quick Start

### Installation

1. Install conda environment:

```bash
conda env create -f environment.yml
conda activate the-grove
```

2. Install package in development mode:

```bash
pip install -e .
```

### Forest Generation Workflow

Generate a complete forest based on real tree inventory data:

```bash
# Run complete pipeline (prepare assets, convert twigs, create models)
python src/growpy/cli/run_pipeline.py

# Generate forest from CSV
python src/growpy/cli/generate_forest.py data/input/forest_inventory.csv
```

**CSV Format Required**: `x`, `y`, `species`, `height` columns (optional: `z`)

**Output**: `data/output/forest/` with trees, twigs, textures, metadata

### Import to Unreal Engine

1. Copy entire output folder to Unreal Content Browser
2. USD files are auto-imported as Nanite Assemblies (UE 5.7+)
3. Trees and twigs are organized by species in individual folders
4. Enable Nanite for optimized rendering (usually auto-detected)

**No twig placement needed** - trees and twigs export as separate assets for Unreal-side assembly

## Project Structure

```
the-grove/
├── src/
│   ├── growpy/                    # Main Python package
│   │   ├── cli/                   # Command-line scripts
│   │   │   ├── run_pipeline.py           # Complete pipeline runner
│   │   │   ├── prepare_assets.py         # Copy Grove 2.2 assets
│   │   │   ├── convert_twigs.py          # Convert twigs to USD
│   │   │   ├── create_growth_models.py   # Generate height models
│   │   │   └── generate_forest.py        # Forest from CSV
│   │   ├── config/                # Configuration management
│   │   ├── core/                  # Forest/Grove/Tree simulation
│   │   ├── io/                    # USD export functionality
│   │   └── utils/                 # Utilities
│   └── the_grove_22/              # Grove 2.2 Python API
├── data/
│   ├── assets/                    # Copied from Grove 2.2
│   │   ├── presets/              # Species .seed.json files
│   │   ├── textures/             # Bark and leaf textures
│   │   ├── twigs/                # Original .blend twig files
│   │   └── growth_models/        # Generated prediction models
│   ├── input/                     # Your CSV files
│   └── output/                    # Generated forests/libraries
├── docs/growpy/                   # Complete documentation
└── environment.yml                # Conda environment definition
```

## Core Pipeline Steps

The `run_pipeline.py` script executes:

1. **Prepare Assets** - Copy presets, textures, and twigs from Grove 2.2
2. **Convert Twigs** - Export .blend files to FBX format
3. **Create Growth Models** - Generate height prediction models for all species

Then:

- **Forest Generation** - Multi-species forest from CSV data

## CLI Scripts Reference

### Pipeline Runner

```bash
# Run complete pipeline with defaults
python src/growpy/cli/run_pipeline.py

# Run specific steps
python src/growpy/cli/run_pipeline.py --steps prepare,twigs,models

# Skip steps
python src/growpy/cli/run_pipeline.py --skip-prepare
```

### Individual Steps

```bash
# Step 1: Prepare assets
python src/growpy/cli/prepare_assets.py

# Step 2: Convert twigs
python src/growpy/cli/convert_twigs.py data/assets/twigs

# Step 3: Create growth models
python src/growpy/cli/create_growth_models.py --cycles 125 --seeds 1

# Step 4: Generate forest
python src/growpy/cli/generate_forest.py data/input/forest.csv
```

### Performance Optimization Flags

Forest generation supports several flags to optimize export time:

```bash
# Fast mode - skip wind JSON, PVE JSON (skeletal meshes only by default)
python src/growpy/cli/generate_forest.py data/input/test.csv --fast

# Profile to identify bottlenecks
python src/growpy/cli/generate_forest.py data/input/test.csv --profile

# Also generate static mesh assemblies (disabled by default)
python src/growpy/cli/generate_forest.py data/input/test.csv --include-static

# Skip individual optional steps
python src/growpy/cli/generate_forest.py data/input/test.csv --skip-wind-json --skip-pve-json
```

**Performance Flags**:

- `--fast` - Skip wind JSON, PVE JSON, static meshes, and validation (saves ~60% export time)
- `--skip-wind-json` - Skip wind animation JSON (saves ~37% export time)
- `--skip-pve-json` - Skip PVE preset JSON (saves ~3% export time)
- `--skip-validation` - Skip USD assembly validation (saves ~5% export time)
- `--include-static` - Also generate static mesh assemblies (adds ~7% time)
- `--profile` - Print timing report to identify bottlenecks

## Output Structure

Forest generation creates organized output folders ready for Unreal import:

```
output/
└── forest/
    ├── species_name/
    │   ├── tree_0001/
    │   │   ├── species_name.usda              # Nanite assembly
    │   │   ├── species_name_0001_skeletal.usda  # Tree mesh with skeleton
    │   │   └── [twig files copied here]
    │   └── tree_0002/
    │       └── ...
    ├── textures/                              # Shared textures
    └── unreal_import_trees.py                 # Optional import script
```

## Requirements

- **The Grove 2.2** - Commercial tree modeling software with Python API
- **Python 3.8+** - Via conda/mamba environment
- **bpy module** - Blender Python API (install via `conda install -c conda-forge bpy`)

### Key Dependencies

```bash
conda install -c conda-forge bpy pandas numpy scikit-learn matplotlib tqdm
```

## Configuration

Species configuration is managed in `src/growpy/config/tree_asset_lookup.csv`:

```csv
species,seed_path,texture_path,twig_path
European beech,EuropeanBeech.seed.json,European_Beech,EuropeanBeechTwig
Norway spruce,NorwaySpruce.seed.json,Norway_Spruce,NorwaySpruceTwig
```

## Documentation

- **[docs/growpy/](docs/growpy/)** - Complete GrowPy documentation
- **[docs/growpy/USER_GUIDE.md](docs/growpy/USER_GUIDE.md)** - Comprehensive usage guide
- **[docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)** - Multiprocessing and memory management
- **[docs/growpy/UNREAL_IMPORT_GUIDE.md](docs/growpy/UNREAL_IMPORT_GUIDE.md)** - Unreal Engine import instructions
- **[docs/the_grove/](docs/the_grove/)** - Grove 2.2 API documentation

## Key Features

### Forest/Grove/Tree/Twig Hierarchy

- **Forest**: Multi-species with light competition simulation
- **Grove**: Species-specific tree collection with shared growth models
- **Tree**: Individual instances with mesh + skeleton
- **Twig**: Reusable assets exported as FBX

### Smart Growth Models

- Automatic early termination when growth plateaus
- Configurable height threshold and cycle limits
- Timeout protection for reliable batch processing

### USD Export

- Native USD/USDA format for Unreal Engine 5.7+
- Nanite Assembly structure with skeletal mesh support
- Material and texture assignments
- Compatible with Unreal Engine 5 Nanite workflows

### Unreal Engine Optimized

- Nanite-ready mesh topology
- Skeletal mesh support for wind animation
- Organized folder structure for Content Browser
- Separation of trees and twigs for procedural assembly

## Programmatic Usage

```python
from growpy import create_grove, get_config
from growpy.io.assembly_export import export_tree_as_nanite_assembly
from pathlib import Path

# Get configuration
config = get_config()

# Create grove for species
grove = create_grove("European beech")

# Add tree and simulate growth
import the_grove_22_core as gc
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Build models and skeletons
skeletons = grove.build_skeletons()
bones = grove.tag_bone_id(2.0, 0.16, 0.5, True)
models = grove.build_models({"resolution": 16})

# Export as USD Nanite Assembly
export_tree_as_nanite_assembly(
    model=models[0],
    skeleton=skeletons[0],
    bones_info=bones,
    output_path=Path("beech.usda"),
    species_name="European beech",
    tree_id="0001"
)
```

## Troubleshooting

### Grove API Import Issues

Ensure `PYTHONPATH` includes both `./src` and `./src/the_grove_22/modules`:

```bash
# Windows PowerShell
$env:PYTHONPATH=".\src;.\src\the_grove_22\modules"

# Linux/Mac
export PYTHONPATH="./src:./src/the_grove_22/modules"
```

### bpy Module Not Found

Install via conda-forge:

```bash
conda install -c conda-forge bpy
```

### Missing Assets

Run prepare_assets.py to copy assets from Grove 2.2:

```bash
python src/growpy/cli/prepare_assets.py
```

## License

This project uses The Grove 2.2, a commercial product. Ensure you have proper licensing for The Grove 2.2 before use.

## Contributing

This project follows a template-based structure. Key guidelines:

- Python files use snake_case
- All scripts in `src/growpy/cli/` directory
- Configuration in `src/growpy/config/`
- Documentation in `docs/growpy/`
- Use conda/mamba for environment management (never pip venv)

---

**Simplified. Clean. Ready for Unreal Engine.**
