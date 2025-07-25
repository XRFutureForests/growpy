#!/usr/bin/env python3
"""Debug Grove core USD generation to identify corruption source."""

import sys

sys.path.append("/Users/maximiliansperlich/Developer/the-grove/src")

from pathlib import Path

import pandas as pd

try:
    import the_grove_22_core as gc

    print("✓ Grove core imported successfully")
except ImportError as e:
    print(f"✗ Error importing Grove core: {e}")
    sys.exit(1)

from growpy.config import GrowPyConfig
from growpy.grove import create_forest, simulate_forest_growth
from growpy.tree import calculate_growth_cycles_from_height


def main():
    print("🔍 Debugging Grove core USD generation...")

    # Load minimal forest data
    csv_path = Path(
        "/Users/maximiliansperlich/Developer/the-grove/data/input/small_demo.csv"
    )
    if not csv_path.exists():
        print(f"✗ CSV file not found: {csv_path}")
        return

    forest_data = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(forest_data)} trees from CSV")

    # Take just one tree for debugging
    forest_data = forest_data.head(1)
    print(f"🎯 Testing with single tree: {forest_data.iloc[0]['species']}")

    # Calculate growth cycles
    calculate_growth_cycles_from_height(forest_data)

    # Create forest
    forest = create_forest(forest_data)
    grove, species_name, tree_count = forest[0]
    print(f"✓ Created grove for {species_name} with {tree_count} trees")

    # Simulate minimal growth
    simulate_forest_growth(forest, 1)
    print(f"✓ Growth simulation complete")

    # Build a simple model
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()

    # Get the first LOD configuration
    lod_name = list(lod_configs.keys())[0]
    lod_config = lod_configs[lod_name]
    print(f"🔧 Using LOD: {lod_name} with config: {lod_config}")

    # Build one model
    print("🏗️  Building model...")
    try:
        model = grove.build_model(**lod_config)
        print(f"✓ Model built successfully")
        print(f"  Model type: {type(model)}")
        if hasattr(model, "__dict__"):
            print(f"  Model attributes: {list(model.__dict__.keys())}")
    except Exception as e:
        print(f"✗ Error building model: {e}")
        return

    # Convert to USD string
    print("🔄 Converting to USD string...")
    try:
        usd_string = gc.io.model_to_usda_string(model)
        print(f"✓ USD conversion successful")
        print(f"  USD string length: {len(usd_string)} characters")

        # Check the first and last few lines
        lines = usd_string.split("\n")
        print(f"  Total lines: {len(lines)}")
        print("  First 5 lines:")
        for i, line in enumerate(lines[:5]):
            print(f"    {i+1}: {repr(line)}")

        print("  Last 5 lines:")
        for i, line in enumerate(lines[-5:]):
            print(f"    {len(lines)-5+i+1}: {repr(line)}")

        # Check for suspicious content
        if not usd_string.startswith("#usda"):
            print("⚠️  WARNING: USD string doesn't start with '#usda'")
            print(f"  Actually starts with: {repr(usd_string[:50])}")

        # Look for coordinate patterns
        import re

        coord_pattern = r"\(\d+\.\d+,\s*\d+\.\d+"
        coords = re.findall(coord_pattern, usd_string[:1000])
        if coords:
            print(
                f"⚠️  Found coordinate-like patterns in first 1000 chars: {coords[:3]}"
            )

    except Exception as e:
        print(f"✗ Error converting to USD: {e}")
        import traceback

        traceback.print_exc()
        return

    # Write to a test file
    test_output = Path(
        "/Users/maximiliansperlich/Developer/the-grove/debug_output.usda"
    )
    print(f"💾 Writing test output to: {test_output}")
    try:
        with open(test_output, "w") as f:
            f.write(usd_string)
        print(f"✓ Test file written successfully")

        # Verify the written file
        with open(test_output, "r") as f:
            first_line = f.readline()
            print(f"  First line of written file: {repr(first_line)}")

    except Exception as e:
        print(f"✗ Error writing test file: {e}")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
