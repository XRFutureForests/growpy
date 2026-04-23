# GrowPy Workspace Assessment

**Date:** 2026-04-22
**Assessor:** AI Assistant
**Workspace:** d:\Git\growpy (The Grove / GrowPy)

---

## 1. Project Overview

**GrowPy** is a procedural forest generation system that wraps The Grove 2.3 commercial tree modeling API in a Python pipeline. It produces USD Nanite Assemblies optimized for Unreal Engine 5.7+ with skeletal animation support, yield-table-calibrated growth models, and multi-species light competition simulation.

**Version:** 0.1.0 (Unreleased)
**License:** CC-BY-NC-4.0
**Python:** 3.12+
**Environment:** conda/mamba (MANDATORY)

---

## 2. Architecture Summary

### 2.1 Core Hierarchy

```
Forest (multi-species, light competition)
  └── Grove (per-species tree group)
        └── Tree (individual instance: mesh + skeleton)
              └── Twig (reusable foliage asset)
```

### 2.2 Package Structure (`src/growpy/`)

```
growpy/
├── __init__.py              # Package entry, lazy imports for heavy deps
├── constants.py             # BREAST_HEIGHT_METERS, etc.
├── config/                  # Configuration system
│   ├── core.py              # GrowPyConfig dataclass, layered TOML resolution
│   ├── paths.py             # Asset path resolution, GBIF species lookup
│   ├── preset_overrides.py  # Dynamic Grove parameter interpolation
│   ├── pve_species_overrides.py  # Per-species PVE JSON overrides
│   ├── quality.py           # Quality preset loading from TOML
│   └── templates/           # Starter config files (bootstrapped by growpy-init-config)
├── core/                    # Core simulation logic
│   ├── forest.py            # create_forest(), simulate_forest_growth()
│   ├── grove.py             # create_grove(), grow_and_build_roots()
│   ├── tree.py              # Height/DBH calculation, Chapman-Richards fitting
│   ├── twig.py              # Twig placement computation (pure Python)
│   └── skeleton.py          # Skeleton hierarchy computation (pure Python)
├── io/                      # Export modules
│   ├── forest_export.py     # Cross-format export orchestration
│   ├── usd/                 # USD export
│   │   ├── assembly_export.py   # Nanite Assembly USD (skeletal/static)
│   │   ├── tree_export.py       # Per-tree USD export
│   │   ├── twig_export.py       # Blender twig processor
│   │   ├── twig_geometry.py     # Pure twig geometry computation
│   │   ├── preview.py           # 2D preview image generation
│   │   ├── texture_utils.py     # Bump-to-normal, power-of-2 resize
│   │   └── overview.py          # Markdown overview generation
│   ├── unreal/              # UE integration
│   │   ├── pve_schema.py        # PVE preset JSON schema
│   │   ├── pve_growth_defaults.py  # Hazel-derived growth defaults
│   │   ├── pve_hierarchy_builder.py  # Branch parent/child derivation
│   │   ├── pve_foliage_extractor.py  # Grove→PVE instancer conversion
│   │   ├── pve_grove_mapper.py    # Grove→PVE mapping (main orchestrator)
│   │   ├── pve_import_script.py   # UE Python script for PVE DataAssets
│   │   ├── pve_graph_script.py    # UE Python script for PVE Graphs
│   │   ├── pve_foliage_data.py    # FoliageData.json generation
│   │   ├── nanite_voxelize_script.py
│   │   ├── ue_remote.py           # UE Python Remote Execution client
│   │   ├── unreal_scripts.py      # Import/cleanup script generation
│   │   └── wind_json.py           # DynamicWind JSON generation
│   └── helios/              # Helios++ LiDAR simulation
│       ├── helios_scene.py      # Scene XML generation
│       ├── mesh_simplify.py     # Material-aware decimation
│       └── obj_export.py        # OBJ/MTL export with baked twigs
├── pipelines/             # Pipeline orchestration
│   ├── dataset_csv_planner.py   # Merged CSV generation per species
│   ├── dataset_job_planner.py   # Species selection, CSV discovery
│   ├── forest_stages.py         # Height-based milestone pipeline
│   ├── forest_exports.py        # Fixed-cycle export pipeline
│   └── step_runner.py           # Subprocess runner for all 4 steps
├── cli/                   # CLI entry points
│   ├── init_config.py         # growpy-init-config
│   ├── prepare_assets.py      # Step 1: Copy Grove assets
│   ├── convert_twigs.py       # Step 2: .blend→USD twig conversion
│   ├── create_growth_models.py  # Step 3: Growth simulation + calibration
│   ├── generate_forest.py     # Step 4: Forest generation + export
│   └── dataset_pipeline.py    # Master orchestrator for all steps
├── blender/               # Blender integration
│   ├── grove_extract.py
│   ├── operators.py
│   ├── panels.py
│   ├── preferences.py
│   ├── skeleton_builder.py
│   ├── twig_converter.py
│   └── usd_export.py
├── tools/                 # Standalone diagnostic tools
│   ├── analyze_usda.py
│   ├── cap_assembly_instances.py
│   ├── diagnose_growth.py
│   ├── sweep_dbh_params.py
│   ├── ue_exec.py
│   ├── validate_pve_json.py
│   └── visualize_tree.py
├── utils/                 # Shared utilities
│   ├── analysis.py          # SpeciesGrowthAnalyzer, Chapman-Richards fitting
│   ├── export_naming.py     # Filename formatting utilities
│   ├── gbif_species.py      # GBIF taxonomy validation
│   ├── growth_report.py     # Growth report generation
│   ├── log.py               # Logging setup
│   ├── naming.py            # Species name standardization
│   ├── plotting.py          # Visualization helpers
│   ├── profiling.py         # ProfileTimer
│   ├── pxr_init.py          # USD/pxr initialization
│   └── yield_tables.py      # Yield table calibration math
└── tests/                 # 40+ test files
```

