# GrowPy Configuration

All user-editable configuration for this project lives in this directory. The
`src/growpy/config/` package contains only loader logic; it does not contain any
default TOMLs or the species lookup CSV.

## Resolution order

For every setting, the final value is resolved as:

```text
dataclass defaults (src/growpy/config/core.py)
  -> config/*.toml (this directory, all files deep-merged in sorted order)
  -> CLI arguments (--flag)
```

A fresh checkout with no `config/` directory still runs — the dataclass defaults
take over. To regenerate a starter set of TOMLs, run:

```bash
growpy-init-config
```

## File layout

Files are grouped by pipeline step (or by cross-cutting concern). Every `*.toml`
in this directory is loaded automatically; filenames are for humans.

| File                  | Purpose                                            | Pipeline step |
| --------------------- | -------------------------------------------------- | ------------- |
| `general.toml`        | `[general]` — shared settings (seed, paths, I/O)   | all           |
| `assets.toml`         | `[assets]` — Grove copy + texture resize           | 1             |
| `twigs.toml`          | `[twigs]` — .blend → USD conversion + densify      | 2             |
| `growth_models.toml`  | `[growth_models, calibration, yield_sources, ...]` | 3             |
| `forest.toml`         | `[forest, export]`                                 | 4             |
| `quality.toml`        | `[quality.*, density_variant.*]`                   | cross-cutting |
| `competition.toml`    | `[competition.*]` — thinning schedules             | cross-cutting |
| `unreal.toml`         | `[unreal]` — UE import + Nanite                    | cross-cutting |
| `helios.toml`         | `[helios]` — LiDAR OBJ export                      | cross-cutting |
| `tree_asset_lookup.csv` | Species master table                             | cross-cutting |

## Custom config directory

Point `GROWPY_CONFIG` at a different directory (or a file inside one) to load a
separate set of TOMLs without touching this one:

```bash
GROWPY_CONFIG=/path/to/experiment/config growpy-generate-forest
```

## Species lookup CSV

`tree_asset_lookup.csv` is the master species table consumed by
`growpy.config.paths`. Columns:

- `Common Name` — human-readable species name used in input CSVs
- `Standardized Name` — lowercase snake_case used for asset directory/file lookup
- `Scientific Name` — binomial nomenclature
- `Preset` — Grove seed JSON filename
- `Twig` — twig asset identifier (CamelCase) or `—` if none
- `Growth Model` — growth model directory name (legacy family-based naming)
- `Branch Color`, `Leaf Color` — hex colors
- `Competition Group` — group key referenced in `competition.toml`
- `Aliases` — comma-separated synonyms

New species are picked up automatically — no package reinstall needed.
