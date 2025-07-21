#!/usr/bin/env python3
"""
Generate forest models using cleaned growpy structure with USD multi-LOD export.

This script creates forest models from CSV data using the simplified growpy API
and species growth models from utils.
"""

import sys
from pathlib import Path

# Add paths for imports
src_path = Path(__file__).parent / "src"
grove_core_path = src_path / "the_grove_22" / "modules"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(grove_core_path))

# Import after path setup
import pandas as pd

from growpy.core.config import GrowPyConfig
from growpy.core.grove import (
    add_tree_to_grove,
    calculate_shared_light_competition,
    create_grove,
)
from growpy.core.validate import validate_csv_data
from growpy.io.models import export_forest_models_with_twigs
from utils.species_growth_analysis import GrowthModelLoader


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """Load and validate CSV forest data."""
    data = pd.read_csv(csv_path)
    validate_csv_data(data)
    return data


def save_grove_json_files(forest_data, grove_dir: Path) -> list[Path]:
    """Save grove JSON files for Blender import."""
    import the_grove_22_core as gc
    
    grove_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    
    for grove, species_name, tree_count in forest_data:
        safe_species_name = species_name.replace(" ", "_").replace("_-_", "_")
        filename = f"{safe_species_name}_grove.json"
        file_path = grove_dir / filename
        
        # Use correct Grove to JSON export method
        json_string = gc.io.grove_to_json_string(grove)
        
        with open(file_path, 'w') as f:
            f.write(json_string)
            
        saved_files.append(file_path)
        
    return saved_files


def main():
    """Generate forest models using new growpy structure."""
    print("Grove Forest Generator v4.0 - USD Multi-LOD")
    print("=" * 50)
    
    # Setup paths
    data_dir = Path(__file__).parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"
    csv_path = input_dir / "small_demo.csv"
    config_path = Path(__file__).parent / "config.ini"
    growth_models_dir = data_dir / "growth_models"
    
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return 1
    
    # Load configuration
    if config_path.exists():
        config = GrowPyConfig.from_config_file(config_path)
        print(f"Loaded configuration from {config_path.name}")
    else:
        config = GrowPyConfig()
        print("Using default configuration")
    
    input_name = csv_path.stem
    print(f"Input: {csv_path}")
    print(f"Output: {output_dir / input_name}")
    
    # Step 1: Load and validate CSV data
    print("\n1. Loading forest data...")
    data = load_csv_data(csv_path)
    print(f"   Loaded {len(data)} trees from CSV")
    
    # Step 2: Load growth models for age prediction
    if 'height' in data.columns and growth_models_dir.exists():
        print("\n2. Loading species growth models...")
        growth_loader = GrowthModelLoader(growth_models_dir)
        
        print("   Calculating age predictions...")
        enhanced_data, max_cycles = growth_loader.calculate_forest_delays(data)
        print(f"   Age predictions complete, max cycles: {max_cycles}")
    else:
        print("\n2. No height data or growth models, using default cycles")
        enhanced_data = data
        max_cycles = 50  # Default cycles when no height data
        if 'height' in data.columns:
            # Add default delay column
            enhanced_data = enhanced_data.copy()
            enhanced_data['delay'] = 0
    
    # Step 3: Create grove objects
    print("\n3. Creating grove objects...")
    forest_data = []
    species_groups = enhanced_data.groupby("species")
    
    for species_name, species_data in species_groups:
        print(f"   Creating grove for {species_name} ({len(species_data)} trees)")
        grove = create_grove(species_name, config.random_seed)
        
        for _, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = row.get("delay", 0)
            add_tree_to_grove(grove, position, delay=delay)
        
        forest_data.append((grove, species_name, len(species_data)))
    
    total_trees = sum(tree_count for _, _, tree_count in forest_data)
    print(f"   Created {len(forest_data)} species groves")
    print(f"   Total trees: {total_trees}, Growth cycles: {max_cycles}")
    
    # Step 4: Simulate growth
    print("\n4. Simulating growth...")
    groves = [grove for grove, _, _ in forest_data]
    
    for cycle in range(max_cycles):
        # Calculate light competition
        calculate_shared_light_competition(groves)
        
        # Simulate one cycle for each grove
        for grove, _, _ in forest_data:
            grove.simulate(1)
        
        if (cycle + 1) % 10 == 0 or cycle == max_cycles - 1:
            print(f"   Completed cycle {cycle + 1}/{max_cycles}")
    
    print("   Growth simulation complete")
    
    # Step 5: Export files
    print("\n5. Exporting files...")
    
    # Export grove JSONs for Blender
    grove_dir = output_dir / input_name / "groves"
    grove_files = save_grove_json_files(forest_data, grove_dir)
    
    # Export USD models with multi-LOD and twig instances
    lod_configs = config.get_lod_configs()
    twig_prototypes_dir = data_dir / "twig_prototypes"
    
    usd_files = export_forest_models_with_twigs(
        forest_data, 
        output_dir, 
        lod_configs, 
        input_name, 
        twig_prototypes_dir if twig_prototypes_dir.exists() else None
    )
    
    # Final summary
    print("\n" + "=" * 50)
    print("Forest generation complete!")
    print("\nExport Summary:")
    print(f"  Grove JSON files: {len(grove_files)}")
    print(f"  USD multi-LOD files: {len(usd_files)}")
    
    print(f"\nOutput structure:")
    print(f"  {grove_dir}/              - JSON files for Blender import")
    print(f"  {output_dir / input_name / 'usd_trees_multi_lod'}/  - USD files with all LODs and twigs")
    
    if growth_models_dir.exists():
        print(f"  Growth models from: {growth_models_dir}/")
    else:
        print(f"\nTip: Generate species growth models with:")
        print(f"  python src/utils/species_growth_analysis.py --output_dir {growth_models_dir}")
    
    if not twig_prototypes_dir.exists():
        print(f"\nTip: Generate USD twig prototypes with:")
        print(f"  python src/utils/convert_twigs_to_usd.py --twigs_dir src/the_grove_22/twigs --output_dir {twig_prototypes_dir}")
    
    return 0


if __name__ == "__main__":
    exit(main())