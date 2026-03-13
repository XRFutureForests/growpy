#!/usr/bin/env python3
"""Create growth models for Grove species with automatic plateau detection.

Step 3 of the pipeline. Defaults from growpy.toml [growth_models]. See docs/cli-reference.md.

When [calibration] enabled = true in growpy.toml, this script also:
- Calibrates against yield tables (local CSV or openyieldtables.org)
- Re-simulates with calibration applied
- Produces final calibrated growth models in a single run
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from growpy.config import get_config
from growpy.utils.analysis import SpeciesGrowthAnalyzer
from growpy.utils.log import setup_logging

logger = logging.getLogger(__name__)


def _resolve_species_from_csv(
    csv_path: Path, script_dir: Path
) -> Optional[List[str]]:
    """Parse CSV and return list of standardized species names."""
    import pandas as pd

    df = pd.read_csv(csv_path)

    if "species" in df.columns and "Common Name" not in df.columns:
        unique_species = df["species"].dropna().unique().tolist()

        asset_lookup_path = (
            script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
        )
        if not asset_lookup_path.exists():
            logger.error("Asset lookup table not found: %s", asset_lookup_path)
            return None

        lookup_df = pd.read_csv(asset_lookup_path)

        csv_species = []
        for species in unique_species:
            match = lookup_df[
                lookup_df["Common Name"].str.lower() == species.lower()
            ]

            if match.empty and "Aliases" in lookup_df.columns:
                for _, row in lookup_df.iterrows():
                    aliases = str(row.get("Aliases", "")).lower()
                    if species.lower() in [
                        a.strip() for a in aliases.split(",")
                    ]:
                        match = lookup_df[
                            lookup_df["Common Name"] == row["Common Name"]
                        ]
                        break

            if not match.empty:
                standardized = match.iloc[0].get("Standardized Name")
                if standardized:
                    csv_species.append(standardized)

        return csv_species if csv_species else None

    if "Standardized Name" in df.columns:
        return df["Standardized Name"].tolist()

    import re

    def standardize_name(name):
        name = re.sub(r"[^\w\s-]", "", name.lower())
        return re.sub(r"[-\s]+", "_", name).strip("_")

    return [standardize_name(s) for s in df["Common Name"].tolist()]


def _run_calibration_pass(
    analyzer: SpeciesGrowthAnalyzer,
    species_list: List[str],
    config,
    script_dir: Path,
) -> List[str]:
    """Run yield table calibration for species with available yield tables.

    Computes calibration from uncalibrated curves (already in analyzer) and
    writes per-cycle overrides to seed.json files.

    Returns list of species that were calibrated (need re-simulation).
    """
    from growpy.utils.yield_tables import (
        calibrate_species,
        interpolate_yield_table,
        load_lookup_table,
        resolve_yield_table,
    )

    presets_dir = analyzer.presets_dir

    # Resolve yield tables dir
    yield_tables_dir = config.calibration_yield_tables_dir
    if not yield_tables_dir.is_absolute():
        yield_tables_dir = script_dir / yield_tables_dir

    # Resolve plot output dir
    do_plot = config.calibration_plot
    plot_dir = config.calibration_output_dir
    if not plot_dir.is_absolute():
        plot_dir = script_dir / plot_dir

    # Load lookup table for common name <-> standardized name mapping
    lookup = load_lookup_table(script_dir)
    std_to_common = {v["standardized"]: name for name, v in lookup.items()}

    calibrated_species = []

    for species_std in species_list:
        common_name = std_to_common.get(species_std)
        if not common_name:
            logger.debug("No lookup entry for %s — skipping calibration", species_std)
            continue

        height_curve = analyzer.height_curves.get(species_std)
        dbh_curve = analyzer.dbh_curves.get(species_std)
        if not height_curve:
            logger.debug("No height curve for %s — skipping calibration", species_std)
            continue

        yield_search = lookup.get(common_name, {}).get("yield_search", "")

        logger.info("")
        logger.info("Calibrating %s...", common_name)

        yield_data = resolve_yield_table(
            species_common=common_name,
            species_std=species_std,
            yield_tables_dir=yield_tables_dir,
            calibration_species=config.calibration_species,
            yield_search=yield_search,
        )

        if yield_data is None:
            logger.debug("No yield table for %s — skipping calibration", common_name)
            continue

        # Use explicit fpy from TOML override, or None for auto-estimation
        fpy = config.calibration_species.get(common_name, {}).get(
            "flushes_per_year"
        )

        ok = calibrate_species(
            species_name=common_name,
            grove_heights=height_curve,
            grove_dbhs=dbh_curve or [],
            yield_data=yield_data,
            presets_dir=presets_dir,
            flushes_per_year=fpy,
        )

        if ok:
            calibrated_species.append(species_std)

        # Generate comparison plot
        if do_plot:
            from growpy.utils.plotting import plot_calibration_comparison

            # Read back the fpy that was actually used (auto-estimated or explicit)
            import json as _json

            _preset = presets_dir / f"{species_std}.seed.json"
            _cal = {}
            if _preset.exists():
                with open(_preset) as _f:
                    _cal = _json.load(_f).get("_yield_table_calibration", {})
            plot_fpy = _cal.get("flushes_per_year", fpy or 1.0)

            max_cycles = len(height_curve)
            _, target_heights = interpolate_yield_table(
                yield_data.ages, yield_data.heights, max_cycles, plot_fpy
            )
            _, target_dbhs = interpolate_yield_table(
                yield_data.ages, yield_data.dbhs, max_cycles, plot_fpy,
                initial_value=0.0,
            )

            plot_calibration_comparison(
                species_name=common_name,
                grove_heights=height_curve,
                grove_dbhs=dbh_curve or [],
                yield_ages=yield_data.ages,
                yield_heights=yield_data.heights,
                yield_dbhs=yield_data.dbhs,
                table_title=yield_data.title,
                output_path=plot_dir / f"{species_std}_comparison.png",
                calibrated_heights=target_heights,
                calibrated_dbhs=target_dbhs,
            )
            logger.info("  Plot saved to %s", plot_dir / f"{species_std}_comparison.png")

    return calibrated_species


def main():
    """Main function for command line usage."""
    config = get_config()

    parser = argparse.ArgumentParser(
        description=(
            "Generate growth models for Grove species from prepared assets. "
            "Features intelligent height monitoring to detect when tree growth plateaus "
            "and automatically stop simulation early to save time. Also includes timeout "
            "protection to prevent infinite loops. "
            "When calibration is enabled in growpy.toml, automatically calibrates against "
            "yield tables and re-simulates in a single run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze species from forest placement CSV (auto-extracts from data/input/test.csv)
    python src/growpy/cli/create_growth_models.py

    # Analyze with custom height monitoring and timeout
    python src/growpy/cli/create_growth_models.py --height-threshold 0.005 --max-cycles-without-growth 15 --timeout 120

    # Analyze specific species
    python src/growpy/cli/create_growth_models.py --species "European oak"

    # Analyze ALL 57 available species using comprehensive lookup table
    python src/growpy/cli/create_growth_models.py --csv src/growpy/config/tree_asset_lookup.csv

    # Skip calibration even when enabled in config
    python src/growpy/cli/create_growth_models.py --no-calibrate

CSV Format Support:
    Automatically handles forest placement CSV (x,y,species) or asset lookup CSV (Common Name,Preset)

Calibration (when enabled in growpy.toml [calibration]):
    1. Simulates uncalibrated growth curves
    2. Calibrates against yield tables (local CSV in yield_tables_dir, or openyieldtables.org)
    3. Re-simulates calibrated species with overrides applied
    All in a single run — no need to run calibrate_growth.py separately.

Note: Run prepare_assets.py first to copy species presets from Grove installation.
        """,
    )

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_assets_dir = script_dir / "data" / "assets"

    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to species CSV (default: from config)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Number of growth cycles for analysis (default: from config)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=None,
        help="Number of random seeds to average for robust curves (default: from config)",
    )
    parser.add_argument(
        "--height-threshold",
        type=float,
        default=None,
        help="Minimum height increase to consider as growth (default: from config)",
    )
    parser.add_argument(
        "--max-cycles-without-growth",
        type=int,
        default=None,
        help="Number of cycles without growth before stopping (default: from config)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Maximum time in seconds for growth simulation per seed (default: from config)",
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Specific species to analyze (if not provided, analyzes all species)",
    )
    parser.add_argument(
        "--no-calibrate",
        action="store_true",
        help="Skip calibration even when enabled in growpy.toml",
    )

    args = parser.parse_args()

    # Resolve config: TOML defaults + CLI overrides
    config.resolve(args)
    setup_logging(verbose=config.verbose)

    # Resolve CSV path
    csv_path = config.csv_file
    if args.csv is not None:
        csv_path = args.csv
    elif not csv_path.is_absolute():
        csv_path = script_dir / csv_path

    # Check assets directory
    if not default_assets_dir.exists():
        logger.error("Assets directory not found: %s", default_assets_dir)
        return 1

    # Check for presets directory
    presets_dir = default_assets_dir / "presets"
    if not presets_dir.exists():
        logger.error("Presets directory not found: %s", presets_dir)
        return 1

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(
        default_assets_dir,
        config.growth_models_cycles,
        config.growth_models_seeds,
        config.growth_models_height_threshold,
        config.growth_models_max_cycles_without_growth,
        config.growth_models_timeout,
    )

    do_calibrate = config.calibration_enabled and not args.no_calibrate

    if args.species:
        # --- Single species mode ---
        available_species = analyzer.get_available_species()
        if args.species not in available_species:
            logger.error(
                "Species '%s' not found. Available: %s",
                args.species,
                available_species,
            )
            return 1

        # Generate height and DBH curves
        height_curve, dbh_curve, metadata = analyzer.generate_height_curve_for_species(
            args.species
        )

        # Create growth model
        growth_model = analyzer.create_growth_model_for_species(
            args.species, height_curve
        )

        # Store results
        analyzer.height_curves[args.species] = height_curve
        analyzer.dbh_curves[args.species] = dbh_curve
        analyzer.growth_models[args.species] = growth_model
        analyzer.analysis_metadata[args.species] = metadata

        # Save initial results
        analyzer.save_species_results(args.species)

        # Calibration pass
        if do_calibrate:
            logger.info("")
            logger.info("=" * 60)
            logger.info("  Calibration pass")
            logger.info("=" * 60)

            calibrated = _run_calibration_pass(
                analyzer, [args.species], config, script_dir
            )

            if calibrated:
                logger.info("")
                logger.info("=" * 60)
                logger.info("  Re-simulating with calibration applied")
                logger.info("=" * 60)

                # Re-simulate with calibration
                height_curve, dbh_curve, metadata = (
                    analyzer.generate_height_curve_for_species(args.species)
                )
                growth_model = analyzer.create_growth_model_for_species(
                    args.species, height_curve
                )

                analyzer.height_curves[args.species] = height_curve
                analyzer.dbh_curves[args.species] = dbh_curve
                analyzer.growth_models[args.species] = growth_model
                analyzer.analysis_metadata[args.species] = metadata

        # Save final results
        analyzer.save_growth_models()

    else:
        # --- Multi-species mode (from CSV) ---
        try:
            csv_species = _resolve_species_from_csv(csv_path, script_dir)
        except Exception as e:
            logger.error("Error processing CSV file: %s", e)
            return 1

        if not csv_species:
            logger.error("No matching species found in CSV")
            return 1

        available_species = analyzer.get_available_species()
        species_to_process = [s for s in csv_species if s in available_species]

        if not species_to_process:
            logger.error(
                "No available species to process. CSV species: %s, Available presets: %s",
                csv_species,
                available_species,
            )
            return 1

        # Pass 1: initial simulation (uncalibrated)
        logger.info("=" * 60)
        logger.info("  Pass 1: Uncalibrated growth simulation")
        logger.info("=" * 60)

        results = analyzer.analyze_all_species(
            parallel=False,
            max_workers=None,
            species_filter=species_to_process,
        )

        # Calibration + re-simulation pass
        if do_calibrate:
            successful = [s for s, ok in results.items() if ok]

            logger.info("")
            logger.info("=" * 60)
            logger.info("  Calibration pass")
            logger.info("=" * 60)

            calibrated = _run_calibration_pass(
                analyzer, successful, config, script_dir
            )

            if calibrated:
                logger.info("")
                logger.info("=" * 60)
                logger.info(
                    "  Pass 2: Re-simulating %d calibrated species",
                    len(calibrated),
                )
                logger.info("=" * 60)

                # Re-simulate only calibrated species
                analyzer.analyze_all_species(
                    parallel=False,
                    max_workers=None,
                    species_filter=calibrated,
                )
            else:
                logger.info("No species calibrated — skipping re-simulation")

        # Save final results
        analyzer.save_growth_models()


if __name__ == "__main__":
    sys.exit(main())
