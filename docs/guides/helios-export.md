# Helios++ OBJ Export Guide

GrowPy can bake the forest it generates into Wavefront OBJ + Helios++ scene XML so you can run virtual LiDAR scans against it. This guide covers the workflow end-to-end; for the algorithmic details see [architecture/processing-logic.md#helios-obj-export](../architecture/processing-logic.md#helios-obj-export).

## When to use this

- Simulating a TLS / ALS / UAV-LS campaign before going to the field.
- Generating ground-truth point clouds for ML training (e.g. tree/species segmentation).
- LAI / leaf-area studies where you need per-species material classification in the returns.

If you only want renders in Unreal, skip this guide — OBJ export is purely optional.

## Scope: layout mode only

OBJ/Helios export operates **only** on real spatial layouts (`species/tree_NNNN/`) produced by `growpy-generate-forest` with a placement CSV. Dataset mode (`growpy-dataset-pipeline`, `species/rNN/`) is **not** a supported input: dataset-job x/y coordinates are cosmetic separation between calibration variants, not real tree positions, so there is no meaningful scene for a LiDAR simulation to bake. `dataset_pipeline` has no `--export-obj` passthrough for the same reason. This was decided in XRFF-281 (2026-07-31).

## Prerequisites

- A working Step 4 run. Nothing special is needed beyond what the quickstart produces.
- [Helios++](https://github.com/3dgeo-heidelberg/helios) installed separately if you want to run the LiDAR simulation (GrowPy only generates the OBJ/scene).

## Configuration

All Helios options live under `[helios]` in `helios.toml`:

```toml
[helios]
export_obj       = true      # enable OBJ export
helios_scene     = true      # also emit Helios++ scene XML
individual_obj   = false     # keep per-tree OBJ in each tree_NNNN/ dir (else deleted after the combined OBJ is built)
obj_up_axis      = "z"       # "z" for Helios-native; "y" for DCC pipelines

[helios.simplification]
enabled = true
bark    = 0.2                # keep 20% of bark triangles (heavy decimation)
wood    = 0.2                # keep 20% of twig-wood triangles
leaf    = 0.5                # keep 50% of leaf triangles
fruit   = 0.2                # keep 20% of fruit triangles (e.g. EuropeanOakFruits)

# Per-species overrides for any subset of bark/wood/leaf/fruit. Omitted
# keys, and species not listed here, fall back to the globals above.
[helios.simplification.per_species.norway_spruce]
leaf = 0.7                   # keep more needles for conifers

[helios.simplification.per_species.selected_european_oak]
bark = 0.1
wood = 0.05
leaf = 0.25
```

You can also override from the CLI:

```bash
python src/growpy/cli/generate_forest.py \
    --export-obj \
    --helios-scene \
    --obj-up-axis z \
    --individual-obj
```

## Running the export

### During Step 4

The exporter runs automatically at the end of `generate_forest` when `export_obj = true`. You'll see a `HELIOS OBJ EXPORT (N trees, streaming)` log line.

### Standalone (post-hoc)

If you already have `data/output/forest/` from a run without OBJ export, re-run Step 4 with `--export-obj` — it reuses the existing `*_assembly_static.<usd_format>` files (extension follows `[export] usd_format`, e.g. `.usda` or `.usdc`) without re-simulating. (Static variants contain material bindings needed for leaf/wood classification.)

## Output layout

```text
data/output/forest/
├── european_beech/
│   └── tree_0001/
│       ├── european_beech_assembly.usdc
│       ├── european_beech_assembly_static.usdc     <-- source for OBJ
│       ├── european_beech_helios_static.obj         per-tree OBJ (kept only if individual_obj=true)
│       └── european_beech_helios_static.mtl
├── forest_combined.obj                               combined scene, positions baked, at output_dir root
├── forest_combined.mtl                               material library
└── helios_scene.xml                                  Helios++ scene (if helios_scene=true), at output_dir root
```

Extensions follow `[export] usd_format` (`.usda` or `.usdc`); the example above uses `.usdc`, the live default.

Two mutually useful output modes:

| Mode | File(s) | Use case |
|---|---|---|
| Combined OBJ | `forest_combined.obj` (+ `forest_combined.mtl`) at `output_dir` root | One-shot scan of the whole scene; simplest Helios setup |
| Scene XML + individual OBJs | `helios_scene.xml` at `output_dir` root + per-tree `*_helios_static.obj` inside each `tree_NNNN/` (kept only when `individual_obj=true`) | Per-tree `translate` filters, easier to edit tree positions, faster Helios loading for large scenes |

## Material groups

Faces are classified by material name during export (see [`obj_export.WOOD_MATERIAL_KEYWORDS`](../../src/growpy/io/helios/obj_export.py)):

| Group | Contains | Helios spectrum |
|---|---|---|
| `bark` | trunk + branch cylinders | `helios_spectra` wood |
| `twig_wood` | twig-level stems, dead wood | `helios_spectra` wood |
| `twig_leaf` | leaves / needles | `helios_spectra` `conifer` or `deciduous` |

Conifer/deciduous choice is keyword-based on the species folder name. Override per-species with `[helios.simplification.per_species.<species>]`.

## Per-tree classification codes

For labeled point clouds (e.g. training data for tree/species segmentation), enable per-tree Helios++ classification codes:

```toml
[helios]
classification = true
```

Each material gets a two-digit code `[material][fid]` (11–29), fitting the Helios++/LAS classification range (0–31):

- **material**: `1` = leaf, `2` = wood (covers bark, twig wood, fruit)
- **fid**: `1`–`9`, taken from the CSV `fid` column
- **`0`** is reserved for the ground plane — add ground geometry to the Helios scene separately with `helios_classification = 0`; GrowPy does not generate it

Species is joined on `fid` against the input CSV in post-processing, giving a three-digit `[material][fid][species]` code.

**Requirements:**

- Species must be `selected_*` variants (see `SPECIES_CODES` in [`growpy.io.helios.classification`](../../src/growpy/io/helios/classification.py)) — the `stand_*.csv` fixtures under `data/input/` use these.
- Each species needs at least one leaf and one wood material in its twig assets (checked via `*_face_materials.json` sidecars from `growpy-convert-twigs`).
- Validation runs once before export and raises with a list of errors if either requirement fails.

**Trees beyond fid 9:** the code space only covers `fid` 1–9, since Helios++/LAS classification is 0–31. Trees with `fid > 9` fall back to class `4` (ASPRS "high vegetation") instead of failing the run. A single warning per run states the exact split, e.g.:

```
WARNING: Helios classification covers only fid 1-9 (LAS class range is 0-31).
WARNING:   47 trees in this run; fid 1-9 get per-tree codes 11-29,
WARNING:   the remaining 38 trees (fid 10-47) fall back to class 4 (high vegetation).
```

To label every tree in a run, split the stand into batches of 9 trees or fewer (see the `stand_9trees_*.csv` fixtures for the largest fully-coded example).

## Direct export (bypass USD)

`[export] mode = "helios"` (default: `"unreal"`) writes each tree's OBJ/MTL directly from the Grove model during Step 4, instead of post-processing a USD assembly:

```toml
[export]
mode = "helios"
```

What this skips: the trunk mesh never goes through USD — no skeleton binding, no Nanite Assembly, no PVE JSON, no Unreal script generation for that tree. This is the difference between completing and running out of RAM for very large meshes (30M+ vertices).

What it still uses: twig **prototype** meshes (the small, shared per-species twig assets from `growpy-convert-twigs`) are still read from their static USD files — those are cheap, pre-existing static assets, not per-tree data. Twig **placement** (position/orientation/scale per instance) is computed via the same `extract_twig_placements_from_model` function the USD assembly path uses internally, so placement is identical between the two modes.

`export_mode = "helios"` composes with per-species simplification ratios and per-tree classification codes above. It is only implemented for the default multi-stage pipeline (`[forest] height_interval > 0`); setting `height_interval = 0` (the standard growth-cycle pipeline) together with `export_mode = "helios"` logs an error and skips export rather than silently falling back to the USD path.

## Running Helios++

With scene XML:

```bash
helios scripts/example.xml --scene data/output/forest/helios_scene.xml
```

A minimal survey XML that references the generated scene:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document>
    <scene id="growpy_forest">
        <part>
            <filter type="objloader"><param type="string" key="filepath" value="forest_combined.obj"/></filter>
        </part>
    </scene>
</document>
```

See the [Helios++ docs](https://github.com/3dgeo-heidelberg/helios/wiki) for scanner configuration and survey templates.

## Running large batches in a container

For large stands or `export_mode = "helios"` runs with big meshes, `run_docker.sh` launches a resource-limited Jupyter container (CPU/RAM caps via Docker cgroups) so a single run can't take down the host:

```bash
./run_docker.sh              # defaults: 20 cores, 100 GB RAM
./run_docker.sh 10 50        # 10 cores, 50 GB RAM
GROWPY_MESH_DIR=/path/to/meshes ./run_docker.sh   # mount external mesh/point-cloud data read-only
```

Builds from the repo's `Dockerfile`, mounts the repo read-write, and exposes Jupyter on `http://127.0.0.1:8889` (token `growpy`).

## Simplification tuning tips

Mesh simplification is **material-aware** ([`io.helios.mesh_simplify`](../../src/growpy/io/helios/mesh_simplify.py)): each material group is decimated independently so you can preserve leaf area while drastically reducing bark.

- **LAI preservation.** Keep `leaf` at ≥ 0.5 and set `bark` as aggressive as you like (0.1–0.2). Leaf surface area drives LAI; bark barely does.
- **File-size hotspots.** Conifer needles are the usual bottleneck. A single Norway spruce at 30 m can produce 2M+ triangles uncompressed. Use `leaf_per_species` to dial them down without affecting broadleaves.
- **Geometric degeneracy.** Ratios below ~0.1 tend to collapse twig planes to degenerate triangles; Helios silently drops those. Check the log for `decimation produced degenerate faces` warnings.

## Coordinate systems

- Grove/USD use **Y-up** by default. Helios++ uses **Z-up**. The exporter swaps axes when `obj_up_axis = "z"` (the default recommendation).
- Tree positions come from the CSV `x`, `y`, `z` columns. Combined-OBJ mode bakes them into vertex coordinates; scene-XML mode emits `translate` filters.

See [reference/coordinate-systems.md](../reference/coordinate-systems.md) for the full coordinate-frame table.

## Troubleshooting

- **No assembly files found.** OBJ export needs `*_assembly_static.<usd_format>` files under `species/tree_NNNN/` (layout mode only — see [Scope](#scope-layout-mode-only) above). Make sure `[export] static = true` in Step 4 — it defaults to **false** because the UE 5.7/5.8 Nanite Assembly builder deadlocks on StaticMesh targets, so most configs disable it for the Unreal path and forget it's also required here.
- **All leaves classified as `twig_wood`.** Material names in your twig `.blend` don't match the wood keywords (`bark`, `branch`, `wood`, `dead`, `stem`, `twig`). Check the material slots in Blender and rename, or extend `WOOD_MATERIAL_KEYWORDS` in `obj_export.py`.
- **Huge OBJ files.** Enable `[helios.simplification]` and lower the per-group ratios. For very dense forests, prefer `helios_scene = true` with individual OBJs so Helios streams them one per tree.
- **Helios reports "null material".** MTL path is resolved relative to the OBJ file. Copy `forest_combined.mtl` next to `forest_combined.obj` in your survey directory, or adjust the `mtllib` line at the top of the OBJ file.
