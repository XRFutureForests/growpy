"""
Quick test version of the forest generation
"""

from growpy import grow_forest_from_csv
from pathlib import Path

if __name__ == "__main__":
    # Quick test with reduced parameters
    demo_csv = Path("../../data/demo_forest.csv")
    test_output_dir = Path("../../data/output")

    print("Running quick test...")
    print(f"Input CSV: {demo_csv}")
    print(f"Output directory: {test_output_dir}")

    summary_file = grow_forest_from_csv(
        csv_file=demo_csv,
        output_directory=test_output_dir,
        resolution=16,  # Very low resolution for speed
        flushes=10,  # Reduced flushes for quick test
        base_name="test_forest",
        # Build options to avoid artifacts
        build_cutoff_age=0,  # Keep all branches (don't filter by age)
        build_cutoff_thickness=0.0,  # Keep all branches (don't filter by thickness)
        reduce=0.25,  # Standard geometry reduction
        build_end_cap=True,  # Close branch ends
        build_blend=True,  # Smooth transitions
    )

    print("Test completed!")
    print(f"Summary file: {summary_file}")
    
    # Read and display the summary
    if Path(summary_file).exists():
        print("\n" + "="*50)
        print("FOREST GENERATION SUMMARY")
        print("="*50)
        with open(summary_file, 'r') as f:
            summary_content = f.read()
            print(summary_content)
    
    # List all generated OBJ files
    output_dir = Path(summary_file).parent
    obj_files = list(output_dir.glob("*.obj"))
    if obj_files:
        print(f"\nGenerated {len(obj_files)} individual tree files:")
        for obj_file in sorted(obj_files):
            print(f"  - {obj_file.name}")
    else:
        print("\nNo OBJ files found in output directory.")
