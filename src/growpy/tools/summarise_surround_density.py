#!/usr/bin/env python
"""Turn sweep_results.csv into the per-species shell-density decision.

THE GOVERNING RULE (owner, 2026-09-10): ADMISSIBILITY BEATS COMPLETENESS.
Pick the density that produces a CORRECT tree, and accept whatever height
ladder that density happens to reach. Never lower a species' density to buy an
extra stage.

That rule was earned, not assumed. Beech measured at three densities:

    d=0.80  r05 reaches h25 (5/5)   but DBH goes 46/26/42 at h20 and 72/29/47
                                    at h25 -- INVERTED, the tightest shell
                                    giving the thickest stem -- and r05 h15 is
                                    22 cm against a 10.4 cm allometry target
    d=0.90  r05 stops at h20 (4/5)  DBH 11/20/32 at h15, monotonic everywhere,
                                    r05 h15 within 6% of the allometry target,
                                    crown ratio 0.62 at h20, inside Sharma
    d=0.95  r05 stops at h20 (4/5)  identical DBH to 0.90 (the stem has
                                    saturated) but crown crushed to 0.25-0.32

0.80 buys one model and destroys the tree. The owner's call: take 0.90 and the
smaller catalog. "Very tall r05 trees look off."

SO LADDER COMPLETENESS IS REPORTED, NOT SCORED. It tells you how many models a
density yields. It never selects.

WHAT DOES GATE -- DBH monotonicity across r05 < r10 < r20 at every stage the
arm reached. r05 carries the tightest shell so it must carry the thinnest stem;
an inverted or flat ordering means the shell has stopped discriminating between
radii, which defeats the whole point of having three of them. This is the check
that caught beech, and A30 measured DBH as seed-stable, so a single-seed arm
can be trusted on it.

WHAT SCORES -- crown ratio against Sharma et al. 2017's 0.52-0.68 AND crown
diameter/height against ~0.30 broadleaf / ~0.22 spruce. Both, because A21
measured a change that fixed the ratio while pushing the width the wrong way.

WHAT IS ONLY REPORTED -- `fill/m3` (twig attachment points per m3 of crown).
Crown ratio and d/h are ENVELOPE percentiles and cannot see a crown hollowed
from the inside, which is A23's fir failure; fill can. No published target, so
compare it between arms of one species. LAI is not used at all: leaves are
placed by PVE now (A40), so exported leaf area is not this path's deliverable.

A CAUTION ON THE PER-RADIUS TABLE. `[surround.density_per_species_radius]` lets
each radius take its own density, but DBH monotonicity is a CROSS-radius
property: choosing r05's density and r20's density independently, each to
optimise its own crown, can produce a combination whose gradient is not
monotonic. This tool reports monotonicity per ARM (one density across all three
radii). If you mean to mix densities per radius, re-check the resulting gradient
before committing it.

SEEDS (2026-09-15). Arms are grouped by (species, density, SEED). A density
is PASS only when every seed passes; one inverted replicate fails it, because
an ordering that depends on the seed is not a property of the density. The
line shows n, and the crown columns are means over seeds with the range. A
broadleaf on the crown-ø axis needs >= 2 seeds before a PASS may rank -- the
birch replication (seeds 512 / 999 / 7) put r08/r16 on opposite signs at both
densities tested. `--gate-axis base` reads the crown base instead, the axis
shading physically drives; see GATE_BASE for why it is the sign-stable one.

Deliberately does NOT write config. The selection is a decision.

Usage:
    growpy-summarise-surround-density
    growpy-summarise-surround-density --stage h20m
    growpy-summarise-surround-density --species european_beech
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_WORK_DIR = REPO / "data" / "tmp" / "surround_density_sweep"
RESULTS = DEFAULT_WORK_DIR / "sweep_results.csv"

RATIO_BAND = (0.52, 0.68)
RATIO_MID = sum(RATIO_BAND) / 2

# Crown diameter / height. Sharma et al. 2017 report these for stand-grown
# trees; the conifer figure is spruce's and is applied to the other conifers
# only as the nearest published shape, not as their own measurement.
DH_TARGET = {
    "european_beech": 0.30,
    "norway_spruce": 0.22,
    "silver_fir": 0.22,
    "douglas_fir": 0.22,
    "scots_pine": 0.22,
}
DH_DEFAULT = 0.30

# A30's measured seed spread on crown ratio, single tree, radius set held fixed.
# Applies to the crown metrics only -- DBH and height are seed-stable.
SEED_NOISE = 0.30

STAGES = ["h05m", "h10m", "h15m", "h20m", "h25m"]
RADII = ["8", "16"]
# The reference radius for the crown score: the tightest shell in the set, so
# the closest thing to the stand-grown trees the literature measures. Derived,
# not written literally -- a hardcoded "5" survived the move from [5,10,20] to
# [8,16] and silently blanked every crown column.
TIGHTEST = RADII[0]


def fnum(row: dict | None, key: str) -> float | None:
    if not row:
        return None
    raw = (row.get(key) or "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def load() -> list[dict]:
    if not RESULTS.exists():
        raise SystemExit(f"no results yet at {RESULTS}")
    with RESULTS.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if (r.get("status") or "").strip() == "OK"]
    if not rows:
        raise SystemExit("no rows with status OK yet")
    return rows


# WHICH AXIS SEPARATES THE THREE RADII DEPENDS ON HABIT -- measured 2026-09-10.
#
# On a broadleaf the shell moves the STEM. Beech at d=0.90 reads DBH 11/20/32 cm
# at h15 across r05/r10/r20 -- a 21 cm spread, and the inversion of that ordering
# is what disqualified d=0.80.
#
# On a conifer the shell does NOT move the stem at all. Norway spruce reads
# 14/14/14 at h15, 22/22/22 at h20 and 30/30/30 at h25 -- identical to the
# centimetre at every radius, at BOTH densities tested. A18 recorded the same for
# silver fir. What does move is CROWN WIDTH: spruce crown diameter runs
# 1.8/2.1/2.8 m at h10 through 2.9/3.1/3.6 m at h25, monotonic throughout.
#
# So gating every species on DBH is a broadleaf test that rejects all four
# conifers on a property they were never going to have. Each habit is gated on
# the axis that actually responds.
CONIFERS = {"norway_spruce", "silver_fir", "douglas_fir", "scots_pine"}

# DBH is recorded as integer centimetres, so 1 cm is the measurement quantum. At
# h05 the stems are 5-7 cm, where that quantum is ~15-20% of the value and two
# radii routinely land on the same integer; treating such a tie as a failed
# gradient rejected beech at d=0.90, the value every other line of evidence says
# is correct. Crown diameter is reported to 0.1 m, so its quantum is 0.1.
# Each axis is (csv field, tolerance, short label, direction). Direction says
# which way the value must move from the tightest shell outward: +1 means r16
# reads HIGHER than r08 (stem thicker, crown wider), -1 means LOWER (crown base
# nearer the ground, because the weaker shell shades fewer low branches away).
GATE_FIELD = {False: ("dbh_cm", 1.0, "dbh", 1),
              True: ("crown_diameter_m", 0.1, "crownø", 1)}

# CROWN BASE AS THE RADIUS AXIS -- measured 2026-09-15 against every uncapped
# h10+ cell of the completed sweeps (159 cells across three CSVs). The physical
# effect of a closer shell is shading, and shading prunes the LOWEST branches,
# so the axis that must respond is the crown base, not the crown width. It does:
# under the static shell every one of the 31 conifer cells has r08's base above
# r16's, by 0.5-2.3 m, while crown ø alternates sign with density on douglas
# and reads flat on spruce and pine. On the seeded birch arms the crown-ø
# ordering flips with the seed (9 pos / 8 neg over 18 cells) but the crown
# base agrees across all three seeds at d0.70 (6/6 at h15+h20) and is flat at
# d0.60 (0/6) -- the density where the shell has not started biting, and the
# same one whose r08 crown ratio sits at 0.77, out of band. The two readings
# are the same mechanism: the shell lifts r08's base, which is both the bole
# and the radius separation. Quantum 0.5 m: the h05 birch replicates scatter
# within +/-0.2 m, h10 within +/-0.4.
#
# crown_base is still a percentile (p10 of twig height, A61) and inherits every
# caveat of A59/A62 as an ABSOLUTE number. As a DIFFERENCE between two radii of
# one arm it has so far been the most sign-stable column in the data.
GATE_BASE = ("crown_base_m", 0.5, "base", -1)


def gate_axis(species: str, override: str = "auto") -> tuple[str, float, str, int]:
    """(csv field, tolerance, short label, direction) separating radii for this habit.

    `override` forces one axis for every species. It exists because the habit
    rule is not the only thing that decides whether an axis can carry a signal.
    Exported DBH is `grove_dbh * radial_scale` with the scale clamped to
    [0.5, 2.0]; whenever that clamp does NOT bind, the export lands on the
    height-derived allometric target and BOTH radii print the same number by
    construction, regardless of what the shell did. Measured on norway_spruce
    grow=true at h15m: both radii export 14 cm, but at scales 1.1584 and 0.8125,
    so Grove's own stems were 12.1 and 17.2 cm. The difference was real and the
    correction erased it.

    That is not a conifer property -- it applies to every species -- so gating
    broadleaves on `dbh_cm` has been testing a partly-blind column. Use
    "crown" to re-read an existing sweep on the axis the correction does not
    touch, or "base" for the axis the shell physically drives (see GATE_BASE);
    no re-simulation is needed, both fields are already in the CSV.
    """
    if override == "dbh":
        return GATE_FIELD[False]
    if override == "crown":
        return GATE_FIELD[True]
    if override == "base":
        return GATE_BASE
    if override == "habit":
        return GATE_FIELD[species in CONIFERS]
    # auto (owner decision 2026-09-15): crown base for every habit. The habit
    # split above is kept as "habit" for re-reading older verdicts.
    return GATE_BASE


# Epic's Nanite assembly cap, mirrored from [export] max_assembly_instances.
# When a tree exceeds it the exporter removes instances PROXIMITY-WEIGHTED
# (crowded twigs first), so a capped cell's twig cloud is not a random subsample
# -- it is preferentially thinned where foliage was densest. Every crown metric
# is an order statistic over that cloud (crown_diameter = 95th percentile of
# radial distance, crown_base = 10th percentile of height), so comparing a
# capped cell against an uncapped one compares differently-biased estimators.
# The cap cannot simply be raised: a USD assembly past it fails to build on the
# hybrid route (XRFF-426), so the measurement has to account for it instead.
ASSEMBLY_INSTANCE_CAP = 65000
CAP_MARGIN = 100          # treat within this of the cap as capped


def is_capped(cell: dict | None) -> bool:
    """True when this cell's twig cloud was thinned by the instance cap."""
    n = fnum(cell, "n_twigs")
    return n is not None and n >= ASSEMBLY_INSTANCE_CAP - CAP_MARGIN


