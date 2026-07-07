# Processing Logic — Deep Dive

This document walks through the algorithms behind each pipeline step so you can follow the code without reading every file. For the high-level shape of the pipeline see [pipeline-overview.md](pipeline-overview.md); for per-module reference see [module-reference.md](module-reference.md); for the data contracts between steps see [data-flow.md](data-flow.md).

Conventions used below: `module.function()` is a call, `[module.py]` is a clickable link, indentation indicates the call tree during a run.

## Contents

- [Step 1 — prepare_assets](#step-1--prepare_assets)
- [Step 2 — convert_twigs](#step-2--convert_twigs)
- [Step 3 — create_growth_models](#step-3--create_growth_models)
- [Step 4 — generate_forest](#step-4--generate_forest)
- [Growth-simulation internals](#growth-simulation-internals)
- [Height-milestone snapshot mode](#height-milestone-snapshot-mode)
- [Surround light competition](#surround-light-competition)
- [Per-tree USD export](#per-tree-usd-export)
- [Radial DBH scaling](#radial-dbh-scaling)
- [Twig alpha-trim densification](#twig-alpha-trim-densification)
- [Helios OBJ export](#helios-obj-export)
- [Unreal handoff scripts](#unreal-handoff-scripts)

---

## Step 1 — prepare_assets

**Script:** [`cli/prepare_assets.py`](../../src/growpy/cli/prepare_assets.py)
**Purpose:** Stage the Grove installation into `data/assets/` using standardised names.

```
prepare_assets.main()
└── read CSV -> standardise species names via utils.gbif_species
└── for each unique species:
    ├── copy preset:  src/the_grove_23/presets/<Preset>.seed.json
    │                 -> data/assets/presets/<species_std>.seed.json
    ├── copy texture: src/the_grove_23/textures/<name>.png
    │                 -> data/assets/textures/<species_std>/*.png
    └── mkdir twig dir: data/assets/twigs/<twig_name_snake>/
```

Notes:

- **Species standardisation** uses GBIF canonical names so CSV aliases resolve to a consistent folder name (e.g. `Norway Spruce`, `norway spruce`, `Picea abies` → `norway_spruce`).
- **Twig sharing.** Multiple species can map to the same Grove twig (Norway spruce → `PacificSilverFirTwig`). The `Twig` column in `tree_asset_lookup.csv` is the single source of truth; step 2 reverses that map so the output `.usda` is named by the consuming species, not the donor twig.
- **No Grove API is imported here.** This step is pure file I/O + CSV parsing — cheap and safe to re-run.

## Step 2 — convert_twigs

**Script:** [`cli/convert_twigs.py`](../../src/growpy/cli/convert_twigs.py)
**Purpose:** Convert Grove twig `.blend` files into Nanite-ready `.usda` meshes.

```
convert_twigs.main()
└── build species-per-twig map from tree_asset_lookup.csv
└── for each twig directory:
    └── io.usd.twig_export.process_twig_file(blend_path, species_list, cfg)
        ├── bpy: load .blend, pick the twig collection
        ├── bpy: bake texture paths / material slots
        ├── classify faces via io.usd.twig_geometry (tube vs. plane)
        ├── alpha-trim -> remove fully-transparent plane triangles
        ├── densify planes (subdiv) so Nanite clusters render clean silhouettes
        ├── interior-decimate planes (keep boundary)
        ├── decimate tubes (branches) harder, preserve topology
        └── write two variants per species:
            - <species>_foliage_skeletal.usda  (geometry + skeleton, no materials)
            - <species>_foliage_static.usda    (geometry + materials, no skeleton)
```

The tube/plane split is the heart of Step 2 — see [twig alpha-trim densification](#twig-alpha-trim-densification) below.

## Step 3 — create_growth_models

**Script:** [`cli/create_growth_models.py`](../../src/growpy/cli/create_growth_models.py)
**Purpose:** Produce a calibrated per-cycle growth model for each species so Step 4 can hit a requested target height in a predictable number of cycles.

```
create_growth_models.main()
├── (optional) --ingest-yield-tables -> pylometree-ingest
└── for each species:
    ├── [1] Uncalibrated simulation
    │   └── utils.analysis.SpeciesGrowthAnalyzer.run_uncalibrated(cycles)
    │       └── Grove.simulate(1) × N, record height/DBH/volume per cycle
    ├── [2] Load reference yield table
    │   └── utils.yield_tables.load_for_species(species)
    │       ├── prefer data/input/yield_tables/<species>.csv
    │       └── else query pylometree store; else skip calibration
    ├── [3] Calibrate
    │   └── utils.yield_tables.fit_chapman_richards(yield_curve)
    │       └── utils.analysis.compute_cycle_deltas(simulated, target)
    │           -> produces:
    │              - grow_length_per_cycle  (interpolated)
    │              - thicken_tips_per_cycle (interpolated)
    │              - target_dbh_per_cycle   (used for radial scaling later)
    │              - static_overrides       (flat constants, e.g. grow_nodes)
    ├── [4] Re-simulate with overrides -> sanity-check residual
    └── [5] Write back
        └── data/assets/growth_models/<species>.seed.json
            + "_yield_table_calibration" block
            (read later by config.preset_overrides.get_species_overrides)
```

Why two simulations? Grove's preset parameters are coupled; instead of solving for them analytically, GrowPy uses the *uncalibrated* growth curve as a baseline, fits a correction per cycle, and validates that the correction actually lands on-target by running the simulation a second time. Plots land in `data/assets/growth_models/` for visual QA.

See [reference/yield-table-calibration.md](../reference/yield-table-calibration.md) for the full mathematical treatment.

## Step 4 — generate_forest

**Script:** [`cli/generate_forest.py`](../../src/growpy/cli/generate_forest.py)
**Purpose:** Grow a forest from a CSV and export USD/OBJ/PVE artefacts.

The CLI is a thin argparse wrapper; it dispatches to one of two pipelines:

| Mode | Pipeline | Trigger |
|---|---|---|
| Standard (target cycles per tree) | [`pipelines.forest_exports.generate_forest_exports`](../../src/growpy/pipelines/forest_exports.py) | default |
| Multi-stage (snapshot every N metres) | [`pipelines.forest_stages.generate_forest_stages`](../../src/growpy/pipelines/forest_stages.py) | `--height-interval > 0` |

### Standard mode (single target cycle per tree)

```
generate_forest_exports(csv, output_dir, config, quality, ...)
├── load CSV, validate required columns {x,y,species,height}
├── clip heights to config.forest_max_height
├── calculate_growth_cycles_from_height(df)
│       └── per-species growth model predicts cycles-to-reach-target-height
│       └── clip to growth_cycle_limit, compute delay = max_cycles - my_cycles
├── forest = core.forest.create_forest(df)           # groves per species/context
├── core.forest.simulate_forest_growth(forest, max_cycles, ...)
│       └── per-cycle loop: overrides -> shade -> weigh_and_bend -> simulate(1)
│       └── then: smooth() × N -> weigh_and_bend()
├── resolve quality_params from quality.toml [quality.<preset>]
├── apply skeleton_overrides (cli flags)
└── io.forest_export.export_individual_trees(forest, df, output_dir, ...)
        └── for each tree:
            ├── io.usd.assembly_export.export_tree_as_nanite_assembly(...)
            │       ├── core.skeleton.build_skeleton(branches)
            │       ├── core.twig.place_twigs(branches)     -> PointInstancer
            │       ├── io.usd.tree_export.build_tree_mesh  -> radial DBH scaling
            │       ├── io.usd.preview.render_preview
            │       └── io.unreal.wind_json.generate_wind_json
            └── (optional) io.unreal.pve_grove_mapper.generate_pve_from_grove
```

### Multi-stage mode (snapshot per height milestone)

```
generate_forest_stages(csv, ...)
├── create_forest, init overrides
├── core.forest.simulate_forest_growth_with_snapshots(
│        forest, max_cycles, snapshot_cycles=[],
│        height_interval=H, max_height=M, ...)
│     -> snapshots:    {cycle: {species: [(model, skeleton, bones, h, dbh), ...]}}
│     -> milestone_map:{cycle: {species: {tree_idx: milestone_h}}}
└── for each (cycle, species, tree) in snapshots:
    └── export_tree_as_nanite_assembly with milestone-tagged filename
        -> {species}_c{cycle}_h{milestone}_d{dbh}_assembly.usda
```

Why snapshots? You often want the same tree at 5 m, 10 m, 15 m, 20 m ... for staged dataset renders. Instead of growing a fresh tree per milestone (which wastes cycles and loses variance consistency), Step 4 grows each tree once and captures model + skeleton each time a milestone height is crossed — see [height-milestone snapshot mode](#height-milestone-snapshot-mode).

---

## Growth-simulation internals

All simulation happens inside [`core.forest`](../../src/growpy/core/forest.py). The public entry points are `simulate_forest_growth` (flat) and `simulate_forest_growth_with_snapshots` (sampled); both share the same per-cycle core, `_run_single_growth_cycle`:

```python
def _run_single_growth_cycle(forest, groves, cycle, total_cycles,
                             species_overrides, preset_overrides,
                             frozen_grove_indices):
    # 1. Apply parameter overrides to every active grove for this cycle
    for grove, species_name in forest:
        species_overrides[species_name].apply_to_grove(grove, cycle, total_cycles)
        if preset_overrides:
            preset_overrides.apply_to_grove(grove, cycle, total_cycles)

    # 2. Cross-grove light competition (multi-species only)
    if len(groves) > 1:
        all_coords = [c for g in groves for c in g.build_shade_geometry_flat()]
        for grove in groves:
            grove.calculate_shade_together(all_coords)

    # 3. Mechanical update + advance one Grove cycle
    for grove in forest:
        grove.weigh_and_bend()
        grove.simulate(1)
```

Key points:

- **Overrides are re-applied every cycle.** `PresetOverrides.apply_to_grove` mutates the live grove preset before `simulate(1)`. This is how calibration corrections land on the right cycle (e.g. apply `grow_length = 0.42 m` on cycle 7 only).
- **Shade is computed across groves.** Each grove publishes a flat point cloud of its branches (`build_shade_geometry_flat`); the union is fed back into every grove's `calculate_shade_together` so branches of species A can shade species B.
- **Grove instances are mutated in place.** Snapshot mode must therefore copy out model+skeleton *before* the next cycle runs. `_build_models_for_grove` rebuilds meshes from the current branch state inside the cycle where the milestone triggered.

### Context splitting (individual_type)

When the CSV has an `individual_type` column (as produced by the dataset planner), `create_forest` groups trees by `(species, individual_type)` instead of just `species`. This keeps each individual (e.g. `open_grown` vs `surround`) in its own single-tree grove so Grove's **intra-grove** shade (always-on) and the per-grove Surround shell do not interfere between independent growth contexts. `create_forest` enables Grove's Surround on any single-tree grove whose `individual_type == "surround"` (or when `[surround] enabled = true`).

**Side effect:** a species may be represented by multiple groves. `_compute_grove_offsets` keeps each grove's tree indices globally unique within that species so snapshot merging stays consistent.

### Smoothing pass

After the per-cycle loop finishes, `_apply_smoothing` runs:

```python
for _ in range(smooth_iterations):
    grove.smooth()
grove.weigh_and_bend()
```

`smooth()` relaxes sharp branch angles; `weigh_and_bend()` re-computes positions from those smoothed angles. Both are required — without the final `weigh_and_bend` the smoothing never shows up in the exported mesh.

---

## Height-milestone snapshot mode

`_simulate_height_threshold_mode` in [core/forest.py](../../src/growpy/core/forest.py) is the engine behind `--height-interval`. It runs the simulation cycle-by-cycle, cheaply polling heights, and captures a snapshot whenever *any* tree crosses a new milestone.

### State machine

```
for cycle in 1..max_cycles:
    _run_single_growth_cycle(forest, frozen_grove_indices=frozen)

    # Poll: measurements[tree_idx] = (height, dbh) per grove
    for each active tree:
        if height > prev_h + 0.01: any_growth = True
        next_uncaptured_milestone = smallest M <= floor(height / interval)*interval
                                    not yet in captured[tree]

    # Stop checks
    if all_trees_captured_all_target_milestones: break
    if not any_growth for plateau_cycles consecutive: break

    # Build models only if at least one tree crossed a new milestone this cycle
    if new_crossings:
        for species with crossings:
            merged_data[species] = _build_models_for_grove(grove, ...)
        snapshots[cycle] = merged_data
        captured[(species, tree)].add(milestone)
        # Freeze species whose trees all finished
        if all(target_milestones[k] <= captured[k] for k in species):
            frozen_grove_indices |= species_grove_indices[species]
```

Design notes:

- **One milestone per tree per cycle.** If a tree jumps from 4.8 m to 12.1 m in a single cycle (unlikely but possible with big `grow_length`), only the 5 m snapshot is captured. Subsequent cycles will pick up 10 m, 15 m etc.
- **Plateau detection** (`cycles_without_growth >= plateau_cycles`) prevents infinite loops when a species stalls below the next milestone. Default threshold: 10 cycles.
- **Grove freezing.** Once a species captures all milestones up to `max_height`, its groves are added to `frozen_grove_indices` and skipped in subsequent `_run_single_growth_cycle` calls. This matters for mixed forests where fast-growing species (spruce) finish early and shouldn't keep accumulating branch state while slow species (beech) are still running.
- **Context-split groves are merged by species.** `_compute_grove_offsets` + `species_grove_indices` let two independent groves for the same species emit one unified snapshot dict per cycle.

---

## Surround light competition

The competed individual (`individual_type == "surround"`) is a **single tree** that
uses Grove's built-in Surround feature instead of a multi-tree cluster. In
`create_forest`, any single-tree grove marked `surround` (or every single-tree
grove when `[surround] enabled = true`) gets `enable_surround()` called on it,
which sets `surround_enabled`/`surround_density`/`surround_distance`/
`surround_height`/`surround_grow` on the grove's properties.

Grove then shades the tree against a statistical shell of virtual neighbours each
cycle — no neighbour trees are planted or simulated, and there is no thinning
step. This replaced the earlier competition-cluster workflow (planting `fid >= 100`
neighbours and moving them outward at height milestones), removing the per-cycle
cost of simulating N extra trees. Grove disables Surround when several trees share
one grove, so this only applies to single-tree contexts.

---

## Per-tree USD export

Entry: `io.usd.assembly_export.export_tree_as_nanite_assembly`. High-level tree of calls:

```
export_tree_as_nanite_assembly(model, skeleton, bones, out_path, ...)
├── assembly.usda          (payload references + PointInstancer for twigs)
│   ├── io.usd.tree_export.build_tree_mesh   -> <species>_<fid>_skeletal.usda
│   │     └── radial scaling via target_dbh  (see below)
│   ├── core.twig.place_twigs                -> twig transforms (pos + rot + scale)
│   └── PointInstancer points to Instances/<twig>.usda
├── shared Instances/ dir (populated once per run via clear_twig_copy_cache)
├── io.usd.preview.render_preview            -> <tree>_preview.png
├── io.unreal.wind_json.generate_wind_json   -> <tree>_DynamicWind.json
└── (optional) io.unreal.pve_grove_mapper.generate_pve_from_grove
```

Key design points:

- **Twigs are shared across trees.** A species-wide `Instances/` directory holds one canonical `.usda` per twig variant. The PointInstancer in every tree assembly references those instances. This is what makes Nanite Assembly in UE 5.7+ efficient: instances deduplicate on disk *and* in the GPU instance buffer.
- **Skeletal variant always emits DynamicWind JSON.** The UE DynamicWind plugin can read the JSON directly, or the SkelRoot prim's `unreal:dynamicWind:jointNames` / `unreal:dynamicWind:jointSimulationGroups` attributes.
- **Bone-limit handling.** UE caps skeletal meshes at 32,767 bones. `tree_export.is_bone_limit_error` detects the USD writer throwing past that; the CLI surfaces a clear message pointing to `--skeleton-reduce`.

---

## Radial DBH scaling

After calibration, a tree's simulated DBH is often still 10–20 % off target, because DBH (diameter at breast height = 1.3 m) depends on many coupled Grove parameters (`thicken_tips`, `grow_nodes`, `thicken_deadwood`, etc.) and cannot be precisely hit by per-cycle overrides alone.

The fix is a post-hoc radial scale at mesh-build time in [`io.usd.tree_export.build_tree_mesh`](../../src/growpy/io/usd/tree_export.py):

```
scale = target_dbh / measured_grove_dbh      # from seed.json target_dbh_per_cycle
for ring in branch_rings:
    for vertex in ring:
        vertex_xy = ring_center_xy + (vertex_xy - ring_center_xy) * scale
```

Only the cross-section radius is scaled; vertex *height* and branch topology are untouched. This means DBH hits target exactly without changing branch length, angle, or skeleton. The same `scale` is written into the skeleton bone radii so DynamicWind physics stays consistent.

Parameters that **do not** affect DBH at 1.3 m (verified by parameter sweep): `thicken_base_scale`, `thicken_base_buttress`, `thicken_base_shape`. They only affect geometry below 1.3 m — so they are irrelevant as calibration levers. `thicken_join` has huge DBH impact but destroys height; unusable.

---

## Twig alpha-trim densification

`io.usd.twig_export.process_twig_file` takes a Grove twig `.blend` (bark cylinders + textured leaf/needle planes) and produces two USD variants. The interesting part is densification and decimation on the *planes* (leaves/needles):

```
classify_faces(mesh)
    -> tube components: closed face islands with 0 boundary edges   (branches)
    -> plane components: face islands with boundary edges           (leaves)

for each plane component:
    alpha_trim(cfg.alpha_threshold)     # drop fully-transparent faces
    boundary_smooth(cfg.smooth_iters)   # soften silhouette after trim
    if interior_decimate_enabled and face_count > threshold:
        decimate_interior(keep_boundary=True)  # needles too small -> skipped

for each tube component:
    decimate(cfg.tube_ratio)            # stems heavily reduced; no need for detail
```

The key guarantee: boundary edges of every plane component are preserved, because Nanite's automatic cluster LOD can only simplify interior geometry. Silhouettes drive leaf visibility at distance — reducing them destroys the "tree shape". Interior decimation is safe because interior vertices don't affect the silhouette.

Species notes (from empirical measurement):

- Norway spruce twig: 14 tube components (4,736 faces) + 2,205 plane components (9,482 faces). Needles are 3–5 faces each with no interior → interior decimation no-ops on them.
- Broadleaf twigs (oak, beech) benefit strongly once alpha-trim densification replaces 1 big alpha plane with N smaller leaf-shaped components.

---

## Helios OBJ export

When `[helios] export_obj = true`, Step 4 bakes the USD assemblies into Wavefront OBJ for [Helios++ LiDAR simulation](https://github.com/3dgeo-heidelberg/helios).

```
io.helios.obj_export.export_forest_obj(usda_paths, out_dir, cfg)
├── for each USDA:
│   ├── usd.Stage.Open -> traverse SkelRoot + Mesh prims
│   ├── bake twig PointInstancer transforms into flat triangle lists
│   ├── classify faces by material name:
│   │       bark, branch, wood, dead, stem, twig  -> "twig_wood"
│   │       everything else                       -> "twig_leaf"
│   └── (optional) io.helios.mesh_simplify.simplify(faces, target_ratio)
├── emit combined forest.obj + forest.mtl
├── (optional) individual/<species>_<fid>.obj per tree
└── (optional) io.helios.helios_scene.emit_scene_xml
        -> <part> per tree with translate filter = CSV coord
```

Material-aware simplification preserves leaf area (LAI is the usual LiDAR target) but heavily decimates bark. The OBJ up-axis matches the `[helios] obj_up_axis` setting — Helios scenes default to Z-up.

See [guides/helios-export.md](../guides/helios-export.md) for the recommended workflow.

---

## Unreal handoff scripts

After all Step 4 workers finish (dataset mode) or the single generate_forest call returns (manual mode), `step_runner.generate_unreal_scripts` is called **once** to emit the import scripts:

```
generate_unreal_scripts(output_dir, include_static)
├── io.usd.assembly_export.create_combined_twig_usda
│       -> Instances/combined_twigs.usda (one stage referencing all twigs)
├── io.unreal.unreal_scripts.generate_unreal_import_script
│       -> per-species VRAM-batched import_batch_NN.py (+ instance batch)
├── io.unreal.unreal_scripts.generate_unreal_cleanup_script
│       -> clean_assets.py (dry-run safe)
├── if config.unreal_generate_wind_data:
│     io.unreal.wind_import_script.generate_wind_import_script
├── if config.unreal_generate_pve_presets:
│     io.unreal.pve_foliage_data.generate_all_foliage_data  -> FoliageData.json
│     io.unreal.pve_import_script.generate_pve_preset_import_script
│     io.unreal.pve_graph_script.generate_pve_graph_script
└── if config.unreal_import_to_unreal and config.unreal_voxelization:
      io.unreal.nanite_voxelize_script.generate_nanite_voxelize_script
```

The scripts are **generated on the host** but **executed inside UE** via the Python Editor Script Plugin. Two design constraints drive the split:

- **Parallel species would race.** Two subprocess workers regenerating the same `unreal_scripts/` directory simultaneously produces torn files. Generating once at the end is race-free.
- **VRAM-aware batching.** Large twig meshes (100k+ tris each) cannot be imported in one pass without OOMing UE's editor. `generate_unreal_import_script` splits imports into batches sized by total triangle count so each batch fits the user's target VRAM budget.

See [guides/unreal-import.md](../guides/unreal-import.md) for the runtime workflow.
