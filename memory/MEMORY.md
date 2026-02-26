# GrowPy Project Memory

## Project Overview

Grove API integration for Unreal Engine 5 Nanite foliage. Python package at `src/growpy/`.

- Core: forest/grove/tree simulation, skeleton building, twig placement
- IO: USD/USDA export, PVE generation, texture processing
- CLI: forest generation pipeline, asset prep, twig conversion
- Utils: analysis, profiling, GBIF species lookup

## Key Paths

- Package root: `src/growpy/`
- Core modules: `src/growpy/core/` (forest.py, grove.py, skeleton.py, twig.py, tree.py)
- Config: `src/growpy/config/` (core.py, paths.py, quality.py, preset_overrides.py, pve_species_overrides.py)
- IO: `src/growpy/io/` (tree_export.py, twig_export.py, pve_grove_mapper.py, texture_utils.py, assembly_export.py)
- CLI: `src/growpy/cli/` (generate_forest.py, prepare_assets.py, convert_twigs.py, create_growth_models.py)
- Utils: `src/growpy/utils/` (analysis.py, profiling.py, plotting.py, gbif_species.py)
- Tests: `src/growpy/tests/`
- Data: `data/` (not version controlled)

## Improvement Task Plan

See `memory/task_plan.md` for full detail.

### Priority 1 - Bug Fixes

- T1: Cache growth model per species in `core/tree.py:calculate_growth_cycles_from_height()`
- T2: Raise ValueError when bones > UNREAL_MAX_BONE_INDEX in `core/skeleton.py`
- T3: Consistent FileNotFoundError in `config/paths.py:get_growth_model_path()`
- T4: twig_idx bounds check in `core/twig.py`
- T5: Fix orphaned bone parent walk in `core/skeleton.py`

### Priority 2 - Performance

- T6: Single-pass texture directory scan in `io/texture_utils.py`
- T7: Vectorize alias lookup in `config/paths.py`
- T8: Pre-compute easing lookup table in `config/preset_overrides.py`
- T9: Extract shared growth cycle loop in `core/forest.py`

### Priority 3 - Code Quality

- T10: Replace print() with logging in all modules
- T11: Module-level constants for magic numbers
- T12: Add __all__ to __init__.py files
- T13: bump_to_normal error handling fix
- T14: Break up pve_grove_mapper.py phases
- T15: Break up twig_export.py geometry loop

### Priority 4 - External Script Integration

- T16: extract_grove_attributes() in core/tree.py
- T17: grow_roots()/build_roots() wrappers in core/grove.py
- T18: compare_smoothing_effect() in utils/analysis.py
- T19: dump_grove_data() in utils/diagnostics.py
- T20: Deprecate calculate_tree_heights.py

## Environment

- Conda env: the-grove
- Python packaging: editable install with pyproject.toml
- Grove API: the_grove_22_core (external C extension)
- Key deps: pxr (USD), bpy (optional Blender), PIL, numpy, pandas, sklearn
