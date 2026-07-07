# GrowPy CLI Reference

Four-step pipeline for generating tree assets from The Grove 2.3 for Unreal Engine,
plus dataset production tools for batch generation of multi-species assets.

All scripts read defaults from the `config/*.toml` files (created by `growpy-init-config`). CLI arguments override TOML values.
Run all scripts without arguments to use TOML defaults:

```bash
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py
python src/growpy/cli/create_growth_models.py
python src/growpy/cli/generate_forest.py
```

## Setup: growpy-init-config

(Optional) Scaffold a project-level configuration directory with starter TOML files
and species lookup CSV. Useful for customizing defaults without modifying the package.

```bash
growpy-init-config                      # Copy templates to ./config
growpy-init-config --target ./myconfig  # Copy to custom directory
growpy-init-config --force              # Overwrite existing files
```

**Output:** Copies all files from `growpy/config/templates/` (TOML files + `tree_asset_lookup.csv`)
to target directory. Existing files are skipped unless `--force` is passed.

All CLI scripts read the `config/*.toml` files, deep-merged in sorted order. Point them at
a different directory with the `GROWPY_CONFIG` environment variable. See
[configuration.md](configuration.md) for the full key reference.

## Step 1: prepare_assets.py

Copy species assets (presets, twigs, textures) from The Grove 2.3 installation.

CSV-driven: only copies assets for species listed in input CSV.
Supports forest placement CSV (`x, y, species, height`) or asset lookup CSV
(`Common Name, Preset, Twig, Bark Texture`).

**Output:**

| Directory | Contents |
|---|---|
| `data/assets/presets/` | Species `.seed.json` preset files |
| `data/assets/twigs/` | Twig `.blend` files (snake_case directories) |
| `data/assets/textures/` | Bark texture files |
| `data/assets/pve_configs/` | PVE placeholder configs |

**CLI-only flags:**

| Flag | Description |
|---|---|
| `--all` | Copy ALL 57 Grove assets (ignores CSV filter) |

**TOML-configurable:** `grove_dir`, `csv_file`, `resize_textures` (see `[assets]` and `[general]`).

### Custom Twigs

By default, `prepare_assets.py` copies twig `.blend` files from the vanilla Grove
installation (`src/the_grove_23/twigs/`). For custom or hand-curated twigs (e.g.,
Helios-classified variants with explicit fruit materials), place them in the custom
twigs directory configured by `twigs.custom_twigs_dir` (default: `data/input/custom_twigs/`).

**Setup:**

1. Place the twig directory (CamelCase name with `.blend` + `textures/`) in
   `data/input/custom_twigs/`:

   ```text
   data/input/custom_twigs/
     SelectedScotsPineTwig/
       SelectedScotsPineTwig.blend
       textures/
         ScotsPine.png
   ```

2. Update the `Twig` column in `src/growpy/config/tree_asset_lookup.csv` for the
   species that should use the custom twig:

   ```text
   Scots pine,...,SelectedScotsPineTwig,...
   ```

3. Run `prepare_assets.py` -- custom twigs are found before Grove twigs, copied to
   `data/assets/twigs/` as snake_case, and processed identically by `convert_twigs.py`.

**Resolution order:** custom twigs dir (CamelCase match) > Grove source (CamelCase) >
Grove reverse lookup (snake_case). Custom twigs override Grove twigs when names match.

