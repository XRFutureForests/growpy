#!/usr/bin/env python3
"""
Test script for the updated species lookup functionality with presets and growth models.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import growpy
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def test_updated_species_lookup():
    """Test the updated species lookup functionality."""
    print("🌳 Testing Updated Species Lookup with Presets and Growth Models\n")

    # Test loading available species
    species_list = GrowPyConfig.get_available_species()
    print(f"Found {len(species_list)} species")

    print("\n" + "=" * 60 + "\n")

    # Test getting specific species data with new structure
    test_species = ["European beech", "Silver birch", "Scots pine", "Horse chestnut"]

    for species in test_species:
        print(f"🔍 Testing species: {species}")
        data = GrowPyConfig.get_species_data(species)
        if data:
            print(f"  🧬 Scientific name: {data['scientific_name']}")
            print(f"  📁 Preset: {data['preset']}")
            print(f"  🌿 Twig: {data['twig']}")
            print(f"  🎨 Bark texture: {data['bark_texture']}")
            print(f"  📊 Growth model: {data['growth_model']}")
        else:
            print(f"  ❌ Species not found!")
        print()

    # Test new methods
    print("🎯 Testing new convenience methods:")
    for species in test_species:
        preset = GrowPyConfig.get_preset_for_species(species)
        growth_model = GrowPyConfig.get_growth_model_for_species(species)
        bark = GrowPyConfig.get_bark_texture_for_species(species)
        twig = GrowPyConfig.get_twig_for_species(species)

        print(f"{species}:")
        print(f"  Preset: {preset}")
        print(f"  Growth Model: {growth_model}")
        print(f"  Bark: {bark}")
        print(f"  Twig: {twig}")

        # Test growth model path
        if growth_model:
            growth_path = GrowPyConfig.get_growth_model_path(species)
            print(f"  Growth Model Path: {growth_path}")
            if growth_path and growth_path.exists():
                print(f"  ✅ Growth model directory exists")
            else:
                print(f"  ❌ Growth model directory not found")
        print()

    # Test species with and without growth models
    print("📊 Growth model availability:")
    species_with_growth = []
    species_without_growth = []

    for species in species_list:
        growth_model = GrowPyConfig.get_growth_model_for_species(species)
        if growth_model:
            species_with_growth.append(species)
        else:
            species_without_growth.append(species)

    print(f"Species with growth models: {len(species_with_growth)}")
    print(f"Species without growth models: {len(species_without_growth)}")

    if species_without_growth:
        print(f"Species without growth models: {', '.join(species_without_growth)}")


if __name__ == "__main__":
    test_updated_species_lookup()
