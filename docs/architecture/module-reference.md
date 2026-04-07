# Module Reference

Per-module reference for `src/growpy/`. For each module: **purpose**, **key
public functions/classes** (with inputs and outputs), and **who consumes it**.
Only public, non-underscore symbols are listed; helpers prefixed with `_` are
implementation details and are intentionally omitted.

For the layered import view, see [module-graph.md](module-graph.md). For the
flat inventory (including standalone scripts), see
[../module-audit.md](../module-audit.md).

---

## CLI layer (`src/growpy/cli/`)

### `cli/dataset_pipeline.py`

**Purpose:** Top-level orchestrator that runs the full 4-step dataset
production across one or more species. Spawns every step as a subprocess so
`bpy` is never imported in the orchestrator process.

**Entry point:** `main()` (also exposed via `growpy-generate-dataset-csvs` /
direct invocation).

**Key flags:** `--all`, `--species`, `--pilot`, `--steps {1,2,3,4,all}`,
`--generate-csvs`, `--ingest-yield-tables`, `--dry-run`, `--parallel N`.

**Calls:** `dataset_csv_planner.generate_dataset_csvs`,
`dataset_job_planner.resolve_species`, `step_runner.run_step123`,
`step_runner.run_parallel_step4`, `step_runner.generate_unreal_scripts`,
`overview.generate_overview_markdown`.

### `cli/prepare_assets.py` (Step 1)

**Purpose:** Mirror Grove 2.3 source assets into `data/assets/` with
standardised species names and directory layout.

**Reads:** `src/the_grove_23/{presets,textures}/`, `tree_asset_lookup.csv`.
**Writes:** `data/assets/{presets,textures,twigs}/`.
**Calls:** `utils.gbif_species`, `io.texture_utils`, `config.paths`.

### `cli/convert_twigs.py` (Step 2)

**Purpose:** Convert Grove `.blend` twig meshes to USD foliage files. Imports
`bpy`.

**Reads:** `data/assets/twigs/<twig>/source.blend`, species→twig map from
`tree_asset_lookup.csv`.
**Writes:** `data/assets/twigs/<twig>/<species>_foliage_skeletal.usda`.
**Calls:** `io.twig_export.process_twig_file`, `io.texture_utils`,
`utils.pxr_init`.

### `cli/create_growth_models.py` (Step 3)

**Purpose:** Run uncalibrated Grove growth, fit against yield tables, store
calibration in `seed.json`.

**Reads:** `data/assets/presets/`, yield tables (local CSV or `pylometree`
store), `growpy.toml [calibration]`.
**Writes:** `data/output/seeds/<species>/seed.json`,
`data/output/calibration/*.png`.
**Calls:** `core.grove.create_grove`, `utils.analysis.SpeciesGrowthAnalyzer`,
`utils.yield_tables.calibrate_species`,
`utils.yield_tables.write_calibration_to_seed_json`,
`config.preset_overrides`.

### `cli/generate_forest.py` (Step 4)

**Purpose:** The main forest generation script. Reads a forest CSV, grows each
species' grove, exports USD/OBJ/PVE artefacts, and emits an Unreal import
script. Imports `bpy` and `the_grove_23_core`.

**Reads:** Forest CSV, foliage USDAs, `seed.json` calibration,
`growpy.toml [quality.<preset>]`.
**Writes:** `data/output/forest/<run>/<species>/{*.usda, *.obj, *.json,
dynamic_wind.json, *_unreal_import.py}`.
**Calls:** Almost everything in `core/` and `io/`. The main outbound calls
are `core.forest.{create_forest, simulate_forest_growth_with_snapshots}`,
`io.assembly_export.{create_assembly, create_species_assembly}`,
`io.obj_export.export_forest_obj`,
`io.helios_scene.generate_helios_scene`,
`io.pve_grove_mapper.map_grove_to_pve`,
`io.unreal_scripts.*`, `io.wind_json.generate_wind_json_for_species`.

