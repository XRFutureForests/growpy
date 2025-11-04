# CLI Reference Guide

Quick reference for all GrowPy command-line tools and their flags.

## Overview

The GrowPy pipeline consists of four main scripts:

1. `prepare_assets.py` - Copy assets from The Grove 2.2
2. `convert_twigs.py` - Convert .blend twigs to FBX/USD
3. `create_growth_models.py` - Generate height prediction models
4. `generate_forest.py` - Multi-species forest simulation and export

## Complete Pipeline

```bash
# Run all preparation steps (1-3)
python src/growpy/cli/run_pipeline.py
```

## 1. prepare_assets.py

Copy tree assets from The Grove 2.2 installation to project data directory.

```bash
python src/growpy/cli/prepare_assets.py
```

**No flags** - Uses paths from `GrowPyConfig`

## 2. convert_twigs.py

Convert twig .blend files to FBX/USD formats with texture embedding.

```bash
python src/growpy/cli/convert_twigs.py <path> [options]
```

### Arguments

- `path` - Directory containing .blend files or single .blend file

### Options

- `--output-dir PATH` - Output directory (default: same as input)
- `--formats {fbx,usd,usda}` - Export formats (default: fbx usda)

### Examples

```bash
# Export all twigs to FBX and USDA
python src/growpy/cli/convert_twigs.py data/assets/twigs

# Export only FBX
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats fbx

# Custom output directory
python src/growpy/cli/convert_twigs.py data/assets/twigs --output-dir data/output/twigs

# Convert single twig file
python src/growpy/cli/convert_twigs.py data/assets/twigs/AppleTreeTwig/AppleTreeTwig_A.blend
```

## 3. create_growth_models.py

Generate growth models for predicting tree heights from growth cycles.

```bash
python src/growpy/cli/create_growth_models.py
```

**No flags** - Uses species from `tree_asset_lookup.csv`

## 4. generate_forest.py

Generate multi-species forest from CSV data with export.

```bash
python src/growpy/cli/generate_forest.py <csv_file> [options]
```

### Arguments

- `csv_file` - CSV with columns: x, y, species, height (z optional)

### Core Options

- `--output-dir PATH` - Output directory (default: data/output/forest)
- `--formats {fbx,usd,usda}` - Export formats (default: fbx)

### Quality Settings

- `--quality {ultra,high,medium,low,performance}` - Quality preset (default: ultra)
  - **ultra**: 32 vertices, maximum detail, hero trees
  - **high**: 24 vertices, high detail, close-up trees
  - **medium**: 16 vertices, balanced, mid-distance trees
  - **low**: 12 vertices, reduced detail, background trees
  - **performance**: 8 vertices, minimal detail, distant trees
- `--resolution 4-32` - Override vertices around branch circumference

### Growth Controls

- `--growth-cycle-limit INT` - Maximum growth cycles per tree (default: 10)
- `--height-scale FLOAT` - Scale factor for tree heights (default: 1.0)

### Advanced Options

- `--place-twigs` - Place twig instances on trees (requires twigs directory)
- `--twigs-dir PATH` - Directory containing twig files
- `--create-nanite-assembly` - Create Nanite Assembly USD for UE5.7+ (default: True)
- `--no-nanite-assembly` - Skip Nanite Assembly creation

### Examples

```bash
# Basic usage with default ultra quality
python src/growpy/cli/generate_forest.py forest_data.csv

# High quality, limit growth cycles to 15
python src/growpy/cli/generate_forest.py forest_data.csv --quality high --growth-cycle-limit 15

# Medium quality, export USD only
python src/growpy/cli/generate_forest.py forest_data.csv --quality medium --formats usda

# Custom resolution with performance preset
python src/growpy/cli/generate_forest.py forest_data.csv --quality performance --resolution 12

# Full control with all options
python src/growpy/cli/generate_forest.py forest_data.csv \
  --output-dir data/output/my_forest \
  --quality ultra \
  --growth-cycle-limit 20 \
  --height-scale 0.8 \
  --formats fbx usda \
  --create-nanite-assembly

# Scale tree heights down by 50%
python src/growpy/cli/generate_forest.py forest_data.csv --height-scale 0.5
```

## Quality Presets Reference

| Preset | Resolution | Use Case | Detail Level | Cutoff Thickness |
|--------|-----------|----------|--------------|------------------|
| ultra | 32 | Hero trees, close-up | Maximum | 0.001m |
| high | 24 | Close-up trees | High | 0.002m |
| medium | 16 | Mid-distance | Balanced | 0.005m |
| low | 12 | Background | Reduced | 0.01m |
| performance | 8 | Distant trees | Minimal | 0.02m |

## CSV Format Requirements

### Required Columns

- `x` - X coordinate (meters)
- `y` - Y coordinate (meters)
- `species` - Tree species name (must match asset lookup)
- `height` - Target tree height (meters)

### Optional Columns

- `z` - Z coordinate (defaults to 0)
- `growth_cycles` - Explicit growth cycles (calculated if missing)
- `delay` - Growth delay offset (calculated if missing)

### Example CSV

```csv
x,y,species,height
0.0,0.0,Quaking Aspen,15.5
10.5,5.2,Quaking Aspen,18.2
20.0,0.0,European Beech,22.0
```

## Common Workflows

### Quick Test Export

```bash
# Single species, low quality for testing
python src/growpy/cli/generate_forest.py test.csv --quality low --growth-cycle-limit 5
```

### Production Export

```bash
# Multi-species forest with ultra quality
python src/growpy/cli/generate_forest.py forest_inventory.csv \
  --quality ultra \
  --growth-cycle-limit 20 \
  --formats fbx usda \
  --output-dir data/output/production
```

### Unreal Engine 5 Export

```bash
# USD with Nanite Assembly for UE5.7+
python src/growpy/cli/generate_forest.py forest.csv \
  --formats usda \
  --quality high \
  --create-nanite-assembly \
  --output-dir data/output/ue5_forest
```

### Performance Testing

```bash
# Minimal quality for large forests
python src/growpy/cli/generate_forest.py large_forest.csv \
  --quality performance \
  --growth-cycle-limit 5 \
  --formats fbx
```

## Troubleshooting

### "ERROR: CSV missing required columns"

Ensure your CSV has: x, y, species, height

### "No growth model found for species"

Run `python src/growpy/cli/create_growth_models.py` first

### "Twigs directory not found"

Ensure twigs are exported: `python src/growpy/cli/export_twigs.py data/assets/twigs`

### Growth cycles too high (performance issues)

Use `--growth-cycle-limit` to cap maximum cycles:

```bash
python src/growpy/cli/generate_forest.py forest.csv --growth-cycle-limit 10
```

## Environment Setup

Always activate the conda environment first:

```bash
conda activate the-grove
```

## Related Documentation

- [Getting Started Guide](../GETTING_STARTED.md)
- [GrowPy Package Documentation](../growpy/README.md)
- [The Grove Integration Guide](../the_grove/README.md)
