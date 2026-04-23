# GrowPy — Work Plan

Linear: [XRFF team](https://linear.app/geosense-ufr/team/XRFF/all)

## Issue Sequence

```
XRFF-129 (calibrate remaining species) [IN PROGRESS]
    └─► XRFF-127 (full 11-species batch production)
            └─► XRFF-59  (Paul: import assets into UE)
                XRFF-61  (Paul: showcase library in UE)
                XRFF-17  (Paul: production trees at inventory positions)

XRFF-132 (sensitivity analysis pipeline)  ← parallel track [IN PROGRESS]
XRFF-36  (Grove generation driven by live Ecosense DB)  ← parallel track
```

---

## XRFF-129 — Calibrate remaining species (High, assignee: Max)

**Status: ✅ COMPLETE** (2026-04-22)

All 10 species have `.seed.json` presets in `data/assets/presets/`:
- `norway_spruce`, `european_beech`, `silver_fir`, `scots_pine`, `european_oak`
- `douglas_fir`, `sycamore_maple`, `common_ash`, `european_larch`, `silver_birch`

All 10 species have calibrated growth models in `data/assets/growth_models/`.
All 10 species have merged CSVs in `data/input/dataset/`.

**Note**: The original "missing presets" table below is now obsolete — all listed species have been completed.

### Steps

**1. Ingest yield tables for all remaining species**
**Goal**: Yield table calibration + Grove presets for all 11 dataset species.

**Dataset species** (4 conifer + 7 broadleaf — updated 2026-04-22, European Larch replaced by Small-leaved Linden + Wild Cherry):

| Species | Preset | Calibrated | Twig USDA |
|---|---|---|---|
| Norway spruce | ✅ | ✅ | ✅ |
| Silver fir | ✅ | ✅ | ✅ |
| Scots pine | ✅ | ✅ | ✅ |
| Douglas fir | ✅ | ✅ | ✅ |
| European beech | ✅ | ✅ | ✅ |
| European oak | ✅ | ✅ | ✅ |
| Sycamore maple | ✅ | ✅ | ✅ |
| Common ash | ✅ | ✅ | ✅ |
| Silver birch | ✅ | ✅ | ✅ |
| Small-leaved linden | ✅ | ✅ | ✅ |
| Wild cherry | ✅ | ✅ | ✅ |

Bugs fixed (2026-04-22):

- `yield_tables.py`: `write_calibration_to_seed_json()` and `calibrate_species()` used `lower().replace(" ", "_")` — broke hyphenated species names. Fixed to use `standardize_species_name()`.
- `prepare_assets.py`: step 1 overwrote calibrated presets. Fixed with `_yield_table_calibration` existence guard.
- `dataset_pipeline.py`: `--species` flag not forwarded to step 3. Fixed.
- `create_growth_models.py`: `--species` input not normalized before lookup. Fixed.
- `pyproject.toml`: `requires-python` lowered to `>=3.11` to match growpy conda env (Python 3.11.14). Fixed editable install in growpy env so both `bpy` and `growpy` coexist.

Note: `bpy` lives in the growpy conda env. Steps 1–3 use the base env (has `growpy` editable install, no `bpy`). Steps 2 and 4 use the growpy env directly:

```bash
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --species "..." --steps 2
```

### Remaining steps

#### Step 4 validation (pilot) [IN PROGRESS]

Running pilot (beech + spruce) to verify mesh output at all height steps:

```bash
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --pilot --steps 4
```

Check `data/output/forest/<species>/` for preview icons. Crown silhouette must be species-recognizable.

---

## XRFF-127 — Full batch production (High, assignee: Max) [IN PROGRESS]

**Prerequisite**: XRFF-129 complete ✅

### Steps

**1. Clean previous pilot output** — skipped (re-running all includes done species)

**2. Run full pipeline** — 8/11 species complete as of 2026-04-23

Done: european_beech, norway_spruce, european_oak, sycamore_maple, douglas_fir, common_ash, silver_birch, silver_fir.
Running: scots_pine, small_leaved_linden, wild_cherry.

```bash
# To re-run a specific species:
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --species "Scots pine" --steps 4
```

`species_info.json` (XRFF-134 step 2) backfilled for all 8 completed species via `tmp/backfill_species_info.py`.

**3. Generate dataset overview**

The pipeline auto-generates `data/output/forest/overview.md`. Review icon grid for QA.

**4. Handoff to Paul (XRFF-59)**

Zip `data/output/forest/` and transfer to Unreal project content directory, or set up shared network path. Paul needs the USD files + PVE configs.

---

## XRFF-132 — Sensitivity Analysis Pipeline (Medium, assignee: Max) [DONE]

**Status**: Core pipeline implemented and working end-to-end. All remaining items resolved 2026-04-23.

New files created:

- `src/growpy/tools/param_catalog.py` — scan presets → ranked param catalog CSV
- `src/growpy/pipelines/sensitivity_pipeline.py` — sweep design, simulation, metrics, image gen
- `src/growpy/cli/sensitivity_analysis.py` — CLI entry point

Modified: `src/growpy/io/usd/preview.py` (multi-view icon support), `pyproject.toml` (entry point)

Bugs fixed during implementation:

- `param_catalog.py`: added `_SKIP_PARAMS` to exclude competition/shade geometry params (`shade_area`, `surround_distance`, etc.) from top-N selection
- `sensitivity_pipeline.py`: `run_grove_simulation` used `grove.build_models({})` (returns mesh Model) instead of `grove.build_skeletons(True)` (returns Skeleton with `poly_lines`)
- `sensitivity_pipeline.py`: `measure_metrics` needed Vector-aware point extraction

**Usage**:

```bash
# via base conda env (package installed there)
conda run -n base python src/growpy/cli/sensitivity_analysis.py --dry-run
conda run -n base python src/growpy/cli/sensitivity_analysis.py --n-params 6 --cycles 10,20,30

# or after reinstalling entry point:
growpy-sensitivity-analysis --dry-run
```

**Default sweep** (top 6 params by observed range across 66 presets):

| Parameter | Range | Effect |
|---|---|---|
| `thicken_base_buttress` | 10.0 | trunk base flare |
| `auto_prune_low` | 7.5 | low branch removal |
| `twig_longevity` | 6.0 | twig persistence |
| `bend_mass` | 4.5 | branch droop |
| `add_side_branches` | 4.0 | branching density |
| `grow_nodes` | 4.0 | node count per cycle |

Resolved 2026-04-23:

- Entry point reinstalled (`growpy-sensitivity-analysis.exe` registered in conda env)
- 3-view icons (`_icon_front.png`, `_icon_side.png`, `_icon_top.png`) retrofitted to dataset pipeline step 4 in `forest_stages.py`

---

## XRFF-36 — Grove generation with full Ecosense dataset (Medium, assignee: Max)

**Status: ⏳ IN PROGRESS** (since Dec 2025). The live API integration (XRFF-20) is done — Unreal fetches inventory from PostgREST at runtime. What remains for XRFF-36 is **driving growpy batch generation from the live DB inventory** rather than a static CSV, so that tree proportions (height, DBH) match the actual Ecosense measurements.

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

**1. Complete GBIF Key population in tree_asset_lookup.csv** ✅ DONE 2026-04-23

All 11 dataset species now populated:

| Species | Scientific Name | GBIF Key |
| --- | --- | --- |
| Common ash | Fraxinus excelsior | 3172358 |
| Silver birch | Betula pendula | 5331916 |
| Small-leaved linden | Tilia cordata | 3152047 |
| Wild cherry | Prunus avium | 3020791 |
| + 7 others | (already populated) | ✅ |

**2. Propagate key through pipeline metadata** ✅ DONE 2026-04-23

`_write_species_info()` added to `forest_stages.py`. Writes `species_info.json` per species output folder:

```json
{
  "common_name": "European Beech",
  "standardized_name": "european_beech",
  "scientific_name": "Fagus sylvatica",
  "gbif_taxon_key": 2882316
}
```

File written to `data/output/forest/<species>/species_info.json` once per species on first tree export.

**3. UE DataTable update (Paul — XRFF-14 / XRFF-59)**

Add `GBIFTaxonKey` (int32) column to tree mesh DataTable in UE. Populate from growpy output metadata JSON.

**4. Mark done when** all 11 dataset species have `GBIF Key` populated, key flows into output metadata JSON, and Paul has updated the UE DataTable column.

---

## Dependency Map

```
pylometree yield tables
    ↓ (ingested via --ingest-yield-tables)
XRFF-129: calibrate 11 species [steps 1-3 DONE; steps 2+4 pending Blender]
    ↓
XRFF-127: full batch (11 species)
    ↓
Paul: XRFF-59 → XRFF-61 → XRFF-17

XRFF-132 (sensitivity analysis)  ← parallel track [core pipeline DONE]
XRFF-134 (GBIF taxon key)        ← parallel track
    ↓
XRFF-36 (live DB → growpy) requires all dataset species GBIF keys synced
```

---

## See Also

- `docs/dataset-specification.md` — full production spec
- `docs/yield-table-calibration.md` — calibration workflow detail
- `config/growth_models.toml` — calibration settings
- `data/assets/presets/` — Grove seed files (all 11 calibrated)
- `data/output/sensitivity/` — sensitivity analysis outputs (gitignored)
