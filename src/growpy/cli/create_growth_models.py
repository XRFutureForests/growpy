#!/usr/bin/env python3
"""
Create growth models for Grove species.

Generates height curves and age prediction models with intelligent early termination.

Supports two CSV formats:
  1. Forest placement CSV (x, y, species, height) - auto-extracts unique species
  2. Asset lookup CSV (Common Name, Preset, Twig, Bark Texture) - direct asset reference

Quick Start:
    # Basic growth model generation with defaults shown
    python src/growpy/cli/create_growth_models.py \
        --csv data/input/test.csv \
        --cycles 125 \
        --seeds 1 \
        --height-threshold 0.05 \
        --max-cycles-without-growth 3 \
        --timeout 300
    
    # Quick analysis (fewer cycles)
    python src/growpy/cli/create_growth_models.py --cycles 25
    
    # Analyze specific species
    python src/growpy/cli/create_growth_models.py \
        --species "European oak" \
        --cycles 125 \
        --seeds 3
    
    # Analyze all 57 species
    python src/growpy/cli/create_growth_models.py \
        --csv src/growpy/config/tree_asset_lookup.csv \
        --cycles 125

Common Flags (current):
    --csv PATH                Species CSV (default: data/input/test.csv)
    --cycles INT              Maximum growth cycles (default: 125)
    --seeds INT               Random seeds to average (default: 1)
    --height-threshold FLOAT  Minimum growth to continue (default: 0.05)
    --max-cycles-without-growth INT  Stop after N flat cycles (default: 3)
    --timeout INT             Max simulation time per seed in seconds (default: 300)
    --species TEXT            Analyze a specific species (optional)

Full Documentation:
    See docs/archive/cli-reference.md for complete flag reference and examples

Note:
    Run prepare_assets.py first to copy species presets from Grove installation.

Usage:
    python src/growpy/cli/create_growth_models.py [options]
"""

import argparse
import sys
from pathlib import Path

from growpy.utils.analysis import SpeciesGrowthAnalyzer


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

    # Analyze specific species
    python src/growpy/cli/create_growth_models.py --species "European oak"

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
        """,
    )

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_assets_dir = script_dir / "data" / "assets"

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

    args = parser.parse_args()

    # Check assets directory
    if not default_assets_dir.exists():
        sys.exit(1)

    # Check for presets directory
    presets_dir = default_assets_dir / "presets"
    if not presets_dir.exists():
        sys.exit(1)

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(
        default_assets_dir,
        args.cycles,
        args.seeds,
        args.height_threshold,
        args.max_cycles_without_growth,
        args.timeout,
    )

    if args.species:
        # Analyze single species

        available_species = analyzer.get_available_species()
        if args.species not in available_species:
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

        # Save results
        analyzer.save_growth_models()

    else:
        # Analyze species from CSV

        # Load CSV to get species list
        import pandas as pd

        try:
            df = pd.read_csv(args.csv)

            # Check if this is a forest placement CSV (has "species" column)
            if "species" in df.columns and "Common Name" not in df.columns:
                unique_species = df["species"].dropna().unique().tolist()

                # Load the asset lookup table to get standardized names
                asset_lookup_path = (
                    script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
                )
                if not asset_lookup_path.exists():
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

                if not csv_species:
                    sys.exit(1)

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

        except Exception as e:
            sys.exit(1)

        # Get available species and filter to CSV species only
        available_species = analyzer.get_available_species()
        species_to_process = [s for s in csv_species if s in available_species]

        if not species_to_process:
            sys.exit(1)

        # Analyze filtered species
        results = analyzer.analyze_all_species(
            parallel=False,
            max_workers=None,
            species_filter=species_to_process,
        )

        # Save results
        analyzer.save_growth_models()


if __name__ == "__main__":
    main()
