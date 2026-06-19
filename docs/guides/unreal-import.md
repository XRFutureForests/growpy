# Unreal Engine Import Guide

GrowPy emits USD Nanite Assemblies ready for UE 5.7+. This guide covers the full import path: plugins, settings, auto-import scripts, DynamicWind, PVE presets, and Nanite voxelization. Architectural details live in [architecture/processing-logic.md#unreal-handoff-scripts](../architecture/processing-logic.md#unreal-handoff-scripts).

## Prerequisites

| | |
|---|---|
| **Engine** | Unreal Engine 5.7+ (Nanite Assembly needs 5.7) |
| **Plugins** | USD Importer, Nanite (experimental), Nanite Foliage (experimental), Dynamic Wind (experimental), Python Editor Script Plugin |
| **Project settings** | USD Importer → "Use Nanite" enabled; Remote Execution enabled (for auto-import from VS Code) |
| **Host-side** | Python packages `unreal-stubs` optional; `ue_exec` for remote-exec |

## What Step 4 produces for UE

After a forest run, `data/output/forest/` contains everything UE needs:

```text
data/output/forest/
├── Instances/                              # shared twig USDs (PointInstancer targets)
│   ├── norway_spruce_foliage_skeletal.usda
│   └── combined_twigs.usda                 # one stage referencing all twigs
├── <species>/tree_NNNN/
│   ├── <species>_assembly.usda             # Nanite Assembly entry
│   ├── <species>_NNNN_skeletal.usda        # SkelRoot with DynamicWind metadata
│   ├── <species>_NNNN_DynamicWind.json     # DynamicWind sidecar
│   ├── <species>_NNNN.json                 # PVE preset (optional)
│   └── <species>_NNNN_preview.png
├── unreal_scripts/
│   ├── import_batch_00_instances.py        # twigs first (shared)
│   ├── import_batch_01_<species>.py        # per-species assemblies
│   ├── ...
│   ├── clean_assets.py                      # dry-run cleanup
│   ├── wind_import.py                       # DynamicWind data apply
│   ├── pve_preset_import.py                 # PVE preset import (optional)
│   ├── pve_graph_builder.py                 # PVE graph wiring (optional)
│   ├── growpy_nanite_voxelize.py            # post-restart voxelize (optional)
│   └── growpy_FoliageData.json              # PVE foliage data
└── <species>/helios/                        # Helios OBJ (separate guide)
```

## Fastest path — manual drag-drop

1. Open UE, enable required plugins, restart editor.
2. Copy `data/output/forest/` into `<Project>/Content/GrowPy/` (or symlink).
3. Drag `Instances/combined_twigs.usda` into Content Browser first (populates shared twig meshes).
4. Drag per-species `<species>_assembly.usda` files to spawn Nanite Assembly actors.
5. Done. Wind data already embedded in skeleton prim (`unreal:dynamicWind:jointNames`).

Use this path for one-shot previews or small forests. For datasets run the auto-import scripts.

## Auto-import — recommended

Generated scripts land in `unreal_scripts/`. Each is idempotent and VRAM-aware.

### Enable script generation

```toml
# config/unreal.toml
[unreal]
import_to_unreal         = true
project_path             = "/Game/GrowPy/Trees"
db_path                  = "/Game/Assets/TheGrove"
voxelization             = true
generate_wind_data       = true
generate_pve_presets     = true
pve_import_base          = "/Game/GrowPy/PVE"

[unreal.nanite]
fallback_percent         = 1.0
fallback_target          = "PercentTriangles"
fallback_relative_error  = 0.0
trim_relative_error      = 0.0
target_residency_kb      = 1024
lerp_uvs                 = false
max_edge_length_factor   = 0.0
explicit_tangents        = false
position_precision       = -1
normal_precision         = -1
```

### Run the import scripts

Order matters — twigs first, then per-species, then sidecars:

```bash
# From host, via ue_exec (remote python):
ue_exec data/output/forest/unreal_scripts/import_batch_00_instances.py
ue_exec data/output/forest/unreal_scripts/import_batch_01_norway_spruce.py
ue_exec data/output/forest/unreal_scripts/import_batch_02_european_beech.py
# ... one per species

# Sidecars
ue_exec data/output/forest/unreal_scripts/wind_import.py
ue_exec data/output/forest/unreal_scripts/pve_preset_import.py
ue_exec data/output/forest/unreal_scripts/pve_graph_builder.py

# After UE restart (best VRAM headroom):
ue_exec data/output/forest/unreal_scripts/growpy_nanite_voxelize.py
```

`ue_exec` routes via UE's Remote Execution Protocol. Alternative: paste the file contents into the Python console inside UE.

### Batch sizing

`generate_unreal_import_script` splits by total triangle count to fit your VRAM budget. Each batch:

1. Imports USDs.
2. Waits until VRAM drops below threshold before next file.
3. Logs RSS + VRAM bars per file (`_log_rss`, `_vram_bar`).
4. Applies Nanite config to assemblies via `_configure_nanite_assembly`.

If a batch OOMs, reduce `target_residency_kb` or split species manually.

## DynamicWind

Two delivery paths, pick one:

### Inline (preferred, UE 5.7+)

Attributes live on the `SkelRoot` prim inside `*_skeletal.usda`:

- `unreal:dynamicWind:jointNames` (list of bone names)
- `unreal:dynamicWind:jointSimulationGroups` (per-bone group ids)

UE picks these up on import — no extra step.

### Sidecar JSON (legacy / older workflows)

Each tree also has `*_DynamicWind.json`. Apply via:

- Right-click SkeletalMesh in Content Browser → `Scripted Asset Actions` → `Import DynamicWind`.
- Or batch via generated `wind_import.py`.

Useful when debugging or when the importer strips the prim attributes.

## PVE (Procedural Vegetation Editor)

PVE preset JSONs (`<tree>_NNNN.json`) describe foliage-type parameters: scatter density, cull distance, billboard distance, material channels. GrowPy generates them alongside assemblies.

Scripts:

- `pve_preset_import.py` — creates FoliageType assets from JSON presets.
- `pve_graph_builder.py` — wires presets into PVE graph with species-twig mapping.
- `growpy_FoliageData.json` — aggregated data consumed by the graph builder.

See [reference/pve-attribute-reference.md](../reference/pve-attribute-reference.md) for attribute meanings and [guides/pve-preset-workflow.md](pve-preset-workflow.md) for manual workflow.

## Nanite voxelization

Voxelization gives Nanite streaming at distance (fallback mesh representation). Run **after** editor restart for clean VRAM:

```bash
# restart UE editor first
ue_exec data/output/forest/unreal_scripts/growpy_nanite_voxelize.py
```

Configured via `[unreal.nanite]` in `unreal.toml`. The script walks every assembly under `project_path` and calls `_set_nanite_shape_voxelize`.

## Troubleshooting

- **"bone count exceeds 32767"**: run Step 4 with `--skeleton-reduce 0.5 --skeleton-length 2.5`. `skeleton-reduce` is the strongest lever.
- **Twigs missing after import**: `Instances/` batch must run first. Check Content Browser at `/Game/GrowPy/Trees/Instances/`.
- **Materials pink**: master material missing. Import `db_path` assets from Grove master or set `config.unreal_db_path` to correct Content path.
- **VRAM climbs until crash**: lower `target_residency_kb`, split per-species batches, or disable voxelization on first pass.
- **DynamicWind attributes stripped**: re-enable USD Importer → Preserve Custom Prims. Fallback: `wind_import.py` applies JSON sidecars.
- **Redirectors in destination**: generated scripts call `_fixup_dest_redirectors` to clean stale references. Re-run if renames leave dangling paths.

## Cleanup

`clean_assets.py` is **dry-run by default**. Review its log, then flip `dry_run=False` inside the script to actually delete. Removes orphaned assemblies, twigs not referenced by any assembly, and stale redirectors.

## Per-tree metadata

Each assembly exposes sidecar metadata you can introspect in-editor:

| Attribute | Source | Meaning |
|---|---|---|
| `unreal:growpy:species` | USD custom attr | Species standardised name |
| `unreal:growpy:fid` | USD custom attr | CSV fid |
| `unreal:growpy:height` | USD custom attr | Measured grove height (m) |
| `unreal:growpy:dbh` | USD custom attr | Measured DBH (cm, post radial-scale) |
| `unreal:growpy:cycle` | USD custom attr | Grove cycle when captured |

Handy for runtime scatter logic, analytics, or LOD dispatch via blueprint.
