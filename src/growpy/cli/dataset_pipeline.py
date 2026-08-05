#!/usr/bin/env python3
"""Run the full dataset production pipeline across all four steps.

Orchestrates the four-step dataset workflow for all species:
  Step 1 (prepare-assets):   copy Grove 2.3 assets for all species
  Step 2 (convert-twigs):    convert .blend twigs to USD for all species
  Step 3 (create-models):    run growth simulation and calibration for all species
  Step 4 (generate-forest):  generate tree meshes per species (one subprocess each)

Each step is invoked as a subprocess so that bpy (required by step 4) is
never imported into this process. All four steps are config-driven by
default: species selection comes from tree_asset_lookup.csv's Dataset column,
no CSV file crosses the process boundary. --csv overrides steps 1-3 with an
explicit species-lookup CSV; --generate-csvs writes per-species merged CSVs
for inspection only -- nothing in the pipeline reads them back.

Usage:
    python src/growpy/cli/dataset_pipeline.py --generate-csvs
    python src/growpy/cli/dataset_pipeline.py --pilot
    python src/growpy/cli/dataset_pipeline.py --all
    python src/growpy/cli/dataset_pipeline.py --species "European Beech"
    python src/growpy/cli/dataset_pipeline.py --generate-csvs --all --steps all --ingest-yield-tables --clean
    python src/growpy/cli/dataset_pipeline.py --pilot --dry-run

    # Generate CSVs then run only step 4 for pilot species:
    python src/growpy/cli/dataset_pipeline.py --generate-csvs
    python src/growpy/cli/dataset_pipeline.py --pilot --steps 4

    # Production run: skip the inspection PNGs (preview, export-control and
    # icons). They are not dataset payload and cost roughly a quarter of
    # step 4's runtime:
    python src/growpy/cli/dataset_pipeline.py --all --steps 4 --no-previews --no-icons

See docs/dataset-specification.md for the step-by-step production guide.
"""

import argparse
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from growpy.io.unreal.script_generation import generate_unreal_scripts
from growpy.io.usd.overview import generate_overview_markdown
from growpy.pipelines.dataset_csv_planner import generate_dataset_csvs
from growpy.pipelines.dataset_job_planner import (
    DATASET_DIR,
    list_all_species,
    resolve_species,
)
from growpy.pipelines.run_summary import generate_run_summary
from growpy.pipelines.step_runner import (
    check_environment,
    run_parallel_step4,
    run_species_step4,
    run_step123,
)
from growpy.utils.log import setup_logging

logger = logging.getLogger(__name__)


def _clean_step(step: int) -> None:
    """Remove output directories for a pipeline step before re-running.

    Step 1: data/assets/{presets,textures,twigs,pve_configs}/
    Step 2: *.usda files under data/assets/twigs/
    Step 3: data/assets/growth_models/ + yield table store
    Step 4: data/output/forest/
    """
    from growpy.config.paths import get_assets_directory, get_data_directory

    assets = get_assets_directory()
    data = get_data_directory()

    if step == 1:
        for subdir in ("presets", "textures", "twigs", "pve_configs"):
            target = assets / subdir
            if target.exists():
                shutil.rmtree(target)
                logger.info("Cleaned %s", target)
    elif step == 2:
        twigs_dir = assets / "twigs"
        if twigs_dir.exists():
            removed = 0
            for f in twigs_dir.rglob("*.usda"):
                f.unlink()
                removed += 1
            if removed:
                logger.info("Cleaned %d .usda files from %s", removed, twigs_dir)
    elif step == 3:
        models_dir = assets / "growth_models"
        if models_dir.exists():
            shutil.rmtree(models_dir)
            logger.info("Cleaned %s", models_dir)
        store_dir = data / "input" / "yield_tables" / "store"
        if store_dir.exists():
            shutil.rmtree(store_dir)
            logger.info("Cleaned yield table store: %s", store_dir)
    elif step == 4:
        forest_dir = data / "output" / "forest"
        if forest_dir.exists():
            shutil.rmtree(forest_dir)
            logger.info("Cleaned %s", forest_dir)


def _parse_steps(steps_str: str) -> list:
    """Parse --steps value into a sorted list of step numbers.

    Accepts "all" or a comma-separated list of integers (e.g. "1,2,3,4").
    """
    if steps_str.strip().lower() == "all":
        return [1, 2, 3, 4]
    try:
        steps = [int(s.strip()) for s in steps_str.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid --steps value: {steps_str!r}. "
            "Use integers 1-4 separated by commas, or 'all'."
        ) from None
    invalid = [s for s in steps if s not in (1, 2, 3, 4)]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Invalid step numbers: {invalid}. Valid steps are 1, 2, 3, 4."
        )
    return sorted(set(steps))


