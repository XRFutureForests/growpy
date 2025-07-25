#!/usr/bin/env python3
"""
Simple forest generation using GrowPy.

This script provides a streamlined forest simulation workflow:
1. Load CSV with tree positions, species, heights
2. Calculate growth cycles from height data using pre-computed models
3. Create multi-species forest with light competition
4. Export to USD with multiple LOD levels
5. Add twig instances and bark materials
"""
import sys
from pathlib import Path

# Add paths for imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))
import pandas as pd

from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    simulate_forest_growth,
    twig,
)


def main():
    """Simple forest generation workflow."""
    print("🌲 GrowPy Forest Generator")
    print("=" * 30)

    # Fixed paths - no command line arguments needed
    csv_path = Path(__file__).parent.parent.parent.parent / "data" / "input" / "small_demo.csv"
    output_dir = Path(__file__).parent.parent.parent.parent / "data" / "output" / csv_path.stem

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return 1

    # Load forest data
    print(f"\n📊 Loading forest data")
    forest_data = pd.read_csv(csv_path)

    print(f"✓ Loaded {len(forest_data)} trees")
    print(f"  Species: {forest_data['species'].nunique()}")

    # Calculate growth cycles using pre-computed models
    print(f"\n🧮 Calculating growth cycles")
    calculate_growth_cycles_from_height(forest_data)
    max_cycles = int(forest_data["growth_cycles"].max())
    print(f"✓ Max growth cycles: {max_cycles}")

    # Create forest
    print(f"\n🌳 Creating multi-species forest")
    forest = create_forest(forest_data)
    print(f"✓ Created {len(forest)} species groves")

    # Simulate growth with light competition
    print(f"\n🌱 Simulating growth ({max_cycles} cycles)")
    simulate_forest_growth(forest, max_cycles)
    print(f"✓ Growth simulation complete")

    # Export to USD
    print(f"\n💾 Exporting to USD")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()

    total_exported = 0
    for grove, species_name, tree_count in forest:
        species_clean = species_name.replace(" ", "").replace("-", "_")
        lod_models = build_lod_models(grove, lod_configs)

        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                save_tree_to_usd(model, output_dir / filename)
                total_exported += 1

    print(f"✓ Exported {total_exported} USD models")


if __name__ == "__main__":
    sys.exit(main())
