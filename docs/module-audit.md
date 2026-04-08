# Module Audit

Inventory of all Python modules in `src/growpy/`, their role in the CLI pipeline,
and cleanup recommendations. Last updated 2026-04-08 (post io/cli restructure).

## CLI Pipeline Scripts

These are the entry points invoked directly from the command line.

| Script | Step | Purpose |
|--------|------|---------|
| `cli/prepare_assets.py` | 1 | Copy Grove assets (presets, twigs, textures) to `data/assets/` |
| `cli/convert_twigs.py` | 2 | Convert `.blend` twig meshes to `.usda` foliage files |
| `cli/create_growth_models.py` | 3 | Simulate Grove growth, calibrate against yield tables, fit prediction models |
| `cli/generate_forest.py` | 4 | Grow forest from CSV, export USD assemblies with radial scaling |
| `cli/dataset_pipeline.py` | -- | Dataset orchestrator: runs all four steps, CSV generation, parallel step 4 |

Pipeline order: 1 -> 2 -> 3 -> 4

Dataset production: `dataset_pipeline.py --generate-csvs` -> `dataset_pipeline.py --all` (or `--steps all`)

### Pipelines (orchestration)

| Module | Imported By |
|--------|-------------|
| `pipelines/dataset_csv_planner.py` | `dataset_pipeline.py` (generate merged + all-species CSVs) |
| `pipelines/dataset_job_planner.py` | `dataset_pipeline.py` (species selection, CSV path discovery) |
| `pipelines/step_runner.py` | `dataset_pipeline.py` (subprocess invocation for all four steps) |
| `pipelines/forest_stages.py` | `cli/generate_forest.py` (multi-stage height-milestone export) |
| `pipelines/forest_exports.py` | `cli/generate_forest.py` (default cycle-target export) |

## Active Modules (used by pipeline)

### Configuration

| Module | Imported By |
|--------|-------------|
| `config/core.py` | All CLI scripts (`get_config()`) |
| `config/paths.py` | Most modules (path resolution, twig lookup) |
| `config/preset_overrides.py` | `pipelines/forest_stages.py`, `pipelines/forest_exports.py`, `core/forest.py` (per-cycle overrides + target DBH) |
| `config/pve_species_overrides.py` | `io/unreal/pve_grove_mapper.py`, `cli/prepare_assets.py` |
| `config/quality.py` | `pipelines/forest_stages.py`, `pipelines/forest_exports.py` (mesh resolution presets) |

### Core

| Module | Imported By |
|--------|-------------|
| `core/forest.py` | `pipelines/forest_stages.py`, `pipelines/forest_exports.py` (create + simulate forest) |
| `core/grove.py` | `create_growth_models.py`, `core/forest.py` |
| `core/skeleton.py` | `io/usd/tree_export.py`, `io/usd/assembly_export.py` |
| `core/tree.py` | `core/forest.py`, `pipelines/forest_*.py` (DBH calculation, cycle prediction) |
| `core/twig.py` | `io/usd/assembly_export.py`, `io/usd/tree_export.py`, `io/helios/obj_export.py` |

### I/O & Export

`io/` is split into three sub-packages: `io/usd/` (USD/Nanite exporters),
`io/unreal/` (Unreal-side sidecars), `io/helios/` (Helios++ LiDAR pipeline).
`io/forest_export.py` sits at the top level because it crosses sub-package
boundaries.

