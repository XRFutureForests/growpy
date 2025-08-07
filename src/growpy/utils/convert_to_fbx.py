#!/usr/bin/env python3
"""
Wrapper script to run USD to FBX conversion using local conda environment.

This script can be run directly since bpy is available in the conda environment.

Usage:
    python convert_to_fbx.py
"""

import sys
from pathlib import Path

def main():
    """Run the advanced USD to FBX converter."""
    
    print("🚀 Starting USD to FBX conversion using conda environment...")
    print("=" * 50)
    
    # Import and run the advanced converter
    try:
        script_dir = Path(__file__).parent
        advanced_script = script_dir / "05_advanced_usd_to_fbx.py"
        
        # Execute the advanced conversion script
        with open(advanced_script, 'r') as f:
            script_content = f.read()
        
        # Create a clean namespace for execution
        script_globals = {
            '__file__': str(advanced_script),
            '__name__': '__main__'
        }
        
        exec(script_content, script_globals)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure bpy is installed in your conda environment")
        return 1
    
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())