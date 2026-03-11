# Module Audit

Inventory of all Python modules in `src/growpy/`, their role in the CLI pipeline,
and cleanup recommendations. Last updated 2026-03-11.

## CLI Pipeline Scripts

These are the entry points invoked directly from the command line.

| Script | Step | Purpose |
|--------|------|---------|
| `cli/prepare_assets.py` | 1 | Copy Grove assets (presets, twigs, textures) to `data/assets/` |
| `cli/convert_twigs.py` | 2 | Convert `.blend` twig meshes to `.usda` foliage files |
| `cli/create_growth_models.py` | 3 | Simulate Grove growth and fit height-to-cycle prediction models |
| `cli/calibrate_growth.py` | 3b | Calibrate grow_length / thicken_tips per cycle against yield tables |
| `cli/generate_forest.py` | 4 | Grow forest from CSV, export USD assemblies with radial scaling |

Pipeline order: 1 -> 2 -> 3 -> 3b -> 3 (re-run) -> 4

## Active Modules (used by pipeline)

### Configuration

| Module | Imported By |
|--------|-------------|
| `config/core.py` | All CLI scripts (`get_config()`) |
| `config/paths.py` | Most modules (path resolution, twig lookup) |
| `config/preset_overrides.py` | `generate_forest.py`, `forest.py` (per-cycle overrides + target DBH) |
| `config/pve_species_overrides.py` | `pve_grove_mapper.py` |
| `config/quality.py` | `generate_forest.py` (mesh resolution presets) |

### Core

| Module | Imported By |
|--------|-------------|
| `core/forest.py` | `generate_forest.py` (create + simulate forest) |
| `core/grove.py` | `create_growth_models.py`, `generate_forest.py` |
| `core/skeleton.py` | `tree_export.py`, `assembly_export.py` |
| `core/tree.py` | `generate_forest.py` (DBH calculation, cycle prediction) |
| `core/twig.py` | `assembly_export.py`, `tree_export.py`, `obj_export.py` |

### I/O & Export

| Module | Imported By |
|--------|-------------|
| `io/assembly_export.py` | `generate_forest.py` (USD Nanite Assembly export) |
| `io/tree_export.py` | `assembly_export.py`, `obj_export.py` (mesh + radial scaling) |
| `io/twig_export.py` | `convert_twigs.py` (twig mesh processing) |
| `io/obj_export.py` | `generate_forest.py` (Helios OBJ export) |
| `io/helios_scene.py` | `generate_forest.py` (Helios scene XML) |
| `io/wind_json.py` | `generate_forest.py` (DynamicWind JSON for skeletal meshes) |
| `io/texture_utils.py` | `prepare_assets.py`, `convert_twigs.py` |
| `io/pve_grove_mapper.py` | `generate_forest.py` (PVE JSON generation) |
| `io/pve_foliage_extractor.py` | `pve_grove_mapper.py` |
| `io/pve_hierarchy_builder.py` | `pve_grove_mapper.py` |
| `io/pve_schema.py` | `pve_grove_mapper.py` |
| `io/pve_growth_defaults.py` | `pve_grove_mapper.py` |

### Utilities

| Module | Imported By |
|--------|-------------|
| `utils/log.py` | All CLI scripts (logging setup) |
| `utils/profiling.py` | `generate_forest.py` (execution time tracking) |
| `utils/analysis.py` | `create_growth_models.py` (SpeciesGrowthAnalyzer) |
| `utils/pxr_init.py` | `twig_export.py`, `obj_export.py` (USD plugin path) |
| `utils/gbif_species.py` | `prepare_assets.py` (species name resolution) |
| `utils/diagnostics.py` | `generate_forest.py` (Grove data dump for debugging) |
| `utils/plotting.py` | `analysis.py` (growth curve visualization) |

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

## Removed Modules

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

## Console Entry Points

CLI scripts can be run directly (`python src/growpy/cli/script.py`) or as console
commands after `pip install -e .`:

| Command | Script |
|---------|--------|
| `growpy-prepare-assets` | `cli/prepare_assets.py` |
| `growpy-convert-twigs` | `cli/convert_twigs.py` |
| `growpy-create-models` | `cli/create_growth_models.py` |
| `growpy-calibrate` | `cli/calibrate_growth.py` |
| `growpy-generate-forest` | `cli/generate_forest.py` |

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
