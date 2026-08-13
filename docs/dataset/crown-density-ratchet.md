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

**The deliverable is 639 models live in XRLabDB (UE 5.7.4), not a passing gate report.**
11 species x 6-9 height stages x 3 surround radii (r00/r08/r16, per `config/surround.toml`
`radii = [0.0, 8.0, 16.0]`). Track this every round, not just gate metrics. An asset only
counts once it is actually present in `/Game/Assets/TheGrove` in UE with the full checklist
below satisfied -- generating a USD file that was never imported is not coverage.

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

**Root cause found and fixed (commit `e87e35e`).** The wind and PVE scripts take their
search root from `unreal_pve_import_base`, while the assembly import uses
`unreal_project_path` — two config keys for one concept, whose defaults did not even agree
(`/Game/GrowPy` vs `/Game/Assets/TheGrove`), and no config file in the repo ever set the
former. The pilot config points `project_path` at `TheGrove_dec25`, so assemblies imported
there while wind and PVE searched `TheGrove`. Nothing warned. `pve_import_base` now
defaults to empty and resolves to `project_path`; setting it explicitly still splits the two
for anyone who wants that.

**The catalog step itself works** — it had simply never been run. Executing
`import_batch_100_datatable.py` against `TheGrove_dec25` found its 2 assemblies, parsed
their metadata, duplicated the Templates table and populated 2 rows, first try. So the
remaining gap is operational, not a second defect.

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

**Wall-clock implication for scale-out:** 61 minutes for one asset. The full dataset target
is 639 models. Conifer h15 assets at this triangle count are not viable at that scale
without either a density reduction or a different import strategy. The broadleaves are
free by comparison (3.9–4.1 s per 3-asset batch).

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

### What this design pass does NOT resolve

- ~~**D8** — which prototype size round 2's recorded Gate-2 import validated~~ — **resolved
  2026-08-13**: the 107,876-face one, confirmed by UE inventory. 122.4 M is real. See the D8
  section above.
- ~~The ~3x over-prediction in the old stem-triangle fit~~ — **resolved 2026-08-13**: the fit
  predates the committed `build_cutoff_thickness = 0.0025` and is retired, not re-fitted.
- h30/h35 data for any metric — not generated this session. The twig instance-count fit is
  already known to under-predict by double digits at h25; do not extrapolate either fit past
  h25 for planning purposes.
- Whether `douglas_fir`'s ~45 m target (the tallest of the four conifers) is reachable — no
  data for that species at height beyond its own pilot stages yet. It shares the same twig
  prototype, so the confirmed 107,876-face cost applies to it too.
- A real Gate-2 import at h20 or h25 to confirm the combined-budget numbers above actually
  import cleanly, not just add up on paper.

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
- **`build_cutoff_thickness` is not a triangle-budget lever.** Use voxelization,
  `resolution`, or `max_assembly_instances` instead.
- **`[export] static = false` stays false** — the UE 5.7/5.8 Nanite Assembly builder
  deadlocks on StaticMesh targets.
