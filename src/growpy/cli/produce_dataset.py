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
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from growpy.utils.log import setup_logging
from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

PILOT_SPECIES = ["European Beech", "Norway Spruce"]

DATASET_DIR = Path("data/input/dataset")
GENERATE_SCRIPT = Path("src/growpy/cli/generate_forest.py")


def _find_species_csvs(species_name: str) -> list:
    """Find CSV files for a species.

    Prefers a single merged CSV (open + competition combined) if available.
    Falls back to separate open and competition CSVs.
    """
    std_name = standardize_species_name(species_name)

    # Prefer merged CSV (single simulation for both individual types)
    merged = DATASET_DIR / f"{std_name}_merged.csv"
    if merged.exists():
        return [merged]

    csvs = []
    for suffix in ("open", "competition"):
        path = DATASET_DIR / f"{std_name}_{suffix}.csv"
        if path.exists():
            csvs.append(path)
        else:
            logger.warning("CSV not found: %s", path)
    return csvs


def _list_all_species() -> list:
    """List all species with CSV files in the dataset directory."""
    species = set()
    # Detect merged CSVs
    for csv_path in sorted(DATASET_DIR.glob("*_merged.csv")):
        species.add(csv_path.stem.replace("_merged", ""))
    # Detect separate open+competition pairs
    for csv_path in sorted(DATASET_DIR.glob("*_open.csv")):
        name = csv_path.stem.replace("_open", "")
        comp = DATASET_DIR / f"{name}_competition.csv"
        if comp.exists():
            species.add(name)
    return sorted(species)


def _check_environment() -> bool:
    """Verify that bpy is available in the current Python environment."""
    result = subprocess.run(
        [sys.executable, "-c", "import bpy"],
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error(
            "bpy module not available in %s. "
            "Activate the growpy conda environment first: conda activate growpy",
            sys.executable,
        )
        return False
    return True


def _build_command(csv_path: Path, max_height: float = 0) -> list:
    """Build the generate_forest.py command for a CSV file."""
    cmd = [sys.executable, str(GENERATE_SCRIPT), str(csv_path)]
    if max_height > 0:
        cmd.extend(["--max-height", str(max_height)])
    if "_merged" in csv_path.stem:
        # Merged CSV: export open tree (fid=1) and competition center (fid=2)
        cmd.extend(["--export-trees", "1,2"])
    elif "_competition" in csv_path.stem:
        cmd.extend(["--export-trees", "1"])
    return cmd


def run_species(
    species_name: str, dry_run: bool = False, max_height: float = 0
) -> bool:
    """Run generate_forest.py for both individual types of a species.

    Returns True if all runs succeeded (or dry_run).
    """
    csvs = _find_species_csvs(species_name)
    if not csvs:
        logger.error("No CSV files found for species: %s", species_name)
        return False

    success = True
    for csv_path in csvs:
        cmd = _build_command(csv_path, max_height=max_height)
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


def _run_species_worker(args: tuple) -> tuple:
    """Worker function for parallel execution (must be top-level for pickling)."""
    species_name, max_height = args
    ok = run_species(species_name, max_height=max_height)
    return species_name, ok


def _run_parallel(species_list: list, workers: int, max_height: float) -> list:
    """Run species in parallel using subprocess workers.

    Each species pair (open + competition) runs sequentially within a worker,
    but multiple species run concurrently across workers.
    """
    failed = []

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_species_worker, (species, max_height)): species
            for species in species_list
        }
        for future in as_completed(futures):
            species_name = futures[future]
            try:
                _, ok = future.result()
                if not ok:
                    failed.append(species_name)
            except Exception:
                logger.exception("Worker crashed for %s", species_name)
                failed.append(species_name)

    return failed


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
    parser.add_argument(
        "--max-height",
        type=float,
        default=0,
        help="Cap tree heights at this value in meters (e.g., 15). "
        "Reduces growth cycles for faster testing. 0 = no limit (default).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="Max parallel species workers (default: min(4, cpu_count)). "
        "Use 1 for sequential execution.",
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

    if not args.dry_run and not _check_environment():
        raise SystemExit(1)

    if args.max_height > 0:
        logger.info("Max height cap: %.1fm", args.max_height)

    workers = max(1, args.workers)
    use_parallel = workers > 1 and len(species_list) > 1 and not args.dry_run

    if use_parallel:
        logger.info("Parallel mode: %d workers", workers)
        failed = _run_parallel(species_list, workers, args.max_height)
    else:
        failed = []
        for species in species_list:
            if not run_species(
                species, dry_run=args.dry_run, max_height=args.max_height
            ):
                failed.append(species)

    if failed:
        logger.error("Failed species: %s", ", ".join(failed))
        raise SystemExit(1)

    logger.info("Done. %d species processed.", len(species_list))


if __name__ == "__main__":
    main()
