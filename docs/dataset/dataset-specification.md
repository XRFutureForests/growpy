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
| Common ash | *Fraxinus excelsior* | fast_broadleaf | 30 |
| Sycamore maple | *Acer pseudoplatanus* | slow_broadleaf | 25 |
| Small-leaved linden | *Tilia cordata* | fast_broadleaf | 25 |
| Silver birch | *Betula pendula* | fast_broadleaf | 25 |
| Wild cherry | *Prunus avium* | slow_broadleaf | 20 |

To add or remove a species, edit the `Dataset` / `Max Height` / `Competition Group`
columns in the lookup CSV — see [../reference/configuration.md](../reference/configuration.md).

## Asset hierarchy

Each asset is defined by four orthogonal dimensions:

```
Species (11)
  └─ Individual (2)         open-grown, surround
       └─ Growth stage      every `height_interval` metres up to the height cap
            └─ Density (≤3)  full, reduced, bare (via [export] density_variants)
```

### Individual

Each species is simulated as two single-tree individuals (see the generated
`{species}_merged.csv`):

| Individual | Layout |
|---|---|
| `open_grown` | one tree (fid=1) placed at `x=100`, no light competition; wide crown, heavy branching |
| `surround` | one tree (fid=2) at the origin with Grove's built-in **Surround** light-competition shell enabled; narrow crown, tall clear trunk |

The `surround` individual replaces the earlier multi-tree competition cluster:
instead of planting neighbour trees and thinning them outward, Grove shades the
single tree against a statistical shell (`enable_surround`), giving the same
forest-grown form at a fraction of the cost. Shell parameters come from the
`[surround]` section in `config/surround.toml`.

### Growth stage and density

Stages are produced by `[forest] height_interval` (metres between stages) up to
`[forest] max_height` (or the species' `Max Height`). Density variants are produced
in one simulation via `[export] density_variants` (`full`/`reduced`/`bare`), defined
in `quality.toml`.

## Asset count estimate

Roughly `11 species × 2 individuals × ~5–9 stages × ≤3 densities`. With a 5 m
interval, tall conifers yield the most stages; shorter broadleaf fewer. The exact
count depends on `height_interval`, `max_height`, and how many density variants are
enabled.

## Naming convention

Per-species output lives under `data/output/forest/<species>/tree_####/`. In
multi-stage mode filenames embed cycle/height/DBH:
`<species>_c{cycle}_h{height}_d{dbh}_assembly.usda`. See
[../reference/naming-conventions.md](../reference/naming-conventions.md).
