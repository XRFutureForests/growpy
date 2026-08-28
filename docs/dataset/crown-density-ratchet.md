# Crown-Density Ratchet

The memory of the crown-density tuning loop. One row per round, every gate metric,
the config delta that produced it, and pass/fail.

**Ceilings are derived, never invented.** Round 0 measures the current config and
becomes the baseline. Every later round sets each ceiling at the best value achieved
so far that still passed the other gates. A ceiling is never loosened to make a round
pass — a regression is recorded as a regression.

**Linear home: XRFF-320** — "growpy: 639-model dataset catalog via the crown-density
ratchet". This doc stays the source of truth for measurements (round log, gate metrics,
per-species rationale); XRFF-320 and its children track the deliverables. Keep both in
sync — a round that changes coverage or a ceiling should update the relevant issue too.

| Issue | Scope |
|---|---|
| XRFF-321 | D8 — which twig prototype the recorded Gate-2 import validated (blocks Gate 3) |
| XRFF-322 | Re-import the pilot slice at round-3 densities + admission-checklist audit |
| XRFF-323 | Conifer h15+ import cost at 639 scale (61 min/asset) |
| XRFF-324 | Conifer height-LOD ladder (critical path, 4 of 11 species) |
| XRFF-325 | Gate 4 — first in-editor frame-time measurement |
| XRFF-326 | Extend from the 3-species pilot to all 11 species x 3 radii |
| XRFF-327 | Rule out `max_skeleton_joints = 1000` as a Gate-2 failure cause |

Also related: XRFF-272 (allometric leaf-area parent), XRFF-273 (per-tree resolver),
XRFF-274 (Done — per-prototype leaf area), XRFF-318 (pylometree Forrester registration).

---

## The four gates

| Gate | Measures | Instrument | Needs UE? |
|---|---|---|---|
| 1 | Crown fill and separability | `growpy-icon-metrics` | no |
| 2 | Import survives, in reasonable time | `growpy-ue-import-probe` | yes |
| 3 | Expanded triangle budget | `growpy-analyze-usda --triangle-budget` | no |
| 4 | In-editor frame time | `growpy-ue-viewport-probe` | yes |

Gate 3 is the cheap pre-import predictor: `twig_instances x prototype_faces`, summed
per prototype. It exists so a builder can self-screen before spending a UE import.

**Leaf area vs Forrester et al. 2017 (DOI `10.1016/j.foreco.2017.04.011`) is a sanity
check, NOT a gate.** The twig prototypes are biased in physical size — the shared
Pacific silver fir spray carries 0.109 m² against 0.023 m² for ash — so leaf area
back-solved through them yields a distorted target. That bias is precisely why the
current per-species table spans 103x. Report the direction of error; never gate on it.

---

## Pilot slice

Three species chosen to span the whole problem, not the whole dataset.

| Species | Density at round 0 | Why it is in the slice |
|---|---|---|
| `silver_fir` | 0.0078 | most over-dense; shares the large fir spray; no Forrester equation exists |
| `european_beech` | 0.138 | mid-range broadleaf, established pilot species |
| `common_ash` | 0.80 | near Grove-natural; was 20x too sparse at 0.04 |

Stages h05 / h10 / h15, surround radius **r00 only**.

The known worst case is conifers at h05/h10 coming out sparser than target, because the
per-species table was calibrated at h15. The slice must **expose** that, not hide it.

### How the pilot is run

The pilot uses an isolated config directory so eight rounds of tuning do not churn the
repo's `config/`, whose comments are load-bearing documentation:

```powershell
$env:GROWPY_CONFIG = 'D:\Git\work\growpy\data\tmp\pilot_config'   # gitignored (/data/tmp/)
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --species "Silver Fir"     --steps 4 --max-height 15
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --species "European Beech" --steps 4 --max-height 15
conda run -n growpy python src/growpy/cli/dataset_pipeline.py --species "Common Ash"     --steps 4 --max-height 15
```

`data/tmp/pilot_config/` is seeded from `config/` and differs in exactly one place:

```toml
# surround.toml
radii = [0.0]          # pilot is r00 only; repo config is [0.0, 8.0, 16.0]
```

Winning values are promoted into the repo `config/` at the integration pass, not before.

### Icon-emission caveat

Icons are written **once per tree**, and with `[export] density_variants` non-empty they
would show **variant 0 only**. This loop therefore runs with `density_variants = []` — a
single active density per round — so every icon corresponds to the config that produced
it. Icon emission was **not** extended per variant.

---

## Round 0 — baseline (in progress)

Establishes the observed values. No ceilings exist until this completes.

### Starting config state — read this before comparing anything

These config values were carried **uncommitted** in the working tree when the loop
started, and rounds 0-3 all measured them. Their provenance was unknown at the time, so
the loop recorded them as unexplained drift against HEAD.

**Resolved 2026-08-13 — owner confirms these are the intended config, not drift.** They
are now committed, so HEAD and the working tree agree and the "old HEAD" column below is
history only. Nothing about rounds 0-3 changes: they measured the intended values all
along.

| Key | Old HEAD (pre-2026-08-13) | Committed value (round-0 baseline) |
|---|---|---|
| `[forest] quality` | `medium` | `high` |
| `[forest] plateau_cycles` | 25 | 5 |
| `[export] twig_density` (global fallback) | 0.04 | 0.2 |
| `[export] twig_min_spacing_ratio` | 0.5 | 0.75 |
| `[export] youth_bias` | 2.0 | 1.5 |
| `[export] max_skeleton_joints` | 500 | 1000 |
| `[quality.high] build_cutoff_thickness` | 0.00125 | **0.0025** |
| `[quality.medium] build_cutoff_thickness` | 0.002 | **0.0025** |
| `[surround] height` | 1.0 | 0.5 |
| `[growth_models] max_cycles_without_growth` | 15 | 5 |
| `[growth_models] timeout` | 400 | 300 |

Unchanged and load-bearing: `[export.twig_density_per_species]` (all 11 entries),
`twig_recovery = true`, `twig_reattach_threshold = 0.01`,
`max_assembly_instances = 100000`, `density_variants = []`, `static = false`,
`usd_format = "usdc"`.

**Two flags on the baseline itself:**

1. `build_cutoff_thickness` sits at 0.0025, double the old HEAD value of 0.00125 at
   `[quality.high]`. This is the guardrail parameter: raising it removes the youngest
   branches first, which is exactly where Grove places twigs, and it deletes the
   attachment points recovery would otherwise repack onto. The loop will **not** raise it
   further and will not use it to buy triangles. It is recorded here so that a later
   "crowns are hard to fill" finding is attributed correctly.

   **This also closes out the ~3x stem-triangle fit gap** (see "Stem side" below). With
   0.0025 confirmed intended rather than accidental, the carried-forward
   `S(h) = 25,285 . h^2.476` fit is simply obsolete — it was fitted at the thinner cutoff,
   before this value was adopted, and doubling the cutoff prunes exactly the fine
   branching that would explain a 2-3x drop in stem triangle count. No revert experiment
   is needed: **discard that fit and use the measured column.**
   `pilot_config/quality.toml` independently describes this parameter as "purely a mesh
   triangle-budget lever" with recovery active, which is consistent with that reading.
2. `max_skeleton_joints = 1000` contradicts its own config comment, which states that
   Nanite encodes bone indices in 8-bit fields and that 250 is the safe Nanite-Assembly
   value. This is a candidate Gate-2 failure cause **independent of density**, and must be
   ruled out before any import crash is blamed on crown density. Round 2 set this to 250
   in the pilot config and recorded "joint limit cleared"; the repo-level 1000 stands, so
   this contradiction is still open.

### Results — Gate 1 (measured 2026-08-07)

Pilot generation: 6 min 35 s total for 3 species (fir 3:06, beech 2:58, ash 0:30), all
exit 0. `crown_fill` = green pixels / convex hull of (branch ∪ green), per view.

| Tree | crown_fill front | side | top | mean | final twig instances |
|---|---|---|---|---|---|
| `silver_fir` h05 d09 | 0.0108 | 0.0087 | 0.0056 | **0.008** | 30 |
| `silver_fir` h10 d12 | 0.0567 | 0.0505 | 0.0245 | **0.044** | 145 |
| `silver_fir` h15 d18 | 0.1271 | 0.1137 | 0.0691 | **0.103** | 354 |
| `european_beech` h05 d07 | 0.1222 | 0.1270 | 0.0903 | **0.113** | 570 |
| `european_beech` h10 d18 | 0.3379 | 0.3109 | 0.3560 | **0.335** | 3 048 |
| `european_beech` h15 d27 | 0.3861 | 0.3851 | 0.4378 | **0.403** | 5 165 |
| `common_ash` h05 d09 | 0.1504 | 0.1384 | 0.0939 | **0.128** | 794 |
| `common_ash` h10 d16 | 0.3754 | 0.3838 | 0.3805 | **0.380** | 4 554 |
| `common_ash` h15 | — | — | — | **MISSING** | — |

Three things this baseline establishes:

