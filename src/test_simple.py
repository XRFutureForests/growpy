#!/usr/bin/env python3
"""
Simple test script for GrowPy forest generation.

This script tests the basic functionality of generating trees from CSV data.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

def test_growpy():
    """Test the GrowPy module."""
    
    print("🌲 Testing GrowPy")
    print("=" * 20)
    
    # Import the module
    try:
        from growpy import grow_forest_from_csv
        print("✅ GrowPy imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import GrowPy: {e}")
        return False
    
    # Check if demo CSV exists
    csv_file = os.path.join("..", "data", "demo_forest.csv")
    if not os.path.exists(csv_file):
        print(f"❌ Demo CSV file not found: {csv_file}")
        return False
    
    print(f"✅ Found demo CSV: {csv_file}")
    
    # Set up output directory
    output_dir = os.path.join("..", "data", "output", "test")
    
    print(f"📁 Output directory: {output_dir}")
    print()
    
    # Generate forest
    try:
        print("🌳 Generating forest from CSV...")
        generated_files = grow_forest_from_csv(
            csv_file=csv_file,
            output_dir=output_dir
        )
        
        print()
        print(f"✅ Success! Generated {len(generated_files)} tree models")
        
        # Show some file info
        if generated_files:
            print("📄 Generated files:")
            for filepath in generated_files[:5]:  # Show first 5
                filename = os.path.basename(filepath)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    size_mb = size / (1024 * 1024)
                    print(f"  - {filename} ({size_mb:.1f} MB)")
            
            if len(generated_files) > 5:
                print(f"  ... and {len(generated_files) - 5} more files")
        
        print()
        print("🎉 Test completed successfully!")
        print(f"📂 Check the output in: {output_dir}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_growpy()
    
    if success:
        print("\\n✅ All tests passed!")
    else:
        print("\\n❌ Tests failed!")
        sys.exit(1)
