# GrowPy Pipeline Workflow

Complete guide to the GrowPy tree generation and Unreal Engine import pipeline.

## Pipeline Overview

```
1. prepare_assets    → Copy species presets, twigs, textures from Grove 2.2
2. convert_twigs     → Export .blend twigs to USD with skeletons
3. create_growth_models → Generate height/age prediction models
4. generate_forest   → Simulate forest and export Nanite Assembly USD
5. UNREAL IMPORT     → Import to Unreal Content Browser (optional)
```

## Complete Pipeline Example

### Option A: Step by Step

```bash
# Activate environment
conda activate the-grove

# 1. Prepare assets for species in CSV
python src/growpy/cli/prepare_assets.py

# 2. Convert twigs to USD with skeletons
python src/growpy/cli/convert_twigs.py data/assets/twigs

# 3. Create growth models
python src/growpy/cli/create_growth_models.py --cycles 125

# 4. Generate forest
python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 15

# 5. Import to Unreal (optional)
# Just add --import-to-unreal flag to step 4 above
```

### Option B: Integrated Workflow (RECOMMENDED)

```bash
# Activate environment
conda activate the-grove

# Steps 1-3: Prepare everything
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py --cycles 125

# Step 4-5: Generate forest AND import to Unreal in one command
python src/growpy/cli/generate_forest.py \
    --quality high \
    --growth-cycle-limit 15 \
    --import-to-unreal \
    --unreal-project-path "/Game/GrowPy/Trees"
```

## Input CSV Format

Your CSV should have these columns:

```csv
x,y,species,height
0,0,European beech,25.0
10,5,Norway spruce,30.0
-5,10,Red oak,20.0
```

**Default CSV:** `data/input/test.csv` (5 species)

## Per-Script Options

### 1. prepare_assets.py

```bash
# Default: Uses data/input/test.csv (5 species)
python src/growpy/cli/prepare_assets.py

# Copy ALL 57 available Grove species
python src/growpy/cli/prepare_assets.py --all

# Use custom CSV
python src/growpy/cli/prepare_assets.py --csv my_species.csv
```

**What it does:** Copies species presets (.seed.json), twig directories, and bark textures from Grove 2.2

### 2. convert_twigs.py

```bash
# Default: Converts twigs for species in data/input/test.csv
python src/growpy/cli/convert_twigs.py data/assets/twigs

# Convert with different formats
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Use custom CSV filter
python src/growpy/cli/convert_twigs.py data/assets/twigs --csv my_species.csv
```

**What it does:** Exports .blend twig files to USD with skeletal structure for Nanite assemblies

**Output:** `data/assets/twigs/species_name/*_skeletal.usda`

### 3. create_growth_models.py

```bash
# Default: Creates models for species in data/input/test.csv
python src/growpy/cli/create_growth_models.py

# Longer simulation for better accuracy
python src/growpy/cli/create_growth_models.py --cycles 125

# All 57 species
python src/growpy/cli/create_growth_models.py \
    --csv src/growpy/config/tree_asset_lookup.csv \
    --cycles 125
```

**What it does:** Simulates tree growth to create height/age prediction models

**Output:** `data/assets/growth_models/species_name_height_curve.json`

### 4. generate_forest.py (with Unreal import)

```bash
# Generate only (no Unreal import)
python src/growpy/cli/generate_forest.py \
    --quality high \
    --growth-cycle-limit 15

# Generate AND import to Unreal
python src/growpy/cli/generate_forest.py \
    --quality high \
    --growth-cycle-limit 15 \
    --import-to-unreal

# Custom Unreal destination
python src/growpy/cli/generate_forest.py \
    --quality high \
    --import-to-unreal \
    --unreal-project-path "/Game/MyProject/Trees"

# Custom CSV and output directory
python src/growpy/cli/generate_forest.py my_forest.csv \
    --output-dir data/output/my_forest \
    --quality high \
    --import-to-unreal
```

**Quality Presets:**

- `ultra` - Hero trees (32 vertices, max detail)
- `high` - Foreground trees (24 vertices)
- `medium` - Mid-distance trees (16 vertices)
- `low` - Background trees (12 vertices)
- `performance` - Distant trees (8 vertices)

**What it does:**

1. Simulates multi-species forest with light competition
2. Exports each tree as Nanite Assembly USD with skeleton
3. Optionally imports to Unreal Engine Content Browser

**Output:** `data/output/forest/species_name/*_nanite_assembly.usda`

## Unreal Engine Setup

Required for `--import-to-unreal` flag:

### 1. Enable Python Plugin

