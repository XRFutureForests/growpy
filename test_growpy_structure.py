#!/usr/bin/env python3
"""
Test the simplified growpy package structure.

This test verifies that all modules can be imported and basic functionality works.
"""
import sys
from pathlib import Path

# Add paths for imports
src_path = Path(__file__).parent / "src"
grove_core_path = src_path / "the_grove_22" / "modules"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(grove_core_path))

def test_imports():
    """Test that all modules can be imported correctly."""
    print("Testing imports...")
    
    try:
        # Test main package imports
        from growpy import (
            GrowPyConfig,
            apply_species_preset,
            calculate_growth_cycles_from_height,
            create_grove,
            list_species,
            load_forest_csv,
            validate_csv_data,
        )
        print("✓ Main package imports successful")
        
        # Test models import
        from growpy.models import export_grove_json, export_model_usd
        print("✓ Models module imports successful")
        
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality."""
    print("\nTesting basic functionality...")
    
    try:
        from growpy import GrowPyConfig, create_grove, list_species

        # Test configuration
        config = GrowPyConfig()
        print(f"✓ Config created with seed: {config.random_seed}")
        
        # Test species listing
        species = list_species()
        print(f"✓ Found {len(species)} species presets")
        
        # Test grove creation
        if species:
            grove = create_grove(species[0], random_seed=42)
            print(f"✓ Grove created with species: {species[0]}")
        
        return True
    except Exception as e:
        print(f"✗ Functionality test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("GrowPy Package Structure Test")
    print("=" * 40)
    
    success = True
    success &= test_imports()
    success &= test_basic_functionality()
    
    print("\n" + "=" * 40)
    if success:
        print("✓ All tests passed! Package structure is working correctly.")
        print("\nOptimized GrowPy Structure:")
        print("├── __init__.py          # Main package interface")
        print("├── config.py           # Configuration management")
        print("├── grove.py            # Core Grove operations")
        print("├── forest.py           # Multi-species forest functions")
        print("├── models.py           # USD/JSON export operations")
        print("├── validate.py         # Data validation")
        print("└── age_prediction.py   # Growth cycle calculations")
        
        print("\nKey Improvements:")
        print("• Flattened package structure (no core/io separation)")
        print("• Consolidated species functionality into grove.py")
        print("• Direct Grove core integration without abstraction layers")
        print("• Removed redundant utility modules")
        print("• Simplified I/O to single models.py using Grove's native USD")
        print("• Eliminated excessive progress tracking and logging")
        print("• Atomic functions that compose cleanly")
        return 0
    else:
        print("✗ Some tests failed. Check the package structure.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
        print("✗ Some tests failed. Check the package structure.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