1. **The stage bias is universal, not conifer-specific.** Every species' h05 is 4–13x
   below its own h15. The per-species table was back-solved at h15 alone, and h05 is
   where it fails hardest — for broadleaves too, not just the fir-spray species.
2. **`silver_fir` is ~4x below the broadleaves at every stage** and is effectively bald
   at h05 (30 instances). Its measured leaf area at h15 is ~354 x 0.109 = **38.6 m²**,
   which matches the Forrester pooled-conifer target of 38.6 m² almost exactly. The
   leaf-area target is being hit and the crown is still empty — the exact trap
   `forest.toml`'s own comment predicted. Confirms leaf area must stay a sanity check.
3. **`common_ash` h15 was never generated.** See defect D2 below.

### Defects found at round 0

**D1 — RETRACTED 2026-08-07. Not a defect. Kept here as a trap to avoid re-walking.**

The claim below was wrong, and the numbers in it measure the wrong thing. `densify_twig_placements`
thins **each twig type independently** by the same ratio:

```python
for twig_type, plist in placements.items():
    keep_count = max(1, int(len(plist) * keep_ratio + 0.5))
```

`twig_dead` is therefore thinned inside its own bucket and **never draws budget from
`twig_long`/`twig_upward`**. The "living yield" figures below are dead twigs being thinned
out of a pool they never shared with living foliage — not living foliage being lost.

Verified empirically: with the drop moved ahead of `densify`, `silver_fir` h05 and h10
exported **30 and 145 instances — byte-identical to the round-0 counts**.

The only budget dead twigs genuinely compete for is the global cap in
`thin_placements_to_limit`, and the 2026-08-05 sycamore-maple fix already placed the drop
ahead of that. That fix was correct and complete; there was no second half to it. The
reorder was kept anyway (it makes `effective_density` compose predictably once the cap is
also binding) but it buys **no crown fill**.

Original, incorrect claim follows.

~~Dead twigs are thinned before they are dropped, so the density knob
under-delivers living foliage by a species-dependent 2%–48%.~~

`io/usd/assembly_export.py` runs the stages in this order:

```
densify_twig_placements(effective_density)   # thins ALL types, twig_dead included
  -> drop twig_dead when the species ships no dead-twig asset
  -> thin_placements_to_limit(max_assembly_instances)
```

No dataset species ships a dead-twig asset, so every `twig_dead` placement is discarded
at write time — but it has already consumed density budget. Measured this run:

| Tree | extracted `twig_dead` | share of extraction | survived thinning | dropped | living yield vs promised |
|---|---|---|---|---|---|
| `silver_fir` h15 | 42 704 | 49.4% | 687 total | 333 | **52%** |
| `european_beech` h15 | 15 160 | 46.8% | 7 257 total | 2 092 | **71%** |
| `common_ash` h10 | 131 | 4.0% | 4 659 total | 105 | **98%** |

The 2026-08-05 fix moved this drop ahead of the **instance cap** (and its comment says
so). It was not moved ahead of the **density thinning**, which is the stage that actually
determines crown fill. Consequence: a 2%–48% species-dependent error currently sits
*inside* the hand-tuned per-species table — part of the documented 103x spread is this
defect, not biology. Fixing it roughly doubles `silver_fir`'s living crown at unchanged
density and barely moves `common_ash`.

The per-species table was back-solved with this defect present, so it **must be
re-derived after the fix**.

**D2 — `plateau_cycles = 5` silently deletes dataset stages.**

`common_ash` stopped at cycle 42 with `Growth plateau detected: no height increase for 5
consecutive cycles`, capturing only 2 of 3 milestones. `forest.toml`'s own comment states
the value was "raised from the code default of 10" because "observed real stalls of 7-9
consecutive cycles for some species/radius combos reaching 15-20m" were truncating upper
stages. The working tree's 5 is below both the code default and the documented stall
range. HEAD has 25. This is a working-tree regression, not a loop change.

**D3 — `silver_fir` h15 stems mesh is 256 MB for one tree** (h10 86 MB, h05 17 MB), at
`quality = high`, `resolution = 16`. Unrelated to twigs. Must be isolated before any
Gate-2 import failure is attributed to crown density.

### Gate 2 / 3 / 4

_Pending — harness instruments still building. Gate 3 is computable offline from these
artifacts; Gates 2 and 4 need a UE session, which has not been run._

### Metric calibration — human verdicts on round-0 trees

`crown_fill` and `blob_index` thresholds are **not** hardcoded in the instrument. Round-0
artifacts were reviewed on the contact sheets and judged directly:

| Tree | `crown_fill` | Human verdict (2026-08-07) |
|---|---|---|
| `silver_fir` h05 / h10 / h15 | 0.008 / 0.042 / 0.088 | **too sparse** |
| `european_beech` h05 | 0.101 | "a bit sparse but ok" |
| `european_beech` h10 | 0.313 | (no objection) |
| `common_ash` h10 | 0.374 | **too full** |
| `european_beech` h15 | 0.381 | **too full** |

**Working reference band: `crown_fill` roughly 0.20–0.35.** This is explicitly *not* a
fixed gate — it is the current evaluation, recorded so rounds are comparable, and it is
expected to move as more of the dataset is seen. Do not hardcode it into the instrument
or treat a value inside the band as automatically passing.

The important structural finding is that **Gate 1 is a band, not a floor.** Too dense is
a real failure direction on its own terms (before any triangle-budget consideration), and
the loop can overshoot it.

### On `blob_largest_cc` — do not gate on it

Measured round 0: `european_beech` h15 = 0.804 and `common_ash` h10 = 0.835, on trees that
still visibly read as discrete dots. `blob_largest_cc` is a **percolation** measure — the
instant any dots touch, one component swallows the crown, so it jumps to ~0.8 and then
carries almost no information. `blob_saturation` (compositing depth, 0.207–0.252 on the
same trees) moves continuously with actual stacking and is the usable signal. Report both;
reason with saturation.

---

## Catalog coverage

**The deliverable is models live in XRLabDB (UE 5.7.4), not a passing gate report.**
An asset only counts once it is actually present in `/Game/Assets/TheGrove` in UE with
the full checklist below satisfied -- generating a USD file that was never imported is
not coverage. Track this every round, not just gate metrics.

Two targets:

| | Species | Stages | Radii | Densities | Total |
|---|---|---|---|---|---|
| Full ladder | 11 | 6-9 (71 total) | 3 | 3 | **639** |
| Configured run | 11 | 5 (h05-h25) | 3 | 1 | **165** |

The 639 needs the density axis as well as the stage axis -- `71 x 3 = 213`, not 639.
The configured run is what `config/` produces today: `[forest] max_height = 25` and an
empty `[export] density_variants`, for the cost reasons in the height-LOD section
below. All 165 exist as USD in `data/output/forest/`; the `/ 639` column in the table
below is kept against the standing target so historical rows stay comparable.

Per-asset admission checklist (all required to count):
- Nanite assembly imports cleanly (Gate 2)
- PVE preset wired into the Procedural Vegetation graph
- DynamicWind present (inline `unreal:dynamicWind:*` or sidecar fallback)
- Materials resolve under `db_path` (not pink/default)
- `DT_TreeCatalog` row present with species/height/DBH/cycle metadata

| Date | Assets admitted | / 639 | Species x stages x radii covered | Notes |
|---|---|---|---|---|
| 2026-08-07 | **9** | 1.4% | `silver_fir`, `european_beech`, `common_ash` x h05/h10/h15 x r00 only | Superseded by the audit below — the count was wrong. |
| 2026-08-13 | **0 admitted** (13 present) | 0% | — | First real admission audit, run against XRLabDB over Remote Execution. **13 assemblies present** — 11 in `/Game/Assets/TheGrove` (`common_ash` x3, `european_beech` x3, `silver_fir` x3, **`norway_spruce` x2** outside the pilot) and 2 in `/Game/Assets/TheGrove_dec25` (`silver_fir` h05/h10 at the decimated prototype). **Not 9, as previously recorded.** But **0 of 13 pass the checklist** — see the audit below. All predate round 3, so densities are stale too. XRFF-322. |
| 2026-08-13 (later) | **9** — 4 of 5 items verified, PVE failing | 1.4% | `common_ash`, `european_beech`, `silver_fir` x h05/h10/h15 x r00 | **First time four of the five items have ever passed.** Round-3 densities re-imported to a new path `/Game/Assets/TheGrove_r3`, leaving `TheGrove` and `_dec25` intact. Nanite, materials, DynamicWind and `DT_TreeCatalog` row all **9/9 verified**. PVE graphs were created but left **empty** — the wiring never ran. XRFF-322, XRFF-330. |
| 2026-08-13 (after XRFF-330) | **9** — 5 of 5 items verified | 1.4% | `common_ash`, `european_beech`, `silver_fir` x h05/h10/h15 x r00 | **First time the full checklist has ever passed.** The graph builder was fixed and re-run against XRLabDB: 3/3 `ProceduralVegetation` graphs wired, 28 nodes each (1 Preset Loader + 3 variant chains x 9), every edge verified connected. XRFF-330. |

