# Module Reference

Per-module reference for [`src/growpy/`](../../src/growpy/). For each module:
**purpose**, **key public functions/classes**, and **who consumes it**. Only
public, non-underscore symbols are listed; helpers prefixed with `_` are
implementation details and are intentionally omitted.

This document is the lookup table for "where does X live and what does it do".
For the layered import view, see [module-graph.md](module-graph.md). For the
end-to-end process flow with clickable nodes, see
[pipeline-overview.md](pipeline-overview.md). For the flat inventory
(including standalone scripts), see [../module-audit.md](../module-audit.md).

> **Layout note (April 2026 refactor).** The `io/` package has been split into
> three sub-packages: [`io/usd/`](../../src/growpy/io/usd/) (USD/Nanite
> exporters), [`io/unreal/`](../../src/growpy/io/unreal/) (Unreal-side
> sidecars and import scripts), [`io/helios/`](../../src/growpy/io/helios/)
> (Helios++ LiDAR pipeline). Pipeline orchestration moved from
> `core/orchestration/` to [`pipelines/`](../../src/growpy/pipelines/), which
> now also contains [`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py)
> and [`forest_exports.py`](../../src/growpy/pipelines/forest_exports.py)
> (extracted from `cli/generate_forest.py`).

---

## CLI layer ([`src/growpy/cli/`](../../src/growpy/cli/))

The CLI scripts are thin argparse wrappers. Almost all logic lives in
[`pipelines/`](../../src/growpy/pipelines/) and [`io/`](../../src/growpy/io/);
the CLI layer only parses arguments, resolves config, and dispatches.

### [`cli/dataset_pipeline.py`](../../src/growpy/cli/dataset_pipeline.py)

**Purpose:** Top-level orchestrator that runs the full 4-step dataset
production across one or more species. Spawns every step as a subprocess so
`bpy` is never imported in the orchestrator process.

**Entry point:** `main()` (also exposed as `growpy-generate-dataset` console
script).

**Key flags:** `--all`, `--species`, `--pilot`, `--steps {1,2,3,4,all}`,
`--generate-csvs`, `--ingest-yield-tables`, `--clean`, `--clean-store`,
`--dry-run`, `--workers N`, `--max-height`.

**Calls:** `pipelines.dataset_csv_planner.{generate_dataset_csvs,
synchronize_dataset_csvs}`, `pipelines.dataset_job_planner.{resolve_species,
list_all_species}`, `pipelines.step_runner.{check_environment, run_step123,
run_species_step4, run_parallel_step4, generate_unreal_scripts}`,
`io.usd.overview.generate_overview_markdown`.

### [`cli/prepare_assets.py`](../../src/growpy/cli/prepare_assets.py) (Step 1)

**Purpose:** Mirror Grove 2.3 source assets into `data/assets/` with
standardised species names and directory layout.

**Reads:** `src/the_grove_23/{presets,textures}/`, `tree_asset_lookup.csv`.
**Writes:** `data/assets/{presets,textures,twigs,pve_configs}/`.
**Calls:** `utils.gbif_species`, `utils.naming`,
`io.usd.texture_utils.{copy_and_resize_texture, ensure_power_of_2_textures,
process_twig_textures}`, `config.pve_species_overrides`, `config.paths`.

### [`cli/convert_twigs.py`](../../src/growpy/cli/convert_twigs.py) (Step 2)

**Purpose:** Convert Grove `.blend` twig meshes to USD foliage files. Imports
`bpy` at module level — must run inside the conda env that bundles Blender.

**Reads:** `data/assets/twigs/<twig>/source.blend`, species→twig map from
`tree_asset_lookup.csv`.
**Writes:** `data/assets/twigs/<twig>/<species>_foliage_skeletal.usda`.
**Calls:** `io.usd.twig_export.process_twig_file`, `io.usd.texture_utils`,
`utils.pxr_init`, `utils.naming`.

### [`cli/create_growth_models.py`](../../src/growpy/cli/create_growth_models.py) (Step 3)

**Purpose:** Run uncalibrated Grove growth, fit against yield tables, store
calibration in `<species>.seed.json`.

**Reads:** `data/assets/presets/`, yield tables (local CSV or `pylometree`
store), `growpy.toml [calibration]`.
**Writes:** `data/assets/growth_models/<species>.seed.json` with the
`_yield_table_calibration` block, plus calibration plots.
**Calls:** `core.grove.create_grove`, `utils.analysis.SpeciesGrowthAnalyzer`,
`utils.yield_tables.{calibrate_species, write_calibration_to_seed_json}`,
`config.preset_overrides`.

### [`cli/generate_forest.py`](../../src/growpy/cli/generate_forest.py) (Step 4)

**Purpose:** The forest generation entry point. Parses arguments, resolves
config, picks the multi-stage vs standard pipeline, then delegates. Imports
`bpy` and `the_grove_23_core` (transitively via the pipeline modules).

**Reads:** Forest CSV, foliage USDAs, `<species>.seed.json` (calibration),
`growpy.toml [forest|export|unreal|helios|quality.<preset>]`.
**Writes:** `data/output/forest/<run>/<species>/{*.usda, *.obj, *.json,
*_unreal_wind.json, *_unreal_pve.json, *_unreal_import.py}`.
**Dispatches to:**

- [`pipelines.forest_stages.generate_forest_stages`](../../src/growpy/pipelines/forest_stages.py)
  when `--height-interval > 0` (multi-stage milestone export).
- [`pipelines.forest_exports.generate_forest_exports`](../../src/growpy/pipelines/forest_exports.py)
  for the default cycle-target export.

Also calls `io.helios.obj_export.export_forest_obj` (when `--export-obj`),
`io.unreal.unreal_scripts.{generate_unreal_import_script,
generate_unreal_cleanup_script}`, and
`io.usd.assembly_export.create_combined_twig_usda`.

---

## Pipelines layer ([`src/growpy/pipelines/`](../../src/growpy/pipelines/))

Pure orchestration. No `bpy` import in the dataset planning modules — only
[`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py) and
[`forest_exports.py`](../../src/growpy/pipelines/forest_exports.py) touch
`bpy`, and they only run inside the step-4 subprocess.

