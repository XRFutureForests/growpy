# GrowPy Quickstart

This guide gets a working GrowPy install producing a forest USD in the shortest path possible. For architectural depth see [architecture/](architecture/README.md); for CLI flags see [reference/cli-reference.md](reference/cli-reference.md).

## 1. Prerequisites

- Windows, Linux, or macOS
- Miniconda/Mamba
- A licensed copy of [The Grove 2.3](https://www.thegrove3d.com/)
- Optional: Unreal Engine 5.7+ (Nanite Assembly import), Helios++ (LiDAR simulation)

## 2. Install

```bash
# Clone and enter the repo
git clone <repo-url> growpy
cd growpy

# Create the conda environment and install the package
conda env create -f environment.yml
conda activate growpy
pip install -e .
```

Symlink or copy your Grove installation into `src/the_grove_23/`:

```bash
# Windows (admin shell)
mklink /D src\the_grove_23 C:\path\to\the_grove_23

# Linux / macOS
ln -s /path/to/the_grove_23 src/the_grove_23
```

Verify:

```bash
python -c "import the_grove_23_core as gc; print('Grove API ready')"
```

## 3. Initialize config

```bash
growpy-init-config
```

This copies the packaged templates (`growpy.toml`, `tree_asset_lookup.csv`, and sample CSVs) into `./config/`. Edit `config/growpy.toml` to change output paths, quality preset, export format, etc. See [reference/cli-reference.md](reference/cli-reference.md) for flag/TOML overrides.

## 4. Smallest end-to-end run

The fastest way to exercise the whole pipeline is the dataset orchestrator on a pilot set (European beech + Norway spruce):

```bash
python src/growpy/cli/dataset_pipeline.py --generate-csvs
python src/growpy/cli/dataset_pipeline.py --pilot --steps all --ingest-yield-tables
```

This will:

1. Build input CSVs under `data/input/dataset/`.
2. Run Step 1 (`prepare_assets`) — copy Grove presets/textures/twigs into `data/assets/`.
3. Run Step 2 (`convert_twigs`) — `.blend` -> `.usda` with alpha-trim densification.
4. Run Step 3 (`create_growth_models`) — ingest yield tables, simulate species, calibrate, fit height-to-age model.
5. Run Step 4 (`generate_forest`) — for each species, simulate a forest with light competition and export Nanite assemblies to `data/output/forest/`.

Expect ~30 min on a decent workstation. Parallelise species with `--workers 4`.

## 5. Manual single-species run

If you want to drive the pipeline by hand with a minimal CSV:

```bash
# Use the shipped smoke-test CSV (1 Norway spruce @ 5m)
python src/growpy/cli/prepare_assets.py     --csv data/input/test_single.csv
python src/growpy/cli/convert_twigs.py      --csv data/input/test_single.csv
python src/growpy/cli/create_growth_models.py --csv data/input/test_single.csv --ingest-yield-tables
python src/growpy/cli/generate_forest.py    --csv data/input/test_single.csv
```

A minimal CSV is just:

```csv
x,y,species,height
0,0,Norway spruce,5
```

Optional columns: `z`, `fid`, `dbh`, `twig_density`, `individual_type`. See [reference/naming-conventions.md](reference/naming-conventions.md) for accepted species names.

## 6. Outputs

After Step 4, open `data/output/forest/`:

```text
data/output/forest/
└── norway_spruce/
    └── tree_0001/
        ├── norway_spruce_assembly.usda
        ├── norway_spruce_0001_skeletal.usda
        ├── norway_spruce_0001_DynamicWind.json
        ├── norway_spruce_0001_preview.png
        └── twigs/
```

- `*_assembly.usda` — Nanite Assembly entry-point (drag into UE content browser).
- `*_skeletal.usda` — SkeletalMesh for wind animation.
- `*_DynamicWind.json` — wind data for UE DynamicWind plugin.
- `*_preview.png` — 2D preview.
- `twigs/*.usda` — reusable foliage payloads.

## 7. Where to go next

| Goal | Read |
|------|------|
| Import into Unreal (Nanite Assembly, DynamicWind, PVE) | [guides/unreal-import.md](guides/unreal-import.md) |
| Bake OBJ/MTL + Helios scene for LiDAR simulation | [guides/helios-export.md](guides/helios-export.md) |
| Set up a PVE-driven scatter in UE | [guides/pve-preset-workflow.md](guides/pve-preset-workflow.md) |
| Produce the full 10-species dataset | [dataset/dataset-specification.md](dataset/dataset-specification.md) |
| Understand what each step actually does | [architecture/processing-logic.md](architecture/processing-logic.md) |
| Look up a CLI flag or TOML key | [reference/cli-reference.md](reference/cli-reference.md) |
| Tune yield-table calibration | [reference/yield-table-calibration.md](reference/yield-table-calibration.md) |

## 8. Troubleshooting

- `ModuleNotFoundError: the_grove_23_core` — Grove symlink missing or wrong path; check `src/the_grove_23/modules/`.
- `ModuleNotFoundError: bpy` — `pip install bpy` inside the `growpy` env.
- Step 4 OOMs on large forests — drop `quality = "debug"` or restrict with `--export-trees`.
- UE import fails with "bone count exceeds 32767" — run Step 4 with `--skeleton-reduce 0.5 --skeleton-length 2.5`.