- Edit > Plugins > Search "Python"
- Enable "Python Editor Script Plugin"
- Restart Unreal

### 2. Enable Remote Execution

- Edit > Project Settings > Plugins > Python
- Check "Enable Remote Execution"
- Default ports: Multicast 6766, Command 6776

### 3. Enable USD Plugins

- Edit > Plugins > Search "USD"
- Enable "USD Importer" and "USD Core"

### 4. Install Python Package

```bash
conda activate the-grove
pip install unreal-remote-execution
```

## Import Behavior

When using `--import-to-unreal`:

1. **Searches for:** `*nanite_assembly.usda` or `*nanite_assembly.usd` files
2. **Imports to:** Unreal Content Browser (NOT level)
3. **Location:** Specified by `--unreal-project-path` (default: `/Game/GrowPy/Trees`)
4. **Configuration:**
   - `import_actors = False` (don't spawn in level)
   - `import_geometry = True`
   - `import_materials = True`
   - `replace_existing = True`

**After import:** Assets are ready in Content Browser for:

- Manual placement in level
- PCG (Procedural Content Generation) systems
- Blueprint spawning
- Level sequencer

## Troubleshooting

### Unreal Import Fails

**Error: "Failed to connect to Unreal Engine"**

Check:

1. Unreal Engine is running
2. Remote Execution enabled (Project Settings > Plugins > Python)
3. Firewall not blocking ports 6766/6776
4. Try custom port: `--unreal-port 6777`

**Error: "No Nanite Assembly USD files found"**

- Run `generate_forest.py` first to create USD files
- Check output directory exists
- Look for files matching `*nanite_assembly.usda` pattern

### Import Succeeds but Assets Not Visible

1. Check Content Browser folder: `/Game/GrowPy/Trees` (or your custom path)
2. Verify USD Importer plugin is enabled
3. Try importing manually: File > Import, select USD file

### Performance Issues

**Forest generation is slow:**

- Use `--quality medium` or `--quality low`
- Reduce `--growth-cycle-limit` (try 10 or 5)
- Use fewer species in CSV

**Unreal import is slow:**

- Normal for many large files
- Each tree can be 10-50MB
- Consider importing in batches

## Quick Commands

### Minimal Setup (5 species)

```bash
conda activate the-grove
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py
python src/growpy/cli/generate_forest.py --quality high --import-to-unreal
```

### Full Setup (57 species)

```bash
conda activate the-grove
python src/growpy/cli/prepare_assets.py --all
python src/growpy/cli/convert_twigs.py data/assets/twigs --csv src/growpy/config/tree_asset_lookup.csv
python src/growpy/cli/create_growth_models.py --csv src/growpy/config/tree_asset_lookup.csv --cycles 125
python src/growpy/cli/generate_forest.py --quality high --import-to-unreal
```

### Fast Iteration (for testing)

```bash
conda activate the-grove
# Only run once:
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py

# Iterate on forest:
python src/growpy/cli/generate_forest.py \
    --quality performance \
    --growth-cycle-limit 5 \
    --import-to-unreal
```

## File Outputs

```
data/
├── assets/
│   ├── presets/
│   │   └── european_beech.seed.json
│   ├── twigs/
│   │   └── european_beech/
│   │       └── european_beech_apical_skeletal.usda
│   ├── textures/
│   │   └── beech_60.png
│   └── growth_models/
│       └── european_beech_height_curve.json
└── output/
    └── forest/
        └── european_beech/
            ├── european_beech_tree_0000_nanite_assembly.usda
            ├── european_beech_tree_0001_nanite_assembly.usda
            └── ...
```

## Best Practices

1. **Run setup steps once:** `prepare_assets`, `convert_twigs`, `create_growth_models`
2. **Iterate on forest:** Only re-run `generate_forest.py` with different parameters
3. **Use version control:** Commit after each successful pipeline run
4. **Quality presets:** Start with `performance`, increase quality as needed
5. **Unreal import:** Test with small forests first, then scale up

## Next Steps

After import to Unreal:

1. **Place in Level:** Drag from Content Browser to viewport
2. **Setup PCG:** Use with Procedural Content Generation for forests
3. **Configure Materials:** Adjust PBR materials for your lighting
4. **Add Wind:** Use skeletal animation for wind effects
5. **LOD Setup:** Nanite handles LODs automatically

## Resources

- **Pipeline Scripts:** `src/growpy/cli/`
- **Configuration:** `src/growpy/config/tree_asset_lookup.csv`
- **Unreal Integration:** `docs/growpy/UNREAL_INTEGRATION.md`
- **Quick Start:** `docs/growpy/UNREAL_QUICK_START.md`
