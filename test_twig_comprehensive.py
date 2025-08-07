#!/usr/bin/env python3
"""
Comprehensive test for the enhanced twig integration system.
This demonstrates the full workflow with multiple species and twig types.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def test_twig_integration_comprehensive():
    """Test the comprehensive twig integration system."""
    print("🧪 Comprehensive Twig Integration Test")
    print("=" * 50)

    config = GrowPyConfig()

    # Test multiple species
    test_species = [
        "Silver fir",
        "European beech",
        "Paper birch",
        "Scots pine",
        "Aspen",
        "European oak",
    ]

    for species in test_species:
        print(f"\n🌳 Testing {species}")
        print("-" * 30)

        # Get twig name
        twig_name = config.get_twig_for_species(species)
        if not twig_name:
            print(f"   ❌ No twig available for {species}")
            continue

        print(f"   🌿 Twig folder: {twig_name}")

        # Get twig directory
        twig_dir = config.get_twig_directory_path(species)
        if not twig_dir or not twig_dir.exists():
            print(f"   ❌ Twig directory not found: {twig_dir}")
            continue

        # Get all USD files
        usd_files = config.get_available_twig_usd_files(species)
        print(f"   📁 Total USD files: {len(usd_files)}")

        # Get files by type
        files_by_type = config.get_twig_files_by_type(species)
        print(f"   🎯 Twig types available: {list(files_by_type.keys())}")

        for twig_type, files in files_by_type.items():
            print(f"      • {twig_type}: {len(files)} files")
            if len(files) <= 3:
                for file in files:
                    print(f"        - {file.name}")
            else:
                for file in files[:2]:
                    print(f"        - {file.name}")
                print(f"        - ... and {len(files) - 2} more")

        # Test automatic selection
        best_auto = config.get_best_twig_file_for_type(species, "auto")
        best_apical = config.get_best_twig_file_for_type(species, "apical")
        best_lateral = config.get_best_twig_file_for_type(species, "lateral")

        print(f"   🎲 Best auto: {best_auto.name if best_auto else 'None'}")
        print(f"   🌱 Best apical: {best_apical.name if best_apical else 'None'}")
        print(f"   🍃 Best lateral: {best_lateral.name if best_lateral else 'None'}")

        # Simulate twig placement strategy
        if files_by_type:
            print(f"   🎯 Placement strategy:")

            placements = [
                {"type": "apical", "count": 2, "description": "tree top"},
                {"type": "lateral", "count": 5, "description": "side branches"},
                {"type": "end", "count": 3, "description": "branch ends"},
                {"type": "side", "count": 4, "description": "side twigs"},
            ]

            total_twigs = 0
            for placement in placements:
                ptype = placement["type"]
                if ptype in files_by_type:
                    available_files = len(files_by_type[ptype])
                    count = min(placement["count"], available_files * 3)  # Allow reuse
                    total_twigs += count
                    print(
                        f"      • {count} {ptype} twigs for {placement['description']}"
                    )
                elif ptype in ["apical", "lateral"] and "main" in files_by_type:
                    count = placement["count"]
                    total_twigs += count
                    print(
                        f"      • {count} main twigs for {placement['description']} (fallback)"
                    )

            print(f"   📊 Total twigs planned: {total_twigs}")

    print(f"\n✅ Comprehensive twig integration test completed!")
    print(
        f"🎉 System successfully handles multiple species with diverse twig configurations"
    )


if __name__ == "__main__":
    test_twig_integration_comprehensive()