### `cli/ue_exec.py`

**Purpose:** Trigger remote-control commands inside a running Unreal Engine
editor (uses the Unreal Remote Control API). Optional, post-export.

**Calls:** `io.ue_remote`.

---

## Orchestration layer (`src/growpy/core/orchestration/`)

### `orchestration/dataset_csv_planner.py`

**Purpose:** Build the per-species merged CSVs and the all-species CSV that
feed steps 1–4.

**Public:**

- `generate_merged_csv(species_row, output_path, spacing) -> Path` — write a
  merged CSV (open + competition columns) for a single species.
- `generate_dataset_csvs(output_dir, density="full") -> list[Path]` — produce
  per-species CSVs and `all_species.csv`. Returns the list of files written.
- `synchronize_dataset_csvs(dataset_dir) -> None` — re-emit `all_species.csv`
  from existing per-species CSVs (used after manual edits).

**Calls:** `utils.naming`, `config.core`.

### `orchestration/dataset_job_planner.py`

**Purpose:** Resolve which species to run for a given CLI invocation, and
discover the per-species CSV files on disk.

**Public:**

- `find_species_csv(species_name, dataset_dir=DATASET_DIR) -> Path | None`
- `list_all_species(dataset_dir=DATASET_DIR) -> list[str]`
- `display_names_from_stems(stems) -> list[str]`
- `resolve_species(args, dataset_dir=DATASET_DIR) -> list[str]` — applies
  `--all` / `--species` / `--pilot` selection logic.

