# Generating Species Library

This guide shows how to export all configured tree species as FBX and/or USD files for use in Unreal Engine or other applications.

## Overview

The `generate_species_library.py` script exports template trees for all species configured in your GrowPy configuration. It supports:

- **Multiple formats**: FBX, USD (binary), USDA (text)
- **Twig instances**: Automatic twig placement as USD PointInstancer prims
- **Quality settings**: Adjustable resolution and growth parameters
- **Native USD export**: Uses Grove's native USD export preserving all attributes

## Basic Usage

### Export as USDA (Default)

```bash
python src/growpy/cli/generate_species_library.py
```

This creates `data/output/species_library/USD/` with USDA files for each species.

### Export as Both FBX and USDA

```bash
python src/growpy/cli/generate_species_library.py --formats fbx usda
```

Creates two directories:
- `data/output/species_library/FBX/` - FBX files with skeletal meshes
- `data/output/species_library/USD/` - USDA files with all Grove attributes

### Export with Twigs (USD only)

```bash
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs
```

Each USDA file will include:
- Base tree mesh (from Grove's native export)
- Twig instances as PointInstancer prims
- Nanite attributes for Unreal Engine 5.7+

## Command-Line Options

### `--formats`
Export formats (can specify multiple)
- Choices: `fbx`, `usd`, `usda`
- Default: `usda`

**Examples:**
```bash
# USDA only (text format, readable)
--formats usda

# FBX only
--formats fbx

# Both FBX and USDA
--formats fbx usda

# USD binary (smaller file size)
--formats usd
```

### `--include-twigs`
Include twig instances in USD exports (PointInstancer prims)
- Only works with USD formats
- Automatically finds matching twig USD files
- Uses memory-efficient PointInstancer

**Example:**
```bash
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs
```

### `--resolution`
Branch resolution (vertices around circumference)
- Range: 4-32
- Default: 24
- Higher = more detailed (but larger files)

**Quality presets:**
- Low: `--resolution 12`
- Medium: `--resolution 16` or `24` (default)
- High: `--resolution 32`

**Example:**
```bash
python src/growpy/cli/generate_species_library.py --resolution 32 --formats usda
```

### `--flushes`
Number of growth cycles to simulate
- Default: 10
- Higher = older, larger trees

**Example:**
```bash
python src/growpy/cli/generate_species_library.py --flushes 15
```

### `--output-dir`
Output directory
- Default: `data/output/species_library`

**Example:**
```bash
python src/growpy/cli/generate_species_library.py --output-dir exports/trees
```

## Complete Examples

### Production Export (FBX + USDA with Twigs)

```bash
python src/growpy/cli/generate_species_library.py \
  --formats fbx usda \
  --include-twigs \
  --resolution 24 \
  --flushes 10 \
  --output-dir data/output/production_library
```

Output structure:
```
data/output/production_library/
├── FBX/
│   ├── European_Beech.fbx
│   ├── Scots_Pine.fbx
│   └── ...
└── USD/
    ├── European_Beech.usda (with twigs)
    ├── European_Beech_tree_only.usda (base tree)
    ├── Scots_Pine.usda (with twigs)
    └── ...
```

### High Quality Export

```bash
python src/growpy/cli/generate_species_library.py \
  --formats fbx usda \
  --resolution 32 \
  --flushes 12 \
  --output-dir data/output/high_quality
```

### Quick Low-Res Preview

```bash
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --resolution 12 \
  --flushes 8 \
  --output-dir data/output/preview
```

## Output Structure

### With `--formats fbx usda`

```
data/output/species_library/
├── FBX/
│   ├── European_Beech.fbx
│   ├── Scots_Pine.fbx
│   ├── Common_Linden.fbx
│   └── ...
└── USD/
    ├── European_Beech.usda
    ├── Scots_Pine.usda
    ├── Common_Linden.usda
    └── ...
```

### With `--include-twigs`

```
data/output/species_library/
└── USD/
    ├── European_Beech.usda                  # Complete tree with twigs
    ├── European_Beech_tree_only.usda        # Base tree only (reference)
    ├── Scots_Pine.usda
    ├── Scots_Pine_tree_only.usda
    └── ...
```

## Twig Requirements

For `--include-twigs` to work, you need:

1. **Twig USD files** converted from FBX:
   ```bash
   python src/growpy/cli/convert_twigs.py data/assets/twigs/ --formats usda
   ```

2. **Species configuration** mapping species to twig types in your GrowPy config

The script automatically:
- Finds matching twig USD files for each species
- Maps twig types (apical/lateral/upward/dead) to Grove attributes
- Adds twigs as PointInstancer prims with proper orientation

## Performance Considerations

### Resolution vs File Size

| Resolution | Quality | Verts/Branch | File Size (approx) |
|-----------|---------|--------------|-------------------|
| 12 | Low | 12 | Small (1-2 MB) |
| 16 | Medium | 16 | Medium (2-4 MB) |
| 24 | High | 24 | Large (4-8 MB) |
| 32 | Very High | 32 | Very Large (8-15 MB) |

### Export Time

Approximate time per species (on modern hardware):
- FBX only: ~10-15 seconds
- USD only: ~5-8 seconds
- USD with twigs: ~8-12 seconds
- Both formats: ~15-20 seconds

For 20 species with both formats: ~5-7 minutes total

## Troubleshooting

### No FBX Export

**Error:** `FBX export not available - bpy module required`

**Solution:** Make sure you're running with Blender's Python:
```bash
# Option 1: Use Blender's Python directly
/path/to/blender --background --python src/growpy/cli/generate_species_library.py -- --formats fbx usda

# Option 2: Install bpy in your Python environment (if available)
pip install bpy
```

### No Twig Files Found

**Warning:** `No twig USD files found for {species}`

**Solution:** Convert twig FBX files to USD first:
```bash
python src/growpy/cli/convert_twigs.py data/assets/twigs/ --formats usda
```

### Import Error

**Error:** `ImportError: Grove core (the_grove_22_core) not available`

**Solution:** Make sure Grove core is installed and accessible:
```python
python -c "import the_grove_22_core as gc; print(gc)"
```

### Species Not Found

**Error:** `No species found in configuration`

**Solution:** Check your GrowPy configuration has species defined:
```python
from growpy import get_config
config = get_config()
species_list = config.get_all_species()
print(f"Found {len(species_list)} species")
print(species_list)
```

## Integration with Unreal Engine

### Importing FBX Files

1. Import FBX into Unreal Content Browser
2. Enable Nanite on import (UE 5.7+)
3. Check "Import as Skeletal Mesh" for animation support
4. Materials will be imported automatically

### Importing USD Files

1. Enable USD Importer plugin in Unreal
2. Import USDA files
3. Use "Keep Instances" for twig instances
4. Verify Nanite is enabled on all meshes
5. Check `unrealNanitePreserveArea` is set on foliage

### Using in PCG/Foliage

The exported trees are ready for:
- Procedural Content Generation (PCG)
- Foliage painting tools
- Mass instancing
- Landscape scatter

See the Unreal Engine documentation for more details on USD workflows.

## See Also

- [USD Export with Twigs](../growpy/USD_EXPORT_WITH_TWIGS.md) - Technical details
- [Twig Conversion](../../src/growpy/cli/convert_twigs.py) - Converting twig FBX to USD
- [Export for Unreal](../../src/growpy/cli/export_for_unreal.py) - Forest export workflow
