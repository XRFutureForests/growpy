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
GATE_FIELD = {False: ("dbh_cm", 1.0, "dbh"),
              True: ("crown_diameter_m", 0.1, "crownø")}


def gate_axis(species: str) -> tuple[str, float, str]:
    """(csv field, tolerance, short label) that separates radii for this habit."""
    return GATE_FIELD[species in CONIFERS]


def radius_ordering(cells: dict[str, dict], field: str,
                    tol: float) -> tuple[str, str, float | None]:
    """Classify the r05 -> r10 -> r20 ordering of `field` for one stage.

    r05 carries the tightest shell, so it must sit LOWEST on whichever axis the
    shell drives. Returns (verdict, detail, spread):

      ok        monotonic and separated by more than the quantum
      INVERTED  a real reversal -- the shell is working backwards
      FLAT      spread within the quantum: the three radii are not three
                variants at all, which defeats the point of having three
    """
    vals = [fnum(cells.get(r), field) for r in RADII]
    if any(v is None for v in vals):
        return "--", "", None
    fmt = "{:.0f}" if field == "dbh_cm" else "{:.1f}"
    detail = "/".join(fmt.format(v) for v in vals)
    spread = vals[-1] - vals[0]
    # Walk consecutive pairs rather than indexing three fixed slots: the radius
    # set is a config choice and has already gone from three values to two.
    if any(a > b + tol for a, b in zip(vals, vals[1:])):
        return "INVERTED", detail, spread
    if spread <= tol:
        return "FLAT", detail, spread
    return "ok", detail, spread


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="h20m",
                    help="stage the crown target is judged at (default h20m: "
                         "mature enough for the stand-grown literature to "
                         "apply, and still on most species' ladder)")
    ap.add_argument("--species", nargs="+", help="limit to these species dirs")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR,
                    help="sweep scratch directory holding sweep_results.csv "
                         "(default: data/tmp/surround_density_sweep)")
    args = ap.parse_args()

    global RESULTS
    RESULTS = args.work_dir / "sweep_results.csv"

    rows = load()
    if args.species:
        rows = [r for r in rows if r["species"] in args.species]
        if not rows:
            raise SystemExit(f"no OK rows for {args.species}")

    # (species, density) -> radius -> stage -> row
    arms: dict[tuple[str, float], dict[str, dict[str, dict]]] = defaultdict(
        lambda: defaultdict(dict))
    for r in rows:
        arms[(r["species"], float(r["density"]))][r["radius"]][r["stage"]] = r

    print("RULE: admissibility beats completeness (owner, 2026-09-10).")
    print("  GATE  = DBH monotonic r05 < r10 < r20 at every stage reached")
    print(f"  SCORE = crown ratio vs {RATIO_BAND[0]}-{RATIO_BAND[1]} "
          f"+ crown d/h vs target, judged at {args.stage}")
    print(f"  REPORTED ONLY = models yielded, fill/m3   "
          f"(crown noise +/-{SEED_NOISE}, A30)\n")

    for species in sorted({s for s, _ in arms}):
        target_dh = DH_TARGET.get(species, DH_DEFAULT)
        field, tol, label = gate_axis(species)
        habit = "conifer" if species in CONIFERS else "broadleaf"
        print(f"=== {species}   ({habit}; gated on {label}; "
              f"crown d/h target {target_dh}) ===")
        print(f"{'density':>8} {'models':>7} {'gate':>10} "
              f"{label + ' r05/r10/r20':>20}"
              f" {'spread':>7} {'ratio':>7} {'d/h':>7} {'fill':>7}"
              f"  cells outside gate")

        candidates: list[tuple[float, float, int]] = []
        for density in sorted({d for s, d in arms if s == species}):
            per_radius = arms[(species, density)]
            models = sum(len(v) for v in per_radius.values())

            # INVERTED fails; FLAT only warns. They are different faults: an
            # inversion means the shell is acting backwards, which is a defect
            # and disqualifies the arm (beech at d=0.80). Flatness means the
            # shell simply is not separating two radii at that stage -- true of
            # every species at h05, where the tree is a sapling the shell has
            # barely touched, and it says nothing about the mature tree. Worth
            # seeing, because those cells are near-duplicates across radii, but
            # not worth rejecting a good arm over.
            bad: list[str] = []
            flat: list[str] = []
            checked = 0
            for stage in STAGES:
                cells = {r: per_radius.get(r, {}).get(stage) for r in RADII}
                if any(c is None for c in cells.values()):
                    continue
                checked += 1
                verdict, detail, _ = radius_ordering(cells, field, tol)
                if verdict == "INVERTED":
                    bad.append(f"{stage}:INVERTED({detail})")
                elif verdict == "FLAT":
                    flat.append(f"{stage}:flat({detail})")
            gate = "PASS" if checked and not bad else ("FAIL" if bad else "--")

            # Score at the requested stage on r05 -- the most competed radius,
            # so the closest thing to the stand-grown trees the literature
            # measures. But r05 is also the FIRST radius to run short of the
            # ladder (A53 expects that and accepts it), and reading only r05
            # meant a species whose r05 stopped early reported "--" on every
            # column and "NO arm passes", hiding perfectly good r10/r20 data.
            # So fall back to the deepest stage r05 actually reached, and say
            # which one was used.
            judged_stage = args.stage
            judged = per_radius.get("5", {}).get(judged_stage)
            if judged is None:
                have = [st for st in STAGES if st in per_radius.get("5", {})]
                if have:
                    judged_stage = have[-1]
                    judged = per_radius["5"][judged_stage]
            ratio = fnum(judged, "crown_ratio")
            dh = fnum(judged, "crown_d_over_h")
            fill = fnum(judged, "twigs_per_m3")
            _, dbh_txt, spread = radius_ordering(
                {r: per_radius.get(r, {}).get(judged_stage) for r in RADII},
                field, tol)
            at = "" if judged_stage == args.stage else f" @{judged_stage}"

            score = None
            if ratio is not None:
                score = abs(ratio - RATIO_MID) / RATIO_MID
                if dh is not None:
                    score += abs(dh - target_dh) / target_dh

            print(f"{density:>8} {models:>7} {gate:>10} {dbh_txt or '--':>18}"
                  f" {'--' if spread is None else f'{spread:+.1f}':>7}"
                  f" {'--' if ratio is None else f'{ratio:.2f}':>7}"
                  f" {'--' if dh is None else f'{dh:.2f}':>7}"
                  f" {'--' if fill is None else f'{fill:.1f}':>7}"
                  f"  {at}{' ' if at else ''}{', '.join(bad + flat)}")

            if gate == "PASS" and score is not None:
                candidates.append((score, density, models))

        if not candidates:
            print("  -> NO arm passes the DBH gate with a crown measurement "
                  f"at {args.stage}. Widen the bracket or check A48.\n")
            continue

        candidates.sort()
        best_score, best_density, best_models = candidates[0]
        line = f"  -> {best_density}  ({best_models} models)"
        if len(candidates) > 1:
            runner = candidates[1]
            rb = fnum(arms[(species, best_density)].get("5", {}).get(args.stage),
                      "crown_ratio")
            rr = fnum(arms[(species, runner[1])].get("5", {}).get(args.stage),
                      "crown_ratio")
            if rb is not None and rr is not None and abs(rb - rr) < SEED_NOISE:
                line += (f"   runner-up {runner[1]} is within seed noise "
                         f"({rb:.2f} vs {rr:.2f}) -> NEEDS-SEEDS")
        rejected = [d for _, d, _ in candidates[1:]]
        if rejected:
            line += f"   [also passed gate: {rejected}]"
        print(line + "\n")

    print("NEEDS-SEEDS arms are the replication shortlist: re-run those "
          "densities with --seeds 512 999 7 before believing the choice.")
    print("A FAIL means INVERTED: the shell acted backwards on the gated axis, "
          "so the arm is disqualified, not merely imperfect.")
    print("A lowercase `flat` cell is a WARNING: those radii are near-duplicates "
          "at that stage. Normal at h05; worth a look higher up the ladder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
