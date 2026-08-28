# Tree Asset Dataset Specification

Defines the target tree-asset dataset for a VR forest simulation in Unreal Engine 5.
Assets are produced with GrowPy + The Grove 2.3 and exported as Nanite-ready USD with
skeletal animation support.

For how to produce it (config, species selection, intervals, run commands) see
[../guides/dataset-workflow.md](../guides/dataset-workflow.md). For production status
and previews see [dataset-overview.md](dataset-overview.md). The authoritative
species catalogue is `config/tree_asset_lookup.csv`.

**Purpose.** Systematically cover the most common tree species of southern Germany
(Bavaria, Baden-Württemberg) at multiple growth stages, with open-grown and
competition variants, and several foliage density levels per species.

**Target engine.** Unreal Engine 5.7+ with Nanite and the Procedural Vegetation
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

Each asset is defined by four orthogonal dimensions:

```
Species (11)
  └─ Surround radius (3)   r00 open-grown, r08, r16 (via [surround] radii)
       └─ Growth stage      every `height_interval` metres up to the height cap
            └─ Density (≤3)  full, reduced, bare (via [export] density_variants)
```

### Surround radius

Each species is simulated once per entry in `[surround] radii`
(`config/surround.toml`), one job row per radius, all built from config by
`dataset_csv_planner.build_job_matrix()`:

| Radius | fid | Layout |
|---|---|---|
| `r00` | 1 | no surround shell; wide crown, heavy branching (open-grown) |
| `r08` | 2 | Grove's built-in **Surround** shell at 8 m; narrow crown, tall clear trunk |
| `r16` | 3 | shell at 16 m -- weakly shaded, deliberately near-open |

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
`[forest] max_height` (or the species' `Max Height`). Density variants are produced
in one simulation via `[export] density_variants` (`full`/`reduced`/`bare`), defined
in `quality.toml`.

## Asset count estimate

The **full ladder** is `11 species × 3 radii × 6–9 stages × 3 densities` = 639
assets: 71 stages in total across the species (each species' `Max Height` at the
5 m interval), times 3 radii, times 3 densities.

The **configured run** is smaller, because `[forest] max_height = 25` caps every
species at the h05–h25 ladder and `[export] density_variants` is empty:
`11 × 3 × 5 × 1` = **165 assets**, which is what `data/output/forest/` holds
today. See [dataset-overview.md](dataset-overview.md) for why the cap is there
and what raising it requires.

## Naming convention

Per-species output lives under `data/output/forest/<species>/<radius>/`, one
subdirectory per surround radius, with filenames embedding radius, height
milestone, DBH and density variant:
`<Species>_r{RR}_h{HH}m_d{DD}cm_{density}_assembly.usdc`. Runs without a radius
axis fall back to `<species>/tree_####/` and drop the `r{RR}` token. See
[../reference/naming-conventions.md](../reference/naming-conventions.md).
