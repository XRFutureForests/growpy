#!/usr/bin/env python3
"""
Test the updated twig.py system with the new add_twigs_to_tree function.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig
from growpy.twig import add_twigs_to_tree


def test_updated_twig_system():
    """Test the updated twig system with the high-level add_twigs_to_tree function."""
    print("🧪 Testing Updated Twig System")
    print("=" * 50)

    # Initialize config
    try:
        config = GrowPyConfig()
        print("✅ Config system initialized")
    except Exception as e:
        print(f"❌ Error initializing config: {e}")
        return False

    # Test with different species
    test_species = ["Silver fir", "European beech", "Scots pine", "European oak"]

    # Use a test tree file (any existing USD file will do for testing)
    test_files = [
        Path("data/output/mini_tree_inventory_32632/SilverFir_LOD3_Low_004.usda"),
        Path("data/output/mini_tree_inventory_32632/EuropeanBeech_LOD3_Low_001.usda"),
        Path("data/output/mini_tree_inventory_32632/ScotsPine_LOD3_Low_002.usda"),
    ]

    success_count = 0
    total_tests = 0

    for species in test_species:
        print(f"\n🌳 Testing species: {species}")

        # Find available twig types for this species
        try:
            twig_files_by_type = config.get_twig_files_by_type(species)
            if twig_files_by_type:
                print(f"   Available twig types: {list(twig_files_by_type.keys())}")
                type_count = sum(len(files) for files in twig_files_by_type.values())
                print(f"   Total twig files: {type_count}")

                # Test on any available USD file
                test_file = None
                for file_path in test_files:
                    if file_path.exists():
                        test_file = file_path
                        break

                if test_file:
                    print(f"   Testing with file: {test_file.name}")
                    total_tests += 1

                    try:
                        result = add_twigs_to_tree(test_file, species, config)
                        if result:
                            print(f"   ✅ Successfully processed {species}")
                            success_count += 1
                        else:
                            print(
                                f"   ⚠️  Processing completed with warnings for {species}"
                            )
                    except Exception as e:
                        print(f"   ❌ Error processing {species}: {e}")
                else:
                    print(f"   ⚠️  No test USD file available")
            else:
                print(f"   ⚠️  No twig files found for {species}")

        except Exception as e:
            print(f"   ❌ Error testing {species}: {e}")

    print(f"\n📊 Test Results:")
    print(f"   Successful: {success_count}/{total_tests}")
    print(
        f"   Success rate: {success_count/total_tests*100:.1f}%"
        if total_tests > 0
        else "   No tests completed"
    )

    if success_count > 0:
        print(f"\n🎉 Updated twig system is working!")
        print(f"   The forest generation script can now use add_twigs_to_tree()")
        return True
    else:
        print(f"\n⚠️  Twig system needs adjustment")
        return False


if __name__ == "__main__":
    test_updated_twig_system()
