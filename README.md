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

Yield table calibration (optional, enabled by default in `growpy.toml`):

```bash
# Populate the yield table store from external sources (run once)
python -m growpy.cli.ingest_yield_tables

# Or use pylometree directly with custom providers
pylometree-ingest --store-dir data/input/yield_tables/store \
  --config models_dir=$(pwd)/data/input/yield_models
```

Step 3 automatically calibrates against yield tables when `[calibration] enabled = true`.

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

```text
growpy/
├── src/
│   ├── growpy/                    # Main Python package
│   │   ├── cli/                   # Pipeline CLI scripts
│   │   │   ├── prepare_assets.py         # Step 1: Copy Grove 2.3 assets
│   │   │   ├── convert_twigs.py          # Step 2: Convert twigs to USD
│   │   │   ├── create_growth_models.py   # Step 3: Generate height models
│   │   │   ├── generate_forest.py        # Step 4: Forest from CSV (includes OBJ export)
│   │   │   ├── ingest_yield_tables.py    # Yield table store ingestion
│   │   │   ├── generate_dataset_csvs.py  # Generate dataset input CSVs
│   │   │   └── produce_dataset.py        # Batch dataset production
│   │   ├── config/                # Configuration, quality presets, species lookup
│   │   ├── core/                  # Forest/Grove/Tree/Skeleton simulation
│   │   ├── io/                    # USD export, OBJ export, wind JSON, PVE mapping
│   │   ├── tools/                 # Diagnostic tools (analyze_usda, diagnose_growth, visualize_tree)
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
│   │   └── dataset/              # Dataset CSVs (from generate_dataset_csvs.py)
│   └── output/                    # Generated forests
├── docs/                          # Project documentation
│   └── the_grove/                # Grove 2.3 API reference
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

### Step 1: Prepare Assets (`prepare_assets.py`)

Copies and standardizes Grove 2.3 presets, textures, and twigs into `data/assets/`.

**Requires**:

- The Grove 2.3 installed at `src/the_grove_23/` (presets/, twigs/, textures/ subdirectories)
- `src/growpy/config/tree_asset_lookup.csv` (species-to-asset mapping, included in repo)
- Input CSV with species column (to filter which species to prepare), or `--all`

**Reads from `growpy.toml`**: `[assets] grove_dir`, `[general] csv_file`

**Produces**: `data/assets/presets/`, `data/assets/textures/`, `data/assets/twigs/` (raw .blend files)

```bash
python src/growpy/cli/prepare_assets.py                # Species from default CSV
python src/growpy/cli/prepare_assets.py --csv my.csv   # Species from custom CSV
python src/growpy/cli/prepare_assets.py --all           # All 57 Grove species
python src/growpy/cli/prepare_assets.py --resize-textures  # Power-of-2 textures for GPU
```

**Flags**: `--grove-dir PATH`, `--csv PATH`, `--all`, `--resize-textures`

### Step 2: Convert Twigs (`convert_twigs.py`)

Converts twig .blend files to USD format with optional mesh densification for Nanite silhouettes.

**Requires**:

- Step 1 completed (`data/assets/twigs/` contains .blend files)
- `bpy` module (Blender Python API)
- `src/growpy/config/tree_asset_lookup.csv` (twig-to-species mapping)

**Reads from `growpy.toml`**: `[twigs]` section (densify, alpha_trim, smooth_*, boundary_edge_mm, interior_decimate_ratio)

**Produces**: `.usda` twig files alongside .blend files in `data/assets/twigs/`

```bash
python src/growpy/cli/convert_twigs.py                  # Default settings from growpy.toml
python src/growpy/cli/convert_twigs.py --no-densify     # Raw export without densification
python src/growpy/cli/convert_twigs.py --alpha-trim 0.3 # Lower alpha trimming threshold
python src/growpy/cli/convert_twigs.py --smooth-boundary --smooth-iterations 3
```

**Flags**: `--csv PATH`, `--no-densify`, `--alpha-trim FLOAT`, `--smooth-boundary`, `--smooth-iterations INT`, `--smooth-factor FLOAT`, `--boundary-edge-mm FLOAT`

### Step 3: Create Growth Models (`create_growth_models.py`)

Simulates growth curves and generates height-to-age prediction models. When calibration is enabled, aligns growth to yield tables and re-simulates with calibration applied.

**Requires**:

- Step 1 completed (`data/assets/presets/` contains `.seed.json` files)
- The Grove 2.3 Python API (`the_grove_23_core`)
- Optional: yield table store for calibration (`data/input/yield_tables/store/`, populated by `ingest_yield_tables.py`)
- Optional: local yield table CSVs in `data/input/yield_tables/` (format: age,height,dbh)

**Reads from `growpy.toml`**: `[growth_models]` (cycles, seeds, height_threshold, timeout), `[calibration]` (enabled, align_height, align_dbh, yield_tables_dir), `[yield_sources]` (store_dir)

**Produces**: `data/assets/growth_models/` (JSON prediction models), calibration data in `.seed.json` files, comparison plots in `data/output/growth_comparison/`

```bash
python src/growpy/cli/create_growth_models.py           # Default from growpy.toml
python src/growpy/cli/create_growth_models.py --seeds 3  # More seeds for robust curves
python src/growpy/cli/create_growth_models.py --cycles 35 # Fewer cycles for quick test
python src/growpy/cli/create_growth_models.py --species "European beech"  # Single species
```

**Flags**: `--csv PATH`, `--cycles INT`, `--seeds INT`, `--height-threshold FLOAT`, `--max-cycles-without-growth INT`, `--timeout INT`, `--species TEXT`

### Step 4: Generate Forest (`generate_forest.py`)

Multi-species forest simulation from CSV inventory data with USD Nanite assembly export. Includes optional OBJ export for Helios++ LiDAR.

**Requires**:

- Steps 1-3 completed (presets, converted twigs, growth models all in `data/assets/`)
- Input CSV with columns: `x`, `y`, `species`, `height` (optional: `z`, `fid`, `dbh`, `twig_density`, `individual_type`)
- The Grove 2.3 Python API (`the_grove_23_core`)
- `bpy` module for USD export

**Reads from `growpy.toml`**: `[forest]` (quality, growth_cycle_limit, smooth_iterations, height_interval, max_height), `[export]` (skeletal, density_variants, export_trees, skip_pve_json), `[calibration]` (align_height, align_dbh), `[unreal]`, `[helios]`, `[quality.*]` presets

**Produces**: `data/output/forest/` with per-species directories containing USD assemblies, skeletal meshes, wind JSON, twig USD files, preview images, and optional Unreal import scripts

```bash
python src/growpy/cli/generate_forest.py                # Default from growpy.toml
python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 20
python src/growpy/cli/generate_forest.py --quality medium --fast  # Fast preview
python src/growpy/cli/generate_forest.py --height-interval 5     # Multi-stage export
python src/growpy/cli/generate_forest.py --export-trees 1,2,5    # Selective export
python src/growpy/cli/generate_forest.py --import-to-unreal       # With Unreal scripts
python src/growpy/cli/generate_forest.py \
  --quality ultra --skeleton-length 2.5 --skeleton-reduce 0.5    # Skeleton tuning
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
| `--height-interval FLOAT` | Multi-stage export at height intervals (meters) |
| `--max-height FLOAT` | Cap tree heights at this value in meters (0 = no limit) |
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

