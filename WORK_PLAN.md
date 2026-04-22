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
| Small-leaved linden | ✅ | ✅ | ❌ needs Blender |
| Wild cherry | ✅ | ✅ | ❌ needs Blender |

Bugs fixed (2026-04-22):

- `yield_tables.py`: `write_calibration_to_seed_json()` and `calibrate_species()` used `lower().replace(" ", "_")` — broke hyphenated species names. Fixed to use `standardize_species_name()`.
- `prepare_assets.py`: step 1 overwrote calibrated presets. Fixed with `_yield_table_calibration` existence guard.
- `dataset_pipeline.py`: `--species` flag not forwarded to step 3. Fixed.
- `create_growth_models.py`: `--species` input not normalized before lookup. Fixed.

### Remaining steps

#### 1. Step 2 (twig USDA) for Small-leaved Linden + Wild Cherry

Requires Blender with Grove add-on. In Blender:

- Open `src/the_grove_23/` Grove add-on
- Run twig export script or use the grove convert_twigs step:

```bash
growpy-dataset-pipeline --species "Small-leaved Linden" --steps 2
growpy-dataset-pipeline --species "Wild Cherry" --steps 2
```

#### 2. Step 4 validation (pilot)

Once twig USDAs exist for all species, validate mesh output at ≥1 height step:

```bash
growpy-dataset-pipeline --pilot --steps 4
```

Check `data/output/forest/<species>/` for preview icons. Crown silhouette must be species-recognizable.

---

## XRFF-127 — Full batch production (High, assignee: Max)

**Prerequisite**: XRFF-129 complete (all 11 presets + calibrations validated, twig USDAs for linden + cherry).

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

## XRFF-132 — Sensitivity Analysis Pipeline (Medium, assignee: Max) [IN PROGRESS]

**Status**: Core pipeline implemented and working end-to-end.

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

Remaining:

- Re-install entry point once `growpy-dataset-pipeline.exe` file lock is released:

  ```bash
  pip install -e . --no-deps --ignore-requires-python
  ```

- Retrofit 3-view icons (`_icon_front.png`, `_icon_side.png`) to dataset pipeline step 4 (optional, non-blocking)

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

Priority — resolve these for the 11-species dataset first:

| Species | Scientific Name |
|---|---|
| Common ash | Fraxinus excelsior |
| Silver birch | Betula pendula |
| Small-leaved linden | Tilia cordata |
| Wild cherry | Prunus avium |

**2. Propagate key through pipeline metadata**

In the per-tree metadata JSON writer (wherever `*_DynamicWind.json` or tree metadata is written), add `gbif_taxon_key` field sourced from lookup CSV.

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
