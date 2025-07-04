# GrowPy - Simple Forest Generation

A simple Python module for generating 3D tree forests from CSV data using The Grove 2.2.

## Quick Start

```python
from growpy import grow_forest_from_csv

# Generate trees from CSV
generated_files = grow_forest_from_csv(
    csv_file="data/demo_forest.csv",
    output_dir="output/trees"
)

print(f"Generated {len(generated_files)} tree models")
```

## CSV Format

Your CSV file needs these columns:

```csv
x,y,z,species,age
0.0,0.0,0.0,Fagaceae - European oak,25
15.0,2.0,0.0,Pinaceae - Scots pine,18
-8.0,5.0,0.0,Betulaceae - Silver birch,12
```

- **x,y,z**: Tree position coordinates
- **species**: Species name (must match Grove presets exactly)
- **age**: Tree age in years

## Available Species

Use these exact names in your CSV:

- Fagaceae - European oak
- Fagaceae - Red oak
- Fagaceae - White oak
- Fagaceae - Beech
- Pinaceae - Scots pine
- Pinaceae - Austrian pine
- Pinaceae - Fir
- Betulaceae - Silver birch
- Betulaceae - Downy birch
- Salicaceae - Aspen
- And 40+ more...

See `src/the_grove_22/presets/` for all available species.

## Function Reference

### grow_forest_from_csv(csv_file, output_dir="output", grove_path=None)

Generate 3D tree models from CSV data.

**Parameters:**

- `csv_file`: Path to CSV file with tree data
- `output_dir`: Directory to save OBJ files (default: "output")
- `grove_path`: Path to Grove installation (auto-detected if None)

**Returns:**

- List of generated file paths

**Example:**

```python
files = grow_forest_from_csv("forest.csv", "models/")
```

## Requirements

- Python 3.7+
- The Grove 2.2 (included)
- No additional packages needed

## Test

Run the included test:

```bash
cd src
python test_simple.py
```
