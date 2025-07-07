# The Grove 2.2 - Procedural Tree Generation

The Grove is a powerful Python library for procedural tree generation, designed for experienced developers who want to integrate realistic tree growth simulation into their pipelines. This project includes the core Python bindings and a comprehensive set of species presets.

## Overview

The Grove Core is built as a Python module that simulates realistic tree growth using advanced algorithms. It can generate 3D tree models in various formats (OBJ, USD), making it suitable for use in 3D applications, game engines, and visual effects pipelines.

**Key Features:**

- Procedural tree growth simulation based on realistic biological processes
- 50+ pre-configured species presets (Oak, Pine, Birch, etc.)
- Support for multiple output formats (OBJ, USD)
- Customizable growth parameters
- Support for creating tree scenes from CSV data
- Cross-platform compatibility (Windows, macOS, Linux)

## Project Structure

```text
src/the_grove_22/
├── modules/the_grove_22_core/     # Core Python module
├── presets/                       # Species-specific JSON presets
├── documentation/                 # HTML documentation
├── textures/                      # Bark and leaf textures
└── twigs/                         # Twig geometry files
```

## Installation & Setup

### Requirements

- Python 3.7+
- The Grove requires platform-specific binary modules

### Module Loading

The Grove automatically detects your platform and loads the appropriate binary:

- Linux: `the_grove_22_core_linux.so` *(Note: Currently missing - may need macOS/Windows)*
- Windows: `the_grove_22_core_windows.pyd`
- macOS (Apple Silicon): `the_grove_22_core_macos.so`
- macOS (Intel): `the_grove_22_core_macos_intel.so`

Add the modules directory to your Python path:

```python
import sys
sys.path.append('/path/to/the-grove/src/the_grove_22/modules')
import the_grove_22_core
```

## Basic Usage

### Simple Tree Generation

```python
import the_grove_22_core

# Create a new grove (tree collection)
grove = the_grove_22_core.Grove()

# Simulate 10 years of growth
grove.simulate(10)

# Build 3D models with specified resolution
models = grove.build_models({"resolution": 32})

# Export to OBJ format
obj_string = the_grove_22_core.io.model_to_obj_string(models[0])
with open('tree.obj', 'w') as f:
    f.write(obj_string)
```

### Using Species Presets

```python
import the_grove_22_core
import json

# Load a species preset (e.g., European Oak)
with open('src/the_grove_22/presets/Fagaceae - European oak.seed.json', 'r') as f:
    preset_data = json.load(f)

# Create grove and apply preset
grove = the_grove_22_core.Grove()
props = grove.get_properties()

# Apply preset properties
for key, value in preset_data.items():
    try:
        setattr(props, key, value)
    except TypeError:
        print(f"Skipping property {key}, incorrect type")

grove.set_properties(props)
grove.simulate(15)  # Grow for 15 years

# Build and export
models = grove.build_models({"resolution": 16})
```

## Creating Tree Scenes from CSV Data

For your use case of creating ~20 trees from CSV data with position, species, and height/age information:

### CSV Format Example

```csv
x,y,z,species,age,height
0.0,0.0,0.0,Fagaceae - European oak,15,8.5
10.0,0.0,5.0,Pinaceae - Scots pine,12,6.2
-5.0,0.0,8.0,Betulaceae - Silver birch,8,4.1
```

### Complete Scene Generation Script

