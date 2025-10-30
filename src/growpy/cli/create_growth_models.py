#!/usr/bin/env python3
"""
Create growth models for Grove species.

Generates height curves and age prediction models with intelligent early termination.

Supports two CSV formats:
  1. Forest placement CSV (x, y, species, height) - auto-extracts unique species
  2. Asset lookup CSV (Common Name, Preset, Twig, Bark Texture) - direct asset reference

Quick Start:
    python src/growpy/cli/create_growth_models.py --cycles 25

Common Flags:
    --species TEXT           Analyze specific species (default: all from CSV)
    --csv PATH              Species CSV (default: data/input/test.csv)
    --cycles INT            Maximum growth cycles (default: 125)
    --height-threshold FLOAT Minimum growth to continue (default: 0.05)
    --timeout INT           Max simulation time per seed (default: 300s)
    --workers INT           Parallel workers (default: 3)
    --no-parallel           Disable parallel processing

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Note:
    Run prepare_assets.py first to copy species presets from Grove installation.

Usage:
    python create_growth_models.py [options]
"""

import argparse
import logging
import multiprocessing as mp
import sys
from pathlib import Path

from growpy.utils.analysis import SpeciesGrowthAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress verbose matplotlib logging
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate growth models for Grove species from prepared assets. "
            "Features intelligent height monitoring to detect when tree growth plateaus "
            "and automatically stop simulation early to save time. Also includes timeout "
            "protection to prevent infinite loops."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze 5 species from forest placement CSV (auto-extracts from data/input/test.csv)
    python src/growpy/cli/create_growth_models.py

    # Analyze with custom height monitoring and timeout
    python src/growpy/cli/create_growth_models.py --height-threshold 0.005 --max-cycles-without-growth 15 --timeout 120

    # Analyze with custom assets directory
    python src/growpy/cli/create_growth_models.py --assets-dir data/assets

    # Analyze sequentially (no parallel processing)
    python src/growpy/cli/create_growth_models.py --no-parallel

    # Analyze with custom number of workers
    python src/growpy/cli/create_growth_models.py --workers 4

    # Analyze specific species with detailed logging
    python src/growpy/cli/create_growth_models.py --species "European oak" --verbose

    # Analyze ALL 57 available species using comprehensive lookup table
    python src/growpy/cli/create_growth_models.py --csv src/growpy/config/tree_asset_lookup.csv

CSV Format Support:
    Automatically handles forest placement CSV (x,y,species) or asset lookup CSV (Common Name,Preset)

Height Monitoring & Timeout Protection:
    The script automatically monitors tree height growth and stops simulation early when:
    - Height increase per cycle falls below --height-threshold (default: 0.01 units)
    - No significant growth occurs for --max-cycles-without-growth consecutive cycles (default: 10)
    - Simulation time exceeds --timeout seconds per seed (default: 60)
    - This prevents wasting computation time on trees that have reached their growth plateau or are stuck

