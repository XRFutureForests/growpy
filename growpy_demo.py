"""
GrowPy Demo - Complete demonstration of forest generation from CSV data

This script demonstrates all features of the GrowPy module:
- CSV validation
- Species listing and filtering
- Individual tree generation
- Combined forest generation
- Custom CSV creation
- Error handling

Run this script to see GrowPy in action with various examples.
"""

import sys
from pathlib import Path
from typing import List, Dict

# Add src directory to path for importing growpy
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from growpy import (
    grow_forest_from_csv,
    grow_combined_forest_from_csv,
    list_available_species,
    validate_csv_format,
)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def demo_species_exploration():
    """Demonstrate species listing and filtering"""
    print_section("Available Species Exploration")

    species = list_available_species()
    print(f"Total species available: {len(species)}")

    # Group by family
    families = {}
    for species_name in species:
        if " - " in species_name and not species_name.startswith("."):
            family = species_name.split(" - ")[0]
            if family not in families:
                families[family] = []
            families[family].append(species_name)

    print(f"Organized into {len(families)} botanical families:")
    for family, species_list in sorted(families.items()):
        print(f"\n  📁 {family}: {len(species_list)} species")
        for species in species_list[:3]:  # Show first 3 per family
            print(f"     - {species}")
        if len(species_list) > 3:
            print(f"     ... and {len(species_list) - 3} more")


def demo_csv_validation():
    """Demonstrate CSV validation with various scenarios"""
    print_section("CSV Validation Examples")

    # Test with demo CSV
    demo_csv = Path("data/demo_forest.csv")
    if demo_csv.exists():
        is_valid, message = validate_csv_format(demo_csv)
        print(f"✅ Demo CSV validation: {message}")

    # Create and test various CSV scenarios
    test_cases = [
        {
            "name": "Valid CSV",
            "content": "x,y,z,species,age,height\n0,0,0,Fagaceae - European oak,20,10.0",
            "expected": True,
        },
        {
            "name": "Missing required column",
            "content": "x,y,species,age\n0,0,Oak,20",
            "expected": False,
        },
        {
            "name": "Invalid data types",
            "content": "x,y,z,species,age\nabc,0,0,Oak,twenty",
            "expected": False,
        },
    ]

    temp_dir = Path("temp_validation")
    temp_dir.mkdir(exist_ok=True)

    for case in test_cases:
        test_file = temp_dir / f"test_{case['name'].lower().replace(' ', '_')}.csv"
        with open(test_file, "w") as f:
            f.write(case["content"])

        is_valid, message = validate_csv_format(test_file)
        status = "✅" if is_valid == case["expected"] else "❌"
        print(f"{status} {case['name']}: {message}")

    # Cleanup
    for file in temp_dir.glob("*.csv"):
        file.unlink()
    temp_dir.rmdir()


def demo_quick_forest():
    """Quick demo with 3 different tree species"""
    print_section("Quick Forest Demo (3 Trees)")

    # Create a simple CSV with 3 different trees
    demo_csv = Path("quick_demo.csv")
    csv_content = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,20,10.0
15,0,0,Pinaceae - Scots pine,15,8.0
-15,0,0,Betulaceae - Silver birch,12,6.0"""

    with open(demo_csv, "w") as f:
        f.write(csv_content)

    print("Tree composition:")
    print("  🌳 European Oak (20 years) at (0, 0, 0)")
    print("  🌲 Scots Pine (15 years) at (15, 0, 0)")
    print("  🌿 Silver Birch (12 years) at (-15, 0, 0)")

    # Generate the tree models
    output_dir = Path("output/quick_demo")
    generated_files = grow_forest_from_csv(
        csv_file=demo_csv,
        output_dir=output_dir,
        resolution=12,  # Medium resolution for demo
        file_prefix="quick_",
    )

    print(f"\n✅ Generated {len(generated_files)} individual tree models")
    print(f"📁 Output: {output_dir.absolute()}")

    # Cleanup
    demo_csv.unlink()


def demo_custom_forest():
    """Demo with custom CSV data showing various species"""
    print_section("Custom Mixed Species Forest")

    # Create a more diverse forest
    custom_csv = Path("custom_forest.csv")
    custom_data = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,25,12.0
20,5,0,Pinaceae - Scots pine,18,9.0
-20,8,0,Betulaceae - Silver birch,15,7.5
10,-15,0,Salicaceae - Aspen,12,6.8
-10,20,0,Fagaceae - Beech,22,11.2
30,-10,0,Rosaceae - Wild cherry,8,4.5"""

    with open(custom_csv, "w") as f:
        f.write(custom_data)

    print("Creating diverse forest with 6 species:")
    lines = custom_data.strip().split("\n")[1:]  # Skip header
    for i, line in enumerate(lines, 1):
        parts = line.split(",")
        species = parts[3]
        age = parts[4]
        print(f"  {i}. {species} ({age} years old)")

    # Generate individual models
    output_dir = Path("output/custom_forest")
    files = grow_forest_from_csv(
        csv_file=custom_csv,
        output_dir=output_dir,
        resolution=10,  # Slightly lower resolution for speed
        file_prefix="forest_",
    )

    print(f"\n✅ Generated {len(files)} custom tree models")

    # Cleanup
    custom_csv.unlink()


