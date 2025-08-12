#!/usr/bin/env python3
"""
Root system generation for GrowPy using Grove API features.

This module creates believable root systems by leveraging Grove's existing
growth simulation capabilities with modified parameters for downward growth:

1. Negative gravitropism (turn_up < 0) for downward growth direction
2. Reduced branching angles and more horizontal spreading
3. Tapering root thickness with distance from trunk
4. Species-specific root architecture patterns
5. Integration with existing tree models for complete tree systems

Root Types Supported:
- Tap roots: Deep, central roots (carrots, oaks)
- Fibrous roots: Shallow, spreading networks (grasses, maples)
- Buttress roots: Large surface roots for stability (tropical trees)
- Adventitious roots: Aerial roots that grow downward (banyan trees)

Key Grove Parameters Used:
- turn_up: Set to negative values for downward growth
- add_angle: Controls root branching angles
- grow_length: Root segment length
- thicken_base_buttress: Surface root prominence
- root_distribution: Root thickness distribution
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math

try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    GROVE_CORE_AVAILABLE = False


class RootArchitecture:
    """Defines root system architecture patterns for different species."""
    
    # Root system types
    TAP_ROOT = "tap_root"           # Deep central root (oak, carrot)
    FIBROUS = "fibrous"             # Shallow spreading (maple, grass)
    BUTTRESS = "buttress"           # Large surface roots (tropical)
    ADVENTITIOUS = "adventitious"   # Aerial to ground (banyan)
    
    def __init__(self, root_type: str = FIBROUS):
        self.root_type = root_type
        self.parameters = self._get_default_parameters()
    
    def _get_default_parameters(self) -> Dict:
        """Get default root parameters based on root type."""
        base_params = {
            # Core growth parameters
            "grow_nodes": 3,
            "grow_length": 0.3,
            "grow_length_reduce": 0.85,
            
            # Downward growth (negative gravitropism)
            "turn_up": -0.4,  # Negative for downward growth
            "turn_up_in_shade": -0.3,
            "turn_to_light": 0.0,  # Roots don't seek light
            "turn_to_horizon": 0.2,  # Some horizontal spreading
            "turn_random": 0.15,
            
            # Branching parameters
            "add_side_branches": 2,
            "add_chance": 0.6,
            "add_angle": 45.0,  # Root branching angle
            "add_up": -0.3,  # Downward bias for new branches
            "add_fork": 0.1,
            "add_horizontal": 0.4,
            "add_planar": 0.0,
            "add_twist": 0.05,
            
            # Thickness and structure
            "thicken_tips": 0.003,  # Thin root tips
            "thicken_tips_reduce": 0.1,
            "thicken_join": 0.8,
            "thicken_base_scale": 1.0,
            "thicken_base_buttress": 1.5,  # Moderate buttressing
            "root_distribution": 0.6,
            
            # Favor parameters
            "favor_bright": 0.0,  # Roots don't seek light
            "favor_end": 0.3,
            "favor_end_reduce": 0.05,
            "favor_rising": -0.4,  # Favor downward growth
            "favor_dwindle": 0.8,
            
            # Environmental responses
            "shade_area": 0.0,  # Roots don't cast shade
            "bend_mass": 0.5,  # Less bending than branches
            "bend_reaction": 0.3,
        }
        
        # Modify parameters based on root type
        if self.root_type == self.TAP_ROOT:
            # Deep central roots - typical of oaks, walnuts, ashes
            base_params.update({
                "turn_up": -0.7,  # Strong downward growth for taproot
                "turn_to_horizon": 0.05,  # Minimal horizontal spreading initially
                "add_side_branches": 1,  # Fewer lateral roots, focus on main taproot
                "add_chance": 0.3,  # Lower branching probability
                "grow_length": 0.5,  # Longer segments for deep penetration
                "grow_nodes": 4,  # More nodes per segment for depth
                "thicken_base_buttress": 0.3,  # Minimal surface buttressing
                "thicken_base_scale": 0.9,  # Less trunk flare
                "add_angle": 30.0,  # Narrow lateral branching angles
                "favor_rising": -0.6,  # Strong preference for downward growth
            })
            
        elif self.root_type == self.FIBROUS:
            # Shallow spreading networks - typical of conifers, maples, birches
            base_params.update({
                "turn_up": -0.2,  # Shallow downward growth
                "turn_to_horizon": 0.6,  # Strong horizontal spreading
                "add_side_branches": 4,  # Many lateral roots for wide coverage
                "add_chance": 0.9,  # High branching probability
                "grow_length": 0.2,  # Shorter segments for fine branching
                "grow_nodes": 2,  # Fewer nodes, more branching points
                "add_angle": 70.0,  # Wide branching angles for spread
                "thicken_base_buttress": 1.0,  # Minimal buttressing
                "favor_rising": -0.2,  # Slight downward preference
                "turn_random": 0.25,  # More random exploration
            })
            
        elif self.root_type == self.BUTTRESS:
            # Large surface roots - typical of tropical trees, old growth
            base_params.update({
                "turn_up": -0.1,  # Very shallow, mostly surface
                "turn_to_horizon": 0.8,  # Dominant horizontal spreading
                "add_side_branches": 2,  # Moderate branching
                "add_chance": 0.4,  # Selective branching
                "thicken_base_buttress": 5.0,  # Prominent surface buttressing
                "thicken_base_scale": 2.0,  # Large trunk flare
                "root_distribution": 0.9,  # Wide distribution of root effect
                "grow_length": 0.7,  # Large surface root segments
                "grow_nodes": 3,  # Medium node count
                "add_angle": 45.0,  # Moderate branching angles
                "thicken_tips": 0.008,  # Thicker root tips for large roots
                "favor_rising": -0.1,  # Minimal downward preference
            })
            
        elif self.root_type == self.ADVENTITIOUS:
            # Aerial roots growing downward - typical of tropical species
            base_params.update({
                "turn_up": -0.8,  # Very strong downward growth (aerial to ground)
                "turn_to_horizon": 0.1,  # Minimal horizontal initially
                "add_side_branches": 1,  # Few branches until reaching ground
                "add_chance": 0.2,  # Low branching until established
                "grow_length": 0.8,  # Long aerial segments
                "grow_nodes": 5,  # Many nodes for long aerial growth
                "thicken_tips": 0.002,  # Very thin aerial root tips
                "add_angle": 15.0,  # Very narrow branching
                "favor_rising": -0.8,  # Strong downward bias
                "turn_random": 0.05,  # Minimal randomness for directed growth
                "thicken_base_buttress": 2.0,  # Moderate buttressing at base
            })
        
        return base_params


def create_root_system(
    tree_position: Tuple[float, float, float],
    species_name: str = "Generic",
    root_type: str = RootArchitecture.FIBROUS,
    root_count: int = 6,
    max_depth: float = 3.0,
    spread_radius: float = 4.0,
    growth_cycles: int = 15
) -> Optional[object]:
    """
    Create a root system using Grove's growth simulation.
    
    Args:
        tree_position: (x, y, z) position of the tree trunk base
        species_name: Name of the tree species for root characteristics
        root_type: Type of root architecture (tap_root, fibrous, buttress, adventitious)
        root_count: Number of primary roots to generate
        max_depth: Maximum depth of root penetration
        spread_radius: Maximum horizontal spread of roots
        growth_cycles: Number of growth cycles to simulate
        
    Returns:
        Grove object containing the root system, or None if Grove unavailable
    """
    if not GROVE_CORE_AVAILABLE:
        print("⚠️ Grove core not available for root generation")
        return None
    
    print(f"🌱 Creating {root_type} root system for {species_name}")
    
    # Create root architecture
    root_arch = RootArchitecture(root_type)
    
    # Create grove for root system
    root_grove = gc.Grove()
    
    # Set up root-specific growth properties
    props = root_grove.get_properties()
    
    # Apply root architecture parameters
    for param_name, param_value in root_arch.parameters.items():
        if hasattr(props, param_name):
            setattr(props, param_name, param_value)
    
    root_grove.set_properties(props)
    
    # Calculate root starting positions around the tree base
    x, y, z = tree_position
    
    for i in range(root_count):
        # Distribute roots in a circle around the tree base
        angle = (2 * math.pi * i) / root_count
        
        # Add some randomness to root positioning
        angle_variation = (math.pi / 6) * (0.5 - gc.Randomizer().factor())
        angle += angle_variation
        
        # Calculate root starting position
        base_offset = 0.2 + 0.3 * gc.Randomizer().factor()  # 0.2-0.5m from trunk
        root_x = x + base_offset * math.cos(angle)
        root_y = y + base_offset * math.sin(angle)
        root_z = z  # Start at ground level
        
        # Calculate initial root direction
        # Slight outward bias with downward component
        direction_x = math.cos(angle) * 0.3  # Outward component
        direction_y = math.sin(angle) * 0.3
        direction_z = -0.7  # Downward component
        
        # Add root to grove
        root_position = gc.Vector(root_x, root_y, root_z)
        root_direction = gc.Vector(direction_x, direction_y, direction_z)
        
        # Delay some roots for more natural variation
        delay = int(gc.Randomizer().factor() * 3)
        
        root_grove.add_new_tree(root_position, root_direction, delay)
    
    # Simulate root growth
    print(f"  🔄 Simulating {growth_cycles} growth cycles...")
    root_grove.simulate(growth_cycles)
    
    print(f"  ✅ Generated root system with {root_count} primary roots")
    return root_grove


def get_species_root_examples() -> Dict[str, List[str]]:
    """
    Get examples of species for each root architecture type.
    
    Returns:
        Dictionary with root types as keys and example species lists as values
    """
    return {
        RootArchitecture.TAP_ROOT: [
            "European Oak", "Red Oak", "White Oak",
            "Walnut", "Hickory", "Pecan",
            "European Beech", "Sweet Chestnut",
            "Common Ash", "Narrow-leaved Ash",
            "Linden", "Elm", "Magnolia",
            "Ginkgo", "Honey Locust",
            "Black Tupelo"
        ],
        RootArchitecture.FIBROUS: [
            "Scots Pine", "Austrian Pine", "Monterey Pine",
            "Silver Fir", "Grand Fir", "Douglas Fir",
            "Norway Spruce", "Western Hemlock",
            "Silver Birch", "Downy Birch", "Paper Birch",
            "Alder", "Hazel", "Hornbeam",
            "Field Maple", "Japanese Maple",
            "Weeping Willow", "Aspen", "Grey Poplar",
            "Wild Cherry", "Wild Apple", "Hawthorn"
        ],
        RootArchitecture.BUTTRESS: [
            "London Plane Tree", "Horse Chestnut",
            "Blue Gum", "Manna Gum",
            "Fig", "Ficus", "Kapok",
            "Sweet Chestnut (old growth)"
        ],
        RootArchitecture.ADVENTITIOUS: [
            "Banyan", "Strangler Fig",
            "Mangrove", "Weeping Fig",
            "Rubber Tree"
        ]
    }


def print_root_architecture_guide():
    """Print a comprehensive guide to root architecture assignments."""
    print("🌱 Root Architecture Guide for Tree Species")
    print("=" * 60)
    
    examples = get_species_root_examples()
    
    print(f"\n🔹 {RootArchitecture.TAP_ROOT.upper()} ROOTS")
    print("   Deep central roots that penetrate vertically")
    print("   Characteristics: Strong main root, fewer laterals, good drought tolerance")
    print("   Typical of: Large broadleaf trees, especially oaks and walnuts")
    for species in examples[RootArchitecture.TAP_ROOT][:8]:  # Show first 8
        print(f"   • {species}")
    if len(examples[RootArchitecture.TAP_ROOT]) > 8:
        print(f"   • ... and {len(examples[RootArchitecture.TAP_ROOT]) - 8} more")
    
    print(f"\n🔹 {RootArchitecture.FIBROUS.upper()} ROOTS")
    print("   Shallow spreading networks that maximize surface area")
    print("   Characteristics: Many lateral roots, efficient nutrient uptake")
    print("   Typical of: Most conifers, maples, birches, and smaller trees")
    for species in examples[RootArchitecture.FIBROUS][:8]:
        print(f"   • {species}")
    if len(examples[RootArchitecture.FIBROUS]) > 8:
        print(f"   • ... and {len(examples[RootArchitecture.FIBROUS]) - 8} more")
    
    print(f"\n🔹 {RootArchitecture.BUTTRESS.upper()} ROOTS")
    print("   Large surface roots providing structural stability")
    print("   Characteristics: Prominent trunk flare, wide spreading surface roots")
    print("   Typical of: Large tropical trees and old-growth specimens")
    for species in examples[RootArchitecture.BUTTRESS]:
        print(f"   • {species}")
    
    print(f"\n🔹 {RootArchitecture.ADVENTITIOUS.upper()} ROOTS")
    print("   Aerial roots that grow downward from branches")
    print("   Characteristics: Start above ground, seek soil, form support pillars")
    print("   Typical of: Tropical species in humid environments")
    for species in examples[RootArchitecture.ADVENTITIOUS]:
        print(f"   • {species}")
    
    print(f"\n📚 Botanical Background:")
    print(f"   • Conifers typically have shallow, spreading roots due to acidic soil adaptation")
    print(f"   • Large broadleaf trees often develop taproots for stability and deep water access")
    print(f"   • Tropical species may develop buttress or aerial roots for structural support")
    print(f"   • Root architecture adapts to soil type, climate, and evolutionary history")


def get_species_root_type(species_name: str) -> str:
    """
    Determine appropriate root type based on species name and botanical characteristics.
    
    Root architecture patterns by plant family/ecology:
    - TAP_ROOT: Deep central roots (many broadleaf trees, especially oaks, walnuts)
    - FIBROUS: Shallow spreading networks (most conifers, maples, birches)
    - BUTTRESS: Large surface roots for stability (tropical trees, old growth)
    - ADVENTITIOUS: Aerial roots that grow downward (tropical species)
    
    Args:
        species_name: Name of the tree species
        
    Returns:
        Root architecture type string
    """
    species_lower = species_name.lower()
    
    # TAP ROOT SPECIES - Deep central roots
    # Classic tap root trees (broadleaf species that develop strong taproots)
    tap_root_species = [
        # Oak family (Fagaceae) - classic taproot
        'oak', 'european oak', 'red oak', 'white oak', 'live oak',
        # Walnut family (Juglandaceae) - strong taproots
        'walnut', 'hickory', 'pecan', 'wingnut',
        # Other broadleaf with prominent taproots
        'sweet chestnut', 'chestnut', 'beech', 'european beech',
        'ash', 'common ash', 'narrow-leaved ash', 'one-leaved ash',
        'linden', 'small-leaved linden', 'lime', 'basswood',
        'elm', 'hackberry',
        'magnolia', 'tulip tree',
        'ginkgo', 'ginkgo biloba',
        'avocado',
        'honey locust', 'locust', 'robinia',
        'black tupelo', 'tupelo',
    ]
    
    if any(tree in species_lower for tree in tap_root_species):
        return RootArchitecture.TAP_ROOT
    
    # BUTTRESS ROOT SPECIES - Large surface roots for stability
    # Tropical trees and large old-growth species
    buttress_species = [
        'fig', 'ficus', 'strangler fig',
        'kapok', 'cecropia', 'mahogany',
        'blue gum', 'eucalyptus', 'manna gum',  # Large eucalyptus
        'london plane', 'plane tree', 'sycamore',  # Large urban trees
        'horse chestnut',  # Large spreading tree
        'sweet chestnut',  # Can also have buttress in old specimens
    ]
    
    if any(tree in species_lower for tree in buttress_species):
        return RootArchitecture.BUTTRESS
    
    # ADVENTITIOUS ROOT SPECIES - Aerial roots
    # Tropical species with aerial root systems
    adventitious_species = [
        'banyan', 'ficus benghalensis',
        'mangrove', 'rhizophora',
        'strangler fig',
        'weeping fig',
        'rubber tree', 'ficus elastica',
    ]
    
    if any(tree in species_lower for tree in adventitious_species):
        return RootArchitecture.ADVENTITIOUS
    
    # FIBROUS ROOT SPECIES - Shallow spreading networks
    # Most conifers and many temperate broadleaf species
    fibrous_species = [
        # Conifers (Pinaceae, Cupressaceae, etc.) - typically shallow, spreading
        'pine', 'scots pine', 'austrian pine', 'monterey pine', 'ponderosa pine',
        'longleaf pine', 'lodgepole pine', 'stone pine',
        'fir', 'silver fir', 'grand fir', 'douglas fir',
        'spruce', 'norway spruce',
        'hemlock', 'western hemlock',
        'cedar', 'western redcedar',
        'cypress', 'swamp cypress',
        'yew', 'taxus',
        # Birch family (shallow roots)
        'birch', 'silver birch', 'downy birch', 'paper birch',
        'alder', 'hazel', 'hornbeam',
        # Maple family (typically shallow, spreading)
        'maple', 'field maple', 'japanese maple', 'norway maple',
        # Willow family (shallow, water-seeking)
        'willow', 'weeping willow', 'pussy willow',
        'poplar', 'aspen', 'grey poplar', 'italian poplar',
        # Fruit trees (typically shallow, spreading)
        'apple', 'wild apple', 'crabapple',
        'cherry', 'wild cherry', 'japanese cherry',
        'hawthorn',
        # Small/medium trees with shallow roots
        'rowan', 'mountain ash',
    ]
    
    if any(tree in species_lower for tree in fibrous_species):
        return RootArchitecture.FIBROUS
    
    # DEFAULT ASSIGNMENT BASED ON BOTANICAL PATTERNS
    # If no specific match, use botanical family patterns
    
    # Check for conifer indicators (most conifers = fibrous)
    conifer_indicators = ['pine', 'fir', 'spruce', 'cedar', 'cypress', 'hemlock', 'yew', 'juniper']
    if any(indicator in species_lower for indicator in conifer_indicators):
        return RootArchitecture.FIBROUS
    
    # Check for large broadleaf indicators (many = tap root)
    large_broadleaf_indicators = ['oak', 'ash', 'elm', 'beech', 'chestnut', 'walnut']
    if any(indicator in species_lower for indicator in large_broadleaf_indicators):
        return RootArchitecture.TAP_ROOT
    
    # Check for tropical indicators (many = buttress)
    tropical_indicators = ['tropical', 'palm', 'bamboo', 'eucalyptus']
    if any(indicator in species_lower for indicator in tropical_indicators):
        return RootArchitecture.BUTTRESS
    
    # Final fallback: fibrous (most common and safest default)
    return RootArchitecture.FIBROUS


def build_root_models(
    root_grove: object,
    lod_configs: Optional[Dict] = None
) -> Dict[str, List]:
    """
    Build 3D models of root systems with appropriate LOD levels.
    
    Args:
        root_grove: Grove object containing root system
        lod_configs: LOD configuration dictionary
        
    Returns:
        Dictionary of LOD models
    """
    if not GROVE_CORE_AVAILABLE or not root_grove:
        return {}
    
    # Default LOD configs for roots (simpler than tree branches)
    if lod_configs is None:
        lod_configs = {
            "root_high": {
                "resolution": 12,
                "resolution_reduce": 0.8,
                "build_cutoff_thickness": 0.002,  # Very thin roots
                "build_cutoff_age": 0,
                "build_blend": True,
                "build_end_cap": True,
                "texture_repeat": 1.0,
            },
            "root_medium": {
                "resolution": 8,
                "resolution_reduce": 0.7,
                "build_cutoff_thickness": 0.005,
                "build_cutoff_age": 1,
                "build_blend": True,
                "build_end_cap": True,
                "texture_repeat": 1.0,
            },
            "root_low": {
                "resolution": 6,
                "resolution_reduce": 0.6,
                "build_cutoff_thickness": 0.01,
                "build_cutoff_age": 2,
                "build_blend": False,
                "build_end_cap": False,
                "texture_repeat": 1.0,
            },
        }
    
    root_models = {}
    
    for lod_name, config in lod_configs.items():
        print(f"  🔨 Building {lod_name} root models...")
        
        try:
            models = root_grove.build_models(config)
            
            # Configure models for underground rendering
            for model in models:
                model.set_up_axis("Z")
                model.set_winding_order("COUNTER_CLOCKWISE")
                
                # Apply appropriate UV mapping for root textures
                if hasattr(model, 'apply_uv_aspect_ratio'):
                    model.apply_uv_aspect_ratio(0.8)  # Compressed UV for roots
            
            root_models[lod_name] = models
            print(f"    ✅ Built {len(models)} root models")
            
        except Exception as e:
            print(f"    ❌ Error building {lod_name}: {e}")
    
    return root_models


def save_root_system_to_usd(
    root_models: Dict[str, List],
    output_path: Path,
    species_name: str = "Generic"
) -> bool:
    """
    Save root system models to USD format.
    
    Args:
        root_models: Dictionary of LOD models
        output_path: Output directory path
        species_name: Tree species name for filename
        
    Returns:
        True if successful, False otherwise
    """
    if not GROVE_CORE_AVAILABLE or not root_models:
        return False
    
    output_path.mkdir(parents=True, exist_ok=True)
    species_clean = species_name.replace(" ", "").replace("-", "_")
    
    try:
        for lod_name, models in root_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                filepath = output_path / filename
                
                # Export to USD
                usd_string = gc.io.model_to_usda_string(model)
                with open(filepath, "w") as f:
                    f.write(usd_string)
                
                print(f"    📁 Saved: {filename}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving root system: {e}")
        return False


def create_combined_tree_with_roots(
    tree_grove: object,
    tree_position: Tuple[float, float, float],
    species_name: str,
    root_cycles: Optional[int] = None
) -> Tuple[object, object]:
    """
    Create a complete tree system with both above-ground tree and root system.
    
    Args:
        tree_grove: Existing Grove object for the tree
        tree_position: Position of the tree base
        species_name: Tree species name
        root_cycles: Growth cycles for roots (defaults to tree simulation length)
        
    Returns:
        Tuple of (tree_grove, root_grove)
    """
    if not GROVE_CORE_AVAILABLE:
        return tree_grove, None
    
    # Determine root type from species
    root_type = get_species_root_type(species_name)
    
    # Estimate appropriate root parameters based on tree size
    # This is a simplified estimation - in reality this would be more complex
    root_count = 4 + int(gc.Randomizer().factor() * 4)  # 4-8 primary roots
    
    # Default root cycles to match tree growth if not specified
    if root_cycles is None:
        root_cycles = 12  # Default root growth cycles
    
    # Create root system
    root_grove = create_root_system(
        tree_position=tree_position,
        species_name=species_name,
        root_type=root_type,
        root_count=root_count,
        growth_cycles=root_cycles
    )
    
    print(f"  🌳 Created complete tree system: {species_name}")
    print(f"    - Root type: {root_type}")
    print(f"    - Primary roots: {root_count}")
    print(f"    - Root growth cycles: {root_cycles}")
    
    return tree_grove, root_grove


# Convenience functions for integration with existing GrowPy workflow

def add_roots_to_forest(
    forest: List[Tuple],
    root_growth_cycles: int = 12
) -> List[Tuple]:
    """
    Add root systems to an existing forest.
    
    Args:
        forest: List of (grove, species_name, tree_count, attributes) tuples
        root_growth_cycles: Number of growth cycles for root systems
        
    Returns:
        Extended forest list with root groves added
    """
    if not GROVE_CORE_AVAILABLE:
        print("⚠️ Grove core not available for root generation")
        return forest
    
    extended_forest = []
    
    for grove, species_name, tree_count, attributes in forest:
        # Add original tree grove
        extended_forest.append((grove, species_name, tree_count, attributes))
        
        # Create root systems for this species
        print(f"🌱 Adding root systems for {species_name}")
        
        # Get tree positions from grove (simplified - would need proper extraction)
        # For now, create root systems at origin with species-appropriate parameters
        root_type = get_species_root_type(species_name)
        
        # Create one root grove per tree (simplified approach)
        for tree_idx in range(min(tree_count, 3)):  # Limit for performance
            tree_position = (tree_idx * 2.0, 0.0, 0.0)  # Simplified positioning
            
            root_grove = create_root_system(
                tree_position=tree_position,
                species_name=species_name,
                root_type=root_type,
                growth_cycles=root_growth_cycles
            )
            
            if root_grove:
                root_species_name = f"{species_name} (Roots)"
                root_attributes = attributes.copy() if attributes else {}
                root_attributes['is_root_system'] = True
                root_attributes['parent_species'] = species_name
                
                extended_forest.append((root_grove, root_species_name, 1, root_attributes))
    
    return extended_forest


if __name__ == "__main__":
    """Test root generation functionality."""
    print("🧪 Testing Root Generation System")
    print("=" * 40)
    
    if not GROVE_CORE_AVAILABLE:
        print("❌ Grove core not available - cannot test root generation")
        sys.exit(1)
    
    # Test different root types
    test_species = [
        ("Oak", RootArchitecture.TAP_ROOT),
        ("Maple", RootArchitecture.FIBROUS),
        ("Fig", RootArchitecture.BUTTRESS),
        ("Banyan", RootArchitecture.ADVENTITIOUS),
    ]
    
    for species, root_type in test_species:
        print(f"\n🌱 Testing {species} with {root_type} roots")
        
        root_grove = create_root_system(
            tree_position=(0.0, 0.0, 0.0),
            species_name=species,
            root_type=root_type,
            root_count=5,
            growth_cycles=10
        )
        
        if root_grove:
            print(f"  ✅ Successfully created {species} root system")
            
            # Test model building
            root_models = build_root_models(root_grove)
            print(f"  📦 Built {sum(len(models) for models in root_models.values())} root models")
        else:
            print(f"  ❌ Failed to create {species} root system")
    
    print("\n🎉 Root generation testing complete!")
