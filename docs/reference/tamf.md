# TAMF — Tree Asset Metadata Format

One JSON record per exported tree asset, stating what the geometry represents and under
what contract it was exported, so a consumer holding only the asset and the record can
place it and judge it without opening the geometry. TAMF is the asset-side exchange
component of the Digital Forest Twin profile (publications `digital-forest-twin-standard`);
the schema is [`schemas/tamf.schema.json`](../../schemas/tamf.schema.json) (JSON Schema
2020-12), version `0.2`.

## Where it is written

| Route | Asset | Record |
|-------|-------|--------|
| USD Nanite assembly (`export_mode = "unreal"`) | `<prefix>_assembly.usda` | `<prefix>.tamf.json` next to it, **and** `customData["tamf"]` on the stage's default prim |
| PVE growth JSON (`export_mode = "growth_json_only"`) | `<prefix>_growth_data.json` | `<prefix>.tamf.json` |
| Helios OBJ (`export_mode = "helios"`) | `<prefix>.obj` | `<prefix>.tamf.json` |

`<prefix>` is the stage's file prefix (`European_Beech_r08_h15m_d22cm_full`, see
[naming-conventions.md](naming-conventions.md)). The record is emitted by the `tamf` stage in
`pipelines/forest_stages.py` (module `io/tamf.py`), always on, per density variant. A
metadata failure is logged and never voids a finished asset export. USD custom data cannot
hold `null`, so null leaves are dropped there and kept in the JSON.

## Blocks

| Block | Content | Source in the pipeline |
|-------|---------|------------------------|
| `asset` | id, format (`usd` / `pve_growth_json` / `obj`), file name, `units: m`, `up_axis: Z`, `origin: stem_base`, CityGML `level_of_detail` (`LoD3`), `geometry_class: implicit` | export route; the USD stage is Z-up metres with the stem base at the origin |
| `species` | scientific name, common name, GBIF taxon key | `config/tree_asset_lookup.csv` |
| `source` | `kind: generated`, `dataset`, `process` (growpy version + commit), timestamp | package metadata, `git rev-parse` |
| `growth_stage` | `height_m` (captured milestone), `dbh_cm` (the diameter the exported mesh carries), `age_years`, `growth_cycles`, `calibration`, `competition_context`, `surround_radius_m` | `TreeExportContext`; the allometry artifact in `data/assets/allometry/<species>.json` |
| `structure` | crown base and tip height, plan-view crown projection area (concave hull) and its equivalent-circle diameter; `leaf_area_m2`, `stem_volume_m3` | `utils/crown_geometry.py` on the Grove skeleton |
| `extensions.x-growpy` | variant, twig density, radial scale, whether the DBH came from the input CSV, fid | producer-specific, outside the profile |

## What the record does not claim

- **`age_years` is `null`.** Yield-table height–age pacing is implemented but disabled
  (`config/growth_models.toml`); stages are captured by height milestone and no age is
  derived. `growth_cycles` is the simulator cycle, not an age.
- **`calibration` names the height–DBH power law only** (`quantity: dbh_from_height`,
  `function: power_law`, parameters, R², fitted height range, the yield-table file, region and
  site index). Outside `height_range_m` the diameter is an extrapolation. A DBH supplied in
  the input CSV is recorded as `source: inventory`, not attributed to a table.
- **`leaf_area_m2` and `stem_volume_m3` are `null`.** Foliage is placed by PVE inside
  Unreal on the production route, so growpy cannot state a per-tree leaf area; no
  stem-volume integration is implemented.

## Example

Record for the beech h15 / r08 stage of the 2026-09-14 run (crown metrics recomputed
from that stage's skeleton):

```json
{
  "tamf_version": "0.2",
  "asset": {
    "id": "European_Beech_r08_h15m_d22cm_full",
    "format": "pve_growth_json",
    "path": "European_Beech_r08_h15m_d22cm_full_growth_data.json",
    "units": "m", "up_axis": "Z", "origin": "stem_base",
    "level_of_detail": "LoD3", "geometry_class": "implicit"
  },
  "species": {
    "scientific_name": "Fagus sylvatica", "common_name": "European beech",
    "gbif_taxon_key": 2882316
  },
  "source": {
    "kind": "generated", "tree_entity_id": null,
    "process": "growpy 0.4.0 (7060905) / The Grove",
    "dataset": "growpy-synthetic-forest", "generated": "2026-09-16T12:39:50+00:00"
  },
  "growth_stage": {
    "height_m": 15.344, "dbh_cm": 22.0, "age_years": null, "growth_cycles": null,
    "calibration": {
      "source": "yield_table",
      "reference": "Store: european_beech_denw_si2_staggered_thinning.csv",
      "region": "DE-NW", "site_index": 2.0, "surrogate": false,
      "quantity": "dbh_from_height", "function": "power_law",
      "parameters": { "a": 0.000804, "b": 1.796199 },
      "r_squared": 0.968368, "height_range_m": [6.0, 34.9],
      "age_pacing": "disabled"
    },
    "competition_context": "surround", "surround_radius_m": 8.0
  },
  "structure": {
    "crown_base_height_m": 3.268, "crown_tip_height_m": 15.344,
    "crown_projection_area_m2": 127.88, "crown_diameter_m": 12.76,
    "leaf_area_m2": null, "stem_volume_m3": null
  },
  "extensions": {
    "x-growpy": { "variant": "full", "twig_density": 1.0, "radial_scale": 1.0,
                  "dbh_from_csv": false, "fid": 1 }
  }
}
```

## Validating a record

```bash
pip install jsonschema check-jsonschema   # not a growpy dependency
check-jsonschema --schemafile schemas/tamf.schema.json data/output/forest/**/*.tamf.json
```
