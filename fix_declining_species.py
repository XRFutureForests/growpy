#!/usr/bin/env python3
"""
Re-run growth analysis for all species with declining height curves.
"""

import subprocess
import sys
from pathlib import Path

# Species that need re-running with multiple seeds
DECLINING_SPECIES = [
    "Myrtaceae - Blue gum",
    "Salicaceae - Grey poplar", 
    "Betulaceae - Downy birch",
    "Fabaceae - Robinia",
    "Pinaceae - Stone pine",
    "Salicaceae - Aspen",
    "Rosaceae - Wild cherry",
    "Pinaceae - Lodgepole pine",
    "Salicaceae - Willow"
]

def run_species_analysis(species_name: str, seeds: int = 5, cycles: int = 75):
    """Run growth analysis for a specific species."""
    cmd = [
        sys.executable, 
        "src/utils/species_growth_analysis.py",
        "--species", species_name,
        "--seeds", str(seeds),
        "--cycles", str(cycles)
    ]
    
    print(f"🌱 Re-running analysis for: {species_name}")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print(f"   ✅ Success for {species_name}")
            return True
        else:
            print(f"   ❌ Failed for {species_name}")
            print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timeout for {species_name} (>10 minutes)")
        return False
    except Exception as e:
        print(f"   💥 Exception for {species_name}: {e}")
        return False

def main():
    """Re-run analysis for all declining species."""
    print("🔧 Re-running growth analysis for species with declining curves...")
    print(f"   Found {len(DECLINING_SPECIES)} species to fix")
    print("=" * 80)
    
    successful = 0
    failed = 0
    
    for i, species in enumerate(DECLINING_SPECIES, 1):
        print(f"\n[{i}/{len(DECLINING_SPECIES)}]", end=" ")
        
        if run_species_analysis(species, seeds=5):
            successful += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"📊 SUMMARY:")
    print(f"   ✅ Successfully re-analyzed: {successful}/{len(DECLINING_SPECIES)} species")
    print(f"   ❌ Failed: {failed}/{len(DECLINING_SPECIES)} species")
    
    if successful > 0:
        print(f"\n💡 Updated growth models saved to: data/growth_models/")
        print(f"   These now use averaged curves from 5 different random seeds")

if __name__ == "__main__":
    main()