def radius_ordering(cells: dict[str, dict], field: str, tol: float,
                    direction: int = 1) -> tuple[str, str, float | None]:
    """Classify the r08 -> r16 ordering of `field` for one stage.

    r08 carries the tightest shell, so it must sit LOWEST on an axis the shell
    raises (direction +1: DBH, crown width) and HIGHEST on one it lowers
    (direction -1: crown base). Returns (verdict, detail, spread), spread
    always as r16 minus r08 in the field's own units:

      ok        monotonic and separated by more than the quantum
      INVERTED  a real reversal -- the shell is working backwards
      FLAT      spread within the quantum: the radii are not distinct
                variants at all, which defeats the point of having two
      CAPPED    the instance cap thinned at least one cell, so the twig-cloud
                percentiles are not comparable (see ASSEMBLY_INSTANCE_CAP)
    """
    vals = [fnum(cells.get(r), field) for r in RADII]
    if any(v is None for v in vals):
        return "--", "", None
    fmt = "{:.0f}" if field == "dbh_cm" else "{:.1f}"
    detail = "/".join(fmt.format(v) for v in vals)
    # Refuse the comparison whenever the cap bit AT ALL. One-sided capping is
    # obviously not like-for-like. Both-sided is no better: two trees that
    # naturally carried, say, 80k and 70k instances are thinned by 19% and 7%,
    # and the thinning is proximity-weighted, so it strips the dense crown
    # interior -- exactly where crown_base (10th percentile of twig height) is
    # estimated. Worse, once both cells read the cap the pre-cap counts are
    # gone, so the bias cannot even be quantified after the fact.
    capped = [is_capped(cells.get(r)) for r in RADII]
    if any(capped):
        which = "/".join(f"r{r}" for r, c in zip(RADII, capped, strict=False) if c)
        return "CAPPED", f"{detail} ({which} at instance cap)", None
    spread = vals[-1] - vals[0]
    ordered = [direction * v for v in vals]
    # Walk consecutive pairs rather than indexing three fixed slots: the radius
    # set is a config choice and has already gone from three values to two.
    if any(a > b + tol for a, b in zip(ordered, ordered[1:], strict=False)):
        return "INVERTED", detail, spread
    if ordered[-1] - ordered[0] <= tol:
        return "FLAT", detail, spread
    return "ok", detail, spread


