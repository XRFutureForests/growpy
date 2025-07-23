#!/usr/bin/env python3
"""Quick test of different seeds for Downy birch - fewer cycles for speed."""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

import the_grove_22_core as gc

def test_seed_quick(seed_value, cycles=60):
    """Quick test with specific seed."""
    grove = gc.Grove()
    grove.set_random_seed(seed_value)
    
    # Load preset manually
    presets_dir = src_path / "the_grove_22" / "presets"
    preset_path = presets_dir / "Betulaceae - Downy birch.seed.json"
    with open(preset_path, "r") as f:
        preset_json = f.read()
    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)
    
    grove.clear_trees()
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    
    heights = []
    for cycle in range(cycles):
        grove.simulate(1)
        
        current_height = 0.0
        if grove.trees and len(grove.trees) > 0:
            tree = grove.trees[0]
            if hasattr(tree, "nodes") and len(tree.nodes) > 0:
                for node in tree.nodes:
                    if node.pos.z > current_height:
                        current_height = node.pos.z
        
        heights.append(current_height)
    
    return heights

# Test a few seeds quickly
seeds = [1, 23, 42, 100, 500]
print("Quick birch test (60 cycles):")

for seed in seeds:
    heights = test_seed_quick(seed, 60)
    peak = max(heights)
    final = heights[-1]
    decline = (peak - final) / peak if peak > 0 else 0
    
    print(f"Seed {seed:3d}: Peak {peak:5.2f}m, Final {final:5.2f}m, Decline {decline:5.1%}")