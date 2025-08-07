#!/usr/bin/env python3
"""
Simple test for twig integration with a test USD file.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def test_twig_system():
    """Test the twig system with Silver fir."""
    print("🧪 Testing Twig System")
    print("=" * 30)

    config = GrowPyConfig()
    species = "Silver fir"

    print(f"🌳 Testing species: {species}")

    # Test twig lookup
    twig_name = config.get_twig_for_species(species)
    print(f"🌿 Twig name: {twig_name}")

    if twig_name:
        # Get available twig files
        twig_files_by_type = config.get_twig_files_by_type(species)
        print(f"📁 Available twig types: {list(twig_files_by_type.keys())}")

        for twig_type, files in twig_files_by_type.items():
            print(f"   • {twig_type}: {len(files)} files")
            for file in files:
                print(f"     - {file.name}")

        # Test best file selection
        best_file = config.get_best_twig_file_for_type(species, "auto")
        print(f"🎯 Best file: {best_file.name if best_file else 'None'}")

        if best_file:
            # Show file content reference name
            file_stem = best_file.stem
            if "_" in file_stem:
                reference_name = file_stem.split("_", 1)[1]
            else:
                reference_name = file_stem
            print(f"🔗 Reference name: {reference_name}")

            # Test file existence
            print(f"📄 File exists: {best_file.exists()}")

            if best_file.exists():
                # Try to read first few lines
                try:
                    with open(best_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()[:5]
                    print(f"📖 File preview ({len(lines)} lines):")
                    for line in lines:
                        print(f"   {line.strip()}")
                except Exception as e:
                    print(f"❌ Error reading file: {e}")

    print("\n✅ Twig system test completed!")


if __name__ == "__main__":
    test_twig_system()
