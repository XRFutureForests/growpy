# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - 2026-09-17

### 2026-09-16 — every exported asset carries a TAMF record

#### Added

- **TAMF (Tree Asset Metadata Format) 0.2** — `io/tamf.py` writes `<prefix>.tamf.json` next to
  every exported stage on all three routes (USD assembly, PVE growth JSON, Helios OBJ) and, on
  the USD route, the same record as `customData["tamf"]` on the default prim. The record
  states species (GBIF key), the captured height and the exported DBH, the height–DBH
  calibration exactly as the allometry artifact fitted it (yield-table file, region, site
  index, power-law parameters, R², fitted height range), the competition context and surround
  radius, crown base/tip height and plan-view crown area from the skeleton, and the geometric
  contract (metres, Z-up, stem-base origin, CityGML LoD3). `age_years`, `leaf_area_m2` and
  `stem_volume_m3` are `null` — pacing is disabled, foliage is placed in PVE, no volume
  integration exists — so the record never claims more than the pipeline did. Schema:
  `schemas/tamf.schema.json`; reference: `docs/reference/tamf.md`. `TreeExportContext` gains
  `surround_radius_m` and `cycle`. Asset-side exchange component of the Digital Forest Twin
  profile (publications `digital-forest-twin-standard`).

### 2026-09-15 (evening) — the PVE Export click runs unattended

#### Added

- **`growpy-pve-export`** triggers the Export of PVE graphs in the running editor without a
  hand on the mouse. The Export button is a toolkit action (`FPVEditor::OnExport`) with no
  Python or reflection route, so the tool drives the editor's own UI: remote Python enables
  `Accessibility.Enable` and opens the graph, the PCG profiling log tells it when the graph
  has executed, a posted mouse press + Ctrl+E fires the command, and the export-settings
  dialog (Batch + Export) and the overwrite prompt (Continue) are confirmed through Windows
  UI Automation. It then waits for one `Mesh exported successfully` line per export node and
  saves the export folders. Needs neither focus nor an unlocked desktop (verified through a
  locked workstation). A full-tree UI Automation walk of the editor costs 45–250 s, so the
  toolbar button is addressed by its window offset and the dialogs by a shallow search that
  skips the details view; `--toolbar X,Y` overrides the offset and a UIA search is the
  fallback. Ships `pve_export_drive.ps1` + `pve_export_uia.ps1` as package data.

### 2026-09-15 (afternoon) — one density, a growing shell for every species, Grove's conifer presets

#### Changed

- **`[surround] density = 0.75` for every species and radius**; the per-species and
  per-radius density tables are empty (last fitted values kept in comments). Owner
  decision: the fitted thresholds moved crown shape only marginally against seed noise; a
  tree that collapses under 0.75 gets a different seed, not a different density.
- **`[surround] grow = true` for every species** — the shell rises with the conifers too,
  as it did for the 2026-08-13 catalog. The static conifer shell (2026-08-25 / 2026-09-14)
  gave a bole but a crown 0.27–0.43 wide for its height; the growing one gives the
  in-stand form (0.13–0.20). `[surround.grow_per_species]` is empty.
- **Conifer presets are Grove's own again.** `preset_patches.json` no longer patches
  norway_spruce or silver_fir (drop_decay/drop_weak ramps, fir `drop_shaded`); douglas_fir
  and scots_pine were never patched. All four baked presets are key-for-key equal to
  `src/the_grove_23/presets/`.
- `growpy-sweep-surround-density --radii` and `growpy-summarise-surround-density --radii`
  run and read a sweep at a shell-distance set other than the production one;
  `--max-stage` on the summariser ignores stages above the production cap in the gate.

### 2026-09-15 — shell densities decided; the summariser gates on crown base, per seed

#### Changed

- **All 11 `[surround.density_per_species]` values re-fitted from the r08/r16 sweeps**
  (conifers under the static shell): spruce / fir / pine 0.95, douglas 0.85, birch 0.70
  (three seeds), beech 0.75, ash / oak / maple 0.55, linden / cherry 0.75. The previous
  values were the 2026-08-28 growing-shell fits and had never been replaced by the sweep,
  so the 2026-09-14 catalog ran at them; regenerated at the new values the same day.
- `growpy-summarise-surround-density` groups arms by **seed** (a density passes only when
  every seed passes; `n` and the ratio range are printed; `--min-seeds`), refuses to rank
  a single-seed broadleaf on the crown-ø axis, and its default `--gate-axis` is now
  **`base`**: r08's crown base must sit above r16's. The crown base was the sign-stable
  radius axis in every sweep (31/31 static-conifer cells, 6/6 seeded birch cells), where
  crown width flips with the seed. `habit` keeps the old broadleaf-DBH / conifer-crown-ø
  split for re-reading earlier verdicts.

#### Fixed

- The stale-export clean at the start of step 4 derived the species directory with its
  own normalisation that kept hyphens, so "Small-leaved linden" cleaned
  `small-leaved_linden/` (absent) and the export's `small_leaved_linden/` was never
  emptied: every re-run at a new density left the old DBH-named assemblies behind and
  the run summary counted them (10 for 6 produced). Now uses the export's own slug.

