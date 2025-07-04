"""
GrowPy - Simple forest generation from CSV using The Grove 2.2

This module provides a single function to generate 3D tree models from CSV data.
"""

import os
import sys
import csv
import json
from pathlib import Path

# Add The Grove modules to Python path
grove_modules_path = os.path.join(os.path.dirname(__file__), '..', 'the_grove_22', 'modules')
grove_modules_path = os.path.abspath(grove_modules_path)
if grove_modules_path not in sys.path:
    sys.path.insert(0, grove_modules_path)

try:
    import the_grove_22_core
except ImportError as e:
    raise ImportError(
        f"Could not import The Grove 2.2 core module. "
        f"Please ensure the modules are available at: {grove_modules_path}"
    ) from e


def grow_forest_from_csv(csv_file, output_dir="output", grove_path=None):
    """
    Generate individual 3D tree models from CSV data.
    
    Args:
        csv_file: Path to CSV file with columns: x,y,z,species,age
        output_dir: Directory to save generated OBJ files
        grove_path: Path to The Grove installation (auto-detected if None)
    
    Returns:
        List of generated file paths
    
    CSV Format:
        x,y,z,species,age,height
        0.0,0.0,0.0,Fagaceae - European oak,25,12.5
        15.0,2.0,0.0,Pinaceae - Scots pine,18,9.2
    """
    
    # Auto-detect grove path if not provided
    if grove_path is None:
        grove_path = os.path.join(os.path.dirname(__file__), '..', 'the_grove_22')
        grove_path = os.path.abspath(grove_path)
    
    presets_path = os.path.join(grove_path, 'presets')
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load CSV data
    print(f"Loading CSV: {csv_file}")
    trees = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trees.append({
                'x': float(row['x']),
                'y': float(row['y']),
                'z': float(row['z']),
                'species': row['species'].strip(),
                'age': int(row['age'])
            })
    
    print(f"Found {len(trees)} trees")
    
    # Create single grove for all trees
    print("Creating grove with all trees...")
    grove = the_grove_22_core.Grove()
    
    # Use the first tree's species as base preset (could be improved)
    if trees:
        first_species = trees[0]['species']
        preset_file = os.path.join(presets_path, f"{first_species}.seed.json")
        if os.path.exists(preset_file):
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # Apply preset to grove
            props = grove.get_properties()
            for key, value in preset_data.items():
                try:
                    setattr(props, key, value)
                except:
                    pass
            grove.set_properties(props)
            print(f"Applied base preset: {first_species}")
        
        # Position first tree
        first_tree = trees[0]
        position = the_grove_22_core.Vector(first_tree['x'], first_tree['y'], first_tree['z'])
        rotation = the_grove_22_core.Rotation(0, 0, 0)
        grove.replant_tree(0, position, rotation)
        print(f"Positioned first tree: {first_species}")
        
        # Add remaining trees to the same grove
        for tree_data in trees[1:]:
            position = the_grove_22_core.Vector(tree_data['x'], tree_data['y'], tree_data['z'])
            direction = the_grove_22_core.Vector(0, 0, 1)  # Up direction
            grove.add_new_tree(position, direction, 0)  # No delay
            print(f"Added tree: {tree_data['species']} at ({tree_data['x']:.1f}, {tree_data['y']:.1f}, {tree_data['z']:.1f})")
        
        # Find maximum age for simulation
        max_age = max(tree['age'] for tree in trees)
        print(f"Simulating {max_age} years of growth for all trees simultaneously...")
        grove.simulate(max_age)
        
        # Build individual models for each tree
        print("Building individual tree models...")
        build_options = {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "build_blend": True,
            "build_end_cap": True
        }
        models = grove.build_models(build_options)
        
        # Export each tree as separate OBJ file
        generated_files = []
        if models:
            for i, model in enumerate(models):
                tree_data = trees[i] if i < len(trees) else trees[0]
                species_clean = tree_data['species'].replace(' ', '_').replace('-', '')
                filename = f"tree_{i+1:03d}_{species_clean}.obj"
                filepath = os.path.join(output_dir, filename)
                
                obj_string = the_grove_22_core.io.model_to_obj_string(model)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(obj_string)
                
                generated_files.append(filepath)
                print(f"  -> {filename}")
        else:
            print("  -> Failed to generate models")
    
    print(f"Generated {len(generated_files)} tree models in {output_dir}")
    return generated_files


