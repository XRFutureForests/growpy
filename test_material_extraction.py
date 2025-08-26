#!/usr/bin/env python3
"""
Test script for material extraction from USD twig files.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.twig import extract_materials_from_usd

def test_material_extraction():
    """Test extracting materials from a sample twig file."""
    
    # Path to sample twig file
    twig_file = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig_MannaGumTwig.usda")
    
    if not twig_file.exists():
        print(f"❌ Twig file not found: {twig_file}")
        return False
    
    print(f"🔍 Testing material extraction from: {twig_file}")
    
    try:
        materials = extract_materials_from_usd(twig_file)
        
        if materials:
            print(f"✅ Found {len(materials)} materials:")
            for material_name, material_data in materials.items():
                print(f"   • {material_name}")
                if 'texture' in material_data['shaders']:
                    texture_file = material_data['shaders']['texture'].get('file')
                    print(f"     - Texture: {texture_file}")
                
            return True
        else:
            print("❌ No materials found")
            return False
            
    except Exception as e:
        print(f"❌ Error extracting materials: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_material_extraction()
    sys.exit(0 if success else 1)