### [`pipelines/dataset_csv_planner.py`](../../src/growpy/pipelines/dataset_csv_planner.py)

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

### [`pipelines/dataset_job_planner.py`](../../src/growpy/pipelines/dataset_job_planner.py)

**Purpose:** Resolve which species to run for a given CLI invocation, and
discover the per-species CSV files on disk.

**Public:**

- `find_species_csv(species_name, dataset_dir=DATASET_DIR) -> Path | None`
- `list_all_species(dataset_dir=DATASET_DIR) -> list[str]`
- `display_names_from_stems(stems) -> list[str]`
- `resolve_species(args, dataset_dir=DATASET_DIR) -> list[str]` — applies
  `--all` / `--species` / `--pilot` selection logic.

**Constants:** `DATASET_DIR` — the project's canonical dataset CSV directory.

### [`pipelines/step_runner.py`](../../src/growpy/pipelines/step_runner.py)

**Purpose:** Subprocess invocation for all four steps. Owns the path mapping
from step number to script. Runs step 4 in parallel via `ProcessPoolExecutor`.

**Public:**

- `STEP_SCRIPTS: dict[int, Path]` — mapping `{1: prepare_assets.py, ...}`.
- `check_environment() -> bool` — verifies `bpy` is importable.
- `run_step123(step, csv_path, dry_run=False, extra_args=None) -> bool` —
  sequential subprocess for one of steps 1–3.
- `run_species_step4(species_name, dataset_dir, dry_run=False, max_height=0,
  skip_unreal_scripts=False) -> bool` — single-species step-4 subprocess.
- `run_parallel_step4(species_list, workers, max_height, dataset_dir) -> list`
  — parallel pool. Returns list of failed species names.
- `generate_unreal_scripts(output_dir, include_static=False) -> None` —
  per-run Unreal import-script generator (called once after parallel step 4
  workers finish, to avoid race conditions).

### [`pipelines/forest_stages.py`](../../src/growpy/pipelines/forest_stages.py)

**Purpose:** Pipeline A — multi-stage forest generation with height-based
snapshots. Captures snapshots at every height milestone (e.g. every 5 m) and
exports each milestone as its own assembly USD with height + DBH encoded in
the filename. Activated when `--height-interval > 0`.

**Public:** `generate_forest_stages(csv_path, output_dir, config, quality,
height_interval, growth_cycle_limit, smooth_iterations, ...)`.

