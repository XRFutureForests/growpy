# Getting Started with The Grove

Quick guide to generate trees for Unreal Engine using The Grove.

## Prerequisites

1. **The Grove 2.2** installed at `src/the_grove_22/`
2. **Conda environment** set up and activated

## Initial Setup

### 1. Create Environment

```bash
conda env create -f environment.yml
conda activate the-grove
```

### 2. Install Package

```bash
pip install -e .
```

### 3. Prepare Assets

Copy assets from The Grove 2.2 installation:

```bash
python src/growpy/cli/prepare_assets.py
```

This copies:

- Species presets (.seed.json files)
- Textures (bark, leaves)
- Twig models (.blend files)

## Choose Your Workflow

### Workflow A: Forest from CSV

**Use case**: You have real tree inventory data (GPS coordinates, species, heights)

```bash
# Step 1: Run pipeline (prepare, convert twigs, create models)
python src/growpy/cli/run_pipeline.py

# Step 2: Generate forest from CSV
python src/growpy/cli/generate_forest.py data/input/your_forest.csv
```

**CSV Format**:

```csv
x,y,species,height
100.5,200.3,European beech,25.5
105.2,198.7,Norway spruce,18.3
```

**Output**: `data/output/forest/` with organized tree and twig FBX files

### Workflow B: Species Library

**Use case**: You want template trees for each species to use in Unreal

```bash
# Step 1: Run pipeline
python src/growpy/cli/run_pipeline.py

# Step 2: Generate library with variations
python src/growpy/cli/generate_species_library.py --variations 3
```

**Output**: `data/output/species_library/` with 1-3 variations per species

## Pipeline Details

The `run_pipeline.py` script automatically executes:

1. **Prepare Assets** - Copy from Grove 2.2
2. **Convert Twigs** - Export .blend to FBX
3. **Create Growth Models** - Generate height prediction models

## Output Structure

Both workflows create organized folders:

```
output/
└── [forest or species_library]/
    ├── SpeciesName_001.fbx           # Tree with skeleton
    ├── SpeciesName_002.fbx           # Variation (if multiple)
    ├── twigs/
    │   ├── SpeciesName_Twig_Long.fbx
    │   └── SpeciesName_Twig_Short.fbx
    ├── textures/
    │   ├── bark_diffuse.png
    │   └── leaf_diffuse.png
    └── metadata.json                 # Species info
```

## Import to Unreal Engine

1. **Copy Folder**: Drag entire output folder into Unreal Content Browser
2. **Assets Ready**: Trees and twigs are organized by species
3. **Assembly**: Use PCG, Foliage Tool, or manual placement
4. **Enable Nanite**: For optimized rendering (UE 5.0+)

Trees export with skeletons for wind animation. Twigs are separate meshes for procedural assembly in Unreal.

## Configuration

Edit species in `src/growpy/config/tree_asset_lookup.csv`:

```csv
species,seed_path,texture_path,twig_path
European beech,EuropeanBeech.seed.json,European_Beech,EuropeanBeechTwig
Norway spruce,NorwaySpruce.seed.json,Norway_Spruce,NorwaySpruceTwig
```

Add more species by adding rows with:

- Species name (must match CSV if using forest workflow)
- Seed file from Grove 2.2 presets
- Texture folder name
- Twig folder name

## Common Commands

```bash
# Complete pipeline only
python src/growpy/cli/run_pipeline.py

# Forest from CSV
python src/growpy/cli/generate_forest.py data/input/forest.csv

# Species library with 5 variations
python src/growpy/cli/generate_species_library.py --variations 5

# Skip asset preparation
python src/growpy/cli/run_pipeline.py --skip-prepare

# Custom growth model parameters
python src/growpy/cli/create_growth_models.py --cycles 150 --seeds 3
```

## Troubleshooting

### Grove API not found

Ensure PYTHONPATH is set:

```bash
# Windows PowerShell
$env:PYTHONPATH=".\src;.\src\the_grove_22\modules"
```

### bpy module not found

Install via conda:

```bash
conda install -c conda-forge bpy
```

### Missing assets

Run prepare_assets.py first:

```bash
python src/growpy/cli/prepare_assets.py
```

## Next Steps

- Read **[USER_GUIDE.md](growpy/USER_GUIDE.md)** for detailed CLI reference
- See **[UNREAL_IMPORT_GUIDE.md](growpy/UNREAL_IMPORT_GUIDE.md)** for Unreal workflow
- Check **[CONFIGURATION.md](growpy/CONFIGURATION.md)** for advanced config

---

**Ready to generate forests for Unreal Engine!**
