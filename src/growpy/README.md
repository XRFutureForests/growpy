# GrowPy - Grove API Integration for Unreal Engine 5

> **📖 Complete Documentation: [`docs/`](../../docs/)**
>
> **[Functional Description](../../docs/growpy-functional-description.md)** | **[CLI Reference](../../docs/cli-reference.md)** | **[Grove Preset Reference](../../docs/grove-preset-reference.md)**

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
├── __init__.py        # Package entry point and public API
├── growpy.toml        # Central configuration (all CLI defaults)
├── config/            # Configuration management, quality presets, species lookup
├── core/              # Forest/Grove/Tree/Skeleton simulation
├── io/                # USD export, OBJ export, wind data, PVE mapping
├── cli/               # Pipeline CLI scripts
│   ├── prepare_assets.py         # Step 1: Copy Grove 2.3 assets
│   ├── convert_twigs.py          # Step 2: Convert twigs to USD
│   ├── create_growth_models.py   # Step 3: Generate height models
│   └── generate_forest.py        # Step 4: Forest from CSV (includes OBJ export)
├── utils/             # Analysis, profiling, plotting
└── tests/             # Test suite (pytest, 209 tests)
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
    species_name="Beech"
)
```

**📖 See the [root README](../../README.md#import-to-unreal-engine) for complete Unreal Engine import and setup instructions.**

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

All CLI scripts read defaults from `growpy.toml`. Run without arguments:

```bash
python src/growpy/cli/generate_forest.py
```

## Requirements

- **bpy module**: For Blender operations and FBX/USD export

  ```bash
  conda install -c conda-forge bpy
  ```

- **Grove API**: The Grove 2.3 Python bindings
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

**📖 Complete workflow: see the [root README](../../README.md#import-to-unreal-engine).**

## Usage Examples

See the CLI scripts for complete workflows:

- `cli/prepare_assets.py`: Copy assets from Grove 2.3
- `cli/convert_twigs.py`: Process all twig blend files to USD
- `cli/create_growth_models.py`: Generate species growth models
- `cli/generate_forest.py`: Full forest generation pipeline with USD output
- `io/obj_export.py`: OBJ/MTL export for Helios++ (called from generate_forest.py)