**Calls:** `core.forest.{create_forest, simulate_forest_growth_with_snapshots}`,
`config.preset_overrides.{load_height_dbh_model_from_preset,
load_target_dbh_from_preset, predict_dbh_from_height_model}`,
`config.quality.get_quality_preset`,
`io.usd.assembly_export.{export_tree_as_nanite_assembly,
clear_twig_copy_cache}`,
`io.usd.tree_export.{get_twig_usd_map_for_species, derive_static_from_skeletal,
is_bone_limit_error, handle_bone_limit_error}`,
`io.usd.preview.{generate_preview_image, generate_icon_image,
generate_export_control_image}`,
`io.unreal.wind_json.generate_wind_json`,
`io.unreal.pve_grove_mapper.generate_pve_from_grove`,
`utils.export_naming`, `utils.profiling`.

### [`pipelines/forest_exports.py`](../../src/growpy/pipelines/forest_exports.py)

**Purpose:** Pipeline B — standard forest generation by growth cycles. The
default path: simulates forest growth to a fixed cycle target and exports all
trees in one pass via `io.forest_export.export_individual_trees`.

**Public:** `generate_forest_exports(csv_path, output_dir, config, quality,
growth_cycle_limit, smooth_iterations, ...)`.

**Calls:** `core.forest.{create_forest, simulate_forest_growth}`,
`config.preset_overrides.PresetOverrides`, `config.quality.get_quality_preset`,
`io.forest_export.export_individual_trees`,
`io.usd.tree_export.{is_bone_limit_error, handle_bone_limit_error}`,
`utils.profiling`.

---

## Core simulation layer ([`src/growpy/core/`](../../src/growpy/core/))

Pure simulation logic on top of `the_grove_23_core`. No imports from `io/`
(this is enforced by the layered architecture; see
[module-graph.md](module-graph.md)).

### [`core/forest.py`](../../src/growpy/core/forest.py)

**Purpose:** Forest-level simulation on top of `the_grove_23_core`. The single
biggest module in the package — owns the main simulation loop, growth modes
(height-threshold vs cycle-based), and competition thinning.

**Public:**

- `create_forest(forest_data) -> list[(Grove, species, count, fid_list)]` —
  build per-species (and per-`individual_type`) groves from a CSV DataFrame.
- `simulate_forest_growth(groves, ...)` — drive a forest to a height/cycle
  target without per-cycle snapshots. Used by [`forest_exports.py`](../../src/growpy/pipelines/forest_exports.py).
