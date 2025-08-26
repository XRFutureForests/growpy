#!/usr/bin/env python3
"""
Test script for USD material embedding with proper API usage.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_material_embedding_simple():
    """Test material embedding with direct USD API calls."""
    
    # Import USD here after environment is set up
    try:
        from pxr import Usd, Sdf, UsdShade
    except ImportError:
        print("❌ USD not available")
        return False
    
    print("🔍 Testing simplified material embedding approach")
    
    try:
        # Create new stage for embedding test
        test_stage = Usd.Stage.CreateInMemory()
        
        # Create materials scope
        materials_scope = test_stage.DefinePrim("/materials", "Scope")
        
        # Create a simple material manually
        material_path = "/materials/TestMaterial"
        material = UsdShade.Material.Define(test_stage, material_path)
        
        # Create UsdPreviewSurface shader
        surface_shader_path = f"{material_path}/PreviewSurface"
        surface_shader = UsdShade.Shader.Define(test_stage, surface_shader_path)
        surface_shader.CreateIdAttr("UsdPreviewSurface")
        
        # Create simple diffuse color input
        diffuse_input = surface_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)
        diffuse_input.Set((0.8, 0.6, 0.4))  # Wood brown color
        
        # Connect material to shader
        material.CreateSurfaceOutput().ConnectToSource(surface_shader.ConnectableAPI(), "surface")
        
        # Verify material was created
        material_prim = test_stage.GetPrimAtPath(material_path)
        if material_prim:
            print(f"✅ Material created at: {material_path}")
            
            # Check surface output connection
            material_obj = UsdShade.Material(material_prim)
            surface_output = material_obj.GetSurfaceOutput()
            if surface_output:
                print(f"✅ Surface output exists")
                connections = surface_output.GetConnectedSources()
                if connections:
                    print(f"✅ Surface output connected to: {connections[0][0].GetPath()}")
                else:
                    print("⚠️  Surface output not connected")
            
            # Save to file for inspection
            output_file = Path("test_simple_material.usda")
            test_stage.Export(str(output_file))
            print(f"📄 Saved test stage to: {output_file}")
            
            return True
        else:
            print("❌ Material prim not found")
            return False
            
    except Exception as e:
        print(f"❌ Error in material embedding: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_material_embedding_simple()
    sys.exit(0 if success else 1)