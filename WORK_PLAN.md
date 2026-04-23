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

**Status: ✅ COMPLETE** (2026-04-22)

All 10 species have `.seed.json` presets in `data/assets/presets/`:
- `norway_spruce`, `european_beech`, `silver_fir`, `scots_pine`, `european_oak`
- `douglas_fir`, `sycamore_maple`, `common_ash`, `european_larch`, `silver_birch`

All 10 species have calibrated growth models in `data/assets/growth_models/`.
All 10 species have merged CSVs in `data/input/dataset/`.

**Note**: The original "missing presets" table below is now obsolete — all listed species have been completed.

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

**Status: ⏳ PENDING** (XRFF-129 prerequisite met)

### Steps

**0. Fix known issues before running**

The last run of `dataset_pipeline.py --all --steps 3` exited with code 1. Investigate and fix before full batch:

```bash
# Check what failed
python src/growpy/cli/dataset_pipeline.py --pilot --steps 3 --verbose
```

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

## Dependency Map

```
pylometree yield tables
    ↓ (ingested via --ingest-yield-tables)
XRFF-129: calibrate 5 species
    ↓
XRFF-127: full batch (~522 models)
    ↓
Paul: XRFF-59 → XRFF-61 → XRFF-17
```

## See Also

- `docs/dataset-specification.md` — full production spec
- `docs/yield-table-calibration.md` — calibration workflow detail
- `config/growth_models.toml` — calibration settings
- `data/assets/presets/` — Grove seed files