def judge_arm(per_radius: dict[str, dict[str, dict]], field: str, tol: float,
              direction: int, stage: str, max_stage: str | None = None) -> dict:
    """Gate and score ONE arm (one species, one density, one seed).

    INVERTED fails; FLAT only warns. They are different faults: an inversion
    means the shell is acting backwards, which is a defect and disqualifies the
    arm (beech at d=0.80). Flatness means the shell simply is not separating
    two radii at that stage -- true of every species at h05, where the tree is
    a sapling the shell has barely touched, and it says nothing about the
    mature tree. Worth seeing, because those cells are near-duplicates across
    radii, but not worth rejecting a good arm over. CAPPED is not a fault in
    the tree but in the comparison; it warns like FLAT.
    """
    bad: list[str] = []
    flat: list[str] = []
    checked = 0
    # Stages above `max_stage` are neither gated nor scored: the production cap
    # is h15 (forest.toml max_height), and above it the shell sits INSIDE a
    # mature broadleaf's crown (A110 -- beech at h20 has a 10 m crown radius
    # against an 8 m shell), which inverts the ordering for a tree the catalog
    # never exports.
    stages = STAGES if max_stage is None else STAGES[:STAGES.index(max_stage) + 1]
    for st in stages:
        cells = {r: per_radius.get(r, {}).get(st) for r in RADII}
        if any(c is None for c in cells.values()):
            continue
        checked += 1
        verdict, detail, _ = radius_ordering(cells, field, tol, direction)
        if verdict == "INVERTED":
            bad.append(f"{st}:INVERTED({detail})")
        elif verdict == "FLAT":
            flat.append(f"{st}:flat({detail})")
        elif verdict == "CAPPED":
            flat.append(f"{st}:CAPPED({detail})")
        # WALL: the crown reaches past its own shell. Owner definition
        # 2026-09-15: the wall stands at the NEIGHBOURS' CROWN EDGE, so touching
        # it is fine and only a crown whose p95 radius exceeds the distance is
        # out of place (ash at r08: 9.0 m against 8). The shell is shade, not
        # an obstacle (A122), so nothing else enforces this. Warns like FLAT.
        for r in RADII:
            crown = fnum(cells.get(r), "crown_diameter_m")
            if crown is not None and crown / 2.0 > float(r):
                flat.append(f"{st}:WALL(r{r} radius {crown / 2.0:.1f}>{r})")
    gate = "PASS" if checked and not bad else ("FAIL" if bad else "--")

    # Score at the requested stage on the tightest radius -- the most competed
    # one, so the closest thing to the stand-grown trees the literature
    # measures. But it is also the FIRST radius to run short of the ladder
    # (A53 expects that and accepts it), and reading only that radius meant a
    # species whose tight radius stopped early reported "--" on every column
    # and "NO arm passes", hiding perfectly good wider-radius data. So fall
    # back to the deepest stage the tightest radius actually reached, and say
    # which one was used.
    judged_stage = stage
    judged = per_radius.get(TIGHTEST, {}).get(judged_stage)
    if judged is None:
        have = [st for st in STAGES if st in per_radius.get(TIGHTEST, {})]
        if have:
            judged_stage = have[-1]
            judged = per_radius[TIGHTEST][judged_stage]
    _, axis_txt, spread = radius_ordering(
        {r: per_radius.get(r, {}).get(judged_stage) for r in RADII},
        field, tol, direction)
    return {
        "gate": gate, "bad": bad, "flat": flat,
        "models": sum(len(v) for v in per_radius.values()),
        "judged_stage": judged_stage, "axis_txt": axis_txt, "spread": spread,
        "ratio": fnum(judged, "crown_ratio"),
        "dh": fnum(judged, "crown_d_over_h"),
        "fill": fnum(judged, "twigs_per_m3"),
    }