| Module | Imported By |
|--------|-------------|
| `io/forest_export.py` | `pipelines/forest_exports.py` (cross-format per-tree export orchestration) |
| `io/usd/assembly_export.py` | `pipelines/forest_stages.py`, `io/forest_export.py`, `cli/generate_forest.py` (USD Nanite Assembly export) |
| `io/usd/tree_export.py` | `io/usd/assembly_export.py`, `io/helios/obj_export.py`, both forest pipelines (mesh + radial scaling) |
| `io/usd/twig_export.py` | `cli/convert_twigs.py` (twig mesh processing) |
| `io/usd/texture_utils.py` | `cli/prepare_assets.py`, `cli/convert_twigs.py` |
| `io/usd/preview.py` | `pipelines/forest_stages.py`, `io/forest_export.py` (per-tree preview/icon images) |
| `io/usd/overview.py` | `cli/dataset_pipeline.py` (dataset overview markdown) |
| `io/unreal/wind_json.py` | `pipelines/forest_stages.py`, `io/forest_export.py` (DynamicWind JSON) |
| `io/unreal/pve_grove_mapper.py` | `pipelines/forest_stages.py`, `io/forest_export.py` (PVE JSON generation) |
| `io/unreal/pve_foliage_extractor.py` | `io/unreal/pve_grove_mapper.py` |
| `io/unreal/pve_hierarchy_builder.py` | `io/unreal/pve_grove_mapper.py` |
| `io/unreal/pve_schema.py` | `io/unreal/pve_grove_mapper.py` |
| `io/unreal/pve_growth_defaults.py` | `io/unreal/pve_grove_mapper.py` |
| `io/unreal/unreal_scripts.py` | `cli/generate_forest.py`, `pipelines/step_runner.py` (UE import/cleanup script generation) |
| `io/unreal/ue_remote.py` | `tools/ue_exec.py` (Unreal Remote Control client) |
| `io/helios/obj_export.py` | `cli/generate_forest.py` (Helios OBJ export) |
| `io/helios/helios_scene.py` | `io/helios/obj_export.py` (Helios scene XML) |
| `io/helios/mesh_simplify.py` | `io/helios/obj_export.py`, `io/usd/tree_export.py` (decimation) |

### Utilities

| Module | Imported By |
|--------|-------------|
| `utils/log.py` | All CLI scripts (logging setup) |
| `utils/profiling.py` | `cli/generate_forest.py`, both forest pipelines (execution time tracking) |
| `utils/analysis.py` | `cli/create_growth_models.py` (SpeciesGrowthAnalyzer) |
| `utils/pxr_init.py` | `io/usd/twig_export.py`, `io/helios/obj_export.py` (USD plugin path) |
| `utils/gbif_species.py` | `cli/prepare_assets.py` (species name resolution) |
| `utils/plotting.py` | `utils/analysis.py` (growth curve visualization) |
| `utils/naming.py` | `cli/*`, `pipelines/dataset_*_planner.py` (species name standardization) |
| `utils/export_naming.py` | `pipelines/forest_stages.py`, `io/usd/assembly_export.py` (height/DBH/density filename formatting) |
| `utils/yield_tables.py` | `cli/create_growth_models.py` (yield table loading, Chapman-Richards interpolation) |

### Tools

| Module | Imported By |
|--------|-------------|
| `tools/analyze_usda.py` | Standalone CLI (USDA assembly analysis) |
| `tools/diagnose_growth.py` | Standalone CLI (growth simulation diagnostics) |
| `tools/visualize_tree.py` | Standalone CLI (tree mesh side-view rendering) |
| `tools/ue_exec.py` | Standalone CLI (run a Python file inside a live UE editor via Remote Control) |

## Standalone / Development Scripts

These files have `if __name__ == "__main__"` blocks but are **not imported** by any
pipeline module. They are useful for development and debugging but are not required
for production runs. Relocated to `src/scripts/` to keep the growpy package clean.

| Script | Purpose |
|--------|----------|
| `src/scripts/sweep_dbh_params.py` | Parameter sweep for DBH calibration levers |
| `src/scripts/create_minimal_pve_test.py` | Create minimal PVE JSON for Unreal testing |
| `src/scripts/validate_pve_json.py` | Validate PVE JSON against Unreal requirements |
| `src/scripts/extract_pve_config.py` | Extract PVE overrides from reference JSON |
| `src/scripts/the-grove-output-complete.py` | Grove output analysis |

