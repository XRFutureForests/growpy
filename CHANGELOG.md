# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- `simulate_forest_growth_with_snapshots()` crashed with `ValueError: too many
  values to unpack (expected 2)` for every species in the dataset job-matrix
  path -- a leftover `for (sp, sp_radius), ov in species_overrides.items():`
  from before `species_overrides` was re-keyed to `dict[str, PresetOverrides]`
  (radius dropped as a key when surround became a pure runtime parameter). The
  sibling loop in `simulate_forest_growth()` had already been fixed; this
  second copy, in the snapshot-based path step 4 actually uses, was missed.
  Found by running a full dataset production end-to-end: all 11 species failed
  identically at `PHASE 1: GROWTH SIMULATION WITH HEIGHT MILESTONES`, since
  Grove's own presets define native `_curve` fields (e.g. `drop_decay_curve`)
  independent of yield-table calibration, so `species_overrides` is non-empty
  and this loop always runs.

### Added

- Height-DBH allometry (`DBH = a * H^b`) is now a first-class, standalone
  artifact at `data/assets/allometry/<species>.json`, built by the new
  `growpy-build-allometry` CLI. The fit needs only a yield table's height and
  DBH columns, so it runs in seconds with no Grove simulation, no cycle axis,
  and no surround-radius axis. Previously it was produced only as a by-product
  of the two-pass calibration run and stored inside each seed.json's
  `_yield_table_calibration` block, which `_strip_previous_calibration`
  deletes between runs.
- Export-time DBH correction now fades out below the yield table's own height
  range, leaving Grove's physically derived pipe-model diameter in place for
  saplings the table never described. Each artifact records `height_range_m`
  so the blend knows where the fit stops being supported by data.
- `[forest] growth_cycle_limit` raised 140 -> 160. Measured uncalibrated
  cycles-to-max-height: Douglas fir 147 (45 m), Norway spruce and silver fir 131
  (35 m), common ash 124 (30 m); everything else is under 105. At 140 Douglas
  fir could never reach its top stage -- with calibration either (151 cycles), so
  this was a pre-existing gap rather than a consequence of turning calibration
  off.
- `generate_forest_stages` now warns when a species fails to capture every
  milestone up to its ceiling. A shortfall used to be silent -- the run simply
  exported fewer stages -- which is why the Douglas fir gap went unnoticed.

### Changed

- **Dataset production no longer reads or writes CSVs.** `generate-forest`
  gained `--species NAME`, which builds that species' job rows in memory from
  config alone (`Max Height` in tree_asset_lookup.csv, `[surround] radii`), and
  step 4's subprocess now passes `--species` instead of a merged CSV path. The
  CSVs never carried any information config did not already have -- every
  column was derived, and `x`/`y`/`z` were cosmetic separation -- so they were
  a cache of config that could silently drift from it. `--generate-csvs` still
  dumps them for inspection; nothing reads them back.
- **Steps 1-3 (prepare-assets, convert-twigs, create-models) also no longer
  need a CSV.** Each gained `--dataset`, which resolves species directly from
  `tree_asset_lookup.csv`'s `Dataset` column via
  `dataset_csv_planner._get_dataset_species()` -- the same source step 4's
  `--species` job matrix already used. `dataset_pipeline.py` passes
  `--dataset` to steps 1-3 by default and drops the
  `generate_dataset_csvs()`-before-every-run regeneration this replaces; an
  explicit `--csv PATH` still runs a step from a hand-authored species-lookup
  CSV. `step_runner.run_step123()` gained a `dataset_mode` parameter mirroring
  `run_species_step4`'s `--species` path.
- Species membership now comes from the `Dataset` column of
  tree_asset_lookup.csv rather than from globbing `*_merged.csv`. A file's
  presence was a second, hidden species switch: deleting a merged CSV silently
  dropped that species from the run, and `synchronize_dataset_csvs` would then
  prune it from `all_species.csv` to match. Both are gone.
- `generate_forest_stages`, `generate_forest_exports` and `export_forest_obj`
  take a `forest_data` DataFrame instead of a CSV path; loading moved up to
  `generate_forest.main`, which resolves it from either `--species` (dataset job
  matrix) or the CSV positional (real spatial layout).
- `--export-trees` is no longer synthesised for step 4. The child builds every
  job row for its species, so there is nothing to filter down to.
- **Surround is now a pure runtime parameter.** `create_grove()`,
  `get_species_overrides()`, `get_preset_path()` and `get_growth_model_path()`
  no longer take a radius, and the `.rNN.seed.json` preset family is gone along
  with `_radius_suffix`. A species has one preset and one growth model; the
  radius is applied only through `enable_surround()` at simulation time. This is
  what removes the per-surround-scenario model fan-out: the competition matrix
  now multiplies growth *runs*, which were always required, instead of *models*.
  `radius_label()` is unchanged -- output paths still separate variants.
- **Growth-pacing calibration is off by default** (`[calibration] enabled`).
  It costs two Grove passes per species and only matters when several real trees
  are co-simulated in one grove; dataset production grows to height milestones,
  where pacing does not change the result. `growpy-create-models` and
  `calibrate_species` remain available for the CSV -> plot path.
- DBH realisation at export moved out of `[calibration] align_dbh` to
  `[export] dbh_from_allometry`, since its input is the allometry artifact and
  needs no simulation. `calibration.align_dbh` and `export.radial_scale` are
  still read as deprecated aliases.
- **The milestone ceiling now comes from `tree_asset_lookup.csv`'s `Max Height`**
  rather than from a simulated growth model. The models are bounded by
  `[growth_models] max_height` (20 m), so their Chapman-Richards asymptotes
  either pinned at the 5x guard and fell back to ~20 m or ran away from the
  authored value -- giving the wrong stage count for 10 of 11 dataset species:
  Douglas fir 4 stages instead of 9, silver fir 3 instead of 7, European oak 3
  instead of 6, and Scots pine 11 instead of 6 (a 55 m ceiling for a 30 m
  species). Only silver birch was correct. Dataset totals are now 71 stages.
- `fit_height_dbh_model` now fits in log-log space instead of optimising raw
  residuals. The previous fit seeded from a log-log guess and then minimised
  absolute residuals, letting large-diameter rows dominate and systematically
  underestimating small trees -- by up to 58% *inside* a table's own height
  range (Douglas fir: table 12.1 cm at 12.9 m, fit 5.0 cm). Worst relative
  error across the 11 dataset species drops from 6-58% to 5-18%, and fitted
  exponents tighten from 1.10-2.26 into the allometrically plausible
  1.34-1.80. Rows below 1 cm DBH (a stand only just reaching breast height)
  are excluded, since in log space such a near-zero point dominates the fit.
- Yield table selection for allometry no longer uses the simulation-derived
  `preferred_h50` hint. That hint made table choice depend on how fast a tree
  grew, so a shaded (surround) tree selected a *different* table than the same
  species grown open -- giving one species several contradictory height-DBH
  relationships (Norway spruce predicted 3.9 cm at 5 m open vs 1.3 cm under
  surround). Shading changes how fast a tree reaches a height, not the
  diameter it carries there. Affected species: Norway spruce, Scots pine,
  silver fir, small-leaved linden.
- As a consequence of the two changes above, the selected yield table changes
  for Douglas fir, Norway spruce, small-leaved linden, silver birch, common
  ash and Scots pine. Assets exported before this change used the old values
  and should be regenerated.

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