### Admission audit — 2026-08-13, XRLabDB, all 13 present assemblies

| Checklist item | Result |
|---|---|
| Nanite assembly imports cleanly | **13 / 13 pass** — all present, `nanite_settings.enabled = True` |
| Materials resolve under `db_path` | **13 / 13 pass** — 2 slots each, zero `/Engine/` or `DefaultMaterial` fallbacks |
| DynamicWind present | **0 / 13** — `get_asset_user_data_of_class(DynamicWindSkeletalData)` returns `None` on every one |
| PVE preset wired | **0 / 13** — zero `ProceduralVegetationPreset` assets exist anywhere under `/Game` |
| `DT_TreeCatalog` row | **0 / 13** — the table exists at `/Game/Templates` with the correct `ST_TreeCatalogEntry` row struct, but **0 rows** |

**None of the three failures is a missing-plugin artifact.** Both plugins are loaded and
their classes resolve: `/Script/DynamicWind.DynamicWindSkeletalData` and
`/Script/DynamicWind.DynamicWindData` both load, and `unreal.ProceduralVegetationPreset`,
`ProceduralVegetationGraph` and `ProceduralVegetationFactory` are all present.
`/Game/Templates` even holds a `Wind_TransformProvider` DynamicWindData asset. The
infrastructure is in place; the post-import steps simply never landed on these assets.

**Three independent faults, each of which alone would have left the checklist failing.**

**1. Wind went to the wrong path (commit `e87e35e`, XRFF-328).** The wind and PVE scripts
take their search root from `unreal_pve_import_base`, while the assembly import uses
`unreal_project_path` — two config keys for one concept, whose defaults did not even agree
(`/Game/GrowPy` vs `/Game/Assets/TheGrove`), and no config file in the repo ever set the
former. The pilot config points `project_path` at `TheGrove_dec25`, so assemblies imported
there while wind searched `TheGrove`. Nothing warned. `pve_import_base` now defaults to
empty and resolves to `project_path`.

**2. PVE was switched off.** The pilot config carried `generate_pve_presets = false`, which
sets `skip_pve_json = True` (`generate_forest.py:470`), so no PVE preset or graph script was
generated at all and no per-tree recipe was written. Enabled 2026-08-13.

**3. PVE recipe generation was broken anyway (commit `646e8f5`, XRFF-329).** With the flag
on, `generate_pve_from_grove()` raised `too many values to unpack (expected 3)` on **every
tree**, and `write_pve_json()` swallowed it into a warning. `TwigPlacement.orientation` is
Grove's twig frame quaternion — four floats, `(w, x, y, z)` scalar-first — and the extractor
passed it to a helper that unpacks three, under a stale comment calling it an `(x, y, z)` up
vector. **This is the same Grove-orientation-is-a-quaternion mismatch already fixed once on
the twig-placement side; it has now bitten twice.** Fixed with `quaternion_to_pve_up()`,
which rotates local +Z using the same formulation as `_quat_forward`.

Fault 2 masked fault 3: while PVE was off, the broken code was never reached, so enabling
the flag alone would have produced warnings and still no presets.

**The catalog step, by contrast, works** — it had simply never been run. Executing
`import_batch_100_datatable.py` against `TheGrove_dec25` found its 2 assemblies, parsed
their metadata, duplicated the Templates table and populated 2 rows, first try.

### Round-3 re-import and re-audit — 2026-08-13, `/Game/Assets/TheGrove_r3`

All 9 pilot assemblies re-imported at round-3 densities to a **new** path, per operational
hazard #8. Post-import steps then ran in order: materials, consolidate, catalog, wind, PVE
presets, PVE graphs.

| Checklist item | Result |
|---|---|
| Nanite assembly imports cleanly | **9 / 9 verified** |
| Materials resolve under `db_path` | **9 / 9 verified** — 2 slots each, zero `/Engine/` fallbacks |
| DynamicWind present | **9 / 9 verified** — `get_asset_user_data_of_class` returns data, 3 simulation groups each |
| `DT_TreeCatalog` row | **9 / 9 verified** — `TheGrove_r3/DT_TreeCatalog`, 9 rows, keyed by assembly name |
| PVE preset wired into the graph | **0 / 9 as run** — the graphs were created empty; **9 / 9 after the XRFF-330 fix and re-run**, see below |

**The PVE item fails; it is no longer merely unproven.** 15 PVE assets were
created (9 per-tree presets, 3 per-species presets, 3 `ProceduralVegetation`
graphs), but the graph builder aborted before adding a single node on UE 5.7.4:

```
[PVE-G] get graph property failed: Property 'Graph' for attribute 'graph' on
        'ProceduralVegetation' is protected and cannot be read
[PVE-G] GetGraph call failed: Failed to find function 'GetGraph' on 'ProceduralVegetation'
[PVE-G] Could not obtain inner graph for PVG_Common_Ash_R00
```

Reading the plugin source settles it without opening the editor.
`ProceduralVegetationFactory` always calls `UProceduralVegetation::CreateGraph()`,
which creates an **empty** `UProceduralVegetationGraph` subobject; nothing else
in the plugin adds nodes to it (`CreateGraphFromPreset`, which would, is dead
code in 5.7 — no caller). The builder is the only thing that was going to wire
them, and it never got a handle. So all three graphs hold zero nodes.

**Three separate defects sat behind that one line** (XRFF-330, fixed):

1. **The accessor.** `Graph` is a bare `UPROPERTY()` — no `EditAnywhere`, no
   `BlueprintReadOnly` — so `PropertyAccessUtil` refuses the read, and
   `GetGraph()` is plain C++, never a `UFUNCTION`, so it was never callable
   from Python in any version. The graph is reachable as a named subobject:
   `unreal.find_object(pv_asset, "ProceduralVegetationGraph")`.
2. **A node class that does not exist.** The chain led with
   `PVCurveSettings`; the plugin ships `PVCarveSettings`. The `hasattr` guard
   quietly dropped the first node of every chain.
3. **The silence itself.** Remote Execution reports success unless the script
   raises, and the builder logged errors and then printed `Done.`. It now
   verifies every edge by reading the pin back (`AddEdge` returns its `To` node
   whether or not the edge was made) and raises on any failure.

The earlier claim that "none of the 15 PVE assets exposes any graph/variant
property through Python reflection at all" was **wrong**, and it is what made
this look unverifiable. `preset_variations`, the graph's `nodes`, node
`input_pins`/`output_pins`, and `PCGPin.is_connected()` are all readable — see
[pve-python-api.md](../reference/pve-python-api.md). PVE is auditable from a
script after all.

**Re-run after the fix, same day, same editor: 3/3 graphs wired.** Each
`PVG_*` now holds **28 nodes** — one Preset Loader plus 3 variant chains of 9
(`Carve → Gravity → Scale → RemoveBranches → MeshBuilder → BoneReduction →
FoliagePalette → FoliageDistributor → Output`) — with every edge read back as
connected, confirmed by an independent read-only probe. **All five checklist
items now pass on the 9 pilot assemblies.**

**Wind reported "9 applied, 9 failed out of 18".** The 9 failures are `douglas_fir`,
`norway_spruce` and `scots_pine` — species whose wind JSON is still on disk from the earlier
6-species run but whose assemblies were deliberately not imported into the pilot slice. Not a
defect; the step reports one failure per orphaned JSON.

**Consolidate is load-bearing for asset counts.** It took the project from 161 to 114 assets
by deduplicating the shared twig prototypes each assembly ships with. Any count taken before
consolidate runs will overstate.

Conifer height-LOD ladder is **on the critical path**, not an optimization: without it, 4 of
11 species (those reaching 35-45 m) are structurally incapable of reaching their upper height
stages at all, so coverage has a hard ceiling around h16-h24 for those species regardless of
density tuning. Prioritize accordingly once the pilot slice's four gates pass.

---

## Round log

| Round | Config / code delta | G1 `crown_fill` range | G1 worst `blob_saturation` | G2 import | G3 worst expanded tris | G4 frame time | Verdict |
|---|---|---|---|---|---|---|---|
| 0 | baseline (working tree) | 0.008 – 0.381 (8 trees; ash h15 missing) | 0.252 (beech h15) | not run | 65.3 M (beech h15) | not run | baseline |
| 1 | dead-twig drop moved ahead of `densify`; `plateau_cycles` 5 → 25 | 0.008 – 0.553 (9 trees) | 0.685 (ash h15) | not run | 75.0 M (ash h15) | not run | **no Gate-1 change** |
| 2 | `silver_fir` 0.0078 → 0.025; `skeleton_length` 1.0 → 1.1, `skeleton_reduce` 0.333 → 0.36; `max_skeleton_joints` 1000 → 250 | 0.026 – 0.552 | 0.690 (ash h15) | not run | 122.4 M (fir h15) | not run | **2 of 9 in band; joint limit cleared** |
| 3 | `european_beech` 0.138 → 0.095; `common_ash` 0.800 → 0.15 (`silver_fir` untouched) | 0.026 – 0.351 | 0.211 (ash h15) | not run | 122.4 M (fir h15, unchanged) | not run | **4 of 9 numerically in band; blind critic flags the metric alone as unreliable — see detail** |

