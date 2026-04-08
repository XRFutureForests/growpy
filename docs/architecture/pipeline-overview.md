# Pipeline Overview

GrowPy turns species/position CSVs into Unreal-Engine-ready USD forests by
running a fixed 4-step pipeline. Step 4 (forest generation) imports `bpy`
(Blender Python), so it always runs in a subprocess — the orchestrator
([`dataset_pipeline.py`](../../src/growpy/cli/dataset_pipeline.py)) keeps `bpy`
out of its own process by invoking every step as a subprocess for consistency.

> **How to read the diagrams below.** Every shape is a clickable link to the
> module/function it represents. Click any node to jump straight to the source
> file. The diagrams are the canonical "process flow + entry points" reference;
> for raw structural views (class UML, package import graph) see
> [generated/](generated/).

## End-to-end flow

```mermaid
flowchart TB
    subgraph inputs[Inputs]
        I1[Grove 2.3 source<br/>src/the_grove_23/]
        I2[Species lookup<br/>config/tree_asset_lookup.csv]
        I3[Yield tables<br/>data/input/yield_tables/]
        I4[Forest CSV<br/>data/input/dataset/*.csv]
    end

    subgraph orch[Orchestration]
        O[dataset_pipeline.py<br/>--all / --species / --pilot]
    end

    subgraph steps[Pipeline steps - each runs as a subprocess]
        S1[Step 1<br/>prepare_assets.py]
        S2[Step 2<br/>convert_twigs.py]
        S3[Step 3<br/>create_growth_models.py]
        S4[Step 4<br/>generate_forest.py<br/>imports bpy]
    end

    subgraph artefacts[On-disk artefacts]
        A1[data/assets/presets/<br/>data/assets/textures/]
        A2[data/assets/twigs/<br/>*.usda foliage]
        A3[data/assets/growth_models/<br/>seed.json + calibration]
        A4[data/output/forest/<br/>USD assemblies, OBJ, PVE JSON]
    end

    subgraph downstream[Downstream consumers]
        D1[Unreal Engine 5.7+<br/>via unreal_scripts.py]
        D2[Helios++ LiDAR<br/>via helios_scene.py]
    end

    inputs --> O
    O --> S1 --> A1
    A1 --> S2 --> A2
    A2 --> S3
    I3 --> S3
    S3 --> A3
    A3 --> S4
    A2 --> S4
    I4 --> S4
    S4 --> A4
    A4 --> D1
    A4 --> D2

    click I2 href "../../src/growpy/config/tree_asset_lookup.csv" "Species/twig/texture lookup table"
    click O  href "../../src/growpy/cli/dataset_pipeline.py" "Top-level orchestrator"
    click S1 href "../../src/growpy/cli/prepare_assets.py" "Step 1: copy Grove assets"
    click S2 href "../../src/growpy/cli/convert_twigs.py" "Step 2: .blend to .usda foliage"
    click S3 href "../../src/growpy/cli/create_growth_models.py" "Step 3: simulate + calibrate growth"
    click S4 href "../../src/growpy/cli/generate_forest.py" "Step 4: grow forest, export USD/OBJ/PVE"
    click D1 href "../../src/growpy/io/unreal/unreal_scripts.py" "Unreal import/cleanup script generation"
    click D2 href "../../src/growpy/io/helios/helios_scene.py" "Helios++ scene XML emitter"
```

## What each step does

### Step 1 — `cli/prepare_assets.py`

**Purpose:** Mirror the Grove 2.3 source tree into `data/assets/` in a
predictable layout, normalising species names along the way.

| | |
|---|---|
| **Reads** | `src/the_grove_23/presets/`, `src/the_grove_23/textures/`, `config/tree_asset_lookup.csv` |
| **Writes** | `data/assets/presets/<species>.json`, `data/assets/textures/`, `data/assets/twigs/<twig_name>/` (empty dirs ready for step 2) |
| **Key calls** | `utils.gbif_species` (name standardisation), `io.texture_utils` (texture copy/normalise) |
| **CLI entry** | `growpy-prepare-assets` |

