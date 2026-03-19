# GrowPy Package

Python package for procedural forest generation using The Grove 2.3 with USD export for Unreal Engine 5 Nanite workflows.

For installation, pipeline usage, and dataset production, see the [project README](../../README.md).

## Package Structure

```text
growpy/
├── __init__.py        # Public API (create_grove, create_forest, export functions)
├── growpy.toml        # Central configuration (all CLI defaults)
├── config/            # Configuration management
│   ├── core.py                  # GrowPyConfig dataclass, TOML loading
│   ├── paths.py                 # Path resolution, twig lookup
│   ├── preset_overrides.py      # Per-cycle overrides, target DBH loading
│   ├── pve_species_overrides.py # PVE species-specific config
│   └── quality.py               # Quality presets (ultra/high/medium/low/performance)
├── core/              # Simulation logic
│   ├── forest.py                # Forest creation, multi-species growth simulation
│   └── grove.py                 # Grove API wrapper, single-species growth
├── io/                # Export and file I/O
│   ├── usd_builder.py           # USD assembly construction
│   ├── usd_export.py            # Tree USD export with skeleton
│   ├── obj_export.py            # OBJ/MTL export for Helios++ LiDAR
│   ├── twig_export.py           # Twig .blend to USD conversion
│   ├── preview.py               # Preview image generation
│   ├── pve_grove_mapper.py      # PVE preset JSON generation
│   ├── texture_utils.py         # Texture processing and resizing
│   └── unreal_scripts.py        # Unreal import/cleanup script generation
├── cli/               # Pipeline entry points
│   ├── prepare_assets.py        # Step 1: Copy Grove assets
│   ├── convert_twigs.py         # Step 2: Twig .blend to USD
│   ├── create_growth_models.py  # Step 3: Growth models + calibration
│   ├── generate_forest.py       # Step 4: Forest simulation + export
│   ├── ingest_yield_tables.py   # Yield table store ingestion
│   ├── generate_dataset_csvs.py # Dataset CSV generation
│   └── produce_dataset.py       # Batch dataset production
├── tools/             # Diagnostic utilities (not part of core pipeline)
│   ├── analyze_usda.py          # USD assembly inspection
│   ├── diagnose_growth.py       # Growth simulation debugging
│   └── visualize_tree.py        # 2D tree rendering
├── utils/             # Shared utilities
│   ├── analysis.py              # SpeciesGrowthAnalyzer
│   ├── naming.py                # Species/file name standardization
│   ├── plotting.py              # Calibration comparison plots
│   ├── profiling.py             # ProfileTimer for pipeline timing
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
from growpy.utils.dependencies import gc

grove = create_grove("European beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

skeletons = grove.build_skeletons()
bones = grove.tag_bone_id(2.0, 0.16, 0.5, True)
models = grove.build_models({"resolution": 16})
```

### USD export

```python
from growpy import export_tree_as_usd
from pathlib import Path

export_tree_as_usd(
    grove=grove,
    output_path=Path("output/beech.usda"),
    species_name="European beech",
)
```

### Twig export

```python
from growpy import export_twigs_from_blend
from pathlib import Path

exported = export_twigs_from_blend(
    Path("data/assets/twigs/european_beech_twig/EuropeanBeechTwig.blend"),
    Path("output/twigs/"),
)
```

### Configuration

```python
from growpy import get_config

config = get_config()  # Loads from growpy.toml
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
- **Configuration over code**: `growpy.toml` centralizes all defaults. CLI args override TOML. Quality presets bundle related parameters.
- **CSV-driven**: Species selection and forest layout defined in CSV files, not hardcoded.
- **Separation of concerns**: CLI layer (orchestration) / core layer (simulation) / IO layer (export) / config layer (parameters).

### External dependencies

- **The Grove 2.3** (`the_grove_23_core`): C++ tree simulation via Python bindings
- **bpy**: Blender Python API for mesh manipulation and USD export
- **pxr** (USD): Bundled with bpy, used for USD file construction

## Detailed Documentation

| Document | Description |
|----------|-------------|
| [CLI Reference](../../docs/cli-reference.md) | Complete CLI flags for all scripts |
| [Functional Description](../../docs/growpy-functional-description.md) | Architecture and data flow |
| [Grove Preset Reference](../../docs/grove-preset-reference.md) | Growth parameters |
| [Coordinate Systems](../../docs/coordinate-systems.md) | Grove/Blender/Unreal transforms |
| [Naming Conventions](../../docs/naming-conventions.md) | Species and file naming |
| [USD Builder](../../docs/usd-builder.md) | USD export internals |
| [Module Audit](../../docs/module-audit.md) | Module inventory and dependencies |
| [Grove API](../../docs/the_grove/) | Grove core API documentation |
