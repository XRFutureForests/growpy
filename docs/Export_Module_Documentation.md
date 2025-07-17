# Grove Export Module Documentation

The `export_forest` module provides a modular approach to exporting Grove forest simulation data in various formats. This module separates the concerns of different export types and provides flexible format options.

## Overview

The module supports three main types of exports:

1. **Grove JSON Export**: Simulation state data for importing into Blender
2. **Grove Model Export**: Combined 3D models (one model per grove/species) with LOD levels
3. **Individual Tree Export**: Separate 3D models for each tree

## Supported Formats

- **JSON**: Grove simulation state for Blender import
- **OBJ**: Wavefront OBJ 3D model format
- **USD**: Universal Scene Description format

## Functions

### `export_grove_json(forest, output_dir)`

Exports grove simulation data as JSON files for Blender import.

**Parameters:**

- `forest`: List of (grove, species_name, tree_count) tuples
- `output_dir`: Directory to save JSON files

**Returns:** List of paths to exported JSON files

**Example:**

```python
from export_forest import export_grove_json

json_files = export_grove_json(forest, Path("output/json"))
```

### `export_grove_models(forest, output_dir, lod_configs=None, model_format=ModelFormat.OBJ)`

Exports grove models (one model per grove, all trees combined) with multiple LOD levels.

**Parameters:**

- `forest`: List of (grove, species_name, tree_count) tuples
- `output_dir`: Directory to save model files
- `lod_configs`: Dictionary of LOD configurations (optional)
- `model_format`: Format to export models (OBJ or USD)

**Returns:** List of paths to exported model files

**Example:**

```python
from export_forest import export_grove_models, ModelFormat

# Export as OBJ
obj_files = export_grove_models(forest, Path("output/obj"), model_format=ModelFormat.OBJ)

# Export as USD
usd_files = export_grove_models(forest, Path("output/usd"), model_format=ModelFormat.USD)
```

### `export_individual_tree_models(forest, output_dir, build_options=None, model_format=ModelFormat.OBJ)`

Exports individual tree models (one model per tree).

**Parameters:**

- `forest`: List of (grove, species_name, tree_count) tuples
- `output_dir`: Directory to save model files
- `build_options`: Build options for model generation (optional)
- `model_format`: Format to export models (OBJ or USD)

**Returns:** List of paths to exported model files

**Example:**

```python
from export_forest import export_individual_tree_models, ModelFormat

individual_files = export_individual_tree_models(
    forest, 
    Path("output/individual"), 
    model_format=ModelFormat.OBJ
)
```

### `export_complete_forest(forest, config, include_json=True, include_grove_models=True, include_individual_trees=False, model_format=ModelFormat.OBJ)`

Exports complete forest data including JSON and 3D models with flexible options.

**Parameters:**

- `forest`: List of (grove, species_name, tree_count) tuples
- `config`: Configuration object with output directory and LOD settings
- `include_json`: Whether to export grove JSON files
- `include_grove_models`: Whether to export grove models (one per species)
- `include_individual_trees`: Whether to export individual tree models
- `model_format`: Format for 3D models (OBJ or USD)

**Returns:** Dictionary with lists of exported file paths by type

**Example:**

```python
from export_forest import export_complete_forest, ModelFormat

exported_files = export_complete_forest(
    forest=forest,
    config=config,
    include_json=True,
    include_grove_models=True,
    include_individual_trees=True,
    model_format=ModelFormat.USD
)

print(f"JSON files: {len(exported_files['json'])}")
print(f"Grove models: {len(exported_files['grove_models'])}")
print(f"Individual trees: {len(exported_files['individual_trees'])}")
```

## Model Formats

### ModelFormat Enum

```python
from export_forest import ModelFormat

# Available formats
ModelFormat.OBJ  # Wavefront OBJ format
ModelFormat.USD  # Universal Scene Description format
```

### Format Characteristics

- **OBJ**: Widely supported, simple format, good for game engines and 3D software
- **USD**: Pixar's format, excellent for complex scenes, supports advanced features

## LOD (Level of Detail) Configuration

The module automatically uses the default LOD configurations from `GrowPyConfig.get_lod_configs()`:

| Level | Resolution | Reduce | Age Cut | Thick Cut | Blend | End Cap |
|-------|------------|--------|---------|-----------|-------|---------|
| LOD0_Ultra | 24 | 0.70 | 0 | 0.00 | True | True |
| LOD1_High | 16 | 0.80 | 0 | 0.00 | True | True |
| LOD2_Medium | 12 | 0.85 | 1 | 0.01 | True | False |
| LOD3_Low | 8 | 0.90 | 2 | 0.02 | False | False |
| LOD4_VeryLow | 6 | 0.95 | 3 | 0.03 | False | False |
| LOD5_Minimal | 4 | 0.98 | 4 | 0.05 | False | False |

## Workflow Integration

### Basic Workflow

```python
from pathlib import Path
from config import GrowPyConfig
from grow_forest import add_trees, grow_forest
from export_forest import export_complete_forest, ModelFormat

# 1. Setup
config = GrowPyConfig()
config.output_dir = Path("output")
csv_path = Path("data/forest.csv")

# 2. Create and grow forest
forest = []
forest = add_trees(forest, csv_path, config)
grow_forest(forest, config)

# 3. Export everything
export_complete_forest(
    forest=forest,
    config=config,
    include_json=True,
    include_grove_models=True,
    include_individual_trees=False,
    model_format=ModelFormat.OBJ
)
```

### Blender Integration Workflow

```python
# Export grove JSON for Blender animation
from export_forest import export_grove_json

json_files = export_grove_json(forest, Path("output/blender"))

# Then in Blender, use import_to_blender.py:
# bpy.ops.script.python_file(filepath="path/to/import_to_blender.py")
```

### Game Engine Workflow

```python
# Export LOD models for game engines
from export_forest import export_grove_models, ModelFormat

lod_models = export_grove_models(
    forest, 
    Path("output/game_assets"), 
    model_format=ModelFormat.OBJ
)
```

## File Naming Convention

- **Grove JSON**: `{species_name}_grove.json`
- **Grove Models**: `{species_name}_{lod_level}.{format}`
- **Individual Trees**: `{species_name}_tree_{index:03d}.{format}`

Examples:

- `Fagaceae___Beech_grove.json`
- `Fagaceae___Beech_LOD0_Ultra.obj`
- `Fagaceae___Beech_tree_001.obj`

## Performance Considerations

- **Grove Models**: Faster to export, fewer files, good for most use cases
- **Individual Trees**: Slower to export, many files, useful for detailed placement control
- **USD Format**: May take longer to export than OBJ but provides richer metadata
- **LOD Levels**: Use appropriate LOD for your target platform (LOD5_Minimal for mobile, LOD0_Ultra for high-end)

## Error Handling

The module includes error handling for:

- Invalid model formats
- File I/O errors
- Missing directories (automatically created)

## Migration from Old System

If you're migrating from the old `grow_forest.py` export functions:

**Old:**

```python
export_grove_data_only(forest, config)
export_forest(forest, config)
```

**New:**

```python
export_complete_forest(
    forest=forest,
    config=config,
    include_json=True,
    include_grove_models=True,
    model_format=ModelFormat.OBJ
)
```
