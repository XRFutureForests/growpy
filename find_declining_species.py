#!/usr/bin/env python3
"""
Find species with declining height curves in existing growth models.
"""

import json
from pathlib import Path
from typing import List, Tuple

def analyze_height_curve(height_curve: List[float]) -> Tuple[float, float, bool]:
    """
    Analyze a height curve for decline patterns.
    
    Returns:
        (peak_height, final_height, has_significant_decline)
    """
    if not height_curve or len(height_curve) < 10:
        return 0.0, 0.0, False
    
    peak_height = max(height_curve)
    final_height = height_curve[-1]
    
    # Consider significant if final height is more than 20% below peak
    decline_ratio = (peak_height - final_height) / peak_height if peak_height > 0 else 0
    has_significant_decline = decline_ratio > 0.2
    
    return peak_height, final_height, has_significant_decline

def find_declining_species(growth_models_dir: Path) -> List[dict]:
    """Find all species with declining height curves."""
    declining_species = []
    
    if not growth_models_dir.exists():
        print(f"Growth models directory not found: {growth_models_dir}")
        return declining_species
    
    # Scan all species directories
    for species_dir in growth_models_dir.iterdir():
        if not species_dir.is_dir():
            continue
            
        height_curve_file = species_dir / "height_curve.json"
        if not height_curve_file.exists():
            continue
            
        try:
            with open(height_curve_file, 'r') as f:
                data = json.load(f)
                
            height_curve = data.get("height_curve", [])
            species_name = data.get("species", species_dir.name)
            
            peak_height, final_height, has_decline = analyze_height_curve(height_curve)
            
            if has_decline:
                decline_ratio = (peak_height - final_height) / peak_height
                declining_species.append({
                    'species': species_name,
                    'species_dir': species_dir.name,
                    'peak_height': peak_height,
                    'final_height': final_height,
                    'decline_ratio': decline_ratio,
                    'cycles': len(height_curve)
                })
                
        except Exception as e:
            print(f"Error analyzing {species_dir.name}: {e}")
            continue
    
    return declining_species

def main():
    """Find and report declining species."""
    growth_models_dir = Path("data/growth_models")
    
    print("Scanning for species with declining height curves...")
    declining_species = find_declining_species(growth_models_dir)
    
    if not declining_species:
        print("✅ No species found with significant height curve declines!")
        return
    
    print(f"\n🔍 Found {len(declining_species)} species with significant decline:")
    print("=" * 80)
    
    # Sort by decline ratio (worst first)
    declining_species.sort(key=lambda x: x['decline_ratio'], reverse=True)
    
    for i, species in enumerate(declining_species, 1):
        print(f"{i:2d}. {species['species']}")
        print(f"    Peak: {species['peak_height']:.2f}m → Final: {species['final_height']:.2f}m")
        print(f"    Decline: {species['decline_ratio']:.1%} over {species['cycles']} cycles")
        print(f"    Directory: {species['species_dir']}")
        print()
    
    # Generate re-run commands
    print("🔧 Commands to re-run these species with multiple seeds:")
    print("=" * 80)
    for species in declining_species:
        # Convert directory name back to species name (rough approximation)
        species_name = species['species']
        print(f'python src/utils/species_growth_analysis.py --species "{species_name}" --seeds 5 --cycles 75')
    
    print(f"\n💡 Tip: Use --seeds 5 to average across 5 different random seeds")

if __name__ == "__main__":
    main()