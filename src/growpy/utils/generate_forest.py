#!/usr/bin/env python3
"""
Simplified forest generation with FBX export.

This script generates a forest from CSV data and exports trees as individual FBX files.
Much simpler than the previous USD-based approach with fewer dependencies and issues.

Usage:
    python generate_forest_fbx.py [csv_file]

Features:
- Load forest data from CSV (position, species, height)
- Calculate growth cycles from height data
- Create realistic forest with light competition
- Export trees as individual FBX files with skeletons
- No positioning issues or complex USD workflows
"""

import sys
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
        print("❌ Export not available - bpy module required")
        return

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return

    print(f"🌲 Loading forest data from: {csv_path}")

    # Load forest data
    try:
        forest_data = pd.read_csv(csv_path)
        required_columns = ['x', 'y', 'species', 'height']

        if not all(col in forest_data.columns for col in required_columns):
            print(f"❌ CSV must contain columns: {required_columns}")
            return

        print(f"📊 Loaded {len(forest_data)} trees")
        print(f"🌳 Species: {forest_data['species'].nunique()}")

    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return

    # Calculate growth cycles from height
    print("📈 Calculating growth cycles from height data...")
    try:
        calculate_growth_cycles_from_height(forest_data)
    except Exception as e:
        print(f"⚠️ Could not calculate growth cycles: {e}")
        # Use default growth cycles
        forest_data['growth_cycles'] = 10
        forest_data['delay'] = 0

    # Create forest simulation
    print("🌲 Creating forest simulation...")
    try:
        forest = create_forest(forest_data)
        print("🌱 Simulating forest growth...")
        max_cycles = forest_data['growth_cycles'].max()
        simulate_forest_growth(forest, max_cycles)
    except Exception as e:
        print(f"❌ Forest simulation failed: {e}")
        return

    # Export trees as FBX
    print("📦 Exporting trees as FBX files...")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        exported_files = batch_export_tree_fbx(forest_data, output_dir, config)

        if exported_files:
            print(f"✅ Successfully exported {len(exported_files)} tree FBX files")
            for fbx_path in exported_files:
                print(f"   📄 {fbx_path}")
        else:
            print("⚠️ No FBX files were exported")

    except Exception as e:
        print(f"❌ FBX export failed: {e}")


def main():
    """Main forest generation function."""
    try:
        # Get CSV file path from command line or use default
        if len(sys.argv) > 1:
            csv_path = Path(sys.argv[1])
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
                print("❌ No CSV file found. Usage: python generate_forest_fbx.py [csv_file]")
                return

        config = get_config()
        output_dir = Path("output/forest_fbx")

        print("🌲 Starting forest generation and FBX export...")
        generate_forest_fbx(csv_path, output_dir, config)

    except Exception as e:
        print(f"❌ Generation failed: {e}")


if __name__ == "__main__":
    main()