## Removed / Relocated Modules

| Module | Reason | Date |
|--------|--------|------|
| `io/pve_preset_json.py` | Superseded by `pve_grove_mapper.py`, contained TODO placeholders | 2026-03-11 |
| `utils/unreal_schema_env.py` | Redundant with `utils/pxr_init.py` | 2026-03-11 |
| `tests/test_obj_export.py` | Manual test, not imported by any module | 2026-03-11 |
| `tests/test_pve_generation.py` | Manual test, not imported by any module | 2026-03-11 |
| `cli/sweep_dbh_params.py` | Moved to `src/scripts/` -- standalone research tool, not a pipeline step | 2026-03-11 |
| `io/create_minimal_pve_test.py` | Moved to `src/scripts/` -- standalone PVE test tool | 2026-03-11 |
| `io/validate_pve_json.py` | Moved to `src/scripts/` -- standalone PVE validator | 2026-03-11 |
| `utils/extract_pve_config.py` | Moved to `src/scripts/` -- standalone PVE config extractor | 2026-03-11 |
| `core/orchestration/*` | Moved to `pipelines/` (`dataset_csv_planner`, `dataset_job_planner`, `step_runner`) | 2026-04-08 |
| `io/{assembly_export,tree_export,twig_export,texture_utils,preview,overview}.py` | Moved into `io/usd/` sub-package | 2026-04-08 |
| `io/{wind_json,pve_*,unreal_scripts,ue_remote}.py` | Moved into `io/unreal/` sub-package | 2026-04-08 |
| `io/{obj_export,helios_scene,mesh_simplify}.py` | Moved into `io/helios/` sub-package | 2026-04-08 |
| `cli/ue_exec.py` | Moved to `tools/ue_exec.py` (it's a diagnostic, not a pipeline step) | 2026-04-08 |
| Step-4 control flow | Extracted from `cli/generate_forest.py` into `pipelines/forest_stages.py` and `pipelines/forest_exports.py` (CLI is now thin argparse only) | 2026-04-08 |
| `scripts/generate_arch_diagrams.sh` (+ `pylint`/`code2flow`/`graphviz` deps) | Removed: replaced by hand-authored Mermaid flowcharts in [architecture/](architecture/) | 2026-04-08 |

## Console Entry Points

CLI scripts can be run directly (`python src/growpy/cli/script.py`) or as console
commands after `pip install -e .`:

| Command | Script |
|---------|--------|
| `growpy-prepare-assets` | `cli/prepare_assets.py` |
| `growpy-convert-twigs` | `cli/convert_twigs.py` |
| `growpy-create-models` | `cli/create_growth_models.py` |
| `growpy-generate-forest` | `cli/generate_forest.py` |
| `growpy-generate-dataset-csvs` | `cli/generate_dataset_csvs.py` |
| `growpy-analyze-usda` | `tools/analyze_usda.py` |
| `growpy-diagnose-growth` | `tools/diagnose_growth.py` |
| `growpy-visualize-tree` | `tools/visualize_tree.py` |

## Configuration Notes

### `growpy.toml`

The config is well-structured with clear section boundaries. All quality presets
(ultra, high, medium, low, performance, helios) are grouped together. The
`[calibration]` section documents the correct 3-step pipeline order.

### `pyproject.toml`

- `[project.scripts]` provides console entry points for all 6 CLI scripts.
- `the_grove_23_core` is listed as a setuptools package but it's a compiled binary
  module (`.pyd`/`.so`). The `package-dir` mapping handles this correctly for
  development but won't bundle the binary in a wheel distribution.

### `environment.yml`

- Environment name `growpy` matches the active conda environment.
- `PYTHONPATH` variable correctly includes both `./src` and `./src/the_grove_23/modules`.
- `PYTHONPATH` variable correctly includes both `./src` and `./src/the_grove_23/modules`.
