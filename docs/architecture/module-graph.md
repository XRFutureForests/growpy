# Module Dependency Graph

This is the static import graph of the `growpy` package, grouped by layer. Edges
show "imports from". Read top-to-bottom: each layer only depends on layers
below it (with one documented exception in `io/`, where some `io/pve_*` modules
import each other).

## Layered view

> Every shape below is a clickable link to the source file it represents.

```mermaid
flowchart TB
    classDef cli fill:#fde68a,stroke:#92400e,color:#000
    classDef pipe fill:#fbcfe8,stroke:#9d174d,color:#000
    classDef core fill:#bbf7d0,stroke:#166534,color:#000
    classDef iotop fill:#bfdbfe,stroke:#1e3a8a,color:#000
    classDef iousd fill:#bae6fd,stroke:#075985,color:#000
    classDef ioue fill:#a5f3fc,stroke:#155e75,color:#000
    classDef iohel fill:#99f6e4,stroke:#115e59,color:#000
    classDef cfg fill:#e9d5ff,stroke:#6b21a8,color:#000
    classDef util fill:#e5e7eb,stroke:#374151,color:#000
    classDef ext fill:#fecaca,stroke:#991b1b,color:#000

    %% CLI layer
    DP[cli/dataset_pipeline]:::cli
    PA[cli/prepare_assets]:::cli
    CT[cli/convert_twigs]:::cli
    CGM[cli/create_growth_models]:::cli
    GF[cli/generate_forest]:::cli

    %% Pipelines layer
    CSVP[pipelines/dataset_csv_planner]:::pipe
    JP[pipelines/dataset_job_planner]:::pipe
    SR[pipelines/step_runner]:::pipe
    FS[pipelines/forest_stages]:::pipe
    FE[pipelines/forest_exports]:::pipe

    %% Core
    Forest[core/forest]:::core
    Grove[core/grove]:::core
    Tree[core/tree]:::core
    Skel[core/skeleton]:::core
    Twig[core/twig]:::core

    %% IO top level
    FX[io/forest_export]:::iotop

    %% IO usd
    AE[io/usd/assembly_export]:::iousd
    TE[io/usd/tree_export]:::iousd
    TWE[io/usd/twig_export]:::iousd
    Tex[io/usd/texture_utils]:::iousd
    Prev[io/usd/preview]:::iousd
    OV[io/usd/overview]:::iousd

    %% IO unreal
    US[io/unreal/unreal_scripts]:::ioue
    Wind[io/unreal/wind_json]:::ioue
    PVEMap[io/unreal/pve_grove_mapper]:::ioue
    PVEFol[io/unreal/pve_foliage_extractor]:::ioue
    PVEHier[io/unreal/pve_hierarchy_builder]:::ioue
    PVESch[io/unreal/pve_schema]:::ioue
    PVEDef[io/unreal/pve_growth_defaults]:::ioue
    UER[io/unreal/ue_remote]:::ioue

    %% IO helios
    OBJ[io/helios/obj_export]:::iohel
    HEL[io/helios/helios_scene]:::iohel
    MS[io/helios/mesh_simplify]:::iohel

    %% Config
    Cfg[config/core]:::cfg
    Paths[config/paths]:::cfg
    POv[config/preset_overrides]:::cfg
    PVEov[config/pve_species_overrides]:::cfg
    Q[config/quality]:::cfg

    %% Utils
    Log[utils/log]:::util
    Prof[utils/profiling]:::util
    An[utils/analysis]:::util
    YT[utils/yield_tables]:::util
    Plot[utils/plotting]:::util
    Pxr[utils/pxr_init]:::util
    Gbif[utils/gbif_species]:::util
    Nm[utils/naming]:::util
    EN[utils/export_naming]:::util

    %% External
    GC[the_grove_23_core]:::ext
    Bpy[bpy]:::ext
    Pylo[pylometree]:::ext

    %% CLI -> pipelines / core / io
    DP --> CSVP & JP & SR & OV & Log
    PA --> Tex & Gbif & Nm & PVEov & Cfg & Paths & Log
    CT --> TWE & Tex & Pxr & Nm & Log & Bpy
    CGM --> Grove & An & YT & POv & Nm & Cfg & Log & Pylo
    GF --> FS & FE & OBJ & US & AE & POv & Q & Cfg & Paths & Log & Prof & Bpy

    %% Pipelines internals
    SR --> JP
    CSVP --> Nm & Cfg
    JP --> Nm & Cfg
    FS --> Forest & POv & Q & AE & TE & Prev & Wind & PVEMap & EN & Prof & Bpy & GC
    FE --> Forest & POv & Q & FX & TE & Prof & Bpy & GC

    %% Core internals
    Forest --> Grove & Tree & POv & Log & GC
    Grove --> GC
    Tree --> Cfg & GC
    Skel --> Cfg
    Twig --> Cfg

    %% IO internals
    FX --> AE & TE & Prev & Wind & PVEMap
    AE --> TE & Skel & Twig & EN & Q & Paths
    TE --> Skel & MS & Paths
    TWE --> Tex & Pxr
    OBJ --> TE & Twig & Pxr & MS & HEL
    HEL --> Paths
    PVEMap --> PVEFol & PVEHier & PVESch & PVEDef & PVEov
    OV --> Paths

    %% Config internals
    POv --> Cfg & Paths
    Paths --> Cfg
    Q --> Cfg

    %% Utils internals
    An --> YT & Plot & GC
    YT --> Pylo

    %% Click links to source
    click DP    href "../../src/growpy/cli/dataset_pipeline.py"
    click PA    href "../../src/growpy/cli/prepare_assets.py"
    click CT    href "../../src/growpy/cli/convert_twigs.py"
    click CGM   href "../../src/growpy/cli/create_growth_models.py"
    click GF    href "../../src/growpy/cli/generate_forest.py"
    click CSVP  href "../../src/growpy/pipelines/dataset_csv_planner.py"
    click JP    href "../../src/growpy/pipelines/dataset_job_planner.py"
    click SR    href "../../src/growpy/pipelines/step_runner.py"
    click FS    href "../../src/growpy/pipelines/forest_stages.py"
    click FE    href "../../src/growpy/pipelines/forest_exports.py"
    click Forest href "../../src/growpy/core/forest.py"
    click Grove href "../../src/growpy/core/grove.py"
    click Tree  href "../../src/growpy/core/tree.py"
    click Skel  href "../../src/growpy/core/skeleton.py"
    click Twig  href "../../src/growpy/core/twig.py"
    click FX    href "../../src/growpy/io/forest_export.py"
    click AE    href "../../src/growpy/io/usd/assembly_export.py"
    click TE    href "../../src/growpy/io/usd/tree_export.py"
    click TWE   href "../../src/growpy/io/usd/twig_export.py"
    click Tex   href "../../src/growpy/io/usd/texture_utils.py"
    click Prev  href "../../src/growpy/io/usd/preview.py"
    click OV    href "../../src/growpy/io/usd/overview.py"
    click US    href "../../src/growpy/io/unreal/unreal_scripts.py"
    click Wind  href "../../src/growpy/io/unreal/wind_json.py"
    click PVEMap href "../../src/growpy/io/unreal/pve_grove_mapper.py"
    click PVEFol href "../../src/growpy/io/unreal/pve_foliage_extractor.py"
    click PVEHier href "../../src/growpy/io/unreal/pve_hierarchy_builder.py"
    click PVESch href "../../src/growpy/io/unreal/pve_schema.py"
    click PVEDef href "../../src/growpy/io/unreal/pve_growth_defaults.py"
    click UER   href "../../src/growpy/io/unreal/ue_remote.py"
    click OBJ   href "../../src/growpy/io/helios/obj_export.py"
    click HEL   href "../../src/growpy/io/helios/helios_scene.py"
    click MS    href "../../src/growpy/io/helios/mesh_simplify.py"
    click Cfg   href "../../src/growpy/config/core.py"
    click Paths href "../../src/growpy/config/paths.py"
    click POv   href "../../src/growpy/config/preset_overrides.py"
    click PVEov href "../../src/growpy/config/pve_species_overrides.py"
    click Q     href "../../src/growpy/config/quality.py"
    click Log   href "../../src/growpy/utils/log.py"
    click Prof  href "../../src/growpy/utils/profiling.py"
    click An    href "../../src/growpy/utils/analysis.py"
    click YT    href "../../src/growpy/utils/yield_tables.py"
    click Plot  href "../../src/growpy/utils/plotting.py"
    click Pxr   href "../../src/growpy/utils/pxr_init.py"
    click Gbif  href "../../src/growpy/utils/gbif_species.py"
    click Nm    href "../../src/growpy/utils/naming.py"
    click EN    href "../../src/growpy/utils/export_naming.py"
```

