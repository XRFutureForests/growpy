# Tree Asset Dataset Specification

Defines the target tree-asset dataset for a VR forest simulation in Unreal Engine 5.
Assets are produced with GrowPy + The Grove 2.3 and exported as Nanite-ready USD with
skeletal animation support.

For how to produce it (config, species selection, intervals, run commands) see
[../guides/dataset-workflow.md](../guides/dataset-workflow.md). For production status
and previews see [dataset-overview.md](dataset-overview.md). The authoritative
species catalogue is `config/tree_asset_lookup.csv`.

**Purpose.** Systematically cover the most common tree species of southern Germany
(Bavaria, Baden-Württemberg) at multiple growth stages, under two competition levels
(Grove surround shells). Foliage density is *not* a dataset axis: since 2026-09-10 it is
calibrated on the Unreal side (PVE distributor), and the density variants in `[export]`
stay off.

**Target engine.** Unreal Engine 5.7+ (5.8 for the PVE route) with Nanite and the Procedural Vegetation
Editor (PVE).

## Species selection

Species are chosen from German National Forest Inventory (Bundeswaldinventur)
frequency data for southern Germany, prioritising area share, ecological importance,
and Grove preset availability. The dataset is **11 species (4 conifer + 7 broadleaf)**.
Membership is controlled by the `Dataset` column in `config/tree_asset_lookup.csv`.

### Conifers (4)

| Common name | Scientific name | Competition group | Max height (m) |
|---|---|---|---|
| Norway spruce | *Picea abies* | slow_conifer | 35 |
| Silver fir | *Abies alba* | slow_conifer | 35 |
| Scots pine | *Pinus sylvestris* | slow_conifer | 30 |
| Douglas fir | *Pseudotsuga menziesii* | fast_conifer | 45 |

### Broadleaf (7)

| Common name | Scientific name | Competition group | Max height (m) |
|---|---|---|---|
| European beech | *Fagus sylvatica* | slow_broadleaf | 30 |
| European oak | *Quercus robur* | slow_broadleaf | 30 |
| Common ash | *Fraxinus excelsior* | fast_broadleaf_wide | 30 |
| Sycamore maple | *Acer pseudoplatanus* | slow_broadleaf | 30 |
| Small-leaved linden | *Tilia cordata* | fast_broadleaf_wide | 30 |
| Silver birch | *Betula pendula* | fast_broadleaf | 30 |
| Wild cherry | *Prunus avium* | slow_broadleaf | 30 |

To add or remove a species, edit the `Dataset` / `Max Height` / `Competition Group`
columns in the lookup CSV — see [../reference/configuration.md](../reference/configuration.md).

## Asset hierarchy

Each asset is defined by three dimensions (a fourth, density, exists in the config and is off):

```
Species (11)
  └─ Surround radius (2)   r08, r16 (via [surround] radii — no open-grown r00 by decision, 2026-09-11)
       └─ Growth stage      every `height_interval` metres up to `[forest] max_height` (15 m today: h05, h10, h15)
            └─ Density (1)     full only; `[export] density_variants` is empty
```

### Surround radius

Each species is simulated once per entry in `[surround] radii`
(`config/surround.toml`), one job row per radius, all built from config by
`dataset_csv_planner.build_job_matrix()`:

| Radius | fid | Layout |
|---|---|---|
| `r08` | 1 | Grove's built-in **Surround** shell at 8 m; narrow crown, tall clear trunk |
| `r16` | 2 | shell at 16 m -- weakly shaded, deliberately near-open |

There is no `r00` open-grown row: a weaker shell was measured as nearly indistinguishable
from open-grown, so r16 serves that role (owner decision 2026-09-11, recorded in
`config/surround.toml`). A `surround_radius` of 0 is still accepted for ad-hoc CSVs.

Rows are separated along x (`OPEN_TREE_X * i`) purely so they do not overlap;
each is simulated in its own grove regardless, because Grove disables Surround
when several trees share a grove.

The surround shell replaces the earlier multi-tree competition cluster: instead
of planting neighbour trees and thinning them outward, Grove shades the single
tree against a statistical shell (`enable_surround`), giving the same
forest-grown form at a fraction of the cost. Shell parameters come from the
`[surround]` section in `config/surround.toml`, where `grow` and `density` both
take per-species overrides.

16 m is beyond the 4-10 m range Grove documents for `surround_distance`, so read
r16 as a wide, weakly-competed variant rather than a strongly-shaded one.

### Growth stage and density

Stages are produced by `[forest] height_interval` (metres between stages) up to
`[forest] max_height` (or the species' `Max Height`). Density variants *can* be produced
in one simulation via `[export] density_variants` (`full`/`reduced`/`bare`, defined in
`quality.toml`) but the list is empty in production: crown density is calibrated in the
PVE distributor, not baked into assets.

## Asset count

The **configured run** is `11 species × 2 radii × 3 stages (h05, h10, h15) × 1 density` =
**66 assets**, which is what `data/output/forest/` holds today
(`dataset_run_summary.md`, 2026-09-14). The earlier full-ladder figure (639 = 71 stages ×
3 radii × 3 densities) no longer describes any target: the density axis and r00 were
dropped, and the cap is 15 m until the conifer height-LOD ladder exists (XRFF-324). See
[dataset-overview.md](dataset-overview.md) for why the cap is there and what raising it
requires.

## Naming convention

Per-species output lives under `data/output/forest/<species>/<radius>/`, one
subdirectory per surround radius, with filenames embedding radius, height
milestone, DBH and density variant:
`<Species>_r{RR}_h{HH}m_d{DD}cm_{density}_assembly.usdc`. Runs without a radius
axis fall back to `<species>/tree_####/` and drop the `r{RR}` token. See
[../reference/naming-conventions.md](../reference/naming-conventions.md).