**Included custom twigs** (from Tom's Helios branch): `SelectedEuropeanBeechTwig`,
`SelectedEuropeanOakTwigTom`, `SelectedPacificSilverFirTwigTom`,
`SelectedPaparBirchVarATwig`, `SelectedScotsPineTwig` (with fruit material),
`SelectedSycamoreMapleTwig`.

## Step 2: convert_twigs.py

Convert Grove twig `.blend` files to USD with skeletal and static mesh variants.
Pure Blender-to-USD conversion -- no Grove API required, only Blender Python API (bpy).

### Algorithm (Interleaved Densify+Trim)

1. Build vertex alpha map by sampling texture at UV coordinates
2. Identify working faces:
   - Transition faces: have BOTH opaque and transparent vertices
   - Transparent faces: ALL vertices transparent with long edges
   - Boundary faces: have at least one mesh boundary edge
3. Delete small fully-transparent faces (all edges <= target)
4. Subdivide long edges in working faces (`edge_split` affects neighbors)
5. Repeat steps 1-4 until no more changes

Key advantages:

- Transition faces (the actual silhouette) get densified first
- Transparent faces subdivided only to make them small enough to delete
- `edge_split` naturally propagates to neighboring faces sharing edges
- Auto-detects inverted alpha masks (black=opaque convention)

### Export Variants

Both variants are created by default for each twig:

| Variant | Filename | Description |
|---|---|---|
| Skeletal | `{species}_foliage_{type}_skeletal.usda` | Root joint skeleton for animation. Geometry only (no materials). Used in skeletal Nanite assemblies. |
| Static | `{species}_foliage_{type}_static.usda` | Full PBR materials with Grove textures. No skeleton. Used in static Nanite assemblies. |

**CLI-only flags:**

| Flag | Description |
|---|---|
| `path` (positional, optional) | Path to twig directory or `.blend` file (default: from TOML `twigs.path`) |
| `--no-densify` | Disable mesh densification |

**TOML-configurable:** `path`, `densify`, `alpha_trim`, `smooth_boundary`, `smooth_iterations`,
`smooth_factor`, `boundary_edge_mm` (see `[twigs]`).

## Step 3: create_growth_models.py

Generate height curves and age prediction models with intelligent early termination.
Features automatic plateau detection to stop simulation when trees stop growing.

When calibration is enabled in `growth_models.toml [calibration]`, automatically calibrates
against yield tables and re-simulates with calibration applied.

**Output per species:**

| File | Description |
|---|---|
| `data/assets/growth_models/{species}_growth_model.json` | Growth curve data |
| `data/assets/growth_models/{species}_height_curve.png` | Visualization plot |

**CLI flags:**

| Flag | Description |
|---|---|
| `--species TEXT` | Analyze a single species instead of all from CSV |
| `--ingest-yield-tables` | Populate yield table store from external providers before calibration |
| `--list-providers` | List available yield table providers and their status, then exit |
| `--clean-store` | Clear existing yield table store before ingesting |
| `--providers NAME [NAME ...]` | Run only specified providers (default: all available) |

**TOML-configurable:** `csv_file`, `cycles`, `seeds`, `height_threshold`,
`max_cycles_without_growth`, `timeout`, calibration settings (see `[growth_models]`, `[calibration]`, `[yield_sources]`).

## Step 4: generate_forest.py

Generate multi-species forests from CSV with USD export and optional Unreal import scripts.
Creates skeletal (animation-ready) Nanite assemblies by default.

### Export Modes

**Height-based (default):** Trees grown to target heights specified in CSV.
CSV columns: `x, y, species, height` (optional: `z`, `fid`).

**Multi-stage:** Multiple tree models at different heights from single positions.
Enabled with `--height-interval`. Each species gets snapshots at height milestones
(e.g., 5m, 10m, 15m...) using growth models to determine the corresponding cycles.

### Assembly Types

| Type | Flag | Description |
|---|---|---|
| Skeletal (default) | -- | Geometry + skeleton only. Supports animation. Smaller file size. |
| Static | `--include-static` | Full PBR materials. No animation. Better visual quality for static placement. |

### Skeleton Simplification

Independent of mesh quality. Critical for Unreal Engine's 32,767 bone limit.
Both `length` and `reduce` independently reduce bone count.

- **length** (0.0-5.0): Merge nodes into longer bones along branch length.
  `0.1` = one bone per node (most bones), `4.0` = very long bones (fewest).
- **reduce** (0.0-1.0): Skip thin side branches entirely. Most effective reducer.
  `0.1` = keep all, `0.4` = skip thin, `0.8` = only thick main branches.
- **bias** (0.0-1.0): `0.0` = more bones near trunk, `1.0` = more near tips.
- **connected** (true/false): Connected chains required for animation; floating bones = fewer bones.

Example: ultra mesh with simplified skeleton:

```bash
python src/growpy/cli/generate_forest.py --quality ultra --skeleton-reduce 0.5
```

### Preset Overrides (prevent tree death)

`--longevity-mode` applies pre-configured overrides (`drop_decay=0.1`, `drop_weak=0.1`, etc.)
to prevent trees from dying at high growth cycles.

`--preset-override PARAM=VALUE` overrides individual preset parameters.
Common: `drop_decay`, `drop_weak`, `drop_shaded`, `drop_obsolete` (0.0-1.0, lower = less dropping).

### Output Structure

**Height mode:**

```
data/output/forest/{species}/tree_####/{species}_assembly.usda
data/output/forest/{species}/tree_####/{species}_stems_skeletal.usda
```

**Multi-stage mode:**

```
data/output/forest/{species}/tree_####/{species}_c{cycle}_h{height}_d{dbh}_assembly.usda
```

Format: `{species}_c{cycle:03d}_h{meters}m{tenths}_d{dbh_cm}cm_assembly`

**CLI-only flags:**

| Flag | Description |
|---|---|
| `--height-interval FLOAT` | Export every N meters of height (enables multi-stage mode) |
| `--max-cycles INT` | Cap maximum cycles (default: height-derived) |
| `--export-trees IDs` | Comma-separated fids to export (others still compete for light) |
| `--preset-override P=V` | Override preset parameter (repeatable) |

**TOML-configurable:** `csv_file`, `output_dir`, `quality`, `growth_cycle_limit`,
`smooth_iterations`, `include_grove_attributes`, `longevity_mode`, skeleton parameters,
export flags, unreal settings (see `[forest]`, `[export]`, `[unreal]`).

## Helios++ OBJ Export

OBJ/MTL export for Helios++ LiDAR simulation runs automatically in Step 4
when `helios.export_obj = true` in `helios.toml`. Configuration is in the `[helios]`
section of `helios.toml`.

**TOML-configurable:** `export_obj`, `helios_scene`, `combined_obj` (see `[helios]`).

## Dataset Production

Two integrated features automate batch production of tree assets across all 11 dataset
species. See [../dataset/dataset-specification.md](../dataset/dataset-specification.md) for the full
specification and [../dataset/dataset-overview.md](../dataset/dataset-overview.md) for production status.

### dataset_pipeline.py

Full dataset production pipeline. Orchestrates all four steps across dataset species:
step 1 (prepare assets), step 2 (convert twigs), step 3 (create growth models),
step 4 (generate forest). Each step is invoked as a subprocess. Steps 1-3 use
`all_species.csv`; step 4 runs one subprocess per species using per-species merged CSVs.

**CSV Generation:**

Must be run once before step 4. Reads `tree_asset_lookup.csv` metadata and writes
per-species merged CSVs (open-grown + surround, one tree each) plus
`all_species.csv` (one row per species, used by steps 1-3).

```bash
# Generate all CSV templates with full twig density
python src/growpy/cli/dataset_pipeline.py --generate-csvs

# Generate with reduced density variant
python src/growpy/cli/dataset_pipeline.py --generate-csvs --density reduced

# Custom output directory
python src/growpy/cli/dataset_pipeline.py --generate-csvs --output-dir data/input/my_dataset
```

**Dataset CSV Output:**

| File | Contents |
|---|---|
| `data/input/dataset/{species}_merged.csv` | Open tree (fid=1) + surround tree (fid=2) |
| `data/input/dataset/all_species.csv` | One row per species (for steps 1-3) |

**Forest Production:**

Runs the selected steps for the specified species. Default is step 4 only.
Use `--steps all` to run the full pipeline in a single command.

```bash
# Step 4 only for a single species (default)
python src/growpy/cli/dataset_pipeline.py --species "European Beech"

# Pilot run (European Beech + Norway Spruce)
python src/growpy/cli/dataset_pipeline.py --pilot

# All species, step 4 only
python src/growpy/cli/dataset_pipeline.py --all

# Full pipeline (steps 1-4) for all species
python src/growpy/cli/dataset_pipeline.py --all --steps all

# Full pipeline with yield table ingestion
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables

# Full pipeline with clean yield table store (wipe and re-ingest)
python src/growpy/cli/dataset_pipeline.py --all --steps all --ingest-yield-tables --clean-store

# Steps 3 and 4 only for pilot species
python src/growpy/cli/dataset_pipeline.py --pilot --steps 3,4

# Preview all commands without executing
python src/growpy/cli/dataset_pipeline.py --all --steps all --dry-run

# List available species
python src/growpy/cli/dataset_pipeline.py --list
```

**CLI flags:**

| Flag | Description |
|---|---|
| `--generate-csvs` | Generate dataset CSV files from lookup table, then exit |
| `--output-dir PATH` | Output directory for CSVs (default: `data/input/dataset`) |
| `--density {full,reduced,bare}` | Twig density variant for CSV generation (default: full) |
| `--steps STEPS` | Steps to run: comma-separated (1,2,3,4) or `all` (default: 4) |
| `--csv PATH` | Override all_species.csv path for steps 1-3 |
| `--species TEXT` | Single species by common name (e.g. "European Beech") |
| `--pilot` | Pilot species only (European Beech, Norway Spruce) |
| `--all` | All species with merged CSV files in dataset directory |
| `--list` | List available species and exit |
| `--dry-run` | Print commands without executing |
| `--max-height FLOAT` | Cap tree heights for step 4 (for faster testing) |
| `--workers INT` | Parallel workers for step 4 (default: min(4, cpu_count)) |
| `--ingest-yield-tables` | Ingest yield tables from external providers before step 3 calibration |
| `--clean-store` | Clear existing yield table store before re-ingestion (requires `--ingest-yield-tables`) |

## Diagnostic Tools

Standalone tools for debugging and analysis. Available as console commands after
`pip install -e .` or run directly from `src/growpy/tools/`.

| Command | Script | Purpose |
|---------|--------|---------|
| `growpy-analyze-usda` | `tools/analyze_usda.py` | Analyze USDA assembly files (mesh stats, bone counts, twig instances) |
| `growpy-diagnose-growth` | `tools/diagnose_growth.py` | Diagnose growth simulation issues (height/DBH curves, calibration data) |
| `growpy-visualize-tree` | `tools/visualize_tree.py` | Render side-view PNG of tree mesh geometry |
