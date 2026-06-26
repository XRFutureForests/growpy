# GrowPy - Procedural Forest Generation

Procedural tree generation using The Grove 2.3, optimized for Unreal Engine 5 Nanite workflows. GrowPy provides a complete pipeline from species configuration to USD export, with yield-table-calibrated growth models and multi-species light competition.

## Overview

GrowPy wraps The Grove 2.3 tree modeling API in a Python pipeline that:

- Simulates multi-species forests with inter-tree light competition
- Calibrates growth against forestry yield tables (height and DBH)
- Exports USD Nanite Assemblies with skeletal animation support for UE 5.7+
- Produces systematic datasets covering 11 southern German tree species

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

**Important:** No separate Blender installation is required. The `bpy` module (Blender's Python API) is installed via conda and includes all dependencies including USD tools (`pxr`). All USD export functionality works out of the box through `bpy`.

### 2. Install the package

```bash
pip install -e .
```

### 3. (Optional) Initialize project configuration

Copy starter TOML files and species lookup CSV to a local `config/` directory:

```bash
growpy-init-config                    # Copies to ./config (default)
growpy-init-config --target ./my_config  # Copies to custom directory
```

These files override the built-in defaults. All `config/*.toml` files are deep-merged in sorted order, then CLI arguments override them. See [docs/reference/configuration.md](docs/reference/configuration.md).

### 4. Add The Grove 2.3

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
python -c "import the_grove_23_core as gc; print('Grove API ready')"
```

## Configuration

All CLI scripts read defaults from the TOML files in [`config/`](config/) (user-editable; bootstrapped from the packaged templates in `src/growpy/config/templates/` via `growpy-init-config`). CLI arguments override TOML values. Resolution order: dataclass defaults -> `config/*.toml` (deep-merged in sorted order) -> CLI arguments.

Key configuration files in `config/`:

| Section | Controls |
|---------|----------|
| `[general]` | Random seed, default CSV, output directory, verbosity, profiling |
| `[assets]` | Grove installation path, texture resizing |
| `[twigs]` | Mesh densification, alpha trimming, smoothing, interior decimation |
| `[growth_models]` | Simulation cycles, seeds, plateau detection, timeouts |
| `[calibration]` | Yield table alignment (height, DBH), plot generation |
| `[yield_sources]` | Ingested yield table store path, region filter |
| `[forest]` | Quality preset, growth cycle limit, height interval, max height |
| `[quality.*]` | Named presets (mesh resolution, skeleton parameters) |
| `[export]` | USD format, skeletal/static mesh, twig density, density variants |
| `[unreal]` | Import script generation, Unreal content path |
| `[helios]` | OBJ export, scene XML, mesh simplification |
| `[density_variant.*]` | Named density variants (twig_density, build_cutoff) |

Species-to-asset mapping is defined in `config/tree_asset_lookup.csv` (the Grove species catalogue; the `Dataset` column selects which species the dataset pipeline produces). Quality presets (`high`, `helios`, `debug`) are defined in `quality.toml` under `[quality.*]` sections.

For the full CLI flags reference, see [docs/reference/cli-reference.md](docs/reference/cli-reference.md).

## Core Pipeline

The pipeline has 4 sequential steps. Each reads defaults from the `config/*.toml` files and can run without arguments.

```
prepare_assets -> convert_twigs -> create_growth_models -> generate_forest
```

Yield table ingestion is integrated into Step 3 via the `--ingest-yield-tables` flag (see Step 3 below).

### Step 1: Prepare assets

Copies and standardizes presets, textures, and twigs from The Grove 2.3 into `data/assets/`. CSV-driven: only processes species listed in the input CSV.

```bash
python src/growpy/cli/prepare_assets.py                # Species from default CSV
python src/growpy/cli/prepare_assets.py --csv my.csv   # Species from custom CSV
python src/growpy/cli/prepare_assets.py --all           # All 60 Grove species
```

**Produces:** `data/assets/presets/`, `data/assets/textures/`, `data/assets/twigs/`

### Step 2: Convert twigs

Converts twig `.blend` files to USD with optional mesh densification for Nanite silhouettes.

```bash
python src/growpy/cli/convert_twigs.py                  # Defaults from config/*.toml
python src/growpy/cli/convert_twigs.py --no-densify     # Raw export without densification
python src/growpy/cli/convert_twigs.py --alpha-trim 0.5 # Custom alpha threshold
```

Densification includes alpha-based silhouette trimming, boundary smoothing, and interior decimation. Per-twig parameters are configurable via `[twigs]` in `twigs.toml`.

**Produces:** Two USD variants per twig in `data/assets/twigs/`: `*_skeletal.usda` (no materials, with skeleton) and `*_static.usda` (with materials, no skeleton)

### Step 3: Create growth models

Simulates species growth curves and generates height-to-age prediction models. When `[calibration] enabled = true`, aligns growth to yield tables and re-simulates with calibration applied.

```bash
python src/growpy/cli/create_growth_models.py                                  # Defaults from config/*.toml
python src/growpy/cli/create_growth_models.py --species "European beech"       # Single species
python src/growpy/cli/create_growth_models.py --seeds 3 --cycles 35            # Robust curves
python src/growpy/cli/create_growth_models.py --ingest-yield-tables            # Populate yield table store first
python src/growpy/cli/create_growth_models.py --ingest-yield-tables --clean-store  # Wipe and re-ingest
```

**Produces:** `data/assets/growth_models/` (JSON models), calibration data in `.seed.json` files, comparison plots in `data/output/growth_comparison/`

### Step 4: Generate forest

Multi-species forest simulation from CSV with USD Nanite assembly export.

```bash
python src/growpy/cli/generate_forest.py                                  # Defaults from config/*.toml
python src/growpy/cli/generate_forest.py --quality high                    # Quality preset
python src/growpy/cli/generate_forest.py --height-interval 5               # Multi-stage export
python src/growpy/cli/generate_forest.py --export-obj --helios-scene       # Helios++ OBJ + scene XML
python src/growpy/cli/generate_forest.py --skeleton-reduce 0.5             # Override skeleton params
python src/growpy/cli/generate_forest.py --export-trees 1,2                # Export specific trees only
python src/growpy/cli/generate_forest.py --preset-override drop_decay=0.1  # Override preset params
```

**Input CSV format:** `x`, `y`, `species`, `height` columns (optional: `z`, `fid`, `dbh`, `twig_density`, `individual_type`)

**Produces:** `data/output/forest/` with per-species directories containing USD assemblies, skeletal meshes, twig USD files, wind data, preview images, PVE presets, and optional Unreal import scripts or Helios++ OBJ/scene files

Quality presets are defined in `quality.toml` under `[quality.*]` sections:

| Preset | Vertices | Skeleton | Use Case |
|--------|----------|----------|----------|
| high | 16 | length=0.75, reduce=0.333 | USD Nanite export (default) |
| helios | 9 | length=2.0, reduce=0.8 | OBJ export for LiDAR simulation |
| debug | 8 | length=2.0, reduce=0.5 | Quick iteration |

Skeleton parameters (`--skeleton-length`, `--skeleton-reduce`, `--skeleton-bias`, `--skeleton-connected`) can be overridden independently of the quality preset on the command line.

### Helios++ OBJ export

GrowPy can export [Helios++](https://github.com/3dgeo-heidelberg/helios) compatible Wavefront OBJ files for LiDAR point cloud simulation. Enable via CLI flags or `[helios]` in `helios.toml`:

```bash
python src/growpy/cli/generate_forest.py --export-obj                     # OBJ/MTL export
python src/growpy/cli/generate_forest.py --export-obj --helios-scene       # + Helios scene XML
python src/growpy/cli/generate_forest.py --export-obj --individual-obj     # Per-tree OBJ files
python src/growpy/cli/generate_forest.py --export-obj --obj-up-axis z      # Z-up coordinates
```

The OBJ exporter converts USD assemblies to Wavefront OBJ with baked twig instances and material classification (`bark`, `twig_wood`, `twig_leaf`). Material-aware mesh simplification can be configured in `[helios.simplification]` to reduce file size while preserving leaf area for LAI accuracy. The Helios scene XML positions trees at their CSV coordinates using `<part>` entries with translate filters.

```toml
[helios]
export_obj = true
helios_scene = true
obj_up_axis = "z"

[helios.simplification]
enabled = true
bark = 0.2
leaf = 0.5
```

## Dataset Production

The dataset pipeline produces a systematic set of tree assets: 11 southern German species (4 conifer + 7 broadleaf), 2 individuals each (open-grown and competition), multiple height stages, 3 density variants. Species selection focuses on the dominant trees of Bavaria and Baden-Wuerttemberg. See [Dataset Specification](docs/dataset/dataset-specification.md) for species catalog and full details.

### Preparation

Generate input CSVs from species metadata in `tree_asset_lookup.csv`:

```bash
python src/growpy/cli/dataset_pipeline.py --generate-csvs             # Generate per-species CSVs
```

This produces `data/input/dataset/all_species.csv` (one row per species for steps 1-3) and `{species}_merged.csv` files (open-grown + competition layout per species).

### Run pipeline for all species

```bash
# All steps in one command (recommended):
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables

# Or run individual steps:
python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/convert_twigs.py --csv data/input/dataset/all_species.csv
python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv --ingest-yield-tables
```

### Configure the dataset run

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

# Optional: Helios++ OBJ export alongside USD
[helios]
export_obj = false
helios_scene = false
```

### Produce the dataset

```bash
python src/growpy/cli/dataset_pipeline.py --pilot       # European Beech + Norway Spruce
python src/growpy/cli/dataset_pipeline.py --all         # All 11 dataset species
python src/growpy/cli/dataset_pipeline.py --all --dry-run  # Preview commands only
python src/growpy/cli/dataset_pipeline.py --list        # Show available species
python src/growpy/cli/dataset_pipeline.py --all --workers 4  # Parallel species processing
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables  # Full pipeline with yield tables
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables --clean  # Full clean re-run
```

Each species produces two exported trees:

- **fid=1** -- open-grown (isolated, no light competition)
- **fid=2** -- competition center (surrounded by 3 equilateral triangle neighbors)

Neighbor trees (fid=101-103) participate in growth simulation but are not exported. With `density_variants` active, each tree gets `full`, `reduced`, and `bare` variants at every height milestone.

### Quick reference (full dataset from scratch)

```bash
conda activate growpy
python src/growpy/cli/dataset_pipeline.py --generate-csvs
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables

# Or with a full clean re-run (wipe outputs and yield table store):
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables --clean
```

## Output Structure

Forest generation creates organized output ready for Unreal import:

```text
data/output/forest/
├── species_name/
│   └── tree_0001/
│       ├── species_name_assembly.usda                # Nanite assembly (or .usdc)
│       ├── species_name_0001_skeletal.usda            # Tree mesh with skeleton
│       ├── species_name_0001_DynamicWind.json         # Wind animation data
│       ├── species_name_0001.json                     # PVE preset (optional)
│       ├── species_name_0001_preview.png              # 2D preview image
│       └── twigs/                                     # Twig USD files
│           ├── species_name_foliage_apical_skeletal.usda
│           └── species_name_foliage_lateral_skeletal.usda
├── helios/                                            # Optional (--export-obj)
│   ├── forest.obj                                     # Combined OBJ (all trees)
│   ├── forest.mtl                                     # Material definitions
│   ├── helios_scene.xml                               # Helios++ scene (--helios-scene)
│   └── individual/                                    # Optional (--individual-obj)
│       └── species_name_0001.obj
└── unreal_scripts/                                    # Optional (--import-to-unreal)
    ├── import_batch_00_instances.py
    ├── import_batch_01_species.py
    ├── ...
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

See [PVE Preset Workflow](docs/guides/pve-preset-workflow.md) for Procedural Vegetation Editor integration.

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
│   │   └── (config templates live in config/templates/)
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

See [docs/reference/testing.md](docs/reference/testing.md) for coverage details.

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
| [Quickstart](docs/quickstart.md) | Fastest path from install to working forest |
| [Dataset Workflow](docs/guides/dataset-workflow.md) | Full multi-species dataset production |
| [Forest Generation](docs/guides/forest-generation.md) | Manual single-forest run from a CSV |
| [Configuration](docs/reference/configuration.md) | All TOML keys + species lookup CSV columns |
| [CLI Reference](docs/reference/cli-reference.md) | Complete CLI flags and options for all scripts |
| [Pipeline Overview](docs/architecture/pipeline-overview.md) | Package architecture and data flow |
| [Processing Logic](docs/architecture/processing-logic.md) | Per-step algorithm walkthrough |
| [Dataset Specification](docs/dataset/dataset-specification.md) | Species catalog and dataset production plan |
| [Dataset Overview](docs/dataset/dataset-overview.md) | Production status and preview gallery |
| [Helios Export](docs/guides/helios-export.md) | OBJ/MTL export for Helios++ LiDAR |
| [Unreal Import](docs/guides/unreal-import.md) | UE 5.7+ import, wind, PVE, Nanite |
| [PVE Preset Workflow](docs/guides/pve-preset-workflow.md) | Procedural Vegetation Editor integration |
| [Grove Preset Reference](docs/reference/grove-preset-reference.md) | Growth parameters and cycle-based curves |
| [Naming Conventions](docs/reference/naming-conventions.md) | Species, file, and directory naming standards |
| [Coordinate Systems](docs/reference/coordinate-systems.md) | Grove, Blender, Unreal, PVE transforms |
| [PVE Attribute Reference](docs/reference/pve-attribute-reference.md) | PVE attributes and Grove mapping |
| [Yield Table Calibration](docs/reference/yield-table-calibration.md) | Calibration methodology |
| [USD Builder](docs/reference/usd-builder.md) | USD export internals |
| [Module Reference](docs/architecture/module-reference.md) | Per-module purpose, functions, inputs, outputs |
| [Grove 2.3 API](docs/reference/vendor/the-grove/) | Grove core API documentation |

## License

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

This project is licensed under the
[Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).
You may use, share, and adapt it for **non-commercial** purposes with attribution;
commercial use is not permitted. See [LICENSE](LICENSE). Note: CC BY-NC is not an
OSI-approved license — this is intentional, to keep the project non-commercial.

**The Grove 2.3** is a separate commercial product with its own license. Ensure
you have proper licensing from [The Grove](https://www.thegrove3d.com) before use.

## Citation

<!-- After the first Zenodo release, replace XXXXXXX and uncomment the badge. -->
<!-- [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX) -->

If you use GrowPy or its outputs in a publication, please cite it. See
[CITATION.cff](CITATION.cff) for machine-readable metadata, or:

> Sperlich, M. (2026). GrowPy: Procedural Forest Generation for Unreal Engine.
> University of Freiburg.
> https://gitlab.uni-freiburg.de/xr-future-forests-lab/growpy

---

**Simplified. Clean. Ready for Unreal Engine.**
