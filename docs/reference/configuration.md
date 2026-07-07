# Configuration Reference

GrowPy is configured by the TOML files in `config/` plus the species catalogue
`config/tree_asset_lookup.csv`. `growpy-init-config` seeds both from the packaged
templates in `src/growpy/config/templates/`.

## How config is resolved

- Every `config/*.toml` is read and **deep-merged in sorted filename order** into a
  single settings object — there is no single `growpy.toml`.
- Precedence (lowest to highest): **dataclass defaults -> `config/*.toml` -> CLI flags**.
- Point the pipeline at a different directory with `GROWPY_CONFIG=/path/to/config`.

## TOML files

| File | Sections | Controls |
|---|---|---|
| `general.toml` | `[general]` | random seed, default input CSV, output dir, verbosity, profiling |
| `assets.toml` | `[assets]` | Grove install path (`grove_dir`), texture resizing |
| `twigs.toml` | `[twigs]` | twig densification, alpha trim, smoothing, custom-twig dir |
| `growth_models.toml` | `[growth_models]`, `[calibration]`, `[yield_sources]` | simulation cycles/seeds/timeouts, yield-table calibration, ingested store |
| `forest.toml` | `[forest]`, `[export]` | quality preset, growth-cycle limit, `height_interval`, `max_height`, USD format, skeletal/static, twig density, density variants, assembly caps |
| `quality.toml` | `[quality.*]`, `[density_variant.*]` | named mesh/skeleton presets; named density variants |
| `unreal.toml` | `[unreal]` | import-script generation, Unreal content path |
| `helios.toml` | `[helios]`, `[helios.simplification]` | OBJ/MTL + Helios scene export (secondary feature) |
| `surround.toml` | `[surround]` | Grove Surround light-competition shell (density, distance, height, grow) for the `surround` dataset individual |

### Keys you will reach for most

| Key | File | Meaning |
|---|---|---|
| `quality` | `forest.toml [forest]` | preset name resolved against `quality.toml` |
| `height_interval` | `forest.toml [forest]` | growth-stage spacing in metres (`0` = single export) |
| `max_height` | `forest.toml [forest]` | global height cap in metres (`0` = no cap) |
| `growth_cycle_limit` | `forest.toml [forest]` | max simulation cycles per tree |
| `usd_format` | `forest.toml [export]` | `usda` (text) or `usdc` (binary) |
| `skip_pve_json` | `forest.toml [export]` | skip PVE preset JSON |
| `import_to_unreal` | `unreal.toml [unreal]` | emit UE import scripts after step 4 |
| `export_obj` | `helios.toml [helios]` | emit Helios++ OBJ alongside USD |
| `csv_file` | `general.toml [general]` | default input CSV when `--csv` is omitted |

## Species catalogue — `tree_asset_lookup.csv`

One row per Grove species. The columns the pipeline reads:

| Column | Used for |
|---|---|
| `Common Name` | species lookup key matched against input CSVs |
| `Standardized Name` | snake_case name used for files/directories |
| `Scientific Name`, `GBIF Key`, `Aliases` | name resolution / metadata |
| `Preset` | Grove `.seed.json` to load |
| `Twig` | twig set (custom twig overrides the Grove twig of the same name) |
| `Growth Model` | growth-model key |
| `Branch Color`, `Leaf Color`, `Bark Texture` | appearance |
| `Yield Search` | search term used when ingesting yield tables |
| `Max Height` | mature height in metres (required for dataset membership) |
| `Competition Spacing` | informational spacing hint |
| `Competition Group` | silvicultural group label; must be set for dataset membership |
| `Dataset` | **single control for dataset membership** — mark `yes` to include the species in `dataset_pipeline.py` runs |

To change which species the dataset produces, edit the `Dataset` column only (and
ensure `Max Height` + `Competition Group` are set). See
[../guides/dataset-workflow.md](../guides/dataset-workflow.md).

Custom twigs live under `data/input/custom_twigs/` (configurable via
`twigs.custom_twigs_dir`); they override Grove twigs of the same name. See
[cli-reference.md](cli-reference.md) for the resolution order.