**Constants:** `DATASET_DIR` (the project's canonical dataset CSV directory).

### `orchestration/step_runner.py`

**Purpose:** Subprocess invocation for all four steps. Owns the path mapping
from step number to script. Runs step 4 in parallel via
`ProcessPoolExecutor`.

**Public:**

- `STEP_SCRIPTS: dict[int, Path]` — mapping `{1: prepare_assets.py, ...}`.
- `check_environment() -> bool` — verifies `bpy` is importable.
- `run_step123(steps, csv_path, ...)` — sequential subprocess for steps 1–3.
- `run_species_step4(species, csv_path, ...)` — single-species subprocess.
- `run_parallel_step4(species_list, ..., max_workers)` — parallel pool.
- `generate_unreal_scripts(output_dir, include_static=False)` — runs the
  per-run Unreal import-script generator.

---

## Core simulation layer (`src/growpy/core/`)

### `core/forest.py`

**Purpose:** Forest-level simulation on top of `the_grove_23_core`. The single
biggest module in the package — owns the main simulation loop, growth modes
(height-threshold vs cycle-based), and competition thinning.

**Public:**

- `create_forest(forest_data) -> list[(Grove, species, count, fid_list)]` —
  build per-species (and per-`individual_type`) groves from a CSV DataFrame.
- `simulate_forest_growth(groves, ...)` — drive a forest to a height/cycle
  target without per-cycle snapshots. Used by quick runs.
- `simulate_forest_growth_with_snapshots(groves, ...) -> SnapshotData` —
  same, but emits a per-cycle snapshot dict for the export pipeline:
  `{cycle: {species: [(model, skeleton, bones_info, height, dbh), ...]}}`.

**Type alias:** `SnapshotData` — the canonical "what step 4 produces in
memory" type. Almost every export function in `io/` consumes this.

**Calls:** `core.grove`, `core.tree`, `config.preset_overrides`,
`the_grove_23_core`.

### `core/grove.py`

**Purpose:** Thin wrapper around `the_grove_23_core.Grove` creation and tree
addition. Keeps Grove-specific quirks (preset loading, root growing) out of
`forest.py`.

**Public:**

- `create_grove(species=None) -> gc.Grove`
- `grow_and_build_roots(grove, ...)` — runs the post-growth root build pass
  Grove requires before mesh extraction.
- `add_tree_to_grove(grove, x, y, z=0.0, delay=0)` — append a single tree
  with optional delay (for staggered planting).

### `core/tree.py`

**Purpose:** Per-tree measurements derived from a Grove tree object: height,
DBH at 1.3m, growth-cycle prediction. Pure geometry, no I/O.

**Public:**

- `find_max_height_in_branch(branch) -> float`
- `calculate_tree_height(tree) -> float`
- `calculate_dbh_at_height(tree, target_height=1.3) -> float`
- `extract_tree_measurements(grove) -> list[(height, dbh)]`
- `extract_grove_attributes(grove) -> dict[str, Any]`
- `calculate_growth_cycles_from_height(forest_data) -> None` — mutates the
  DataFrame in place to add a `cycles` column based on target heights.

### `core/skeleton.py`

**Purpose:** Pure skeleton math (bone hierarchy, joint transforms, vertex
weights) with **no** USD or Grove dependencies. Designed to be unit-testable.

**Public dataclasses:** `Vector3`, `JointTransform`, `SkeletonHierarchy`.

**Public functions:**

- `convert_grove_vector_to_vector3(grove_vector) -> Vector3`
- `calculate_rotation_to_align(from_vec, to_vec) -> tuple` — quaternion
  rotation between two unit vectors.
- `build_skeleton_hierarchy(bones_info) -> SkeletonHierarchy` — turn the flat
  bone list returned by Grove into a parent-indexed hierarchy.
- `filter_bones_for_mesh(...)` — drop bones outside a mesh's vertex set.
- `calculate_vertex_weights(...)` — distance/falloff vertex skinning.
- `get_bone_data_from_grove(grove)` — extract the canonical bone tuple list.

**Consumed by:** `io.tree_export`, `io.assembly_export`.

### `core/twig.py`

**Purpose:** Pure twig placement math — extract per-twig anchor points,
normals, rotations from a Grove tree and turn them into instancer-ready
quaternions and positions. No USD dependencies.

**Public:**

- `class TwigPlacement` — dataclass: position, rotation quaternion, scale,
  parent bone index, etc.
- `get_face_center_and_normal(...)`
- `normal_to_rotation_matrix(normal) -> 3x3`
- `rotation_matrix_to_quaternion(matrix) -> (w, x, y, z)`
- `extract_twig_placements_from_model(model, ...) -> list[TwigPlacement]`
- `densify_twig_placements(placements, ...)` — interpolate additional twigs
  along long edges.

**Consumed by:** `io.assembly_export`, `io.tree_export`, `io.obj_export`.

---

## I/O and export layer (`src/growpy/io/`)

### `io/assembly_export.py`

**Purpose:** Build Unreal Engine 5.7+ Nanite Assembly USD files. The most
complex module in `io/` because it has to satisfy both the USD schema and
Unreal's Nanite-specific extensions.

**Public:**

- `create_assembly(species, snapshot, output_dir, ...) -> Path` — top-level
  entry: produces a single species' assembly USD from a `SnapshotData` slice.
- `create_species_assembly(...)` — variant that bundles multiple cycle
  snapshots into one assembly with LODs.
- `export_tree_as_nanite_assembly(...)` — single-tree export used by tests
  and the diagnostic tools.
- `validate_assembly(usd_path) -> dict` — sanity check a written USD against
  the Nanite schema. Returns a dict of `{check: bool/str}`.
- `create_combined_twig_usda(...)` — combine multiple twig prototypes into
  one USDA referenced by the assembly.
- `clear_twig_copy_cache()` — invalidate the in-process file-copy cache (used
  between runs in the same process).

**Calls:** `io.tree_export`, `core.skeleton`, `core.twig`, `io.wind_json`,
`utils.export_naming`, `config.quality`, `config.paths`.

### `io/tree_export.py`

**Purpose:** Build the per-tree USD mesh: skeleton attachment, materials,
Nanite attributes, and **radial scaling** (DBH targeting). Shared between
`assembly_export.py` and `obj_export.py`.

**Public:**

- `build_tree_mesh(tree, target_dbh=None, ...) -> mesh data` — the radial
  scaling step that maps Grove DBH to the calibration target.
- `strip_skeleton_from_usd(skeletal_path, static_path) -> bool` — produce a
  static-only LOD by removing the skeleton from a skeletal USD.
- `add_nanite_attributes_to_usd(usd_path, is_foliage=False) -> bool`
- `get_twig_usd_map_for_species(species) -> dict`
- `bundle_twigs_for_species(species, output_dir) -> list[Path]`

### `io/twig_export.py`

**Purpose:** The Blender-side twig processor. Run inside `bpy`. Owns the
tube/plane topology classification, alpha-trim densification, and per-twig
USD writing.

**Public:**

- `process_twig_file(blend_path, output_path, species, ...)` — top-level entry
  used by `cli/convert_twigs.py`. Loads the blend, runs the full
  densify/trim/decimate/USD pipeline.
- `export_blender_mesh_to_usd(obj, output_path, ...)`
- `clean_static_usd_file(usd_path)`
- `add_skeleton_to_usd_file(usd_path, pivot_point, minimal_export=True)`
- `densify_mesh(obj, subdivision_levels=3, material_indices=None)`
- `densify_mesh_to_target_edge(obj, target_edge_length)`
- `apply_normal_displacement(obj, ...)`
- `trim_by_alpha_mask(obj, alpha_image, ...)`
- `densify_and_trim_interleaved(obj, ...)` — the combined densify+alpha-trim
  loop that creates large leaf meshes for broadleaves.
- `smooth_leaf_mesh(obj, ...)`
- `setup_materials_with_textures(...)`
- `copy_opaque_textures_for_skeletal(...)`
- `classify_texture_from_name(name) -> str`

### `io/obj_export.py`

**Purpose:** Convert USDA tree assemblies to Wavefront OBJ + MTL for
Helios++ LiDAR simulation. Bakes twig point-instancers into real geometry,
applies decimation per the `[helios]` config block.

**Public:**

- `export_forest_obj(forest_dir, output_dir, ...)` — top-level entry from
  `generate_forest.py`.
- `convert_tree_to_obj(usda_path, obj_path, ...)`
- `write_combined_obj(...)`, `write_combined_obj_streaming(...)` — single-
  pass and streaming variants.
- `clear_twig_cache()` — analogue of `assembly_export.clear_twig_copy_cache`.

### `io/helios_scene.py`

**Purpose:** Generate the `scene.xml` that Helios++ consumes, referencing the
per-tree OBJ files written by `obj_export.py`.

**Public:** `generate_helios_scene(tree_paths, output_path, ...)`.

### `io/wind_json.py`

**Purpose:** Generate the `dynamic_wind.json` payload that Unreal's
DynamicWind system uses to animate skeletal trees. Classifies joints by
hierarchy depth so trunk/branch/twig get different stiffnesses.

**Public:**

- `extract_joint_names_from_bones_info(bones_info) -> list[str]`
- `generate_wind_json(joint_names, ...)`
- `generate_wind_json_for_species(species, output_path, ...)`

### `io/pve_grove_mapper.py`

**Purpose:** Map a Grove instance to Unreal's Procedural Vegetation Editor
(PVE) preset JSON. The public face of the `pve_*` sub-package.

**Public:**

- `create_pve_template_from_reference(reference_json_path) -> dict`
- `map_grove_to_pve(grove, species_name, output_path, ...)`

**Calls:** `io.pve_foliage_extractor`, `io.pve_hierarchy_builder`,
`io.pve_schema`, `io.pve_growth_defaults`, `config.pve_species_overrides`.

### `io/pve_foliage_extractor.py`, `io/pve_hierarchy_builder.py`, `io/pve_schema.py`, `io/pve_growth_defaults.py`

**Purpose:** Private collaborators of `pve_grove_mapper`. Treat as one
sub-package — see [pve-attribute-reference.md](../pve-attribute-reference.md)
for the schema details.

### `io/unreal_scripts.py`

**Purpose:** Generate standalone Python scripts that run inside Unreal Engine
to import the exported assemblies (skeletal + static), apply materials, and
clean up old assets.

**Public:** `generate_import_script(...)`,
`generate_cleanup_script(...)`, `generate_all_scripts(forest_dir, ...)`.

### `io/ue_remote.py` / `cli/ue_exec.py`

**Purpose:** Trigger Unreal Remote Control endpoints from the command line.
Optional — used to drive an already-running editor without manually clicking
the import script.

### `io/overview.py`

**Purpose:** Aggregate per-species icon previews, preset summaries, and
calibrated growth-model plots into a single `overview.md` for a dataset run.

**Public:** `generate_overview_markdown(dataset_dir, output_path)`.

### `io/texture_utils.py`

**Purpose:** Texture copy + standardisation helpers shared by
`prepare_assets.py` and `convert_twigs.py`. Renames Grove textures to the
project's canonical scheme.

### `io/mesh_simplify.py`

**Purpose:** Generic mesh decimation helpers shared by `tree_export` and
`twig_export` (and indirectly by `obj_export`). Wraps the underlying
decimator with preset ratios.

### `io/preview.py`

**Purpose:** Render small preview thumbnails of trees/twigs for inclusion in
the dataset overview (used by `overview.py`).

---

## Configuration layer (`src/growpy/config/`)

### `config/core.py`

**Purpose:** Load `growpy.toml` and expose it as a `GrowPyConfig` object via
`get_config()`. Layered resolution: project root → user override → CLI
override.

**Public:**

- `class GrowPyConfig` — dataclass-style holder with attribute access.
- `get_config() -> GrowPyConfig` — cached, lazy load.
- `get_global_config()` / `set_global_config()` — for CLI scripts that need
  to inject an override.

### `config/paths.py`

**Purpose:** Canonical path resolution for everything under `data/` and
`src/the_grove_23/`. Owns the species → on-disk filename mapping including
the 3-step twig fallback.

**Public:**

- `get_data_directory() -> Path`
- `get_assets_directory() -> Path`
- `get_preset_path(species) -> Path`
- `get_growth_model_path(species) -> Path`
- `get_bark_texture_path(species) -> Optional[Path]`
- `get_bark_normal_texture_path(species) -> Optional[Path]`
- `get_twig_files_by_type(species) -> dict[str, list[Path]]` — returns
  `{"skeletal": [...], "static": [...]}` for a species.

### `config/preset_overrides.py`

**Purpose:** Runtime modification of Grove preset parameters from
`seed.json` calibration data. Supports static overrides, per-cycle
interpolated curves, and target-DBH lists.

**Public:**

- `class StaticOverride` — single-value override.
- `class InterpolatedOverride` — start/end interpolation between cycles.
- `class CycleArrayOverride` — explicit per-cycle list.
- `class PresetOverrides` — container; the object passed into
  `core.forest.simulate_*`. Owns `apply()`.
- `parse_override_arg(arg) -> (key, value)` — `--override key=value` parser.
- `parse_curve_arg(arg) -> (key, start, end, mode)` — `--curve key=start..end`.
- `create_overrides_from_args(args) -> PresetOverrides`
- `load_curves_from_preset(preset_path) -> PresetOverrides` — read from
  `seed.json` `_yield_table_calibration` block.
- `load_target_dbh_from_preset(preset_path) -> list[float]`
- `load_height_dbh_model_from_preset(preset_path) -> dict`
- `predict_dbh_from_height(model, height) -> float`
- `get_species_overrides(species_name) -> PresetOverrides` — top-level
  helper used by `core.forest`.

### `config/quality.py`

**Purpose:** Load LOD/quality presets (`ultra`, `high`, `medium`, `low`,
`performance`, `helios`) from `growpy.toml`.

**Public:** `get_quality_preset(preset_name) -> dict`.

### `config/pve_species_overrides.py`

**Purpose:** Per-species overrides for the PVE mapping (e.g. tweaking
density curves for individual species). Consumed only by
`io.pve_grove_mapper`.

---

## Utility layer (`src/growpy/utils/`)

### `utils/log.py`

**Purpose:** Logging setup shared by every CLI script.
**Public:** `setup_logging(verbose=False)`, `is_verbose() -> bool`.

### `utils/profiling.py`

**Purpose:** Lightweight per-step timing for `generate_forest.py`.
**Public:** `class TimingEntry`, `class ProfileTimer`,
`get_timer() -> ProfileTimer`, `init_profiler(enabled=True) -> ProfileTimer`.

### `utils/analysis.py`

**Purpose:** Growth-curve analysis. Owns the Chapman-Richards fit and the
`SpeciesGrowthAnalyzer` class used by `cli/create_growth_models.py`.

**Public:**

- `fit_chapman_richards(ages, heights, ...) -> ChapmanRichardsModel`
- `class ChapmanRichardsModel` — `.predict(age)`, `.params`, `.r2`.
- `class PiecewiseLinearModel` — fallback when Chapman-Richards fails.
- `class SpeciesGrowthAnalyzer` — top-level orchestrator: simulate → fit →
  re-simulate → save.

### `utils/yield_tables.py`

**Purpose:** Yield-table calibration math (loading is delegated to
`pylometree`). Owns the Chapman-Richards interpolation, height→DBH model
fitting, and the `seed.json` writer.

**Public:**

- `load_lookup_table(project_root) -> dict`
- `estimate_flushes_per_year(...)`
- `fit_height_dbh_model(heights, dbhs) -> dict`
- `predict_dbh_from_height(model, height) -> float`
- `interpolate_yield_table(yt_df, ...) -> dict`
- `compute_grow_length_curve(...) -> list[float]`
- `write_calibration_to_seed_json(seed_path, calibration) -> None`
- `calibrate_species(species, ...) -> dict` — top-level entry called by
  step 3.

### `utils/plotting.py`

**Purpose:** matplotlib plotting helpers for growth curves and calibration
diagnostics. Imported only by `utils.analysis` and step 3.

### `utils/pxr_init.py`

**Purpose:** Bootstrap the USD plugin path before any `pxr` import. Imported
near the top of every USD-touching module.

### `utils/gbif_species.py`

**Purpose:** GBIF-backed common-name → scientific-name resolution. Used by
step 1 to standardise species directory names.

### `utils/naming.py`

**Purpose:** Pure string normalisation: CamelCase → snake_case, species name
standardisation, twig name standardisation. No I/O.

**Public:** `camel_to_snake(name)`, `standardize_species_name(common_name)`,
`standardize_twig_name(...)`.

### `utils/export_naming.py`

**Purpose:** Filename formatters for height, DBH, and density values used in
exported file paths (e.g. `tree_h12m_dbh28cm.usda`).

**Public:** `format_height_for_filename`, `format_dbh_for_filename`,
`format_density_for_filename`.

---

## Tools (`src/growpy/tools/`)

Standalone diagnostic CLIs, not part of the production pipeline.

| Module | Console entry | Purpose |
|---|---|---|
| `tools/analyze_usda.py` | `growpy-analyze-usda` | Inspect a written USDA assembly: prim count, joint count, materials |
| `tools/diagnose_growth.py` | `growpy-diagnose-growth` | Run an isolated growth simulation with verbose tracing for debugging |
| `tools/visualize_tree.py` | `growpy-visualize-tree` | Render a side-view PNG of a tree mesh for visual sanity-checking |