## Layer rules (the spine)

The package is structured as a strict layered architecture. From most
dependent to least dependent:

1. **`cli/`** — argparse front-ends only. Allowed to import from anywhere
   below. The CLI scripts contain almost no logic; they parse arguments,
   resolve config, and dispatch to `pipelines/`.
2. **`pipelines/`** — orchestration. The dataset planners
   (`dataset_csv_planner`, `dataset_job_planner`, `step_runner`) never import
   `bpy`; the forest pipelines (`forest_stages`, `forest_exports`) do, and
   only run inside the step-4 subprocess.
3. **`core/`** — pure simulation logic on top of `the_grove_23_core`. Imports
   `config/` and `utils/`. Does **not** import `io/`.
4. **`io/`** — every persistence concern, split into three sub-packages:
   `io/usd/` (Nanite USD assemblies, twigs, textures, previews), `io/unreal/`
   (DynamicWind JSON, PVE configs, import scripts, remote control),
   `io/helios/` (OBJ baking, scene XML, mesh decimation). `io/forest_export.py`
   sits at the top level because it crosses sub-package boundaries.
5. **`config/`** — pure config loading and resolution. Imports only `utils/`.
6. **`utils/`** — leaf modules. No intra-package imports above this level.

**Hot rule for new code:** if you find yourself wanting to import `io/` from
`core/`, you have probably mixed simulation and serialisation — split the
function instead. The cleanest tell is `core/skeleton.py` and `core/twig.py`,
which deliberately contain *only* the math, while the corresponding USD
serialisation lives in `io/usd/assembly_export.py`.

