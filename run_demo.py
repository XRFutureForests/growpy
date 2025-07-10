#!/usr/bin/env python3
"""
Run GrowPy with the demo_forest.csv file to generate trees.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import growpy


def main():
    """Run tree generation demo."""
    print("=== GrowPy Demo - Forest Generation ===")
    print()

    # Get Grove info
    grove_info = growpy.get_grove_info()
    print(f"Grove Version: {grove_info['version']}")
    print(f"Grove Edition: {grove_info['edition']}")
    print()

    # List available species
    print("Available species:")
    species = growpy.list_species()
    print(f"Found {len(species)} species presets")
    for i, sp in enumerate(species[:10]):  # Show first 10
        print(f"  {i+1:2d}. {sp}")
    if len(species) > 10:
        print(f"  ... and {len(species) - 10} more")
    print()

    # Path to demo forest CSV
    csv_path = Path("data/demo_forest.csv")

    if not csv_path.exists():
        print(f"Error: {csv_path} not found!")
        return 1

    print(f"Loading forest data from: {csv_path}")

    # Run with default configuration (individual trees)
    try:
        print("\n--- Generating individual trees with mixed species simulation ---")
        config = growpy.GrowPyConfig(
            growth_cycles=10,
            resolution=20,
            random_seed=42,
        )

        files = growpy.generate_trees(csv_path, config)
        print(
            f"\nSuccess! Generated {len(files)} individual tree files with proper positioning:"
        )
        for file_path in files[:5]:  # Show first 5
            print(f"  - {file_path}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more files")

    except Exception as e:
        print(f"Error generating trees: {e}")

    print("\n=== Demo Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