- `simulate_forest_growth_with_snapshots(groves, ...)` — same, but emits a
  per-cycle snapshot dict shaped as
  `{cycle: {species: [(model, skeleton, bones_info, height, dbh), ...]}}`.
  Used by [`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py).

**Calls:** `core.grove`, `core.tree`, `config.preset_overrides`,
`the_grove_23_core`.

### [`core/grove.py`](../../src/growpy/core/grove.py)

**Purpose:** Thin wrapper around `the_grove_23_core.Grove` creation and tree
addition. Keeps Grove-specific quirks (preset loading, root growing) out of
`forest.py`.

**Public:**

- `create_grove(species=None) -> gc.Grove`
- `grow_and_build_roots(grove, ...)` — runs the post-growth root build pass
  Grove requires before mesh extraction.
- `add_tree_to_grove(grove, x, y, z=0.0, delay=0)` — append a single tree
  with optional delay (for staggered planting).

### [`core/tree.py`](../../src/growpy/core/tree.py)

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

### [`core/skeleton.py`](../../src/growpy/core/skeleton.py)

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

**Consumed by:** `io.usd.tree_export`, `io.usd.assembly_export`.

### [`core/twig.py`](../../src/growpy/core/twig.py)

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

**Consumed by:** `io.usd.assembly_export`, `io.usd.tree_export`,
`io.helios.obj_export`.

---

## I/O top level ([`src/growpy/io/`](../../src/growpy/io/))

### [`io/forest_export.py`](../../src/growpy/io/forest_export.py)

**Purpose:** Cross-format per-tree export orchestration. Sits at the `io/`
top level (sibling to `usd/`, `unreal/`, `helios/`) because it crosses
sub-package boundaries: it produces USD meshes/assemblies, Unreal wind JSON,
Unreal PVE configs, and preview images from a single grove instance.

**Public:** `export_individual_trees(forest, forest_data, output_dir, config,
...)` — top-level entry from [`forest_exports.py`](../../src/growpy/pipelines/forest_exports.py).
Iterates over groves and exports each tree as a sequence of stages.

**Calls:** `io.usd.assembly_export`, `io.usd.tree_export`, `io.usd.preview`,
`io.unreal.wind_json`, `io.unreal.pve_grove_mapper`.

---

## USD export sub-package ([`src/growpy/io/usd/`](../../src/growpy/io/usd/))

### [`io/usd/assembly_export.py`](../../src/growpy/io/usd/assembly_export.py)

**Purpose:** Build Unreal Engine 5.7+ Nanite Assembly USD files. The most
complex module in `io/` because it has to satisfy both the USD schema and
Unreal's Nanite-specific extensions. Owns the in-process twig file copy cache.

**Public:**

- `create_assembly(...)` — top-level: produces a single species' assembly USD
  from a snapshot slice.
- `create_species_assembly(...)` — bundles multiple cycle snapshots into one
  assembly with LODs.
- `export_tree_as_nanite_assembly(...)` — single-tree export used by the
  multi-stage pipeline and the diagnostic tools.
- `validate_assembly(usd_path) -> dict[str, Any]` — sanity-check a written
  USD against the Nanite schema.
- `create_combined_twig_usda(instances_dir, include_static=False)` — combine
  multiple twig prototypes into one USDA referenced by the assembly.
- `clear_twig_copy_cache()` — invalidate the in-process file-copy cache (used
  between runs in the same process).

**Calls:** `io.usd.tree_export`, `core.skeleton`, `core.twig`,
`utils.export_naming`, `config.quality`, `config.paths`.

### [`io/usd/tree_export.py`](../../src/growpy/io/usd/tree_export.py)

**Purpose:** Build the per-tree USD mesh: skeleton attachment, materials,
Nanite attributes, and **radial scaling** (DBH targeting). Shared between
`assembly_export.py` and `helios.obj_export`.

**Public:**

- `build_tree_mesh(...)` — produces the per-tree mesh; this is where the
  `target_dbh / grove_dbh` radial scaling is applied.
- `strip_skeleton_from_usd(skeletal_path, static_path) -> bool` — produce a
  static-only LOD by removing the skeleton from a skeletal USD.
- `derive_static_from_skeletal(...)` — orchestrator helper used by
  [`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py) to emit
  the static variant alongside the skeletal one.
- `add_nanite_attributes_to_usd(usd_path, is_foliage=False) -> bool`
- `get_twig_usd_map_for_species(species, config, ...) -> dict`
- `bundle_twigs_for_species(species, output_dir) -> list[Path]`
- `is_bone_limit_error(error) -> bool`, `handle_bone_limit_error(error)` —
  shared error-handling helpers used by both pipeline modules.

### [`io/usd/twig_export.py`](../../src/growpy/io/usd/twig_export.py)

**Purpose:** The Blender-side twig processor. Run inside `bpy`. Owns the
tube/plane topology classification, alpha-trim densification, and per-twig
USD writing. Excluded from any code-walking tools because of the bpy import.

**Public:**

- `process_twig_file(blend_path, output_path, species, ...)` — top-level entry
  used by [`cli/convert_twigs.py`](../../src/growpy/cli/convert_twigs.py).
  Loads the blend, runs the full densify/trim/decimate/USD pipeline.
- `export_blender_mesh_to_usd(obj, output_path, ...)`
- `clean_static_usd_file(usd_path)`
- `add_skeleton_to_usd_file(usd_path, pivot_point, minimal_export=True)`
- `densify_mesh(obj, subdivision_levels=3, material_indices=None)`
- `densify_mesh_to_target_edge(obj, target_edge_length)`
- `apply_normal_displacement(obj, ...)`
- `trim_by_alpha_mask(obj, alpha_image, ...)`
- `densify_and_trim_interleaved(obj, ...)` — combined densify+alpha-trim loop
  that creates large leaf meshes for broadleaves.
- `smooth_leaf_mesh(obj, ...)`
- `setup_materials_with_textures(...)`
- `copy_opaque_textures_for_skeletal(...)`
- `classify_texture_from_name(name) -> str`

