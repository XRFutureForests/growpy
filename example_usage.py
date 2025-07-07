"""
Example usage of the GrowPy module

This script demonstrates how to use GrowPy to generate forest models
from CSV data with different options and settings.
"""

from pathlib import Path
import sys

# Add src directory to path for importing growpy
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from growpy import (
    grow_forest_from_csv,
    grow_combined_forest_from_csv,
    list_available_species,
    validate_csv_format,
)


def example_basic_usage():
    """Basic example - generate trees from demo CSV"""
    print("=== Basic Usage Example ===")

    demo_csv = Path("data/demo_forest.csv")
    if not demo_csv.exists():
        print(f"Demo CSV not found: {demo_csv}")
        return

    # Generate individual tree models
    output_dir = Path("data/output/basic_example")
    files = grow_forest_from_csv(
        csv_file=demo_csv,
        output_dir=output_dir,
        resolution=8,  # Lower resolution for faster generation
        file_prefix="example_",
    )

    print(f"Generated {len(files)} tree models in {output_dir}")
    print()


def example_validation():
    """Example showing CSV validation"""
    print("=== CSV Validation Example ===")

    demo_csv = Path("data/demo_forest.csv")
    if demo_csv.exists():
        is_valid, message = validate_csv_format(demo_csv)
        print(f"Demo CSV validation: {message}")

    # Show what would happen with invalid CSV
    print("Example error messages for invalid CSV:")
    print("  - Missing columns: 'Missing required columns: species, age'")
    print(
        "  - Invalid data: 'Invalid data format in first row: invalid literal for float(): abc'"
    )
    print()


def example_species_list():
    """Example showing available species"""
    print("=== Available Species Example ===")

    species = list_available_species()
    print(f"Total species available: {len(species)}")

    # Group by family
    families = {}
    for species_name in species:
        if " - " in species_name:
            family = species_name.split(" - ")[0]
            if family not in families:
                families[family] = []
            families[family].append(species_name)

    print(f"Organized into {len(families)} families:")
    for family, species_list in sorted(families.items())[:5]:  # Show first 5 families
        print(f"  {family}: {len(species_list)} species")
        for species in species_list[:2]:  # Show first 2 species per family
            print(f"    - {species}")
        if len(species_list) > 2:
            print(f"    ... and {len(species_list) - 2} more")
    print()


def example_custom_csv():
    """Example with custom CSV data"""
    print("=== Custom CSV Example ===")

    # Create a small custom CSV for testing
    custom_csv = Path("data/custom_trees.csv")
    custom_data = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,20,10.0
10,0,0,Pinaceae - Scots pine,15,8.0
-10,0,0,Betulaceae - Silver birch,10,6.0"""

    custom_csv.parent.mkdir(exist_ok=True)
    with open(custom_csv, "w") as f:
        f.write(custom_data)

    print(f"Created custom CSV: {custom_csv}")

    # Generate trees
    output_dir = Path("data/output/custom_example")
    files = grow_forest_from_csv(
        csv_file=custom_csv, output_dir=output_dir, resolution=16, file_prefix="custom_"
    )

    print(f"Generated {len(files)} custom trees")
    print()


def example_combined_forest():
    """Example of combined forest generation"""
    print("=== Combined Forest Example ===")

    # Create a small CSV for combined forest
    combined_csv = Path("data/small_forest.csv")
    combined_data = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,25,12.0
15,0,0,Fagaceae - European oak,20,10.0
30,0,0,Fagaceae - European oak,18,9.0"""

    combined_csv.parent.mkdir(exist_ok=True)
    with open(combined_csv, "w") as f:
        f.write(combined_data)

    print(f"Created small forest CSV: {combined_csv}")

    # Generate combined model
    output_file = Path("data/output/combined_oak_forest.obj")
    result_file = grow_combined_forest_from_csv(
        csv_file=combined_csv, output_file=output_file, resolution=12
    )

    print(f"Generated combined forest: {result_file}")
    print()


def main():
    """Run all examples"""
    print("GrowPy Examples\n")

    try:
        example_validation()
        example_species_list()
        example_basic_usage()
        example_custom_csv()
        example_combined_forest()

        print("All examples completed successfully!")

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
