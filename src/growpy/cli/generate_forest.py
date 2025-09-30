#!/usr/bin/env python3
"""
Forest generation with FBX export.

Usage:
    python generate_forest.py [csv_file]
"""

# IMPORTANT: Import bpy first to avoid DLL loading issues on Windows
try:
    import bpy
except (ImportError, OSError):
    bpy = None

from pathlib import Path
import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    get_config,
    create_forest,
    simulate_forest_growth,
    calculate_growth_cycles_from_height,
    batch_export_tree_fbx,
    EXPORT_AVAILABLE,
)


def generate_forest_fbx(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig
) -> None:
    """Generate forest from CSV data and export as FBX files.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save FBX files
        config: GrowPy configuration
    """
    if not EXPORT_AVAILABLE:
        print("ERROR: Export not available - bpy module required")
        return

    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return

    print(f"Loading forest data from: {csv_path}")

    # Load forest data
    try:
        forest_data = pd.read_csv(csv_path)
        required_columns = ['x', 'y', 'species', 'height']

        # Check required columns
        missing_cols = [col for col in required_columns if col not in forest_data.columns]
        if missing_cols:
            print(f"ERROR: CSV missing required columns: {missing_cols}")
            print(f"   Available columns: {list(forest_data.columns)}")
            print(f"   Required columns: {required_columns}")
            return

        # Ensure z column exists (will be added by create_forest if missing)
        if 'z' not in forest_data.columns:
            print("INFO: No 'z' column found, using z=0 for all trees")


    except Exception as e:
        print(f"ERROR: Error loading CSV: {e}")
        return

    try:
        calculate_growth_cycles_from_height(forest_data)
    except Exception:
        forest_data['growth_cycles'] = 10
        forest_data['delay'] = 0

    try:
        forest = create_forest(forest_data)
        max_cycles = forest_data['growth_cycles'].max()
        simulate_forest_growth(forest, max_cycles)
    except Exception as e:
        print(f"Forest simulation failed: {e}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        exported_files = batch_export_tree_fbx(forest_data, output_dir, config)
        if exported_files:
            print(f"Exported {len(exported_files)} tree FBX files")
    except Exception as e:
        print(f"FBX export failed: {e}")


def main():
    """Main forest generation function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate forest from CSV data and export trees as FBX files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV Format:
    Required columns: x, y, species, height
    Optional columns: z (defaults to 0)

Examples:
    # Generate forest from CSV (auto-detects in data/ or current directory)
    python generate_forest.py

    # Specify CSV file and output directory
    python generate_forest.py forest_data.csv --output-dir output/my_forest
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
        default=Path("output/forest_fbx"),
        help="Directory to save FBX files (default: output/forest_fbx)"
    )

    args = parser.parse_args()

    try:
        # Determine CSV path
        if args.csv_file:
            csv_path = args.csv_file
        else:
            # Look for common CSV file locations
            project_root = Path(__file__).parent.parent.parent.parent
            possible_csvs = [
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
                print("Usage: python generate_forest.py <csv_file>")
                print("Or place forest.csv in data/ or current directory")
                return

        config = get_config()
        generate_forest_fbx(csv_path, args.output_dir, config)

    except Exception as e:
        print(f"ERROR: Generation failed: {e}")


if __name__ == "__main__":
    main()