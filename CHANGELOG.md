# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `.editorconfig` for cross-editor consistency.
- `CONTRIBUTING.md` with contribution workflow.
- `CHANGELOG.md` (this file).
- `docs/reference/package-api.md`: Package API reference with Python examples.
- `docs/reference/testing.md`: Test suite documentation.

### Changed

- **Code quality refactor** (thermo-nuclear audit): decomposed 6 files that
  exceeded 1000 lines and extracted shared utilities to eliminate duplication.
  All 864 tests pass, behavior preserved exactly.
  - `unreal_scripts.py`: 1751 → 1000 lines. Extracted
    `unreal_vram_preamble.py`, `unreal_material_script.py`,
    `unreal_nanite_script.py`.
  - `pve_growth_defaults.py`: 827 → 84 lines. Hazel defaults now loaded from
    `hazel_growth_defaults.json` resource instead of a hardcoded dict.
  - `pve_grove_mapper.py`: 1457 → 1102 lines. Pure skeleton calculators
    extracted to `pve_skeleton_calculators.py`.
  - `tree_export.py`: 1631 → 1462 lines. Deleted 2 dead material functions.
  - `ue_exec.py`: VRAM/RAM monitoring delegated to shared `utils/vram.py`.
  - `unreal_scripts.py`: color helpers delegated to shared `utils/color.py`.
  - `analysis.py`: `find_max_height_in_branch` moved from nested closure to
    module level.
  - `forest_stages.py`: inline species slugification replaced with
    `filename_safe_species_slug` from `utils/naming.py`.
  - Introduced `GroveEntry` and `TreeSnapshot` NamedTuples to replace
    positional 4-tuples and 5-tuples throughout `core/forest.py`.
- `pyproject.toml`: `requires-python` from `>=3.9` to `>=3.12`.
- `environment.yml`: Python version from `3.11` to `3.12`.
- `README.md`: Configuration section updated to reference the user-editable
  `config/` directory and the packaged template layout.
- `src/growpy/README.md` → `docs/reference/package-api.md`: Package API reference.
- `src/growpy/tests/README.md` → `docs/reference/testing.md`: Test suite docs.
- `src/growpy/config/templates/README.md`: Rewritten as brief pointer to
  user-editable `config/` directory.

### Removed

- Dead code (118 lines): `_read_twig_mesh`, `_read_twig_material`,
  `_read_face_material_names` in `obj_export.py`; `_build_vertex_alpha_map`
  in `twig_geometry.py`. All defined but never called.
- `.coverage` test coverage artifact removed from version control and added
  to `.gitignore`.
- Stale redirect file `docs/growpy/cli-reference.md` removed; live docs are
  in `docs/cli-reference.md`.
- Empty `src/the_grove_23/groves/` directory removed.

## [0.1.0]

Initial release of the Grove API integration pipeline: procedural forest
generation for Unreal Engine 5.7 Nanite skeletal-mesh assemblies, multi-stage
dataset production, and yield-table calibrated growth models.
