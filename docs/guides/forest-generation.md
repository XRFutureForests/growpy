# Forest Generation (manual run)

The hand-driven path for generating one forest from a CSV you control. This is the
original "clean step" pipeline: initialise config once, then run four CLI scripts.
For batch production of the multi-species dataset, use
[dataset-workflow.md](dataset-workflow.md) instead.

Every flag below is documented in [../reference/cli-reference.md](../reference/cli-reference.md);
every config key in [../reference/configuration.md](../reference/configuration.md).

---

## Prerequisites

- `conda activate growpy` and `pip install -e .`
- A licensed [The Grove 2.3](https://www.thegrove3d.com/) at `src/the_grove_23/`
- `growpy-init-config` has been run (creates `config/`)

## The pipeline

```
prepare_assets -> convert_twigs -> create_growth_models -> generate_forest
```

Steps are CSV-driven: each only processes the species present in the input CSV.

### Step 1 — prepare assets

Copies Grove presets, textures, and twigs for the CSV's species into `data/assets/`.

```bash
python src/growpy/cli/prepare_assets.py --csv data/input/test.csv
```

### Step 2 — convert twigs

Converts twig `.blend` files to USD (skeletal + static) with alpha-trim
densification for clean Nanite silhouettes.

```bash
python src/growpy/cli/convert_twigs.py --csv data/input/test.csv
```

### Step 3 — create growth models

Simulates height/DBH curves and fits a height-to-age model per species. Add
`--ingest-yield-tables` to populate the yield-table store and calibrate against it.

```bash
python src/growpy/cli/create_growth_models.py --csv data/input/test.csv --ingest-yield-tables
```

### Step 4 — generate forest

Simulates the forest with inter-tree light competition and exports Nanite
assemblies to `data/output/forest/`.

```bash
python src/growpy/cli/generate_forest.py --csv data/input/test.csv
```

## Input CSV format

Minimum columns:

```csv
x,y,species,height
0,0,Norway spruce,5
```

Optional columns: `z`, `fid`, `dbh`, `twig_density`, `individual_type`. Accepted
species names (and aliases) come from `config/tree_asset_lookup.csv` — see
[../reference/naming-conventions.md](../reference/naming-conventions.md).

Useful step-4 flags:

| Flag | Effect |
|---|---|
| `--quality high` | quality preset (see `quality.toml`) |
| `--height-interval 5` | multi-stage export every 5 m of height |
| `--export-trees 2` | export only these fids (others still compete for light) |
| `--skeleton-reduce 0.5` | cut bone count (UE 32,767-bone limit) |

## Where the secondary exports plug in

Step 4 also emits, by default unless disabled in config:

- **Wind** — a `*_DynamicWind.json` per tree (wind is also baked into the USD skeleton).
- **PVE preset** — a `*.json` per tree unless `[export] skip_pve_json = true` in `forest.toml`.
  See [pve-preset-workflow.md](pve-preset-workflow.md).
- **Unreal import scripts** — generated when `[unreal] import_to_unreal = true`.
  See [unreal-import.md](unreal-import.md).
- **Helios++ OBJ** (secondary feature) — when `[helios] export_obj = true` or
  `generate_forest.py --export-obj`. See [helios-export.md](helios-export.md).

## Troubleshooting

- `ModuleNotFoundError: the_grove_23_core` — Grove symlink missing/wrong; check `src/the_grove_23/modules/`.
- `ModuleNotFoundError: bpy` — `pip install bpy` inside the `growpy` env.
- UE import "bone count exceeds 32767" — re-run step 4 with `--skeleton-reduce 0.5 --skeleton-length 2.5`.
- Out of memory on large forests — lower the quality preset or restrict with `--export-trees`.
