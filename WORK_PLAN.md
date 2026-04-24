# GrowPy — Work Plan

Linear: [XRFF team](https://linear.app/geosense-ufr/team/XRFF/all)

**Last updated:** 2026-04-23

---

## Issue Sequence

```
✅ XRFF-129 (calibrate species)
    └─► ✅ XRFF-127 (batch production: 10 species)
            └─► Paul: XRFF-59 (import assets into UE)
                XRFF-61 (showcase library in UE)
                XRFF-17 (production trees at inventory positions)

✅ XRFF-132 (sensitivity analysis pipeline) — core done, CLI entry point registered
✅ XRFF-134 (GBIF taxon key) steps 1+2 ✅ DONE
    └─► Paul: XRFF-14/59 (UE DataTable GBIFKey column)

❌ XRFF-36 (full-stand Grove generation) — CANCELED
    └─► Adopted approach: dataset pipeline → UE catalog match → spawn

Backlog:
XRFF-135  spatial batch processing for full-stand generation (low, deferred)
XRFF-136  crown diameter + structural params in DB for better catalog matching (medium)
```

---

## XRFF-127 — Full batch production (High, assignee: Max)

**Status: ✅ COMPLETE** (2026-04-23)

10 species delivered (3 conifers + 7 broadleaves):

- Norway spruce, Silver fir, Douglas fir
- European beech, European oak, Sycamore maple, Common ash, Silver birch, Small-leaved linden, Wild cherry

Scots pine dropped — generation issues, coverage sufficient without it.

Each species: competition + open-grown context, 5m height steps, USD + PVE configs + 3-view icons + `species_info.json`. Overview at `data/output/forest/dataset_overview.md`.

**Next**: Paul imports assets (XRFF-59). Zip `data/output/forest/` and transfer to Unreal project.

---

## XRFF-132 — Sensitivity Analysis Pipeline (Medium, assignee: Max)

**Status:** ✅ **Core pipeline implemented and working.** CLI entry point registered.

New files:

- `src/growpy/tools/param_catalog.py` — scan presets → ranked param catalog CSV
- `src/growpy/pipelines/sensitivity_pipeline.py` — sweep design, simulation, metrics, image gen
- `src/growpy/cli/sensitivity_analysis.py` — CLI entry point (`growpy-sensitivity-analysis`)

Modified: `src/growpy/io/usd/preview.py` (multi-view icon support), `pyproject.toml` (entry point)

Bugs fixed:

- `param_catalog.py`: `_SKIP_PARAMS` excludes competition/shade geometry params from top-N selection
- `sensitivity_pipeline.py`: `run_grove_simulation` uses `grove.build_skeletons(True)` (not `build_models({})`)
- `sensitivity_pipeline.py`: `measure_metrics` needs Vector-aware point extraction

**Usage**:

```bash
# via base conda env
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

---

## XRFF-36 — Grove generation with full Ecosense dataset

**Status: ❌ CANCELED** (2026-04-23)

Grove cannot process a full stand. Spatial batch processing not planned.

**Adopted approach**: dataset pipeline produces species catalog → UE selects best-matching tree by height/DBH → spawns at inventory position. See XRFF-17 (Paul).

**Backlog**:

- XRFF-135: spatial batch processing if per-stand simulation becomes needed (low priority)
- XRFF-136: add crown diameter + structural params to DB for better catalog matching + overlap avoidance

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

**3. UE DataTable update (Paul — XRFF-14 / XRFF-59)** ⬜ TODO

Add `GBIFTaxonKey` (int32) column to tree mesh DataTable in UE. Populate from growpy output metadata JSON.

**4. Mark done when** all 11 dataset species have `GBIF Key` populated, key flows into output metadata JSON, and Paul has updated the UE DataTable column.

---

## Dependency Map

```
✅ XRFF-129 → ✅ XRFF-127 → Paul: XRFF-59 → XRFF-61 → XRFF-17

✅ XRFF-132  ✅ XRFF-134 (steps 1+2 ✅, step 3 Paul)
```

---

## See Also

- `docs/dataset-specification.md` — full production spec
- `docs/yield-table-calibration.md` — calibration workflow detail
- `config/growth_models.toml` — calibration settings
- `data/assets/presets/` — Grove seed files (all 11 calibrated)
- `data/output/sensitivity/` — sensitivity analysis outputs (gitignored)

