#!/usr/bin/env python3
"""
Demo script showing root generation for different tree species.

This script demonstrates the new root generation functionality in GrowPy,
showcasing how different tree species get appropriate root architecture
types based on botanical characteristics.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from growpy.roots import (
        create_root_system,
        get_species_root_type,
        print_root_architecture_guide,
        RootArchitecture,
        build_root_models,
        save_root_system_to_usd
    )
    import the_grove_22_core as gc
    GROVE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure Grove core is available and GrowPy is properly set up")
    GROVE_AVAILABLE = False


def demo_root_types():
    """Demonstrate root type assignment for different species."""
    print("🌱 Root Type Assignment Demo")
    print("=" * 40)
    
    test_species = [
        ("European Oak", "Classic taproot tree"),
        ("Scots Pine", "Conifer with shallow spreading roots"), 
        ("Silver Birch", "Broadleaf with fibrous roots"),
        ("London Plane Tree", "Large tree with buttress roots"),
        ("Fig", "Tropical tree with buttress roots"),
        ("Banyan", "Tropical tree with aerial roots"),
    ]
    
    for species, description in test_species:
        root_type = get_species_root_type(species)
        print(f"{species:20} -> {root_type:12} ({description})")


def demo_root_generation():
    """Demonstrate actual root system generation."""
    if not GROVE_AVAILABLE:
        print("❌ Grove core not available for root generation demo")
        return
    
    print("\n🌿 Root System Generation Demo")
    print("=" * 40)
    
    test_cases = [
        ("European Oak", RootArchitecture.TAP_ROOT, (0, 0, 0)),
        ("Scots Pine", RootArchitecture.FIBROUS, (5, 0, 0)),
        ("London Plane Tree", RootArchitecture.BUTTRESS, (10, 0, 0)),
    ]
    
    output_dir = Path("output/root_demo")
    
    for species, expected_type, position in test_cases:
        print(f"\n🌳 Creating {species} root system...")
        
        # Get the automatically determined root type
        auto_type = get_species_root_type(species)
        print(f"   Auto-assigned type: {auto_type}")
        
        # Create root system
        root_grove = create_root_system(
            tree_position=position,
            species_name=species,
            root_type=auto_type,
            root_count=5,
            growth_cycles=12
        )
        
        if root_grove:
            print(f"   ✅ Created root system")
            
            # Build models
            root_models = build_root_models(root_grove)
            total_models = sum(len(models) for models in root_models.values())
            print(f"   📦 Built {total_models} models across {len(root_models)} LOD levels")
            
            # Save to USD
            species_output_dir = output_dir / species.replace(" ", "_").replace("-", "_")
            if save_root_system_to_usd(root_models, species_output_dir, species):
                print(f"   💾 Saved USD files to {species_output_dir}")
            else:
                print(f"   ⚠️ Failed to save USD files")
        else:
            print(f"   ❌ Failed to create root system")


def main():
    """Main demo function."""
    print("🚀 GrowPy Root Generation Demo")
    print("=" * 50)
    
    # Show the root architecture guide
    print_root_architecture_guide()
    
    print("\n" + "=" * 60)
    
    # Demo root type assignments
    demo_root_types()
    
    print("\n" + "=" * 60)
    
    # Demo actual root generation
    demo_root_generation()
    
    print(f"\n🎉 Root generation demo complete!")
    print(f"💡 Key Features:")
    print(f"   • Species-specific root architecture assignment")
    print(f"   • Botanically accurate root growth patterns") 
    print(f"   • Multiple LOD levels for performance optimization")
    print(f"   • USD export for integration with 3D pipelines")
    print(f"   • Negative gravitropism simulation for downward growth")


if __name__ == "__main__":
    main()