### Round 3 detail — first round with an independent critic pass, and it overruled the builder's numeric pick

Only `european_beech` and `common_ash` per-species `twig_density` changed (pilot config only,
`data/tmp/pilot_config/forest.toml`); `silver_fir` and all skeleton/quality parameters are
untouched from round 2. Builder ran a 4-point bracket search per species (all 3 stages, r00),
picked the candidate whose h15 `crown_fill` landed safely inside 0.20–0.35 by the numbers
alone. Before accepting that pick, a **fresh critic reviewed the contact sheets blind** —
shuffled, unlabelled, no knowledge of which candidate was which — and independently ranked
every candidate per species per stage. The critic's rankings **did not match the builder's
numeric optimum**:

| Species | Builder's numeric pick | Critic's independent verdict on that pick | Critic's actual preference |
|---|---|---|---|
| `common_ash` | 0.10 (h15 fill 0.281, "safely inside") | **worst of 4** at h10, still "too sparse" at h15 despite being in-band | 0.40 for h10, 0.15 for h15 — no single value serves both |
| `european_beech` | 0.085 (h15 fill 0.295, "best-balanced") | 3rd of 4 at h10 ("too sparse"), 2nd of 4 at h15 (near-tied, loses) | 0.095 at both stages |

**The gap this exposes: `crown_fill` landing inside the 0.20–0.35 band does not guarantee the
tree looks right.** The builder's search only checked whether h15's number cleared the floor
by margin (avoiding the "too close to the edge" trap flagged in rounds prior); it did not
catch that the *chosen* value still read as visibly bald at h10, nor that `blob_saturation`-style
collapse at the high end can dominate the critic's judgment even when `crown_fill` itself isn't
extreme. This is the same class of finding as round 0's `blob_largest_cc` retirement — a single
scalar metric misses information a human/critic visual pass catches — now shown to apply to
`crown_fill` itself, not just the metrics already known to be unreliable. **Every future
per-species density round must run a blind critic pass on shuffled contact sheets before a
candidate is finalized, not just check the number against the band.**

Final values were revised to the critic's preference where an already-generated candidate
matched it: `european_beech` 0.085 → **0.095**, `common_ash` 0.10 → **0.15**. No new
generation was needed — both were already bracket-search candidates with full metrics and
contact sheets on disk. Rationale is recorded per-species in
`data/tmp/pilot_config/forest.toml`.

| Tree | `crown_fill` R2 → R3 | band | `blob_sat` R2 → R3 |
|---|---|---|---|
| `silver_fir` h05 | 0.026 → 0.026 (unchanged) | low | 0.007 → 0.007 |
| `silver_fir` h10 | 0.117 → 0.117 (unchanged) | low | 0.046 → 0.046 |
| `silver_fir` h15 | 0.221 → 0.221 (unchanged) | **IN** | 0.123 → 0.123 |
| `european_beech` h05 | 0.102 → 0.074 | low (known, XRFF-273) | 0.037 → 0.025 |
| `european_beech` h10 | 0.311 → 0.243 | **IN**, but critic still calls it visibly under-filled | 0.129 → 0.091 |
| `european_beech` h15 | 0.376 → 0.314 | **IN** | 0.257 → 0.182 |
| `common_ash` h05 | 0.127 → 0.028 | low, and worse than R2 (known tradeoff) | 0.033 → 0.008 |
| `common_ash` h10 | 0.366 → 0.120 | dropped from just-over-band to under-band | 0.214 → 0.041 |
| `common_ash` h15 | 0.552 → 0.351 | **borderline IN** (right at the 0.35 ceiling) | 0.690 → 0.211 |

Numerically in-band count: 2 of 9 (round 2) → **4 of 9** (round 3), plus `common_ash` h15
sitting exactly on the ceiling. `common_ash`'s worst-case `blob_saturation` fell from 0.690 to
0.211 — the extreme blob-collapse that dominated round 2's ash h15 is gone. But per the critic
finding above, **band membership is necessary, not sufficient** — `european_beech` h10 is
numerically in-band yet was independently judged too sparse, so this round's "4 of 9" is a
softer win than round 2's "2 of 9" was.

**Not this round's job (XRFF-273, unresolved, restated):** `common_ash` h05/h10 and
`european_beech` h05 all got worse in the sparse direction as a side effect of fixing h15 —
the same opposite-sign-across-stages problem already on file. `common_ash`'s `crown_fill`
response to density is confirmed highly nonlinear/saturating (halving density 0.800→0.40 barely
moved h15 fill), unlike `european_beech`'s roughly monotonic response — worth remembering before
assuming a bracket search will behave the same way across species.