### [`io/usd/texture_utils.py`](../../src/growpy/io/usd/texture_utils.py)

**Purpose:** Texture copy + standardisation helpers shared by
[`prepare_assets.py`](../../src/growpy/cli/prepare_assets.py) and
[`convert_twigs.py`](../../src/growpy/cli/convert_twigs.py). Renames Grove
textures to the project's canonical naming scheme and ensures power-of-2
dimensions.

**Public:** `copy_and_resize_texture(...)`, `ensure_power_of_2_textures(...)`,
`process_twig_textures(...)`.

### [`io/usd/preview.py`](../../src/growpy/io/usd/preview.py)

**Purpose:** Render small preview thumbnails of trees for the dataset overview
and the per-export icon strip.

**Public:** `generate_preview_image(...)`, `generate_icon_image(...)`,
`generate_export_control_image(...)`.

### [`io/usd/overview.py`](../../src/growpy/io/usd/overview.py)

**Purpose:** Aggregate per-species icon previews, preset summaries, and
calibrated growth-model plots into a single `overview.md` for a dataset run.

**Public:** `generate_overview_markdown(forest_dir, height_interval, preset_dir,
models_dir)`, `build_dataset_dataframe(...)`, `generate_icon_grid(...)`.

---

## Helios++ sub-package ([`src/growpy/io/helios/`](../../src/growpy/io/helios/))

### [`io/helios/obj_export.py`](../../src/growpy/io/helios/obj_export.py)

**Purpose:** Convert USDA tree assemblies to Wavefront OBJ + MTL for
Helios++ LiDAR simulation. Bakes twig point-instancers into real geometry,
applies decimation per the `[helios]` config block.

**Public:**

- `export_forest_obj(forest_dir, output_dir, ...)` — top-level entry from
  [`generate_forest.py`](../../src/growpy/cli/generate_forest.py).
- `convert_tree_to_obj(usda_path, obj_path, ...)`
- `write_combined_obj_streaming(...)` — single-pass streaming variant.
- `clear_twig_cache()` — analogue of
  `assembly_export.clear_twig_copy_cache`.

### [`io/helios/helios_scene.py`](../../src/growpy/io/helios/helios_scene.py)

**Purpose:** Generate the Helios++ `scene.xml` that references the per-tree
OBJ files written by `obj_export.py` and places them at the CSV positions.

**Public:** `generate_helios_scene(tree_paths, output_path, ...)`.

### [`io/helios/mesh_simplify.py`](../../src/growpy/io/helios/mesh_simplify.py)

**Purpose:** Aggressive mesh decimation tailored to the Helios export path:
trunk decimation, per-material twig simplification, and prototype-level
reduction. Uses the bundled `bpy` decimator under the hood.

**Public:** `classify_material(material_name)`, `simplify_trunk_mesh(...)`,
`simplify_twig_meshes(...)`, `simplify_prototype(...)`,
`simplify_tree_mesh(...)`.

---

## Unreal sub-package ([`src/growpy/io/unreal/`](../../src/growpy/io/unreal/))

### [`io/unreal/unreal_scripts.py`](../../src/growpy/io/unreal/unreal_scripts.py)

**Purpose:** Generate standalone Python scripts that run inside Unreal Engine
to import the exported assemblies (skeletal + static), apply materials, set
Nanite attributes, configure DynamicWind data, and clean up old assets. Also
produces VRAM-aware batch import scripts for large datasets.

**Public:**

- `generate_unreal_import_script(output_dir, project_path, include_static=False)`
- `generate_unreal_cleanup_script(output_dir, project_path, dry_run=True)`

### [`io/unreal/wind_json.py`](../../src/growpy/io/unreal/wind_json.py)

**Purpose:** Generate the per-tree DynamicWind JSON payload that Unreal's
DynamicWind system uses to animate skeletal trees. Classifies joints by
hierarchy depth so trunk/branch/twig get different stiffnesses.

**Public:**

- `extract_joint_names_from_bones_info(bones_info) -> list[str]`
- `generate_wind_json(tree_usd_path, skeleton, bones_info, output_path)`
- `generate_wind_json_for_species(...)`

### [`io/unreal/pve_grove_mapper.py`](../../src/growpy/io/unreal/pve_grove_mapper.py)

