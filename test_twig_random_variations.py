#!/usr/bin/env python3
"""
Test the enhanced random twig variation assignment system.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_random_twig_variations():
    """Test the random twig variation assignment functionality."""
    print("🎲 Testing Random Twig Variation Assignment")
    print("=" * 50)

    # Test species with multiple twig variations
    test_species = [
        ("Scots pine", "Should have apical, lateral, main, and variations"),
        ("Paper birch", "Should have many end and side variations"),
        ("European beech", "Should have apical and lateral variations"),
        ("Silver fir", "Should have only main (no variations)"),
    ]

    try:
        from growpy.config import GrowPyConfig
        from growpy.twig import assign_twig_variations_randomly

        print("✅ Successfully imported required modules")
    except Exception as e:
        print(f"❌ Error importing modules: {e}")
        return False

    config = GrowPyConfig()

    for species_name, description in test_species:
        print(f"\n🌳 Testing {species_name}")
        print(f"   Expected: {description}")

        try:
            # Get available twig files by type
            twig_files_by_type = config.get_twig_files_by_type(species_name)

            if not twig_files_by_type:
                print(f"   ⚠️  No twig files found for {species_name}")
                continue

            print(f"   Available types: {list(twig_files_by_type.keys())}")

            # Create mock twig instances for testing
            twig_instances_by_type = {}

            for twig_type, files in twig_files_by_type.items():
                # Create multiple instances to test variation distribution
                num_instances = 10 if len(files) > 1 else 3
                twig_instances_by_type[twig_type] = []

                for i in range(num_instances):
                    twig_instances_by_type[twig_type].append(
                        {
                            "position": (i * 0.1, i * 0.1, i * 0.1),
                            "orientation": (1.0, 0.0, 0.0, 0.0),
                            "instance_index": i,
                        }
                    )

            # Test random assignment with a fixed seed for reproducibility
            print(f"   Testing with seed 12345...")
            assignments_1 = assign_twig_variations_randomly(
                twig_instances_by_type,
                twig_files_by_type,
                species_name,
                random_seed=12345,
            )

            # Test with different seed to verify randomness
            print(f"   Testing with seed 54321...")
            assignments_2 = assign_twig_variations_randomly(
                twig_instances_by_type,
                twig_files_by_type,
                species_name,
                random_seed=54321,
            )

            # Analyze results
            total_files_1 = len(assignments_1)
            total_files_2 = len(assignments_2)
            total_instances_1 = sum(len(a["instances"]) for a in assignments_1.values())
            total_instances_2 = sum(len(a["instances"]) for a in assignments_2.values())

            print(f"   Results comparison:")
            print(
                f"     Seed 12345: {total_files_1} variations, {total_instances_1} instances"
            )
            print(
                f"     Seed 54321: {total_files_2} variations, {total_instances_2} instances"
            )

            # Check if different seeds produce different distributions (for species with variations)
            has_variations = any(
                len(files) > 1 for files in twig_files_by_type.values()
            )
            if has_variations:
                files_1 = set(assignments_1.keys())
                files_2 = set(assignments_2.keys())

                if files_1 != files_2:
                    print(
                        f"   ✅ Different seeds produce different variation selections"
                    )
                else:
                    print(
                        f"   ⚠️  Seeds produced same variations (might be expected for small sets)"
                    )
            else:
                print(f"   ℹ️  Single variation per type - no randomness expected")

        except Exception as e:
            print(f"   ❌ Error testing {species_name}: {e}")

    print(f"\n🔬 Testing specific variation patterns:")

    # Test Scots pine specifically (should have most variations)
    try:
        twig_files_by_type = config.get_twig_files_by_type("Scots pine")

        if (
            "variation" in twig_files_by_type
            and len(twig_files_by_type["variation"]) > 1
        ):
            print(f"\n   🌲 Scots Pine Variation Test:")
            print(f"   Variation files: {len(twig_files_by_type['variation'])}")

            # Create many instances to see distribution
            mock_instances = {
                "variation": [
                    {
                        "position": (i * 0.1, 0, 0),
                        "orientation": (1, 0, 0, 0),
                        "instance_index": i,
                    }
                    for i in range(20)
                ]
            }

            assignments = assign_twig_variations_randomly(
                mock_instances, twig_files_by_type, "Scots pine", random_seed=42
            )

            variation_usage = {}
            for file_key, assignment in assignments.items():
                if assignment["type"] == "variation":
                    file_name = assignment["file"].stem
                    variation_usage[file_name] = len(assignment["instances"])

            print(f"   Distribution across {len(variation_usage)} variations:")
            for var_name, count in variation_usage.items():
                short_name = var_name.split("_")[-1] if "_" in var_name else var_name
                print(f"     {short_name}: {count} instances")

    except Exception as e:
        print(f"   ❌ Error in Scots pine test: {e}")

    print(f"\n🎉 Random variation assignment testing complete!")
    print(
        f"💡 The system should now distribute twig variations randomly within type groups"
    )
    print(f"   creating more natural-looking forests with varied twig appearances.")

    return True


if __name__ == "__main__":
    test_random_twig_variations()