**Catalog coverage impact:** none yet. No UE import ran this round (Gate 1 needs no UE), so
the 9 assemblies in `/Game/Assets/TheGrove` still reflect round-2 density, now doubly stale —
neither round 2's nor round 3's per-species values have been re-imported. Re-import (to a new
path, per operational hazard #8) is needed before the catalog-coverage table can be updated
past the 2026-08-07 baseline row.

`data/output/forest/` was regenerated for `european_beech` and `common_ash` at the final,
critic-corrected round-3 values (0.095 / 0.15) and re-verified with `growpy-icon-metrics`
directly against the exported files (not just the pilot-config comment): both match the logged
numbers exactly (beech 0.074/0.243/0.314, ash 0.028/0.120/0.351 at h05/h10/h15). So the on-disk
assemblies are ready to import whenever a clean, isolated import is possible. Two things must
happen first, neither done yet:

**D7 — a real UE import attempt this round was aborted, not completed, for two independent
reasons, both worth recording so a later session doesn't re-walk into them:**

1. **The editor's state changed unexpectedly between two checks a few minutes apart, with no
   action from this session.** First check: `UnrealEditor.exe` PID 28012, started 18:10:09,
   remote-exec port 6776 (not 6766 as this doc's own resume instructions stated — verified,
   corrected here) reachable. Second check, ~3 minutes later, after two unrelated background
   `conda run` exports finished: PID 28012 gone, a **different** PID 36996 running instead
   (started 18:41:34, i.e. after the first check), port 6776 unreachable, process not
   responding. Nothing in this session restarted UE. Per the operational hazard on exclusive
   discovery-socket access ("contention fails in a way that looks identical to editor not
   running"), this is exactly that failure signature, and the safe response is to not attempt
   any import against an editor whose state can't currently be verified -- not to relaunch,
   reconnect, or otherwise push through the ambiguity. No import was attempted. Re-verify
   editor state fresh before the next attempt; do not assume 36996 (or whatever PID exists by
   then) is safe to drive without re-checking the port.
2. **`data/output/forest/unreal_scripts/` is not a clean pilot-slice — it is contaminated with
   unrelated species from some other run.** Independent of the editor issue: this directory
   currently also contains `douglas_fir`, `norway_spruce`, `scots_pine` (not part of the
   3-species pilot slice) alongside the pilot species, and the generated `import_batch_*.py`
   numbering has visibly shifted between the two just-run per-species regenerations (e.g. a
   stale `import_batch_02_european_beech_done.txt` marker sits next to a freshly generated
   `import_batch_03_european_beech.py` -- the done-tracking and the current scripts disagree on
   numbering). Running `growpy-ue-exec` against this directory as-is would import unknown-
   provenance species alongside the pilot trees, and the mismatched `_done.txt` files risk
   silently skipping or misordering batches. This is the same class of mistake as the
   `small_leaved_linden` stale-file lesson already on record, now hitting the *import* side
   rather than the measurement side. **Before any real Gate-2/coverage import: isolate just the
   pilot-slice batches** (`import_batch_00_instances`, `..._common_ash`, `..._european_beech`,
   `..._silver_fir`) from the extraneous ones, and regenerate or manually reconcile the
   `_done.txt` markers rather than trusting the directory as found.

**D9 — this machine had 20+ leftover Python processes running from earlier the same day
(clusters at 10:24 AM and 17:46-17:49) before this session's own work started**, discovered
while investigating why a background `silver_fir` h30 generation (`--steps 4 --max-height 30`,
otherwise identical to the h25 command that worked cleanly minutes earlier) was killed
externally twice in a row, both times with zero streamed output and zero files written despite
`--no-capture-output`. Not root-caused this session and no process was killed to test it, but
this is a plausible common cause for **both** oddities observed this session: the UE editor's
unexplained process churn (D7) and the h30 kills — resource pressure from accumulated stale
processes, not a problem with the generation command itself (h25 used the identical pattern and
completed cleanly). **Do not retry h30/h35 generation blind** in a future session without first
checking for and clearing stale processes; the twig/stem numbers this session already has
(h05-h25, real, measured) remain valid regardless of this.

### Round 2 detail (composed run — both builders' changes together)

Re-run as a single 9-tree slice rather than trusting the two builders' concurrent partial
runs, because `[quality.high]` skeleton parameters apply to **every** species and the
density builder's silver fir runs may have straddled the skeleton change. Composed result
confirms both: skeleton reduction cost almost no crown fill (ash h10 0.374 → 0.366, beech
h15 0.381 → 0.376).

| Tree | `crown_fill` R1 → R2 | band | `blob_sat` | instances | expanded tris | joints R1 → R2 |
|---|---|---|---|---|---|---|
| `silver_fir` h05 | 0.008 → **0.026** | low | 0.007 | 94 | 10.1 M | 125 → 97 |
| `silver_fir` h10 | 0.042 → **0.117** | low | 0.046 | 462 | 49.8 M | 153 → 87 |
| `silver_fir` h15 | 0.088 → **0.221** | **IN** | 0.123 | 1 135 | **122.4 M** | 174 → 111 |
| `european_beech` h05 | 0.101 → 0.102 | low | 0.037 | 567 | 7.0 M | 83 → 59 |
| `european_beech` h10 | 0.313 → 0.311 | **IN** | 0.129 | 3 048 | 38.6 M | 190 → 142 |
| `european_beech` h15 | 0.381 → 0.376 | high | 0.257 | 5 144 | 65.0 M | 263 → **197** |
| `common_ash` h05 | 0.127 → 0.127 | low | 0.033 | 794 | 3.2 M | 92 → 73 |
| `common_ash` h10 | 0.374 → 0.366 | high | 0.214 | 4 525 | 18.4 M | 219 → 145 |
| `common_ash` h15 | 0.553 → 0.552 | high | 0.690 | 19 066 | 75.0 M | 288 → **216** |

**D4 — DOWNGRADED 2026-08-07 by project owner. 256 is not a hard limit.**

> "the skeletal joints limit is not a hard limit but a suggestion. ue can deal with way
> more. i just have it in place to stop the models from creating excessively detailed
> skeletons."

`max_skeleton_joints` is a **deliberate detail budget**, not an engine correctness
boundary. UE handles far more than 256 joints. Therefore:

- Ash h15 at 288 joints and beech h15 at 263 were **never import-blocking**. The working
  tree's `max_skeleton_joints = 1000` already accommodated them.
- The round-2 skeleton reduction (`skeleton_length` 1.0 → 1.1, `skeleton_reduce`
  0.333 → 0.36) solved a non-problem and cost some wind fidelity at branch tips and on the
  thinnest twigs. It is aligned with the owner's stated intent (leaner skeletons) but was
  not required. Reverting is one line in each of `forest.toml` / `quality.toml`.
- **The perf critic's "unsafe — hard-limit violation" verdict is void.** It was graded
  against a false premise supplied in its brief by the lead agent, taken from the
  `forest.toml` comment below. A critic can only be as right as its brief.

**D5 — `max_skeleton_joints` is warning-only, and that is BY DESIGN.** Its sole consumer is
`io/usd/assembly_export.py:1242-1255`, which logs a warning and returns — no clamp, no
decimation, nowhere in `src/`. Given D4, warning-only is the correct behaviour for a detail
budget. What is wrong is only the comment's framing:

```
# Nanite encodes bone indices in 8-bit fields (max 256).
# 250 = safe default for Nanite Assembly USD import path.
```

This reads as an engine constraint and an enforced clamp. It is neither. **Correct the
comment at the integration pass** to say it is an advisory detail budget that emits a
warning, so nobody again mistakes a style preference for a crash risk — as this loop did.

**Scale-out risk the pilot structurally cannot see.** The skeleton fix buys headroom at
15 m but does not flatten the growth curve: ash's h10→h15 joint increment is +69 before and
+71 after. Douglas fir reaches ~45 m and Norway spruce / silver fir ~35 m in this dataset.
Those species will re-breach 256 at stages above h15, and `--max-height 15` means no pilot
round can detect it. Joint counts must be re-checked when height stages are extended.

### Ceilings after round 2 (ratcheted — best achieved that did not regress another gate)

| Gate | Ceiling | Set by |
|---|---|---|
| 3 — expanded triangles | **122.4 M** per assembly, **real-import-confirmed (D8 resolved 2026-08-13)** | `silver_fir` h15, round 2: 1,135 instances x 107,876 faces = 122,439,260. Verified in XRLabDB — the h15 assembly's `SK_pacific_silver_fir_foliage` carries **108,665 verts**, matching the 107,876-face prototype, imported 16:02:41. Historical: 147 M imported cleanly, 2.45 B crashed. |
| 3 — skeleton joints | **advisory only**, not a gate (see D4) | owner: "not a hard limit but a suggestion" |
| 1 — `blob_saturation` | **0.690 is a FAIL**, not a ceiling | `common_ash` h15; passing trees measure 0.123–0.257 |
| 2 — import wall-clock | **3 671.8 s** per batch | `silver_fir` (one asset built) |
| 2 — import peak RAM | **85.1%** | `silver_fir` h15 |
| 2 — import peak VRAM | **21.2%** | `silver_fir` h15 |
| 4 — frame time | not yet measured | — |

### Gate 2 — measured 2026-08-07, XRLabDB / UE 5.7.4

| batch | duration | peak RAM | peak VRAM | restarts | crashes | result |
|---|---|---|---|---|---|---|
| `import_batch_00_instances` | 3.9 s | 53.3% | 11.2% | 0 | 0 | 3/3 OK |
| `import_batch_01_common_ash` | 3.9 s | 53.5% | 13.1% | 0 | 0 | 3/3 OK |
| `import_batch_02_european_beech` | 4.1 s | 53.5% | 13.1% | 0 | 0 | 3/3 OK |
| `import_batch_03_silver_fir` | **3 671.8 s** | **85.1%** | 21.2% | 0 | 0 | 3/3 OK |

All 9 assemblies present in `/Game/Assets/TheGrove`. Zero crashes, zero OOM, zero
watchdog restarts (watchdog disabled — see below).

**SUPERSEDED 2026-08-13 for the broadleaf rows — the 3.9 / 4.1 s figures do not survive a
cold import.** Re-importing the same batches into a fresh path (`TheGrove_r3`, XRFF-322)
measured:

| batch | 2026-08-07 recorded | 2026-08-14 measured (cold, empty path) | error |
|---|---|---|---|
| `import_batch_00_instances` (3 twig prototypes) | 3.9 s | **27.8 s** | 7x |
| `common_ash` (3 trees) | 3.9 s | **372.6 s** (6.2 min) | 96x |
| `european_beech` (3 trees) | 4.1 s | **1 797.4 s** (30.0 min) | 438x |
| `silver_fir` (3 trees) | 3 671.8 s | **5 031.4 s** (83.9 min) | 1.4x |
| **total** | 3 683.7 s (61.4 min) | **7 229.2 s (120.5 min)** | 2.0x |

Per asset, all `outcome=imported`, **0 skipped and 0 failed across all 12**:

| stage | `common_ash` | `european_beech` | `silver_fir` |
|---|---|---|---|
| h05 | 10.0 s | 30.7 s | 27.1 s |
| h10 | 22.1 s | 392.5 s | 524.9 s |
| h15 | **340.5 s** | **1 374.2 s** | **4 479.4 s** (74.7 min) |

**"The broadleaves are free by comparison" is dead.** It was wrong by 96x on ash and 438x
on beech. A single `european_beech` h15 costs 22.9 minutes -- the same cost class as the
conifer asset this whole line of work was built around. The 2026-08-07 broadleaf rows timed
a *skip*, not a build.

Instances batch, per prototype: `european_beech_twigs` 14.3 s, `one_leaved_ash_twigs` 6.9 s,
`pacific_silver_fir_twigs` 6.6 s. Every number in this section is recorded inline on purpose
-- the raw record lands under `data/output/`, which is gitignored, so a file reference alone
would not survive the machine.

Method, for reproducibility: batch scripts regenerated with the per-asset `[ASSET]`
instrumentation (XRFF-323) and pointed at a **new empty path** `/Game/Assets/TheGrove_r4_cold`;
four stale `*_done.txt` resume files archived first (leaving them would have skipped every
asset -- the exact failure being corrected); editor restarted for a cold baseline (53% RAM
with the project loaded, vs 75.6% after a long session).

### Cost scales with height, steeply -- that is the real finding

Log-log fit of `cost(h) = a * h^k` on the three measured stages per species:

| species | k | h05 -> h15 growth |
|---|---|---|
| `common_ash` | 2.99 | 34x |
| `european_beech` | 3.48 | 45x |
| `silver_fir` | **4.61** | **165x** |

Conifers scale worst, and every stage above h15 is unmeasured. Two projections, and the
distance between them is the point:

* **Mostly-measured floor** -- h05/h10/h15 only, which is 33 of the 71 stages (297 of 639
  models, 46%), using the measured per-species totals: **69.3 h = 2.9 days** of continuous
  import.
* **Full 639 extrapolated** -- same fits carried to each species' `Max Height`: **~5 800 h
  = ~242 days**. `douglas_fir` alone is 59% of it, because it runs to h45 on the conifer
  exponent.

**Do not plan against the 242-day figure.** It extrapolates a 3-point fit three times past
its fitted range; `(45/15)^4.61` is a factor of 152. Its value is only as an
order-of-magnitude signal: on the current import path the 639-model target is not
reachable, and the gap is not close. The floor is the number to trust, and it already
costs ~3 days for the *cheapest* 46% of the catalog.

If the conifer exponent holds, per-asset cost runs 4.7 h at h20, 13.1 h at h25, 30.4 h at
h30 and 61.8 h at h35. **A single h20 or h25 import measurement would collapse most of this
uncertainty** -- it is the highest-value next measurement, and XRFF-324 needs it too.

Tracked in XRFF-323.



**D6 — `silver_fir` h15 cannot be imported with the default watchdog.** That single
asset (122.4 M expanded triangles, 1 135 instances of a 107 876-face prototype) takes
**61 minutes** to build and peaks at **85.1% system RAM on a 63.5 GB machine**. The
`growpy-ue-exec` watchdog default is `--restart-ram-limit 82`, i.e. **below the peak this
asset requires**. The result is an unbreakable loop: RAM crosses 82% → watchdog kills UE →
relaunches → retries the same asset → crosses 82% again. It never completes and never
reports a failure.

Confirmed by contrast: the same batch with `--restart-ram-limit 0` completed cleanly in
61 minutes with no restarts. Every other batch in the slice finishes in under 5 seconds.

Options, none yet chosen:
- raise `--restart-ram-limit` above ~87% for datasets containing conifer h15 assets
- reduce `silver_fir` density (Gate 1 regression — it is only just in band at 0.221)
- accept that the heaviest conifer assets need a watchdog-off import pass

**Wall-clock implication for scale-out:** superseded by the cold re-measure above. h15 is
74.7 minutes for `silver_fir`, and the broadleaves are **not** free -- `european_beech` h15
is 22.9 minutes. See "Cost scales with height, steeply" above for the current numbers and
projections.

**Operational note — `conda run` buffers stdout.** `conda run <cmd>` captures output and
releases it only on process exit; it needs `--no-capture-output` to stream. During this
session that made three long-running imports appear to produce no output at all, which
was misread as a stall on each occasion and led to the runs being killed. A killed
`conda run` discards the buffer, so the probe's measurements were destroyed along with
the process. **Always pass `--no-capture-output` for long imports.**

Ceilings are never loosened to make a round pass.

### Conifer twig cost is fixed, not a defect (owner, 2026-08-07)

> "the prototype simply is bigger because of the needles. nothing to be done about that."

The Pacific silver fir spray is 107,876 faces because it is needles — the silhouette *is*
the geometry, so there is no subdivision or simplification that keeps the look. Three
species share it (`silver_fir`, `norway_spruce`, `douglas_fir`).

This **retires the "smaller twig asset" idea for conifers**, which both XRFF-273 and this
loop's round-2 analysis had proposed as the durable fix. It is not available. Conifer
foliage costs ~108 K triangles per instance, full stop, and the correct response is to
**budget for it** rather than engineer around it:

- `silver_fir` h15 at `crown_fill` 0.221 costs 122.4 M expanded triangles (1,135 instances).
- Reaching mid-band (~0.30) would need ~1,600 instances ≈ 172 M.
- This is a **cost**, not a conflict to resolve. Whether 172 M is affordable is a Gate-2/4
  question that only a real import and frame-time measurement can answer — not something
  to be assumed from the 147 M historical reference, which came from an unknown scene
  composition (flagged by the perf critic as an untrustworthy comparison).

### Round 1 detail

`plateau_cycles = 25` recovered the `common_ash` h15 stage that round 0 never generated
(3 of 3 milestones for all three species). The dead-twig reorder changed **nothing** — see
the D1 retraction above; all 8 trees shared with round 0 measured byte-identical.

| Tree | `crown_fill` | Δ vs R0 | `blob_saturation` | `blob_largest_cc` | instances | expanded tris | joints |
|---|---|---|---|---|---|---|---|
| `silver_fir` h05 d09 | 0.008 | = | 0.007 | 0.053 | 30 | 3.24 M | 125 |
| `silver_fir` h10 d12 | 0.042 | = | 0.019 | 0.021 | 145 | 15.64 M | 153 |
| `silver_fir` h15 d18 | 0.088 | = | 0.041 | 0.024 | 354 | 38.19 M | 174 |
| `european_beech` h05 d07 | 0.101 | = | 0.040 | 0.050 | 570 | 7.05 M | 83 |
| `european_beech` h10 d18 | 0.313 | = | 0.128 | 0.437 | 3 048 | 38.57 M | 190 |
| `european_beech` h15 d27 | 0.381 | = | 0.252 | 0.804 | 5 165 | 65.27 M | **263** |
| `common_ash` h05 d09 | 0.127 | = | 0.033 | 0.046 | 794 | 3.24 M | 92 |
| `common_ash` h10 d16 | 0.374 | = | 0.207 | 0.835 | 4 554 | 18.50 M | 219 |
| `common_ash` h15 d32 | **0.553** | new | **0.685** | 0.991 | 19 059 | 74.98 M | **288** |

**D4 — two assets exceed Nanite's 256-joint hard limit.** `common_ash` h15 has 288 joints
and `european_beech` h15 has 263. Nanite encodes bone indices in 8-bit fields, and
`[export] max_skeleton_joints = 1000` in the working tree does not clamp them (the key's
own comment states 250 is the safe Nanite-Assembly value). This is an import-crash
candidate with **no connection to crown density** and must be ruled out before any Gate-2
failure is attributed to foliage.

**The actual Gate-1 problem, restated after the D1 retraction.** `crown_fill` spans **69x**
across the slice (0.008 – 0.553) and the required correction has **opposite signs** by
species *and* by stage:

| | needs |
|---|---|
| `silver_fir` h05 / h10 / h15 (0.008 / 0.042 / 0.088) | **up**, 3–25x |
| `european_beech` h05 (0.101), `common_ash` h05 (0.127) | up |
| `european_beech` h10 (0.313) | in band |
| `common_ash` h10 (0.374), `european_beech` h15 (0.381) | down |
| `common_ash` h15 (0.553) | **down**, hardest |

No single static per-species constant can produce corrections of opposite sign at
different stages of the same species. This is the case XRFF-273's per-tree resolver exists
for, and it is already scoped there (fallback chain, wild_cherry override,
`Σ(instances × leaf_area_per_prototype)` target).

---

## Conifer height-LOD ladder — first design pass (2026-08-07)

**This is on the critical path, not an optimization.** 4 of 11 species reach 35–45 m and are
structurally incapable of getting there without it, regardless of any further density tuning.

**RETRACTION, same session:** the first version of this section built a twig-decimation ladder
on top of a 107,876-face "full" prototype baseline, per this session's own resume-protocol
carried-forward notes and this doc's own round-2 log (`silver_fir` h15, 1,135 instances,
122.4 M expanded triangles = 1,135 x 107,876). **That baseline no longer matches what is on
disk.** Measured with `growpy-analyze-usda --triangle-budget` against the actual files:

```
silver_fir h15 (same 1,135 instances as round 2): 30,609,815 expanded triangles
Prototype pacificsilverfirf: 1,135 instances x 26,969 faces (sidecar-reported)
```

26,969 is the round-2 0.25-decimation candidate face count. The live twig asset
(`data/assets/twigs/pacific_silver_fir_twig/`, gitignored, not in version control) is the
decimated prototype — filesystem mtime 2026-08-07 16:38-16:39.

### D8 — RESOLVED 2026-08-13, in favour of the recorded ceiling

The open question was whether round 2's recorded Gate-2 import (3,671.8 s, 85.1% peak RAM,
"3/3 OK") ran against the 107,876-face or the 26,969-face prototype. **It ran against the
107,876-face one.** Confirmed by direct inventory of XRLabDB over Remote Execution — the
assemblies carry their twig prototype as a child `SkeletalMesh`, so its size is readable
per-assembly, and `.uasset` mtimes date each import:

