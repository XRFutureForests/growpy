# Crown-Density Ratchet

The memory of the crown-density tuning loop. One row per round, every gate metric,
the config delta that produced it, and pass/fail.

**Ceilings are derived, never invented.** Round 0 measures the current config and
becomes the baseline. Every later round sets each ceiling at the best value achieved
so far that still passed the other gates. A ceiling is never loosened to make a round
pass — a regression is recorded as a regression.

Related Linear issues: XRFF-272 (parent), XRFF-273 (per-tree resolver), XRFF-274 (Done —
per-prototype leaf area), XRFF-318 (pylometree Forrester registration).

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

The working tree carried **uncommitted** config changes when the loop started. These were
not made by this loop. Round 0 measures the **working tree** state, because that is
literally the current config; HEAD is recorded for comparison.

| Key | HEAD | Working tree (round-0 baseline) |
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

1. `build_cutoff_thickness` is **already raised** in the working tree (0.00125 -> 0.0025
   at `[quality.high]`). This is the guardrail parameter: raising it removes the youngest
   branches first, which is exactly where Grove places twigs, and it deletes the
   attachment points recovery would otherwise repack onto. The loop will **not** raise it
   further and will not use it to buy triangles. It is recorded here so that a later
   "crowns are hard to fill" finding is attributed correctly.
2. `max_skeleton_joints = 1000` contradicts its own config comment, which states that
   Nanite encodes bone indices in 8-bit fields and that 250 is the safe Nanite-Assembly
   value. This is a candidate Gate-2 failure cause **independent of density**, and must be
   ruled out before any import crash is blamed on crown density.

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

## Round log

| Round | Config / code delta | G1 `crown_fill` range | G1 worst `blob_saturation` | G2 import | G3 worst expanded tris | G4 frame time | Verdict |
|---|---|---|---|---|---|---|---|
| 0 | baseline (working tree) | 0.008 – 0.381 (8 trees; ash h15 missing) | 0.252 (beech h15) | not run | 65.3 M (beech h15) | not run | baseline |
| 1 | dead-twig drop moved ahead of `densify`; `plateau_cycles` 5 → 25 | 0.008 – 0.553 (9 trees) | 0.685 (ash h15) | not run | 75.0 M (ash h15) | not run | **no Gate-1 change** |
| 2 | `silver_fir` 0.0078 → 0.025; `skeleton_length` 1.0 → 1.1, `skeleton_reduce` 0.333 → 0.36; `max_skeleton_joints` 1000 → 250 | 0.026 – 0.552 | 0.690 (ash h15) | not run | 122.4 M (fir h15) | not run | **2 of 9 in band; joint limit cleared** |

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
| 3 — expanded triangles | **122.4 M** per assembly | `silver_fir` h15, round 2. Historical: 147 M imported cleanly, 2.45 B crashed. |
| 3 — skeleton joints | **advisory only**, not a gate (see D4) | owner: "not a hard limit but a suggestion" |
| 1 — `blob_saturation` | **0.690 is a FAIL**, not a ceiling | `common_ash` h15; passing trees measure 0.123–0.257 |
| 2 — import | measuring now (first real UE run) | — |
| 4 — frame time | not yet measured | — |

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
