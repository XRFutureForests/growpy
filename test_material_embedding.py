#!/usr/bin/env python3
"""
Test script for material embedding into USD stages.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.twig import extract_materials_from_usd, embed_materials_in_stage

def test_material_embedding():
    """Test extracting and embedding materials into a new USD stage."""
    
    # Import USD here after environment is set up
    try:
        from pxr import Usd
    except ImportError:
        print("❌ USD not available")
        return False
    
    # Path to sample twig file
    twig_file = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig_MannaGumTwig.usda")
    
    if not twig_file.exists():
        print(f"❌ Twig file not found: {twig_file}")
        return False
    
    print(f"🔍 Testing material embedding from: {twig_file}")
    
    try:
        # Extract materials
        materials = extract_materials_from_usd(twig_file)
        
        if not materials:
            print("❌ No materials found to embed")
            return False
            
        print(f"✅ Extracted {len(materials)} materials")
        
        # Create new stage for embedding test
        test_stage = Usd.Stage.CreateInMemory()
        
        # Embed materials
        embed_materials_in_stage(test_stage, materials)
        
        # Verify materials were embedded
        embedded_materials = []
        for prim in test_stage.Traverse():
            if prim.GetTypeName() == "Material":
                embedded_materials.append(prim.GetName())
                
        if embedded_materials:
            print(f"✅ Successfully embedded materials: {embedded_materials}")
            
            # Save to file for inspection
            output_file = Path("test_embedded_materials.usda")
            test_stage.Export(str(output_file))
            print(f"📄 Saved test stage to: {output_file}")
            
            return True
        else:
            print("❌ No materials found in embedded stage")
            return False
            
    except Exception as e:
        print(f"❌ Error in material embedding: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_material_embedding()
    sys.exit(0 if success else 1)