### 2026-08-04 → 2026-09-14, condensed (186 commits on `dev`)

No entries were written during this period; this block summarises it by theme. Commit
subjects on `dev` carry the detail; the measurements are in the XR Future Forests Lab
knowledge hub (`04-LOGIC-TIER/growpy-surround-density-calibration`,
`growpy-crown-density-ratchet`) and on Linear XRFF-320 / XRFF-356 / XRFF-390.

#### Changed — the dataset matrix

- The catalog is **11 species × h05/h10/h15 × r08/r16 = 66 assemblies**. `[forest]
  max_height` 25 → 15 and `usd_format` → `usda` (`5eacb91`); `[surround] radii` moved
  [0, 8, 16] → [5, 10, 20] → **[8, 16]** (`fee285e`, owner decision 2026-09-11) — there is
  deliberately no r00 open-grown variant. Density variants stay off.
- **Crown density is no longer corrected in growpy** (`091b0ac`, 2026-09-10): it is
  calibrated in the PVE distributor against Forrester (2017) leaf area. growpy owns crown
  *structure*; the shell density varies per species and radius
  (`[surround.density_per_species_radius]`, `3cc67e8`), with shell height as a second lever
  (`bac10b5`) and a per-species grow/static split (broadleaves grow the shell, conifers
  keep it static — `85fe679`, `ada7940`).
- Crown geometry calibrated per species against published forest allometry (`9047c4f`);
  the Grove knob → crown property map is documented per species (`8fa3068`). Conifer drop
  ramps are declared, not flat-scaled, and get a floor so the tree still builds a stem
  (`c477dff`, `c058f07`); wild cherry gets a drop-rate patch (it stalled at 15 m under
  the shell, `339ce8d`). Shade-induced structural collapse traced to the shell and the
  yield-table pacing curve, not branch shedding (`3bdec66`, `4fe9d5c`, `e615729`).

#### Added — tools

- `growpy-sweep-surround-density` / `growpy-summarise-surround-density`: the surround-density
  sweep harness, in the repo with resume, pruning and per-arm measurement (`34f5a53`,
  `b932418`); `growpy-crown-metrics` (forestry crown dimensions from exported assemblies,
  `429fc3d`); `growpy-calibrate-crown-density`, `growpy-icon-metrics`.
- `growpy-preflight-assembly`, `growpy-ue-import-probe`, `growpy-ue-viewport-probe`
  (SceneCapture2D + post-tick collection, `b311386`); `ue_exec` watchdog gains a VRAM arm
  (`7d15975`) and a resumable relaunched editor (`06f9fc3`).
- `growpy-derive-twig-ladder` and the fir foliage size ladder (seven sprays overlaid on
  the Grove twig, derived at conversion, not stored — `7f181da`, `69fc16d`, `8cbbe70`).

#### Added — PVE route (in-engine growth)

- **Growth-data JSON route** replaces the deprecated Preset-Loader path: real branch
  generations, calibrated radius, decimation as a fraction of trunk radius (`2952f7d`,
  `dd6dbea`, `9231d0e`); `lengthFromRoot` is path length (`9d36300`); a branch's last
  point gets a real apical direction (`46f9a03`).
- PVE graphs are **authored from growpy** per species from a forest export
  (`1b6907a`, `1b07c44`; `generate_pve_graphs` in `unreal.toml`, still `false`), carrying
  the measured twig pose (`26fcbe0`), jitter (`6c55842`), vector ramps (`d01180b`),
  Voxelize by default (`fed4f0d`). The twig palette is authored in PVE's part frame at
  import (`1e02276`, XRFF-445); palette + bark material have an owner,
  `growpy-pve-assets` (`475f0eb`, `e47ceb3`); `growpy-pve-leaf-area` measures leaf area
  at the scale the distributor actually places at (`6fe19f7`).
- `config/pve_calibration.toml` tracks the measured densities and poses (`20e21c7`,
  `11a7198`); it is read as its own file, not through the config merge.
- Materials: per-species PVE material instances the MegaPlants way, virtual textures,
  packed twig atlases (`daf1af5`, `8fa3263`, `0434b9e`, `b08af7b`).

#### Added — compound foliage parts (XRFF-356, experimental)

- A Grove subtree and its leaves bake into one welded USD part (`0db2e10`); parts are
  shared by package path (`3d43e67`); a leafy subtree never gets a twigless prototype
  (`b447752`); the compound path assembles correctly on a conifer (`4fb5c25`).

#### Fixed

- Step 4 no longer reports OK after an export failure or leaves a 0-byte artifact, and a
  MemoryError is reported as memory (`0eebe4a`, XRFF-331/333); an import is recorded as
  done only once its package is on disk (`d8436c5`, XRFF-332); a lost stage is named as a
  build shortfall and counted per radius (`e753f16`, XRFF-334).