The species → twig mapping in the lookup CSV is what allows multiple species to
share the same Grove twig geometry (e.g. Norway spruce uses
`PacificSilverFirTwig`).

### Step 2 — `cli/convert_twigs.py`

**Purpose:** Run inside Blender (via `bpy`) to load each Grove `.blend` twig
file and export it as a `.usda` foliage mesh that USD can consume.

| | |
|---|---|
| **Reads** | `data/assets/twigs/<twig_name>/source.blend`, plus the `Twig` column from `tree_asset_lookup.csv` to build the species→twig map |
| **Writes** | `data/assets/twigs/<twig_name>/<species>_foliage_skeletal.usda` (named after the *species*, not the donor twig) |
| **Key calls** | `io.twig_export.process_twig_file()`, `io.texture_utils`, `utils.pxr_init` (USD plugin path) |
| **CLI entry** | `growpy-convert-twigs` |

`twig_export.py` is the heart of this step — it does the tube/plane topology
classification described in `MEMORY.md` so leaf/needle planes survive
decimation but stem cylinders get reduced.

### Step 3 — `cli/create_growth_models.py`

**Purpose:** Simulate uncalibrated Grove growth for each species, fit it
against yield-table reference data, store calibration coefficients, and
re-simulate to produce the final per-cycle prediction model.

| | |
|---|---|
| **Reads** | `data/assets/presets/`, yield tables (local CSV or `pylometree` store), `growpy.toml [calibration]` |
| **Writes** | `data/assets/growth_models/<species>.seed.json` (with `_yield_table_calibration` block), calibration plots under `data/assets/growth_models/` |
| **Key calls** | `core.grove.create_grove`, `utils.analysis.SpeciesGrowthAnalyzer`, `utils.yield_tables` (Chapman-Richards interpolation), `utils.plotting` |
| **CLI entry** | `growpy-create-models` |

The calibration coefficients written here are read back by
[`config/preset_overrides.py`](../../src/growpy/config/preset_overrides.py)
during step 4 — that is the only handoff between step 3 and step 4.

### Step 4 — `cli/generate_forest.py`

**Purpose:** Read a forest CSV (positions + species), grow a Grove for each
species applying calibration overrides, and export USD/OBJ/PVE artefacts.

| | |
|---|---|
| **Reads** | Forest CSV, `data/assets/twigs/.../foliage_skeletal.usda`, `data/assets/growth_models/<species>.seed.json` (calibration), `growpy.toml [quality.<preset>]` |
| **Writes** | `data/output/forest/<run>/<species>/*.usda` (Nanite assemblies), `*.obj`/`*.mtl` (Helios), `*.json` (PVE), `*_unreal_wind.json`, Unreal import script |
| **Key calls** | `pipelines.forest_stages.generate_forest_stages` / `pipelines.forest_exports.generate_forest_exports`, `core.forest.{create_forest, simulate_forest_growth_with_snapshots, simulate_forest_growth}`, `io.usd.assembly_export.export_tree_as_nanite_assembly`, `io.usd.tree_export.build_tree_mesh` (radial scaling), `io.helios.obj_export`, `io.helios.helios_scene`, `io.unreal.wind_json`, `io.unreal.pve_grove_mapper`, `io.unreal.unreal_scripts` |
| **CLI entry** | `growpy-generate-forest` |

This step is the only one that imports `bpy` and `the_grove_23_core`, and is
the only step that's parallelised (one subprocess per species via
`step_runner.run_parallel_step4`).

## Inside Step 4 — generation order

`cli/generate_forest.py` is a thin argparse wrapper. The actual pipeline lives
in two sibling modules in [`pipelines/`](../../src/growpy/pipelines/):

- [`forest_stages.py`](../../src/growpy/pipelines/forest_stages.py) — multi-stage
  export, captures snapshots at every height milestone (5 m, 10 m, …) and
  exports each as its own assembly. Activated when `--height-interval > 0`.
