# Dataset Overview

Living registry of the GrowPy tree asset dataset. Updated as production progresses.

See [Dataset Specification](dataset-specification.md) for the full production plan, hierarchy description, and step-by-step guide.

## Summary

Species membership, `Max Height` and therefore stage count all come from
`config/tree_asset_lookup.csv` (the `Dataset` column). That file is the single
source of truth -- this page is a status view over it.

The **configured run** is what `config/` produces today; the earlier "full ladder"
(639 = 71 stages × 3 radii × 3 densities) is history — the density axis was dropped, r00
was dropped, and the height cap is 15 m. The generated record of every run is
`data/output/forest/dataset_run_summary.md` (+ `.csv` with the full history); **that file,
not this page, is the production status.**

| Metric | Configured run (2026-09-14) |
|---|---|
| Species | 11 (4 conifer + 7 broadleaf; spruce and fir share a preset) |
| Surround radii | 2 — r08, r16 (`[surround] radii`; no open-grown variant by decision) |
| Height stages | h05, h10, h15 (`[forest] max_height = 15`) |
| Density variants | 1 (full) — `[export] density_variants` empty |
| **Total** | **66 assemblies**, 0 failed species, 1 h 20 min |
| Imported into UE | the 66 as `DT_TreeCatalog` rows in XRLabDB; the four conifers still carry uncalibrated shell densities (XRFF-449) |

The cap is not a placeholder. Above h15 the conifers need the height-LOD ladder that does
not exist yet (XRFF-324): at `[quality.high]` an open-grown silver fir exhausts a 63.5 GB
host at h20, and the one h30 attempt died on a `MemoryError`. Density variants are off
because crown density is calibrated in the PVE distributor since 2026-09-10 and
`DT_TreeCatalog` has no density column. Measurements: the knowledge hub's
`04-LOGIC-TIER/growpy-surround-density-calibration` and `growpy-crown-density-ratchet`;
deliverables: XRFF-320.

Raising the cap means raising `[forest] max_height` **and** `[growth_models] max_height`
together.

## Production Status

Per-species, per-run status is generated: `data/output/forest/dataset_run_summary.md`.
The table below is the species catalogue with its *ladder* facts (max height from
`tree_asset_lookup.csv`, stages at the 5 m interval); it does not track production.

| # | Species | Std. name | Max height | Full-ladder stages | Notes |
|---|---|---|---|---|---|
| 1 | Norway spruce | `norway_spruce` | 35 m | 7 | |
| 2 | Scots pine | `scots_pine` | 30 m | 6 | |
| 3 | Silver fir | `silver_fir` | 35 m | 7 | Shares Norway spruce's Grove preset |
| 4 | Douglas fir | `douglas_fir` | 45 m | 9 | Needs ~147 cycles; cap is 160 |
| 5 | European beech | `european_beech` | 30 m | 6 | Pilot species |
| 6 | European oak | `european_oak` | 30 m | 6 | |
| 7 | Common ash | `common_ash` | 30 m | 6 | Slowest realised growth (0.23 m/cycle) |
| 8 | Sycamore maple | `sycamore_maple` | 30 m | 6 | Borrows common ash's yield table |
| 9 | Silver birch | `silver_birch` | 30 m | 6 | |
| 10 | Small-leaved linden | `small_leaved_linden` | 30 m | 6 | Borrows European beech's yield table |
| 11 | Wild cherry | `wild_cherry` | 30 m | 6 | Borrows silver birch's yield table |

Today's run stops every species at h15 (3 stages), so the full-ladder column is the
ceiling the species *could* reach, not what is produced.

European larch is present in `tree_asset_lookup.csv` but is **not** marked for
the dataset, so it is not produced.

Three species have no yield table of their own and borrow a proxy for their
height-DBH allometry (recorded in each `data/assets/allometry/<species>.json`
under `source.title`).

## Preview Gallery

Icon PNGs are generated during production, once per tree. Link the per-species
icons here as they become available.

Stage heights follow `Max Height` in `config/tree_asset_lookup.csv` at the
5 m interval set by `[forest] height_interval`. The per-species tables below are
the **full ladder**, so every row above 30 m -- and, under the current
`[forest] max_height = 25`, every row above 25 m -- is unreachable by a run of
the committed config. Those cells stay in the tables as the standing target.

### Norway spruce

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |

### Scots pine

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver fir

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |

### Douglas fir

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |
| 40 m | | | |
| 45 m | | | |

### European beech

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### European oak

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Common ash

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Sycamore maple

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver birch

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Small-leaved linden

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Wild cherry

| Height | r00 (open) | r08 | r16 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

## Output Directory Structure

Completed models are exported to `data/output/forest/<species>/<radius>/`, one
subdirectory per surround radius:

```
data/output/forest/
├── european_beech/
│   ├── species_info.json
│   ├── r00/
│   │   ├── european_beech_h25m_d86cm_stems_skeletal.usdc
│   │   ├── European_Beech_r00_h25m_d86cm_full_assembly.usdc
│   │   ├── European_Beech_r00_h25m_d86cm_full_stems_unreal_wind.json
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front.png
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front_twigs.png
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front_branches.png
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front_twigsonly.png
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front_skeleton.png
│   │   ├── European_Beech_r00_h25m_d86cm_full_icon_front_merged.png
│   │   ├── (the same six icons again for _side and _top)
│   │   ├── European_Beech_r00_h25m_d86cm_crown_outline.png
│   │   └── textures/
│   ├── r08/
│   └── r16/
├── norway_spruce/
│   └── ...
├── dataset_overview.md
├── dataset_overview.csv
└── dataset_run_summary.md
```

The `h<NN>m` token is the height milestone; `d<NN>cm` is the DBH the exported
mesh actually carries after allometric scaling. The `full` token is the density
variant label -- with `[export] density_variants` empty it is always `full`.
`.usdc` follows `[export] usd_format`.

One stage above is shown in full; the other four (h05/h10/h15/h20) repeat the
same file set. Six icons per view x three views is what `[export]
icon_components = true` produces; `_preview.png` and the export-control render
are absent because `previews` and `export_control` are off. `_crown_outline.png`
is written only by `growpy-crown-metrics --outlines`, and only for the stage it
was run against.

## Changelog

| Date | Change |
|---|---|
| 2026-08-28 | Split the summary into full ladder (639) vs configured run (165). The page claimed 639 as a single target while `[forest] max_height = 25` and an empty `[export] density_variants` produce 165; the surround radii were listed as r00/r05/r10, two revisions behind `[surround] radii = [0.0, 8.0, 16.0]`; and "Completed 0" predated the 2026-08-13 admission audit. |
| 2026-07-29 | Corrected against `tree_asset_lookup.csv`: 11 species (linden and wild cherry were missing, European larch is not marked for the dataset), sycamore maple and silver birch are 30 m not 25 m. Stage counts now follow the authored `Max Height` rather than a simulated growth model, so the total is 639 models (71 stages x 3 radii x 3 densities), not 384. |
| 2026-04-04 | Reduced to 10 southern German species (5 conifer + 5 broadleaf), added Douglas fir and European larch |
| *(initial)* | Created dataset overview with 16 species, all pending |
