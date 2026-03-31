# GrowPy Test Suite

Unit tests for the growpy package. Tests live alongside the source code in `src/growpy/tests/` following the src layout convention.

## Running Tests

### Quick start

```bash
conda activate growpy
python -m pytest src/growpy/tests/ -v
```

### Common options

```bash
# Run a single test module
python -m pytest src/growpy/tests/test_config.py -v

# Run a specific test class or method
python -m pytest src/growpy/tests/test_skeleton.py::TestVector3 -v
python -m pytest src/growpy/tests/test_tree.py::TestCalculateDbh::test_interpolation -v

# Run with short traceback on failure
python -m pytest src/growpy/tests/ --tb=short

# Run only tests matching a keyword
python -m pytest src/growpy/tests/ -k "texture" -v

# Stop on first failure
python -m pytest src/growpy/tests/ -x

# Show print output during tests
python -m pytest src/growpy/tests/ -s

# Run with conda run (without activating env)
conda run -n growpy python -m pytest src/growpy/tests/ -v
```

### Known issues

- **test_orchestration.py** may fail with an `ImportError` if `_hex_neighbors` has been refactored out of `dataset_csv_planner`. Skip with `--ignore=src/growpy/tests/test_orchestration.py` if needed.
- **Windows DLL crash at exit**: On Windows, a non-fatal `code 0xc0000139` crash trace may appear after all tests pass. This is caused by `tree_export.py` attempting to load Blender DLLs during Python garbage collection at shutdown. It does not affect test results.

## Test Modules

### config/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_config.py | config/core.py | 25 | Config defaults, TOML loading, CLI resolve, global singleton, density variants |
| test_preset_overrides.py | config/preset_overrides.py | 25 | Static/interpolated/cycle overrides, easing, memoization, cache invalidation |
| test_quality.py | config/quality.py | 7 | Default values, preset loading, value types |
| test_paths.py | config/paths.py | 7 | Grove texture name normalization (CamelCase to snake_case) |
| test_pve_species_overrides.py | config/pve_species_overrides.py | 12 | Config loading, example creation, override merging, null placeholders |

### core/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_skeleton.py | core/skeleton.py | 44 | Vector3 math, JointTransform, rotation, hierarchy, bone filtering, distance/falloff |
| test_twig.py | core/twig.py | 18 | TwigPlacement, face center/normal, rotation matrix, quaternion conversion |
| test_tree.py | core/tree.py | 19 | find_max_height, calculate_tree_height, calculate_dbh_at_height (interpolation) |
| test_forest.py | core/forest.py | 7 | _split_bones_by_tree (per-tree bone splitting). Skipped if Grove API unavailable |
| test_orchestration.py | core/orchestration/ | 30 | Hex neighbors, CSV generation, dataset planning, species resolution, step running |

### io/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_texture_utils.py | io/texture_utils.py | 38 | Power-of-2, resize, bump-to-normal, alpha extraction/stripping/normalization |
| test_pve_foliage.py | io/pve_foliage_extractor.py | 10 | Coordinate conversion (Z-up to Y-up), position scaling |
| test_pve_schema.py | io/pve_schema.py | 17 | Schema sections, attribute types, array flags, empty preset generation |
| test_pve_hierarchy.py | io/pve_hierarchy_builder.py | 16 | Parent derivation, hierarchy arrays, branch generation calculation |
| test_pve_growth_defaults.py | io/pve_growth_defaults.py | 14 | Hazel defaults structure, default/minimal params, merge with overrides |
| test_wind_json.py | io/wind_json.py | 15 | Joint name extraction, classify_joint, hierarchy depth classification |
| test_mesh_simplify.py | io/mesh_simplify.py | 14 | classify_material, vertex extraction/reindexing, per-material proto split |
| test_helios_scene.py | io/helios_scene.py | 9 | XML scene generation, part count, translate offsets, OBJ loader params |
| test_overview.py | io/overview.py | 15 | _snap_to_interval, _build_interval_columns, _height_label, icon regex pattern |
| test_unreal_scripts.py | io/unreal_scripts.py | 8 | Import block generation, consolidation script generation |