| Asset | Prototype verts | Imported |
|---|---|---|
| `TheGrove/silver_fir/.../Silver_Fir_r00_h15m_d18cm_full_assembly` | **108,665** | 16:02:41 |
| `TheGrove/silver_fir/...h05`, `...h10` | 108,665 | 12:52, 12:59 |
| `TheGrove/norway_spruce/...h05`, `...h10` | 108,665 | 16:28, 16:40 |
| `TheGrove_dec25/silver_fir/...h05`, `...h10` | **31,312** | 17:41, 17:48 |

The two clusters sit 3.47x apart and map cleanly onto the two face counts (108,665 verts to
107,876 faces, ratio 1.007; 31,312 to 26,969, ratio 1.161 — decimation raises the vert/face
ratio via UV seam splits). **1,135 x 107,876 = 122,439,260**, reproducing the recorded 122.4 M
exactly.

The timeline is now unambiguous and self-consistent: the h15 import completed at 16:02, the
twig asset was decimated on disk at 16:38-16:39, and `TheGrove_dec25` was imported afterwards
at 17:41-17:48 as a separate decimated-prototype trial. The `dec25` = "decimated at 0.25"
reading was correct, and it is a **later, different** target — not a collision with round 2's
import. It holds h05 and h10 only; **h15 was never imported at the decimated prototype.**

