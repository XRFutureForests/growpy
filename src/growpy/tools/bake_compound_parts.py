"""Bake a species' compound foliage parts for the PVE palette (XRFF-463).

MegaPlants dresses a mature tree with 300-900 foliated BRANCH parts of
0.5-2.3 m, not with thousands of single twigs. This tool bakes that unit for a
species: a Grove tree of the species is grown headless, its crown is cut into
subtrees at a base-diameter threshold, and one *typical* foliated subtree per
span bin is welded -- woody mesh plus the species' twig at every Grove twig
placement -- into a single mesh. The result is a small, size-graded palette
(``<species>_compound_p00..p04``) that PVE's distributor places by Scale, tip
cap and generation exactly as it places Epic's own parts.

It reuses the growth, model, cut and weld of ``harvest_compound_parts`` (the
USD-route library) but chooses the prototypes differently. The harvester
k-medoid-clusters *every* cut point of one tree for coverage, which on a
conifer seats medoids on bare stubs and on beech produced 21 cm stubs carrying
three twigs. PVE needs the opposite: a few well-foliated parts of graded size,
so the members are binned by span and the one nearest each bin's median twig
count and span is baked.

Welded twig: the species' converted twig variant whose leaf area is nearest
``--weld-area`` (0.01 m2 by default). A full conifer spray (0.109 m2, ~100k
faces) welded 50 times is a 5 M-face part; the 0.0089 m2 sub-spray gives
0.2-0.5 m2 parts of 0.2-0.5 M faces, Epic's unit on both area and weight. Leaf
area per part is REPORTED in a ``<name>_leaf_area_geom.json`` sidecar (the
same shape the twig converter writes) and is never a target.

Outputs, under ``data/assets/compound_parts/``:

* ``<species>_compound_pNN_static.usda`` / ``_skeletal.usda`` -- the parts, in
  growpy's twig frame (base at the origin, axis +X, up +Z), so the PVE asset
  script's X->Z re-frame applies to them unchanged
* ``<species>_compound_pNN_leaf_area_geom.json`` -- leaf area per part
* ``<species>_pve_palette.json`` -- the manifest ``pve_asset_script`` resolves
  ``palette = "compound"`` from

Runs as the last stage of dataset step 2 (``growpy-convert-twigs`` writes the
twig this welds), and standalone::

    growpy-bake-compound-parts --dataset
    growpy-bake-compound-parts --species silver_fir european_beech --height 15
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

logger = logging.getLogger("growpy.bake_compound_parts")

# The tree the parts are cut from. 15 m is the middle of the h05-h25 ladder;
# a part is a crown FRAGMENT, so the tree's own size matters only through the
# span distribution the bins select from.
DEFAULT_HEIGHT_M = 15.0
DEFAULT_SEED = 42
DEFAULT_CYCLE_CAP = 80

# Cut and band, from the fir bake of 2026-09-15 (XRFF-463): a 3 cm base cut
# inside a <=200 tips / <=2 m span / <=150 twigs band gave 5,032 cut points on
# a 15 m fir, 1,319 of them carrying >= 8 twigs.
DEFAULT_CUT_DIAMETER_M = 0.03
DEFAULT_MAX_TIPS = 200
DEFAULT_MAX_SPAN_M = 2.0
DEFAULT_MAX_TWIGS = 150
DEFAULT_MIN_TWIGS = 8

# Span bins (m), one part each. Epic's Branch family on an 18 m spruce tops
# out at 1.1 m and its broadleaf complexes run 0.5-2.3 m, so the ladder spans
# both; the graph plan decides which tiers a species' fill layer draws from.
DEFAULT_BINS: tuple[tuple[float, float], ...] = (
    (0.25, 0.45),
    (0.45, 0.70),
    (0.70, 1.00),
    (1.00, 1.40),
    (1.40, 2.00),
)

DEFAULT_WELD_AREA_M2 = 0.01

MANIFEST_SCHEMA = 1


def _twig_variants(species: str) -> list[tuple[Path, float]]:
    """Every converted ``*_static.usda`` of the species' twig with its leaf area.

    Leaf area comes from the wood-corrected ``_leaf_area_geom.json`` sidecar
    the converter writes beside each variant (XRFF-274); a variant without one
    is skipped rather than guessed at.
    """
    from growpy.config.paths import get_twig_files_by_type

    variants = []
    for stem, paths in get_twig_files_by_type(species).items():
        if not stem.endswith("_static"):
            continue
        static = paths[0]
        sidecar = static.parent / f"{stem[: -len('_static')]}_leaf_area_geom.json"
        if not sidecar.is_file():
            logger.warning(
                "%s: no leaf-area sidecar for %s, skipping", species, static.name
            )
            continue
        area = float(json.loads(sidecar.read_text(encoding="utf-8"))["leaf_area_m2"])
        if area > 0.0:
            variants.append((static, area))
    return variants


def resolve_weld_twig(species: str, weld_area_m2: float) -> tuple[Path, float]:
    """The twig variant welded into every part: nearest ``weld_area_m2`` in leaf area.

    Raises:
        FileNotFoundError: If the species has no converted twig with a
            leaf-area sidecar -- run ``growpy-convert-twigs`` first.
    """
    variants = _twig_variants(species)
    if not variants:
        raise FileNotFoundError(
            f"{species}: no converted twig variant with a _leaf_area_geom.json "
            f"sidecar under data/assets/twigs/ -- run growpy-convert-twigs first"
        )
    return min(variants, key=lambda v: abs(v[1] - weld_area_m2))


def choose_typical_members(
    candidates: list[int],
    metrics: dict[str, list],
    twig_totals: list[int],
    bins: tuple[tuple[float, float], ...],
) -> list[tuple[tuple[float, float], int, dict]]:
    """One subtree per span bin: nearest the bin's median twig count and span."""
    chosen = []
    for lo, hi in bins:
        members = [i for i in candidates if lo <= metrics["span"][i] < hi]
        if not members:
            logger.info("  bin %.2f-%.2f m: no foliated member, skipped", lo, hi)
            continue
        counts = sorted(twig_totals[i] for i in members)
        median_twigs = counts[len(counts) // 2]
        median_span = statistics.median(metrics["span"][i] for i in members)
        pick = min(
            members,
            key=lambda i: (
                abs(twig_totals[i] - median_twigs) / max(median_twigs, 1)
                + abs(metrics["span"][i] - median_span) / max(median_span, 1e-6)
            ),
        )
        chosen.append(
            (
                (lo, hi),
                pick,
                {
                    "members": len(members),
                    "median_twigs": median_twigs,
                    "twigs_min": counts[0],
                    "twigs_max": counts[-1],
                    "median_span_m": median_span,
                },
            )
        )
        logger.info(
            "  bin %.2f-%.2f m: %d members, median %d twigs / %.2f m -> branch %d "
            "(%.2f m, %d twigs)",
            lo,
            hi,
            len(members),
            median_twigs,
            median_span,
            pick,
            metrics["span"][pick],
            twig_totals[pick],
        )
    return chosen


def bake_species(
    species: str,
    output_dir: Path,
    *,
    height_m: float = DEFAULT_HEIGHT_M,
    seed: int = DEFAULT_SEED,
    cycle_cap: int = DEFAULT_CYCLE_CAP,
    cut_diameter_m: float = DEFAULT_CUT_DIAMETER_M,
    max_tips: int = DEFAULT_MAX_TIPS,
    max_span_m: float = DEFAULT_MAX_SPAN_M,
    max_twigs: int = DEFAULT_MAX_TWIGS,
    min_twigs: int = DEFAULT_MIN_TWIGS,
    bins: tuple[tuple[float, float], ...] = DEFAULT_BINS,
    weld_area_m2: float = DEFAULT_WELD_AREA_M2,
) -> dict:
    """Grow, cut, choose and bake one species. Returns the written manifest."""
    from growpy.tools.harvest_compound_parts import (
        LIVING_TWIG_TYPES,
        bake_prototypes,
        build_reference_model,
        count_subtree_twigs,
        find_cut_set_adaptive,
        flatten_branches,
        grow_grove,
        precompute_subtrees,
        subtree_stats,
    )

    twig_usd, twig_area = resolve_weld_twig(species, weld_area_m2)
    logger.info(
        "%s: welding %s (%.4f m2 leaf) into every part",
        species,
        twig_usd.name,
        twig_area,
    )

    t0 = time.monotonic()
    grove = grow_grove(species, cycle_cap, seed, height_m)
    tree = grove.trees[0]
    records = flatten_branches(tree)
    metrics = precompute_subtrees(records)
    model = build_reference_model(grove)
    twig_totals = count_subtree_twigs(model, records)
    logger.info(
        "%s: grown and built in %.0f s -- %d branches, %d living twigs",
        species,
        time.monotonic() - t0,
        len(records),
        twig_totals[0],
    )

    cut = find_cut_set_adaptive(
        records,
        metrics,
        cut_diameter_m / 2.0,
        max_tips,
        max_span_m,
        twig_totals,
        max_twigs,
    )
    foliated = [i for i in cut if twig_totals[i] >= min_twigs]
    logger.info(
        "%s: cut %.3f m, band tips<=%d span<=%.1f twigs<=%d -> %d cut points, "
        "%d with >= %d twigs",
        species,
        cut_diameter_m,
        max_tips,
        max_span_m,
        max_twigs,
        len(cut),
        len(foliated),
        min_twigs,
    )
    chosen = choose_typical_members(foliated, metrics, twig_totals, bins)
    if not chosen:
        raise RuntimeError(
            f"{species}: no span bin has a foliated subtree at cut {cut_diameter_m} m; "
            f"widen the bins or lower --min-twigs"
        )

    t1 = time.monotonic()
    report = bake_prototypes(
        model,
        records,
        metrics,
        [pick for _, pick, _ in chosen],
        dict.fromkeys(LIVING_TWIG_TYPES, twig_usd),
        output_dir,
        species,
    )
    prototypes = []
    for (span_bin, pick, bin_stats), row in zip(chosen, report, strict=True):
        leaf_area = row["welded_twigs"] * twig_area
        sidecar = output_dir / f"{row['name']}_leaf_area_geom.json"
        sidecar.write_text(
            json.dumps(
                {
                    "leaf_area_m2": leaf_area,
                    "welded_twigs": row["welded_twigs"],
                    "twig_leaf_area_m2": twig_area,
                    "twig_usd": twig_usd.name,
                    "source": "growpy-bake-compound-parts",
                },
                indent=1,
            ),
            encoding="utf-8",
        )
        stats = subtree_stats(records, metrics, pick, twig_totals)
        prototypes.append(
            {
                "name": row["name"],
                "file": Path(row["file"]).name,
                "skeletal_file": Path(row["skeletal_file"]).name,
                "span_bin_m": list(span_bin),
                "span_m": stats["span"],
                "tips": stats["tips"],
                "max_depth": stats["max_depth"],
                "welded_twigs": row["welded_twigs"],
                "faces": row["faces"],
                "file_bytes": row["file_bytes"],
                "local_extent_m": row["local_extent"],
                "leaf_area_m2": leaf_area,
                "bin": bin_stats,
            }
        )
        logger.info(
            "  %s: span %.2f m, %d twigs, %d faces, %.1f MB, leaf %.3f m2",
            row["name"],
            stats["span"],
            row["welded_twigs"],
            row["faces"],
            row["file_bytes"] / 1e6,
            leaf_area,
        )
    logger.info(
        "%s: baked %d parts in %.0f s", species, len(prototypes), time.monotonic() - t1
    )

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "species": species,
        "target_height_m": height_m,
        "seed": seed,
        "cycle_cap": cycle_cap,
        "cut_diameter_m": cut_diameter_m,
        "max_tips": max_tips,
        "max_span_m": max_span_m,
        "max_twigs": max_twigs,
        "min_twigs": min_twigs,
        "bins": [list(b) for b in bins],
        "twig_usd": twig_usd.name,
        "twig_leaf_area_m2": twig_area,
        "branches": len(records),
        "living_twigs": twig_totals[0],
        "cut_points": len(cut),
        "foliated_cut_points": len(foliated),
        "prototypes": prototypes,
    }
    manifest_path = output_dir / f"{species}_pve_palette.json"
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    logger.info("%s: manifest %s", species, manifest_path)
    return manifest


