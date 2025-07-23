#!/usr/bin/env python3
"""
Quick test of the new filtering methods.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def test_new_methods():
    """Test the new filtering methods."""
    print("🌳 Testing New Filtering Methods\n")

    # Test family grouping
    families = GrowPyConfig.get_available_families()
    print(f"Available families ({len(families)}):")
    for family in families:
        species_in_family = GrowPyConfig.get_species_by_family(family)
        print(f"  {family}: {len(species_in_family)} species")
        for species in species_in_family:
            print(f"    - {species}")

    # Test growth model availability
    species_with_models = GrowPyConfig.get_species_with_growth_models()
    print(f"\nSpecies with growth models: {len(species_with_models)}")


if __name__ == "__main__":
    test_new_methods()
