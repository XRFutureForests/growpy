#!/usr/bin/env python3
"""
Example: Using the species lookup functionality in GrowPyConfig

This demonstrates how to access the CommonName-ScientificName-Model-Twig-BarkTexture.csv
data through the configuration system without having to load it separately in each module.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import growpy
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def main():
    """Example usage of the species lookup functionality."""

    # Create a config instance (though the lookup methods are class methods)
    config = GrowPyConfig()

    print("🌳 GrowPy Species Lookup Example\n")

    # Example 1: Get all available species
    print("📋 Available species:")
    species_list = GrowPyConfig.get_available_species()
    for i, species in enumerate(sorted(species_list), 1):
        print(f"  {i:2d}. {species}")
    print(f"\nTotal: {len(species_list)} species available\n")

    # Example 2: Get detailed data for specific species
    example_species = ["European beech", "Silver birch", "Scots pine"]
    print("🔍 Detailed species information:")

    for species in example_species:
        print(f"\n{species}:")
        data = GrowPyConfig.get_species_data(species)
        if data:
            print(f"  🧬 Scientific name: {data['scientific_name']}")
            print(f"  📁 Model file: {data['model']}")
            print(f"  🌿 Twig: {data['twig']}")
            print(f"  🎨 Bark texture: {data['bark_texture']}")
        else:
            print(f"  ❌ Species not found!")

    # Example 3: Quick access to specific attributes
    print(f"\n🎯 Quick access examples:")
    print(
        f"European beech model: {GrowPyConfig.get_model_for_species('European beech')}"
    )
    print(
        f"Silver birch bark: {GrowPyConfig.get_bark_texture_for_species('Silver birch')}"
    )

    # Example 4: Error handling for unknown species
    print(f"\n⚠️  Error handling:")
    unknown_species = "Magical Rainbow Tree"
    data = GrowPyConfig.get_species_data(unknown_species)
    print(f"Data for '{unknown_species}': {data}")

    # Example 5: Using with practical scenarios
    print(f"\n🛠  Practical usage scenarios:")

    # Scenario 1: Building a tree generator menu
    print("Scenario 1 - Tree generator menu:")
    favorites = ["European oak", "Norway spruce", "Wild cherry"]
    for species in favorites:
        model = GrowPyConfig.get_model_for_species(species)
        if model:
            print(f"  {species} -> {model}")

    # Scenario 2: Batch processing multiple species
    print("\nScenario 2 - Batch processing:")
    birch_species = [s for s in species_list if "birch" in s.lower()]
    print(f"Found {len(birch_species)} birch species:")
    for species in birch_species:
        bark = GrowPyConfig.get_bark_texture_for_species(species)
        print(f"  {species}: {bark}")


if __name__ == "__main__":
    main()