Note: Run prepare_assets.py first to copy species presets from Grove installation.
      Parallel processing significantly speeds up analysis when processing multiple species.
        """,
    )

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent

    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=script_dir / "data" / "assets",
        help="Directory containing prepared GrowPy assets (default: data/assets)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=script_dir / "data" / "input" / "test.csv",
        help="Path to species CSV (default: data/input/test.csv)",
    )
    parser.add_argument(
        "--cycles", type=int, default=125, help="Number of growth cycles for analysis"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=1,
        help="Number of random seeds to average for robust curves",
    )
    parser.add_argument(
        "--height-threshold",
        type=float,
        default=0.05,
        help="Minimum height increase to consider as growth (default: 0.05)",
    )
    parser.add_argument(
        "--max-cycles-without-growth",
        type=int,
        default=3,
        help="Number of cycles without growth before stopping (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum time in seconds for growth simulation per seed (default: 300)",
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Specific species to analyze (if not provided, analyzes all species)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Use parallel processing (default: True)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing (run sequentially)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Keep matplotlib logging suppressed even in verbose mode
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

    # Determine parallel processing settings
    use_parallel = args.parallel and not args.no_parallel
    max_workers = args.workers

    logger.info("Grove Species Growth Analysis")
    logger.info("=" * 40)
    logger.info(f"Assets directory: {args.assets_dir}")
    logger.info(f"Growth cycles: {args.cycles}")
    logger.info(f"Random seeds: {args.seeds}")
    logger.info(f"Height threshold: {args.height_threshold}")
    logger.info(f"Max cycles without growth: {args.max_cycles_without_growth}")
    logger.info(f"Timeout: {args.timeout} seconds")
    logger.info(f"Parallel processing: {'Enabled' if use_parallel else 'Disabled'}")
    if use_parallel and max_workers:
        logger.info(f"Max workers: {max_workers}")
    elif use_parallel:
        logger.info(f"Max workers: {max(1, mp.cpu_count() - 1)} (CPU count - 1)")

    # Check assets directory
    if not args.assets_dir.exists():
        logger.error(f"Assets directory not found: {args.assets_dir}")
        logger.error(
            "Please run prepare_assets.py first to copy assets from Grove installation"
        )
        sys.exit(1)

    # Check for presets directory
    presets_dir = args.assets_dir / "presets"
    if not presets_dir.exists():
        logger.error(f"Presets directory not found: {presets_dir}")
        logger.error("Please run prepare_assets.py first to copy species presets")
        sys.exit(1)

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(
        args.assets_dir,
        args.cycles,
        args.seeds,
        args.height_threshold,
        args.max_cycles_without_growth,
        args.timeout,
    )

    if args.species:
        # Analyze single species
        logger.info(f"Analyzing single species: {args.species}")

        available_species = analyzer.get_available_species()
        if args.species not in available_species:
            logger.error(f"Species '{args.species}' not found in available presets")
            logger.info(f"Available species: {', '.join(available_species[:10])}...")
            sys.exit(1)

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

        # Save individual species results
        species_dir = analyzer.save_species_results(args.species)

        logger.info(f"Final height: {metadata['final_height']:.2f}")
        logger.info(f"Growth rate: {metadata['growth_rate']:.3f} units/cycle")
        logger.info(f"Max height: {metadata['max_height']:.2f}")
        logger.info(f"Final DBH: {metadata['final_dbh']:.3f}")
        logger.info(f"Max DBH: {metadata['max_dbh']:.3f}")
        logger.info(
            f"Planned cycles: {metadata['planned_cycles']}, "
            f"Actual max cycles: {metadata['actual_max_cycles']}"
        )
        logger.info(f"Average actual cycles: {metadata['avg_actual_cycles']:.1f}")
        logger.info(
            f"Average simulation time: {metadata['avg_simulation_time']:.1f} seconds"
        )

        if metadata["early_terminations"] > 0:
            logger.info(
                f"Early terminations: {metadata['early_terminations']}/{metadata['num_seeds']} seeds"
            )
        else:
            logger.info("No early terminations occurred")

        if metadata["timeouts"] > 0:
            logger.warning(
                f"Timeouts occurred: {metadata['timeouts']}/{metadata['num_seeds']} seeds"
            )
        else:
            logger.info("No timeouts occurred")

        # Save results
        analyzer.save_growth_models()

    else:
        # Analyze species from CSV
        logger.info("Analyzing species from CSV...")

        # Load CSV to get species list
        import pandas as pd

        try:
            df = pd.read_csv(args.csv)

            # Check if this is a forest placement CSV (has "species" column)
            if "species" in df.columns and "Common Name" not in df.columns:
                logger.info(
                    "Detected forest placement CSV, extracting unique species..."
                )
                unique_species = df["species"].dropna().unique().tolist()
                logger.info(
                    f"Found {len(unique_species)} unique species: {', '.join(unique_species)}"
                )

                # Load the asset lookup table to get standardized names
                asset_lookup_path = (
                    script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
                )
                if not asset_lookup_path.exists():
                    logger.error(f"Asset lookup table not found: {asset_lookup_path}")
                    sys.exit(1)

                lookup_df = pd.read_csv(asset_lookup_path)

                # Map species names to standardized names
                csv_species = []
                for species in unique_species:
                    # Try matching Common Name
                    match = lookup_df[
                        lookup_df["Common Name"].str.lower() == species.lower()
                    ]

                    # Try matching aliases if no direct match
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
                        else:
                            logger.warning(f"No standardized name for '{species}'")
                    else:
                        logger.warning(
                            f"Species '{species}' not found in asset lookup table"
                        )

                if not csv_species:
                    logger.error(
                        f"None of the species in {args.csv.name} were found in asset lookup table"
                    )
                    sys.exit(1)

                logger.info(f"Standardized species names from CSV: {csv_species}")
            else:
                # Direct asset lookup CSV - use Standardized Name column
                if "Standardized Name" in df.columns:
                    csv_species = df["Standardized Name"].tolist()
                else:
                    # Fallback: standardize Common Name
                    import re

                    def standardize_name(name):
                        name = re.sub(r"[^\w\s-]", "", name.lower())
                        return re.sub(r"[-\s]+", "_", name).strip("_")

                    csv_species = [
                        standardize_name(s) for s in df["Common Name"].tolist()
                    ]

                logger.info(f"Found {len(csv_species)} species in CSV: {args.csv.name}")
                logger.info(f"Standardized species names: {csv_species}")

        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            sys.exit(1)

        # Get available species and filter to CSV species only
        available_species = analyzer.get_available_species()
        species_to_process = [s for s in csv_species if s in available_species]

        if not species_to_process:
            logger.error("No matching species found between CSV and available presets")
            sys.exit(1)

        logger.info(f"Processing {len(species_to_process)} species (CSV-driven)")

        # Analyze filtered species
        results = analyzer.analyze_all_species(
            parallel=use_parallel,
            max_workers=max_workers,
            species_filter=species_to_process,
        )

        # Save results
        analyzer.save_growth_models()


if __name__ == "__main__":
    # For Windows multiprocessing support
    mp.set_start_method("spawn", force=True)
    main()
