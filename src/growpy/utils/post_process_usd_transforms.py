#!/usr/bin/env python3
"""
Post-process USD files to ensure transforms are at origin (0,0,0).

This utility script fixes USD files to ensure all twig pivot points
are at the origin, which is required for proper Grove integration.

Usage:
    python post_process_usd_transforms.py

This script:
1. Finds all .usda files in the twig assets directory
2. Replaces any xformOp:translate values with (0, 0, 0)
3. Reports which files were modified
"""
import re
from pathlib import Path


def fix_usd_transforms(usd_file_path):
    """
    Fix transform values in a USD file to ensure pivot is at origin.
    
    Args:
        usd_file_path (Path): Path to the USD file to fix
        
    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        # Read the file
        with open(usd_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match: double3 xformOp:translate = (any numbers)
        pattern = r'(double3 xformOp:translate = )\([^)]+\)'
        replacement = r'\1(0, 0, 0)'
        new_content = re.sub(pattern, replacement, content)
        
        # Only write if content changed
        if new_content != content:
            with open(usd_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ❌ Failed to process {usd_file_path.name}: {e}")
        return False


def main():
    """Main function to process all USD files."""
    print("🔧 Post-processing USD files to reset transforms to origin")
    print("=" * 60)

    # Find twig assets directory
    twig_asset_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "assets" / "twigs"
    )
    
    if not twig_asset_path.exists():
        print(f"❌ Twig assets directory not found: {twig_asset_path}")
        return 1

    # Find all USD files
    usd_files = list(twig_asset_path.glob("**/*.usda"))
    print(f"📁 Found {len(usd_files)} USD files to process")
    
    if not usd_files:
        print("No USD files found to process.")
        return 0

    # Process each file
    processed_count = 0
    for usd_file in usd_files:
        if fix_usd_transforms(usd_file):
            processed_count += 1
            print(f"  🔄 Fixed transforms in {usd_file.name}")
    
    print(f"\n✅ Post-processed {processed_count} USD files with transform fixes")
    
    if processed_count == 0:
        print("🎉 All USD files already have correct transforms at (0, 0, 0)")
    else:
        print(f"🎉 Fixed {processed_count} files - all twigs now have pivot at origin")
    
    return 0


if __name__ == "__main__":
    exit(main())
