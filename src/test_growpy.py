"""
Simple test script for GrowPy module
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from growpy import grow_forest_from_csv, list_available_species, validate_csv_format


def main():
    """Test the GrowPy module with the demo forest data"""

    print("=== GrowPy Test Script ===\n")

    # Show available species (first 10)
    print("Available species (showing first 10):")
    species = list_available_species()
    for i, species_name in enumerate(species[:10]):
        print(f"  {i+1:2d}. {species_name}")
    print(f"  ... and {len(species) - 10} more\n")

    # Test with demo CSV
    demo_csv = Path("../data/demo_forest.csv")
    if not demo_csv.exists():
        print(f"Demo CSV not found at {demo_csv}")
        return

    print("Validating demo CSV format...")
    is_valid, message = validate_csv_format(demo_csv)
    print(f"Validation result: {message}\n")

    if not is_valid:
        print("Cannot proceed with invalid CSV format")
        return

    # Generate forest models
    print("Generating forest models...")
    try:
        output_dir = Path("../data/output/test")
        generated_files = grow_forest_from_csv(
            csv_file=demo_csv,
            output_dir=output_dir,
            resolution=8,  # Lower resolution for faster testing
            validate_format=False,  # Already validated
        )

        print(f"\nSuccessfully generated {len(generated_files)} tree models!")
        print(f"Output directory: {output_dir}")

        # Show first few generated files
        if generated_files:
            print("\nGenerated files:")
            for i, filepath in enumerate(generated_files[:5]):
                print(f"  - {Path(filepath).name}")
            if len(generated_files) > 5:
                print(f"  ... and {len(generated_files) - 5} more")

    except Exception as e:
        print(f"Error generating forest: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
