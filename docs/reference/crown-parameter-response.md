# Crown Parameter Response

Which Grove knob moves which crown property, for which species, by how much —
measured on exported assemblies, not judged by eye.

**Read when:** tuning a species toward a target crown shape, or building an
inverse model ("grow me a 25 m beech with a 12 m crown starting at 8 m").
**Canonical:** Yes, for parameter → response. The per-species values currently
in force live in `config/surround.toml` and `config/preset_patches.json`.

---

## How these numbers were obtained

`growpy-crown-metrics` (`src/growpy/tools/crown_metrics.py`) reads the
`TwigInstances` PointInstancer out of each `*_assembly.usd*` and reports, in
metres:

| metric | definition |
|---|---|
| `crown_diameter_m` | 2 x the 95th-percentile horizontal radius of the foliage |
| `crown_base_m` | height below which only 2% of the foliage sits |
| `crown_ratio` | `(height - crown_base) / height` |
| `crown_projection_m2` | convex-hull area of the foliage seen from above |
| `crown_d_over_h` | crown diameter / tree height — scale-free, the main handle |

It measures the **foliage envelope**, deliberately. Branch tips extend past the
leafy volume, and a stem that wanders laterally defeats any stem-based estimate:
an earlier bole metric reported **1.4 m** on an oak whose live crown visibly
started near **17 m**. `--outlines` draws the measured lines back onto the tree
so a number can always be checked against the shape.

Percentiles, not extremes: one long limb otherwise sets the diameter, which made
crown width read non-monotonically across a whole sweep.

## Reference targets

| species group | crown diameter / H | crown ratio | height to crown base |
|---|---|---|---|
| Norway spruce (n=5526) | **0.22** | 0.60 | 5.6 m mean |
| European beech (n=5666) | **0.30** | 0.57 | 8.2 m mean |
| working target, conifers | 0.22-0.25 | 0.52-0.68 | 7-10 m at H~25 m |
| working target, broadleaves | 0.30-0.45 | 0.52-0.68 | 7-10 m at H~25 m |

Sharma, Vacek, Vacek & Kucera (2017), *Modelling tree crown-to-bole diameter
ratio for Norway spruce and European beech*, Silva Fennica 51(5):1740. Largest
crowns observed in those sets: spruce **11.9 m**, beech **19.7 m**. Companion
height-to-crown-base model: PLOS One 12(10):e0186394.

**Open-grown trees are exempt.** They legitimately carry far wider, lower crowns
(Peper, McPherson & Mori 2001, J. Arboriculture 27(6):306), so `r00` is never
held to the stand figures — only the shaded radii are.

---

## The three surround knobs

`surround_distance` (radii), `surround_density`, `surround_grow`. Nothing else
in the shell matters.

* **`surround_grow` is the master switch.** With `false` the shell is a fixed
  height the tree simply outgrows: a shaded spruce came out at crown width
  **18.3 m against 18.2 m open-grown** — no competition effect at all above the
  bole. With `true` the shell tracks the tree and competition is sustained.
* **`surround_height` is INERT when `grow = true`.** A/B at 0.5 / 5 / 10 m gave
  byte-identical trees. Do not tune it in that mode.
* **`surround_distance` is the weakest of the three.** Grove documents 4-10 m;
  16 m still produces trees, but several species come out close to open-grown.

### Density is a THRESHOLD, not a gradient

The single most important finding. Each species has a cliff, and the cliffs span
**0.38 to 0.90**. Crown ratio typically falls from ~0.85 to ~0.25 between two
adjacent density steps, often skipping the realistic band entirely.

A single global density therefore cannot serve the set: at 0.45 `douglas_fir`
was already past its cliff (crown ratio 0.39) while `european_beech` had not
reached its own (0.93). That produces exactly the observed symptom — some
species slimmer, others untouched.

| species | cliff | calibrated density | Ø/H | crown base | ratio |
|---|---|---|---|---|---|
| douglas_fir | <0.45 | **0.38** | 0.14 | 9.9 m | **0.61** |
| european_oak | 0.45-0.60 | **0.45** | 0.95 | 10.1 m | **0.60** |
| scots_pine | 0.45-0.60 | **0.55** | 0.24 | 11.8 m | **0.52** |
| silver_birch | >0.80 | **0.60** | 0.25 | 3.3 m | 0.87 |
| sycamore_maple | 0.65-0.70 | **0.65** | 0.47 | 11.4 m | **0.55** |
| norway_spruce | 0.70-0.75 | **0.70** | 0.11 | 9.2 m | **0.63** |
| silver_fir | 0.70-0.75 | **0.70** | 0.12 | 9.2 m | **0.64** |
| wild_cherry | 0.66-0.70, unstable | **0.70** | 0.62 | 14.0 m | 0.39 |
| common_ash | none found | **0.75** | 1.25 | 6.1 m | 0.76 |
| european_beech | 0.70-0.75 | **0.90** | 0.36 | 5.8 m | 0.76 |
| small_leaved_linden | gradual | **0.90** | 0.37 | 3.1 m | 0.88 |

`silver_fir` and `norway_spruce` share the `Pinaceae - Fir` preset and measure
identically throughout — expect one to stand in for the other.

---

## Preset knobs, by the property they move

### `add_regenerate` -> CROWN BASE

The strongest single lever for crown base, and the reason density alone cannot
lift it on some species. It controls whether shed branches **regrow**, so a high
value pins the live crown near the ground however hard the tree is competed.

The three species whose crown base would not lift at any density are the three
highest in the set; every species that calibrated on density alone sits at
0.0-0.7.

