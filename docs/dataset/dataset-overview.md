# Dataset Overview

Living registry of the GrowPy tree asset dataset. Updated as production progresses.

See [Dataset Specification](dataset-specification.md) for the full production plan, hierarchy description, and step-by-step guide.

## Summary

Species membership, `Max Height` and therefore stage count all come from
`config/tree_asset_lookup.csv` (the `Dataset` column). That file is the single
source of truth -- this page is a status view over it.

The ladder is **one tree at its growth steps**: every stage of a species is a
snapshot of a single continuous Grove simulation, captured as the tree crosses
each 5 m milestone. A taller stage therefore cannot be added to a finished
dataset; raising `Max Height` regrows the species from cycle 0.

| Metric | Produced run (2026-09-22/23) |
|---|---|
| Species | 11 (4 conifer + 7 broadleaf; spruce and fir share a preset) |
| Competition | 3 stands per species — r00 open-grown, r07, r10 (`[surround] radii`, `neighbours = 6` real neighbour trees) |
| Height stages | per species, 5 m interval to its own `Max Height` (h05..h45) |
| Density variants | 1 (full) — `[export] density_variants` empty |
| **Total** | **213 valid of 222 assemblies** — 7 European beech cells never grown (r00 h30, h35/h40 at all three stands) and 2 written as unusable stubs (Norway spruce and silver fir r00 h40) |
| Wall time | 18 h, one species at a time (`-P 1`) |
| On disk | 80 GB under `data/output/forest/` |
| Reproducible from | growpy `dev` @ `69906ac`, config unchanged over the whole run |

`Max Height` per species was set on 2026-09-22 from the digital-twin database
(`trees.trees`, measured `variant_type_id = 1` plus SILVA projections `= 4`,
p99 of the height distribution): beech/spruce/fir 40 m, Douglas fir 45 m, oak
35 m, ash/linden/pine/maple 30 m, birch/cherry 25 m. Birch and cherry exceed
25 m in neither the measured nor the projected data, so their ladder ends there
by evidence rather than by cost.

Density variants are off because crown density is calibrated in the PVE
distributor since 2026-09-10 and `DT_TreeCatalog` has no density column.

Raising a cap means raising `[forest] max_height` **and**
`[growth_models] max_height` together; both are 45 today.

### What limits the ladder

Memory, and it scales with **crown weight, not height**. Measured peak resident
set of the grow process, one species at a time on a 63.5 GB host:

| | peak | outcome |
|---|---|---|
| Douglas fir to 45 m | 32.6 GB | complete |
| Norway spruce / silver fir to 40 m | 42.7 / 41.7 GB | complete |
| European beech to 30 m | 46.4 GB | **MemoryError** |

Beech carries the heaviest crown in the matrix and is the only species whose
ladder ended early; the tallest tree in the dataset cost a third less than beech's
failed h30. This supersedes the older note on this page that an open-grown
conifer "exhausts a 63.5 GB host at h20" — that measurement predates
capture-time export (`core/forest.py`: each milestone is exported and released
as it is captured, instead of the whole ladder being retained for an export
phase at the end, which alone measured 37 GB before export began).

`[quality.dataset_tall]` (resolution 12, `build_cutoff_thickness` 0.005, ~25x
lighter mesh) exists and is wired via `[forest] quality_above_height` +
`quality_above_height_threshold`, switching per grove per milestone so short
stages and shaded siblings keep `[quality.high]`. It is **not enabled**. It is
the available remedy for beech's missing stages; the owner's standing rule is
that a species which collapses gets a different seed, not a lower density
(2026-09-15).

## Production Status

| # | Species | Std. name | Max height | Stages produced | Assemblies | Cycles | Peak RAM | Size |
|---|---|---|---|---|---|---|---|---|
| 1 | Norway spruce | `norway_spruce` | 40 m | h05–h40 (8) | 23+1 stub | 139 | 42.7 GB | 13.6 GB |
| 2 | Scots pine | `scots_pine` | 30 m | h05–h30 (6) | 18/18 | 101 | 31.9 GB | 5.3 GB |
| 3 | Silver fir | `silver_fir` | 40 m | h05–h40 (8) | 23+1 stub | 139 | 41.7 GB | 13.6 GB |
| 4 | Douglas fir | `douglas_fir` | 45 m | h05–h45 (9) | 27/27 | 147 | 32.6 GB | 10.3 GB |
| 5 | European beech | `european_beech` | 40 m | h05–h30 r07/r10, h05–h25 r00 | **17/24** | OOM | 47.8 GB | 11.1 GB |
| 6 | European oak | `european_oak` | 35 m | h05–h35 (7) | 21/21 | 82 | 25.9 GB | 7.6 GB |
| 7 | Common ash | `common_ash` | 30 m | h05–h30 (6) | 18/18 † | 130/242 | 5.3 GB | 1.9 GB |
| 8 | Sycamore maple | `sycamore_maple` | 30 m | h05–h30 (6) | 18/18 | 56 | 19.3 GB | 4.6 GB |
| 9 | Silver birch | `silver_birch` | 25 m | h05–h25 (5) | 15/15 | 80 | 15.5 GB | 3.0 GB |
| 10 | Small-leaved linden | `small_leaved_linden` | 30 m | h05–h30 (6) | 18/18 | 93 | 18.8 GB | 5.4 GB |
| 11 | Wild cherry | `wild_cherry` | 25 m | h05–h25 (5) | 15/15 | 58 | 12.1 GB | 2.5 GB |

