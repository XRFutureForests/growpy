#!/usr/bin/env python3
"""
Post-process all USD files to reset transform values to 0,0,0.
This fixes any twig USD files that have non-zero translate values.
"""
import re
from pathlib import Path

def fix_usd_transforms():
    """Fix transform values in all USD files."""
    print("🔧 Post-processing USD files to reset transforms to 0,0,0...")
    
    twig_asset_path = Path("data/assets/twigs")
    usd_files = list(twig_asset_path.glob("**/*.usda"))
    processed_count = 0
    
    print(f"📁 Found {len(usd_files)} USD files to process")
    
    for usd_file in usd_files:
        try:
            # Read the file
            with open(usd_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace translate values with 0,0,0
            pattern = r'(double3 xformOp:translate = )\([^)]+\)'
            replacement = r'\1(0, 0, 0)'
            new_content = re.sub(pattern, replacement, content)
            
            # Only write if content changed
            if new_content != content:
                with open(usd_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                processed_count += 1
                print(f"  🔄 Fixed transforms in {usd_file.name}")
            
        except Exception as e:
            print(f"  ❌ Failed to process {usd_file.name}: {e}")
    
    print(f"\n✅ Post-processed {processed_count} USD files with transform fixes")
    print(f"🎉 All twig pivots are now at origin (0,0,0)")
    return processed_count

if __name__ == "__main__":
    fix_usd_transforms()
