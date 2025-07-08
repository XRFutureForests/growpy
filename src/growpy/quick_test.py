"""
Quick test version of the forest generation
"""

from growpy import grow_forest_from_csv
from pathlib import Path

if __name__ == "__main__":
    # Quick test with reduced parameters
    demo_csv = Path("../../data/demo_forest.csv")
    test_output = Path("../../data/output/test_forest.obj")

    print("Running quick test...")

    result = grow_forest_from_csv(
        csv_file=demo_csv,
        output_file=test_output,
        resolution=4,  # Low resolution for speed
    )

    print(f"Test completed! Output: {result}")
