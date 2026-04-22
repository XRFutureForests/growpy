# GrowPy — Work Plan

Linear: [XRFF team](https://linear.app/geosense-ufr/team/XRFF/all)

## Issue Sequence

```
XRFF-129 (calibrate 5 remaining species)
    └─► XRFF-127 (full 16-species batch production)
            └─► XRFF-59  (Paul: import assets into UE)
                XRFF-61  (Paul: showcase library in UE)
                XRFF-17  (Paul: production trees at inventory positions)

XRFF-36  (Grove generation driven by live Ecosense DB)  ← parallel track
```

---

## XRFF-129 — Calibrate remaining species (High, assignee: Max)

**Goal**: Yield table calibration + Grove branching presets for the 5 species missing from `data/assets/presets/`.

**Already done**: `european_beech`, `norway_spruce`, `european_oak`, `sycamore_maple`, `douglas_fir` have `.seed.json` presets.

**Missing presets** (from 10-species priority list):

| Species | Scientific | Type |
|---|---|---|
| Scots Pine | *Pinus sylvestris* | Conifer |
| Silver Birch | *Betula pendula* | Broadleaf |
| Common Ash | *Fraxinus excelsior* | Broadleaf |
| Silver Fir | *Abies alba* | Conifer |
| Small-leaved Linden | *Tilia cordata* | Broadleaf |
| Wild Cherry | *Prunus avium* | Broadleaf |

### Steps

**1. Ingest yield tables for all remaining species**

```bash
growpy-create-models --ingest-yield-tables --list-providers
growpy-dataset-pipeline --generate-csvs
```

Check `data/input/yield_tables/` and `data/input/yield_tables/store/` for coverage. For any species with no provider data, add a manual yield table CSV: `data/input/yield_tables/<standardized_name>.csv` with columns `age,height,dbh`.

**2. Run step 1–3 for each missing species**

```bash
# Per species — substitute species name
growpy-dataset-pipeline --species "Scots Pine" --steps 1,2,3 --ingest-yield-tables
```

Review calibration plots in `data/assets/growth_models/<species>/`. Accept if H vs age and DBH vs age curves track the yield table within ±10%.

**3. Create Grove preset per species**

Each species needs a `.seed.json` in `data/assets/presets/`. Workflow:
- Open Grove 2.3 in Blender
- Load the species-appropriate starter (conifer base for pines/firs, broadleaf base for others)
- Tune: `Branch Angle`, `Branch Length`, `Internode`, `Tropism`, `Crown Shape`
- Export seed from Grove UI → save as `data/assets/presets/<standardized_name>.seed.json`

Reference: existing `data/assets/presets/norway_spruce.seed.json` (conifer) and `european_beech.seed.json` (broadleaf) as starting points.

**4. Validate at 1 height step**

```bash
growpy-dataset-pipeline --species "Scots Pine" --steps 4 --pilot
```

Check `data/output/forest/<species>/` for preview icons. Crown silhouette must be species-recognizable.

**5. Add to `config/assets.toml`** if species is not yet listed, then regenerate CSVs:

```bash
growpy-dataset-pipeline --generate-csvs
```

---

## XRFF-127 — Full batch production (High, assignee: Max)

**Prerequisite**: XRFF-129 complete (all 10-species presets + calibrations validated).

### Steps

**1. Clean previous pilot output** (optional if re-running all)

```bash
growpy-dataset-pipeline --all --steps 4 --clean
```

**2. Run full pipeline**

```bash
growpy-dataset-pipeline --all --steps all --ingest-yield-tables
```

Step 4 runs one subprocess per species. Monitor `data/output/forest/`. Estimated: 4–8 h depending on hardware.

**3. Generate dataset overview**

The pipeline auto-generates `data/output/forest/overview.md`. Review icon grid for QA.

**4. Handoff to Paul (XRFF-59)**

Zip `data/output/forest/` and transfer to Unreal project content directory, or set up shared network path. Paul needs the USD files + PVE configs.

---

## XRFF-36 — Grove generation with full Ecosense dataset (Medium, assignee: Max)

**Status**: In Progress (since Dec 2025). The live API integration (XRFF-20) is done — Unreal fetches inventory from PostgREST at runtime. What remains for XRFF-36 is **driving growpy batch generation from the live DB inventory** rather than a static CSV, so that tree proportions (height, DBH) match the actual Ecosense measurements.

### Steps

**1. Export inventory snapshot for growpy input**

```bash
# Query PostgREST for Ecosense trees_flat view
curl "http://<db-host>/trees_flat?site=eq.ecosense&select=species,height_m,dbh_cm,x,y" \
  -H "apikey: <anon-key>" > data/input/ecosense_inventory.csv
```

Or write `scripts/export_inventory_for_growpy.py` in `digital-twin-db` that queries and formats to growpy CSV schema (`x,y,species,height`).

**2. Run growpy with inventory CSV**

```bash
growpy-generate-forest --csv data/input/ecosense_inventory.csv --quality high
```

This places trees matching the actual inventory height/DBH distribution, not the calibration grid.

**3. Validate species coverage**

Cross-check that all 5 Ecosense dominant species have presets. If any inventory record uses a species without a preset, the pipeline falls back to nearest calibrated species — document this in the run log.

**4. Mark done when** the generated forest for the full Ecosense plot (not just pilot 2 species) produces correctly-proportioned trees for all inventory records.

---

## XRFF-134 — Add GBIF taxon key to species lookup (High, assignee: Max)

**Goal**: Add `GBIF Key` column to `src/growpy/config/templates/tree_asset_lookup.csv` and embed `gbif_taxon_key` in per-tree output metadata JSON. UE DataTable uses integer key (not name string) for cross-system species matching against digital-twin-db.

**Prerequisite**: XRFF-133 (digital-twin-db) complete — DB must have `gbif_taxon_key` populated before validation in Step 4.

### Steps

**1. Complete GBIF Key population in tree_asset_lookup.csv**

`GBIF Key` column added. 9 dataset species populated. Resolve remaining dataset species via GBIF Species Match API:

```bash
curl "https://api.gbif.org/v1/species/match?name=Fraxinus+excelsior"
# Response includes: { "usageKey": <int>, "scientificName": "...", "status": "ACCEPTED" }
```

Priority — resolve these for the 16-species dataset (XRFF-127) first:

| Species | Scientific Name |
|---|---|
| Common ash | Fraxinus excelsior |
| Silver birch | Betula pendula |
| Downy birch | Betula pubescens |
| Small-leaved linden | Tilia cordata |
| Grand fir | Abies grandis |
| Rowan / Mountain ash | Sorbus aucuparia |
| Black alder | Alnus glutinosa |
| Hornbeam | Carpinus betulus |

Remaining 44 Grove species can be populated later.

**2. Propagate key through pipeline metadata**

In the per-tree metadata JSON writer (wherever `*_DynamicWind.json` or tree metadata is written), add `gbif_taxon_key` field sourced from lookup CSV:

```python
# metadata output
{
    "species": "european_beech",
    "scientific_name": "Fagus sylvatica",
    "gbif_taxon_key": 2882316,
    ...
}
```

Find the metadata writer: search `src/growpy/io/` for the JSON output function.

**3. UE DataTable update (Paul — XRFF-14 / XRFF-59)**

Add `GBIFTaxonKey` (int32) column to tree mesh DataTable in UE. Populate from growpy output metadata JSON. Switch species match logic from name string to `GBIFTaxonKey` int match against API response `gbif_taxon_key`.

**4. Validate sync with digital-twin-db**

Every `GBIF Key` in growpy lookup must exist in `shared.species.gbif_taxon_key` in the DB:

```bash
# Spot-check: query DB species keys, compare against tree_asset_lookup.csv
curl "http://<db-host>/species?select=common_name,gbif_taxon_key" -H "apikey: <anon-key>"
```

**5. Mark done when** all 16 dataset species have `GBIF Key` populated, key flows into output metadata JSON, and Paul has updated the UE DataTable column.

---

## Dependency Map

```
pylometree yield tables
    ↓ (ingested via --ingest-yield-tables)
XRFF-129: calibrate 5 species
    ↓
XRFF-127: full batch (~522 models)
    ↓
Paul: XRFF-59 → XRFF-61 → XRFF-17

XRFF-134 (GBIF taxon key in lookup + metadata)  ← parallel track
    ↓
XRFF-36 (live DB → growpy) requires all dataset species GBIF keys synced
```

---

## XRFF-132 — Sensitivity Analysis Pipeline for Grove Seed Parameters (Medium, assignee: Max)

**Goal**: Systematically sweep Grove `.seed.json` parameters across the full preset library, grow individual trees at 10/20/30 cycles per parameter combination, and produce standardized plots + an aggregate overview CSV to understand which parameters drive tree morphology.

**Non-goal**: USD export, Blender, or Unreal. This runs via `the_grove_23_core` directly (like `sweep_dbh_params.py`). No mesh export — skeleton-only renders.

### Architecture

```
growpy-sensitivity-analysis
    ├── scan all .seed.json → param_catalog.py (stats per parameter)
    ├── select top-N params by observed range → sweep design
    ├── generate all combinations (3 values × N params)
    ├── for each combo × cycles (10, 20, 30):
    │       run_single_simulation() → height, DBH, crown metrics
    │       render preview (2×2 square canvas)
    │       render 3 separate icon PNGs (front / side / top)
    └── aggregate → sensitivity_overview.csv + summary plot grid
```

Output tree: `data/output/sensitivity/`

### Step 1 — Parameter catalog (`src/growpy/tools/param_catalog.py`)

- Scan all `.seed.json` from `src/the_grove_23/presets/` (55 files) and `data/assets/presets/` (5 calibrated species)
- Skip: keys starting with `_`, boolean fields, nested dict/list fields
- Per parameter: compute `min`, `max`, `range`, `mean`, `std` across all files
- Rank by `range` descending
- Output: `data/output/sensitivity/param_catalog.csv`

Run standalone:

```bash
growpy-sensitivity-analysis --dry-run --n-params 0  # just catalog, no sweep
```

### Step 2 — Sweep design (in `sensitivity_pipeline.py`)

- Load catalog, select top-N by range (CLI `--n-params`, default 6)
- For each selected parameter: `lo` = p10, `mid` = p50, `hi` = p90 of observed values across presets
- Generate all combinations via `itertools.product` → each combo is a `dict[str, float]`
- Total simulations: `len(combos) × len(cycle_counts)` — logged clearly before run starts
- Each combo written as a dict in memory (no temp files needed)

**Recommended default parameters** (by expected range from partial scan):

| Parameter | Effect |
|---|---|
| `grow_length` | primary height driver |
| `add_angle` | branch spread angle |
| `add_side_branches` | branching density |
| `add_horizontal` | horizontal vs vertical growth |
| `favor_bright` | phototropism |
| `bend_mass` | branch droop |

### Step 3 — Simulation loop (in `sensitivity_pipeline.py`)

Reuse `run_single_simulation()` pattern from `src/growpy/tools/sweep_dbh_params.py`:

```python
import the_grove_23_core as gc

# For each (combo_id, combo_params, cycles):
preset_data = load_base_preset(base_preset_path)
preset_data.pop("_yield_table_calibration", None)
preset_data.update(combo_params)
grove = gc.Grove(); grove.clear_trees(); grove.set_random_seed(seed)
grove.set_properties(gc.io.properties_from_json_string(json.dumps(preset_data)))
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(cycles)
skeleton = grove.build_models({})[0]  # or grove.trees[0]
```

Captured metrics per run:

| Metric | Source |
|---|---|
| `height_m` | max Z of `skeleton.points` |
| `dbh_m` | trunk radius interpolation at 1.3m (existing `_measure_dbh`) |
| `crown_width_m` | XY bounding box width of points above 50% of max Z |
| `crown_radius_m` | mean radial distance from XY centroid, upper-50% points |
| `crown_area_m2` | convex hull area of XY points, upper-50% |
| `branch_count` | `len(skeleton.poly_lines)` |
| `segment_count` | total polyline segments |

### Step 4 — Image generation

**New/updated functions in `src/growpy/io/usd/preview.py`:**

#### Preview (`_sensitivity.png`) — square canvas

- 2×2 matplotlib figure, `figsize=(12, 12)`:
  - `[0,0]` Front view (X vs Z)
  - `[0,1]` Side view (Y vs Z)
  - `[1,0]` Top view (X vs Y)
  - `[1,1]` Text panel: swept param name/value, stats (H, DBH, crown width/area)
- Save at 150 dpi → 1800×1800 px square PNG
- Filename: `{combo_id:04d}_c{cycles:02d}_preview.png`

#### Icons — 3 separate square PNGs

Extend `generate_icon_image()` to accept a `view` argument:

- `view="front"` → X vs Z (horizontal axis = X, vertical = Z)
- `view="side"` → Y vs Z (existing default)
- `view="top"` → X vs Y (horizontal axis = X, vertical = Y)

Filenames:

- `{combo_id:04d}_c{cycles:02d}_icon_front.png`
- `{combo_id:04d}_c{cycles:02d}_icon_side.png`
- `{combo_id:04d}_c{cycles:02d}_icon_top.png`

All icons: 512×512 px (existing `size_px` default). Square canvas enforced via existing XY padding logic; apply same padding for top/front views.

### Step 5 — Aggregate CSV

`data/output/sensitivity/sensitivity_overview.csv`

Columns:

```
combo_id, cycles, <param1>, <param2>, ..., <paramN>,
height_m, dbh_m, crown_width_m, crown_radius_m, crown_area_m2,
branch_count, segment_count,
icon_front, icon_side, icon_top, preview
```

Also produce `data/output/sensitivity/sensitivity_overview.md` with:

- Param catalog table (top-N params, ranges, lo/mid/hi values used)
- Side-by-side icon grid: rows = param values (lo/mid/hi), cols = cycle counts (10/20/30), grouped by parameter (one section per swept param, holding others at mid)

### Step 6 — CLI entry point (`src/growpy/cli/sensitivity_analysis.py`)

```
growpy-sensitivity-analysis
  --preset-dir   DIR   Preset dir(s) to scan, space-separated (default: src/the_grove_23/presets data/assets/presets)
  --base-preset  STEM  Base preset stem to build combos on (default: "Fagaceae - Beech")
  --n-params     INT   Top-N params by range to sweep (default: 6)
  --cycles       LIST  Comma-separated cycle counts (default: 10,20,30)
  --output-dir   DIR   Output root (default: data/output/sensitivity)
  --seed         INT   RNG seed (default: 42)
  --dry-run            Print plan (combo count, param table) without running
```

### Step 7 — Register entry point in `pyproject.toml`

Add to `[project.scripts]`:

```toml
growpy-sensitivity-analysis = "growpy.cli.sensitivity_analysis:main"
```

### Step 8 — Retrofit 3-view icons to dataset pipeline (optional follow-up)

The existing `generate_icon_image()` in `forest_stages.py` only produces side view.
After Step 4 adds multi-view support, optionally retrofit `generate_forest_stages()` to call all 3 variants.
This is a non-breaking additive change — new files alongside existing `_icon.png`.

### New files

```
src/growpy/
  tools/param_catalog.py             # Step 1: scan presets → catalog CSV
  pipelines/sensitivity_pipeline.py  # Steps 2–5: sweep design, simulation, CSV
  cli/sensitivity_analysis.py        # Step 6: CLI entry point

data/output/sensitivity/             # all outputs (gitignored)
  param_catalog.csv
  sensitivity_overview.csv
  sensitivity_overview.md
  {combo_id:04d}_c{cycles:02d}_preview.png
  {combo_id:04d}_c{cycles:02d}_icon_front.png
  {combo_id:04d}_c{cycles:02d}_icon_side.png
  {combo_id:04d}_c{cycles:02d}_icon_top.png
```

Modified: `src/growpy/io/usd/preview.py` — `generate_icon_image()` gains `view` param.

---

## See Also

- `docs/dataset-specification.md` — full production spec
- `docs/yield-table-calibration.md` — calibration workflow detail
- `config/growth_models.toml` — calibration settings
- `data/assets/presets/` — Grove seed files
