#!/usr/bin/env python3
"""
Test different random seeds for Downy birch to see if some keep growing.
"""

import sys
from pathlib import Path

# Add src to path for Grove imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

import the_grove_22_core as gc
from growpy import apply_species_preset
from tqdm import tqdm

def test_birch_with_seed(seed_value, cycles=75):
    """Test Downy birch growth with a specific random seed."""
    grove = gc.Grove()
    grove.set_random_seed(seed_value)
    
    # Apply Downy birch preset
    try:
        apply_species_preset(grove, "Betulaceae - Downy birch")
    except:
        # Fallback to manual preset loading
        presets_dir = src_path / "the_grove_22" / "presets"
        preset_path = presets_dir / "Betulaceae - Downy birch.seed.json"
        with open(preset_path, "r") as f:
            preset_json = f.read()
        properties = gc.io.properties_from_json_string(preset_json)
        grove.set_properties(properties)
    
    # Clear and add tree
    grove.clear_trees()
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    
    heights = []
    max_height = 0.0
    
    for cycle in range(cycles):
        grove.simulate(1)
        
        if grove.trees and len(grove.trees) > 0:
            tree = grove.trees[0]
            if hasattr(tree, "nodes") and len(tree.nodes) > 0:
                current_height = 0.0
                
                # Find max height in tree
                def find_max_height_in_branch(branch):
                    local_max = 0.0
                    if hasattr(branch, "nodes"):
                        for node in branch.nodes:
                            if node.pos.z > local_max:
                                local_max = node.pos.z
                            if hasattr(node, "side_branches") and node.side_branches:
                                for side_branch in node.side_branches:
                                    side_max = find_max_height_in_branch(side_branch)
                                    if side_max > local_max:
                                        local_max = side_max
                    return local_max
                
                current_height = find_max_height_in_branch(tree)
                if current_height > max_height:
                    max_height = current_height
                    
                heights.append(current_height)
            else:
                heights.append(0.0)
        else:
            heights.append(0.0)
    
    return heights, max_height

def main():
    """Test multiple seeds for Downy birch."""
    print("Testing Downy birch with different random seeds...")
    
    seeds_to_test = [1, 5, 10, 23, 42, 50, 77, 100, 123, 500, 999, 1337, 2023, 5555]
    results = []
    
    for seed in tqdm(seeds_to_test, desc="Testing seeds"):
        try:
            heights, max_height = test_birch_with_seed(seed, cycles=75)
            
            # Check if tree kept growing (no major decline)
            final_height = heights[-1]
            peak_height = max(heights)
            decline_ratio = (peak_height - final_height) / peak_height if peak_height > 0 else 0
            
            # Find when peak occurred
            peak_cycle = heights.index(peak_height) if peak_height in heights else -1
            
            results.append({
                'seed': seed,
                'peak_height': peak_height,
                'final_height': final_height,
                'peak_cycle': peak_cycle,
                'decline_ratio': decline_ratio,
                'kept_growing': decline_ratio < 0.1  # Less than 10% decline
            })
            
            print(f"Seed {seed}: Peak {peak_height:.2f}m at cycle {peak_cycle}, "
                  f"Final {final_height:.2f}m, Decline {decline_ratio:.1%}")
                  
        except Exception as e:
            print(f"Seed {seed} failed: {e}")
    
    # Summary
    growing_trees = [r for r in results if r['kept_growing']]
    declining_trees = [r for r in results if not r['kept_growing']]
    
    print(f"\n=== SUMMARY ===")
    print(f"Trees that kept growing: {len(growing_trees)}/{len(results)}")
    print(f"Trees that declined: {len(declining_trees)}/{len(results)}")
    
    if growing_trees:
        print(f"\nSeeds with continued growth:")
        for r in growing_trees:
            print(f"  Seed {r['seed']}: {r['final_height']:.2f}m final height")
    
    if declining_trees:
        print(f"\nSeeds with major decline:")
        for r in declining_trees[:5]:  # Show first 5
            print(f"  Seed {r['seed']}: {r['peak_height']:.2f}m → {r['final_height']:.2f}m "
                  f"({r['decline_ratio']:.1%} decline)")

if __name__ == "__main__":
    main()