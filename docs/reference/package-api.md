# GrowPy Package API

Python package for procedural forest generation using The Grove 2.3 with USD export for Unreal Engine 5 Nanite workflows. This document is the Python-API reference for the `growpy` package.

For installation, pipeline usage, and dataset production, see the [project README](../README.md).

## Package Structure

```text
growpy/
├── __init__.py        # Public API (create_grove, create_forest, export functions)
├── config/            # Configuration management
│   ├── core.py                  # GrowPyConfig dataclass, TOML loading
│   ├── paths.py                 # Path resolution, twig lookup
│   ├── preset_overrides.py      # Per-cycle overrides, target DBH loading
│   ├── pve_species_overrides.py # PVE species-specific config
│   └── quality.py               # Quality presets (ultra/high/medium/low/performance)
├── core/              # Simulation logic
│   ├── forest.py                # Forest creation, multi-species growth simulation
│   ├── grove.py                 # Grove API wrapper, single-species growth
│   ├── tree.py                  # Tree measurements (height, DBH, growth cycles)
│   ├── skeleton.py              # Skeletal mesh hierarchy for animation
│   ├── twig.py                  # Twig placement extraction and densification
│   └── orchestration/           # Dataset pipeline orchestration
├── io/                # Export and file I/O
│   ├── tree_export.py           # Tree USD export with skeleton
│   ├── assembly_export.py       # Nanite Assembly USD construction
│   ├── obj_export.py            # OBJ/MTL export for Helios++ LiDAR
│   ├── helios_scene.py          # Helios++ scene XML generation
│   ├── twig_export.py           # Twig .blend to USD conversion
│   ├── preview.py               # Preview image generation
│   ├── wind_json.py             # Dynamic wind JSON for Unreal
│   ├── pve_grove_mapper.py      # PVE preset JSON generation
│   ├── texture_utils.py         # Texture processing and resizing
│   └── unreal_scripts.py        # Unreal import/cleanup script generation
├── cli/               # Pipeline entry points
│   ├── init_config.py              # Setup: Scaffold config/ directory (optional)
│   ├── prepare_assets.py           # Step 1: Copy Grove assets
│   ├── convert_twigs.py            # Step 2: Twig .blend to USD
│   ├── create_growth_models.py     # Step 3: Growth models + calibration (+ yield ingestion)
│   ├── generate_forest.py          # Step 4: Forest simulation + export
│   └── dataset_pipeline.py         # Dataset orchestrator: all 4 steps + CSV generation
├── tools/             # Diagnostic utilities (not part of core pipeline)
│   ├── analyze_usda.py          # USD assembly inspection
│   ├── diagnose_growth.py       # Growth simulation debugging
│   └── visualize_tree.py        # 2D tree rendering
├── utils/             # Shared utilities
│   ├── analysis.py              # SpeciesGrowthAnalyzer
│   ├── export_naming.py         # Height/DBH/density filename formatting
│   ├── gbif_species.py          # GBIF species name resolution
│   ├── log.py                   # Logging configuration
│   ├── naming.py                # Species/file name standardization
│   ├── plotting.py              # Calibration comparison plots
│   ├── profiling.py             # ProfileTimer for pipeline timing
│   ├── pxr_init.py              # USD/Pixar library initialization
│   └── yield_tables.py          # Yield table loading and calibration
└── tests/             # Test suite (pytest)
```

## Python API

### Forest-level workflow

```python
from growpy import create_forest, simulate_forest_growth
import pandas as pd

forest_data = pd.read_csv("data/input/test.csv")
forest = create_forest(forest_data)
simulate_forest_growth(forest, max_cycles=10)
```

### Grove-level control

```python
from growpy import create_grove
import the_grove_23_core as gc

grove = create_grove("European beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

skeletons = grove.build_skeletons()
bones = grove.tag_bone_id(2.0, 0.16, 0.5, True)
models = grove.build_models({"resolution": 16})
```

### USD export

```python
from growpy.io.tree_export import build_tree_mesh
from pathlib import Path

build_tree_mesh(
    model=models[0],
    skeleton=skeletons[0],
    bones=bones[0],
    output_path=Path("output/beech.usda"),
    species_name="european_beech",
)
```

### Configuration

```python
from growpy import get_config

config = get_config()  # Loads from config/*.toml
print(config.csv_file, config.output_dir, config.verbose)
```

## Architecture

### Pipeline data flow

```
Grove 2.3 installation
    |
    v
prepare_assets.py --> data/assets/ (presets, textures, twigs)
    |
    v
convert_twigs.py --> data/assets/twigs/*.usda
    |
    v
create_growth_models.py --> data/assets/growth_models/*.json
    |
    v
generate_forest.py --> data/output/forest/ (USD assemblies)
```

### Key design decisions

- **Pipeline architecture**: Each step produces files consumed by later steps. Steps are independently re-runnable.
- **Configuration over code**: `config/*.toml` files centralize all defaults. CLI args override TOML. Quality presets bundle related parameters.
- **CSV-driven**: Species selection and forest layout defined in CSV files, not hardcoded.
- **Separation of concerns**: CLI layer (orchestration) / core layer (simulation) / IO layer (export) / config layer (parameters).

### External dependencies

- **The Grove 2.3** (`the_grove_23_core`): C++ tree simulation via Python bindings
- **bpy**: Blender Python API for mesh manipulation and USD export
- **pxr** (USD): Bundled with bpy, used for USD file construction

## Detailed Documentation

| Document | Description |
|----------|-------------|
| [CLI Reference](cli-reference.md) | Complete CLI flags for all scripts |
| [Pipeline Overview](../architecture/pipeline-overview.md) | Architecture and data flow |
| [Grove Preset Reference](grove-preset-reference.md) | Growth parameters |
| [Coordinate Systems](coordinate-systems.md) | Grove/Blender/Unreal transforms |
| [Naming Conventions](naming-conventions.md) | Species and file naming |
| [USD Builder](usd-builder.md) | USD export internals |
| [Module Reference](../architecture/module-reference.md) | Per-module purpose, functions, inputs, outputs |
| [Grove API](../the_grove/) | Grove core API documentation |
