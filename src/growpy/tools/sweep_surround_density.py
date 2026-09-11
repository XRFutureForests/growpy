#!/usr/bin/env python
"""Re-fit the surround shell density per species AND per radius.

WHY THIS EXISTS. Every value in config/surround.toml's density table was fitted
at r08 against a [0.0, 8.0, 16.0] matrix. The matrix moved to [5.0, 10.0, 20.0]
on 2026-09-09, and those values are per-species THRESHOLDS rather than a
gradient -- at a shared 0.45, douglas_fir was already past its cliff (crown
ratio 0.39) while european_beech had not reached its own (0.93). A threshold is
a property of the species AND the shell it was measured against, so it does not
transfer between radii by interpolation. surround.toml says so itself and asks
for this re-sweep.

WHAT ONE ARM IS. One species at one global shell density, grown through the
whole h05..h25 ladder at ALL THREE production radii in a single run. That last
part is deliberate and is what makes the sweep affordable: one arm yields three
radius cells, not one.

It also sidesteps two traps at once.

  A24 -- the plateau counter is SHARED across a species' radius groves, so a
  single-radius arm is not comparable to a multi-radius run. Every arm here
  uses the same [5, 10, 20] set, which is also the production set, so arms are
  comparable to each other AND to what production will do.

  A28 -- Grove's RNG appears to be global inside the compiled core, so adding
  or removing a radius shifts every other radius's draws. Holding the radius
  set fixed at the production one removes that as a variable entirely.

WHAT IT VARIES. Exactly one knob: [surround] density. Both per-species tables
are stripped from the arm's config so nothing shadows it -- see _strip_tables,
which is line-based rather than a regex on purpose (A20: the table names appear
inside comment prose in surround.toml, and a naive substitution corrupts it).

WHAT IT DOES NOT TOUCH. config/preset_patches.json, and therefore the baked
presets in data/assets/presets/. A19: patches are applied at step 1, and step 4
reads the baked seed JSON, so a preset change does NOT take effect on --steps 4
and a preset bracket run this way returns byte-identical arms. [surround] keys
are different -- step 4 reads them straight from the config dir, so they
isolate cleanly (A20). Keep it that way: if a future sweep needs a preset key,
it needs --steps 1,4 and it mutates SHARED state.

ISOLATION. Each arm gets its own copied config dir (GROWPY_CONFIG) and its own
output dir ([general] output_dir), so arms never clobber one another and the
shared data/output/forest/ that Path B consumes is left alone. data/assets is
NOT redirectable and is read-only here.

RESUMABLE. An arm whose rows are already in sweep_results.csv with status OK is
skipped, so an interrupted sweep continues where it stopped rather than redoing
17 hours of work. A FAILED arm is NOT treated as done and will be retried.
`--redo` forces everything.

PRUNED AS IT GOES. After an arm is measured and its rows flushed, its
`_stems_skeletal.usdc` and `_full_growth_data.json` files are deleted -- ~3 GB
per arm, ~126 GB over the sweep, none of which this sweep reads. The
`_full_assembly.usdc` files are KEPT, so a pruned arm can still be re-measured
without re-simulating. `--keep-all-output` disables it.

Usage
-----
    # validate the harness and measure real wall-clock on one arm
    python growpy-sweep-surround-density --species "European beech" \
        --verify-only

    # the coarse pass -- each species bracketed around its OWN fitted density
    python growpy-sweep-surround-density --all --dry-run
    python growpy-sweep-surround-density --all

    # after an interruption: the same command resumes
    python growpy-sweep-surround-density --all

    # the replication pass, once the coarse pass has located a band
    python growpy-sweep-surround-density --species "European beech" \
        --densities 0.80 0.90 --seeds 512 999 7
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Scratch, not a deliverable: every path below lives under data/tmp/, which the
# project treats as deletable run scratch. Only the RESULT of this sweep -- the
# values written into [surround.density_per_species_radius] -- is durable.
DEFAULT_WORK_DIR = REPO / "data" / "tmp" / "surround_density_sweep"
HERE = DEFAULT_WORK_DIR
CFG_ROOT = HERE / "cfg"
OUT_ROOT = HERE / "out"
LOG_ROOT = HERE / "logs"
RESULTS = HERE / "sweep_results.csv"

# The production ladder and radius set. Held fixed across every arm (A24/A28).
STAGES = ["h05m", "h10m", "h15m", "h20m", "h25m"]
RADII = [8.0, 16.0]

# The 11 dataset-flagged species, as config/tree_asset_lookup.csv spells them.
# The CSV name is what --species matches; the output directory is the
# lowercased, underscored form, and --list prints a third spelling that the
# lookup rejects outright. Do not "simplify" these strings.
ALL_SPECIES = [
    "European beech",
    "Norway spruce",
    "Scots pine",
    "Silver fir",
    "European oak",
    "Common ash",
    "Silver birch",
    "Sycamore maple",
    "Small-leaved linden",
    "Wild cherry",
    "Douglas fir",
]

# Sharma et al. 2017, Silva Fennica 51(5):1740 (n=5526 spruce, 5666 beech), plus
# the companion HCB model in PLOS One 12(10):e0186394. Reported here only so the
# summary can flag which cells land inside the band -- the sweep does not select
# on them automatically, because A30 measured crown ratio carrying +/-0.30 seed
# noise against a band only 0.16 wide.
CROWN_RATIO_BAND = (0.52, 0.68)

# The committed r08 fits, as config/surround.toml carries them. Not values to
# trust -- the whole point of this sweep is that they were measured against a
# shell distance the matrix no longer uses -- but they are the best available
# estimate of WHERE each species' threshold sits, and that is what the bracket
# needs.
#
# WHY A PER-SPECIES BRACKET RATHER THAN ONE GLOBAL GRID. Measured on the
# 2026-09-10 pilot: beech at density 0.45 (a plausible-looking global grid
# point, and half its own fitted 0.9) produced h15 DBH of 41 / 36 / 41 cm at
# r05 / r10 / r20. Two things are wrong with that and either alone rules the
# arm out.
#
#   The COMPETITION GRADIENT COLLAPSES. At the committed 0.9 the same stage
#   reads 11 / 20 / 32 cm -- monotonic, and the reason three radii are three
#   distinct variants at all. At 0.45 it is not even monotonic. A shell that
#   weak stops discriminating between radii, which defeats the matrix.
#
#   It is also ~4x the allometric target (~10.4 cm at h15), and A12 holds r05
#   to that curve.
#
#   And it is RUINOUSLY SLOW. Growth went from ~1.15 s/cycle to 16-50 s/cycle
#   as the tree ballooned -- an arm at 0.45 runs >1.5 h against ~16 min at 0.9.
#   Grove rebuilds .faces/.points on every access (A8), so cost scales hard
#   with tree size. A global low-end grid would have spent most of the sweep's
#   wall clock on arms that were never admissible.
#
# So each species is bracketed around its own fitted value instead. Same number
# of arms, all of them near a plausible threshold, and none of them enormous.
FITTED_R08 = {
    "european_beech": 0.90,
    "small_leaved_linden": 0.90,
    "common_ash": 0.75,
    "norway_spruce": 0.70,
    "silver_fir": 0.70,
    "wild_cherry": 0.70,
    "sycamore_maple": 0.65,
    "silver_birch": 0.60,
    "scots_pine": 0.55,
    "european_oak": 0.45,
    "douglas_fir": 0.38,
}

# A SINGLE GLOBAL DENSITY RANGE, owner-set 2026-09-11: 0.75 to 0.95 inclusive.
#
# This replaces the per-species bracket around each fitted value. Two reasons it
# is better, and one caveat.
#
# The fitted values spanned 0.38 to 0.90, so the old bracket reached as low as
# 0.28. Everything measured says that end is wrong: the low arm was INADMISSIBLE
# in every species tested -- beech 0.8 inverted its DBH gradient, spruce 0.6 and
# pine 0.45 left the crown ratio far out of band, fir 0.6 failed the gate -- and
# it was also the most expensive arm by 3-10x, because a weak shell means a big
# tree and Grove's per-access rebuild scales with size. So this range is the
# CHEAP end as well as the plausible one.
#
# THE FLOOR IS 0.55, not 0.75. Two of the four species measured so far have their
# optimum below 0.75: norway_spruce lands in band at 0.70 (ratio 0.57) and
# scots_pine crosses between 0.55 and 0.65. A 0.75 floor would have excluded
# both. Those were measured at the tighter [5,10,20] radii and a wider shell
# competes less, so the optima should shift UP at [8,16] -- but not necessarily
# by the 0.05-0.15 needed to clear 0.75, and that is not worth betting a run on.
# 0.50 is the hard minimum the owner set; 0.55 is the first step above it.
#
# THREE ARMS, step 0.20: 0.55 / 0.75 / 0.95. The full range at finer resolution
# is not affordable at these radii -- one arm at the CHEAP end of the density
# range measured 93 min at [8,16] against 9 min for the same arm at [5,10,20],
# because both radii now run the full ladder and the trees are correspondingly
# larger. Five arms projected to 55-140 h.
#
# THIS IS A COARSE PASS AND CANNOT RESOLVE THE BAND. The response is steep --
# scots_pine moves crown ratio 0.87 -> 0.22 across a single 0.10 step, jumping
# clean over a target band only 0.16 wide. So a 0.10 step BRACKETS the crossing;
# it does not find it. Refine at 0.05 or finer around whichever pair of arms
# straddles the band, per species. Two stages at 0.10 cost less than one stage at
# 0.05 over a range wide enough to contain every optimum.
#
# CAVEAT worth watching in the results: for douglas_fir (fitted 0.38),
# european_oak (0.45), scots_pine (0.55) and silver_birch (0.60) this range sits
# well ABOVE their fitted value, and over-density crushes the crown -- beech at
# 0.95 reads ratio 0.25 against a 0.52-0.68 target. If those species come out
# uniformly over-suppressed at 0.75, the range is wrong for them specifically,
# not the species. Note also those fitted values are themselves suspect: they
# were measured with the old twig population and the broken drop rates.
DENSITY_RANGE = (0.55, 0.95)
DENSITY_STEP = 0.20

# Kept only so a caller can still reproduce a pre-2026-09-11 per-species bracket
# via --densities; nothing reads it by default any more.
FITTED_R08 = {
    "european_beech": 0.90,
    "small_leaved_linden": 0.90,
    "common_ash": 0.75,
    "norway_spruce": 0.70,
    "silver_fir": 0.70,
    "wild_cherry": 0.70,
    "sycamore_maple": 0.65,
    "silver_birch": 0.60,
    "scots_pine": 0.55,
    "european_oak": 0.45,
    "douglas_fir": 0.38,
}


def default_densities() -> list[float]:
    """The density arms every species is swept over."""
    lo, hi = DENSITY_RANGE
    n = round((hi - lo) / DENSITY_STEP)
    return [round(lo + i * DENSITY_STEP, 2) for i in range(n + 1)]

# Assembly filename shape, copied from crown_metrics._NAME so DBH can be read
# back off the name the tool measured. Groups: species, radius, height, DBH.
ASSEMBLY_NAME = re.compile(r"^(.+?)_r(\d+)_h(\d+)m_d(\d+)cm_", re.IGNORECASE)


def crown_fill(metrics: dict) -> float | None:
    """Twig attachment points per m3 of crown -- the interior-fill measure.

    WHY THIS REPLACES LAI (owner decision 2026-09-10). Leaves are placed by PVE
    in Unreal now, so the leaf area growpy exports is not the deliverable and
    LAI cannot confirm a crown. Crown SHAPE is the deliverable, and that is
    structure.

    But crown_ratio and crown_d_over_h alone do not confirm it either: both are
    ENVELOPE percentiles (crown_base is the 2nd percentile of twig height,
    crown_diameter the 95th of horizontal radius), so a crown that has been
    hollowed from the inside still measures a perfect envelope. That is not a
    hypothetical -- A23 measured exactly it on the silver fir, where
    drop_shaded dropped branches from INSIDE the crown and the ratio barely
    moved while the foliage went.

    So the fill measure has to be count-based and interior-sensitive:
    n_twigs (Grove's own attachment points, now that nothing adds or removes
    them) over the crown's own volume, taken as a cylinder of the measured
    diameter and crown length.

    A cylinder is deliberately crude. There is no published target for this
    number and it is not meant to be compared with literature -- only between
    ARMS of the same species, where the shape assumption cancels. Read it as a
    ratio, never as an absolute.
    """
    d = metrics.get("crown_diameter_m")
    h = metrics.get("height_m")
    base = metrics.get("crown_base_m")
    n = metrics.get("n_twigs")
    if not d or h is None or base is None or not n:
        return None
    crown_length = h - base
    if crown_length <= 0:
        return None
    volume = math.pi * (d / 2.0) ** 2 * crown_length
    return round(n / volume, 1) if volume > 0 else None


def species_dir(species: str) -> str:
    return species.lower().replace(" ", "_").replace("-", "_")


def _strip_tables(text: str, prefixes: tuple[str, ...]) -> str:
    """Drop whole TOML tables whose header starts with any of ``prefixes``.

    Line-based, not a regex. A20 recorded the failure mode: the table names
    also appear inside surround.toml's own comment prose, and a substitution
    anchored loosely enough to match the header also matches the prose. Here a
    line only counts as a header if it starts with '[' at column 0, and only
    the lines between one matching header and the next header are dropped.
    """
    out: list[str] = []
    dropping = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        is_header = stripped.startswith("[") and not stripped.startswith("[[")
        if is_header:
            name = stripped[1:].split("]", 1)[0].strip()
            dropping = any(
                name == p or name.startswith(p + ".") for p in prefixes
            )
        if not dropping:
            out.append(line)
    return "".join(out)


def _set_scalar(text: str, key: str, value: str) -> str:
    """Replace the first top-level ``key = ...`` assignment, at column 0 only."""
    out: list[str] = []
    done = False
    for line in text.splitlines(keepends=True):
        if not done and line.startswith(f"{key} ") or (
            not done and line.startswith(f"{key}=")
        ):
            head = line.split("=", 1)[0]
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            out.append(f"{head}= {value}{eol}")
            done = True
        else:
            out.append(line)
    if not done:
        raise SystemExit(f"key {key!r} not found at column 0 -- refusing to guess")
    return "".join(out)


def build_arm_config(arm: str, density: float, seed: int, out_dir: Path,
                     cycle_limit: int | None = None) -> Path:
    """Copy config/ and set exactly the three things an arm varies."""
    cfg = CFG_ROOT / arm
    if cfg.exists():
        shutil.rmtree(cfg)
    shutil.copytree(REPO / "config", cfg)

    surround = cfg / "surround.toml"
    text = surround.read_text(encoding="utf-8")
    # Strip both per-species tables so the global density is the only lever.
    # density_per_species_radius is nested (one sub-table per species), which is
    # why the prefix match has to cover 'name.startswith(prefix + ".")'.
    text = _strip_tables(
        text,
        (
            "surround.density_per_species",
            "surround.density_per_species_radius",
        ),
    )
    text = _set_scalar(text, "density", f"{density}")
    text = _set_scalar(text, "radii", "[" + ", ".join(str(r) for r in RADII) + "]")
    surround.write_text(text, encoding="utf-8")

    if cycle_limit:
        # THE lever that bounds an arm's wall clock. --max-height only bounds
        # which stages are exported: once every milestone is captured the
        # simulation keeps running to this limit or a plateau, and on a weak
        # shell the tree never plateaus. Measured 2026-09-11: an arm wrote its
        # last assembly at 13:35 and was still burning CPU two hours later with
        # nothing left to produce. dataset_pipeline has no CLI flag for this, so
        # it goes in the arm's own config.
        forest_toml = cfg / "forest.toml"
        ftext = forest_toml.read_text(encoding="utf-8")
        ftext = _set_scalar(ftext, "growth_cycle_limit", str(cycle_limit))
        forest_toml.write_text(ftext, encoding="utf-8")

    general = cfg / "general.toml"
    gtext = general.read_text(encoding="utf-8")
    gtext = _set_scalar(gtext, "random_seed", str(seed))
    gtext = _set_scalar(
        gtext, "output_dir", '"' + out_dir.as_posix() + '"'
    )
    general.write_text(gtext, encoding="utf-8")
    return cfg


def verify_arm(cfg: Path, density: float, seed: int, out_dir: Path) -> dict:
    """Print back what the arm's config actually resolves to, before running.

    A35 is the reason this is not optional. A 2026-09-09 cutoff sweep edited the
    wrong species-keyed table, produced a full table of plausible-looking
    nonsense, and was only caught when one crown vanished entirely. Assert the
    knob you meant to turn moved, AND that the ones you did not mean to turn
    did not.
    """
    script = (
        "import json\n"
        "from growpy.config import get_config\n"
        "c = get_config()\n"
        "print(json.dumps({\n"
        "  'density': c.surround_density,\n"
        "  'radii': c.surround_radii,\n"
        "  'per_species': c.surround_density_per_species,\n"
        "  'per_species_radius': c.surround_density_per_species_radius,\n"
        "  'grow': c.surround_grow,\n"
        "  'grow_per_species': c.surround_grow_per_species,\n"
        "  'height': c.surround_height,\n"
        "  'seed': c.random_seed,\n"
        "  'output_dir': str(c.output_dir),\n"
        "  'twig_density': c.export_twig_density,\n"
        "  'twig_density_per_species': c.export_twig_density_per_species,\n"
        "  'twig_recovery': c.export_twig_recovery,\n"
        "  'max_assembly_instances': c.export_max_assembly_instances,\n"
        "  'cutoff_per_species': c.quality_build_cutoff_thickness_per_species,\n"
        "}))\n"
    )
    env = dict(os.environ, GROWPY_CONFIG=str(cfg))
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=REPO, env=env,
    )
    line = ""
    for candidate in proc.stdout.splitlines():
        if candidate.startswith("{"):
            line = candidate
    if not line:
        raise SystemExit(
            f"could not read back arm config {cfg}:\n{proc.stdout}\n{proc.stderr}"
        )
    got = json.loads(line)

    problems = []
    if abs(got["density"] - density) > 1e-9:
        problems.append(f"density is {got['density']}, expected {density}")
    if got["radii"] != RADII:
        problems.append(f"radii are {got['radii']}, expected {RADII}")
    if got["per_species"]:
        problems.append(f"per-species density table not stripped: {got['per_species']}")
    if got["per_species_radius"]:
        problems.append(f"per-radius table not stripped: {got['per_species_radius']}")
    if got["seed"] != seed:
        problems.append(f"seed is {got['seed']}, expected {seed}")
    if Path(got["output_dir"]).resolve() != out_dir.resolve():
        problems.append(f"output_dir is {got['output_dir']}, expected {out_dir}")
    # The knobs this sweep must NOT have moved (2026-09-10 owner decision).
    if got["twig_density"] != 1.0 or got["twig_density_per_species"]:
        problems.append(
            "crown density correction is back on: "
            f"twig_density={got['twig_density']} "
            f"per_species={got['twig_density_per_species']}"
        )
    if got["twig_recovery"]:
        problems.append("twig_recovery is on; it must stay off")
    if got["cutoff_per_species"] != {"silver_birch": 0.0025}:
        problems.append(
            f"cutoff override table changed: {got['cutoff_per_species']}"
        )
    if problems:
        raise SystemExit("arm config is wrong:\n  " + "\n  ".join(problems))
    return got


def run_arm(species: str, cfg: Path, out_dir: Path, log: Path,
            max_height: float | None = None) -> tuple[int, float]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GROWPY_CONFIG=str(cfg))
    started = time.time()
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [
                sys.executable, "src/growpy/cli/dataset_pipeline.py",
                "--species", species,
                "--steps", "4",
                "--workers", "1",
                # Inspection aids only, and together a large share of a run.
                "--no-icons", "--no-previews", "--no-export-control",
                "-v",
                # Bracketing a preset key does not need the top of the ladder,
                # and the top is where the cost is: a gentle drop ramp keeps the
                # tree bushy, and Grove's per-access rebuild took one arm to
                # 143 s/cycle past h20. Capping the height keeps a bracket arm
                # to minutes instead of hours.
                *(["--max-height", str(max_height)] if max_height else []),
            ],
            stdout=fh, stderr=subprocess.STDOUT, cwd=REPO, env=env,
        )
    return proc.returncode, time.time() - started


def measure_arm(out_dir: Path, stage: str, json_out: Path) -> list[dict]:
    """Run crown_metrics for one stage and flatten what it writes.

    crown_metrics emits a NESTED mapping, species -> radius -> metrics, not a
    list, and publishes these names: height_m, crown_diameter_m, crown_base_m,
    crown_ratio, crown_d_over_h, crown_projection_m2, leaf_area_m2, lai,
    n_twigs. It does NOT carry DBH -- that exists only in the assembly
    filename -- so it is recovered here with the same regex the tool uses, and
    matched on (species dir, radius) the same way the tool keys its rows.

    crown_d_over_h is worth keeping alongside crown_ratio: the published
    targets are a PAIR (crown diameter / height ~0.30 for beech, ~0.22 for
    spruce, Sharma et al. 2017), and a density that fixes the ratio while
    pushing the width the wrong way is not a fit -- A21 measured exactly that
    on the fir, where a static shell moved diameter/height 0.21 -> 0.37.
    """
    json_out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "src/growpy/tools/crown_metrics.py",
            str(out_dir), "--stage", stage, "--json", str(json_out),
        ],
        capture_output=True, text=True, cwd=REPO,
    )
    if not json_out.exists():
        return []
    try:
        data = json.loads(json_out.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    dbh: dict[tuple[str, int], int] = {}
    for f in out_dir.glob(f"*/r*/*_{stage}_*_full_assembly.usd*"):
        m = ASSEMBLY_NAME.match(f.name)
        if m:
            dbh[(f.parts[-3], int(m.group(2)))] = int(m.group(4))

    rows: list[dict] = []
    for sp, per_radius in data.items():
        for radius, metrics in per_radius.items():
            row = {"species": sp, "radius": int(radius),
                   "dbh_cm": dbh.get((sp, int(radius))), **metrics}
            row["twigs_per_m3"] = crown_fill(row)
            rows.append(row)
    return rows


PRUNE_SUFFIXES = ("_stems_skeletal.usdc", "_full_growth_data.json")


def already_measured() -> set[tuple[str, float, int]]:
    """(species_dir, density, seed) triples that already have rows in RESULTS.

    Only arms whose run reported OK count as done. A FAILED arm is left in the
    queue so a resume retries it rather than silently accepting the gap.
    """
    if not RESULTS.exists():
        return set()
    done: set[tuple[str, float, int]] = set()
    with RESULTS.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("status") or "").strip() != "OK":
                continue
            try:
                done.add((row["species"], float(row["density"]), int(row["seed"])))
            except (KeyError, ValueError):
                continue
    return done


def prune_arm(out_dir: Path) -> tuple[int, float]:
    """Delete what the sweep will never read again; keep it re-measurable.

    An arm produces ~3 GB, and 42 of them would be ~126 GB. Almost all of it is
    weight this sweep does not use: per stage a ~100 MB `_stems_skeletal.usdc`
    and a ~25 MB `_full_growth_data.json`. Those are the DATASET deliverables
    (Path B consumes them) but a calibration arm's copies are throwaway.

    What is KEPT is the `_full_assembly.usdc` files, ~0.5 MB each, because that
    is the only thing `crown_metrics` reads. So a pruned arm can still be
    re-measured without re-simulating it -- which matters, since re-running one
    costs 20-30 minutes.
    """
    removed, freed = 0, 0.0
    for f in out_dir.rglob("*"):
        if f.is_file() and f.name.endswith(PRUNE_SUFFIXES):
            try:
                freed += f.stat().st_size
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed, freed / (1024 ** 3)


ARM_DIR = re.compile(r"^(?P<species>.+)_d(?P<density>[0-9.]+)_s(?P<seed>\d+)$")


def remeasure(args) -> int:
    """Rebuild every row from the assemblies already on disk.

    The point of keeping `_full_assembly.usdc` through pruning: an arm costs
    20-30 minutes to simulate and seconds to measure, so a change to any crown
    metric can be applied to the whole sweep without re-running a single tree.

    Writes a NEW file rather than rewriting the live one. A sweep in progress
    holds sweep_results.csv open in append mode, and rewriting underneath that
    handle corrupts it.
    """
    out_root = args.work_dir / "out"
    dest = args.work_dir / "sweep_results_remeasured.csv"
    arm_dirs = sorted(d for d in out_root.glob("*") if d.is_dir())
    if not arm_dirs:
        raise SystemExit(f"no arm directories under {out_root}")

    print(f"[{datetime.now():%H:%M:%S}] REMEASURE: {len(arm_dirs)} arm(s) from "
          f"retained assemblies -> {dest.name}")
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "run_utc", "species", "density", "seed", "radius", "stage",
            "height_m", "dbh_cm", "crown_diameter_m", "crown_base_m",
            "crown_ratio", "crown_d_over_h", "n_twigs", "twigs_per_m3",
            "leaf_area_m2", "lai",
            "in_sharma_band", "elapsed_s", "status",
        ])
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        total = 0
        for d in arm_dirs:
            m = ARM_DIR.match(d.name)
            if not m:
                print(f"  skipped {d.name}: not an arm directory")
                continue
            wrote = 0
            for stage in STAGES:
                rows = measure_arm(
                    d, stage, args.work_dir / "metrics" / f"{d.name}_{stage}.json")
                for row in rows:
                    ratio = row.get("crown_ratio")
                    in_band = ("" if ratio is None else
                               CROWN_RATIO_BAND[0] <= ratio <= CROWN_RATIO_BAND[1])
                    writer.writerow([
                        stamp, row.get("species", m["species"]),
                        float(m["density"]), int(m["seed"]),
                        row.get("radius"), stage,
                        row.get("height_m"), row.get("dbh_cm"),
                        row.get("crown_diameter_m"), row.get("crown_base_m"),
                        ratio, row.get("crown_d_over_h"),
                        row.get("n_twigs"), row.get("twigs_per_m3"),
                        row.get("leaf_area_m2"), row.get("lai"),
                        in_band, "", "OK",
                    ])
                    wrote += 1
            total += wrote
            print(f"  {d.name:<40} {wrote:>3} cell(s)")
        fh.flush()
    print(f"[{datetime.now():%H:%M:%S}] REMEASURE: {total} cell(s) -> {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--species", nargs="+", help="CSV species name(s)")
    g.add_argument("--all", action="store_true", help="all 11 dataset species")
    ap.add_argument("--densities", nargs="+", type=float,
                    help="explicit density arms, applied to EVERY species. "
                         "Omit to bracket each species around its own fitted "
                         "threshold instead, which is what you want -- a "
                         f"defaults to {DENSITY_RANGE[0]}-{DENSITY_RANGE[1]} "
                         f"in steps of {DENSITY_STEP}, applied to every "
                         "species (see DENSITY_RANGE).")
    ap.add_argument("--seeds", nargs="+", type=int, default=[512])
    ap.add_argument("--verify-only", action="store_true",
                    help="build and check each arm's config, run nothing")
    ap.add_argument("--dry-run", action="store_true", help="list arms and exit")
    ap.add_argument("--growth-cycle-limit", type=int,
                    help="hard cap on growth cycles. THIS is what bounds an "
                         "arm's wall clock -- --max-height only bounds which "
                         "stages are exported.")
    ap.add_argument("--max-height", type=float,
                    help="cap the height ladder for this run (m). Use when "
                         "bracketing a preset key: the top of the ladder is "
                         "where the wall clock is spent.")
    ap.add_argument("--remeasure", action="store_true",
                    help="re-derive every row from the RETAINED assemblies "
                         "without re-simulating anything, and write them to a "
                         "fresh CSV. Use after changing a crown metric: the "
                         "arms cost hours, the measurement costs seconds. "
                         "Writes <work-dir>/sweep_results_remeasured.csv so a "
                         "running sweep's open handle on the live CSV is never "
                         "disturbed.")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR,
                    help="scratch directory for per-arm configs, output, "
                         "logs and the results CSV "
                         "(default: data/tmp/surround_density_sweep)")
    ap.add_argument("--redo", action="store_true",
                    help="re-run arms already present in sweep_results.csv "
                         "(default: skip them, so an interrupted sweep resumes)")
    ap.add_argument("--keep-all-output", action="store_true",
                    help="keep every file an arm produces. Default is to prune "
                         "the stems meshes and growth JSON once the arm has "
                         "been measured -- see prune_arm()")
    args = ap.parse_args()

    global HERE, CFG_ROOT, OUT_ROOT, LOG_ROOT, RESULTS
    HERE = args.work_dir
    CFG_ROOT, OUT_ROOT, LOG_ROOT = HERE / "cfg", HERE / "out", HERE / "logs"
    RESULTS = HERE / "sweep_results.csv"

    if args.remeasure:
        return remeasure(args)

    species_list = ALL_SPECIES if args.all else args.species
    arms = [
        (sp, d, s)
        for sp in species_list
        for d in (args.densities or default_densities())
        for s in args.seeds
    ]

    print(f"[{datetime.now():%H:%M:%S}] SWEEP: {len(arms)} arm(s) "
          f"= {len(species_list)} species x "
          + (f"{len(args.densities)} densities (explicit)"
             if args.densities else
             f"{len(default_densities())} densities "
             f"{DENSITY_RANGE[0]}-{DENSITY_RANGE[1]}")
          + f" x {len(args.seeds)} seed(s)")
    print(f"[{datetime.now():%H:%M:%S}] SWEEP: radii {RADII} held fixed on every "
          f"arm (A24/A28); one arm yields {len(RADII)} radius cells")
    if args.dry_run:
        for sp, d, s in arms:
            print(f"  {sp:22s} d={d:<5} seed={s}")
        return 0

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    new_file = not RESULTS.exists()

    # Resume: an arm already in the results file is not re-run. A 17-hour
    # sequential sweep will meet an interruption sooner or later -- a crash, an
    # OOM (A45: 26 GB per arm), a machine restart -- and redoing all 42 arms
    # each time makes it effectively un-finishable.
    done = already_measured()
    if done and not args.redo:
        skipping = [a for a in arms if (species_dir(a[0]), a[1], a[2]) in done]
        if skipping:
            print(f"[{datetime.now():%H:%M:%S}] SWEEP: resuming — skipping "
                  f"{len(skipping)} arm(s) already in {RESULTS.name}")
            arms = [a for a in arms if (species_dir(a[0]), a[1], a[2]) not in done]
    if not arms:
        print(f"[{datetime.now():%H:%M:%S}] SWEEP: nothing to do — every "
              f"requested arm is already measured (use --redo to force)")
        return 0

    fh = RESULTS.open("a", newline="", encoding="utf-8")
    writer = csv.writer(fh)
    if new_file:
        writer.writerow([
            "run_utc", "species", "density", "seed", "radius", "stage",
            "height_m", "dbh_cm", "crown_diameter_m", "crown_base_m",
            "crown_ratio", "crown_d_over_h", "n_twigs", "twigs_per_m3",
            "leaf_area_m2", "lai",
            "in_sharma_band", "elapsed_s", "status",
        ])
        fh.flush()

    for index, (sp, density, seed) in enumerate(arms, start=1):
        spd = species_dir(sp)
        arm = f"{spd}_d{density}_s{seed}"
        out_dir = OUT_ROOT / arm
        stamp = datetime.now(UTC).isoformat(timespec="seconds")

        print(f"[{datetime.now():%H:%M:%S}] ARM {index}/{len(arms)}: "
              f"{sp} density={density} seed={seed}")
        cfg = build_arm_config(arm, density, seed, out_dir,
                               cycle_limit=args.growth_cycle_limit)
        resolved = verify_arm(cfg, density, seed, out_dir)
        print(f"[{datetime.now():%H:%M:%S}]   VERIFIED: density="
              f"{resolved['density']} radii={resolved['radii']} "
              f"seed={resolved['seed']} twig_density={resolved['twig_density']} "
              f"recovery={resolved['twig_recovery']} "
              f"cap={resolved['max_assembly_instances']}")
        if args.verify_only:
            continue

        code, elapsed = run_arm(sp, cfg, out_dir, LOG_ROOT / f"{arm}.log",
                                max_height=args.max_height)
        status = "OK" if code == 0 else f"FAILED({code})"
        print(f"[{datetime.now():%H:%M:%S}]   RUN: {status} in {elapsed/60:.1f} min")

        wrote = 0
        for stage in STAGES:
            rows = measure_arm(out_dir, stage, HERE / "metrics" / f"{arm}_{stage}.json")
            for row in rows:
                ratio = row.get("crown_ratio")
                in_band = (
                    ""
                    if ratio is None
                    else CROWN_RATIO_BAND[0] <= ratio <= CROWN_RATIO_BAND[1]
                )
                writer.writerow([
                    stamp, row.get("species", spd), density, seed,
                    row.get("radius"), stage,
                    row.get("height_m"), row.get("dbh_cm"),
                    row.get("crown_diameter_m"), row.get("crown_base_m"),
                    ratio, row.get("crown_d_over_h"),
                    row.get("n_twigs"), row.get("twigs_per_m3"),
                    row.get("leaf_area_m2"), row.get("lai"),
                    in_band, round(elapsed, 1), status,
                ])
                wrote += 1
        fh.flush()
        print(f"[{datetime.now():%H:%M:%S}]   MEASURED: {wrote} cell(s) -> "
              f"{RESULTS.name}")

        # Prune AFTER the rows are flushed, so an interrupt between the two
        # leaves a measured arm rather than a pruned unmeasured one.
        if not args.keep_all_output and wrote:
            n, gb = prune_arm(out_dir)
            print(f"[{datetime.now():%H:%M:%S}]   PRUNED: {n} file(s), "
                  f"{gb:.2f} GB freed (assemblies kept, still re-measurable)")

    fh.close()
    print(f"[{datetime.now():%H:%M:%S}] SWEEP: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
