# Dataset Overview

Living registry of the GrowPy tree asset dataset. Updated as production progresses.

See [Dataset Specification](dataset-specification.md) for the full production plan, hierarchy description, and step-by-step guide.

## Summary

Species membership, `Max Height` and therefore stage count all come from
`config/tree_asset_lookup.csv` (the `Dataset` column). That file is the single
source of truth -- this page is a status view over it.

| Metric | Value |
|---|---|
| Target species | 11 (4 conifer + 7 broadleaf) |
| Surround radii | 3 (r00 open-grown, r05, r10) |
| Height stages | 6--9 per species, 71 total |
| Density variants | 3 (full, reduced, bare) |
| **Target total** | **639 models** (71 x 3 x 3) |
| Completed | 0 |

## Production Status

| # | Species | Std. name | Max height | Stages | r00 | r05 | r10 | Notes |
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

Each radius column covers all three density variants (full/reduced/bare) together.
Mark OK when all three pass the review checklist.

European larch is present in `tree_asset_lookup.csv` but is **not** marked for
the dataset, so it is not produced.

Three species have no yield table of their own and borrow a proxy for their
height-DBH allometry (recorded in each `data/assets/allometry/<species>.json`
under `source.title`).

## Preview Gallery

Preview images are generated during production (first density variant only).
Link the per-species preview PNGs here as they become available.

Stage heights follow `Max Height` in `config/tree_asset_lookup.csv` at the
5 m interval set by `[forest] height_interval`.

### Norway spruce

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |

### Scots pine

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver fir

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |

### Douglas fir

| Height | r00 (open) | r05 | r10 |
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

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### European oak

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Common ash

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Sycamore maple

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver birch

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Small-leaved linden

| Height | r00 (open) | r05 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Wild cherry

| Height | r00 (open) | r05 | r10 |
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
│   ├── r00/
│   │   ├── European_Beech_r00_h10_d05_full_stems_skeletal.usda
│   │   ├── European_Beech_r00_h10_d05_full_foliage_a_static.usda
│   │   ├── European_Beech_r00_h10_d05_full_assembly.usda
│   │   ├── European_Beech_r00_h10_d05_full_preview.png
│   │   ├── European_Beech_r00_h10_d05_reduced_assembly.usda
│   │   ├── European_Beech_r00_h10_d05_bare_assembly.usda
│   │   └── textures/
│   ├── r05/
│   └── r10/
├── norway_spruce/
│   └── ...
└── ...
```

The `h<N>` token is the height milestone; `d<NN>` is the DBH the exported mesh
actually carries after allometric scaling.

## Changelog

| Date | Change |
|---|---|
| 2026-07-29 | Corrected against `tree_asset_lookup.csv`: 11 species (linden and wild cherry were missing, European larch is not marked for the dataset), sycamore maple and silver birch are 30 m not 25 m. Stage counts now follow the authored `Max Height` rather than a simulated growth model, so the total is 639 models (71 stages x 3 radii x 3 densities), not 384. |
| 2026-04-04 | Reduced to 10 southern German species (5 conifer + 5 broadleaf), added Douglas fir and European larch |
| *(initial)* | Created dataset overview with 16 species, all pending |
