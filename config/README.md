# GrowPy Configuration

This is the project's live `config/` directory. Every `*.toml` file here is
loaded and deep-merged (in sorted filename order), plus `tree_asset_lookup.csv`
for species metadata. Filenames are for humans only -- the loader doesn't care
which file a section lives in, it just merges all sections it finds.

## Resolution order

```
dataclass defaults (growpy.config.core.GrowPyConfig)
    -> config/*.toml   (this directory, deep-merged)
    -> CLI arguments   (--flag overrides, via GrowPyConfig.resolve())
```

Any key omitted from these TOML files silently falls back to the built-in
dataclass default in `growpy.config.core.GrowPyConfig`.

## Config directory resolution

At runtime, GrowPy finds this directory in the following order:

1. `GROWPY_CONFIG` environment variable (a directory, or any file inside one)
2. `./config/` in the current working directory
3. The packaged fallback shipped inside the `growpy` install
   (`growpy/config/templates/`) -- used only if neither of the above exists

To use a scratch/alternate config directory for one run:

```bash
GROWPY_CONFIG=/path/to/custom/config python -m growpy.cli.generate_forest
```

## Files

| File | Sections | Used by |
|------|----------|---------|
| `general.toml` | `[general]` | all steps |
| `assets.toml` | `[assets]` | step 1: `prepare_assets.py` |
| `twigs.toml` | `[twigs]` | step 2: `convert_twigs.py` |
| `growth_models.toml` | `[growth_models]`, `[calibration]`, `[yield_sources]` | step 3: `create_growth_models.py` |
| `forest.toml` | `[forest]`, `[export]` | step 4: `generate_forest.py` |
| `quality.toml` | `[quality.*]`, `[density_variant.*]` | referenced by `forest.toml`'s `quality` and `export.density_variants` |
| `surround.toml` | `[surround]` | step 3 & 4 (light-competition shell) |
| `unreal.toml` | `[unreal]` | Unreal Engine import script generation |
| `helios.toml` | `[helios]`, `[helios.simplification]` | Helios++ LiDAR export |
| `tree_asset_lookup.csv` | -- | species name/preset/twig/growth-model resolution |

Regenerate a fresh starter set (without touching files that already exist)
with `growpy-init-config`; pass `--force` to overwrite.

## Editing

Edit the files in this directory directly -- they take precedence over the
packaged defaults in `growpy/config/templates/`. Each file documents its own
keys inline; see `growpy.config.core.GrowPyConfig` for the authoritative list
of every recognized field and its default.
