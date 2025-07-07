"""
Quick demonstration of GrowPy - Generate 3 trees and show the results
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy import grow_forest_from_csv


def main():
    print("GrowPy Quick Demo - Creating 3 Tree Models")
    print("=" * 50)

    # Create a simple CSV with 3 different trees
    demo_csv = Path("demo_3_trees.csv")
    csv_content = """x,y,z,species,age,height
0,0,0,Fagaceae - European oak,20,10.0
15,0,0,Pinaceae - Scots pine,15,8.0
-15,0,0,Betulaceae - Silver birch,12,6.0"""

    with open(demo_csv, "w") as f:
        f.write(csv_content)

    print(f"Created demo CSV: {demo_csv}")
    print("Tree data:")
    print("  1. European Oak (20 years old) at (0, 0, 0)")
    print("  2. Scots Pine (15 years old) at (15, 0, 0)")
    print("  3. Silver Birch (12 years old) at (-15, 0, 0)")
    print()

    # Generate the tree models
    output_dir = Path("demo_trees_output")
    print(f"Generating tree models in {output_dir}...")

    generated_files = grow_forest_from_csv(
        csv_file=demo_csv,
        output_dir=output_dir,
        resolution=12,  # Medium resolution
        file_prefix="demo_",
    )

    print(f"\n✅ Successfully generated {len(generated_files)} tree models!")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print("\n📄 Generated files:")
    for filepath in generated_files:
        filename = Path(filepath).name
        print(f"   - {filename}")

    print(
        f"\n🎯 These OBJ files can be imported into Blender, Maya, or any 3D software"
    )
    print(f"💡 To see all available species, use: list_available_species()")

    # Clean up
    demo_csv.unlink()
    print(f"\n🧹 Cleaned up demo CSV file")


if __name__ == "__main__":
    main()
