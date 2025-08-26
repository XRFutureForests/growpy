#!/usr/bin/env python3
"""
Test the complete material extraction and PointInstancer implementation.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_complete_implementation():
    """Test the complete material extraction and embedding workflow."""
    
    # Import required modules
    try:
        from pxr import Usd, UsdGeom, Gf
        from growpy.twig import (
            extract_materials_from_usd, 
            embed_materials_in_stage,
            write_usd_pointinstancer_to_stage_with_materials
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    print("🔍 Testing complete material extraction and PointInstancer workflow")
    
    # Path to sample twig file
    twig_file = Path("data/assets/twigs/MannaGumTwig/MannaGumTwig_MannaGumTwig.usda")
    
    if not twig_file.exists():
        print(f"❌ Twig file not found: {twig_file}")
        return False
    
    try:
        # Step 1: Create a test tree stage
        test_stage = Usd.Stage.CreateInMemory()
        
        # Create a simple tree structure
        tree_prim = UsdGeom.Xform.Define(test_stage, "/Tree")
        
        # Step 2: Test material extraction
        print(f"📤 Extracting materials from {twig_file.name}")
        materials = extract_materials_from_usd(twig_file)
        
        if not materials:
            print("❌ No materials extracted")
            return False
            
        print(f"✅ Extracted {len(materials)} materials: {list(materials.keys())}")
        
        # Step 3: Test material embedding  
        print("📥 Embedding materials in tree stage")
        embed_materials_in_stage(test_stage, materials, "/Tree/TwigMaterials")
        
        # Verify materials were embedded
        embedded_materials = []
        for prim in test_stage.Traverse():
            if prim.GetTypeName() == "Material":
                embedded_materials.append(prim.GetName())
                
        if not embedded_materials:
            print("❌ No materials found in embedded stage")
            return False
            
        print(f"✅ Embedded materials: {embedded_materials}")
        
        # Step 4: Test PointInstancer with materials
        print("🔧 Testing PointInstancer with embedded materials")
        
        # Create sample twig positions and orientations
        positions = [
            (1.0, 2.0, 3.0),
            (4.0, 5.0, 6.0),
            (7.0, 8.0, 9.0)
        ]
        
        orientations = [
            (1.0, 0.0, 0.0, 0.0),  # Identity quaternion
            (1.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0)
        ]
        
        # This will test the complete workflow
        success = write_usd_pointinstancer_to_stage_with_materials(
            test_stage,
            positions, 
            orientations,
            twig_file,
            "MannaGumTwig",  # twig_xform_name
            "MannaGum"       # twig_type
        )
        
        if success:
            print("✅ PointInstancer with materials created successfully")
            
            # Save complete test stage
            output_file = Path("test_complete_implementation.usda")
            test_stage.Export(str(output_file))
            print(f"📄 Saved complete test to: {output_file}")
            
            return True
        else:
            print("❌ PointInstancer creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in complete implementation test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_implementation()
    sys.exit(0 if success else 1)