def grow_combined_forest_from_csv(csv_file, output_file="forest.obj", grove_path=None):
    """
    Generate a single combined 3D forest model from CSV data.
    
    Args:
        csv_file: Path to CSV file with columns: x,y,z,species,age
        output_file: Path to save the combined OBJ file
        grove_path: Path to The Grove installation (auto-detected if None)
    
    Returns:
        Path to generated file
    
    This function creates all trees in a single grove and exports them as one model.
    Trees will compete for light and space naturally.
    """
    
    # Auto-detect grove path if not provided
    if grove_path is None:
        grove_path = os.path.join(os.path.dirname(__file__), '..', 'the_grove_22')
        grove_path = os.path.abspath(grove_path)
    
    presets_path = os.path.join(grove_path, 'presets')
    
    # Create output directory
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Load CSV data
    print(f"Loading CSV: {csv_file}")
    trees = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trees.append({
                'x': float(row['x']),
                'y': float(row['y']),
                'z': float(row['z']),
                'species': row['species'].strip(),
                'age': int(row['age'])
            })
    
    print(f"Found {len(trees)} trees")
    
    # Create single grove for all trees
    print("Creating combined forest grove...")
    grove = the_grove_22_core.Grove()
    
    # Use the first tree's species as base preset
    if trees:
        first_species = trees[0]['species']
        preset_file = os.path.join(presets_path, f"{first_species}.seed.json")
        if os.path.exists(preset_file):
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # Apply preset to grove
            props = grove.get_properties()
            for key, value in preset_data.items():
                try:
                    setattr(props, key, value)
                except:
                    pass
            grove.set_properties(props)
            print(f"Applied base preset: {first_species}")
        
        # Position first tree
        first_tree = trees[0]
        position = the_grove_22_core.Vector(first_tree['x'], first_tree['y'], first_tree['z'])
        rotation = the_grove_22_core.Rotation(0, 0, 0)
        grove.replant_tree(0, position, rotation)
        print(f"Positioned first tree: {first_species}")
        
        # Add remaining trees to the same grove
        for tree_data in trees[1:]:
            position = the_grove_22_core.Vector(tree_data['x'], tree_data['y'], tree_data['z'])
            direction = the_grove_22_core.Vector(0, 0, 1)  # Up direction
            grove.add_new_tree(position, direction, 0)  # No delay
            print(f"Added tree: {tree_data['species']} at ({tree_data['x']:.1f}, {tree_data['y']:.1f}, {tree_data['z']:.1f})")
        
        # Find maximum age for simulation
        max_age = max(tree['age'] for tree in trees)
        print(f"Simulating {max_age} years of growth for combined forest...")
        grove.simulate(max_age)
        
        # Build single combined model
        print("Building combined forest model...")
        build_options = {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "build_blend": True,
            "build_end_cap": True
        }
        model = grove.build_model(build_options)  # Single model
        
        # Export as single OBJ file
        if model:
            obj_string = the_grove_22_core.io.model_to_obj_string(model)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(obj_string)
            
            print(f"Generated combined forest: {output_file}")
            return output_file
        else:
            print("Failed to generate combined model")
            return None
    
    return None
    
    # Auto-detect grove path if not provided
    if grove_path is None:
        grove_path = os.path.join(os.path.dirname(__file__), '..', 'the_grove_22')
        grove_path = os.path.abspath(grove_path)
    
    presets_path = os.path.join(grove_path, 'presets')
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load CSV data
    print(f"Loading CSV: {csv_file}")
    trees = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trees.append({
                'x': float(row['x']),
                'y': float(row['y']),
                'z': float(row['z']),
                'species': row['species'].strip(),
                'age': int(row['age'])
            })
    
    print(f"Found {len(trees)} trees")
    
    # Create single grove for all trees
    print("Creating grove with all trees...")
    grove = the_grove_22_core.Grove()
    
    # Use the first tree's species as base preset (could be improved)
    if trees:
        first_species = trees[0]['species']
        preset_file = os.path.join(presets_path, f"{first_species}.seed.json")
        if os.path.exists(preset_file):
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # Apply preset to grove
            props = grove.get_properties()
            for key, value in preset_data.items():
                try:
                    setattr(props, key, value)
                except:
                    pass
            grove.set_properties(props)
            print(f"Applied base preset: {first_species}")
        
        # Position first tree
        first_tree = trees[0]
        position = the_grove_22_core.Vector(first_tree['x'], first_tree['y'], first_tree['z'])
        rotation = the_grove_22_core.Rotation(0, 0, 0)
        grove.replant_tree(0, position, rotation)
        print(f"Positioned first tree: {first_species}")
        
        # Add remaining trees to the same grove
        for tree_data in trees[1:]:
            position = the_grove_22_core.Vector(tree_data['x'], tree_data['y'], tree_data['z'])
            direction = the_grove_22_core.Vector(0, 0, 1)  # Up direction
            grove.add_new_tree(position, direction, 0)  # No delay
            print(f"Added tree: {tree_data['species']} at ({tree_data['x']:.1f}, {tree_data['y']:.1f}, {tree_data['z']:.1f})")
        
        # Find maximum age for simulation
        max_age = max(tree['age'] for tree in trees)
        print(f"Simulating {max_age} years of growth for all trees simultaneously...")
        grove.simulate(max_age)
        
        # Build individual models for each tree
        print("Building individual tree models...")
        build_options = {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "build_blend": True,
            "build_end_cap": True
        }
        models = grove.build_models(build_options)
        
        # Export each tree as separate OBJ file
        generated_files = []
        if models:
            for i, model in enumerate(models):
                tree_data = trees[i] if i < len(trees) else trees[0]
                species_clean = tree_data['species'].replace(' ', '_').replace('-', '')
                filename = f"tree_{i+1:03d}_{species_clean}.obj"
                filepath = os.path.join(output_dir, filename)
                
                obj_string = the_grove_22_core.io.model_to_obj_string(model)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(obj_string)
                
                generated_files.append(filepath)
                print(f"  -> {filename}")
        else:
            print("  -> Failed to generate models")
    
    print(f"Generated {len(generated_files)} tree models in {output_dir}")
    return generated_files