**Consequences:**
- The Gate-3 ceiling of 122.4 M is real-import-confirmed. Restored in the ceilings table.
- The 61-minute / 85.1%-RAM Gate-2 cost is the cost of the **full** prototype, so XRFF-323's
  scaling problem is real and not an artifact of mis-attributed prototype size.
- The combined-budget table below compares against a figure that is now trustworthy.
- `douglas_fir` shares this prototype, so the same reading applies to it.

Record the prototype face count alongside every future Gate-2 run so this cannot recur.

**Practical consequence, though: this is good news, not bad.** Whatever the history, the
*currently deployed* prototype is the smaller one, and it is already real-data-measured across
five height stages this session (not fitted/projected):

### Twig side — now measured directly at 5 real stages, not fitted

Generated for real this session (`--species "Silver Fir" --steps 4 --max-height 25`, pilot
config, r00, density 0.025 unchanged from round 2) and read back with
`growpy-analyze-usda --triangle-budget`:

| Height | Twig instances | Prototype faces (current, live) | Expanded triangles | Leaf area (sanity only) |
|---|---|---|---|---|
| h05 | 94 | 26,969 | 2.5 M | 10.2 m² |
| h10 | 462 | 26,969 | 12.5 M | 50.1 m² |
| h15 | 1,135 | 26,969 | 30.6 M | 123.1 m² |
| h20 | 2,293 | 26,969 | 61.8 M | 248.6 m² |
| h25 | 4,136 | 26,969 | 111.5 M | 448.4 m² |

All five are real measurements, not fits. Instance counts are noticeably higher than the
`N(h) = 2.44 . h^2.271` curve this session's resume notes carried forward (h20 measured 2,293
vs fit's 2,198, +4%; h25 measured 4,136 vs fit's 3,645, +13.5%) — the fit under-predicts more
as height grows past its h05-h15 fitting range, so treat that formula as a rough guide only
beyond h15, not a number to plan a ceiling around. **Re-fit this session on all 5 real points**
(log-log least squares, `silver_fir`, r00, density 0.025): `N(h) = 2.155 . h^2.332`, errors
-2%/+0.3%/+5%/+1.6%/-5.2% at h05/h10/h15/h20/h25 respectively — tighter and more even than the
old fit at every point, use this one instead if extrapolating past h25 until a real h30/h35
measurement exists. **Against the 122.4 M ceiling — now real-import-confirmed (D8 resolved) —
h25's twig-only 111.5 M sits under it** with real, current-prototype numbers, so twig-only cost
at h25 is not obviously a problem. h30/h35 need their own real
generation-and-measure pass before claiming anything; do not extrapolate the instance-count
fit that far given the h25 miss above.

### Stem side — now a real, measured triangle count, not file size or a fit

`growpy-analyze-usda --triangle-budget` previously reported twig triangles only. Added a small
extension this session (~15 lines, reuses the existing `_count_mesh_faces_pxr` helper already
used for twig prototypes, applied to the referenced stems USD instead) so it also opens each
`stems_ref` file as its own stage and sums `faceVertexCounts` across every Mesh prim. All 25
existing `test_analyze_usda.py` tests still pass unmodified. Real measured stem triangle counts
for the same five silver_fir trees:

| Height | Stem triangles (measured) | Prior fitted projection `S(h)` | Ratio (fit / real) |
|---|---|---|---|
| h05 | 462,024 | ~1.36 M | 2.9x over |
| h10 | 2,387,679 | ~7.58 M | 3.2x over |
| h15 | 7,110,507 | ~20.7 M | 2.9x over |
| h20 | 13,909,312 | ~42.0 M | 3.0x over |
| h25 | 25,408,355 | ~73.1 M | 2.9x over |

**The carried-forward `S(h) = 25,285 . h^2.476` stem-triangle fit over-predicts by a
consistent ~3x across every stage measured, including h15 — which was supposedly inside its own
fitted range**, not an extrapolation miss. Checked: neither this formula nor the twig
instance-count fit (`N(h) = 2.44 . h^2.271`) appears anywhere else in the repository — no
script, notebook, test, or other doc produces or references either one. Both arrived in this
session only via the resume-protocol's carried-forward notes, with no artifact on disk to trace
them back to. The instance-count fit at least reproduces measured h05/h10/h15 within 1-6% and
degrades gracefully at h25 (+13.5%, a plausible extrapolation miss) — consistent with being a
real fit that's just old. **The stem fit missing by a uniform ~3x at a point inside its own
claimed range is not what a real regression's extrapolation error looks like; it looks like the
formula (or the conditions it was fitted under) is simply wrong.** The hypothesis raised here
was that `[quality.high] build_cutoff_thickness` had been raised from 0.00125 to 0.0025 before
this session — doubling the thinnest-branch cutoff prunes a large fraction of a conifer's fine
branching and could plausibly cut stem triangle count by 2-3x on its own — so a stem fit
predating that change would explain the gap without the fit itself being wrong.