- Twig orientation quaternion read as a quaternion, not a 3-vector (`646e8f5`); twigs
  deleted by `build_cutoff_thickness` are recovered instead of guessed (`c491431`); dead
  twigs no longer render as one upright cluster (`a279092`); DBH scaling axis and
  branch-connection artefacts (`fc91ca7`, `ea0bac8`).
- Assembly instance cap 100k → 40k applied before the bone remap (`34c9d9e`, `68dcd68`,
  `a91bce4`); Grove `model.faces`/`model.points` hoisted out of the twig hot loops —
  dataset production 44 min/17 assemblies → 10 min/99 (`d861957`).

#### Removed

- GitHub Actions CI workflow and pre-commit config (`3f06ce1`); the empty `.gitlab-ci.yml`
  (`7faf244`); superseded tools (`45a1baa`).

## [0.4.0] - 2026-08-03

### Fixed

- Combined Helios OBJ export regenerated a fixed bark/twig_wood/twig_leaf
  MTL instead of merging the per-tree MTLs it actually referenced. Harmless
  while all per-tree OBJs used exactly those three unprefixed names, but a
  per-tree material prefix (XRFF-309's classification codes) would have
  made the combined OBJ reference materials the combined MTL never defines,
  silently losing every classification code. `_write_combined_mtl` now
  merges the source MTLs (dedup by name, first definition wins) instead of
  regenerating a fixed material set. Ported from main_tom. (XRFF-310)

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

- 21 curated `stand_*.csv` fixtures under `data/input/` (`stand_1tree_*` through
  `stand_9trees_*`), covering single-species and mixed stands of all six
  `selected_*` species that Helios classification supports. Converted from
  main_tom's schema (`fid,species,x,y,dbh,height,z`) to dev's
  (`fid,species,x,y,z,dbh,height,twig_density`). The natural test inputs for
  classification (`stand_9trees_*` uses the full fid 1-9 code range) and for
  `export_mode = "helios"` runs. (XRFF-312)
- `Dockerfile`, `run_docker.sh`, and `.gitlab-ci.yml` for running
  resource-limited (CPU/RAM-capped) growpy jobs in a container, e.g. large
  `export_mode = "helios"` stands. `run_docker.sh` takes core/memory limits
  as arguments and an optional `GROWPY_MESH_DIR` env var for mounting
  external mesh data read-only. `.gitlab-ci.yml` only disables GitLab Auto
  DevOps; there is no CI on this project by policy. Added `.dockerignore`
  (excludes `data/output`, `data/tmp`, `.git`, caches) so the build context
  doesn't include multi-GB generated output. Ported from main_tom, adapted
  for dev's `the_grove_23` module path and curated `environment.yml`
  (main_tom's is an uncurated `conda env export` dump; not ported).
  (XRFF-312)

- `[export] mode = "helios"` (default `"unreal"`): writes each tree's OBJ/MTL
  directly from the Grove model, bypassing USD, skeleton binding, and Nanite
  Assembly entirely for the trunk. Twig prototype meshes still come from the
  small, pre-existing per-species twig USD assets (shared static assets, not
  per-tree data); twig placement uses the same USD-independent
  `extract_twig_placements_from_model` the assembly path uses internally, so
  placement is identical between modes. Composes with per-tree Helios
  classification codes and simplification ratios. Only implemented for the
  multi-stage pipeline (`[forest] height_interval > 0`, the default); the
  standard growth-cycle pipeline logs an error and refuses the combination
  rather than silently running the USD path. Ported from main_tom, adapted:
  main_tom's version also skipped twig-placement USD writes for the whole
  assembly; here twig prototypes (not placement) still resolve via the
  existing static-USD reader, since duplicating that skeletal-attachment
  math without a way to verify it against real Grove growth was judged too
  risky for a port. (XRFF-311)

- Per-tree Helios++ classification codes for labeled point clouds:
  `[helios] classification = true` (or `--classification`) encodes a
  two-digit `[material][fid]` code (11-29) per material, fitting the
  0-31 LAS classification range. Requires `selected_*` species variants
  and at least leaf + wood materials per species; fid 0 is reserved for
  the ground plane. Trees with fid > 9 fall back to the default class
  (4, high vegetation) since the code space only covers fid 1-9 -- the
  run logs an explicit warning naming the exact coded/uncoded split.
  New `growpy.io.helios.classification` module. Ported from main_tom. (XRFF-309)

- Trunk meshes above 10M faces (`CHUNK_FACE_LIMIT`) are decimated in
  spatial Z-axis chunks instead of in one Blender pass, keeping peak RAM
  proportional to chunk size instead of total mesh size. Ported from
  main_tom. (XRFF-308)

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

- `[helios.simplification.leaf_per_species]` is renamed to
  `[helios.simplification.per_species.<species_clean>]` and now covers
  bark/wood/leaf/fruit (previously leaf only). A `leaf_per_species` key still
  present in config is ignored with a warning naming the new key; it was only
  ever shipped commented-out in the template, so no user config depended on
  the old key. (XRFF-307)

- Bark and twig wood now take independent Helios simplification ratios
  (`bark` / `wood`), instead of sharing a single `wood` ratio. (XRFF-308)

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
