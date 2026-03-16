# GrowPy - Procedural Forest Generation

Clean, simplified tree generation system using The Grove 2.3 optimized for **Unreal Engine 5 Nanite workflows**.

**Documentation:**

- **[Functional Description](docs/growpy-functional-description.md)** - Complete package architecture and data flow
- **[Coordinate Systems](docs/coordinate-systems.md)** - Grove, Blender, Unreal, and PVE coordinate transforms
- **[Naming Conventions](docs/naming-conventions.md)** - Species, file, and directory naming standards
- **[PVE Preset Workflow](docs/pve-preset-workflow.md)** - Procedural Vegetation Editor integration
- **[PVE Attribute Reference](docs/pve-attribute-reference.md)** - PVE attributes and Grove mapping
- **[Dataset Specification](docs/dataset-specification.md)** - Tree asset dataset for VR forest simulation
- **[Dataset Overview](docs/dataset-overview.md)** - Production status and preview gallery
- **[Grove 2.3 API](docs/the_grove/)** - Grove core API documentation

## Quick Start

### Installation

1. Install conda environment:

```bash
conda env create -f environment.yml
conda activate growpy
```

1. Install package in development mode:

```bash
pip install -e .
```

1. Add The Grove (commercial, not included in repo):

```bash
# Copy or symlink your licensed Grove 2.3 installation into src/
cp -r /path/to/the_grove_23 src/the_grove_23
# or on Windows: mklink /D src\the_grove_23 C:\path\to\the_grove_23
```

