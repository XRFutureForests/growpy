# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.1] - 2026-07-29

### Removed

- `.claude/`, `CLAUDE.md`, `AGENTS.md`, and `.github/copilot-instructions.md`
  from `main` — dev-workflow tooling, not project documentation; they now
  live on a `dev` branch instead.
- A stale tracked `.coverage` report and personal `.vscode/` editor config
  (which included an Unreal remote-python port and a Claude Code permission
  flag) — both untracked, kept locally via `.gitignore`.
- An orphaned `claude-code-skills` submodule gitlink with no matching
  `.gitmodules` entry.

## [0.3.0] - 2026-07-27

### Added

- Per-radius calibration: species overrides, calibration curve resets, and
  comparison plots are now keyed by `(species, radius)` instead of the base
  (r0) preset, so a species with multiple surround-radius groves (r0/r7/r15)
  no longer has all but the last-processed radius silently overwritten by
  the same calibration curve.
- Conifer/broadleaf twig density defaults, resolved from
  `tree_asset_lookup.csv`'s Competition Group column; an explicit
  `[export] twig_density` in TOML still overrides both uniformly.
- `growth_models.toml`'s `max_height` decoupled from `forest.toml`'s export
  `max_height`, so a quick-testing export height cap can no longer silently
  truncate step 3's calibration passes.
- Dataset overview now shows the actual surround radius (r00/r07/r15)
  instead of collapsing every non-zero radius into a single "Surround"
  bucket, which had been discarding r15 data.
- `config.paths.radius_label()`: single source of truth for the zero-padded
  `r{N}` label, replacing four separate inline implementations.

### Changed

- CI now builds its environment from `environment.yml` via setup-micromamba
  instead of a hand-written pip list, which had drifted and pulled in an
  untested numpy version; `environment.yml` gains `pytest` and `ruff`.
- PVE preset generation disabled by default at dataset export to reduce
  step-4 load (per-tree wind JSON export is unaffected).
- README's Zenodo DOI badge switched to a static shields.io badge — the
  dynamic badge endpoint was intermittently failing GitHub's image proxy.

### Fixed

- Chapman-Richards asymptote fits pinned at their own upper bound (5x
  observed max height) are now rejected and fall back to observed max
  height, instead of driving 7 of 11 species toward a fictitious ~100m
  export target.
- Calibration time is now bounded by a real height target (`max_height=20`)
  rather than defaulting to an unbounded ~1800s timeout per species.
- Removed a leftover quick-testing height cap (15m) that was silently
  truncating both calibration passes.
- Dataset export now derives the exported radius list from
  `config.surround_radii` instead of a hardcoded `--export-trees 1,2`, which
  had dropped the last configured radius from every dataset export.
- Dataset overview icon matching now uses the current `r{radius}` filename
  convention instead of a stale `surr`/`open` tag, restoring
  `dataset_overview.md`/`.csv` generation.
- `requires-python` corrected to `>=3.12` to match pylometree's actual
  dependency floor.
- Test suite and `growpy.utils.analysis` no longer require a Grove licence
  to import/run: Grove-dependent test modules are skipped, and the
  module-scope import was moved to only the two methods that need it.

## [0.2.0] - 2026-07-23

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
