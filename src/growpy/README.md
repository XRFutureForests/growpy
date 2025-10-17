# GrowPy - Grove API Integration for Unreal Engine 5

> **📖 Complete Documentation: [`docs/growpy/`](../../docs/growpy/)**
>
> **[User Guide](../../docs/growpy/USER_GUIDE.md)** | **[Module Overview](../../docs/growpy/MODULE_OVERVIEW.md)** | **[Unreal Engine Nanite](../../docs/growpy/UNREAL_ENGINE_NANITE.md)**

Clean Grove API integration for forest creation and export, optimized for Unreal Engine 5 Nanite foliage with simplified single high-quality output and USD export.

## Key Features

- **Single High-Quality Output**: No complex multi-LOD system (Nanite handles LOD)
- **USD/USDA Export**: Universal Scene Description format for Unreal Engine 5
- **UE5 Nanite Optimized**: Full geometry exports ready for Nanite virtualized geometry
- **Skeleton Support**: Optional armature export for wind/physics animation
- **Simplified Twig Processing**: Direct Blender export using bpy module
- **Clean Architecture**: Straightforward export workflow

## Structure

```
growpy/
├── config.py          # Configuration management
├── forest.py          # Forest-level operations
├── grove.py           # Grove-level operations
├── tree.py            # Tree model functions
├── export.py          # USD export functionality
├── common.py          # Shared utilities
└── utils/
    ├── export_trees.py      # Export trees as USD
    ├── export_twigs.py      # Export twigs from blend files
    ├── generate_forest.py   # Forest generation with USD
    ├── prepare_assets.py    # Asset preparation
    └── create_growth_models.py # Growth model creation
```

## Quick Start

### Export Trees for Unreal Engine 5 Nanite

#### USD Export (For Nanite Assemblies in UE 5.7+)

```python
from growpy import create_grove, export_tree_as_usd
from pathlib import Path

# Create grove
grove = create_grove("Beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export as USD for Nanite workflows
export_tree_as_usd(
    grove=grove,
    output_path=Path("output/Beech_nanite.usda"),
    species_name="Beech",
    include_skeleton=True,
    export_skeleton_separately=False
)
```

**📖 See [Unreal Engine Nanite Guide](../../docs/growpy/UNREAL_ENGINE_NANITE.md) for complete import and setup instructions.**

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
python src/growpy/cli/generate_forest.py forest_data.csv --formats usda
```

## Requirements

- **bpy module**: For Blender operations and FBX/USD export

  ```bash
  conda install -c conda-forge bpy
  ```

- **Grove API**: The Grove 2.2 Python bindings
- **pandas**: For CSV forest data processing
- **Unreal Engine 5.0+**: For Nanite foliage (5.7+ for Nanite Assemblies)

## Export Format

USD/USDA format provides:

- **UE5 Compatibility**: Excellent support (5.7+)
- **Nanite Support**: Full Nanite Assembly support
- **Skeleton/Armature**: Complete skeleton export
- **Materials**: Advanced material support
- **File Size**: Efficient (USDA text format)

## Unreal Engine 5 Integration

GrowPy exports are optimized for UE5 Nanite foliage:

1. **Full Geometry**: No alpha-masked cards—Nanite handles detail efficiently
2. **Opaque Materials**: Faster than masked materials with Nanite
3. **Preserve Area**: Enabled to prevent thinning on foliage
4. **Tangent Space Normals**: Correct lighting in Unreal Engine
5. **Skeleton Support**: Wind animation using Control Rigs or Niagara

### Workflow Summary

1. **Export** trees using `export_tree_as_usd()`
2. **Import** into UE5 Content Browser
3. **Enable Nanite** in Static Mesh settings
4. **Create Foliage Type** for painting
5. **Paint forests** using Foliage Mode
6. **Add wind animation** using skeleton/armature

**📖 Complete workflow: [Unreal Engine Nanite Guide](../../docs/growpy/UNREAL_ENGINE_NANITE.md)**

## Usage Examples

See the CLI scripts for complete workflows:

- `generate_forest.py`: Full forest generation pipeline with USD output
- `convert_twigs.py`: Process all twig blend files to USD
- `prepare_assets.py`: Copy assets from Grove 2.2
- `create_growth_models.py`: Generate species growth models
