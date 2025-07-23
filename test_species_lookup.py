#!/usr/bin/env python3
"""
Test script for the species lookup functionality in GrowPyConfig.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import growpy
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def test_species_lookup():
    """Test the species lookup functionality."""
    print("Testing species lookup functionality...")

    # Test loading available species
    species_list = GrowPyConfig.get_available_species()
    print(f"Found {len(species_list)} species")
    print("Available species:")
    for species in sorted(species_list):
        print(f"  - {species}")

    print("\n" + "=" * 50 + "\n")

    # Test getting specific species data
    test_species = ["European beech", "Scots pine", "Silver birch"]

    for species in test_species:
        print(f"Testing species: {species}")
        data = GrowPyConfig.get_species_data(species)
        if data:
            print(f"  Scientific name: {data['scientific_name']}")
            print(f"  Model: {data['model']}")
            print(f"  Twig: {data['twig']}")
            print(f"  Bark texture: {data['bark_texture']}")
        else:
            print(f"  Species not found!")
        print()

    # Test convenience methods
    print("Testing convenience methods:")
    for species in test_species:
        model = GrowPyConfig.get_model_for_species(species)
        bark = GrowPyConfig.get_bark_texture_for_species(species)
        print(f"{species}: Model={model}, Bark={bark}")

    # Test non-existent species
    print(f"\nTesting non-existent species:")
    fake_species = "Nonexistent Tree"
    data = GrowPyConfig.get_species_data(fake_species)
    print(f"{fake_species}: {data}")


if __name__ == "__main__":
    test_species_lookup()