### 2.3 Configuration System

Layered TOML resolution: dataclass defaults → packaged templates → `config/*.toml` → CLI arguments.

| File | Controls |
|------|----------|
| `general.toml` | Random seed, CSV path, output dir, verbosity, profiling |
| `assets.toml` | Grove installation path, texture resizing |
| `twigs.toml` | Mesh densification, alpha trimming, smoothing, decimation |
| `growth_models.toml` | Simulation cycles, seeds, plateau detection, timeouts |
| `calibration` | Yield table alignment (height, DBH) |
| `yield_sources` | Ingested yield table store path |
| `forest.toml` | Quality preset, growth cycle limit, height interval |
| `quality.toml` | Named presets (mesh resolution, skeleton params) |
| `unreal.toml` | Import script generation, UE content path |
| `helios.toml` | OBJ export, scene XML, mesh simplification |
| `competition.toml` | Competition group spacing |
| `tree_asset_lookup.csv` | 60 Grove species mapping (Common→Standardized→Twig) |

---

## 3. Data Assets

### 3.1 Presets (`data/assets/presets/`) - 10 species complete
- `norway_spruce.seed.json` (conifer)
- `european_beech.seed.json` (broadleaf)
- `silver_fir.seed.json`
- `scots_pine.seed.json`
- `european_oak.seed.json`
- `douglas_fir.seed.json`
- `sycamore_maple.seed.json`
- `common_ash.seed.json`
- `european_larch.seed.json`
- `silver_birch.seed.json`

### 3.2 Twigs (`data/assets/twigs/`) - 7 twig variants
- `european_beech_twig/`, `european_oak_twig/`, `one_leaved_ash_twig/`
- `pacific_silver_fir_twig/`, `paper_birch_twig/`, `scots_pine_twig/`
- `sycamore_maple_fall_twig/`

### 3.3 Textures (`data/assets/textures/`) - 7 bark textures
### 3.4 Growth Models (`data/assets/growth_models/`) - 10 species calibrated
### 3.5 Dataset CSVs (`data/input/dataset/`) - 10 merged CSVs + all_species.csv
### 3.6 Yield Tables (`data/input/yield_tables/store/`) - pylometree store
### 3.7 Output (`data/output/forest/`) - 4 species with output (pilot)

---

## 4. Pipeline (4 Steps)

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `prepare_assets.py` | Copy Grove 2.3 assets (presets, textures, twigs) |
| 2 | `convert_twigs.py` | Convert .blend twigs to USD |
| 3 | `create_growth_models.py` | Grove simulation + yield table calibration |
| 4 | `generate_forest.py` | Multi-species forest generation + USD export |

**Master orchestrator:** `dataset_pipeline.py` (runs steps 1-3 as subprocesses, step 4 as per-species subprocesses)

---

## 5. CLI Entry Points (8 commands)

| Command | Module |
|---------|--------|
| `growpy-init-config` | `cli.init_config` |
| `growpy-prepare-assets` | `cli.prepare_assets` |
| `growpy-convert-twigs` | `cli.convert_twigs` |
| `growpy-create-models` | `cli.create_growth_models` |
| `growpy-generate-forest` | `cli.generate_forest` |
| `growpy-dataset-pipeline` | `cli.dataset_pipeline` |
| `growpy-ue-exec` | `tools.ue_exec` |
| `growpy-analyze-usda` | `tools.analyze_usda` |