def main():
    parser = argparse.ArgumentParser(
        description="Run the full dataset production pipeline (steps 1-4).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --generate-csvs\n"
            "  %(prog)s --pilot --dry-run\n"
            "  %(prog)s --all --steps all\n"
            "  %(prog)s --species 'European Beech' --steps 4 --max-height 15\n"
            "  %(prog)s --all --steps 4 --no-previews --no-icons\n"
        ),
    )

    # CSV generation
    parser.add_argument(
        "--generate-csvs",
        action="store_true",
        help=(
            "Generate per-species merged CSVs and all_species.csv from "
            "tree_asset_lookup.csv. Exits unless combined with --all/--pilot/--species."
        ),
    )
    parser.add_argument(
        "--density",
        choices=["full", "reduced", "bare"],
        default="full",
        help="Twig density variant for CSV generation (default: full).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATASET_DIR,
        help="Output directory for generated CSV files (default: data/input/dataset).",
    )

    # Step selection
    parser.add_argument(
        "--steps",
        default="4",
        metavar="STEPS",
        help=(
            "Steps to run, comma-separated or 'all' (default: 4). "
            "E.g. --steps 1,2,3,4 or --steps all or --steps 3,4."
        ),
    )

    # CSV override for steps 1-3 (default: config-driven, no CSV needed)
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Run steps 1-3 from this species-lookup CSV instead of the "
            "config-driven default (tree_asset_lookup.csv Dataset column)."
        ),
    )

    # Species selection (step 4)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--species",
        type=str,
        help='Single species by common name (e.g. "European Beech").',
    )
    group.add_argument(
        "--pilot",
        action="store_true",
        help="Run pilot species only (European Beech, Norway Spruce).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Run all species with merged CSV files in the dataset directory.",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List available species and exit.",
    )

    # Execution options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument(
        "--max-height",
        type=float,
        default=0,
        help=(
            "Cap tree height in meters for step 4 (e.g. 15). "
            "Reduces growth cycles for faster testing. 0 = no limit (default)."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="Parallel workers for step 4 (default: min(4, cpu_count)). "
        "Use 1 for sequential execution.",
    )
    parser.add_argument(
        "--ingest-yield-tables",
        action="store_true",
        help="Ingest yield tables from external providers before step 3 calibration.",
    )
    parser.add_argument(
        "--calibrate",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override step 3 calibration for this run only (default: from TOML).",
    )
    parser.add_argument(
        "--pve",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override step 4 PVE preset generation this run (default: from TOML).",
    )
    parser.add_argument(
        "--wind",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override step 4 wind-data generation this run (default: from TOML).",
    )
    parser.add_argument(
        "--previews",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Override step 4 preview/export-control PNGs this run (default: TOML). "
            "Inspection aids only -- together with --no-icons, disabling these "
            "cuts roughly a quarter off step 4 runtime."
        ),
    )
    parser.add_argument(
        "--icons",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Override step 4 icon PNGs this run (default: from TOML). "
            "Inspection aids only -- see --previews."
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean output directories for each step before running. "
        "Implies --clean-store for step 3.",
    )
    parser.add_argument(
        "--clean-store",
        action="store_true",
        help="Clear existing yield table store before re-ingestion (requires --ingest-yield-tables).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress INFO-level logging (only show warnings and errors)",
    )
    parser.add_argument(
        "--profile",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Override step 4 profiling this run (default: from TOML). Prints a "
            "per-stage timing report from each species subprocess."
        ),
    )

    args = parser.parse_args()
    if args.quiet:
        args.verbose = False
    setup_logging(verbose=args.verbose)

    # Provenance: make this run's TOML-override switches visible in the log.
    # None means "use config/*.toml" for that switch.
    logger.info(
        "Effective switches: calibrate=%s pve=%s wind=%s previews=%s icons=%s "
        "profile=%s "
        "(None = from TOML)",
        args.calibrate,
        args.pve,
        args.wind,
        args.previews,
        args.icons,
        args.profile,
    )

    # --generate-csvs: generate CSVs, then continue or exit
    if args.generate_csvs:
        logger.info("Generating dataset CSVs in %s", args.output_dir)
        files = generate_dataset_csvs(args.output_dir, args.density)
        logger.info("Generated %d CSV files.", len(files))
        if not any([args.species, args.pilot, args.all]):
            return 0

    # --list: show available species and exit
    if args.list:
        stems = list_all_species()
        if not stems:
            print("No species marked for the dataset in tree_asset_lookup.csv.")
        for stem in stems:
            print(stem.replace("_", " ").title())
        return 0

    # Parse --steps
    try:
        steps = _parse_steps(args.steps)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    # Steps 1-3 default to config-driven species selection (--dataset, no CSV
    # file crosses the process boundary); an explicit --csv overrides that.
    dataset_mode_123 = not args.csv

    # Determine species list (only needed for step 4)
    species_list = []
    if 4 in steps:
        if not any([args.species, args.pilot, args.all]):
            parser.error(
                "Step 4 requires a species selection: --species, --pilot, or --all."
            )
        species_list = resolve_species(args)
        if not species_list:
            logger.error(
                "No species selected. Mark species for the dataset in "
                "tree_asset_lookup.csv (Dataset column)."
            )
            raise SystemExit(1)

    # Guard: bpy check before any step 4 execution
    if 4 in steps and not args.dry_run and not check_environment():
        raise SystemExit(1)

    # Step 4 realises DBH at export from the height-DBH allometry.  Building it
    # is simulation-free (seconds) and its artifacts live under the gitignored
    # data/assets/, so rebuild here rather than trusting a previous run to have
    # left them behind.
    if 4 in steps and not args.dry_run:
        from growpy.pipelines.dataset_csv_planner import _get_dataset_species
        from growpy.utils.allometry import build_all_allometries

        logger.info("Building height-DBH allometry from yield tables...")
        written = build_all_allometries(list(_get_dataset_species()["Common Name"]))
        logger.info("  %d allometry artifact(s) ready", len(written))

    # --clean implies --clean-store for step 3
    if args.clean:
        args.clean_store = True

    # Execute steps in order
    failed = []
    for step in steps:
        # Clean output directories before running
        if args.clean and not args.dry_run:
            _clean_step(step)

        if step in (1, 2, 3):
            extra = []
            if step == 3 and args.ingest_yield_tables:
                extra.append("--ingest-yield-tables")
                if args.clean_store:
                    extra.append("--clean-store")
            if step == 3 and args.calibrate is not None:
                extra.append("--calibrate" if args.calibrate else "--no-calibrate")
            # Pass --species to step 3 so calibration is limited to one species
            if step == 3 and args.species:
                extra.extend(["--species", args.species])
            # Pass --max-height to step 3 so growth simulation stops once
            # species reach the target height instead of always running
            # the full cycle count
            if step == 3 and args.max_height > 0:
                extra.extend(["--max-height", str(args.max_height)])
            extra = extra or None
            ok = run_step123(
                step,
                csv_path=args.csv,
                dataset_mode=dataset_mode_123,
                dry_run=args.dry_run,
                extra_args=extra,
                verbose=args.verbose,
            )
            if not ok:
                logger.error("Pipeline aborted at step %d.", step)
                raise SystemExit(1)

        else:  # step 4
            workers = max(1, args.workers)
            use_parallel = workers > 1 and len(species_list) > 1 and not args.dry_run
            elapsed_by_species: dict = {}

            if use_parallel:
                logger.info(
                    "Step 4: %d species, %d parallel workers",
                    len(species_list),
                    workers,
                )
                failed, elapsed_by_species = run_parallel_step4(
                    species_list,
                    workers,
                    args.max_height,
                    verbose=args.verbose,
                    pve=args.pve,
                    wind=args.wind,
                    previews=args.previews,
                    icons=args.icons,
                    profile=args.profile,
                )
            else:
                failed = []
                for species in species_list:
                    t0 = time.monotonic()
                    ok = run_species_step4(
                        species,
                        args.dry_run,
                        args.max_height,
                        verbose=args.verbose,
                        pve=args.pve,
                        wind=args.wind,
                        previews=args.previews,
                        icons=args.icons,
                        profile=args.profile,
                    )
                    elapsed_by_species[species] = time.monotonic() - t0
                    if not ok:
                        failed.append(species)

            if failed:
                logger.error("Step 4 failed for: %s", ", ".join(failed))

    # Generate Unreal scripts once after all step 4 workers complete
    if 4 in steps and not args.dry_run:
        from growpy.config.core import get_config as _get_config

        _cfg = _get_config()
        if _cfg.unreal_import_to_unreal:
            _out = _cfg.output_dir
            if not _out.is_absolute():
                _out = Path(__file__).parent.parent.parent.parent / _out
            generate_unreal_scripts(_out, _cfg, include_static=_cfg.export_static)

    # Generate dataset overview after step 4 (even if some species failed)
    if 4 in steps and not args.dry_run:
        from growpy.config.core import get_config
        from growpy.config.paths import get_assets_directory

        config = get_config()
        assets_dir = get_assets_directory()
        generate_overview_markdown(
            config.output_dir,
            config.forest_height_interval,
            preset_dir=assets_dir / "presets",
            models_dir=assets_dir / "growth_models",
        )
        generate_run_summary(
            config.output_dir,
            species_list,
            elapsed_by_species,
            failed,
            config,
        )

    if 4 in steps and failed:
        raise SystemExit(1)

    logger.info("Done. %d step(s) completed.", len(steps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