### Yield Table Ingestion (`ingest_yield_tables.py`)

Populates the local yield table store from external providers (pylometree). Run once before Step 3 if you want calibration.

**Requires**:

- `pylometree` package installed (provides yield table providers)
- Optional: parametric model JSON files in `data/input/yield_models/`
- `src/growpy/config/tree_asset_lookup.csv` (species mapping)

**Reads from `growpy.toml`**: `[yield_sources] store_dir`

**Produces**: `data/input/yield_tables/store/` (normalized CSVs + manifest.csv)

```bash
python -m growpy.cli.ingest_yield_tables                # All available providers
python -m growpy.cli.ingest_yield_tables --list-providers
python -m growpy.cli.ingest_yield_tables --providers forest_elements et_nwfva
python -m growpy.cli.ingest_yield_tables --clean         # Clear store first
```

**Flags**: `--list-providers`, `--providers NAME [NAME ...]`, `--clean`, `--verbose`

### Generate Dataset CSVs (`generate_dataset_csvs.py`)

Generates input CSV files for dataset production. Reads species metadata (Max Height, Competition Spacing) from `tree_asset_lookup.csv` and creates per-species merged CSVs plus an all-species CSV.

**Requires**:

- `src/growpy/config/tree_asset_lookup.csv` with `Max Height` and `Competition Spacing` columns populated for target species

**Produces**: `data/input/dataset/` containing:
- `all_species.csv` -- one row per species, for pipeline steps 1-3
- `{species}_merged.csv` -- open-grown tree (fid=1 at x=100) + competition cluster (fid=2 at origin + 6 hex neighbors at fid=101-106)

```bash
python src/growpy/cli/generate_dataset_csvs.py                      # Default output dir
python src/growpy/cli/generate_dataset_csvs.py --output-dir custom/  # Custom dir
python src/growpy/cli/generate_dataset_csvs.py --density reduced     # 50% twig density
```

**Flags**: `--output-dir PATH`, `--density {full,reduced,bare}`, `-v`

### Produce Dataset (`produce_dataset.py`)

Batch runner that iterates merged CSV files and calls `generate_forest.py` for each species. Exports open-grown (fid=1) and competition center (fid=2) trees per species.

**Requires**:

