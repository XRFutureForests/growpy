# The Grove - Simplified Tree Generation

Clean, simplified tree generation system using The Grove 2.2 with FBX export workflow.

## Project Structure

```
the-grove/
├── src/growpy/                 # Core Python package
│   ├── __init__.py            # Main package interface
│   ├── config.py              # Configuration management
│   ├── forest.py              # Forest-level operations
│   ├── grove.py               # Grove-level operations
│   ├── tree.py                # Tree model functions
│   ├── export.py              # FBX export functionality
│   ├── common.py              # Shared utilities
│   ├── README.md              # Package documentation
│   └── utils/                 # Utility scripts
│       ├── export_trees.py    # Export all species as FBX
│       ├── export_twigs.py    # Export twigs from blend files
│       ├── generate_forest.py # Generate forest from CSV
│       ├── prepare_assets.py  # Asset preparation
│       └── create_growth_models.py # Growth model creation
├── docs/                      # Documentation
├── CLAUDE.md                  # Project instructions
└── README.md                  # This file
```

## Core Philosophy

**Simplified & Clean**: Removed complex USD workflows, multiple LOD variants, and positioning hacks in favor of straightforward FBX export using Grove's native mesh + skeleton output.

**Four-Layer Hierarchy**: Forest → Grove → Tree → Twig structure maintained for logical organization.

**Single High-Quality Output**: One high-resolution model per species instead of multiple LOD variants.

## Quick Usage

### Export All Tree Species
```bash
python src/growpy/utils/export_trees.py
```

### Export Twigs from Blend Files
```bash
python src/growpy/utils/export_twigs.py
```

### Generate Forest from CSV
```bash
python src/growpy/utils/generate_forest.py forest_data.csv
```

### Programmatic Usage
```python
from growpy import create_grove, export_tree_as_fbx

# Create and export a single tree
grove = create_grove("oak")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)
export_tree_as_fbx(grove, Path("oak.fbx"), "oak", include_skeleton=True)
```

## Requirements

- **The Grove 2.2** Python API
- **bpy module**: `conda install -c conda-forge bpy`
- **pandas**: For CSV forest data
- **tqdm**: Progress bars

## What's Different

### ✅ Added
- Clean FBX export with mesh + skeleton + textures
- Simplified utility scripts with clear names
- Single high-quality output per species
- Direct Blender integration for twigs

### ❌ Removed
- Complex USD/USDA export system
- Multiple LOD variants (LOD0, LOD1, LOD2)
- Positioning and texture workarounds
- Try/except approaches everywhere
- Numbered script prefixes (00_, 01_, etc.)

## Output

All exports generate FBX files compatible with:
- **Blender** (native)
- **Unreal Engine**
- **Unity**
- **Maya/3ds Max**
- Other FBX-compatible applications

Trees include mesh geometry, skeleton/armature, and basic materials. Twigs are exported as individual FBX assets ready for instancing.

## Migration Notes

This is a simplified version of the original complex system. The old USD-based workflow has been replaced with a cleaner FBX approach that eliminates positioning issues and texture problems while maintaining the core Forest/Grove/Tree/Twig hierarchy.