- [`forest_exports.py`](../../src/growpy/pipelines/forest_exports.py) — standard
  single-cycle-target export. The default path.

Both end up calling the same exporter chain in [`io/usd/`](../../src/growpy/io/usd/),
[`io/unreal/`](../../src/growpy/io/unreal/), and [`io/helios/`](../../src/growpy/io/helios/).

```mermaid
flowchart LR
    CLI[cli/generate_forest.py<br/>argparse + dispatch]

    subgraph dispatch[Mode dispatch]
        FS[pipelines/forest_stages.py<br/>generate_forest_stages]
        FE[pipelines/forest_exports.py<br/>generate_forest_exports]
    end

    CSV[/forest CSV/] --> CLI
    CLI -->|height_interval > 0| FS
    CLI -->|default| FE

    subgraph sim[Simulation]
        CF[core/forest.py<br/>create_forest]
        SS[core/forest.py<br/>simulate_forest_growth_with_snapshots]
        SG[core/forest.py<br/>simulate_forest_growth]
        Cal[/seed.json<br/>calibration/]
        PO[config/preset_overrides.py<br/>PresetOverrides]
    end

    FS --> CF
    FE --> CF
    CF --> Groves[(per-species<br/>Grove instances)]
    Groves --> SS
    Groves --> SG
    Cal --> PO
    PO --> SS
    PO --> SG
    SS --> Snap[(snapshots:<br/>model, skeleton,<br/>bones, h, dbh)]
    SG --> Snap

    subgraph export[Export chain]
        AE[io/usd/assembly_export.py<br/>export_tree_as_nanite_assembly]
        TE[io/usd/tree_export.py<br/>build_tree_mesh - radial scaling]
        SK[core/skeleton.py]
        TW[core/twig.py]
        FX[io/forest_export.py<br/>export_individual_trees]
        Prev[io/usd/preview.py<br/>preview / icon images]
    end

    Snap --> FX
    FX --> AE
    FS --> AE
    AE --> TE
    AE --> SK
    AE --> TW
    AE --> Prev

    subgraph sidecars[Per-tree sidecars]
        Wind[io/unreal/wind_json.py<br/>generate_wind_json]
        PVE[io/unreal/pve_grove_mapper.py<br/>generate_pve_from_grove]
    end

    AE --> Wind
    AE --> PVE

    subgraph helios[Helios++ post-processing]
        OBJ[io/helios/obj_export.py<br/>export_forest_obj]
        Hsim[io/helios/mesh_simplify.py]
        Hscn[io/helios/helios_scene.py]
    end

    AE --> USDA[/*.usda assemblies/]
    USDA --> OBJ
    OBJ --> Hsim
    OBJ --> Hscn
    OBJ --> OBJF[/*.obj + *.mtl/]
    Hscn --> SceneXML[/scene.xml/]
    Wind --> WJ[/*_unreal_wind.json/]
    PVE --> PJ[/*_unreal_pve.json/]

    subgraph unreal[Unreal handoff]
        OV[io/usd/overview.py<br/>generate_overview_markdown]
        US[io/unreal/unreal_scripts.py<br/>generate_unreal_import_script]
    end

    USDA --> OV
    USDA --> US
    US --> ImportPy[/*_unreal_import.py/]

    click CLI  href "../../src/growpy/cli/generate_forest.py"
    click FS   href "../../src/growpy/pipelines/forest_stages.py"
    click FE   href "../../src/growpy/pipelines/forest_exports.py"
    click CF   href "../../src/growpy/core/forest.py"
    click SS   href "../../src/growpy/core/forest.py"
    click SG   href "../../src/growpy/core/forest.py"
    click PO   href "../../src/growpy/config/preset_overrides.py"
    click AE   href "../../src/growpy/io/usd/assembly_export.py"
    click TE   href "../../src/growpy/io/usd/tree_export.py"
    click SK   href "../../src/growpy/core/skeleton.py"
    click TW   href "../../src/growpy/core/twig.py"
    click FX   href "../../src/growpy/io/forest_export.py"
    click Prev href "../../src/growpy/io/usd/preview.py"
    click Wind href "../../src/growpy/io/unreal/wind_json.py"
    click PVE  href "../../src/growpy/io/unreal/pve_grove_mapper.py"
    click OBJ  href "../../src/growpy/io/helios/obj_export.py"
    click Hsim href "../../src/growpy/io/helios/mesh_simplify.py"
    click Hscn href "../../src/growpy/io/helios/helios_scene.py"
    click OV   href "../../src/growpy/io/usd/overview.py"
    click US   href "../../src/growpy/io/unreal/unreal_scripts.py"
```

