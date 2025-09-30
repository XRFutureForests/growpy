# GrowPy Pipeline Guide

Complete guide for using the GrowPy pipeline to generate realistic forest models from The Grove 2.2.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Pipeline Steps](#pipeline-steps)
- [CLI Reference](#cli-reference)
- [CSV Format](#csv-format)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Overview

GrowPy provides a complete pipeline for generating realistic tree and forest models:

1. **Asset Preparation** - Copy assets from The Grove 2.2
2. **Twig Export** - Convert twig .blend files to FBX with materials
3. **Growth Model Creation** - Generate height curves and prediction models
4. **Forest Generation** - Create forests from CSV data with light competition
5. **Tree Export** - Export individual species as FBX files

### Features

✅ **FBX Export** - Trees and twigs with mesh, skeleton, materials, and textures
✅ **Growth Models** - Pre-computed height-to-cycles prediction for accurate sizing
✅ **Smart Iteration** - Automatically stops when tree growth plateaus
✅ **Light Competition** - Multi-species forest simulation with realistic shading
✅ **Flexible Input** - Support for 2D (x,y) or 3D (x,y,z) positioning
✅ **Comprehensive CLI** - Full argparse support for all scripts

## Installation

### Requirements

- Python 3.8+
- The Grove 2.2 (installed at `src/the_grove_22`)
- Conda environment with required packages

### Setup Conda Environment

```bash
# Create conda environment
conda create -n growpy python=3.10

# Activate environment
conda activate growpy

# Install dependencies
conda install -c conda-forge bpy pandas numpy scikit-learn matplotlib tqdm
```

## Quick Start

### Option 1: Run Complete Pipeline

```bash
# Run the full pipeline (recommended for first-time setup)
python src/growpy/cli/run_pipeline.py
```

This will:
- Copy assets from The Grove 2.2
- Export all twigs to FBX
- Create growth models for all species

### Option 2: Run Steps Individually

```bash
# Step 1: Prepare assets
python src/growpy/cli/prepare_assets.py

# Step 2: Export twigs
python src/growpy/cli/export_twigs.py data/assets/twigs

# Step 3: Create growth models
python src/growpy/cli/create_growth_models.py
```

## Pipeline Steps

### Step 1: Prepare Assets

Copies species presets, textures, and twig files from The Grove 2.2 installation.

**Command:**
```bash
python src/growpy/cli/prepare_assets.py
```

**Options:**
```bash
--grove-dir PATH      Path to The Grove 2.2 directory
--assets-dir PATH     Path to assets output directory
```

**Example:**
```bash
# Use custom Grove directory
python src/growpy/cli/prepare_assets.py --grove-dir /path/to/grove
```

**Output:**
- `data/assets/presets/` - Species preset JSON files
- `data/assets/textures/` - Bark and leaf textures
- `data/assets/twigs/` - Twig .blend files

---

### Step 2: Export Twigs

Converts twig .blend files to FBX format with materials and textures.

**Command:**
```bash
python src/growpy/cli/export_twigs.py data/assets/twigs
```

**Options:**
```bash
PATH                  Path to twig directory or single .blend file
--twigs-dir PATH      Alternative way to specify twigs directory
```

**Examples:**
```bash
# Export all twigs in directory
python src/growpy/cli/export_twigs.py data/assets/twigs

# Export single blend file
python src/growpy/cli/export_twigs.py data/assets/twigs/EuropeanBeech/beech.blend
```

**Output:**
- Individual FBX files for each twig object
- Materials and textures copied to twig directories
- Skeleton data preserved in FBX

---

### Step 3: Create Growth Models

Generates height curves and prediction models for all species.

**Command:**
```bash
python src/growpy/cli/create_growth_models.py
```

**Key Options:**
```bash
--cycles INT                      Maximum growth cycles (default: 125)
--seeds INT                       Number of random seeds to test (default: 1)
--height-threshold FLOAT          Min height increase to count as growth (default: 0.05)
--max-cycles-without-growth INT   Stop after N cycles without growth (default: 3)
--timeout INT                     Timeout in seconds per seed (default: 300)
--species NAME                    Analyze single species
--parallel                        Use parallel processing (default: True)
--workers INT                     Number of parallel workers (default: 3)
```

**Examples:**
```bash
# Quick test with single species
python src/growpy/cli/create_growth_models.py --species "European beech" --cycles 50

# Full analysis with multiple seeds (more accurate)
python src/growpy/cli/create_growth_models.py --cycles 150 --seeds 3

# Custom early termination parameters
python src/growpy/cli/create_growth_models.py \
    --height-threshold 0.03 \
    --max-cycles-without-growth 5 \
    --timeout 600
```

**Smart Iteration:**
Growth simulation automatically stops when:
- Height increase per cycle falls below `--height-threshold`
- No significant growth for `--max-cycles-without-growth` consecutive cycles
- Simulation time exceeds `--timeout` seconds

This prevents wasting computation time on trees that have reached their growth plateau.

**Output:**
- `data/assets/growth_models/[Species]/`
  - `height_curve.json` - Height data per cycle
  - `dbh_curve.json` - Diameter at breast height data
  - `growth_model.pkl` - Trained prediction model
  - `metadata.json` - Analysis metadata
  - `growth_curves.png` - Visualization
  - `height_dbh_correlation.png` - Correlation plot

---

### Step 4: Generate Forest

Creates forest from CSV data with light competition and exports trees as FBX.

**Command:**
```bash
python src/growpy/cli/generate_forest.py forest_data.csv
```

**Options:**
```bash
CSV_FILE              Path to CSV file with forest data
--output-dir PATH     Directory to save FBX files
```

**Examples:**
```bash
# Generate with auto-detected CSV
python src/growpy/cli/generate_forest.py

# Specify CSV and output directory
python src/growpy/cli/generate_forest.py forest_data.csv --output-dir output/my_forest
```

**CSV Format:**
See [CSV Format](#csv-format) section below.

**Output:**
- Individual FBX files for each tree species in the forest
- Skeletons included in FBX files
- Materials and basic textures

---

### Step 5: Export Individual Trees

Exports all species as individual high-quality FBX files.

**Command:**
```bash
python src/growpy/cli/export_trees.py
```

**Options:**
```bash
--cycles INT          Number of growth cycles (default: 10)
--output-dir PATH     Directory to save FBX files
```

**Examples:**
```bash
# Export with default settings
python src/growpy/cli/export_trees.py

# Export with more growth cycles
python src/growpy/cli/export_trees.py --cycles 15 --output-dir output/mature_trees
```

**Output:**
- `output/trees_fbx/[Species].fbx` - One FBX per species
- Includes mesh, skeleton, and materials

---

## CLI Reference

### Main Pipeline Script

Run the complete pipeline with a single command:

```bash
python src/growpy/cli/run_pipeline.py
```

**Pipeline Control:**
```bash
--steps STEPS                Steps to run (default: prepare,twigs,models)
--skip-prepare              Skip asset preparation
--skip-twigs                Skip twig export
--skip-models               Skip growth model creation
--forest-csv PATH           Enable forest generation with CSV
--export-trees              Enable individual tree export
```

**Growth Model Parameters:**
```bash
--model-cycles INT          Max growth cycles (default: 125)
--model-seeds INT           Random seeds to test (default: 1)
--height-threshold FLOAT    Min height increase (default: 0.05)
--max-cycles-without-growth Stop after N cycles (default: 3)
--timeout INT               Timeout per seed in seconds (default: 300)
```

**Tree Export Parameters:**
```bash
--tree-cycles INT           Growth cycles for export (default: 10)
```

**Examples:**
```bash
# Run full pipeline including forest generation
python src/growpy/cli/run_pipeline.py --forest-csv data/forest.csv

# Skip preparation, run only models
python src/growpy/cli/run_pipeline.py --skip-prepare --steps models

# Customize growth model parameters
python src/growpy/cli/run_pipeline.py \
    --model-cycles 150 \
    --model-seeds 3 \
    --height-threshold 0.03 \
    --max-cycles-without-growth 5
```

---

## CSV Format

### Required Columns

Forest CSV files must contain these columns:

| Column | Type | Description |
|--------|------|-------------|
| `x` | float | X coordinate position |
| `y` | float | Y coordinate position |
| `species` | string | Tree species common name |
| `height` | float | Target tree height in meters |

### Optional Columns

| Column | Type | Description | Default |
|--------|------|-------------|---------|
| `z` | float | Z coordinate (elevation) | 0.0 |

### Example CSV

```csv
x,y,species,height
0,0,European beech,15.5
10,5,European oak,18.2
5,15,Silver fir,22.0
-5,10,European beech,12.3
```

### Species Names

Use common names from the species lookup table. Examples:
- European beech
- European oak
- Silver fir
- Douglas fir
- Norway spruce
- Scots pine
- Silver birch

To see all available species:
```bash
python -c "from growpy import get_config; print('\n'.join(get_config().get_available_species()))"
```

---

## Advanced Usage

### Parallel Processing

Growth model creation supports parallel processing:

```bash
# Use all CPU cores minus one
python src/growpy/cli/create_growth_models.py --parallel

# Specify number of workers
python src/growpy/cli/create_growth_models.py --workers 4

# Disable parallel processing
python src/growpy/cli/create_growth_models.py --no-parallel
```

### Custom Species Analysis

Analyze a single species in detail:

```bash
python src/growpy/cli/create_growth_models.py \
    --species "European beech" \
    --cycles 200 \
    --seeds 5 \
    --verbose
```

### Growth Model Customization

Fine-tune early termination behavior:

```bash
# Very sensitive (stops quickly)
python src/growpy/cli/create_growth_models.py \
    --height-threshold 0.01 \
    --max-cycles-without-growth 2

# Less sensitive (runs longer)
python src/growpy/cli/create_growth_models.py \
    --height-threshold 0.1 \
    --max-cycles-without-growth 10
```

### Programmatic Usage

Use GrowPy as a Python library:

```python
from growpy import (
    create_grove,
    export_tree_as_fbx,
    create_forest,
    simulate_forest_growth
)
from growpy.utils.dependencies import gc

# Create and export a single tree
grove = create_grove("European beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)
export_tree_as_fbx(grove, "beech.fbx", "European beech", include_skeleton=True)

# Create a forest from DataFrame
import pandas as pd
forest_data = pd.DataFrame({
    'x': [0, 10, 5],
    'y': [0, 5, 15],
    'species': ['European beech', 'European oak', 'Silver fir'],
    'height': [15.5, 18.2, 22.0]
})

forest = create_forest(forest_data)
simulate_forest_growth(forest, cycles=10)
```

---

## Troubleshooting

### Grove Not Found

**Problem:** `❌ Grove directory not found`

**Solution:**
```bash
# Specify Grove directory manually
python src/growpy/cli/prepare_assets.py --grove-dir /path/to/the_grove_22
```

### Blender/bpy Not Available

**Problem:** `❌ Export not available - bpy module required`

**Solution:**
```bash
# Install bpy in conda environment
conda install -c conda-forge bpy
```

### Species Not Found

**Problem:** `❌ Species 'beech' not found in lookup table`

**Solution:**
Use the full common name:
```python
# Wrong
species = "beech"

# Correct
species = "European beech"
```

List available species:
```bash
python -c "from growpy import get_config; print('\n'.join(get_config().get_available_species()))"
```

### Growth Model Timeout

**Problem:** Growth simulation takes too long

**Solution:**
Adjust timeout and early termination:
```bash
python src/growpy/cli/create_growth_models.py \
    --timeout 120 \
    --max-cycles-without-growth 3 \
    --height-threshold 0.05
```

### Missing CSV Columns

**Problem:** `❌ CSV missing required columns`

**Solution:**
Ensure CSV has all required columns: x, y, species, height

```csv
x,y,species,height
0,0,European beech,15.5
```

### Out of Memory

**Problem:** System runs out of memory during parallel processing

**Solution:**
Reduce number of workers:
```bash
python src/growpy/cli/create_growth_models.py --workers 2
```

Or disable parallel processing:
```bash
python src/growpy/cli/create_growth_models.py --no-parallel
```

---

## Output Files

### Asset Preparation
```
data/assets/
├── presets/           # Species preset JSON files
├── textures/          # Bark and leaf textures
└── twigs/            # Twig .blend and FBX files
```

### Growth Models
```
data/assets/growth_models/
└── [Species_Name]/
    ├── height_curve.json
    ├── dbh_curve.json
    ├── growth_model.pkl
    ├── metadata.json
    ├── growth_curves.png
    └── height_dbh_correlation.png
```

### Forest Export
```
output/forest_fbx/
├── European_beech_tree.fbx
├── European_oak_tree.fbx
└── Silver_fir_tree.fbx
```

### Individual Trees
```
output/trees_fbx/
├── European_beech.fbx
├── European_oak.fbx
└── Silver_fir.fbx
```

---

## Performance Tips

1. **Use Parallel Processing**: Speeds up growth model creation significantly
   ```bash
   python src/growpy/cli/create_growth_models.py --workers 4
   ```

2. **Adjust Timeout**: Reduce timeout for faster iterations
   ```bash
   python src/growpy/cli/create_growth_models.py --timeout 60
   ```

3. **Start Small**: Test with one species before running all
   ```bash
   python src/growpy/cli/create_growth_models.py --species "European beech"
   ```

4. **Use Early Termination**: Adjust sensitivity to stop sooner
   ```bash
   python src/growpy/cli/create_growth_models.py \
       --height-threshold 0.1 \
       --max-cycles-without-growth 2
   ```

---

## Next Steps

After completing the pipeline:

1. **Import FBX Files** into Blender, Unreal Engine, Unity, or other 3D software
2. **Adjust Materials** using the included textures
3. **Animate Skeletons** for wind effects or growth animations
4. **Generate Variations** by running with different random seeds
5. **Create Larger Forests** by expanding your CSV file

---

## Support

For issues, questions, or contributions:
- Check the troubleshooting section above
- Review script help: `python script.py --help`
- Check The Grove 2.2 documentation for advanced features

---

## License

This project integrates with The Grove 2.2. Please ensure you have a valid license for The Grove 2.2 before using GrowPy.