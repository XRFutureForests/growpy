# GrowPy - Procedural Forest Generation

Procedural tree generation using The Grove 2.3, optimized for Unreal Engine 5 Nanite workflows. GrowPy provides a complete pipeline from species configuration to USD export, with yield-table-calibrated growth models and multi-species light competition.

## Overview

GrowPy wraps The Grove 2.3 tree modeling API in a Python pipeline that:

- Simulates multi-species forests with inter-tree light competition
- Calibrates growth against forestry yield tables (height and DBH)
- Exports USD Nanite Assemblies with skeletal animation support for UE 5.7+
- Produces systematic datasets covering 16 southern German tree species

**Key concepts:**

| Level | Description |
|-------|-------------|
| Forest | Multi-species collection with light competition simulation |
| Grove | Species-specific tree group with shared growth model |
| Tree | Individual instance with mesh + skeleton for wind animation |
| Twig | Reusable USD foliage asset with Nanite-optimized silhouettes |

## Installation

### 1. Create the conda environment

```bash
conda env create -f environment.yml
conda activate growpy
```

### 2. Install the package

```bash
pip install -e .
```

### 3. Add The Grove 2.3

The Grove is commercial software ([thegrove3d.com](https://www.thegrove3d.com)) and not included in the repository. Copy or symlink your licensed installation:

```bash
# Linux/Mac
cp -r /path/to/the_grove_23 src/the_grove_23

# Windows
mklink /D src\the_grove_23 C:\path\to\the_grove_23
```

Expected structure inside `src/the_grove_23/`:

```text
addons/          # Blender/Houdini add-ons
documentation/   # API reference HTML
modules/         # Python API (the_grove_23_core)
presets/         # Species .seed.json files
textures/        # Bark textures
twigs/           # Twig .blend files
```

### Verify installation

```bash
conda activate growpy
python -c "import the_grove_23_core.grove_core as gc; print('Grove API ready')"
```

## Configuration

All CLI scripts read defaults from [`src/growpy/growpy.toml`](src/growpy/growpy.toml). CLI arguments override TOML values. Resolution order: dataclass defaults -> growpy.toml -> CLI arguments.

Key sections in `growpy.toml`:

| Section | Controls |
|---------|----------|
| `[general]` | Random seed, default CSV, output directory, verbosity |
| `[assets]` | Grove installation path, texture resizing |
| `[twigs]` | Mesh densification, alpha trimming, smoothing |
| `[growth_models]` | Simulation cycles, seeds, plateau detection |
| `[calibration]` | Yield table alignment (height, DBH) |
| `[yield_sources]` | Ingested yield table store path |

Species-to-asset mapping is defined in `src/growpy/config/tree_asset_lookup.csv` (57 Grove species). Quality presets (ultra, high, medium, low, performance) control mesh resolution and skeleton detail.

For the full CLI flags reference, see [docs/cli-reference.md](docs/cli-reference.md).

## Core Pipeline

The pipeline has 4 sequential steps. Each reads from `growpy.toml` and can run without arguments.

```
prepare_assets -> convert_twigs -> create_growth_models -> generate_forest
```

### Step 0 (optional): Ingest yield tables

Populates the local yield table store from pylometree providers. Run once before Step 3 to enable growth calibration. No dependency on Grove assets.

```bash
python src/growpy/cli/ingest_yield_tables.py
```

### Step 1: Prepare assets

Copies and standardizes presets, textures, and twigs from The Grove 2.3 into `data/assets/`. CSV-driven: only processes species listed in the input CSV.

```bash
python src/growpy/cli/prepare_assets.py                # Species from default CSV
python src/growpy/cli/prepare_assets.py --csv my.csv   # Species from custom CSV
python src/growpy/cli/prepare_assets.py --all           # All 57 Grove species
```

**Produces:** `data/assets/presets/`, `data/assets/textures/`, `data/assets/twigs/`

### Step 2: Convert twigs

Converts twig `.blend` files to USD with optional mesh densification for Nanite silhouettes.

```bash
python src/growpy/cli/convert_twigs.py                  # Default from growpy.toml
python src/growpy/cli/convert_twigs.py --no-densify     # Raw export without densification
```

**Produces:** `.usda` twig files alongside `.blend` files in `data/assets/twigs/`

### Step 3: Create growth models

Simulates species growth curves and generates height-to-age prediction models. When `[calibration] enabled = true`, aligns growth to yield tables and re-simulates with calibration applied.

```bash
python src/growpy/cli/create_growth_models.py                          # Default from growpy.toml
python src/growpy/cli/create_growth_models.py --species "European beech"  # Single species
python src/growpy/cli/create_growth_models.py --seeds 3 --cycles 35    # Robust curves
```

**Produces:** `data/assets/growth_models/` (JSON models), calibration data in `.seed.json` files, comparison plots in `data/output/growth_comparison/`

### Step 4: Generate forest

Multi-species forest simulation from CSV with USD Nanite assembly export.

```bash
python src/growpy/cli/generate_forest.py                             # Default from growpy.toml
python src/growpy/cli/generate_forest.py --quality high               # Quality preset
python src/growpy/cli/generate_forest.py --height-interval 5          # Multi-stage export
python src/growpy/cli/generate_forest.py --fast                       # Skip optional steps
```

**Input CSV format:** `x`, `y`, `species`, `height` columns (optional: `z`, `fid`, `dbh`, `twig_density`, `individual_type`)

**Produces:** `data/output/forest/` with per-species directories containing USD assemblies, skeletal meshes, twig USD files, wind data, preview images, and optional Unreal import scripts

Quality presets control mesh resolution and skeleton detail:

| Preset | Vertices | Skeleton | Use Case |
|--------|----------|----------|----------|
| ultra | 32 | Most bones | Hero trees, closeup |
| high | 24 | Many bones | Featured trees |
| medium | 16 | Balanced | Background trees |
| low | 12 | Few bones | Distant trees |
| performance | 8 | Minimal | Far background |

OBJ export for Helios++ LiDAR simulation runs automatically when `helios.export_obj = true` in growpy.toml.

## Dataset Production

The dataset pipeline produces a systematic set of tree assets: 16 species, 2 individuals each (open-grown and competition), multiple height stages, 3 density variants (~522 models total). See [Dataset Specification](docs/dataset-specification.md) for species catalog and full details.

### Preparation

Generate input CSVs from species metadata in `tree_asset_lookup.csv`:

```bash
python src/growpy/cli/ingest_yield_tables.py                         # Populate yield table store
python src/growpy/cli/generate_dataset_csvs.py                       # Generate per-species CSVs
```

This produces `data/input/dataset/all_species.csv` (one row per species for steps 1-3) and `{species}_merged.csv` files (open-grown + competition layout per species).

### Run pipeline for all species

```bash
python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/convert_twigs.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv
```

### Configure growpy.toml for dataset

```toml
[forest]
quality = "high"
height_interval = 5
growth_cycle_limit = 125

[export]
density_variants = ["full", "reduced", "bare"]
skeletal = true
skip_pve_json = true
skip_validation = true
```

### Produce the dataset

```bash
python src/growpy/cli/produce_dataset.py --pilot    # European Beech + Norway Spruce
python src/growpy/cli/produce_dataset.py --all       # All 16 species
python src/growpy/cli/produce_dataset.py --all --dry-run  # Preview commands only
```

Each species produces two exported trees:

- **fid=1** -- open-grown (isolated, no light competition)
- **fid=2** -- competition center (surrounded by 6 hexagonal neighbors)

Neighbor trees (fid=101-106) participate in growth simulation but are not exported. With `density_variants` active, each tree gets `full`, `reduced`, and `bare` variants at every height milestone.

### Quick reference (full dataset from scratch)

```bash
conda activate growpy
python src/growpy/cli/ingest_yield_tables.py
python src/growpy/cli/generate_dataset_csvs.py
python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/convert_twigs.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv
# Configure growpy.toml (height_interval, density_variants, quality)
python src/growpy/cli/produce_dataset.py --all
```

## Output Structure

Forest generation creates organized output ready for Unreal import:

```text
data/output/forest/
├── species_name/
│   └── tree_0001/
│       ├── species_name_assembly.usda                # Nanite assembly
│       ├── species_name_0001_skeletal.usda            # Tree mesh with skeleton
│       ├── species_name_0001_DynamicWind.json         # Wind animation data
│       ├── species_name_0001.json                     # PVE preset (optional)
│       └── twigs/                                     # Twig USD files
│           ├── species_name_foliage_apical_skeletal.usda
│           └── species_name_foliage_lateral_skeletal.usda
└── unreal_scripts/                                    # Optional (--import-to-unreal)
    ├── import_forest.py
    └── clean_assets.py
```

Multi-stage mode adds cycle/height/dbh to filenames: `{species}_c{cycle}_h{height}_d{dbh}_assembly.usda`

## Unreal Engine Import

### Basic import

1. Copy the output folder to the Unreal Content Browser
2. USD files auto-import as Nanite Assemblies (UE 5.7+)
3. Trees and twigs are organized by species in individual folders

Trees and twigs export as separate assets, assembled in Unreal via PointInstancer.

### Wind animation

Wind data is embedded directly in the USD skeleton. For older workflows, each tree also exports a `*_DynamicWind.json` file that can be imported via the right-click scripted asset action on the SkeletalMesh.

### Required plugins

- USD Importer
- Nanite (experimental)
- Nanite Foliage (experimental)
- Dynamic Wind (experimental)
- Python Editor Script Plugin (for auto-import scripts)

### Project settings

- **USD Importer**: Enable "Use Nanite" for automatic Nanite mesh generation
- **Remote Execution**: Enable for running Python scripts from VSCode

See [PVE Preset Workflow](docs/pve-preset-workflow.md) for Procedural Vegetation Editor integration.

## Project Structure

```text
growpy/
├── src/
│   ├── growpy/                    # Main Python package (see src/growpy/README.md)
│   │   ├── cli/                   # Pipeline CLI scripts (steps 1-4 + dataset tools)
│   │   ├── config/                # Configuration, quality presets, species lookup
│   │   ├── core/                  # Forest/Grove/Tree/Skeleton simulation
│   │   ├── io/                    # USD/OBJ export, wind JSON, PVE mapping
│   │   ├── tools/                 # Diagnostic tools (analyze_usda, diagnose_growth, visualize_tree)
│   │   ├── tests/                 # Test suite (pytest)
│   │   ├── utils/                 # Analysis, profiling, plotting
│   │   └── growpy.toml            # Central configuration
│   └── the_grove_23/              # Grove 2.3 installation (not in repo)
├── data/
│   ├── input/                     # CSV files, yield tables, dataset templates
│   ├── assets/                    # Pipeline output from steps 1-3
│   └── output/                    # Generated forests (step 4 output)
├── docs/                          # Documentation (see below)
├── pyproject.toml                 # Python package configuration
└── environment.yml                # Conda environment definition
```

## Testing

```bash
conda activate growpy
python -m pytest src/growpy/tests/ -v
python -m pytest src/growpy/tests/test_skeleton.py -v   # Single module
```

See [src/growpy/tests/README.md](src/growpy/tests/README.md) for coverage details.

## Troubleshooting

### Grove API import issues

Ensure `PYTHONPATH` includes `./src` and `./src/the_grove_23/modules`, or use `pip install -e .` which handles this automatically.

```bash
# Windows PowerShell
$env:PYTHONPATH=".\src;.\src\the_grove_23\modules"

# Linux/Mac
export PYTHONPATH="./src:./src/the_grove_23/modules"
```

### bpy module not found

```bash
pip install bpy
```

### Bone count exceeds Unreal limit

Unreal Engine has a 32,767 bone limit. Use skeleton simplification:

```bash
python src/growpy/cli/generate_forest.py --skeleton-reduce 0.5 --skeleton-length 2.5
```

`--skeleton-reduce` is the most effective parameter for reducing bone count.

## Documentation

| Document | Description |
|----------|-------------|
| [CLI Reference](docs/cli-reference.md) | Complete CLI flags and options for all scripts |
| [Functional Description](docs/growpy-functional-description.md) | Package architecture and data flow |
| [Dataset Specification](docs/dataset-specification.md) | Species catalog and dataset production plan |
| [Dataset Overview](docs/dataset-overview.md) | Production status and preview gallery |
| [Grove Preset Reference](docs/grove-preset-reference.md) | Growth parameters and cycle-based curves |
| [Naming Conventions](docs/naming-conventions.md) | Species, file, and directory naming standards |
| [Coordinate Systems](docs/coordinate-systems.md) | Grove, Blender, Unreal, PVE transforms |
| [PVE Preset Workflow](docs/pve-preset-workflow.md) | Procedural Vegetation Editor integration |
| [PVE Attribute Reference](docs/pve-attribute-reference.md) | PVE attributes and Grove mapping |
| [Yield Table Calibration](docs/yield-table-calibration.md) | Calibration methodology |
| [USD Builder](docs/usd-builder.md) | USD export internals |
| [Module Audit](docs/module-audit.md) | Module inventory and dependencies |
| [Grove 2.3 API](docs/the_grove/) | Grove core API documentation |

## License

This project uses The Grove 2.3, a commercial product. Ensure you have proper licensing before use.

This project follows a template-based structure. Key guidelines:

- Python files use snake_case
- All scripts in `src/growpy/cli/` directory
- Configuration in `src/growpy/config/`
- Documentation in `docs/`
- Use conda/mamba for environment management (never pip venv)

---

**Simplified. Clean. Ready for Unreal Engine.**