**Purpose:** Map a Grove instance to Unreal's Procedural Vegetation Editor
(PVE) preset JSON. The public face of the `pve_*` collaborators in this
sub-package.

**Public:**

- `create_pve_template_from_reference(reference_json_path) -> dict`
- `map_grove_to_pve(grove, species_name, output_path, ...)`
- `generate_pve_from_grove(grove, output_path, species_name, tree_index, ...)`
  — convenience wrapper used by [`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py).

**Calls:** `io.unreal.pve_foliage_extractor`,
`io.unreal.pve_hierarchy_builder`, `io.unreal.pve_schema`,
`io.unreal.pve_growth_defaults`, `config.pve_species_overrides`.

### [`io/unreal/pve_foliage_extractor.py`](../../src/growpy/io/unreal/pve_foliage_extractor.py), [`pve_hierarchy_builder.py`](../../src/growpy/io/unreal/pve_hierarchy_builder.py), [`pve_schema.py`](../../src/growpy/io/unreal/pve_schema.py), [`pve_growth_defaults.py`](../../src/growpy/io/unreal/pve_growth_defaults.py)

**Purpose:** Private collaborators of `pve_grove_mapper`. Treat them as one
sub-module — see [../pve-attribute-reference.md](../pve-attribute-reference.md)
for the schema details. The split exists so each concern (foliage instancer
extraction, hierarchy parent arrays, schema templates, default growth params)
can be unit-tested independently.

### [`io/unreal/ue_remote.py`](../../src/growpy/io/unreal/ue_remote.py)

**Purpose:** Trigger Unreal Remote Control endpoints from the command line.
Optional — used to drive an already-running editor without manually clicking
the import script. Consumed by [`tools/ue_exec.py`](../../src/growpy/tools/ue_exec.py).

**Public:** `discover_nodes(timeout, bind_address) -> list[dict]`,
`run_command(...)`, `run_file(...)`.

---

## Configuration layer ([`src/growpy/config/`](../../src/growpy/config/))

### [`config/core.py`](../../src/growpy/config/core.py)

**Purpose:** Load `growpy.toml` and expose it as a `GrowPyConfig` object via
`get_config()`. Layered resolution: project root → user override → CLI
override (`config.resolve(args)`).

**Public:**

- `class GrowPyConfig` — dataclass-style holder with attribute access.
- `get_config() -> GrowPyConfig` — cached, lazy load.
- `get_global_config()` / `set_global_config()` — for CLI scripts that need
  to inject an override.

### [`config/paths.py`](../../src/growpy/config/paths.py)

**Purpose:** Canonical path resolution for everything under `data/` and
`src/the_grove_23/`. Owns the species → on-disk filename mapping including
the 3-step twig fallback.

**Public:**

- `get_data_directory() -> Path`
- `get_assets_directory() -> Path`
- `get_preset_path(species) -> Path`
- `get_growth_model_path(species) -> Path`
- `get_bark_texture_path(species) -> Path | None`
- `get_bark_normal_texture_path(species) -> Path | None`
- `get_twig_files_by_type(species) -> dict[str, list[Path]]` — returns
  `{"skeletal": [...], "static": [...]}` for a species.

### [`config/preset_overrides.py`](../../src/growpy/config/preset_overrides.py)

**Purpose:** Runtime modification of Grove preset parameters from
`<species>.seed.json` calibration data. Supports static overrides, per-cycle
interpolated curves, and target-DBH lists. This is the only handoff between
step 3 (calibration) and step 4 (forest generation).

**Public:**

- `class PresetOverrides` — container; the object passed into
  `core.forest.simulate_*`. Owns `apply()`.
- `class StaticOverride`, `class InterpolatedOverride`, `class CycleArrayOverride`
  — the three override modes.
- `parse_override_arg(arg) -> (key, value)` — `--preset-override key=value` parser.
- `create_overrides_from_args(static_args) -> PresetOverrides`
- `load_curves_from_preset(preset_path) -> PresetOverrides` — read from the
  `_yield_table_calibration` block in `<species>.seed.json`.
- `load_target_dbh_from_preset(preset_path) -> list[float]`
- `load_height_dbh_model_from_preset(preset_path) -> dict | None`
- `predict_dbh_from_height_model(height, model) -> float`

### [`config/quality.py`](../../src/growpy/config/quality.py)

**Purpose:** Load LOD/quality presets (`ultra`, `high`, `medium`, `low`,
`performance`) from `growpy.toml`.

**Public:** `get_quality_preset(preset_name) -> dict`.

### [`config/pve_species_overrides.py`](../../src/growpy/config/pve_species_overrides.py)

**Purpose:** Per-species overrides for the PVE mapping (e.g. tweaking
density curves for individual species). Consumed by
`io.unreal.pve_grove_mapper` and `cli/prepare_assets.py`.

**Public:** `create_null_placeholder_config()`, plus the species override
table.

---

## Utility layer ([`src/growpy/utils/`](../../src/growpy/utils/))

### [`utils/log.py`](../../src/growpy/utils/log.py)

**Purpose:** Logging setup shared by every CLI script.
**Public:** `setup_logging(verbose=False)`, `is_verbose() -> bool`.

### [`utils/profiling.py`](../../src/growpy/utils/profiling.py)

**Purpose:** Lightweight per-step timing for forest generation.
**Public:** `class ProfileTimer`, `get_timer() -> ProfileTimer`,
`init_profiler(enabled=True) -> ProfileTimer`.

### [`utils/analysis.py`](../../src/growpy/utils/analysis.py)

**Purpose:** Growth-curve analysis. Owns the Chapman-Richards fit and the
`SpeciesGrowthAnalyzer` class used by step 3.

**Public:**

- `fit_chapman_richards(ages, heights, ...) -> ChapmanRichardsModel`
- `class ChapmanRichardsModel` — `.predict(age)`, `.params`, `.r2`.
- `class PiecewiseLinearModel` — fallback when Chapman-Richards fails.
- `class SpeciesGrowthAnalyzer` — top-level orchestrator: simulate → fit →
  re-simulate → save.

### [`utils/yield_tables.py`](../../src/growpy/utils/yield_tables.py)

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

### [`utils/plotting.py`](../../src/growpy/utils/plotting.py)

**Purpose:** matplotlib plotting helpers for growth curves and calibration
diagnostics. Imported only by `utils.analysis` and step 3.

### [`utils/pxr_init.py`](../../src/growpy/utils/pxr_init.py)

**Purpose:** Bootstrap the USD plugin path before any `pxr` import. Imported
near the top of every USD-touching module.

### [`utils/gbif_species.py`](../../src/growpy/utils/gbif_species.py)

**Purpose:** GBIF-backed common-name → scientific-name resolution. Used by
step 1 to standardise species directory names.

### [`utils/naming.py`](../../src/growpy/utils/naming.py)

**Purpose:** Pure string normalisation: CamelCase → snake_case, species name
standardisation, twig name standardisation. No I/O.

**Public:** `camel_to_snake(name)`, `standardize_species_name(common_name)`,
`standardize_twig_name(...)`, plus the `TEXTURE_CLASSIFICATIONS` and
`TEXTURE_MODIFIERS` constants used by `convert_twigs.py`.

### [`utils/export_naming.py`](../../src/growpy/utils/export_naming.py)

**Purpose:** Filename formatters for height, DBH, and density values used in
exported file paths (e.g. `tree_h12m_dbh28cm.usda`).

**Public:** `format_height_for_filename`, `format_dbh_for_filename`,
`format_density_for_filename`.

---

## Tools ([`src/growpy/tools/`](../../src/growpy/tools/))

Standalone diagnostic CLIs, not part of the production pipeline.

| Module | Purpose |
|---|---|
| [`tools/analyze_usda.py`](../../src/growpy/tools/analyze_usda.py) | Inspect a written USDA assembly: prim count, joint count, materials |
| [`tools/diagnose_growth.py`](../../src/growpy/tools/diagnose_growth.py) | Run an isolated growth simulation with verbose tracing for debugging |
| [`tools/visualize_tree.py`](../../src/growpy/tools/visualize_tree.py) | Render a side-view PNG of a tree mesh for visual sanity-checking |
| [`tools/ue_exec.py`](../../src/growpy/tools/ue_exec.py) | Execute a Python file inside a running Unreal editor via the Remote Control API. Wrapper around [`io.unreal.ue_remote`](../../src/growpy/io/unreal/ue_remote.py) |
