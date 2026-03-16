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
| test_skeleton.py | core/skeleton.py | 18 | Vector3 math, JointTransform, rotation alignment, hierarchy construction |
| test_twig.py | core/twig.py | 13 | TwigPlacement dataclass, face center/normal geometry, rotation matrix |
| test_profiling.py | utils/profiling.py | 13 | TimingEntry, ProfileTimer context manager, nesting, accumulation, reporting |
| test_naming.py | utils/naming.py | 13 | camel_to_snake, species/twig name standardization |
| test_export_naming.py | utils/export_naming.py | 13 | Height/DBH/density filename formatting, DensityVariantConfig |
| test_texture_utils.py | io/texture_utils.py | 14 | next_power_of_2, is_power_of_2 (parametrized) |
| test_pve_foliage.py | io/pve_foliage_extractor.py | 10 | Coordinate conversion (Z-up to Y-up), position scaling |

**Total: 209 passed, 2 skipped**

The 2 skipped tests are in test_quality.py when the TOML config file is not found in the test environment.

## Scope

Tests focus on pure-logic functions that can run without external dependencies (The Grove API, Blender/bpy, USD). This covers:

- Configuration parsing and resolution
- 3D math (vectors, rotations, coordinate transforms)
- Data structures (dataclasses, serialization)
- String formatting and naming conventions
- Profiling infrastructure

Modules requiring The Grove API, Blender, or USD (cli/, io/tree_export.py, io/twig_export.py, core/forest.py, core/grove.py, core/tree.py) are not unit-tested here as they depend on commercial or heavy external software.

## Configuration

pytest is configured in the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "src/the_grove_23/modules"]
testpaths = ["src/growpy/tests"]
```