### Two corrupt assemblies (open-grown top stages)

Two assemblies exist as 11-byte stubs and are **not usable**:
`Norway_Spruce_r00_h40m` and `Silver_Fir_r00_h40m`. Each is the top stage of
the open-grown (r00) tree, written while free RAM was under ~3 GB. A third,
`European_Beech_r00_h25m`, was corrupt in the same way and came back clean when
beech was re-run on 2026-09-23 — so a re-run does repair this, given memory.

The failure is in the USD **ASCII** writer, not in the growth simulation: the
referenced `*_stems_skeletal.usda` (1.8–2.8 GB) contains binary garbage where a
`primvars:st` array should be, so the reference cannot resolve and the assembly
collapses to a stub. The growth JSON of all three is complete and valid, which
is why the run reported success — the pipeline logs `Skipping empty/stub
assembly ... (11 bytes)` and carries on rather than failing.

Size alone is not the trigger: `european_beech_h20m` (3.57 GB) and
`norway_spruce_h35m` (2.72 GB) are larger and intact. Memory pressure at write
time is the common factor.

Remedies, none applied: `[export] usd_format = "usdc"` (binary, ~50 % smaller
and not ASCII-serialised) would avoid the writer entirely; the corrupt stages
cannot be rebuilt from what is on disk, so recovering them means regrowing
those species. Any future run should treat a stub warning as a failure.

† **Common ash ships a per-radius pick from two seeds** (owner, 2026-09-23).
At the default seed 512 the OPEN-GROWN ash stopped expanding above h20 and shed
its lower crown (r00 21.7 -> 19.8 -> 19.6 m over h20/h25/h30, crown base 8.1 ->
18.8 m, leaf area 175 -> 71 m2), inverting the competition gradient. Three
seeds were grown, and each failed differently:

| ash | complete | r00 crown h30 | r00 leaf h30 | r07 < r10 ? |
|---|---|---|---|---|
| 512 | 18/18 | 19.6 m (collapsed) | 71 m2 | yes, every stage |
| 999 | 18/18 | 22.7 m | 119 m2 | no, r07 widest |
| 7 | 17/18 (r10 never reached h30) | 42.0 m | 210 m2 | no |
| **shipped: r00←7, r07+r10←512** | **18/18** | **42.0 m** | **210 m2** | **yes, every stage** |

Seed 512's stand pair was right all along; only its open tree collapsed. The
shipped ash therefore takes **r00 from seed 7** and **both stand radii from
seed 512**, giving r07 < r10 < r00 at every stage of the ladder, with
r07/r00 = 0.67 / 0.59 / 0.69 at h15 / h25 / h30 (0.65 is the gate's shell-era
threshold, which every species in this dataset misses).

Seeds are per species, not per radius, so
`[general.random_seed_per_species] common_ash = 7` does NOT reproduce this on
its own — the rebuild recipe is in that config comment, and all three archives
are kept under `data/tmp/ladder35_2026-09-22/`. The r07/r10 pair comes from one
simulation, so their comparison is internally consistent; r00 comes from a
different RNG stream, which is the cost of the pick.

Assemblies = stages × 3 stands. "Cycles" is the cycle at which the last
exported tree captured its top milestone, after which the run stops; only the
three exported centre trees gate that stop, not their 6 neighbours each
(`core/forest.py`, 2026-09-22 — before the fix a run waited for its shaded ring
trees, e.g. oak's centre captured h25 at cycle 101 and the run continued to the
160-cycle cap).

Ash reaching h30 in 147 cycles against maple's 56 is the realised growth-rate
spread, not a fault.

European larch is present in `tree_asset_lookup.csv` but is **not** marked for
the dataset, so it is not produced — although the database holds 31 measured
and 2,480 projected larch trees, so a consumer asking for one falls back to
another species.

Three species have no yield table of their own and borrow a proxy for their
height-DBH allometry (recorded in each `data/assets/allometry/<species>.json`
under `source.title`): sycamore maple borrows common ash, small-leaved linden
borrows European beech, wild cherry borrows silver birch. Birch and cherry are
fitted only to 26.0 m and 24.7 m respectively, which their 25 m ceiling stays
inside.