| species | value | crown base | crown ratio |
|---|---|---|---|
| silver_birch | 0.9 -> **0.3** | 3.3 -> **5.6 m** | 0.87 -> 0.77 |
| european_beech | 1.0 -> 0.9 | 5.8 -> **6.8 m** | 0.76 -> 0.73 |
| european_beech | 1.0 -> 0.8 | 5.8 -> 18.9 m | 0.76 -> **0.24** (overshoots) |
| small_leaved_linden | 0.9 -> 0.5 | 3.1 -> **14.4 m** | 0.88 -> 0.42 |
| small_leaved_linden | 0.9 -> 0.3 | 3.1 -> 17.8 m | 0.88 -> 0.29 (overshoots) |

The response shape differs by species: **birch saturates** (0.15, 0.22 and 0.3
are identical; 0.0 kills it), **beech is a step** between 0.8 and 0.9, **linden
is gradual** across 0.3-0.9 and can be interpolated.

### `add_chance` -> CROWN WIDTH (branch count)

Reduces how many branches form. Gentler than shortening branches, which several
species do not survive.

| species | value | crown diameter |
|---|---|---|
| common_ash | 1.0 -> **0.70** | 31.4 -> **25.6 m** (survives) |
| common_ash | 1.0 -> 0.50 | dies |
| wild_cherry | 1.0 -> 0.70 | 14.1 -> **22.1 m** — *wider*, see below |

**Counter-intuitive for `wild_cherry`:** fewer branches means less self-shading,
so it keeps its lower crown and comes out wider and lower. Do not assume this
knob narrows every species.

### `grow_length` -> branch length — HIGH RISK

Cutting it narrows the crown in principle, but removes the growth a competed
tree needs to survive:

| species | value | outcome |
|---|---|---|
| common_ash | 0.56 -> 0.48 / 0.40 | **dies** at both |
| wild_cherry | 0.6 -> 0.42 | **dies** |
| wild_cherry | 0.6 -> 0.50 | survives, 13.1 m vs 14.1 m — no real gain |

A species sitting at its calibrated density has little survival margin. Prefer
`add_chance`.

### `drop_decay` / `drop_weak` -> SURVIVAL, not shape

Under a growing shell five species cannot survive their own Grove drop rates and
need them scaled to **0.6**: `norway_spruce`, `silver_fir`, `silver_birch`,
`small_leaved_linden`, `wild_cherry`. The other six run Grove-stock.

Reducing these further does **not** rescue a struggling species — linden at
`drop_weak` 0.06 and 0.03 still failed. And suppressing them across the whole
run is the documented way to ruin a dataset: an `ease_in, power 3.0` ramp
applied ~2.7% of the target drop rate at cycle 48 of 160, producing opaque
crowns with no visible bole. If a ramp is ever needed again, use
`transition_cycle`, never `power`.

### Knobs that look right and are not

| knob | species | result |
|---|---|---|
| `turn_to_horizon` | european_beech (0.53, only non-zero in the set) | **inert** — 0.25 matches baseline, 0.0 kills the tree |
| `surround_height` | any, with `grow = true` | **inert** — identical trees at 0.5 / 5 / 10 m |
| `favor_end` | european_oak (0.0, lowest in set) | raising it does not fix crown width; at 0.85 a conifer becomes a bare pole |

---

## Known deviations

* **`common_ash` is ~2x too wide at the source.** Open-grown 33.7 m against
  15-20 m for a real ash. No competition setting fixes a doubled baseline;
  `add_chance 0.70` trims ~20% and is the most it survives.
* **`wild_cherry` responds non-monotonically near its threshold**
  (0.66 -> 0.73, 0.68 -> 0.84, 0.70 -> 0.39) and at 0.66 comes out *wider* than
  open-grown. It runs on density alone.
* **`silver_birch` plateaus at crown ratio 0.77**, short of the 0.68 ceiling.
* **`european_beech` and `small_leaved_linden` cannot have their crown base
  placed precisely.** Their `add_regenerate` response near the threshold jumps
  the target band instead of crossing it, and for beech it is not even
  monotonic:

  | species | value | crown ratio |
  |---|---|---|
  | european_beech | 0.80 | 0.24 |
  | european_beech | 0.84 | 0.81 |
  | european_beech | 0.87 | 0.73 |
  | small_leaved_linden | 0.65 | 0.31 |
  | small_leaved_linden | 0.78 | 0.86 |

  Repeat runs of the SAME beech configuration also differ (r08 ratio 0.73 then
  0.81; r16 0.50 then 0.37) despite a fixed seed, so these two are genuinely
  unstable in this region rather than merely finely tuned. An inverse model
  should treat a requested crown base on these species as approximate, and
  verify by measurement rather than trusting the parameter.

---

## For inverse modelling

To hit a requested crown shape, tune in this order:

1. **`surround_grow = true`** — without it there is no competition response to
   tune at all.
2. **Density -> crown ratio and crown base.** Find the species' threshold first;
   useful values sit within ~0.05 of it and the response is a cliff. Start from
   the calibrated value in the table above.
3. **`add_regenerate` -> crown base**, when density alone leaves the crown
   running to the ground. A preset value >=0.9 is the tell.
4. **`add_chance` -> crown width**, when the crown is too wide at a density that
   already gives the right crown ratio. Check the sign for that species first.
5. **`drop_decay` / `drop_weak` -> survival only**, if the tree dies before h25.

Radius is the weakest handle. Prefer density for a "how competed is this tree"
input, and keep radius for the stand geometry it actually represents.

Always verify with `growpy-crown-metrics --outlines`. Several plausible
parameter guesses recorded in this document turned out to be wrong, and only the
measurement caught them.

**Last Updated:** 2026-08-28