def _dataset_species() -> list[str]:
    from growpy.pipelines.dataset_job_planner import list_all_species

    return list(list_all_species())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--species", nargs="+", help="standardized species names, e.g. silver_fir"
    )
    group.add_argument(
        "--dataset",
        action="store_true",
        help="every species flagged in tree_asset_lookup.csv's Dataset column",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--height", type=float, default=DEFAULT_HEIGHT_M)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cycle-cap", type=int, default=DEFAULT_CYCLE_CAP)
    parser.add_argument("--cut-diameter", type=float, default=DEFAULT_CUT_DIAMETER_M)
    parser.add_argument("--max-tips", type=int, default=DEFAULT_MAX_TIPS)
    parser.add_argument("--max-span", type=float, default=DEFAULT_MAX_SPAN_M)
    parser.add_argument("--max-twigs", type=int, default=DEFAULT_MAX_TWIGS)
    parser.add_argument("--min-twigs", type=int, default=DEFAULT_MIN_TWIGS)
    parser.add_argument("--weld-area", type=float, default=DEFAULT_WELD_AREA_M2)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    from growpy.config.paths import get_assets_directory

    output_dir = args.output_dir or get_assets_directory() / "compound_parts"
    output_dir.mkdir(parents=True, exist_ok=True)

    species_list = _dataset_species() if args.dataset else list(args.species)
    if not species_list:
        logger.error("no species selected")
        return 1

    failed = []
    for species in species_list:
        logger.info("== %s", species)
        try:
            bake_species(
                species,
                output_dir,
                height_m=args.height,
                seed=args.seed,
                cycle_cap=args.cycle_cap,
                cut_diameter_m=args.cut_diameter,
                max_tips=args.max_tips,
                max_span_m=args.max_span,
                max_twigs=args.max_twigs,
                min_twigs=args.min_twigs,
                weld_area_m2=args.weld_area,
            )
        except Exception as exc:  # one species must not take the others down
            logger.error("%s: bake failed: %s", species, exc, exc_info=args.verbose)
            failed.append(species)
    if failed:
        logger.error("compound bake failed for: %s", ", ".join(failed))
        return 1
    logger.info("compound parts baked for %d species", len(species_list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