def mean(vals: list[float | None]) -> float | None:
    have = [v for v in vals if v is not None]
    return sum(have) / len(have) if have else None


def fmt(v: float | None, spec: str = ".2f", signed: bool = False) -> str:
    if v is None:
        return "--"
    return format(v, ("+" if signed else "") + spec)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="h20m",
                    help="stage the crown target is judged at (default h20m: "
                         "mature enough for the stand-grown literature to "
                         "apply, and still on most species' ladder)")
    ap.add_argument("--species", nargs="+", help="limit to these species dirs")
    ap.add_argument("--gate-axis",
                    choices=("auto", "base", "habit", "dbh", "crown"),
                    default="auto",
                    help="axis the radius gate reads. auto = base. habit = the "
                         "pre-2026-09-15 split "
                         "(broadleaf dbh, conifer crown diameter). crown "
                         "re-reads a sweep on the axis the clamped DBH "
                         "correction cannot erase; base reads the crown base "
                         "(r08 must sit HIGHER), the axis shading physically "
                         "drives. No re-simulation needed for either.")
    ap.add_argument("--max-stage", choices=STAGES, default=None,
                    help="ignore stages above this one in the gate (e.g. h15m, "
                         "the production cap). Default: gate every stage the arm "
                         "reached, including ones the catalog never exports.")
    ap.add_argument("--min-seeds", type=int, default=1,
                    help="seeds an arm needs before a PASS may be ranked "
                         "(default 1). Broadleaves on the crown-ø axis always "
                         "need 2: that ordering was measured to flip with the "
                         "seed (birch, 2026-09-14), so one seed proves nothing.")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR,
                    help="sweep scratch directory holding sweep_results.csv "
                         "(default: data/tmp/surround_density_sweep)")
    ap.add_argument("--radii", nargs="+", default=None,
                    help="the work dir's shell distances as the CSV spells them, "
                         "tightest first (default: 8 16). A radius probe run with "
                         "sweep --radii 5 10 is read with --radii 5 10.")
    args = ap.parse_args()

    global RESULTS, RADII, TIGHTEST
    RESULTS = args.work_dir / "sweep_results.csv"
    if args.radii:
        RADII = [str(int(float(r))) for r in args.radii]
        TIGHTEST = RADII[0]

    rows = load()
    if args.species:
        rows = [r for r in rows if r["species"] in args.species]
        if not rows:
            raise SystemExit(f"no OK rows for {args.species}")

    # (species, density, seed) -> radius -> stage -> row. The seed is part of
    # the key: before 2026-09-15 it was dropped, so a replicated density kept
    # whichever seed's rows loaded last and printed a verdict for it alone.
    arms: dict[tuple[str, float, int], dict[str, dict[str, dict]]] = defaultdict(
        lambda: defaultdict(dict))
    for r in rows:
        key = (r["species"], float(r["density"]), int(float(r.get("seed") or 0)))
        arms[key][r["radius"]][r["stage"]] = r

    print("RULE: admissibility beats completeness (owner, 2026-09-10).")
    axis_txt = {"auto": "crown base (r08 above r16)",
                "habit": "habit axis (broadleaf DBH, conifer crown ø)",
                "dbh": "DBH", "crown": "crown ø",
                "base": "crown base (r08 above r16)"}[args.gate_axis]
    ladder = " < ".join(f"r{int(float(r)):02d}" for r in RADII)
    print(f"  GATE  = {axis_txt} monotonic {ladder} at every stage reached, "
          f"every seed")
    if args.gate_axis in ("dbh", "habit"):
        print("          NOTE exported DBH is clamped toward a height-derived "
              "target, so it can read FLAT where the stems truly differ (A93)")
    print(f"  SCORE = crown ratio vs {RATIO_BAND[0]}-{RATIO_BAND[1]} "
          f"+ crown d/h vs target, judged at {args.stage}, mean over seeds")
    print(f"  REPORTED ONLY = n seeds, models yielded, fill/m3   "
          f"(crown noise +/-{SEED_NOISE}, A30)\n")

    unreplicated: list[str] = []
    for species in sorted({s for s, _, _ in arms}):
        target_dh = DH_TARGET.get(species, DH_DEFAULT)
        field, tol, label, direction = gate_axis(species, args.gate_axis)
        habit = "conifer" if species in CONIFERS else "broadleaf"
        # A single seed cannot carry a crown-ø verdict on a broadleaf: the
        # birch replication put the r08/r16 ordering on opposite signs across
        # seeds 512 / 999 / 7 at BOTH densities tested.
        need = args.min_seeds
        if field == "crown_diameter_m" and species not in CONIFERS:
            need = max(need, 2)
        print(f"=== {species}   ({habit}; gated on {label}; "
              f"crown d/h target {target_dh}; PASS needs >= {need} seed(s)) ===")
        print(f"{'density':>8} {'n':>3} {'models':>7} {'gate':>10} "
              f"{label + ' ' + '/'.join('r' + r.zfill(2) for r in RADII):>20}"
              f" {'spread':>7} {'ratio':>11} {'d/h':>7} {'fill':>7}"
              f"  cells outside gate")

        candidates: list[tuple[float, float, int, int]] = []
        ratio_at: dict[float, float | None] = {}
        for density in sorted({d for s, d, _ in arms if s == species}):
            seeds = sorted(sd for s, d, sd in arms if s == species and d == density)
            per_seed = {sd: judge_arm(arms[(species, density, sd)], field, tol,
                                      direction, args.stage, args.max_stage)
                        for sd in seeds}
            n = len(seeds)
            verdicts = [j["gate"] for j in per_seed.values()]
            # Every seed must pass. One inverted replicate is not "2 of 3" --
            # it is evidence the ordering is not a property of the density.
            gate = ("FAIL" if "FAIL" in verdicts
                    else "PASS" if all(v == "PASS" for v in verdicts) else "--")
            ratio = mean([j["ratio"] for j in per_seed.values()])
            dh = mean([j["dh"] for j in per_seed.values()])
            fill = mean([j["fill"] for j in per_seed.values()])
            spread = mean([j["spread"] for j in per_seed.values()])
            models = round(mean([j["models"] for j in per_seed.values()]) or 0)
            ratio_at[density] = ratio
            ratios = [j["ratio"] for j in per_seed.values() if j["ratio"] is not None]
            ratio_txt = fmt(ratio)
            if n > 1 and ratios:
                ratio_txt += f" ({min(ratios):.2f}-{max(ratios):.2f})"

            score = None
            if ratio is not None:
                score = abs(ratio - RATIO_MID) / RATIO_MID
                if dh is not None:
                    score += abs(dh - target_dh) / target_dh

            gate_txt = gate
            if gate == "PASS" and n < need:
                gate_txt = f"PASS/n={n}"
                unreplicated.append(f"{species} {density}")

            if n == 1:
                j = next(iter(per_seed.values()))
                at = ("" if j["judged_stage"] == args.stage
                      else f" @{j['judged_stage']}")
                notes = f"{at}{' ' if at else ''}{', '.join(j['bad'] + j['flat'])}"
                axis_cell = j["axis_txt"] or "--"
            else:
                notes = ""
                axis_cell = "(per seed)"
            print(f"{density:>8} {n:>3} {models:>7} {gate_txt:>10} {axis_cell:>18}"
                  f" {fmt(spread, '.1f', signed=True):>7} {ratio_txt:>11}"
                  f" {fmt(dh):>7} {fmt(fill, '.1f'):>7}  {notes}")
            if n > 1:
                for sd, j in per_seed.items():
                    at = ("" if j["judged_stage"] == args.stage
                          else f" @{j['judged_stage']}")
                    print(f"{'seed ' + str(sd):>20} {j['models']:>7} "
                          f"{j['gate']:>10} {j['axis_txt'] or '--':>18}"
                          f" {fmt(j['spread'], '.1f', signed=True):>7}"
                          f" {fmt(j['ratio']):>11} {fmt(j['dh']):>7}"
                          f" {fmt(j['fill'], '.1f'):>7}  {at}{' ' if at else ''}"
                          f"{', '.join(j['bad'] + j['flat'])}")

            if gate == "PASS" and n >= need and score is not None:
                candidates.append((score, density, models, n))

        if not candidates:
            print(f"  -> NO arm passes the {label} gate with >= {need} seed(s) "
                  f"and a crown measurement at {args.stage}. Widen the "
                  "bracket, replicate, or check A48.\n")
            continue

        candidates.sort()
        best_score, best_density, best_models, best_n = candidates[0]
        line = f"  -> {best_density}  ({best_models} models, {best_n} seed(s))"
        if len(candidates) > 1:
            runner = candidates[1]
            rb = ratio_at.get(best_density)
            rr = ratio_at.get(runner[1])
            if rb is not None and rr is not None and abs(rb - rr) < SEED_NOISE:
                line += (f"   runner-up {runner[1]} is within seed noise "
                         f"({rb:.2f} vs {rr:.2f}) -> NEEDS-SEEDS")
        rejected = [d for _, d, _, _ in candidates[1:]]
        if rejected:
            line += f"   [also passed gate: {rejected}]"
        print(line + "\n")

    print("NEEDS-SEEDS arms are the replication shortlist: re-run those "
          "densities with --seeds 512 999 7 before believing the choice.")
    if unreplicated:
        print("PASS/n=1 arms passed on ONE seed and were not ranked: "
              + "; ".join(unreplicated))
    print("A FAIL means INVERTED on at least one seed: the shell acted "
          "backwards on the gated axis, so the arm is disqualified.")
    print("A lowercase `flat` cell is a WARNING: those radii are near-duplicates "
          "at that stage. Normal at h05; worth a look higher up the ladder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