Production record of this run: `data/tmp/ladder35_2026-09-22/` (`PLAN.md`,
`ladder.log`, per-species `grow_*.log` and `mem_*.log`). The previous 165-row
h05–h25 catalog is preserved at
`data/tmp/ladder35_2026-09-22/forest_h25_backup/`.
`data/output/forest/dataset_run_summary.md` is written by
`growpy-dataset-pipeline`; this run invoked `growpy-generate-forest` per
species, so no such summary exists for it.

## Preview Gallery

Icon PNGs are generated during production, once per tree. Link the per-species
icons here as they become available.

Stage heights follow `Max Height` in `config/tree_asset_lookup.csv` at the 5 m
interval set by `[forest] height_interval`. The tables below are what the
2026-09-22/23 run produced; an empty cell is an unlinked icon, a struck cell is
a stage the run did not reach.

### Norway spruce

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |
| 40 m | | | |

### Scots pine

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver fir

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |
| 40 m | | | |

### Douglas fir

| Height | r00 (open) | r07 | r10 |
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

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | ~~not reached~~ | ~~not reached~~ | ~~not reached~~ |
| 35 m | ~~not reached~~ | ~~not reached~~ | ~~not reached~~ |
| 40 m | ~~not reached~~ | ~~not reached~~ | ~~not reached~~ |

### European oak

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |
| 35 m | | | |

### Common ash

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Sycamore maple

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Silver birch

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |

### Small-leaved linden

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |
| 30 m | | | |

### Wild cherry

| Height | r00 (open) | r07 | r10 |
|---|---|---|---|
| 5 m | | | |
| 10 m | | | |
| 15 m | | | |
| 20 m | | | |
| 25 m | | | |

## Output Directory Structure

Completed models are exported to `data/output/forest/<species>/<radius>/`, one
subdirectory per surround radius:

```
data/output/forest/
├── european_beech/
│   ├── species_info.json
│   ├── r00/
│   │   ├── european_beech_h25m_d35cm_stems_skeletal.usda
│   │   ├── European_Beech_r00_h25m_d35cm_full_assembly.usda
│   │   ├── European_Beech_r00_h25m_d35cm_full_growth_data.json
│   │   ├── European_Beech_r00_h25m_d35cm_full_growth_data.floor.json
│   │   ├── European_Beech_r00_h25m_d35cm_full.tamf.json
│   │   ├── European_Beech_r00_h25m_d35cm_full_stems_unreal_wind.json
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front.png
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front_twigs.png
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front_branches.png
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front_twigsonly.png
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front_skeleton.png
│   │   ├── European_Beech_r00_h25m_d35cm_full_icon_front_merged.png
│   │   ├── (the same six icons again for _side and _top)
│   │   └── textures/
│   ├── r07/
│   └── r10/
├── norway_spruce/
│   └── ...
└── unreal_scripts/
```

The `h<NN>m` token is the height milestone; `d<NN>cm` is the DBH the exported
mesh actually carries after allometric scaling. The `full` token is the density
variant label -- with `[export] density_variants` empty it is always `full`.
`.usda` follows `[export] usd_format`.

One stage above is shown in full; the others repeat the same file set. Six
icons per view x three views is what `[export] icon_components = true`
produces. `_growth_data.json` feeds the PVE foliage route;
`_growth_data.floor.json` is its crown-floor-pruned twin, written at plan time
for species with a `crown_floor` calibration. `_crown_outline.png` is written
only by `growpy-crown-metrics --outlines`, and only for the stage it was run
against.

## Changelog

| Date | Change |
|---|---|
| 2026-09-23 | Rewritten for the h05–h45 ladder: 210 valid of 222 assemblies at r00/r07/r10 with 6 real neighbours, per-species `Max Height` derived from the database, per-species production table with measured cycles and peak RAM. Corrected the standing claim that a conifer cannot be built above h20 (silver fir now reaches h40 at 41.7 GB) and recorded the one shortfall (beech h30/h35/h40, MemoryError at 46.4 GB). The page had still described 66 assemblies at r08/r16 with `max_height = 15`. |
| 2026-08-28 | Split the summary into full ladder (639) vs configured run (165). The page claimed 639 as a single target while `[forest] max_height = 25` and an empty `[export] density_variants` produce 165; the surround radii were listed as r00/r05/r10, two revisions behind `[surround] radii = [0.0, 8.0, 16.0]`; and "Completed 0" predated the 2026-08-13 admission audit. |
| 2026-07-29 | Corrected against `tree_asset_lookup.csv`: 11 species (linden and wild cherry were missing, European larch is not marked for the dataset), sycamore maple and silver birch are 30 m not 25 m. Stage counts now follow the authored `Max Height` rather than a simulated growth model, so the total is 639 models (71 stages x 3 radii x 3 densities), not 384. |
| 2026-04-04 | Reduced to 10 southern German species (5 conifer + 5 broadleaf), added Douglas fir and European larch |
| *(initial)* | Created dataset overview with 16 species, all pending |