**Settled 2026-08-13:** the owner confirmed 0.0025 is the intended value (see "Starting config
state"), and it is now committed. So the fit is obsolete rather than wrong — it was fitted
under a cutoff the project no longer uses. **No revert experiment is needed; retire
`S(h) = 25,285 . h^2.476` and trust the measured column, not either fit.**

### Combined budget, real numbers — the picture is much better than feared

| Height | Twig triangles (measured) | Stem triangles (measured) | **Combined total** | vs the 122.4 M import-confirmed ceiling |
|---|---|---|---|---|
| h05 | 2.5 M | 0.46 M | 3.0 M | 4% |
| h10 | 12.5 M | 2.4 M | 14.9 M | 12% |
| h15 | 30.6 M | 7.1 M | 37.7 M | 31% |
| h20 | 61.8 M | 13.9 M | 75.7 M | 62% |
| h25 | 111.5 M | 25.4 M | 136.9 M | 112% |

Every number in this table is a real measurement from this session — no fits, no projections.
Combined cost at h25 (136.9 M) is only modestly above the 122.4 M reference, and that reference
is now confirmed to have really been imported (D8 resolved 2026-08-13 — it took 61 minutes at
85.1% peak RAM). **The practical read: on triangle budget alone, conifers reaching into the
h20-h25 range is realistic** — but note the cost of getting there is the 61-minute import, not
just the triangle count. The open question is no longer "is there a triangle-budget crisis,"
it's the wall-clock one tracked in XRFF-323.

### Second pass, 2026-08-14/15 -- round-3 densities, and h30 attempted for real

The twig/stem tables above are **round 2**, at `silver_fir = 0.025`. The live config is
**round 3, `silver_fir = 0.0078`** (`[export.twig_density_per_species]`), so those numbers
describe a tree 3.2x heavier than the pipeline now produces. Re-measured at live density
with `growpy-analyze-usda --triangle-budget`:

| radius | stage | twig inst | twig tris | stem tris | **combined** | of 122.4 M |
|---|---|---|---|---|---|---|
| r00 | h05 | 31 | 0.84 M | 0.47 M | 1.31 M | 1% |
| r00 | h10 | 160 | 4.3 M | 2.8 M | 7.1 M | 6% |
| r00 | h15 | 424 | 11.4 M | 8.4 M | 19.9 M | 16% |
| r00 | h20 | 793 | 21.4 M | 17.2 M | **38.5 M** | 31% |
| r00 | h25 | 1 328 | 35.8 M | 29.5 M | **65.3 M** | **53%** |
| r08 | h05/h10/h15 | 26 / 63 / 63 | | | 1.1 / 2.8 / 3.1 M | 1-3% |
| r16 | h05/h10/h15/h20 | 31 / 128 / 158 / 165 | | | 1.3 / 5.7 / 7.8 / 8.2 M | 1-7% |

Round-2 -> round-3 instance ratios are 3.03x / 2.89x / 2.68x / 2.89x / 3.11x at h05..h25,
matching the density change. **The h25 triangle-budget problem is gone**: 65.3 M against the
import-confirmed 122.4 M ceiling, where round 2 sat at 136.9 M (112%). Extrapolated, h30
lands near 86% -- still under.

**Triangles are no longer the ladder's constraint. Generation memory is.**

### h30: simulated, export failed on a MemoryError, run reported OK

First attempt to get past where two earlier ones died
(`--species "Silver Fir" --steps 4 --max-height 30`, sampled at 20 s):

Simulation **succeeded** -- 30.2 m at cycle 102, `[Grove Complete] all milestones captured`.
Export **failed**:

```
MemoryError
USD export failed:
  Type mismatch for </silver_fir_stems/silver_fir_stems_mesh.primvars:st>:
  expected 'VtArray<GfVec2f>', got 'vector<VtValue,allocator<VtValue> >'
  tree_export.py:432 in build_tree_mesh -> uv_primvar.Set(usd_uvs)
  Export failed for tree 1 (Silver fir) at cycle 102 (h=30.2m)
```

A `MemoryError` hits while building the UV array, `usd_uvs` is left as an untyped fallback
list, and `.Set()` is called on it anyway -- so USD reports a **type mismatch** and anyone
reading the last line chases a schema bug instead of memory. The pipeline then printed
`Step 4 [Silver Fir]: OK` and **exited 0**, leaving a **0-byte**
`silver_fir_h30m_d41cm_stems_skeletal.usdc`. The import scripts correctly omit it.

**The memory curve -- what the hazard never had:**

| point | host RAM | growpy RSS |
|---|---|---|
| baseline, editor closed first | 41.7% | -- |
| through h15/h20 | 59-60% | 13-14 GB |
| **h25 milestone (cycle 86)** | **70%** | **22 GB** |
| h30 reached (cycle 102) | 86% | 35 GB |
| **export peak** | **99%** | **48.7 GB** |

Per-cycle time tracks it: 2.89 s/cycle at c41, 5.75 at c70, 11.27 at c86.

**h30 needs ~49 GB.** The earlier attempts ran with the editor resident at ~34 GB on a
63.5 GB machine, leaving ~30 GB, so they died in the h25 -> h30 segment -- exactly where an
identical h25 command "completed cleanly" minutes before. **Do not generate h30+ with the
editor open.** Closing it first is what let this attempt reach h30 at all.

### The 2026-08-07 hazard note was wrong on all three counts

Recorded there: "killed externally twice, zero output and zero files written", blamed on
"resource pressure from accumulated stale processes".

| claim | status |
|---|---|
| stale Python processes caused it | **wrong** -- they are MCP servers (`unreal-engine-mcp`, `notebooklm-mcp`, `markitdown-mcp`), parent+child shim pairs from one client startup: ~214 MB and ~2 s CPU across six, over 18 h |
| zero output | **not evidence** -- `growpy-dataset-pipeline` prints nothing without `-v`; its progress is INFO and the root logger sits at WARNING |
| zero files written | **expected for any death before the export phase** -- USD export runs only after every grove finishes simulating |

Drop the pre-flight process sweep. The real precondition is **memory headroom**.

### Stage drops -- the ladder came out uneven

Export logged `Skipping Silver fir tree N (fid=M) at cycle C: model is None` at several
milestones, and the delivered ladder is ragged: r00 reached h25, **r08 stopped at h15**,
**r16 stopped at h20**. Undiagnosed. Read any "h20/h25 coverage" claim per radius, not per
species.

### Import timings are good to about +/-30%, not to the digit

The same `silver_fir` h15 asset measured **74.7 min** cold and **100.9 min** later the same
day; h10 moved 524.9 s -> 692.1 s. Treat the wall-clock projections above as
order-of-magnitude.

### What this design pass does NOT resolve

- ~~**D8** — which prototype size round 2's recorded Gate-2 import validated~~ — **resolved
  2026-08-13**: the 107,876-face one, confirmed by UE inventory. 122.4 M is real. See the D8
  section above.
- ~~The ~3x over-prediction in the old stem-triangle fit~~ — **resolved 2026-08-13**: the fit
  predates the committed `build_cutoff_thickness = 0.0025` and is retired, not re-fitted.
- ~~h30/h35 data for any metric~~ -- **partially resolved 2026-08-14**: h30 simulates and its
  memory cost is measured, but **no h30 asset exists** -- the export died on a `MemoryError`.
  h35 is untouched, and `silver_fir`'s allometry is fitted only to 30.85 m, so h35 would
  extrapolate DBH.
- Why the export failed beyond the `MemoryError` itself, and why a `MemoryError` is allowed to
  surface as a USD type mismatch rather than aborting the export.
- Why radii drop stages (`model is None`).
- ~~Whether `douglas_fir`'s ~45 m target is reachable~~ -- **DBH is not its limit**: its
  allometry covers **54.6 m**, the widest in the catalog. Generation memory is. The species
  with a real allometry ceiling is **`scots_pine` at 25.2 m**, and nothing guards the upper
  bound -- `allometry.correction_weight()` fades only *below* the fitted floor, so above the
  fitted range the power law is applied at full weight with no clamp and no warning.
- A real Gate-2 import at h20 or h25 -- **h05/h10/h15 done, h20/h25 in progress 2026-08-15.**

---

## Lessons that must not be relearned

- **Check for stale output files before back-solving from a measured run.** The
  `small_leaved_linden` density was wrong by ~14x because six files from an older
  0.5-density run survived under different DBH filenames and were averaged in. Verify the
  file set matches the run before trusting any aggregate.
- **Grove's own seed `twig_density` is inert** in the core API — 1.0 / 0.25 / 0.0 grow the
  same twig count. `[export] twig_density` (times the per-species table, times the CSV
  column) is the only working knob.
- **All twig instance scales are exactly 1.0.** Every twig is the same physical ~39x35 cm
  spray regardless of tree size or crown position. A crown can therefore be at correct
  leaf area and still read sparse: ~1,400 fixed-size sprays cannot fill a 90 m² crown
  shell. The lever for that is a **smaller/subdivided twig asset**, not more leaf area.
- **`build_cutoff_thickness` IS the triangle-budget lever, and `resolution` is not**
  (amended 2026-08-23, measured -- see "Open-grown h20/h25" below). On an h20 open-grown
  silver fir, dropping `resolution` 16 -> 8 with `resolution_reduce` 0.5 -> 0.95 moved the
  mesh from 12,371,707 points to 5,287,045, and *everything below res 12 was identical*
  (5,288,077 at res 12) because `resolution_reduce` already floors the thin branches --
  only the trunk responds to base resolution. `build_cutoff_thickness` 0.0025 -> 0.005 on
  the same tree gives 489,898 points, a 10.8x cut, because a mature conifer's branch count
  is dominated by sub-5mm twiglets.
  The original warning was about crown sparseness, and **twig recovery now answers it** --
  orphans are restored exactly rather than lost. What raising the cutoff actually costs is
  *recovery work*: twig survival falls from 95.3% at 0.0025 to 0.1% at 0.005, so recovery
  reattaches 131,657 orphans instead of 6,245. Budget for that, not for a thin crown.
  The cutoff is also **quantised** -- 0.0025, 0.003 and 0.0035 produce a bit-identical
  mesh; the cliff is at 0.004.
- **`[export] static = false` stays false** — the UE 5.7/5.8 Nanite Assembly builder
  deadlocks on StaticMesh targets.


---

## Open-grown h20/h25 (2026-08-23)

The h05..h25 x r00/r05/r10/r15 dataset run surfaced a cost this doc had never
measured, because **r00 had never actually been open-grown**. Surround is a
*preset* property and four dataset species ship `surround_enabled = true`
(european_beech 10 m, norway_spruce 9.5 m, scots_pine 10 m, silver_fir 9.5 m);
`create_forest()` only ever enabled surround and never disabled it. Every r00
measurement in this doc above -- including **"22 GB at the h25 milestone"** --
was therefore taken on a *shaded* tree. Fixed in 0be41dc.

A genuinely open-grown silver fir is far bigger, and the numbers move with it:

| stage | branches | mesh points @ [quality.high] | stems .usdc |
|---|---|---|---|
| h10 | ~100,024 | 4,515,590 | 252.6 MB |
| h15 | 155,325 | 7,030,216 | 1,069.3 MB |
| h20 | 273,421 | 12,371,707 | -- (OOM at high) |
| h25 | 423,952 | 19,095,895 | -- (OOM at high) |

At `[quality.high]` the h20 export exhausts a 63.5 GB host and never reaches
h25. Three memory defects were fixed first (all in the pipeline, none of them
this):

1. **The whole ladder was retained** until an export phase at the end -- 37 GB
   before export began. Now each milestone is exported as it is captured
   (`on_capture`, db10906).
2. **The previous stage stayed referenced** by `merged_data` until the next
   milestone, so two full stages were alive at once. Released after capture.
3. **24.9M face-varying UVs** (3.5x the point count) were materialised as Python
   lists of tuples and then of `Gf.Vec2f`. Typed `Vt` arrays instead: 36b5445
   took `build_tree_mesh` from +6.27 GB to +0.29 GB.

Together those make memory *fall* between stages -- RSS drops 38.3 -> 3.2 GB
the moment a stage finishes exporting -- but they do not shrink a 19M-point
mesh. That needs `[quality.dataset_tall]` (cutoff 0.005, res 12), applied to
h20/h25 at r00 only. Everything at h15 and below, and every shaded radius,
stays on `[quality.high]`.

Resulting ladder, silver_fir r00:

    h05 32.7 MB | h10 252.6 MB | h15 1069.3 MB | h20 48.3 MB | h25 105.4 MB

**Open question for Gate 2:** h15 -> h20 is a ~20x step down in mesh density
between adjacent stages. It is invisible in the icons, which render from the
skeleton rather than the mesh, so it has to be judged in the editor.
