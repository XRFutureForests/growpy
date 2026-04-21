# Helios++ OBJ Export Guide

GrowPy can bake the forest it generates into Wavefront OBJ + Helios++ scene XML so you can run virtual LiDAR scans against it. This guide covers the workflow end-to-end; for the algorithmic details see [architecture/processing-logic.md#helios-obj-export](../architecture/processing-logic.md#helios-obj-export).

## When to use this

- Simulating a TLS / ALS / UAV-LS campaign before going to the field.
- Generating ground-truth point clouds for ML training (e.g. tree/species segmentation).
- LAI / leaf-area studies where you need per-species material classification in the returns.

If you only want renders in Unreal, skip this guide — OBJ export is purely optional.

## Prerequisites

- A working Step 4 run. Nothing special is needed beyond what the quickstart produces.
- [Helios++](https://github.com/3dgeo-heidelberg/helios) installed separately if you want to run the LiDAR simulation (GrowPy only generates the OBJ/scene).

## Configuration

All Helios options live under `[helios]` in `growpy.toml`:

```toml
[helios]
export_obj       = true      # enable OBJ export
helios_scene     = true      # also emit Helios++ scene XML
individual_obj   = false     # also emit per-tree OBJ files in helios/individual/
obj_up_axis      = "z"       # "z" for Helios-native; "y" for DCC pipelines

[helios.simplification]
enabled = true
bark    = 0.2                # keep 20% of bark triangles (heavy decimation)
leaf    = 0.5                # keep 50% of leaf triangles
branch  = 0.3                # keep 30% of branch cylinders

[helios.simplification.per_species_leaf]
# Species-specific overrides (optional)
"norway_spruce" = 0.7        # keep more needles for conifers
"european_beech" = 0.4
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

If you already have `data/output/forest/` from a run without OBJ export, re-run Step 4 with `--export-obj` — it reuses the existing `*_assembly_static.usda` files without re-simulating. (Static variants contain material bindings needed for leaf/wood classification.)

## Output layout

```text
data/output/forest/
├── european_beech/
│   └── tree_0001/
│       ├── european_beech_assembly.usda
│       └── european_beech_assembly_static.usda   <-- source for OBJ
└── helios/                                        <-- OBJ outputs
    ├── forest.obj                                  combined scene, positions baked
    ├── forest.mtl                                  material library
    ├── helios_scene.xml                            Helios++ scene (if helios_scene=true)
    └── individual/                                 per-tree OBJs (if individual_obj=true)
        └── european_beech_0001.obj
```

Two mutually useful output modes:

| Mode | File(s) | Use case |
|---|---|---|
| Combined OBJ | `forest.obj` (+ `forest.mtl`) | One-shot scan of the whole scene; simplest Helios setup |
| Scene XML + individual OBJs | `helios_scene.xml` + `individual/*.obj` | Per-tree `translate` filters, easier to edit tree positions, faster Helios loading for large scenes |

## Material groups

Faces are classified by material name during export (see [`obj_export.WOOD_MATERIAL_KEYWORDS`](../../src/growpy/io/helios/obj_export.py)):

| Group | Contains | Helios spectrum |
|---|---|---|
| `bark` | trunk + branch cylinders | `helios_spectra` wood |
| `twig_wood` | twig-level stems, dead wood | `helios_spectra` wood |
| `twig_leaf` | leaves / needles | `helios_spectra` `conifer` or `deciduous` |

Conifer/deciduous choice is keyword-based on the species folder name. Override per-species with `[helios.simplification.per_species_leaf]`.

## Running Helios++

With scene XML:

```bash
helios scripts/example.xml --scene data/output/forest/helios/helios_scene.xml
```

A minimal survey XML that references the generated scene:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document>
    <scene id="growpy_forest">
        <part>
            <filter type="objloader"><param type="string" key="filepath" value="forest.obj"/></filter>
        </part>
    </scene>
</document>
```

See the [Helios++ docs](https://github.com/3dgeo-heidelberg/helios/wiki) for scanner configuration and survey templates.

## Simplification tuning tips

Mesh simplification is **material-aware** ([`io.helios.mesh_simplify`](../../src/growpy/io/helios/mesh_simplify.py)): each material group is decimated independently so you can preserve leaf area while drastically reducing bark.

- **LAI preservation.** Keep `leaf` at ≥ 0.5 and set `bark` as aggressive as you like (0.1–0.2). Leaf surface area drives LAI; bark barely does.
- **File-size hotspots.** Conifer needles are the usual bottleneck. A single Norway spruce at 30 m can produce 2M+ triangles uncompressed. Use `per_species_leaf` to dial them down without affecting broadleaves.
- **Geometric degeneracy.** Ratios below ~0.1 tend to collapse twig planes to degenerate triangles; Helios silently drops those. Check the log for `decimation produced degenerate faces` warnings.

## Coordinate systems

- Grove/USD use **Y-up** by default. Helios++ uses **Z-up**. The exporter swaps axes when `obj_up_axis = "z"` (the default recommendation).
- Tree positions come from the CSV `x`, `y`, `z` columns. Combined-OBJ mode bakes them into vertex coordinates; scene-XML mode emits `translate` filters.

See [reference/coordinate-systems.md](../reference/coordinate-systems.md) for the full coordinate-frame table.

## Troubleshooting

- **No assembly files found.** OBJ export needs `*_assembly_static.usda` files. Make sure `config.export_static = true` in Step 4.
- **All leaves classified as `twig_wood`.** Material names in your twig `.blend` don't match the wood keywords (`bark`, `branch`, `wood`, `dead`, `stem`, `twig`). Check the material slots in Blender and rename, or extend `WOOD_MATERIAL_KEYWORDS` in `obj_export.py`.
- **Huge OBJ files.** Enable `[helios.simplification]` and lower the per-group ratios. For very dense forests, prefer `helios_scene = true` with individual OBJs so Helios streams them one per tree.
- **Helios reports "null material".** MTL path is resolved relative to the OBJ file. Copy `forest.mtl` next to `forest.obj` in your survey directory, or adjust the `mtllib` line at the top of `forest.obj`.
