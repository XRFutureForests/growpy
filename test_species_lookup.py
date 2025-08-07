#!/usr/bin/env python3
"""
Test script to verify the case-insensitive species lookup functionality.
"""
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from growpy.config import GrowPyConfig


def test_species_lookup():
    """Test the case-insensitive species lookup functionality."""
    config = GrowPyConfig()

    # Test cases from the mini_tree_inventory_32632.csv
    test_species = ["Beech", "Oak", "Silver Fir", "Douglas Fir"]

    print("🧪 Testing Species Lookup")
    print("=" * 40)

    for species in test_species:
        print(f"\nTesting: '{species}'")

        try:
            # Test growth model lookup
            growth_model_path = config.get_growth_model_path(species)
            print(f"  ✓ Growth model: {growth_model_path.name}")

            # Test preset lookup
            preset_path = config.get_preset_path(species)
            print(f"  ✓ Preset: {preset_path.name}")

            # Test bark texture lookup
            bark_texture_path = config.get_bark_texture_path(species)
            if bark_texture_path:
                print(f"  ✓ Bark texture: {bark_texture_path.name}")
            else:
                print(f"  ⚠ Bark texture: None")

            # Test twig lookup
            twig_name = config.get_twig_for_species(species)
            if twig_name:
                print(f"  ✓ Twig: {twig_name}")
            else:
                print(f"  ⚠ Twig: None")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print(f"\n✅ Species lookup test completed!")


if __name__ == "__main__":
    test_species_lookup()
