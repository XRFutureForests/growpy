# Runbook — growpy

Install it, run the four pipeline steps, produce the dataset, get the result into Unreal, and
fix it when it breaks. For what growpy is and why it is built this way, see
[README.md](README.md).

---

## 1. Install

```bash
conda env create -f environment.yml
conda activate growpy
pip install -e .
```

No separate Blender installation — `bpy` comes through conda, with USD (`pxr`) included.

> **Always work through the conda environment.** R and Java live *inside* it. Calling
> `python.exe` directly hides them, and tools then report "not installed" for things that are
> installed. Use `conda activate growpy`, or `conda run -n growpy …` from a script.

### Starter configuration (optional)

```bash
growpy-init-config                       # copies templates to ./config
growpy-init-config --target ./my_config
```

These override the built-in defaults. All `config/*.toml` are deep-merged in sorted order,
then CLI arguments override them.

### Add The Grove 2.3

Commercial software ([thegrove3d.com](https://www.thegrove3d.com)), not in the repository.

```bash
cp -r /path/to/the_grove_23 src/the_grove_23        # Linux/Mac
mklink /D src\the_grove_23 C:\path\to\the_grove_23  # Windows
```

Expected inside `src/the_grove_23/`: `addons/`, `documentation/`, `modules/`, `presets/`,
`textures/`, `twigs/`.

### Verify

```bash
python -c "import the_grove_23_core as gc; print('Grove API ready')"
```

---

## 2. The four steps

Each reads its defaults from `config/*.toml` and runs without arguments.

```
prepare_assets → convert_twigs → create_growth_models → generate_forest
```

### Step 1 — prepare assets

Copies and standardises presets, textures and twigs out of Grove into `data/assets/`.
CSV-driven: only the species listed are processed.

```bash
python src/growpy/cli/prepare_assets.py                # species from the default CSV
python src/growpy/cli/prepare_assets.py --csv my.csv
python src/growpy/cli/prepare_assets.py --all          # all 60 Grove species
```

Produces `data/assets/{presets,textures,twigs}/`.

### Step 2 — convert twigs

`.blend` → USD, with optional densification for Nanite silhouettes (alpha-based trimming,
boundary smoothing, interior decimation). Per-twig parameters live under `[twigs]`.

```bash
python src/growpy/cli/convert_twigs.py
python src/growpy/cli/convert_twigs.py --no-densify
python src/growpy/cli/convert_twigs.py --alpha-trim 0.5
```

Produces two USD variants per twig: `*_skeletal.usda` (skeleton, no materials) and
`*_static.usda` (materials, no skeleton).

> Compound foliage prototypes bake **here**, in step 2 — not in step 4 — and output to
> `data/assets/compound_parts/`, never inside `twigs/` (an `rglob` basename collision).

### Step 3 — create growth models

Simulates growth curves and fits height-to-age models. With `[calibration] enabled = true`,
aligns to yield tables and re-simulates with the calibration applied.

```bash
python src/growpy/cli/create_growth_models.py
python src/growpy/cli/create_growth_models.py --species "European beech"
python src/growpy/cli/create_growth_models.py --seeds 3 --cycles 35
python src/growpy/cli/create_growth_models.py --ingest-yield-tables
python src/growpy/cli/create_growth_models.py --ingest-yield-tables --clean-store
```

Produces `data/assets/growth_models/` (JSON), calibration data written into `.seed.json`,
and comparison plots in `data/output/growth_comparison/`.

### Step 4 — generate forest

Multi-species simulation from a CSV, exporting USD Nanite assemblies.

```bash
python src/growpy/cli/generate_forest.py
python src/growpy/cli/generate_forest.py --quality high
python src/growpy/cli/generate_forest.py --height-interval 5
python src/growpy/cli/generate_forest.py --export-obj --helios-scene
python src/growpy/cli/generate_forest.py --skeleton-reduce 0.5
python src/growpy/cli/generate_forest.py --export-trees 1,2
python src/growpy/cli/generate_forest.py --preset-override drop_decay=0.1
```

**Input CSV:** `x`, `y`, `species`, `height` (optional `z`, `fid`, `dbh`, `twig_density`,
`individual_type`).

Produces `data/output/forest/` — per-species directories with USD assemblies, skeletal
meshes, twig USD, wind data, preview images, PVE presets, and optional Unreal import scripts
or Helios OBJ/scene files.

### Quality presets

| Preset | Vertices | Skeleton | Use |
|--------|----------|----------|-----|
| `high` | 16 | length 0.75, reduce 0.333 | USD Nanite export (default) |
| `helios` | 9 | length 2.0, reduce 0.8 | OBJ export for LiDAR simulation |
| `debug` | 8 | length 2.0, reduce 0.5 | Quick iteration |

`--skeleton-length`, `--skeleton-reduce`, `--skeleton-bias`, `--skeleton-connected` override
the preset independently.

---

## 3. Produce the dataset

Species selection is config-driven, read from `tree_asset_lookup.csv`'s `Dataset` column. No
preparation step is needed.

```bash
python src/growpy/cli/dataset_pipeline.py --list                    # what's available
python src/growpy/cli/dataset_pipeline.py --all --dry-run           # preview commands
python src/growpy/cli/dataset_pipeline.py --pilot                   # beech + spruce
python src/growpy/cli/dataset_pipeline.py --all                     # all 11 species
python src/growpy/cli/dataset_pipeline.py --all --workers 4         # parallel by species
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables --clean
```

`--generate-csvs` dumps the selected rows to `data/input/dataset/` for manual review only;
nothing reads them back.

### Typical dataset configuration

```toml
[forest]
quality = "high"
height_interval = 5
growth_cycle_limit = 125

[export]
density_variants = ["full", "reduced", "bare"]
skeletal = true
skip_pve_json = true
skip_validation = true
```

### Full run from scratch

```bash
conda activate growpy
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables
```

`data/assets/` and `data/output/` are regenerable — clearing them and re-running is the
normal recovery. `data/input/` is tracked and is not.

---

## 4. Helios++ export

```bash
python src/growpy/cli/generate_forest.py --export-obj
python src/growpy/cli/generate_forest.py --export-obj --helios-scene
python src/growpy/cli/generate_forest.py --export-obj --individual-obj
python src/growpy/cli/generate_forest.py --export-obj --obj-up-axis z
```

Converts USD assemblies to Wavefront OBJ with baked twig instances and material
classification (`bark`, `twig_wood`, `twig_leaf`). Material-aware simplification preserves
leaf area for LAI accuracy:

```toml
[helios]
export_obj = true
helios_scene = true
obj_up_axis = "z"

[helios.simplification]
enabled = true
bark = 0.2
leaf = 0.5
```

Details: [docs/guides/helios-export.md](docs/guides/helios-export.md).

---

## 5. Import into Unreal

1. Copy the output folder into the Content Browser.
2. USD auto-imports as Nanite Assemblies (UE 5.7+).
3. Trees and twigs are separate assets, assembled via PointInstancer.

**Required plugins:** USD Importer · Nanite (experimental) · Nanite Foliage (experimental) ·
Dynamic Wind (experimental) · Python Editor Script Plugin (for the auto-import scripts).

**Project settings:** enable "Use Nanite" in the USD Importer; enable Remote Execution to run
Python from an editor.

**Wind** is embedded in the USD skeleton. Each tree also exports `*_DynamicWind.json` for
older workflows — import it via the right-click scripted asset action on the SkeletalMesh.

PVE integration: [docs/guides/pve-preset-workflow.md](docs/guides/pve-preset-workflow.md).
Import settings: [docs/reference/nanite-import-settings.md](docs/reference/nanite-import-settings.md).

---

## 6. Testing

```bash
conda activate growpy
python -m pytest src/growpy/tests/ -v
python -m pytest src/growpy/tests/test_skeleton.py -v
```

Coverage details: [docs/reference/testing.md](docs/reference/testing.md).

---

## 7. Troubleshooting

**`ModuleNotFoundError: the_grove_23_core`**
`PYTHONPATH` must include `./src` and `./src/the_grove_23/modules`. `pip install -e .` handles
this; otherwise set it manually:

```bash
export PYTHONPATH="./src:./src/the_grove_23/modules"     # Linux/Mac
$env:PYTHONPATH=".\src;.\src\the_grove_23\modules"       # PowerShell
```

**`bpy` not found**
`pip install bpy`, inside the activated environment.

**A tool reports R or Java "not installed"**
You called `python.exe` directly instead of going through the environment. R and Java live
inside the conda env. Use `conda activate growpy` or `conda run -n growpy …`.

**Bone count exceeds Unreal's limit**
Unreal caps at 32,767 bones. `--skeleton-reduce` is the effective lever:

```bash
python src/growpy/cli/generate_forest.py --skeleton-reduce 0.5 --skeleton-length 2.5
```

**Generation is far slower than expected**
Grove's `.faces` and `.points` properties rebuild the entire list on every access. Hoisting
two in-loop reads once took dataset production from 44 min / 17 assemblies to 10 min / 99.
If you have added a loop over Grove geometry, hoist the property read out of it.

**An assembly imports as empty, with no error**
Look for a dangling `bindJoint` token — a single one silently kills the whole assembly.

**PVE materials render as shifting magenta/violet/neon**
Either a clone got re-parented to the `/Game/Templates` copy of `MA_Foliage_Trees`, or the
textures are non-virtual. Grep the log for `expects texture`.

**Crown looks too sparse or too dense**
That correction no longer lives here — it moved to the PVE side of the pipeline
(2026-09-10). Fix the asset; LAI is the acceptance metric, and `crown_ratio` alone cannot see
a hollow crown.
