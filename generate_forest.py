#!/usr/bin/env python3
"""
Generate forest models using simplified growpy functions.

This script demonstrates the simplified, atomic functionality of growpy
that directly uses Grove's core capabilities.
"""
import sys
from pathlib import Path

# Add paths for imports
src_path = Path(__file__).parent / "src"
grove_core_path = src_path / "the_grove_22" / "modules"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(grove_core_path))
import pandas as pd

# Import simplified atomic functions
from growpy import (
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest_groves,
    simulate_forest_growth,
)
from growpy.models import save_forest_groves_json, save_forest_usd_models


def main():
    """Generate forest models using simplified growpy functions."""
    print("Grove Forest Generator v4.1 - Simplified Atomic Functions")
    print("=" * 60)

    # Setup paths
    data_dir = Path(__file__).parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"
    csv_path = input_dir / "small_demo.csv"
    config_path = Path(__file__).parent / "config.ini"

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return 1

    # Load configuration
    if config_path.exists():
        config = GrowPyConfig.from_config_file(config_path)
        print(f"Loaded configuration from {config_path.name}")
    else:
        config = GrowPyConfig()
        print("Using default configuration")

    input_name = csv_path.stem
    print(f"Input: {csv_path}")
    print(f"Output: {output_dir / input_name}")

    # Step 1: Load forest data
    print("\n1. Loading forest data...")
    forest_data = pd.read_csv(csv_path)
    print(f"   Loaded {len(forest_data)} trees from CSV")

    # Step 2: Calculate growth cycles
    print("\n2. Calculating growth cycles...")
    calculate_growth_cycles_from_height(forest_data)
    max_cycles = forest_data["growth_cycles"].max()
    print(f"   Growth cycles calculated: {max_cycles}")

    # Step 3: Create forest groves
    print("\n3. Creating forest groves...")
    forest_groves = create_forest_groves(forest_data, config.random_seed)

    # Step 4: Simulate forest growth
    print("\n4. Simulating forest growth...")
    simulate_forest_growth(forest_groves, max_cycles)

    # Step 5: Export files
    print("\n5. Exporting files...")

    # Export grove JSONs for Blender
    grove_dir = output_dir / input_name / "groves"
    save_forest_groves_json(forest_groves, grove_dir)

    # Export USD models with LOD variants
    lod_configs = config.get_selected_lod_configs()
    usd_files = save_forest_usd_models(
        forest_groves, output_dir / input_name, lod_configs, forest_data
    )

    # Final summary
    print("\n" + "=" * 60)
    print("Forest generation complete!")
    print("\nExport Summary:")
    print(f"  Grove JSON files: {len(grove_files)}")
    print(f"  USD model files: {len(usd_files)}")

    print(f"\nOutput structure:")
    print(f"  {grove_dir}/              - JSON files for Blender import")
    print(f"  {output_dir / input_name / 'usd_models'}/  - USD tree files")

    return 0


if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