```python
import the_grove_22_core
import csv
import json
import os

def load_preset(preset_name):
    """Load species preset from JSON file"""
    preset_path = f"src/the_grove_22/presets/{preset_name}.seed.json"
    if os.path.exists(preset_path):
        with open(preset_path, 'r') as f:
            return json.load(f)
    return None

def create_tree_scene_from_csv(csv_file, output_dir="output"):
    """Create a scene of trees from CSV data"""
    os.makedirs(output_dir, exist_ok=True)
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            # Extract data from CSV
            x, y, z = float(row['x']), float(row['y']), float(row['z'])
            species = row['species']
            age = int(row['age'])
            target_height = float(row.get('height', 0))  # Optional
            
            print(f"Creating tree {i+1}: {species} at ({x}, {y}, {z}), age {age}")
            
            # Create new grove for this tree
            grove = the_grove_22_core.Grove()
            
            # Load and apply species preset
            preset_data = load_preset(species)
            if preset_data:
                props = grove.get_properties()
                for key, value in preset_data.items():
                    try:
                        setattr(props, key, value)
                    except (TypeError, AttributeError):
                        pass  # Skip invalid properties
                grove.set_properties(props)
            
            # Position the tree
            grove.replant_tree(0, 
                             the_grove_22_core.Vector(x, y, z),
                             the_grove_22_core.Rotation(0, 0, 0))
            
            # Simulate growth
            grove.simulate(age)
            
            # Build model
            models = grove.build_models({
                "resolution": 16,
                "resolution_reduce": 0.8,
                "build_blend": True,
                "build_end_cap": True
            })
            
            # Export to OBJ
            if models:
                obj_string = the_grove_22_core.io.model_to_obj_string(models[0])
                filename = f"{output_dir}/tree_{i+1:03d}_{species.replace(' ', '_')}.obj"
                with open(filename, 'w') as f:
                    f.write(obj_string)
                
                print(f"  -> Exported to {filename}")

# Usage
create_tree_scene_from_csv("trees.csv")
```

### Combined Scene Export

```python
def create_combined_scene_from_csv(csv_file, output_file="forest_scene.obj"):
    """Create a single combined OBJ file with all trees"""
    grove = the_grove_22_core.Grove()
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        first_tree = True
        
        for i, row in enumerate(reader):
            x, y, z = float(row['x']), float(row['y']), float(row['z'])
            species = row['species']
            age = int(row['age'])
            
            if first_tree:
                first_tree = False
                # Configure the first tree
                preset_data = load_preset(species)
                if preset_data:
                    props = grove.get_properties()
                    for key, value in preset_data.items():
                        try:
                            setattr(props, key, value)
                        except (TypeError, AttributeError):
                            pass
                    grove.set_properties(props)
            else:
                # Add additional trees to the grove
                position = the_grove_22_core.Vector(x, y, z)
                direction = the_grove_22_core.Vector(0, 0, 1)
                grove.add_new_tree(position, direction, 0)
    
    # Simulate all trees
    grove.simulate(max(ages_from_csv))  # You'd need to track max age
    
    # Build as single model
    combined_model = grove.build_as_one_model({"resolution": 16})
    
    # Export
    obj_string = the_grove_22_core.io.model_to_obj_string(combined_model)
    with open(output_file, 'w') as f:
        f.write(obj_string)
```

## Available Species Presets

The Grove includes 50+ scientifically-named presets:

**Trees by Family:**

- **Fagaceae**: European oak, Red oak, White oak, Beech, Sweet chestnut
- **Pinaceae**: Scots pine, Austrian pine, Ponderosa pine, Fir, Grand fir
- **Betulaceae**: Silver birch, Paper birch, Downy birch, Alder, Hazel
- **Salicaceae**: Aspen, Grey poplar, Italian poplar, Weeping willow
- **And many more...**

## Growth Parameters

Key properties you can modify:

- `grow_nodes`: Number of nodes to grow per flush (default: 4)
- `grow_length`: Length of each growth segment (default: 0.5)
- `favor_bright`: How much to favor bright directions (0.0-1.0)
- `turn_to_light`: Light tropism strength (0.0-1.0)
- `thicken_tips`: Branch tip thickness (default: 0.006)
- `bend_mass`: How much branches bend under weight (0.0-1.0)

## Build Options

When calling `build_models()`:

- `resolution`: Number of points at tree base (default: 16)
- `resolution_reduce`: How fast resolution decreases (0.0-1.0, default: 0.8)
- `texture_repeat`: Bark texture repetitions around trunk (default: 3)
- `build_cutoff_thickness`: Minimum branch thickness to build (default: 0.0)
- `build_blend`: Add blending geometry at branch junctions (default: True)
- `build_end_cap`: Close branch ends (default: True)

## Important Notes

### Rust-Python Ownership

The Grove is written in Rust, which has different memory management than Python. Always use getter/setter methods:

```python
# ❌ This won't work (creates copies):
grove.trees[0].nodes[4].dead = True

# ✅ Do this instead:
props = grove.get_properties()
props.some_setting = new_value
grove.set_properties(props)
```

### Platform Compatibility

- **Linux**: May require the macOS binary renamed to `the_grove_22_core_linux.so`
- **Windows**: Should work with included `.pyd` file
- **macOS**: Works with both Intel and Apple Silicon binaries

## Advanced Features

- **Manual Pruning**: Use `grove.manual_prune(RayTree)` to prune against geometry
- **Manual Drawing**: Guide growth with `grove.manual_draw(start_node, guide_path)`
- **Random Seeds**: Set `grove.set_random_seed(seed)` for reproducible results
- **Multiple Formats**: Export to USD with `model_to_usda_string()` (Studio edition)

## Troubleshooting

1. **Module Import Errors**: Ensure the correct binary for your platform exists
2. **Performance**: Use lower `resolution` values for faster builds
3. **Memory**: Process trees individually for large scenes
4. **Linux**: May need to use macOS binary or compile from source

## GrowPy Python Module

We've created **GrowPy**, a simple Python module that makes it easy to generate forests from CSV data. GrowPy provides a single function interface to The Grove's procedural tree generation system with proper error handling and the correct Rotation API usage.

### Quick Start with GrowPy

```python
from growpy import grow_forest_from_csv

# Generate trees from CSV
generated_files = grow_forest_from_csv(
    csv_file="data/demo_forest.csv",
    output_dir="data/output"
)

print(f"Generated {len(generated_files)} tree models")
```

### CSV Format

Your CSV file must include these columns:

- `x`, `y`, `z`: Tree position coordinates (float)
- `species`: Species name matching a preset (string)
- `age`: Tree age in years (integer)
- `height`: Optional target height in meters (float)

### Example CSV

```csv
x,y,z,species,age,height
0.0,0.0,0.0,Fagaceae - European oak,25,12.5
15.0,2.0,0.0,Pinaceae - Scots pine,18,9.2
-8.0,5.0,0.0,Betulaceae - Silver birch,12,7.8
```

### Available Functions

- `grow_forest_from_csv()`: Generate individual tree OBJ files
- `grow_combined_forest_from_csv()`: Generate single combined forest OBJ
- `list_available_species()`: Get all available species names
- `validate_csv_format()`: Check CSV format before processing

### Quick Demo

```bash
cd src
python main.py
```

This demonstrates the complete GrowPy functionality using the demo forest CSV and generates both individual tree models and a combined forest OBJ file.

See the [GrowPy documentation](src/growpy/README.md) for complete API details.

### Quick Test

```bash
cd src
python main.py
```

This demonstrates the complete GrowPy functionality using the demo forest CSV and generates tree models as OBJ files using the fixed Rotation API.

## Example Projects

- **GrowPy Module**: Simple Python package in `src/growpy/` with single-function forest generation
- **Demo Forest**: See `data/demo_forest.csv` for a 20-tree example scene with mixed species
- **Main Demo**: Run `python main.py` in the `src/` directory to see all features in action
- **Species Presets**: Browse `src/the_grove_22/presets/` for 50+ species parameters
- **Documentation**: Explore `src/the_grove_22/documentation/` for comprehensive API docs

---

**The Grove 2.2** - For procedural tree generation in production pipelines
