# GrowPy Test Suite

Unit tests for the growpy package. Tests live alongside the source code in `src/growpy/tests/` following the src layout convention.

## Running Tests

```bash
conda activate growpy
python -m pytest src/growpy/tests/ -v
```

## Test Modules

| Module | Source | Tests | Coverage |
| --- | --- | --- | --- |
| test_config.py | config/core.py | 25 | Config defaults, TOML loading, CLI resolve, global singleton, density variants |
| test_preset_overrides.py | config/preset_overrides.py | 25 | Static/interpolated/cycle overrides, easing, memoization, cache invalidation |
| test_quality.py | config/quality.py | 7 | Default values, preset loading, value types |
| test_paths.py | config/paths.py | 7 | Grove texture name normalization (CamelCase to snake_case) |
| test_pve_species_overrides.py | config/pve_species_overrides.py | 12 | Config loading, example creation, override merging, null placeholders |
| test_skeleton.py | core/skeleton.py | 44 | Vector3 math, JointTransform, rotation, hierarchy, bone filtering, distance/falloff |
| test_twig.py | core/twig.py | 18 | TwigPlacement, face center/normal, rotation matrix, quaternion conversion |
| test_tree.py | core/tree.py | 19 | find_max_height, calculate_tree_height, calculate_dbh_at_height (interpolation) |
| test_profiling.py | utils/profiling.py | 13 | TimingEntry, ProfileTimer context manager, nesting, accumulation, reporting |
| test_naming.py | utils/naming.py | 13 | camel_to_snake, species/twig name standardization |
| test_export_naming.py | utils/export_naming.py | 13 | Height/DBH/density filename formatting, DensityVariantConfig |
| test_yield_tables.py | utils/yield_tables.py | 25 | YieldTableData, local CSV loading, flushes estimation, interpolation, calibration curves |
| test_log.py | utils/log.py | 6 | Logging setup, level switching, handler idempotency |
| test_texture_utils.py | io/texture_utils.py | 38 | Power-of-2, resize, bump-to-normal, alpha extraction/stripping/normalization |
| test_pve_foliage.py | io/pve_foliage_extractor.py | 10 | Coordinate conversion (Z-up to Y-up), position scaling |
| test_pve_schema.py | io/pve_schema.py | 17 | Schema sections, attribute types, array flags, empty preset generation |
| test_pve_hierarchy.py | io/pve_hierarchy_builder.py | 16 | Parent derivation, hierarchy arrays, branch generation calculation |
| test_wind_json.py | io/wind_json.py | 15 | Joint name extraction, classify_joint, hierarchy depth classification |

**Total: 376 passed, 2 skipped**

The 2 skipped tests are in test_quality.py when the TOML config file is not found in the test environment.

## Scope

Tests cover pure-logic functions, 3D math, data structures, configuration, I/O utilities, and calibration math. This includes:

- Configuration parsing, path resolution, and species overrides
- 3D math (vectors, rotations, coordinate transforms, skeleton hierarchy)
- Tree measurement extraction and interpolation
- Texture processing (resizing, normal map generation, alpha handling)
- PVE preset schema, hierarchy building, and wind JSON generation
- Yield table loading, interpolation, and growth calibration curves
- Data structures, serialization, and string formatting
- Profiling and logging infrastructure

Modules requiring The Grove API or Blender (cli/, io/tree_export.py, io/twig_export.py, core/forest.py, core/grove.py) depend on external software and are not unit-tested here.

## Configuration

pytest is configured in the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "src/the_grove_23/modules"]
testpaths = ["src/growpy/tests"]
```
