# GrowPy - Simplified Grove API Integration

Clean Grove API integration for forest creation and FBX export, maintaining the Forest/Grove/Tree/Twig hierarchy with simplified single high-quality output and clean FBX export workflow.

## Key Features

- **Single High-Quality Output**: No complex multi-LOD system
- **FBX Export**: Trees with mesh + skeleton + textures as FBX files
- **Simplified Twig Processing**: Direct Blender export using bpy module
- **Clean Architecture**: Removed positioning and texture workarounds

## Structure

```
growpy/
├── config.py          # Configuration management
├── forest.py          # Forest-level operations
├── grove.py           # Grove-level operations
├── tree.py            # Tree model functions
├── export.py          # FBX export functionality
├── common.py          # Shared utilities
└── utils/
    ├── export_trees.py      # Export trees as FBX
    ├── export_twigs.py      # Export twigs from blend files
    ├── generate_forest.py   # Forest generation with FBX
    ├── prepare_assets.py    # Asset preparation
    └── create_growth_models.py # Growth model creation
```

## Quick Start

### Export Individual Trees

```python
from growpy import create_grove, export_tree_as_fbx
from pathlib import Path

# Create grove for specific species
grove = create_grove("oak")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export as FBX with skeleton
export_tree_as_fbx(grove, Path("oak_tree.fbx"), "oak", include_skeleton=True)
```

### Export Twigs from Blend Files

```python
from growpy import export_twigs_from_blend
from pathlib import Path

# Export all twigs from a blend file
blend_file = Path("assets/twigs/oak_twigs.blend")
output_dir = Path("output/twigs/oak")
exported_files = export_twigs_from_blend(blend_file, output_dir)
```

### Generate Forest from CSV

```bash
python src/growpy/utils/generate_forest_fbx.py forest_data.csv
```

## Requirements

- **bpy module**: For Blender operations and FBX export
  ```bash
  conda install -c conda-forge bpy
  ```
- **Grove API**: The Grove 2.2 Python bindings
- **pandas**: For CSV forest data processing

## What Changed

### Removed Complexity
- ❌ Multiple LOD levels (LOD0, LOD1, LOD2)
- ❌ Complex USD/USDA export with positioning issues
- ❌ Try/except approaches everywhere for USD handling
- ❌ Complex twig placement with face attributes and USD materials

### Added Simplicity
- ✅ Single high-quality mesh export
- ✅ Direct FBX export with mesh + skeleton + textures
- ✅ Straightforward Blender-based twig processing
- ✅ Clean error handling without nested try/catch blocks

## Migration from Old System

Old USD-based scripts have been deprecated (`.deprecated` extension). The new FBX-based workflow provides:

1. **Better Compatibility**: FBX works natively in Blender, Unreal, Unity
2. **Fewer Dependencies**: No complex USD Python bindings required
3. **Cleaner Code**: Removed positioning hacks and texture workarounds
4. **Single Source of Truth**: Grove API provides mesh and skeleton directly

## Usage Examples

See the utils scripts for complete workflows:
- `export_trees_fbx.py`: Export all species as individual tree FBX files
- `export_twigs_fbx.py`: Process all twig blend files to FBX
- `generate_forest_fbx.py`: Full forest generation pipeline with FBX output