---

## 6. Dependencies

### Core (pyproject.toml)
- numpy>=1.20.0
- pandas>=1.3.0
- tqdm>=4.60.0
- joblib>=1.2.0
- pylometree (git+https://gitlab.uni-freiburg.de/xr-future-forests-lab/pylometree.git)

### Environment (environment.yml)
- Python 3.12
- matplotlib, scikit-learn, pillow, openpyxl, ipykernel
- pip: openyieldtables, bpy, tabula-py

### External (not in repo)
- **The Grove 2.3** (commercial, `src/the_grove_23/`)
- **bpy** (Blender Python API, conda-forge)
- **pxr** (bundled with bpy)

---

## 7. Test Suite

**40+ test files** covering:
- Core simulation (`test_forest.py`, `test_tree.py`, `test_skeleton.py`, `test_twig.py`)
- Configuration (`test_config.py`, `test_quality.py`, `test_preset_overrides.py`)
- Pipeline orchestration (`test_dataset_pipeline.py`, `test_dataset_csv_planner.py`, `test_dataset_job_planner.py`, `test_step_runner.py`)
- Export (`test_assembly_export.py`, `test_tree_export.py`, `test_twig_export.py`, `test_obj_export.py`, `test_helios_scene.py`)
- Unreal integration (`test_unreal_scripts.py`, `test_ue_exec.py`, `test_ue_remote.py`, `test_pve_foliage.py`, `test_wind_json.py`)
- Utilities (`test_analysis.py`, `test_plotting.py`, `test_naming.py`, `test_yield_tables.py`, `test_gbif_species.py`)
- Edge cases (`test_export_naming.py`, `test_mesh_simplify.py`, `test_preview.py`, `test_profiling.py`)

---

## 8. Documentation

### Structure
```
docs/
├── README.md
├── quickstart.md
├── growpy-functional-description.md
├── architecture/          # Architecture docs
│   ├── data-flow.md
│   ├── generate-forest-refactoring-plan.md
│   ├── module-graph.md
│   ├── module-reference.md
│   ├── pipeline-overview.md
│   └── processing-logic.md
├── dataset/             # Dataset documentation
│   ├── dataset-overview.md
│   ├── dataset-specification.md
│   └── dataset-update-april-2026.md
├── guides/              # User guides
│   ├── helios-export.md
│   ├── pve-preset-workflow.md
│   └── unreal-import.md
├── internals/           # Internal documentation
│   ├── module-audit.md
│   ├── nanite-assembly-readme.md
│   └── pve-json-reverse-engineering.md
├── literature/          # Academic references
│   ├── references.bib
├── reference/           # API/reference docs
│   ├── cli-reference.md
│   ├── coordinate-systems.md
│   ├── grove-api-attributes.md
│   ├── grove-preset-reference.md
│   ├── naming-conventions.md
│   ├── nanite-import-settings.md
│   ├── package-api.md
│   ├── pve-attribute-reference.md
│   ├── pve-python-api.md
│   ├── testing.md
│   ├── usd-builder.md
│   └── yield-table-calibration.md
├── supplementary/       # Supplementary docs
│   └── the_grove/       # Grove 2.3 API reference (17 files)
└── growpy/              (legacy, removed per CHANGELOG)
```

---

## 9. Development Environment

### VS Code Configuration
- Python analysis extra paths: `src/`, `src/the_grove_23/modules/`
- PYTHONPATH: `./src;./src/the_grove_23/modules`
- Debugger: debugpy with generate_forest.py launch config
- Formatting: Black (88 char)
- Default interpreter: `.conda\python.exe`

### Dev Container
- Image: `condaforge/miniforge3:latest`
- Post-create: `mamba env create -f environment.yml -n growpy`
- Extensions: Python, Black, Flake8, Jupyter, Copilot

### No Docker files present (`.docker/` does not exist)
### No `.specify/` directory present
### No `.config/` directory present

---

## 10. Current State Assessment

### What's Complete
- **10/10 species presets** in `data/assets/presets/` (all from XRFF-129)
- **10/10 species growth models** calibrated in `data/assets/growth_models/`
- **10/10 merged CSVs** in `data/input/dataset/`
- **7 twig variants** exported
- **7 bark textures** available
- **40+ test files** covering all major modules
- **Comprehensive documentation** (30+ docs across 7 categories)
- **Full pipeline** implemented (4 steps + master orchestrator)
- **PVE workflow** complete (schema, growth defaults, hierarchy, foliage extraction, UE scripts)
- **Helios++ workflow** complete (OBJ export, mesh simplification, scene XML)
- **Yield table calibration** system with pylometree integration
- **GBIF species validation** for name standardization

### What's Partially Complete
- **Output forest**: Only 4 species have output (`common_ash/`, `european_beech/`, `european_larch/`, `Instances/`)
- **XRFF-127** (full batch production): Not yet executed (prerequisite XRFF-129 complete)
- **UE integration**: PVE scripts generated but not yet imported into UE
- **Showcase library** (XRFF-61): Not started
- **Production trees** (XRFF-17): Not started

### Potential Issues
1. **Terminal error**: `dataset_pipeline.py --all --steps 3` exited with code 1 (last command in terminal)
2. **VS Code settings**: Contains trailing comma in JSON (line 37 `./**/.venv,`) - invalid JSON
3. **VS Code settings**: Contains `ue-python` and `claudeCode` settings that may be from other extensions
4. **No `.docker/` directory**: Despite documentation mentioning Docker workflows
5. **No `.specify/` directory**: Despite documentation referencing spec-driven process
6. **The Grove 2.3**: External dependency not present in workspace (expected)
7. **pylometree**: Git dependency from GitLab - may require authentication

---

## 11. Code Quality Observations

### Strengths
- **Modular architecture**: Clear separation between core simulation, export, and CLI layers
- **Pure Python computation**: `skeleton.py`, `twig.py`, `analysis.py` have no USD/Blender dependencies
- **Lazy imports**: Heavy dependencies (bpy, the_grove_23_core) loaded on demand
- **Comprehensive config system**: Layered TOML resolution with dataclass defaults
- **Extensive documentation**: 30+ docs covering architecture, reference, guides, internals
- **Test coverage**: 40+ test files across all major modules
- **Yield table calibration**: Sophisticated Chapman-Richards fitting with pylometree integration
- **PVE workflow**: Complete PVE preset generation with UE Python scripts
- **Helios++ support**: Material-aware mesh simplification and OBJ export

### Areas for Improvement
1. **VS Code settings.json**: Invalid JSON (trailing comma on line 37)
2. **No Docker files**: Despite documentation references
3. **No `.specify/` directory**: Despite spec-driven workflow references
4. **Terminal error on last run**: `dataset_pipeline.py` step 3 failed
5. **Limited output**: Only 4 species have forest output despite 10 species being calibrated
6. **Blender module**: `blender/` directory present but unclear if actively used
7. **Configuration drift**: `config/` (user-editable) vs `config/templates/` (packaged) may diverge

---

## 12. Linear Issue Tracking

### Active Issues (from WORK_PLAN.md)
| Issue | Description | Status |
|-------|-------------|--------|
| XRFF-129 | Calibrate remaining 5 species | COMPLETE (all 10 presets done) |
| XRFF-127 | Full 16-species batch production | PENDING (XRFF-129 prerequisite met) |
| XRFF-59 | Import assets into UE | PENDING |
| XRFF-61 | Showcase library in UE | PENDING |
| XRFF-17 | Production trees at inventory positions | PENDING |
| XRFF-36 | Grove generation driven by live Ecosense DB | PARALLEL TRACK |

### Next Priority
1. **Fix terminal error** from last `dataset_pipeline.py` run
2. **Execute XRFF-127**: Full batch production (`growpy-dataset-pipeline --all --steps all --ingest-yield-tables`)
3. **Fix VS Code settings.json** (invalid JSON)
4. **Progress XRFF-59**: Import assets into UE

---

## 13. File Count Summary

| Category | Count |
|----------|-------|
| Python source files | ~80+ |
| Test files | 40+ |
| TOML config files | 11 |
| Seed presets | 10 |
| Twig variants | 7 |
| Bark textures | 7 |
| Documentation files | 30+ |
| Grove 2.3 supplementary docs | 17 |
| **Total files** | **~160+** |

---

## 14. Key Architectural Decisions

1. **bpy isolation**: Step 4 runs as subprocess to avoid bpy import conflicts
2. **Pure Python computation**: Skeleton/twig/analysis modules have no USD/Blender deps
3. **Chapman-Richards growth models**: Parametric fitting for height/DBH prediction
4. **PVE over direct simulation**: PVE JSON recipes for UE-side procedural vegetation
5. **Nanite Assembly USD**: USD references (not FBX) for Nanite compatibility
6. **Material-aware simplification**: Wood vs leaf classification for Helios accuracy
7. **GBIF name resolution**: Fallback taxonomy validation for species names
8. **Layered config**: TOML deep-merge with CLI override priority
9. **Context splitting**: `individual_type` prevents intra-grove shade interference
10. **Twig instancing**: PointInstancer prims for foliage rather than baked geometry

---

*Assessment complete. Work plan update recommended below.*
