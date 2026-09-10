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
RADII = ["5", "10", "20"]


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


# DBH is recorded as integer centimetres, so 1 cm is the measurement quantum.
# At h05 the stems are 5-7 cm, where that quantum is ~15-20% of the value and
# two radii routinely land on the same integer. Treating such a tie as a failed
# gradient rejected beech at d=0.90 -- the value every other line of evidence
# says is correct -- purely on rounding at the smallest stage. Only a genuine
# inversion beyond the quantum counts against an arm.
DBH_TOL_CM = 1.0


def dbh_ordering(cells: dict[str, dict]) -> tuple[str, str, float | None]:
    """Classify the r05 -> r10 -> r20 DBH ordering for one stage of one arm.

    Returns (verdict, detail, spread). r05 must be the THINNEST: it carries the
    tightest shell. A tie within DBH_TOL_CM is quantisation and passes; a real
    inversion fails. `spread` is r20 - r05, which is how much the shell is
    actually discriminating between radii -- reported, not gated, because there
    is no published threshold for it.
    """
    vals = [fnum(cells.get(r), "dbh_cm") for r in RADII]
    if any(v is None for v in vals):
        return "--", "", None
    detail = "/".join(f"{int(v)}" for v in vals)
    spread = vals[2] - vals[0]
    if vals[0] > vals[1] + DBH_TOL_CM or vals[1] > vals[2] + DBH_TOL_CM:
        return "INVERTED", detail, spread
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
        print(f"=== {species}   (crown d/h target {target_dh}) ===")
        print(f"{'density':>8} {'models':>7} {'gate':>10} {'dbh r05/r10/r20':>18}"
              f" {'spread':>7} {'ratio':>7} {'d/h':>7} {'fill':>7}"
              f"  cells outside gate")

        candidates: list[tuple[float, float, int]] = []
        for density in sorted({d for s, d in arms if s == species}):
            per_radius = arms[(species, density)]
            models = sum(len(v) for v in per_radius.values())

            # Gate: every stage present at ALL THREE radii must be monotonic.
            bad: list[str] = []
            checked = 0
            for stage in STAGES:
                cells = {r: per_radius.get(r, {}).get(stage) for r in RADII}
                if any(c is None for c in cells.values()):
                    continue
                checked += 1
                verdict, detail, _ = dbh_ordering(cells)
                if verdict not in ("ok", "--"):
                    bad.append(f"{stage}:{verdict}({detail})")
            gate = "PASS" if checked and not bad else ("FAIL" if bad else "--")

            judged = per_radius.get("5", {}).get(args.stage)
            ratio = fnum(judged, "crown_ratio")
            dh = fnum(judged, "crown_d_over_h")
            fill = fnum(judged, "twigs_per_m3")
            _, dbh_txt, spread = dbh_ordering(
                {r: per_radius.get(r, {}).get(args.stage) for r in RADII})

            score = None
            if ratio is not None:
                score = abs(ratio - RATIO_MID) / RATIO_MID
                if dh is not None:
                    score += abs(dh - target_dh) / target_dh

            print(f"{density:>8} {models:>7} {gate:>10} {dbh_txt or '--':>18}"
                  f" {'--' if spread is None else f'{spread:+.0f}':>7}"
                  f" {'--' if ratio is None else f'{ratio:.2f}':>7}"
                  f" {'--' if dh is None else f'{dh:.2f}':>7}"
                  f" {'--' if fill is None else f'{fill:.1f}':>7}"
                  f"  {', '.join(bad) if bad else ''}")

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
    print("A FAIL on the gate is not a near-miss -- an inverted or flat DBH "
          "gradient means the three radii are not three variants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