## Dataset orchestration (multiple species)

```mermaid
flowchart TB
    User[User] --> DP[cli/dataset_pipeline.py]
    DP -->|--generate-csvs| CSVP[pipelines/dataset_csv_planner.py<br/>generate_dataset_csvs]
    CSVP --> CSVs[/per-species merged CSVs<br/>+ all_species.csv/]
    DP -->|--all / --species / --pilot| JP[pipelines/dataset_job_planner.py<br/>resolve_species + find_species_csv]
    JP --> SR[pipelines/step_runner.py]
    SR -->|"steps 1,2,3<br/>(all_species.csv)"| RUN123[run_step123<br/>subprocess]
    SR -->|"step 4<br/>(per-species CSV)"| RUN4[run_parallel_step4<br/>ProcessPoolExecutor]
    RUN123 --> Done1[Steps 1-3 complete]
    RUN4 --> Done4[Step 4 complete]
    Done4 --> OV[io/usd/overview.py<br/>generate_overview_markdown]
    Done4 --> US2[step_runner.generate_unreal_scripts]

    click DP   href "../../src/growpy/cli/dataset_pipeline.py"
    click CSVP href "../../src/growpy/pipelines/dataset_csv_planner.py"
    click JP   href "../../src/growpy/pipelines/dataset_job_planner.py"
    click SR   href "../../src/growpy/pipelines/step_runner.py"
    click RUN123 href "../../src/growpy/pipelines/step_runner.py"
    click RUN4 href "../../src/growpy/pipelines/step_runner.py"
    click OV   href "../../src/growpy/io/usd/overview.py"
    click US2  href "../../src/growpy/pipelines/step_runner.py"
```

`dataset_pipeline.py` itself does **no Python work** other than argument
parsing and calling into the three orchestration helpers in
[`pipelines/`](../../src/growpy/pipelines/). All actual file I/O happens in
the step scripts that it spawns as subprocesses. This is what makes it safe to run from a shell that
doesn't have `bpy` available — only the spawned step-4 subprocess imports it.

## Where to plug in changes

| If you want to… | Edit this |
|---|---|
| Add a new species | `config/tree_asset_lookup.csv` (+ optional yield-table CSV) |
| Change calibration math | `utils/yield_tables.py` + `config/preset_overrides.py` |
| Change step-4 control flow (multi-stage / standard) | `pipelines/forest_stages.py`, `pipelines/forest_exports.py` |
| Change USD layout | `io/usd/assembly_export.py` (+ `core/skeleton.py`, `core/twig.py`) |
| Change radial scaling / DBH targeting | `io/usd/tree_export.build_tree_mesh` |
| Change quality presets / LOD ratios | `growpy.toml [quality.*]` |
| Change Helios export | `io/helios/obj_export.py`, `io/helios/helios_scene.py` |
| Change PVE mapping for Unreal | `io/unreal/pve_grove_mapper.py` |
| Change DynamicWind metadata | `io/unreal/wind_json.py` |
| Add a new pipeline step | Add CLI script + register in `pipelines/step_runner.STEP_SCRIPTS` + add to `pyproject.toml [project.scripts]` |
| Change dataset planning logic | `pipelines/dataset_*_planner.py` |

For the per-module function/class reference, see
[module-reference.md](module-reference.md).
