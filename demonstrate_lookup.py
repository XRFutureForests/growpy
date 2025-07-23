#!/usr/bin/env python3
"""
Comprehensive example of the updated GrowPy species lookup system.

This demonstrates the new terminology (preset instead of model) and the addition
of growth model integration.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def demonstrate_species_lookup():
    """Demonstrate all the updated species lookup functionality."""

    print("🌳 GrowPy Species Lookup - Updated with Presets & Growth Models")
    print("=" * 70)

    # 1. Basic species information
    print("\n📋 1. Basic Species Information")
    print("-" * 30)

    species_count = len(GrowPyConfig.get_available_species())
    families = GrowPyConfig.get_available_families()
    print(f"Total species available: {species_count}")
    print(f"Botanical families represented: {len(families)}")
    print(f"Families: {', '.join(families)}")

    # 2. Detailed species data (new terminology)
    print("\n🔍 2. Detailed Species Data (Note: 'Model' is now 'Preset')")
    print("-" * 55)

    example_species = "European beech"
    data = GrowPyConfig.get_species_data(example_species)

    print(f"Species: {example_species}")
    print(f"  🧬 Scientific name: {data['scientific_name']}")
    print(f"  📁 Preset file: {data['preset']}")  # Changed from 'model'
    print(f"  🌿 Twig type: {data['twig']}")
    print(f"  🎨 Bark texture: {data['bark_texture']}")
    print(f"  📊 Growth model: {data['growth_model']}")  # New!

    # 3. Quick access methods (updated names)
    print("\n🎯 3. Quick Access Methods (Updated Method Names)")
    print("-" * 50)

    test_species = ["Silver birch", "Scots pine", "European oak"]

    for species in test_species:
        preset = GrowPyConfig.get_preset_for_species(
            species
        )  # Changed from get_model_for_species
        growth_model = GrowPyConfig.get_growth_model_for_species(species)  # New!
        scientific = GrowPyConfig.get_scientific_name_for_species(species)  # New!

        print(f"{species} ({scientific}):")
        print(f"  Preset: {preset}")
        print(f"  Growth Model: {growth_model}")

    # 4. Growth model paths (new functionality)
    print("\n📊 4. Growth Model Integration (New Feature)")
    print("-" * 45)

    for species in test_species:
        growth_path = GrowPyConfig.get_growth_model_path(species)
        if growth_path:
            exists = "✅ EXISTS" if growth_path.exists() else "❌ MISSING"
            print(f"{species}: {growth_path.name} ({exists})")

    # 5. Family-based filtering (new functionality)
    print("\n🏷️  5. Family-Based Filtering (New Feature)")
    print("-" * 40)

    interesting_families = ["Fagaceae", "Pinaceae", "Betulaceae"]

    for family in interesting_families:
        species_in_family = GrowPyConfig.get_species_by_family(family)
        print(f"{family} ({len(species_in_family)} species):")
        for species in species_in_family[:3]:  # Show first 3
            growth_model = GrowPyConfig.get_growth_model_for_species(species)
            print(f"  • {species} → {growth_model}")
        if len(species_in_family) > 3:
            print(f"  ... and {len(species_in_family) - 3} more")

    # 6. Practical usage scenarios
    print("\n🛠️  6. Practical Usage Scenarios")
    print("-" * 35)

    print("Scenario A: Building a tree generator with presets and growth models")
    favorites = ["European beech", "Silver birch", "Norway spruce"]

    for species in favorites:
        preset = GrowPyConfig.get_preset_for_species(species)
        growth_model = GrowPyConfig.get_growth_model_for_species(species)
        print(f"  {species}: Preset={preset}, Growth={growth_model}")

    print("\nScenario B: Filtering trees by botanical family")
    deciduous_families = ["Fagaceae", "Betulaceae", "Rosaceae"]

    for family in deciduous_families:
        count = len(GrowPyConfig.get_species_by_family(family))
        print(f"  {family}: {count} species available")

    print("\n✨ Summary of Changes:")
    print(
        "  • 'Model' terminology changed to 'Preset' (clearer distinction from 3D models)"
    )
    print("  • Added 'Growth Model' support linking to growth_models/ directory")
    print("  • New filtering methods by botanical family")
    print("  • Enhanced path resolution for growth model directories")
    print("  • All species now have corresponding growth models available")


if __name__ == "__main__":
    demonstrate_species_lookup()
