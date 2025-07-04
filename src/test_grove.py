#!/usr/bin/env python3
"""
Test script for GrowPy multi-tree forest generation.

This script tests both individual tree generation and combined forest generation.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

def test_growpy():
    """Test the GrowPy module."""
    
    print("🌲 Testing GrowPy Multi-Tree Forest Generation")
    print("=" * 50)
    
    # Import the module
    try:
        from growpy import grow_forest_from_csv, grow_combined_forest_from_csv
        print("✅ GrowPy imported successfully")
        print("  - grow_forest_from_csv (individual trees)")
        print("  - grow_combined_forest_from_csv (combined forest)")
    except ImportError as e:
        print(f"❌ Failed to import GrowPy: {e}")
        return False
    
    # Check if demo CSV exists
    csv_file = os.path.join("..", "data", "demo_forest.csv")
    if not os.path.exists(csv_file):
        print(f"❌ Demo CSV file not found: {csv_file}")
        return False
    
    print(f"✅ Found demo CSV: {csv_file}")
    
    # Test 1: Individual Trees
    print("\n" + "="*30)
    print("🌳 TEST 1: Individual Tree Generation")
    print("="*30)
    
    output_dir = os.path.join("..", "data", "output", "individual_trees")
    
    try:
        print("Generating individual tree models...")
        generated_files = grow_forest_from_csv(
            csv_file=csv_file,
            output_dir=output_dir
        )
        
        print(f"✅ Success! Generated {len(generated_files)} individual tree models")
        
        # Show some file info
        if generated_files:
            print("📄 Generated files:")
            for filepath in generated_files[:3]:  # Show first 3
                filename = os.path.basename(filepath)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    size_kb = size / 1024
                    print(f"  - {filename} ({size_kb:.1f} KB)")
            
            if len(generated_files) > 3:
                print(f"  ... and {len(generated_files) - 3} more files")
        
    except Exception as e:
        print(f"❌ Error during individual tree generation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Combined Forest
    print("\n" + "="*30)
    print("🏞️  TEST 2: Combined Forest Generation")
    print("="*30)
    
    output_file = os.path.join("..", "data", "output", "combined_forest.obj")
    
    try:
        print("Generating combined forest model...")
        generated_file = grow_combined_forest_from_csv(
            csv_file=csv_file,
            output_file=output_file
        )
        
        if generated_file and os.path.exists(generated_file):
            size = os.path.getsize(generated_file)
            size_mb = size / (1024 * 1024)
            print(f"✅ Success! Generated combined forest: {os.path.basename(generated_file)} ({size_mb:.1f} MB)")
        else:
            print("❌ Combined forest generation failed")
            return False
        
    except Exception as e:
        print(f"❌ Error during combined forest generation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*50)
    print("🎉 All tests completed successfully!")
    print("\nWhat was generated:")
    print(f"📂 Individual trees: {output_dir}")
    print(f"📄 Combined forest: {output_file}")
    print("\nKey benefits of the multi-tree approach:")
    print("✓ Trees compete for light and space naturally")
    print("✓ No overlap or collision between trees") 
    print("✓ More realistic forest ecosystem simulation")
    print("✓ Can export as individual trees OR combined forest")
    
    return True

if __name__ == "__main__":
    success = test_growpy()
    
    if success:
        print("\n✅ All tests passed! You now have a working Grove-based forest generator!")
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
