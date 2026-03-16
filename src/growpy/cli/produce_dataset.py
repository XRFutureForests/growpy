#!/usr/bin/env python3
"""Produce dataset models by running generate_forest.py for each species.

Convenience wrapper that iterates per-species CSV files in data/input/dataset/
and calls generate_forest.py for each open-grown and competition CSV.

Usage:
    python src/growpy/cli/produce_dataset.py --species "European Beech"
    python src/growpy/cli/produce_dataset.py --pilot
    python src/growpy/cli/produce_dataset.py --all
    python src/growpy/cli/produce_dataset.py --all --dry-run

See docs/dataset-specification.md for the step-by-step production guide.
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from growpy.utils.log import setup_logging
from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

PILOT_SPECIES = ["European Beech", "Norway Spruce"]

DATASET_DIR = Path("data/input/dataset")
GENERATE_SCRIPT = Path("src/growpy/cli/generate_forest.py")


def _find_species_csvs(species_name: str) -> list:
    """Find open and competition CSVs for a species."""
    std_name = standardize_species_name(species_name)
    csvs = []
    for suffix in ("open", "competition"):
        path = DATASET_DIR / f"{std_name}_{suffix}.csv"
        if path.exists():
            csvs.append(path)
        else:
            logger.warning("CSV not found: %s", path)
    return csvs


def _list_all_species() -> list:
    """List all species with CSV pairs in the dataset directory."""
    species = set()
    for csv_path in sorted(DATASET_DIR.glob("*_open.csv")):
        name = csv_path.stem.replace("_open", "")
        comp = DATASET_DIR / f"{name}_competition.csv"
        if comp.exists():
            species.add(name)
    return sorted(species)


def _build_command(csv_path: Path) -> list:
    """Build the generate_forest.py command for a CSV file."""
    return [sys.executable, str(GENERATE_SCRIPT), str(csv_path)]


def run_species(species_name: str, dry_run: bool = False) -> bool:
    """Run generate_forest.py for both individual types of a species.

    Returns True if all runs succeeded (or dry_run).
    """
    csvs = _find_species_csvs(species_name)
    if not csvs:
        logger.error("No CSV files found for species: %s", species_name)
        return False

    success = True
    for csv_path in csvs:
        cmd = _build_command(csv_path)
        label = csv_path.stem

        if dry_run:
            logger.info("[DRY RUN] %s", " ".join(str(c) for c in cmd))
            continue

        logger.info("Running: %s", label)
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            logger.error("FAILED: %s (exit code %d)", label, result.returncode)
            success = False
        else:
            logger.info("OK: %s", label)

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Run generate_forest.py for dataset species."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--species",
        type=str,
        help='Species common name, e.g. "European Beech"',
    )
    group.add_argument(
        "--pilot",
        action="store_true",
        help=f"Run pilot species only ({', '.join(PILOT_SPECIES)})",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Run all 16 dataset species",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List available species and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if args.list:
        for name in _list_all_species():
            print(name)
        return

    if args.species:
        species_list = [args.species]
    elif args.pilot:
        species_list = PILOT_SPECIES
    else:
        species_list = [
            name.replace("_", " ").title() for name in _list_all_species()
        ]

    logger.info(
        "Dataset production: %d species%s",
        len(species_list),
        " (dry run)" if args.dry_run else "",
    )

    failed = []
    for species in species_list:
        if not run_species(species, dry_run=args.dry_run):
            failed.append(species)

    if failed:
        logger.error("Failed species: %s", ", ".join(failed))
        raise SystemExit(1)

    logger.info("Done. %d species processed.", len(species_list))


if __name__ == "__main__":
    main()