### utils/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_analysis.py | utils/analysis.py | 21 | Chapman-Richards growth model fitting, PiecewiseLinearModel, backward compat |
| test_yield_tables.py | utils/yield_tables.py | 25 | YieldTableData, local CSV loading, flushes estimation, interpolation, calibration |
| test_profiling.py | utils/profiling.py | 13 | TimingEntry, ProfileTimer context manager, nesting, accumulation, reporting |
| test_naming.py | utils/naming.py | 13 | camel_to_snake, species/twig name standardization |
| test_export_naming.py | utils/export_naming.py | 13 | Height/DBH/density filename formatting, DensityVariantConfig |
| test_log.py | utils/log.py | 6 | Logging setup, level switching, handler idempotency |

### cli/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_convert_twigs.py | cli/convert_twigs.py | 12 | classify_texture_type (PBR classification), find_textures_for_material (matching) |
| test_dataset_pipeline.py | cli/dataset_pipeline.py | 10 | _parse_steps argument parsing ("all", comma-separated, validation) |

### tools/

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_analyze_usda.py | tools/analyze_usda.py | 8 | parse_vec3f_array, parse_int_array (USD text parsing without pxr) |

Total: ~533 passed, 2 skipped.

The 2 skipped tests are in test_quality.py when the TOML config file is not found, and test_forest.py when The Grove API is unavailable.

## Scope

Tests cover pure-logic functions, 3D math, data structures, configuration, I/O utilities, calibration math, and string generation. This includes:

- Configuration parsing, path resolution, and species overrides
- 3D math (vectors, rotations, coordinate transforms, skeleton hierarchy)
- Tree measurement extraction and interpolation
- Texture processing (resizing, normal map generation, alpha handling)
- PVE preset schema, hierarchy building, growth defaults, and wind JSON generation
- Yield table loading, interpolation, and growth calibration curves
- Mesh simplification logic (material classification, vertex reindexing)
- Helios++ scene XML generation
- Unreal Engine import script generation
- Dataset overview helpers (snapping, labeling, icon pattern matching)
- CLI argument parsing and texture classification
- USDA file parsing (geometry arrays without USD libraries)
- Data structures, serialization, and string formatting
- Profiling and logging infrastructure

## Not tested (external dependencies)

The following modules depend on external software and cannot be unit-tested in isolation:

| Module | Dependency | Reason |
| --- | --- | --- |
| core/forest.py (most functions) | The Grove API | Growth simulation requires `the_grove_23_core` |
| core/grove.py | The Grove API | Thin wrapper around Grove |
| io/tree_export.py | Blender + USD | Mesh export requires `bpy` and `pxr` |
| io/twig_export.py | Blender | Twig conversion requires `bpy` |
| io/assembly_export.py | USD | Assembly creation requires `pxr` |
| io/obj_export.py | Blender + USD | OBJ export requires both |
| io/preview.py | Matplotlib + Grove | Preview rendering |
| io/pve_grove_mapper.py | Grove API | Maps Grove data to PVE presets |
| cli/prepare_assets.py | Filesystem | Copies Grove installation assets |
| cli/create_growth_models.py | Grove API | Full growth simulation pipeline |
| cli/generate_forest.py | Blender + Grove | Forest mesh generation |
| utils/plotting.py | Matplotlib | Visualization only |
| utils/gbif_species.py | Network | GBIF API queries |
| tools/diagnose_growth.py | Blender + Grove | Interactive diagnosis |
| tools/visualize_tree.py | Matplotlib | USDA visualization |

## Configuration

pytest is configured in the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "src/the_grove_23/modules"]
testpaths = ["src/growpy/tests"]
```

## Adding tests

When adding new test modules:

1. Create `test_<module>.py` in `src/growpy/tests/`
2. Import directly from the submodule (e.g. `from growpy.io.helios_scene import ...`) to avoid triggering heavy transitive imports from package `__init__.py` files
3. If the module has unavoidable external dependencies, use a try/except import with `pytest.mark.skipif` (see `test_forest.py` for an example)
4. Update this README with the new module in the appropriate section
