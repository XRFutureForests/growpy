# Dataset Overview

Living registry of the GrowPy tree asset dataset. Updated as production progresses.

See [Dataset Specification](dataset-specification.md) for the full production plan, hierarchy description, and step-by-step guide.

## Summary

| Metric | Value |
|---|---|
| Target species | 16 |
| Individual types | 2 (open-grown, competition) |
| Height stages | 4--7 per species |
| Density variants | 3 (full, reduced, bare) |
| **Target total** | **~522 models** |
| Completed | 0 |

## Production Status

| # | Species | Std. name | Max height | Stages | Growth model | Open | Comp | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Norway spruce | `norway_spruce` | 35 m | 7 | -- | -- | -- | |
| 2 | Scots pine | `scots_pine` | 30 m | 6 | -- | -- | -- | Own height group |
| 3 | Silver fir | `silver_fir` | 35 m | 7 | -- | -- | -- | |
| 4 | Austrian pine | `austrian_pine` | 25 m | 5 | -- | -- | -- | |
| 5 | Grand fir | `grand_fir` | 35 m | 7 | -- | -- | -- | |
| 6 | Western redcedar | `western_redcedar` | 25 m | 5 | -- | -- | -- | |
| 7 | European beech | `european_beech` | 30 m | 6 | -- | -- | -- | Pilot species |
| 8 | European oak | `european_oak` | 30 m | 6 | -- | -- | -- | |
| 9 | Common ash | `common_ash` | 30 m | 6 | -- | -- | -- | |
| 10 | Sycamore maple | `sycamore_maple` | 25 m | 5 | -- | -- | -- | |
| 11 | Silver birch | `silver_birch` | 25 m | 5 | -- | -- | -- | |
| 12 | Black alder | `black_alder` | 25 m | 5 | -- | -- | -- | |
| 13 | Hornbeam | `hornbeam` | 20 m | 4 | -- | -- | -- | |
| 14 | Small-leaved linden | `small_leaved_linden` | 25 m | 5 | -- | -- | -- | |
| 15 | Wild cherry | `wild_cherry` | 20 m | 4 | -- | -- | -- | |
| 16 | Field maple | `field_maple` | 20 m | 4 | -- | -- | -- | |

**Status key**: -- = not started, WIP = in progress, OK = complete, SKIP = intentionally skipped

**Open/Comp columns** track all three density variants (full/reduced/bare) together. Mark OK when all three variants pass the review checklist.

## Preview Gallery

Preview images are generated during production (first density variant only). Link to the per-species preview PNGs here as they become available.

### Pilot Species

#### European Beech

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |

#### Norway Spruce

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |
| 35 m | | |

### Conifers

#### Scots Pine

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |

#### Silver Fir

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |
| 35 m | | |

#### Austrian Pine

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

#### Grand Fir

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |
| 35 m | | |

#### Western Redcedar

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

### Broadleaves

#### European Oak

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |

#### Common Ash

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |
| 30 m | | |

#### Sycamore Maple

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

#### Silver Birch

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

#### Black Alder

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

#### Hornbeam

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |

#### Small-leaved Linden

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |
| 25 m | | |

#### Wild Cherry

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |

#### Field Maple

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | | |
| 10 m | | |
| 15 m | | |
| 20 m | | |

## Output Directory Structure

Completed models are exported to `data/output/forest/<species>/`:

```
data/output/forest/
├── european_beech/
│   └── tree_0001/
│       ├── european_beech_h10_d05_full_stems_skeletal.usda
│       ├── european_beech_h10_d05_full_foliage_a_static.usda
│       ├── european_beech_h10_d05_full_assembly.usda
│       ├── european_beech_h10_d05_full_preview.png
│       ├── european_beech_h10_d05_reduced_stems_skeletal.usda
│       ├── european_beech_h10_d05_reduced_assembly.usda
│       ├── european_beech_h10_d05_bare_stems_skeletal.usda
│       ├── european_beech_h10_d05_bare_assembly.usda
│       └── textures/
├── norway_spruce/
│   └── ...
└── ...
```

## Changelog

| Date | Change |
|---|---|
| *(initial)* | Created dataset overview with 16 species, all pending |
