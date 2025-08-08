#!/usr/bin/env python3
"""
Test script to verify the USD transform post-processing works correctly.
"""
import re
from pathlib import Path

def test_usd_transform_fix():
    twig_asset_path = Path("data/assets/twigs")
    usd_files = list(twig_asset_path.glob("**/*.usda"))
    
    print(f"Found {len(usd_files)} USD files")
    
    # Test the regex pattern
    test_lines = [
        'double3 xformOp:translate = (0.00016898103058338165, 0.00015532481484115124, 0)',
        'double3 xformOp:translate = (1.5, -2.3, 0.7)',
        'double3 xformOp:translate = (0, 0, 0)',
        'float3 xformOp:rotateXYZ = (0, -0, 0)',
    ]
    
    pattern = r'(double3 xformOp:translate = )\([^)]+\)'
    replacement = r'\1(0, 0, 0)'
    
    print("\nTesting regex pattern:")
    for line in test_lines:
        new_line = re.sub(pattern, replacement, line)
        print(f"Original: {line}")
        print(f"Fixed:    {new_line}")
        print()
    
    # Process a few real files
    processed = 0
    for usd_file in usd_files[:3]:
        print(f"\nProcessing: {usd_file.name}")
        try:
            with open(usd_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it needs fixing
            if 'xformOp:translate' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'xformOp:translate' in line:
                        print(f"  Line {i+1}: {line.strip()}")
                        new_line = re.sub(pattern, replacement, line)
                        if new_line != line:
                            print(f"  Fixed:    {new_line.strip()}")
                        else:
                            print(f"  No change needed")
            else:
                print("  No transform found")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    return True

if __name__ == "__main__":
    test_usd_transform_fix()