The `src/the_grove_23/` directory is excluded from git because The Grove is proprietary software requiring a [separate license](https://www.thegrove3d.com). After cloning, you must place or symlink your licensed Grove installation there. The expected structure is:

```text
src/the_grove_23/
├── addons/          # Blender/Houdini add-ons
├── documentation/   # API reference HTML
├── modules/         # Python API (the_grove_23_core)
├── presets/         # Species .seed.json files
├── textures/        # Bark textures
└── twigs/           # Twig .blend files
```

### Pipeline Workflow

All CLI scripts read defaults from the central config file [`src/growpy/growpy.toml`](src/growpy/growpy.toml). CLI arguments override config values when provided. Resolution order: dataclass defaults -> growpy.toml -> CLI arguments.

The pipeline has 4 sequential steps. Run them in order:

```bash
# Step 1: Copy and standardize Grove 2.3 assets (presets, twigs, textures)
python src/growpy/cli/prepare_assets.py

# Step 2: Convert twig .blend files to USD format
python src/growpy/cli/convert_twigs.py

# Step 3: Generate species growth models (height-to-age curves)
python src/growpy/cli/create_growth_models.py

# Step 4: Generate forest from CSV inventory data
python src/growpy/cli/generate_forest.py
```

Steps 1-3 only need to run once per species set. Step 4 is the main generation step.

OBJ export for Helios++ LiDAR simulation runs automatically in Step 4 when `helios.export_obj = true` in growpy.toml. Configure decimation ratios, scene XML, and combined OBJ in the `[helios]` section.

**CSV Format Required**: `x`, `y`, `species`, `height` columns (optional: `z`, `fid`)

**Output**: `data/output/forest/` with trees, twigs, textures, and metadata organized by species

### Import to Unreal Engine

1. Copy entire output folder to Unreal Content Browser
2. USD files are auto-imported as Nanite Assemblies (UE 5.7+)
3. Trees and twigs are organized by species in individual folders
4. Enable Nanite for optimized rendering (usually auto-detected)

Trees and twigs export as separate assets for Unreal-side assembly via PointInstancer.

### Import DynamicWind Data (Wind Animation)

Wind data is embedded directly in the USD skeleton. For older workflows, each tree also exports a `*_DynamicWind.json` file:

**Method 1: Right-Click Asset Action (Recommended)**

1. Import the USD assembly first (drag into Content Browser)
2. Select the imported **SkeletalMesh** asset
3. Right-click and look for **"Scripted Asset Actions"** > **"Import Dynamic Wind Data"**
4. Select the matching `*_DynamicWind.json` file

**Method 2: Blueprint/Python**

```python
# Unreal Python
import unreal
skeletal_mesh = unreal.load_asset("/Game/Path/To/YourSkeletalMesh")
unreal.DynamicWindBlueprintLibrary.import_dynamic_wind_skeletal_data_from_file(skeletal_mesh)
```

**Required Plugins**: Dynamic Wind, Nanite, Nanite Foliage (all experimental)

### Unreal Engine Setup

**Required Plugins** (enable in Plugins window):

- Python Editor Script Plugin
- Editor Scripting Utilities
- USD Importer
- Nanite (experimental)
- Nanite Foliage (experimental)
- Dynamic Wind (experimental)

**Project Settings**:

- **Remote Execution**: Edit > Project Settings > Plugins > Python > Enable Remote Execution
  - Allows running Python scripts from VSCode
- **USD Importer**: Edit > Project Settings > Plugins > USD Importer
  - Enable "Use Nanite" for automatic Nanite mesh generation

**Environment Variables** (for custom USD plugins):

```bash
# Point to custom USD plugin path if needed
set PXR_PLUGINPATH_NAME=C:\Path\To\Plugins
```

**VSCode Integration**:

```bash
# Install Unreal Python extension
code --install-extension NilsSoderman.ue-python
```

This enables running Python scripts directly in Unreal from VSCode.

### PVE Debug Mode (Procedural Vegetation Editor)

To see hidden PVE attributes in the editor:

```
# In Unreal console (press ~)
PV.DebugMode.Enabled 1
```

This reveals additional debug information for procedural vegetation assets. See [PVE Preset Workflow](docs/pve-preset-workflow.md) for the full PVE integration guide.

### USD Import Tips

**USD Import**:

- USD files auto-import as Nanite assemblies in UE 5.7+
- Skeletal mesh hierarchy is preserved
- Materials reference textures by relative path

**FBX Import Settings** (if using FBX fallback):

- Auto Generate Collision: **Disabled** (not needed for foliage)
- Build Nanite: **Enabled**
- Import Materials: **Enabled**

## Project Structure

```
growpy/
├── src/
│   ├── growpy/                    # Main Python package
│   │   ├── cli/                   # Command-line scripts
│   │   │   ├── prepare_assets.py         # Step 1: Copy Grove 2.3 assets
│   │   │   ├── convert_twigs.py          # Step 2: Convert twigs to USD
│   │   │   ├── create_growth_models.py   # Step 3: Generate height models
│   │   │   └── generate_forest.py        # Step 4: Forest from CSV (includes OBJ export)
│   │   ├── config/                # Configuration and quality presets
│   │   ├── core/                  # Forest/Grove/Tree/Skeleton simulation
│   │   ├── io/                    # USD export, OBJ export, wind JSON, PVE mapping
│   │   ├── tests/                 # Test suite (pytest)
│   │   └── utils/                 # Analysis, profiling, plotting
│   └── the_grove_23/              # Grove 2.3 (not in repo, add after clone)
├── data/
│   ├── assets/                    # Copied from Grove 2.3 (step 1-3 output)
│   │   ├── presets/              # Species .seed.json files
│   │   ├── textures/             # Bark and leaf textures
│   │   ├── twigs/                # Twig .blend and converted .usda files
│   │   └── growth_models/        # Generated prediction models
│   ├── input/                     # Your CSV files
│   └── output/                    # Generated forests
├── docs/                          # Project documentation
│   └── the_grove/                # Grove 2.3 API reference
│   (+ cli-reference, coordinate systems, naming conventions, PVE guides)
├── pyproject.toml                 # Python package configuration
└── environment.yml                # Conda environment definition
```

## Testing

Tests live alongside the source code in `src/growpy/tests/`.

```bash
# Run all tests
conda activate growpy
python -m pytest src/growpy/tests/ -v

# Run a specific test module
python -m pytest src/growpy/tests/test_skeleton.py -v

# Run with short tracebacks
python -m pytest src/growpy/tests/ --tb=short
```

Test modules cover configuration, skeleton math, twig geometry, preset overrides, quality presets, texture utilities, PVE coordinate transforms, profiling, and naming conventions. See the [test suite README](src/growpy/tests/README.md) for coverage details.

## Core Pipeline Steps

The pipeline consists of 4 sequential CLI scripts that produce output consumed by subsequent steps, plus an optional standalone export:

```
prepare_assets.py --> convert_twigs.py --> create_growth_models.py --> generate_forest.py
```

1. **Prepare Assets** - Copy and standardize presets, textures, and twigs from Grove 2.3
2. **Convert Twigs** - Convert .blend twig files to USD with silhouette-optimized mesh densification
3. **Create Growth Models** - Simulate growth curves and generate height-to-age prediction models
4. **Generate Forest** - Multi-species forest simulation with USD Nanite assembly export (includes OBJ/MTL for Helios++ when `helios.export_obj = true`)

All scripts read defaults from [`src/growpy/growpy.toml`](src/growpy/growpy.toml) and can be run without arguments. Each step is independently re-runnable and produces deterministic output.

## CLI Scripts Reference

### Step 1: Prepare Assets

```bash
# Copy assets for species in CSV (uses csv_file from growpy.toml)
python src/growpy/cli/prepare_assets.py

# Copy ALL 57 available species (ignores CSV filter)
python src/growpy/cli/prepare_assets.py --all

# Resize textures to power-of-2 for GPU compatibility
python src/growpy/cli/prepare_assets.py --resize-textures
```

**Flags**: `--grove-dir PATH`, `--csv PATH`, `--all`, `--resize-textures`

### Step 2: Convert Twigs

```bash
# Convert twigs with default settings from growpy.toml (densification + alpha trimming enabled)
python src/growpy/cli/convert_twigs.py

# Skip mesh densification (raw export)
python src/growpy/cli/convert_twigs.py --no-densify

# Adjust alpha trimming threshold
python src/growpy/cli/convert_twigs.py --alpha-trim 0.3

# Enable boundary smoothing
python src/growpy/cli/convert_twigs.py --smooth-boundary --smooth-iterations 3
```

**Flags**: `--csv PATH`, `--no-densify`, `--alpha-trim FLOAT`, `--smooth-boundary`, `--smooth-iterations INT`, `--smooth-factor FLOAT`, `--boundary-edge-mm FLOAT`

### Step 3: Create Growth Models

```bash
# Generate growth models for species in CSV (uses defaults from growpy.toml)
python src/growpy/cli/create_growth_models.py

# Production quality (more seeds = more robust curves)
python src/growpy/cli/create_growth_models.py --seeds 3

# Quick test with fewer cycles
python src/growpy/cli/create_growth_models.py --cycles 35

# Single species
python src/growpy/cli/create_growth_models.py --species "European beech"
```

**Flags**: `--csv PATH`, `--cycles INT`, `--seeds INT`, `--height-threshold FLOAT`, `--max-cycles-without-growth INT`, `--timeout INT`, `--species TEXT`

### Step 4: Generate Forest

```bash
# Default generation (uses quality, cycles, etc. from growpy.toml)
python src/growpy/cli/generate_forest.py

# Production quality with profiling
python src/growpy/cli/generate_forest.py \
  --quality ultra --growth-cycle-limit 20 --smooth-iterations 15 --profile

# Fast preview
python src/growpy/cli/generate_forest.py --quality medium --fast

# Multi-stage export (trees at different growth stages)
python src/growpy/cli/generate_forest.py --cycle-interval 10 --growth-cycle-limit 40

# Export only specific trees (others still participate in growth simulation)
python src/growpy/cli/generate_forest.py --export-trees 1,2,5

# Generate Unreal import scripts
python src/growpy/cli/generate_forest.py --import-to-unreal

# Skeleton simplification (reduce bone count independently of mesh quality)
python src/growpy/cli/generate_forest.py \
  --quality ultra --skeleton-length 2.5 --skeleton-reduce 0.5
```

**Quality Presets**:

| Preset      | Vertices | Skeleton Detail | Use Case            |
| ----------- | -------- | --------------- | ------------------- |
| ultra       | 32       | Most bones      | Hero trees, closeup |
| high        | 24       | Many bones      | Featured trees      |
| medium      | 16       | Balanced        | Background trees    |
| low         | 12       | Few bones       | Distant trees       |
| performance | 8        | Minimal         | Far background      |

**All Flags**:

| Flag | Description |
| ---- | ----------- |
| `--quality {ultra,high,medium,low,performance}` | Quality preset (default: ultra) |
| `--growth-cycle-limit INT` | Max growth cycles per tree (default: 10) |
| `--smooth-iterations INT` | Branch smoothing passes, 0-20 (default: 10) |
| `--output-dir PATH` | Output directory (default: data/output/forest) |
| `--skeleton-length FLOAT` | Merge nodes into longer bones, 0-5 (default: from preset) |
| `--skeleton-reduce FLOAT` | Skip thin branches, 0-1 (default: from preset) |
| `--skeleton-bias FLOAT` | Bone distribution, 0=trunk 1=tips (default: 0.5) |
| `--skeleton-connected {true,false}` | Connected bone chains (default: true) |
| `--cycle-interval INT` | Multi-stage export at cycle intervals |
| `--max-cycles INT` | Max cycles for multi-stage export |
| `--export-trees IDS` | Comma-separated tree IDs to export |
| `--import-to-unreal` | Generate Unreal Python import script |
| `--unreal-project-path PATH` | Unreal content path (default: /Game/GrowPy/Trees) |
| `--include-grove-attributes` | Add Grove metadata to USD (increases size ~70%) |
| `--include-static` | Also generate static mesh assemblies |
| `--preset-override PARAM=VALUE` | Override preset parameter (repeatable) |
| `--longevity-mode` | Prevent tree death at high cycle counts |
| `--skip-pve-json` | Skip PVE preset JSON generation |
| `--skip-validation` | Skip USD assembly validation |
| `--fast` | Skip PVE JSON, validation, and static meshes |
| `--profile` | Print detailed timing report |
| `-v, --verbose` | Verbose output |

### Performance Optimization

```bash
# Fast mode - skip PVE JSON, validation, static meshes
python src/growpy/cli/generate_forest.py --fast

# Profile to identify bottlenecks
python src/growpy/cli/generate_forest.py --profile

# Skip individual optional steps
python src/growpy/cli/generate_forest.py --skip-pve-json --skip-validation
```

**Performance Flags**:

- `--fast` - Skip PVE JSON, validation, and static mesh generation
- `--skip-pve-json` - Skip PVE preset JSON (saves ~3% export time)
- `--skip-validation` - Skip USD assembly validation (saves ~5-10% export time)
- `--include-static` - Also generate static mesh assemblies (adds ~7% time)
- `--profile` - Print timing report to identify bottlenecks

## Data Folders

The `data/` directory holds all pipeline inputs and outputs:

```
data/
├── input/                     # Your CSV files with tree positions and species
│   └── test.csv              # Default input (configured in growpy.toml: csv_file)
├── assets/                    # Generated by Step 1 (prepare_assets.py)
│   ├── presets/              # Species .seed.json files (growth parameters)
│   ├── textures/             # Bark and leaf textures
│   ├── twigs/                # Twig .blend files and converted .usda files
│   ├── growth_models/        # Generated by Step 3 (height-to-age curves)
│   └── pve_configs/          # PVE preset overrides per species
└── output/                    # Generated by Step 4 (forest output)
    └── forest/               # Default output (configured in growpy.toml: output_dir)
```

### Customizing Species Presets

After Step 1 copies the presets from The Grove 2.3, you can edit the `.seed.json` files in `data/assets/presets/` to adjust growth behavior per species. Each preset contains approximately 60 parameters controlling branch structure, growth dimensions, environmental responses, pruning, and twig placement.

See the [Grove Preset Reference](docs/grove-preset-reference.md) for a complete description of all parameters and GrowPy's cycle-based curve extensions.

## Output Structure

Forest generation (Step 4) creates organized output folders ready for Unreal import:

```
data/output/forest/
├── species_name/
│   └── tree_0001/
│       ├── species_name.usda                        # Nanite assembly
│       ├── species_name_0001_skeletal.usda           # Tree mesh with skeleton
│       ├── species_name_0001_DynamicWind.json        # Wind animation data
│       ├── species_name_0001.json                    # PVE preset (optional)
│       └── twigs/                                    # Copied twig USD files
│           ├── species_name_twig_apical_skeletal.usda
│           └── species_name_twig_lateral_skeletal.usda
└── unreal_scripts/                                   # Optional (--import-to-unreal)
    ├── import_forest.py                              # Auto-generated Unreal import
    └── clean_assets.py                               # Auto-generated cleanup
```

## Requirements

- **The Grove 2.3** - Commercial tree modeling software ([thegrove3d.com](https://www.thegrove3d.com)), not included in repo — see [Installation](#installation)
- **Python 3.9-3.13** - Via conda/mamba environment
- **bpy module** - Blender Python API (bundled USD, MaterialX, OpenImageIO)

### Key Dependencies

```bash
conda install -c conda-forge numpy pandas matplotlib scikit-learn tqdm pillow
pip install bpy  # Blender Python API with bundled USD
```

Or install everything via the environment file:

```bash
conda env create -f environment.yml
```

## Configuration

Species configuration is managed in `src/growpy/config/tree_asset_lookup.csv` which maps 57 Grove species to their asset files:

```csv
species,seed_path,texture_path,twig_path
European beech,EuropeanBeech.seed.json,European_Beech,EuropeanBeechTwig
Scots pine,ScotsPine.seed.json,Scots_Pine,ScotsPineTwig
Common oak,CommonOak.seed.json,Common_Oak,CommonOakTwig
...
```

Quality presets are defined in `src/growpy/config/quality.py` with 5 LOD levels controlling resolution, skeleton detail, and build cutoffs.

## Key Features

### Forest/Grove/Tree/Twig Hierarchy

- **Forest**: Multi-species with inter-species light competition simulation
- **Grove**: Species-specific tree collection with shared growth models
- **Tree**: Individual instances with mesh + skeleton for wind animation
- **Twig**: Reusable USD assets with silhouette-optimized mesh densification

### Smart Growth Models

- Automatic early termination when growth plateaus
- Configurable height threshold and cycle limits
- Multi-seed averaging for robust growth curves
- Timeout protection for reliable batch processing

### USD Export

- Native USD/USDA format for Unreal Engine 5.7+
- Nanite Assembly structure with skeletal mesh support
- DynamicWind attributes embedded in skeleton for wind animation
- PointInstancer-based twig placement
- PVE preset JSON generation for Procedural Vegetation Editor

### Quality and Skeleton Control

- 5 quality presets (ultra, high, medium, low, performance)
- Independent skeleton simplification parameters
- Skeleton length, reduce, bias, and connected bone controls
- Critical for Unreal Engine's 32,767 bone limit

### Multi-Stage and Selective Export

- Multi-stage export: generate trees at different growth stages from single positions
- Selective export: choose specific trees to export while all participate in simulation
- Longevity mode to prevent tree death at high cycle counts
- Preset override system for dynamic parameter adjustment

### Unreal Engine Optimized

- Nanite-ready mesh topology
- Skeletal mesh support for wind animation
- Organized folder structure for Content Browser
- Optional auto-generated Unreal Python import scripts
- PVE integration for procedural vegetation workflows

## Programmatic Usage

```python
from growpy import create_forest, simulate_forest_growth, get_config
import pandas as pd

# Load forest data from CSV
forest_data = pd.read_csv("data/input/test.csv")

# Create forest (groups trees by species, creates groves)
forest = create_forest(forest_data)

# Simulate growth with inter-species light competition
simulate_forest_growth(forest, max_cycles=10)
```

For direct grove-level control:

```python
from growpy import create_grove
import the_grove_23_core as gc

# Create grove for a single species
grove = create_grove("European beech")

# Add tree and simulate growth
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Build models and skeletons
skeletons = grove.build_skeletons()
bones = grove.tag_bone_id(2.0, 0.16, 0.5, True)
models = grove.build_models({"resolution": 16})
```

## Troubleshooting

### Grove API Import Issues

Ensure `PYTHONPATH` includes both `./src` and `./src/the_grove_23/modules`:

```bash
# Windows PowerShell
$env:PYTHONPATH=".\src;.\src\the_grove_23\modules"

# Linux/Mac
export PYTHONPATH="./src:./src/the_grove_23/modules"
```

Or use `pip install -e .` which handles path resolution automatically.

### bpy Module Not Found

Install via pip (includes bundled USD):

```bash
pip install bpy
```

### Missing Assets

Run prepare_assets.py to copy assets from Grove 2.3:

```bash
python src/growpy/cli/prepare_assets.py
```

### Bone Count Exceeds Unreal Limit

Unreal Engine has a 32,767 bone limit. Use skeleton simplification flags:

```bash
python src/growpy/cli/generate_forest.py \
  --skeleton-length 2.5 --skeleton-reduce 0.5
```

Higher `--skeleton-reduce` values are the most effective for reducing bone count.

## License

This project uses The Grove 2.3, a commercial product. Ensure you have proper licensing for The Grove 2.3 before use.

## Contributing

This project follows a template-based structure. Key guidelines:

- Python files use snake_case
- All scripts in `src/growpy/cli/` directory
- Configuration in `src/growpy/config/`
- Documentation in `docs/`
- Use conda/mamba for environment management (never pip venv)

---

**Simplified. Clean. Ready for Unreal Engine.**
