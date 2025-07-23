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

# Import hierarchical modular functions
from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_grove_to_json,
    save_tree_to_usd,
    simulate_forest_growth,
    set_global_config,
)


def main():
    """Generate forest models using hierarchical modular functions."""
    print("Grove Forest Generator v4.1 - Hierarchical Modular Functions")
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

    # Load configuration and set as global
    if config_path.exists():
        config = GrowPyConfig.from_config_file(config_path, set_as_global=True)
        print(f"Loaded configuration from {config_path.name} and set as global")
    else:
        config = GrowPyConfig()
        set_global_config(config)
        print("Using default configuration and set as global")

    input_name = csv_path.stem
    print(f"Input: {csv_path}")
    print(f"Output: {output_dir / input_name}")

    # Step 1: Load forest data
    print("\n1. Loading forest data...")
    forest_data = pd.read_csv(csv_path)
    print(f"   Loaded {len(forest_data)} trees from CSV")

    # Step 2: Calculate growth cycles
    print("\n2. Calculating growth cycles...")
    calculate_growth_cycles_from_height(forest_data)  # Uses global config automatically
    max_cycles = forest_data["growth_cycles"].max()
    print(f"   Growth cycles calculated: {max_cycles}")

    # Step 3: Create forest groves
    print("\n3. Creating forest groves...")
    forest = create_forest(forest_data)  # Uses global config automatically

    # Step 4: Simulate forest growth
    print("\n4. Simulating forest growth...")
    simulate_forest_growth(forest, max_cycles)

    # Step 5: Export files
    print("\n5. Exporting files...")
    lod_configs = config.get_lod_configs()
    # Export grove JSONs for Blender
    for grove, species_name, tree_count in forest:
        species_name = species_name.replace(" ", "").replace("-", "_")
        forest_dir = output_dir / input_name
        forest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{species_name}_grove.json"
        file_path = forest_dir / filename
        save_grove_to_json(grove, file_path)

        lod_models = build_lod_models(grove, lod_configs)
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                model_path = forest_dir / f"{species_name}_{lod_name}_{i}.usda"
                save_tree_to_usd(model, model_path)


if __name__ == "__main__":
    sys.exit(main())