def demo_combined_forest():
    """Demo combined forest generation (single OBJ)"""
    print_section("Combined Forest Generation")

    # Create CSV for combined forest (same species for best results)
    combined_csv = Path("oak_grove.csv")
    combined_data = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,25,12.0
15,10,0,Fagaceae - European oak,20,10.0
-15,12,0,Fagaceae - European oak,18,9.0
8,-18,0,Fagaceae - European oak,22,11.0
-12,-15,0,Fagaceae - European oak,16,8.5"""

    with open(combined_csv, "w") as f:
        f.write(combined_data)

    print("Creating oak grove with 5 trees of varying ages")
    print("(Combined forests work best with same species)")

    # Generate combined model
    output_file = Path("output/oak_grove_combined.obj")
    result_file = grow_combined_forest_from_csv(
        csv_file=combined_csv, output_file=output_file, resolution=14
    )

    print(f"✅ Generated combined oak grove: {Path(result_file).name}")

    # Cleanup
    combined_csv.unlink()


def demo_full_forest():
    """Demo with the included 20-tree demo forest"""
    print_section("Full Demo Forest (20 Trees)")

    demo_csv = Path("data/demo_forest.csv")
    if not demo_csv.exists():
        print(f"❌ Demo forest CSV not found: {demo_csv}")
        return

    print("Using included demo forest with 20 mixed-species trees")

    # Show a few example trees from the demo
    with open(demo_csv, "r") as f:
        lines = f.readlines()
        print("Sample trees from demo forest:")
        for i, line in enumerate(lines[1:6], 1):  # Show first 5 trees
            parts = line.strip().split(",")
            if len(parts) >= 5:
                species = parts[3]
                age = parts[4]
                print(f"  {i}. {species} ({age} years)")
        print(f"  ... and {len(lines) - 6} more trees")

    # Generate with lower resolution for speed
    output_dir = Path("output/full_demo")
    files = grow_forest_from_csv(
        csv_file=demo_csv,
        output_dir=output_dir,
        resolution=8,  # Lower resolution for faster demo
        file_prefix="demo_",
    )

    print(f"\n✅ Generated {len(files)} tree models from demo forest")


def demo_error_handling():
    """Demonstrate error handling scenarios"""
    print_section("Error Handling Examples")

    # Test non-existent file
    try:
        grow_forest_from_csv("non_existent_file.csv")
    except FileNotFoundError as e:
        print(f"✅ Correctly handled missing file: {type(e).__name__}")

    # Test invalid CSV format
    invalid_csv = Path("invalid.csv")
    with open(invalid_csv, "w") as f:
        f.write("not,a,valid,csv\nabc,def,ghi,jkl")

    try:
        grow_forest_from_csv(invalid_csv)
    except ValueError as e:
        print(f"✅ Correctly handled invalid CSV: {type(e).__name__}")

    # Cleanup
    invalid_csv.unlink()

    print("✅ Error handling working correctly")


def show_results_summary():
    """Show summary of all generated files"""
    print_section("Results Summary")

    output_base = Path("output")
    if output_base.exists():
        total_files = 0
        total_size = 0

        print("Generated files by category:")
        for subdir in output_base.iterdir():
            if subdir.is_dir():
                obj_files = list(subdir.glob("*.obj"))
                if obj_files:
                    dir_size = sum(f.stat().st_size for f in obj_files)
                    total_files += len(obj_files)
                    total_size += dir_size

                    print(f"\n  📁 {subdir.name}/")
                    print(f"     Files: {len(obj_files)}")
                    print(f"     Size: {dir_size / (1024*1024):.1f} MB")

                    # Show first few files
                    for obj_file in obj_files[:3]:
                        print(f"     - {obj_file.name}")
                    if len(obj_files) > 3:
                        print(f"     ... and {len(obj_files) - 3} more")

        print(f"\n🎯 Total: {total_files} OBJ files, {total_size / (1024*1024):.1f} MB")
        print("💡 Import these files into Blender, Maya, Unity, or any 3D software")
    else:
        print("No output files found")


def main():
    """Run all demonstrations"""
    print("🌳 GrowPy Complete Demonstration")
    print("Showcasing forest generation from CSV data")

    try:
        # Run all demos
        demo_species_exploration()
        demo_csv_validation()
        demo_quick_forest()
        demo_custom_forest()
        demo_combined_forest()
        demo_full_forest()
        demo_error_handling()
        show_results_summary()

        print_section("Demo Complete!")
        print("✅ All GrowPy features demonstrated successfully")
        print("📚 See src/growpy/README.md for complete documentation")
        print("🚀 Start using GrowPy with your own CSV data!")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
