"""Build per-species height-DBH allometry artifacts from yield tables.

Fits ``DBH = a * H^b`` for each species and writes
``data/assets/allometry/<species>.json``.  This is a simulation-free step: it
loads yield tables and fits a curve, and never imports the Grove engine, so it
runs in seconds rather than the hours a calibration pass takes.

Dataset production needs only this artifact from the yield tables -- trees are
grown to height milestones and their DBH is realised at export from the height
actually measured (see docs/reference/yield-table-calibration.md).

Usage:
    growpy-build-allometry --all
    growpy-build-allometry --species "European Beech" --species "European Oak"
"""

import argparse
import logging
import sys

from growpy.utils.allometry import build_all_allometries, get_allometry_dir
from growpy.utils.log import setup_logging

logger = logging.getLogger(__name__)


def _dataset_species() -> list[str]:
    """Common names of all species marked for the production dataset."""
    from growpy.pipelines.dataset_csv_planner import _get_dataset_species

    return list(_get_dataset_species()["Common Name"])


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="growpy-build-allometry",
        description=(
            "Fit height-DBH allometry (DBH = a * H^b) per species from yield "
            "tables. No Grove simulation is performed."
        ),
    )
    parser.add_argument(
        "--species",
        action="append",
        default=None,
        metavar="NAME",
        help="Species common name; repeat for several. Default: all dataset species.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build for every species marked in tree_asset_lookup.csv.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only report warnings and errors.",
    )
    args = parser.parse_args()

    setup_logging(verbose=not args.quiet)

    if args.species:
        species = args.species
    elif args.all:
        species = _dataset_species()
    else:
        parser.error("Pass --all or at least one --species")
        return 2

    logger.info("Building allometry for %d species...", len(species))
    written = build_all_allometries(species)

    failed = [s for s in species if s not in written]
    logger.info("")
    logger.info(
        "Wrote %d/%d artifacts to %s", len(written), len(species), get_allometry_dir()
    )
    if failed:
        logger.warning("No allometry produced for: %s", ", ".join(failed))

    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
