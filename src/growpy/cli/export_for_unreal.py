#!/usr/bin/env python3
"""
Export trees for Unreal Engine vegetation with procedural variations.

Usage:
    python export_for_unreal.py [csv_file] [--output-dir DIR] [--variations N]
"""

# IMPORTANT: Import bpy first to avoid DLL loading issues on Windows
try:
    import bpy
except (ImportError, OSError):
    bpy = None

from pathlib import Path
import pandas as pd

from growpy import (
    GrowPyConfig,
    get_config,
    batch_export_trees_for_unreal,
    EXPORT_AVAILABLE,
)


def main():
    """Main export function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export trees for Unreal Engine vegetation plugin with variations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV Format:
    Required columns: x, y, species, height
    Optional columns: z (defaults to 0)

Exports:
    - USD files (for Nanite in UE 5.7+)
    - JSON metadata (for PCG and Foliage setup)

Examples:
    # Export with 3 variations per species
    python export_for_unreal.py forest_data.csv

    # Export with 5 variations
    python export_for_unreal.py forest_data.csv --variations 5
        """
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        nargs='?',
        default=None,
        help="Path to CSV file with forest data (x, y, species, height)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/unreal_vegetation"),
        help="Directory to save exported assets (default: data/output/unreal_vegetation)"
    )
    parser.add_argument(
        "--variations",
        type=int,
        default=3,
        help="Number of variations per species (default: 3)"
    )

    args = parser.parse_args()

    if not EXPORT_AVAILABLE:
        print("ERROR: Export not available - bpy module required")
        print("Make sure you're running with Blender's Python or have bpy installed")
        return

    try:
        # Determine CSV path
        if args.csv_file:
            csv_path = args.csv_file
        else:
            # Look for common CSV file locations
            project_root = Path(__file__).parent.parent.parent.parent
            possible_csvs = [
                project_root / "data" / "input" / "mini_tree_inventory_32632.csv",
                project_root / "data" / "forest.csv",
                project_root / "forest_data.csv",
                Path("forest.csv"),
            ]

            csv_path = None
            for path in possible_csvs:
                if path.exists():
                    csv_path = path
                    break

            if csv_path is None:
                print("ERROR: No CSV file found")
                print("Usage: python export_for_unreal.py <csv_file>")
                print("Or place forest.csv in data/ or current directory")
                return

        if not csv_path.exists():
            print(f"ERROR: CSV file not found: {csv_path}")
            return

        print(f"Loading forest data from: {csv_path}")

        # Load forest data
        forest_data = pd.read_csv(csv_path)
        required_columns = ['x', 'y', 'species', 'height']

        # Check required columns
        missing_cols = [col for col in required_columns if col not in forest_data.columns]
        if missing_cols:
            print(f"ERROR: CSV missing required columns: {missing_cols}")
            print(f"   Available columns: {list(forest_data.columns)}")
            print(f"   Required columns: {required_columns}")
            return

        print(f"\nExporting {len(forest_data['species'].unique())} species with {args.variations} variations each")
        print(f"Format: USD")
        print(f"Output: {args.output_dir}\n")

        config = get_config()
        results = batch_export_trees_for_unreal(
            forest_data,
            args.output_dir,
            config,
            num_variations=args.variations
        )

        # Print summary
        print(f"\n{'='*60}")
        print("Export Complete!")
        print(f"{'='*60}")
        print(f"USD files: {len(results['usd'])}")
        print(f"Metadata files: {len(results['metadata'])}")
        print(f"\nOutput directory: {args.output_dir}")
        print(f"\nImport instructions saved to: {args.output_dir / 'import_metadata.json'}")

    except Exception as e:
        print(f"ERROR: Export failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()