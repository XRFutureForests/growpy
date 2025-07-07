# GrowPy - Forest Generation from CSV Data

GrowPy is a Python module that provides a simple interface to The Grove 2.2's procedural tree generation system. It allows you to create realistic 3D tree models from CSV data containing tree positions, species, and growth parameters.

## Features

- **CSV-based forest generation**: Create forests from simple CSV files
- **50+ species presets**: Use scientifically-named tree species with realistic growth parameters
- **Individual or combined models**: Generate separate OBJ files per tree or a single combined forest
- **Customizable resolution**: Control model detail level for performance vs quality
- **Validation**: Built-in CSV format validation and error handling

## Installation

GrowPy is part of The Grove 2.2 project. Ensure you have:

1. Python 3.7+
2. The Grove 2.2 core modules properly installed
3. The species presets and required files

## Quick Start

```python
from growpy import grow_forest_from_csv

# Generate individual tree models from CSV data
generated_files = grow_forest_from_csv(
    csv_file="forest_data.csv",
    output_dir="forest_models",
    resolution=16
)

print(f"Generated {len(generated_files)} tree models")
```

## CSV Format

Your CSV file must contain the following columns:

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

## API Reference

### Main Functions

#### `grow_forest_from_csv(csv_file, output_dir="output", resolution=16, file_prefix="tree_", validate_format=True)`

Generate individual tree models from CSV data.

**Parameters:**

- `csv_file`: Path to CSV file with tree data
- `output_dir`: Directory to save generated OBJ files (default: "output")
- `resolution`: Model resolution - sides at tree base (default: 16)
- `file_prefix`: Prefix for generated filenames (default: "tree_")
- `validate_format`: Whether to validate CSV format first (default: True)

**Returns:** List of generated file paths

**Example:**

```python
files = grow_forest_from_csv(
    "my_forest.csv",
    output_dir="models",
    resolution=8,  # Lower resolution for faster generation
    file_prefix="oak_"
)
```

#### `grow_combined_forest_from_csv(csv_file, output_file="forest_scene.obj", resolution=16, validate_format=True)`

Generate a single combined forest model.

**Note:** All trees will use the same species parameters (from the first tree in CSV). For mixed species, use `grow_forest_from_csv` instead.

**Parameters:**

- `csv_file`: Path to CSV file with tree data
- `output_file`: Path for the combined OBJ file (default: "forest_scene.obj")
- `resolution`: Model resolution (default: 16)
- `validate_format`: Whether to validate CSV format first (default: True)

**Returns:** Path to the generated file

### Utility Functions

#### `list_available_species()`

Get a list of all available species presets.

**Returns:** Sorted list of species names

**Example:**

```python
species = list_available_species()
print(f"Available species: {len(species)}")
for name in species[:5]:  # Show first 5
    print(f"  - {name}")
```

#### `validate_csv_format(csv_file)`

Validate CSV file format.

**Parameters:**

- `csv_file`: Path to CSV file

**Returns:** Tuple of (is_valid: bool, error_message: str)

**Example:**

```python
is_valid, message = validate_csv_format("my_trees.csv")
if not is_valid:
    print(f"CSV format error: {message}")
```

## Available Species

GrowPy includes 50+ scientifically-named species presets organized by family:

### Common Families

- **Fagaceae**: European oak, Red oak, White oak, Beech, Sweet chestnut
- **Pinaceae**: Scots pine, Austrian pine, Ponderosa pine, Fir, Grand fir
- **Betulaceae**: Silver birch, Paper birch, Downy birch, Alder, Hazel
- **Salicaceae**: Aspen, Grey poplar, Weeping willow

### Full Species List

Use `list_available_species()` to see all available species, including:

- Ginkgoaceae - Ginkgo biloba
- Juglandaceae - Walnut, Wingnut
- Lauraceae - Avocado
- Magnoliaceae - Magnolia
- Malvaceae - Linden
- Myrtaceae - Blue gum, Manna gum
- Nyssaceae - Black tupelo
- Oleaceae - Ash varieties
- Platanaceae - London plane tree
- Rosaceae - Hawthorn, Japanese cherry, Wild apple, Wild cherry
- And many more...

## Model Resolution

The `resolution` parameter controls model quality vs performance:

- **8**: Low resolution, fast generation, suitable for distant views
- **16**: Medium resolution (default), good balance
- **32**: High resolution, detailed models, slower generation
- **64+**: Very high resolution, for close-up views

## Output Files

Generated OBJ files include:

- Vertex data for tree geometry
- Normal vectors for lighting
- Standard OBJ format compatible with most 3D software
- Filenames: `{prefix}{number:03d}_{species_name}.obj`

Example: `tree_001_Fagaceae_European_oak.obj`

## Error Handling

GrowPy includes comprehensive error handling:

- **CSV Validation**: Checks for required columns and data types
- **Missing Species**: Warns if species preset not found, continues with default
- **File I/O**: Handles missing directories, permission errors
- **Model Generation**: Continues processing if individual trees fail

## Performance Tips

1. **Lower Resolution**: Use resolution=8 for testing or distant views
2. **Batch Processing**: Process large forests in smaller chunks
3. **Individual Models**: Use separate models for mixed species forests
4. **Age Limits**: Very old trees (50+ years) take longer to simulate

## Example Usage

### Basic Forest Generation

```python
from growpy import grow_forest_from_csv

# Create a forest from CSV data
files = grow_forest_from_csv(
    csv_file="data/my_forest.csv",
    output_dir="generated_trees",
    resolution=16
)

print(f"Generated {len(files)} tree models")
```

### Validation and Error Handling

```python
from growpy import validate_csv_format, grow_forest_from_csv

# Validate first
is_valid, message = validate_csv_format("my_data.csv")
if not is_valid:
    print(f"Error: {message}")
    exit(1)

# Generate with error handling
try:
    files = grow_forest_from_csv(
        "my_data.csv",
        output_dir="output",
        validate_format=False  # Already validated
    )
except Exception as e:
    print(f"Generation failed: {e}")
```

### Check Available Species

```python
from growpy import list_available_species

# List all species
all_species = list_available_species()
print(f"Total species available: {len(all_species)}")

# Filter by family
oak_species = [s for s in all_species if "Fagaceae" in s]
pine_species = [s for s in all_species if "Pinaceae" in s]

print(f"Oak family: {len(oak_species)} species")
print(f"Pine family: {len(pine_species)} species")
```

## Integration with 3D Software

The generated OBJ files can be imported into:

- **Blender**: File → Import → Wavefront (.obj)
- **Maya**: File → Import (set file type to OBJ)
- **3ds Max**: File → Import → Wavefront OBJ
- **Unity**: Drag OBJ files into Assets
- **Unreal Engine**: Import as Static Mesh

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure The Grove 2.2 core module is properly installed
2. **Missing Species**: Check species name spelling against `list_available_species()`
3. **Empty Models**: Verify tree age > 0 and species parameters are valid
4. **Performance**: Reduce resolution or process fewer trees at once

### Debug Mode

```python
# Enable detailed output
files = grow_forest_from_csv(
    "debug.csv", 
    resolution=8,  # Faster for testing
    validate_format=True
)
```

## License

GrowPy is part of The Grove 2.2 project. See the main project license for details.
