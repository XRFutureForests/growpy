# GrowPy Quickstart

The shortest path to a working forest USD. For the full dataset workflow see
[guides/dataset-workflow.md](guides/dataset-workflow.md); for a hand-driven single
forest see [guides/forest-generation.md](guides/forest-generation.md); for config
keys see [reference/configuration.md](reference/configuration.md) and for CLI flags
[reference/cli-reference.md](reference/cli-reference.md).

## 1. Prerequisites

- Windows, Linux, or macOS
- Miniconda/Mamba
- A licensed copy of [The Grove 2.3](https://www.thegrove3d.com/)
- Optional: Unreal Engine 5.7+ (Nanite Assembly import), Helios++ (LiDAR simulation)

## 2. Install

```bash
git clone <repo-url> growpy
cd growpy
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

This copies the packaged templates into `./config/`: **9 TOML files**
(`general`, `assets`, `twigs`, `growth_models`, `forest`, `quality`, `unreal`,
`helios`, `surround`) plus `tree_asset_lookup.csv`. There is no single
`growpy.toml` — all `config/*.toml` files are deep-merged in sorted order and CLI
flags override them. See [reference/configuration.md](reference/configuration.md).

## 4. Smallest end-to-end run

Fastest way to exercise the whole pipeline — the dataset orchestrator on the pilot
set (European beech + Norway spruce):

```bash
python src/growpy/cli/dataset_pipeline.py --generate-csvs
python src/growpy/cli/dataset_pipeline.py --pilot --steps all --ingest-yield-tables
```

This will:

1. Build input CSVs under `data/input/dataset/`.
2. Step 1 (`prepare_assets`) — copy Grove presets/textures/twigs into `data/assets/`.
3. Step 2 (`convert_twigs`) — `.blend` -> `.usda` with alpha-trim densification.
4. Step 3 (`create_growth_models`) — ingest yield tables, simulate, calibrate, fit height-to-age.
5. Step 4 (`generate_forest`) — simulate each species with light competition and export Nanite assemblies to `data/output/forest/`.

Expect ~30 min on a decent workstation. Parallelise with `--workers 4`, or cap
height for a quick check with `--max-height 15`.

## 5. Manual single-species run

To drive the pipeline by hand with a minimal CSV:

```bash
python src/growpy/cli/prepare_assets.py       --csv data/input/test.csv
python src/growpy/cli/convert_twigs.py        --csv data/input/test.csv
python src/growpy/cli/create_growth_models.py --csv data/input/test.csv --ingest-yield-tables
python src/growpy/cli/generate_forest.py      --csv data/input/test.csv
```

A minimal CSV is just:

```csv
x,y,species,height
0,0,Norway spruce,5
```

Optional columns: `z`, `fid`, `dbh`, `twig_density`, `individual_type`. Accepted
species names live in `config/tree_asset_lookup.csv`; see
[reference/naming-conventions.md](reference/naming-conventions.md). Full walkthrough:
[guides/forest-generation.md](guides/forest-generation.md).

## 6. Outputs

After Step 4, open `data/output/forest/`:

```text
data/output/forest/
└── norway_spruce/
    └── tree_0001/
        ├── norway_spruce_assembly.usda      # Nanite Assembly entry point (drag into UE)
        ├── norway_spruce_0001_skeletal.usda  # SkeletalMesh for wind
        ├── norway_spruce_0001_DynamicWind.json
        ├── norway_spruce_0001_preview.png
        └── twigs/                            # reusable foliage payloads
```

## 7. Where to go next

| Goal | Read |
|------|------|
| Produce the full multi-species dataset | [guides/dataset-workflow.md](guides/dataset-workflow.md) |
| Build one forest from your own CSV | [guides/forest-generation.md](guides/forest-generation.md) |
| Change config (quality, intervals, species) | [reference/configuration.md](reference/configuration.md) |
| Import into Unreal (Nanite Assembly, DynamicWind, PVE) | [guides/unreal-import.md](guides/unreal-import.md) |
| Bake OBJ/MTL + Helios scene for LiDAR | [guides/helios-export.md](guides/helios-export.md) |
| Look up a CLI flag | [reference/cli-reference.md](reference/cli-reference.md) |
| Understand what each step does | [architecture/processing-logic.md](architecture/processing-logic.md) |

## 8. Troubleshooting

- `ModuleNotFoundError: the_grove_23_core` — Grove symlink missing or wrong path; check `src/the_grove_23/modules/`.
- `ModuleNotFoundError: bpy` — `pip install bpy` inside the `growpy` env.
- Step 4 OOMs on large forests — lower the quality preset or restrict with `--export-trees`.
- UE import fails with "bone count exceeds 32767" — run Step 4 with `--skeleton-reduce 0.5 --skeleton-length 2.5`.