## Spine of the pipeline (most-imported modules)

These are the modules touched by most other modules — changes here ripple
widely, so review them carefully:

| Module | Imported by |
|---|---|
| [`config/core.py`](../../src/growpy/config/core.py) (`get_config`) | every CLI script + most `core/`/`io/` modules |
| [`config/paths.py`](../../src/growpy/config/paths.py) | most `io/` modules, `config/preset_overrides`, `core/skeleton`, `core/twig` |
| [`utils/log.py`](../../src/growpy/utils/log.py) | every CLI script |
| [`core/forest.py`](../../src/growpy/core/forest.py) | `pipelines/forest_stages.py`, `pipelines/forest_exports.py` (transitively pulls in everything in `core/`) |
| [`io/usd/assembly_export.py`](../../src/growpy/io/usd/assembly_export.py) | `pipelines/forest_stages.py`, `io/forest_export.py`, `cli/generate_forest.py` (entry point for the export tree) |
| [`io/usd/tree_export.py`](../../src/growpy/io/usd/tree_export.py) | `io/usd/assembly_export.py`, `io/helios/obj_export.py`, both forest pipelines (shared mesh + radial scaling) |

## Modules that touch external systems

| Module | External system | Notes |
|---|---|---|
| [`cli/convert_twigs.py`](../../src/growpy/cli/convert_twigs.py), [`io/usd/twig_export.py`](../../src/growpy/io/usd/twig_export.py) | `bpy` (Blender) | Step 2 only |
| [`cli/generate_forest.py`](../../src/growpy/cli/generate_forest.py), [`pipelines/forest_stages.py`](../../src/growpy/pipelines/forest_stages.py), [`pipelines/forest_exports.py`](../../src/growpy/pipelines/forest_exports.py), `core/forest.py`, `core/grove.py`, `core/tree.py` | `bpy`, `the_grove_23_core` | Step 4 only |
| [`cli/create_growth_models.py`](../../src/growpy/cli/create_growth_models.py), [`utils/yield_tables.py`](../../src/growpy/utils/yield_tables.py) | `pylometree` (yield tables) | Step 3 only |
| `io/usd/assembly_export.py`, `io/usd/tree_export.py`, `io/usd/twig_export.py`, `io/helios/obj_export.py` | `pxr` (USD) via `utils/pxr_init.py` | Anywhere USD is written |
| [`io/unreal/unreal_scripts.py`](../../src/growpy/io/unreal/unreal_scripts.py), [`io/unreal/ue_remote.py`](../../src/growpy/io/unreal/ue_remote.py), [`tools/ue_exec.py`](../../src/growpy/tools/ue_exec.py) | Unreal Engine (file-drop and remote-control) | Post-export only |
| [`io/helios/mesh_simplify.py`](../../src/growpy/io/helios/mesh_simplify.py) | `bpy` decimator | Helios export only |

## When the layered view doesn't match reality

A few intentional exceptions:

- `io/unreal/pve_*` modules import each other (`pve_grove_mapper` is the
  public face, the other four are its private collaborators). Treat them as
  a single sub-module.
- `io/forest_export.py` lives at the `io/` top level because it crosses
  sub-package boundaries (USD + Unreal + previews from a single grove).
- `pipelines/forest_stages.py` and `pipelines/forest_exports.py` import `bpy`
  even though they sit in the orchestration layer; this is intentional —
  they only run inside the step-4 subprocess, never in the dataset
  orchestrator process.
- `core/forest.py` imports `tqdm` for progress bars — that's a UI concern in
  a "pure" layer, but it's been kept there because the simulation loop is
  the natural place to report progress.

If you discover a new exception while editing, add it here so the next reader
isn't surprised.