- Steps 1-3 completed for all dataset species (using `all_species.csv`)
- Merged CSV files in `data/input/dataset/` (from `generate_dataset_csvs.py`)
- `bpy` module available in current environment
- `growpy.toml` configured for dataset production (see [Dataset Production](#dataset-production))

**Produces**: output in `data/output/forest/` (or configured output_dir) with per-species directories

```bash
python src/growpy/cli/produce_dataset.py --species "European Beech"  # Single species
python src/growpy/cli/produce_dataset.py --pilot                      # Beech + Spruce
python src/growpy/cli/produce_dataset.py --all                        # All 16 species
python src/growpy/cli/produce_dataset.py --all --dry-run              # Preview commands
python src/growpy/cli/produce_dataset.py --all --workers 2            # Limit parallelism
python src/growpy/cli/produce_dataset.py --all --max-height 15        # Cap heights for testing
```

**Flags**: `--species TEXT`, `--pilot`, `--all`, `--list`, `--dry-run`, `--max-height FLOAT`, `--workers INT`, `-v`

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

### Diagnostic Tools

Diagnostic and debugging scripts live in `src/growpy/tools/` (separate from the core pipeline):

- `growpy-analyze-usda` -- inspect USD assembly structure and validate export
- `growpy-diagnose-growth` -- debug growth simulation issues per species
- `growpy-visualize-tree` -- render 2D side-view images of exported tree geometry

## Dataset Production

The dataset pipeline produces a systematic set of tree assets (16 species, 2 individuals each, multiple growth stages, 3 density variants). See [Dataset Specification](docs/dataset-specification.md) for the full specification and species catalog.

### Prerequisites

Before producing the dataset, ensure:

- The Grove 2.3 is installed at `src/the_grove_23/`
- The `growpy` conda environment is active with `pip install -e .`
- `tree_asset_lookup.csv` has `Max Height` and `Competition Spacing` columns populated for target species
- Yield table store is populated (optional but recommended for calibrated growth)

### Step 0: Generate Dataset Input CSVs

Generate the per-species merged CSVs and the all-species CSV from species metadata:

```bash
python src/growpy/cli/generate_dataset_csvs.py
```

This reads `Max Height` and `Competition Spacing` from `tree_asset_lookup.csv` and produces:
- `data/input/dataset/all_species.csv` -- one row per species, used for steps 1-3
- `data/input/dataset/{species}_merged.csv` -- per-species simulation layout (open-grown at x=100, competition cluster at origin with 6 hexagonal neighbors)

### Step 1-3: Prepare All Species Assets

Run the core pipeline steps for all dataset species using the generated `all_species.csv`:

```bash
python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/convert_twigs.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv
```

After this, verify:
- `data/assets/presets/` contains `.seed.json` files for all 16 species
- `data/assets/twigs/` contains converted `.usda` twig files
- `data/assets/growth_models/` contains growth model JSON files for all 16 species
- Calibration plots in `data/output/growth_comparison/` look reasonable (if calibration enabled)

### Step 4: Configure `growpy.toml` for Dataset

Edit `src/growpy/growpy.toml` for dataset production settings:

```toml
[forest]
quality = "high"
height_interval = 5          # Export at 5m height increments
growth_cycle_limit = 125     # Enough cycles for tallest species

[export]
density_variants = ["full", "reduced", "bare"]  # 3 density levels per stage
skeletal = true
skip_pve_json = true
skip_validation = true
```

### Step 5: Produce the Dataset

Run for all species (parallel by default):

```bash
python src/growpy/cli/produce_dataset.py --all
```

Or start with a pilot run (European beech + Norway spruce):

```bash
python src/growpy/cli/produce_dataset.py --pilot
```

**What `produce_dataset.py` does per species**: For each merged CSV, it runs `generate_forest.py` with `--export-trees 1,2`:
- **fid=1** = open-grown tree (isolated at x=100, no light competition)
- **fid=2** = competition center tree (surrounded by 6 hexagonal neighbors)
- **fid=101-106** = neighbor trees that participate in growth simulation (light competition, shading) but are not exported

With `density_variants` active, each exported tree gets `full`, `reduced`, and `bare` variants at every height milestone -- all from a single growth simulation.

### Quick Reference

```bash
# Full dataset production from scratch:
conda activate growpy
python src/growpy/cli/generate_dataset_csvs.py           # Step 0: generate input CSVs
python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv   # Step 1
python src/growpy/cli/convert_twigs.py --csv data/input/dataset/all_species.csv    # Step 2
python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv  # Step 3
# Edit growpy.toml: set density_variants, height_interval, quality
python src/growpy/cli/produce_dataset.py --all            # Step 4: produce all species
```

## Data Folders

The `data/` directory holds all pipeline inputs and outputs:

```text
data/
├── input/                     # Your CSV files with tree positions and species
│   ├── test.csv              # Default input (configured in growpy.toml: csv_file)
│   ├── yield_tables/         # Local yield table CSVs (age,height,dbh)
│   │   └── store/            # Ingested store from pylometree-ingest
│   └── yield_models/         # Parametric JSON models (pylometree input)
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

### Yield Table Calibration

- Yield tables provided by [pylometree](../pylometree/) (separate package)
- Resolution chain: local CSV -> ingested store (no runtime API calls)
- Height calibration via per-cycle `grow_length` adjustment
- DBH calibration via height-DBH allometric model with radial scaling at export
- Species without yield data fall back to uncalibrated Grove output
- Run `pylometree-ingest` or `python -m growpy.cli.ingest_yield_tables` to populate the store

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
