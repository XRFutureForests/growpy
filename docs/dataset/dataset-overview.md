# Dataset Overview

Living registry of the GrowPy tree asset dataset. Updated as production progresses.

See [Dataset Specification](dataset-specification.md) for the full production plan, hierarchy description, and step-by-step guide.

## Summary

Species membership, `Max Height` and therefore stage count all come from
`config/tree_asset_lookup.csv` (the `Dataset` column). That file is the single
source of truth -- this page is a status view over it.

Two numbers matter and they are not the same. The **full ladder** is what the
species table below describes: every species grown to its own `Max Height`. The
**configured run** is what `config/` actually produces today, and it is smaller
because `[forest] max_height` caps the ladder at 25 m and `[export]
density_variants` is empty.

| Metric | Full ladder | Configured run |
|---|---|---|
| Species | 11 (4 conifer + 7 broadleaf) | 11 |
| Surround radii | 3 (r00 open-grown, r08, r16) | 3 |
| Height stages | 6--9 per species, 71 total | 5 per species (h05--h25), 55 total |
| Density variants | 3 (full, reduced, bare) | 1 (full) |
| **Total** | **639 models** (71 x 3 x 3) | **165 models** (55 x 3 x 1) |
| Admitted in UE | 9 (2026-08-13, r00 h05/h10/h15 x 3 pilot species) | same |

The cap is not a placeholder. Above h25 the tall conifers need the height-LOD
ladder that does not exist yet (XRFF-324): at `[quality.high]` an open-grown
silver fir reaches 19.1 M mesh points at h25 and exhausts a 63.5 GB host at h20.
`[quality.dataset_tall]` gets h20/h25 through at r00; h30+ has no asset at all,
and the one h30 attempt died on a `MemoryError`. Density variants are off for
the same reason -- they triple export cost for an axis nothing consumes yet, as
`DT_TreeCatalog` has no density column. See
[crown-density-ratchet.md](dataset-specification.md) for the measurements and
XRFF-320 for the deliverables.

Raising the target back to 639 means raising `[forest] max_height` **and**
`[growth_models] max_height` together, and re-enabling `density_variants`.

## Production Status

| # | Species | Std. name | Max height | Stages | r00 | r08 | r16 | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Norway spruce | `norway_spruce` | 35 m | 7 | -- | -- | -- | |
| 2 | Scots pine | `scots_pine` | 30 m | 6 | -- | -- | -- | |
| 3 | Silver fir | `silver_fir` | 35 m | 7 | -- | -- | -- | Shares Norway spruce's Grove preset |
| 4 | Douglas fir | `douglas_fir` | 45 m | 9 | -- | -- | -- | Needs ~147 cycles; cap is 160 |
| 5 | European beech | `european_beech` | 30 m | 6 | -- | -- | -- | Pilot species |
| 6 | European oak | `european_oak` | 30 m | 6 | -- | -- | -- | |
| 7 | Common ash | `common_ash` | 30 m | 6 | -- | -- | -- | Slowest realised growth (0.23 m/cycle) |
| 8 | Sycamore maple | `sycamore_maple` | 30 m | 6 | -- | -- | -- | Borrows common ash's yield table |
| 9 | Silver birch | `silver_birch` | 30 m | 6 | -- | -- | -- | |
| 10 | Small-leaved linden | `small_leaved_linden` | 30 m | 6 | -- | -- | -- | Borrows European beech's yield table |
| 11 | Wild cherry | `wild_cherry` | 30 m | 6 | -- | -- | -- | Borrows silver birch's yield table |

**Status key**: -- = not started, WIP = in progress, OK = complete, SKIP = intentionally skipped

Each radius column covers whichever density variants `[export] density_variants`
enables. That list is empty today, so a radius cell is one asset per stage,
labelled `full`; mark OK when it passes the review checklist. With variants
re-enabled a cell becomes three assets and all three must pass.

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
