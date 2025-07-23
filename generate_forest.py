#!/usr/bin/env python3
"""
Generate forest models using growpy with global configuration.

This script demonstrates the clean, global config approach where
configuration is set once and automatically used by all functions.
"""
import sys
from pathlib import Path

# Add paths for imports
src_path = Path(__file__).parent / "src"
grove_core_path = src_path / "the_grove_22" / "modules"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(grove_core_path))
import pandas as pd

# Import growpy functions - no config parameters needed!
from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_grove_to_json,
    save_tree_to_usd,
    simulate_forest_growth,
)


def main():
    """Generate forest models using global configuration approach."""
    print("Grove Forest Generator v5.0 - Global Configuration")
    print("=" * 55)

    # Setup paths
    data_dir = Path(__file__).parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"
    csv_path = input_dir / "small_demo.csv"
    config_path = Path(__file__).parent / "config.ini"

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return 1

    # Load configuration - automatically becomes global config
    if config_path.exists():
        config = GrowPyConfig.from_config_file(config_path)
        print(f"✓ Loaded configuration from {config_path.name}")
        print(f"  Random seed: {config.random_seed}")
        print(f"  LOD levels: {config.lod_levels}")
    else:
        config = GrowPyConfig()
        print("✓ Using default configuration")
        print(f"  Random seed: {config.random_seed}")
        print(f"  LOD levels: {config.lod_levels}")

    input_name = csv_path.stem
    print(f"Input: {csv_path}")
    print(f"Output: {output_dir / input_name}")

    # Step 1: Load forest data
    print("\n1. Loading forest data...")
    forest_data = pd.read_csv(csv_path)
    print(f"   Loaded {len(forest_data)} trees from CSV")

    # Step 2: Calculate growth cycles (uses global config automatically)
    print("\n2. Calculating age-based growth cycles...")
    calculate_growth_cycles_from_height(forest_data)
    max_cycles = forest_data["growth_cycles"].max()
    print(f"   ✓ Maximum growth cycles: {max_cycles}")

    # Step 3: Create forest groves (uses global config automatically)
    print("\n3. Creating species-specific groves...")
    forest = create_forest(forest_data)
    species_count = len(forest)
    total_trees = sum(tree_count for _, _, tree_count in forest)
    print(f"   ✓ Created {species_count} species groves with {total_trees} total trees")

    # Step 4: Simulate forest growth (uses global config automatically)
    print(f"\n4. Simulating {max_cycles} growth cycles...")
    simulate_forest_growth(forest, max_cycles)
    print("   ✓ Growth simulation completed")

    # Step 5: Export models (uses global config LOD settings)
    print("\n5. Exporting tree models...")
    forest_dir = output_dir / input_name
    forest_dir.mkdir(parents=True, exist_ok=True)
    
    # Get LOD configs from global config
    lod_configs = config.get_lod_configs()
    total_models_exported = 0
    
    for grove, species_name, tree_count in forest:
        species_name_clean = species_name.replace(" ", "").replace("-", "_")
        
        # Export grove JSON for Blender import
        json_filename = f"{species_name_clean}_grove.json"
        json_path = forest_dir / json_filename
        save_grove_to_json(grove, json_path)
        
        # Export individual tree models with all LOD variants
        lod_models = build_lod_models(grove, lod_configs)
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                model_filename = f"{species_name_clean}_{lod_name}_{i:03d}.usda"
                model_path = forest_dir / model_filename
                save_tree_to_usd(model, model_path)
                total_models_exported += 1
    
    print(f"   ✓ Exported {total_models_exported} tree models")
    print(f"   ✓ Files saved to: {forest_dir}")
    
    print(f"\n🌳 Forest generation completed successfully!")
    print(f"   Species: {species_count}")
    print(f"   Trees: {total_trees}")
    print(f"   Models: {total_models_exported}")
    print(f"   LOD levels: {len(lod_configs)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
