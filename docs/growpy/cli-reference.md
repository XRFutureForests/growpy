# GrowPy CLI Reference

Four-step pipeline for generating tree assets from The Grove 2.3 for Unreal Engine,
plus dataset production tools for batch generation of multi-species assets.

All scripts read defaults from `src/growpy/growpy.toml`. CLI arguments override TOML values.
Run all scripts without arguments to use TOML defaults:

```bash
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py
python src/growpy/cli/create_growth_models.py
python src/growpy/cli/generate_forest.py
```

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

**Output per species:**

| File | Description |
|---|---|
| `data/assets/growth_models/{species}_growth_model.json` | Growth curve data |
| `data/assets/growth_models/{species}_height_curve.png` | Visualization plot |

**CLI-only flags:**

| Flag | Description |
|---|---|
| `--species TEXT` | Analyze a single species instead of all from CSV |

**TOML-configurable:** `csv_file`, `cycles`, `seeds`, `height_threshold`,
`max_cycles_without_growth`, `timeout` (see `[growth_models]`).

## Step 4: generate_forest.py

Generate multi-species forests from CSV with USD export and optional Unreal import scripts.
Creates skeletal (animation-ready) Nanite assemblies by default.

### Export Modes

**Height-based (default):** Trees grown to target heights specified in CSV.
CSV columns: `x, y, species, height` (optional: `z`, `fid`).

**Multi-stage:** Multiple tree models at different growth cycles from single positions.
Enabled with `--cycle-interval`. Each tree gets snapshots at `[interval, 2*interval, ...]`
up to its height-derived cycle count. Shorter trees get fewer snapshots.

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
| `--cycle-interval INT` | Export every N cycles (enables multi-stage mode) |
| `--max-cycles INT` | Cap maximum cycles (default: height-derived) |
| `--export-trees IDs` | Comma-separated fids to export (others still compete for light) |
| `--preset-override P=V` | Override preset parameter (repeatable) |

**TOML-configurable:** `csv_file`, `output_dir`, `quality`, `growth_cycle_limit`,
`smooth_iterations`, `include_grove_attributes`, `longevity_mode`, skeleton parameters,
export flags, unreal settings (see `[forest]`, `[export]`, `[unreal]`).

## Helios++ OBJ Export

OBJ/MTL export for Helios++ LiDAR simulation runs automatically in Step 4
when `helios.export_obj = true` in growpy.toml. Configuration is in the `[helios]`
section of growpy.toml.

**TOML-configurable:** `export_obj`, `stem_decimate_ratio`, `twig_decimate_ratio`,
`helios_scene`, `combined_obj` (see `[helios]`).

## Dataset Production

Two additional scripts automate batch production of tree assets across all 16 dataset
species. See [dataset-specification.md](../dataset-specification.md) for the full
specification and [dataset-overview.md](../dataset-overview.md) for production status.

### generate_dataset_csvs.py

Generate input CSV templates for dataset production from `tree_asset_lookup.csv` metadata.

Creates per-species open-grown and competition CSVs, plus an all-species CSV for
pipeline steps 1-3. Competition CSVs use a hexagonal 6-neighbor arrangement at the
species-specific competition spacing.

```bash
# Generate all CSV templates with full twig density
python src/growpy/cli/generate_dataset_csvs.py

# Generate with reduced density variant
python src/growpy/cli/generate_dataset_csvs.py --density reduced

# Custom output directory
python src/growpy/cli/generate_dataset_csvs.py --output-dir data/input/my_dataset
```

**Output:**

| File | Contents |
|---|---|
| `data/input/dataset/{species}_open.csv` | Single tree at origin (open-grown individual) |
| `data/input/dataset/{species}_competition.csv` | Center tree + 6 hexagonal neighbors |
| `data/input/dataset/all_species.csv` | One row per species (for steps 1-3) |

**CLI flags:**

| Flag | Description |
|---|---|
| `--output-dir PATH` | Output directory (default: `data/input/dataset`) |
| `--density {full,reduced,bare}` | Twig density variant (default: full) |

### produce_dataset.py

Convenience wrapper that runs `generate_forest.py` for each species' open-grown and
competition CSVs. Expects CSV files in `data/input/dataset/` (generated by
`generate_dataset_csvs.py`).

```bash
# Produce a single species
python src/growpy/cli/produce_dataset.py --species "European Beech"

# Pilot run (European Beech + Norway Spruce only)
python src/growpy/cli/produce_dataset.py --pilot

# All 16 dataset species
python src/growpy/cli/produce_dataset.py --all

# Preview commands without executing
python src/growpy/cli/produce_dataset.py --all --dry-run

# List available species
python src/growpy/cli/produce_dataset.py --list
```

**CLI flags:**

| Flag | Description |
|---|---|
| `--species TEXT` | Species common name (e.g. "European Beech") |
| `--pilot` | Run pilot species only (European Beech, Norway Spruce) |
| `--all` | Run all 16 dataset species |
| `--list` | List available species and exit |
| `--dry-run` | Print commands without executing |

## Diagnostic Tools

Standalone tools for debugging and analysis. Available as console commands after
`pip install -e .` or run directly from `src/growpy/tools/`.

| Command | Script | Purpose |
|---------|--------|---------|
| `growpy-analyze-usda` | `tools/analyze_usda.py` | Analyze USDA assembly files (mesh stats, bone counts, twig instances) |
| `growpy-diagnose-growth` | `tools/diagnose_growth.py` | Diagnose growth simulation issues (height/DBH curves, calibration data) |
| `growpy-visualize-tree` | `tools/visualize_tree.py` | Render side-view PNG of tree mesh geometry |
