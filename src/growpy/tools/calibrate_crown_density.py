#!/usr/bin/env python3
"""Back-solve ``[export.twig_density_per_species]`` against published leaf area.

The method `config/forest.toml` documents, made repeatable:

1. Export the dataset at whatever densities are configured now. This step is
   load-bearing and the tool cannot check it: the ratio divides a leaf area
   measured from files on disk by a density read from the CURRENT config, so an
   export predating a config change silently yields a wrong suggestion. Seen in
   practice -- Douglas fir and Norway spruce exports made at 0.0753/0.0468 and
   read against a config since changed to 0.0399/0.0305 came out 1.89x and 1.53x
   off, exactly the density ratios. Re-export before calibrating.
2. For each exported tree, measure the crown's ONE-SIDED leaf area as
   ``sum(instances_i x prototype_leaf_area_i)`` straight off the assembly's
   PointInstancer -- the instance counts are what ``twig_density`` sets, and the
   per-prototype areas come from the twig sidecars.
3. Compare against Forrester et al. (2017), evaluated at each tree's OWN
   diameter rather than one number for the whole species.
4. New density = current x (target / measured), averaged over the trees.

Step 3 is what this adds over doing it by hand. The values in forest.toml before
this existed came from comparing a *mean over three surround radii* at one height
stage against a single 38.6 m2 figure -- the pooled-conifer equation evaluated at
d=18 cm -- while the trees themselves ranged d=14-29 cm. Forrester's leaf-area
coefficients now live in `pylometree` (model_type "leaf_area"), so each tree gets
its own target.

Two things this deliberately does NOT do. It does not edit forest.toml: the
suggested values are printed, because a density is a judgement about looks as
well as leaf area and forest.toml says so in its own comments. And it does not
re-open which Forrester form to use -- the diameter-only fit (eq. 3) is the one
`pylometree` registers, matching the AGB entries beside it.

Leaf-area basis
---------------
Prefers ``<prototype>_leaf_area_geom.json``, the topological leaf/wood split,
over ``<prototype>_leaf_area.json``, which tags leaves by MATERIAL and so counts
the woody shoot as leaf on any asset shipping a single material -- 8-35%
overstatement across the fir ladder. `growpy-convert-twigs` writes the geom
sidecar, so a clean run has it; an older run falls back, and the report says
which basis each species used.

Usage:
    growpy-calibrate-crown-density
    growpy-calibrate-crown-density --stage h15m --json out.json
    growpy-calibrate-crown-density --forest-dir data/output/forest --all-stages
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger("growpy.calibrate_crown_density")

# Species with no leaf-area equation of their own in Forrester Table A.5 fall
# back to a pooled fit. Conifer vs broadleaved is decided from the genus rather
# than guessed from a common name.
_CONIFER_GENERA = {
    "abies",
    "picea",
    "pinus",
    "pseudotsuga",
    "larix",
    "taxus",
    "tsuga",
    "juniperus",
    "cedrus",
    "thuja",
    "chamaecyparis",
    "sequoia",
}

_DBH_RE = re.compile(r"_d(\d+)cm", re.IGNORECASE)
_STAGE_RE = re.compile(r"_(h\d+m)", re.IGNORECASE)


def _species_lookup(csv_path: Path) -> dict[str, str]:
    """``standardized name -> scientific name`` for the dataset species."""
    out: dict[str, str] = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            std = (row.get("Standardized Name") or "").strip()
            sci = (row.get("Scientific Name") or "").strip()
            if std and sci:
                out[std] = sci
    return out


def leaf_area_by_prototype(twigs_root: Path) -> tuple[dict[str, float], set[str]]:
    """``normalised prototype name -> one-sided leaf area``, plus the geom set.

    Prototype prims are named with the underscores stripped, so the map is keyed
    that way and matched EXACTLY -- a suffix test prices the unsuffixed full
    spray (``pacificsilverfirfoliage``) as whichever variant ends in the same
    letter, which on the fir understated a crown by 48 m2.
    """
    areas: dict[str, float] = {}
    geom_backed: set[str] = set()
    for sidecar in sorted(twigs_root.glob("*/*_leaf_area.json")):
        stem = sidecar.name[: -len("_leaf_area.json")]
        areas[stem.replace("_", "").lower()] = float(
            json.loads(sidecar.read_text())["leaf_area_m2"]
        )
    for sidecar in sorted(twigs_root.glob("*/*_leaf_area_geom.json")):
        stem = sidecar.name[: -len("_leaf_area_geom.json")]
        key = stem.replace("_", "").lower()
        value = json.loads(sidecar.read_text()).get("leaf_area_m2")
        if value is not None:
            areas[key] = float(value)
            geom_backed.add(key)
    return areas, geom_backed


def measure_assembly(
    path: Path, areas: dict[str, float]
) -> tuple[float, int, list[str], set[str]]:
    """One-sided leaf area, instance count, unmatched prototypes, keys used."""
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise ValueError(f"could not open {path}")

    leaf_area = 0.0
    instances = 0
    unmatched: list[str] = []
    used: set[str] = set()
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.PointInstancer):
            continue
        pi = UsdGeom.PointInstancer(prim)
        indices = pi.GetProtoIndicesAttr().Get() or []
        names = [t.name for t in pi.GetPrototypesRel().GetTargets()]
        for index, count in Counter(indices).items():
            key = names[index].lower() if index < len(names) else ""
            if key in areas:
                leaf_area += count * areas[key]
                used.add(key)
            elif key not in unmatched:
                unmatched.append(key)
        instances += len(indices)
    return leaf_area, instances, unmatched, used


def _covers(entry: Any, dbh_cm: float) -> bool:
    """Was this equation fitted over a range that includes `dbh_cm`?"""
    d_min = entry.parameters.get("d_min")
    d_max = entry.parameters.get("d_max")
    if d_min is None or d_max is None:
        return True  # no range recorded: nothing to test against
    return d_min <= dbh_cm <= d_max


def forrester_leaf_area(scientific_name: str, dbh_cm: float) -> tuple[float, str, bool]:
    """Published one-sided leaf area. Returns ``(m2, model id, extrapolated)``.

    Prefers the species' own equation, but falls back to the pooled fit when the
    species one would EXTRAPOLATE and the pooled one covers the diameter. That
    is not a preference for pooling: a power law with beta 1.4-2.4 climbs
    steeply past its data, so a target from outside the fitted range measures
    the extrapolation rather than the crown. Prunus avium's leaf-area fit covers
    d 1-10 cm and Betula pendula's 1-14 cm, while the pooled broadleaved fit
    spans 0.1-88.2 cm and comfortably covers a mature tree of either.

    ``extrapolated`` stays True only when NO available equation covers the tree,
    so the caller can still refuse to trust the number.
    """
    from pylometree.registry.published import registry

    genus = scientific_name.split()[0].lower()
    pooled_key = "conifers" if genus in _CONIFER_GENERA else "broadleaved"
    pooled = registry.get(f"forrester2017_{pooled_key}_la")

    matches = [
        entry
        for entry in registry.query(model_type="leaf_area", species=scientific_name)
        if entry.species
    ]
    entry = matches[0] if matches else pooled
    if not _covers(entry, dbh_cm) and _covers(pooled, dbh_cm):
        entry = pooled
    return float(entry.fn(dsob=dbh_cm)), entry.model_id, not _covers(entry, dbh_cm)


def calibrate(
    forest_dir: Path,
    twigs_root: Path,
    lookup_csv: Path,
    stage: str | None,
) -> list[dict[str, Any]]:
    """Measure every exported tree and back-solve a density per species."""
    from growpy import get_config

    config = get_config()
    scientific = _species_lookup(lookup_csv)
    areas, geom_backed = leaf_area_by_prototype(twigs_root)

    report: list[dict[str, Any]] = []
    for species_dir in sorted(p for p in forest_dir.iterdir() if p.is_dir()):
        species = species_dir.name
        sci = scientific.get(species)
        if sci is None:
            logger.warning("%s: no Scientific Name in the lookup, skipped", species)
            continue

        trees: list[dict[str, Any]] = []
        used_keys: set[str] = set()
        for assembly in sorted(species_dir.glob("r*/*_full_assembly.usd*")):
            if stage and not re.search(rf"_{stage}_", assembly.name, re.IGNORECASE):
                continue
            dbh_match = _DBH_RE.search(assembly.name)
            if not dbh_match:
                logger.warning("%s: no DBH in the name, skipped", assembly.name)
                continue
            dbh = float(dbh_match.group(1))
            measured, instances, unmatched, used = measure_assembly(assembly, areas)
            used_keys |= used
            if unmatched:
                logger.warning(
                    "%s: %d prototype(s) with no leaf-area sidecar (%s) -- the "
                    "measured area is an UNDERCOUNT",
                    assembly.name,
                    len(unmatched),
                    ", ".join(unmatched[:3]),
                )
            target, model_id, extrapolated = forrester_leaf_area(sci, dbh)
            if extrapolated:
                logger.warning(
                    "%s: d=%.0f cm is outside the range %s was fitted over -- "
                    "its target is an extrapolation",
                    assembly.name,
                    dbh,
                    model_id,
                )
            stage_match = _STAGE_RE.search(assembly.name)
            trees.append(
                {
                    "file": assembly.name,
                    "stage": stage_match.group(1) if stage_match else None,
                    "dbh_cm": dbh,
                    "instances": instances,
                    "measured_m2": measured,
                    "target_m2": target,
                    "ratio": (measured / target) if target else float("nan"),
                    "model": model_id,
                    "extrapolated": extrapolated,
                }
            )

        if not trees:
            continue
        ratios = [t["ratio"] for t in trees if t["ratio"] == t["ratio"]]
        if not ratios:
            continue
        mean_ratio = sum(ratios) / len(ratios)
        current = config.get_twig_density_base(species)
        # "geom" only when EVERY prototype this species placed had a topological
        # sidecar -- a partial set would mix two bases in one number.
        basis = "geom" if used_keys and used_keys <= geom_backed else "material"
        report.append(
            {
                "species": species,
                "scientific_name": sci,
                "model": trees[0]["model"],
                "trees": trees,
                "mean_ratio": mean_ratio,
                "current_density": current,
                "suggested_density": (current / mean_ratio) if mean_ratio else current,
                "leaf_area_basis": basis,
                "extrapolated": any(t["extrapolated"] for t in trees),
            }
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Back-solve per-species crown density from exported assemblies "
            "against Forrester et al. (2017) leaf area."
        )
    )
    parser.add_argument(
        "--forest-dir",
        type=Path,
        default=Path("data/output/forest"),
        help="directory of exported species (default: data/output/forest)",
    )
    parser.add_argument(
        "--twigs-root",
        type=Path,
        default=Path("data/assets/twigs"),
        help="converted twig assets, for the leaf-area sidecars",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("config/tree_asset_lookup.csv"),
        help="species lookup, for the Scientific Name column",
    )
    parser.add_argument(
        "--stage",
        default="h15m",
        help=(
            "height stage to calibrate on (default h15m, the stage forest.toml "
            "pinned on deliberately). Conifers need more density at h05m, so one "
            "value cannot serve every stage -- see XRFF-273."
        ),
    )
    parser.add_argument(
        "--all-stages",
        action="store_true",
        help="use every exported stage instead of one",
    )
    parser.add_argument("--json", type=Path, help="also write the full report here")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.forest_dir.is_dir():
        logger.error("no such forest directory: %s", args.forest_dir)
        return 1

    report = calibrate(
        args.forest_dir,
        args.twigs_root,
        args.csv,
        None if args.all_stages else args.stage,
    )
    if not report:
        logger.error(
            "no assemblies measured -- run step 4 first, or check --stage against %s",
            args.forest_dir,
        )
        return 1

    logger.info(
        "\n%-22s %-9s %9s %9s %7s %10s %10s %s",
        "species",
        "basis",
        "measured",
        "target",
        "ratio",
        "current",
        "suggested",
        "note",
    )
    for row in report:
        measured = sum(t["measured_m2"] for t in row["trees"]) / len(row["trees"])
        target = sum(t["target_m2"] for t in row["trees"]) / len(row["trees"])
        note = []
        if row["extrapolated"]:
            note.append("EXTRAPOLATED")
        if not row["model"].startswith("forrester2017_") or row["model"] in {
            "forrester2017_conifers_la",
            "forrester2017_broadleaved_la",
            "forrester2017_all_species_la",
        }:
            note.append("pooled fit")
        logger.info(
            "%-22s %-9s %9.1f %9.1f %7.2f %10.4f %10.4f %s",
            row["species"],
            row["leaf_area_basis"],
            measured,
            target,
            row["mean_ratio"],
            row["current_density"],
            row["suggested_density"],
            ", ".join(note),
        )
    logger.info(
        "\n%d species over %d trees. Ratio is measured/target, so above 1 means "
        "the crown carries more leaf than published allometry says.",
        len(report),
        sum(len(r["trees"]) for r in report),
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2))
        logger.info("report written to %s", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
