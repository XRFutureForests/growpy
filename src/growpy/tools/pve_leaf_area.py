"""Report true leaf area for the calibrated PVE trees, scale correction included.

A count-based measurement -- instances times prototype area, or foliage
triangles times area per triangle -- cannot see instance scale, and leaf area
goes as scale squared. This reports ``mean(scale^2) x instances x prototype
area`` and prints the correction factor beside it, so a factor far from 1.0 is
visible rather than folded invisibly into a total.

    growpy-pve-leaf-area
    growpy-pve-leaf-area --species silver_fir --growth-json-dir path/to/jsons
    growpy-pve-leaf-area --scale-ramp 1.0 0.1     # what the engine default costs

With the shipped flat ramp the factor is 1.0 and this agrees exactly with the
count-based figure. That is precisely why it is tempting to skip -- and skipping
it is what makes the next non-flat ramp silent.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from growpy.config.pve_calibration import load_pve_calibration
from growpy.io.unreal.pve_distributor_model import measure_leaf_area
from growpy.io.unreal.pve_graph_builder import DistributorSpec, FoliageVectorSpec

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--species",
        nargs="*",
        help="standardized species names; default is every calibrated species",
    )
    parser.add_argument(
        "--growth-json-dir",
        type=Path,
        default=Path("data/tmp/pve_test/growthjson"),
        help="directory holding the growth JSONs named in the calibration",
    )
    parser.add_argument(
        "--scale-ramp",
        nargs=2,
        type=float,
        metavar=("START", "END"),
        default=None,
        help="override the shipped flat ramp, to see what a taper costs "
        "(the engine default is 1.0 0.1)",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=None,
        help="override the tracked config/pve_calibration.toml",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    calibration = load_pve_calibration(args.calibration)
    names = args.species or sorted(calibration.species)
    ramp = tuple(args.scale_ramp) if args.scale_ramp else (1.0, 1.0)

    print(
        f"{'species':<16}{'tree':<10}{'dens':>5}{'inst':>8}"
        f"{'factor':>9}{'area m2':>10}{'target':>9}{'delta':>8}"
    )
    print("-" * 74)

    total_area = total_target = 0.0
    missing: list[str] = []

    for name in names:
        try:
            species = calibration.for_species(name)
        except KeyError as err:
            missing.append(str(err))
            continue

        for tree_id in sorted(species.trees):
            tree = species.tree(tree_id)
            try:
                path = species.resolve_growth_json(args.growth_json_dir, tree_id)
            except FileNotFoundError as err:
                missing.append(str(err))
                continue

            resolved = species.resolve_density(tree_id)
            distributor = DistributorSpec(
                branch_density=resolved.density,
                relative_start=species.relative_start,
                phyllotaxy_formation=species.phyllotaxy_formation,
                scale_ramp=ramp,
                face=FoliageVectorSpec(kind="face", vector2="AXIS_AIM"),
                auto_align_end=False,
            )
            measured = measure_leaf_area(
                path, distributor, species.prototype_leaf_area_m2
            )
            delta = 100.0 * (measured.area_m2 / tree.target_m2 - 1.0)
            total_area += measured.area_m2
            total_target += tree.target_m2
            print(
                f"{name:<16}{tree_id:<10}{resolved.density:>5}"
                f"{measured.instances:>8}{measured.correction_factor:>9.4f}"
                f"{measured.area_m2:>10.2f}{tree.target_m2:>9.2f}{delta:>+7.1f}%"
            )

    for line in missing:
        logger.warning("skipped: %s", line)

    if total_target <= 0:
        logger.error("nothing measured")
        return 1

    print("-" * 74)
    print(
        f"{'TOTAL':<16}{'':<10}{'':>5}{'':>8}{'':>9}"
        f"{total_area:>10.2f}{total_target:>9.2f}"
        f"{100.0 * (total_area / total_target - 1.0):>+7.1f}%"
    )
    if ramp != (1.0, 1.0):
        print(
            f"\nScale ramp {ramp} is not flat. A count-based measurement would "
            f"have reported the scale-1.0 figure and been wrong by the factor "
            f"column above."
        )
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
