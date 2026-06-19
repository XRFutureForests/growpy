# Dataset Workflow

How to produce the multi-species tree dataset end to end: set up config, choose
which species you want, pick the growth-stage interval and height range, then run
the pipeline. This is the canonical guide for `dataset_pipeline.py`.

For a single hand-built forest instead of the full dataset, see
[forest-generation.md](forest-generation.md). For every config key and CSV column,
see [../reference/configuration.md](../reference/configuration.md).

---

## 1. Set up config

```bash
conda activate growpy
growpy-init-config            # writes starter config into ./config
```

`growpy-init-config` copies the packaged templates into `config/`:

- **9 TOML files** — `general.toml`, `assets.toml`, `twigs.toml`,
  `growth_models.toml`, `forest.toml`, `quality.toml`, `unreal.toml`,
  `helios.toml`, `competition.toml`. There is **no single `growpy.toml`**; every
  `config/*.toml` is loaded and **deep-merged in sorted filename order**, then CLI
  flags override. (Resolution: dataclass defaults -> `config/*.toml` -> CLI.)
- **`tree_asset_lookup.csv`** — the species catalogue (preset, twig, textures,
  growth model, yield search term, max height, competition group, and the
  `Dataset` flag).

Re-run with `--force` to overwrite, or point the pipeline at a different directory
with the `GROWPY_CONFIG=/path/to/config` environment variable.

---

## 2. Choose which species are in the dataset

Dataset membership is controlled in **one place**: the `Dataset` column of
`config/tree_asset_lookup.csv`. A species is included when:

1. its `Dataset` cell is marked (`yes`), **and**
2. it has a `Max Height` (metres) and a `Competition Group`.

```csv
Common Name,...,Max Height,Competition Spacing,Competition Group,Dataset
Norway spruce,...,35,7,slow_conifer,yes      # in the dataset
Grand fir,...,35,8,slow_conifer,             # NOT in the dataset (blank flag)
```

To add a species: mark `Dataset = yes` and fill `Max Height` + `Competition Group`.
To drop one: clear its `Dataset` cell. Nothing else needs editing — the species
list is no longer hardcoded anywhere in the code.

The shipped dataset is 11 southern German species (4 conifer + 7 broadleaf):
Norway spruce, Silver fir, Scots pine, Douglas fir, European beech, European oak,
Common ash, Sycamore maple, Small-leaved linden, Silver birch, Wild cherry.

Verify your selection without running anything heavy:

```bash
python src/growpy/cli/dataset_pipeline.py --generate-csvs   # build the CSVs
python src/growpy/cli/dataset_pipeline.py --list            # list selected species
```

---

## 3. Pick the growth-stage interval and height range

Each species is exported at several growth stages. Two keys in `forest.toml`
control this:

| Key | Meaning |
|---|---|
| `[forest] height_interval` | Stage spacing in **metres**. `5` exports snapshots at 5 m, 10 m, 15 m, ... The growth model maps each height milestone to the matching simulation cycle (and reports the corresponding age/DBH in the filename). `0` disables staging (single export at the target height). |
| `[forest] max_height` | Upper bound in metres. Trees taller than this in the CSV are clamped, which also caps the number of stages. `0` = no cap (use each species' `Max Height`). |

So the **interval** is `height_interval` and the **range** is from the first
interval up to `max_height` (or the species' `Max Height` if `max_height = 0`).

Example — stages every 5 m, capped at 20 m (4 stages: 5/10/15/20 m):

```toml
# config/forest.toml
[forest]
height_interval = 5
max_height = 20
```

`max_height` can also be set per run on the CLI (overrides the TOML): use it for
fast test runs.

```bash
# step 4 only, capped at 15 m for a quick check
python src/growpy/cli/dataset_pipeline.py --pilot --steps 4 --max-height 15
```

You normally do not edit the competition CSVs by hand — see the next section.

---

## 4. How the competition CSVs are generated

`--generate-csvs` reads `tree_asset_lookup.csv` and writes, per species, a
`{species}_merged.csv` plus a combined `all_species.csv`, into
`data/input/dataset/`:

| fid | role | position |
|---|---|---|
| `1` | open-grown (no light competition) | `x = 100, y = 0` |
| `2` | competition centre (exported) | origin |
| `101..` | competition neighbours | regular polygon at the group `planting_distance` |

Neighbour count comes from config (`dataset_competition_neighbors`, default **3**);
spacing and the thinning schedule come from the species' `Competition Group` in
`config/competition.toml`. Neighbours participate in light competition during
simulation but are not exported as assets.

```bash
python src/growpy/cli/dataset_pipeline.py --generate-csvs                  # full twig density
python src/growpy/cli/dataset_pipeline.py --generate-csvs --density reduced # 0.5x twigs
```

If you want to drive a forest from a hand-written CSV instead, the minimal columns
are `x,y,species,height` (optional `z, fid, dbh, twig_density, individual_type`) —
see [forest-generation.md](forest-generation.md).

---

## 5. Run the pipeline

The four steps (run as isolated subprocesses so Blender's `bpy` never loads into
the orchestrator):

1. **prepare-assets** — copy Grove presets/textures/twigs into `data/assets/`
2. **convert-twigs** — `.blend` -> `.usda` with alpha-trim densification
3. **create-models** — simulate, (optionally) calibrate against yield tables, fit height-to-age
4. **generate-forest** — per species, simulate with light competition and export Nanite assemblies

`--steps` selects which run (default `4`; `all` = `1,2,3,4`). Steps 1-3 read
`all_species.csv`; step 4 reads each `{species}_merged.csv`.

```bash
# full dataset from scratch (recommended single command)
python src/growpy/cli/dataset_pipeline.py --generate-csvs
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables

# clean re-run (wipe step outputs + yield-table store first)
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables --clean
```

Common selections and options:

| Command / flag | Effect |
|---|---|
| `--pilot` | only European Beech + Norway Spruce |
| `--all` | every species with a generated merged CSV |
| `--species "European Beech"` | one species |
| `--list` | print selected species and exit |
| `--steps 3,4` | run only those steps |
| `--ingest-yield-tables` | populate the yield-table store before step-3 calibration |
| `--clean` / `--clean-store` | wipe step outputs / the yield-table store before running |
| `--workers 4` | parallel species for step 4 (default `min(4, cpu_count)`) |
| `--max-height 15` | cap height for faster step-3/step-4 runs |
| `--dry-run` | print the subprocess commands without executing |

A full 11-species run takes roughly half an hour on a workstation and needs a
licensed Grove install plus `bpy`.

---

## 6. Outputs

```text
data/output/forest/<species>/tree_####/
  <species>_assembly.usda          # Nanite Assembly entry point (drag into UE)
  <species>_####_skeletal.usda     # SkeletalMesh for wind
  <species>_####_DynamicWind.json  # wind data for the UE DynamicWind plugin
  <species>_####.json              # PVE preset (unless [export] skip_pve_json)
  <species>_####_preview.png
  twigs/                           # reusable foliage payloads
```

With multi-stage export, filenames include cycle/height/DBH:
`<species>_c{cycle}_h{height}_d{dbh}_assembly.usda`.

Next: [unreal-import.md](unreal-import.md) for the UE side,
[pve-preset-workflow.md](pve-preset-workflow.md) for PVE scatter, and
[helios-export.md](helios-export.md) for the secondary LiDAR/OBJ path.
