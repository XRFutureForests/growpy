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

import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    simulate_forest_growth,
)


def simulate_forest_growth_with_progress(forest, cycles, pbar):
    """Simulate forest growth with progress tracking."""
    # Import grove core here to match the original function
    try:
        import the_grove_22_core as gc
    except ImportError:
        raise ImportError("Grove core not available")

    groves = [grove for grove, _, _ in forest]

    for cycle in range(cycles):
        # Calculate shared light competition between species
        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                all_coords.extend(grove.create_shade_geometry_coords())

            for grove in groves:
                grove.calculate_shade_together(all_coords)

        # Simulate one growth cycle for each grove
        for grove, _, _ in forest:
            grove.weigh_and_bend()
            grove.simulate(1)
        
        # Update progress bar
        pbar.update(1)
        pbar.set_postfix({
            'cycle': f'{cycle + 1}/{cycles}',
            'groves': len(groves)
        })


def main():
    """Simple forest generation workflow."""
    print("🌲 GrowPy Forest Generator")
    print("=" * 30)

    # Fixed paths - no command line arguments needed
    csv_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "input" / "small_demo.csv"
    )
    output_dir = (
        Path(__file__).parent.parent.parent.parent / "data" / "output" / csv_path.stem
    )

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
    
    # Create a custom simulation function with progress tracking
    if max_cycles > 0:
        with tqdm(total=max_cycles, desc="Growth cycles", unit="cycle") as pbar:
            # We'll need to modify simulate_forest_growth or create our own version
            # For now, let's call the original function and update progress manually
            simulate_forest_growth_with_progress(forest, max_cycles, pbar)
    
    print(f"✓ Growth simulation complete")

    # Export to USD
    print(f"\n💾 Exporting to USD")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()

    # Calculate total number of models to export for progress tracking
    total_models = 0
    export_tasks = []
    
    for grove, species_name, tree_count in forest:
        species_clean = species_name.replace(" ", "").replace("-", "_")
        lod_models = build_lod_models(grove, lod_configs)
        
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                export_tasks.append((model, output_dir / filename, species_clean, lod_name, i))
                total_models += 1

    # Export with progress bar
    total_exported = 0
    with tqdm(total=total_models, desc="Exporting USD", unit="model") as pbar:
        for model, filepath, species, lod_name, index in export_tasks:
            save_tree_to_usd(model, filepath)
            total_exported += 1
            pbar.update(1)
            pbar.set_postfix({
                'species': species,
                'lod': lod_name,
                'exported': total_exported
            })

    print(f"✓ Exported {total_exported} USD models")


if __name__ == "__main__":
    sys.exit(main())
