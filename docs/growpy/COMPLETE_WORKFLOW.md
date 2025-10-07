# Complete Workflow - Grove to Unreal Engine

This document outlines the complete workflow from The Grove 2.2 to Unreal Engine 5.7+ with Nanite Assemblies.

## Overview

The workflow consists of three main steps:

1. **Prepare Assets** - One-time setup
2. **Convert Twigs** - Create USD twig files
3. **Export Trees** - Generate tree USD files with Nanite Assemblies

## Prerequisites

### Environment Setup

```bash
# Activate conda environment
conda activate the-grove

# Set Unreal schema path (add to ~/.zshrc for persistence)
export PXR_PLUGINPATH_NAME="$(pwd)/data/unreal_schema"

# Verify setup
python -c "from growpy import get_config; print('✓ GrowPy ready')"
python -c "from pxr import Usd; print('✓ USD Python ready')"
```

### Required Packages

```bash
# Install if missing
conda install -c conda-forge bpy pandas numpy scikit-learn
pip install usd-core
```

## Complete Pipeline

### Step 1: Prepare Assets (One-Time)

Copy assets from The Grove 2.2 installation:

```bash
python src/growpy/cli/prepare_assets.py
```

**What it does:**

- Copies species presets (`.seed.json` files)
- Copies textures (bark, leaf materials)
- Copies twig `.blend` files
- Creates species lookup table

**Output:**

```
data/assets/
├── presets/          # Species .seed.json files
├── textures/         # Bark and leaf textures
├── twigs/           # Twig .blend files (by species)
└── growth_models/   # Created later
```

### Step 2: Convert Twigs to USD

**IMPORTANT: Run this before generating trees!**

```bash
# Convert all twig .blend files to USD
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Or convert specific species
python src/growpy/cli/convert_twigs.py data/assets/twigs/Betulaceae_Downy_birch --formats usda
```

**What it does:**

- Converts `.blend` twig files to `.usda` format
- Standardizes twig naming (apical, lateral, dead)
- Sets up materials with textures
- Creates mount points at origin for proper attachment
- Generates `twig_manifest.json` per species

**Output:**

```
data/assets/twigs/Betulaceae_Downy_birch/
├── Betulaceae_Downy_birch_Twig_Short.blend
├── betulaceae_downy_birch_lateral.usda     # ← NEW
├── Betulaceae_Downy_birch_Twig_Long.blend
├── betulaceae_downy_birch_apical.usda      # ← NEW
└── twig_manifest.json                       # ← NEW
```

**Why USD twigs?**

- ✅ Native USD-to-USD references (more efficient)
- ✅ Better material preservation
- ✅ Smaller file sizes
- ✅ Optimal for PointInstancer
- ✅ No runtime conversion in Unreal

**Can I skip this?**

- ⚠️ Trees will still export using FBX twigs as fallback
- ⚠️ But USD twigs are strongly recommended for best results

### Step 3A: Generate Species Library

Export template trees for all configured species:

```bash
# Default: USDA with Nanite Assemblies
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --resolution 32

# Ultra quality with all formats
python src/growpy/cli/generate_species_library.py \
  --formats fbx usda \
  --include-twigs \
  --resolution 32 \
  --flushes 15

# Standard USD only (no Nanite Assembly)
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --no-nanite-assembly
```

**Output per species:**

```
data/output/species_library/USD/
├── European_Beech_tree_only.usda        # Tree mesh only
├── European_Beech.usda                  # Standard USD (Blender)
└── European_Beech_NaniteAssembly.usda  # Nanite Assembly (Unreal)
```

### Step 3B: Generate Forest

Export trees from forest inventory CSV:

```bash
# Create forest CSV with columns: x, y, species, height
cat > forest.csv << EOF
x,y,species,height
100,200,European Beech,25.5
150,250,Norway Spruce,30.2
200,300,Scots Pine,28.7
EOF

# Generate forest with Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv \
  --formats usda \
  --quality ultra

# Multiple formats
python src/growpy/cli/generate_forest.py forest.csv \
  --formats fbx usda \
  --quality high
```

**Output:**

```
data/output/forest/USD/
├── European_Beech_var1_tree_only.usda
├── European_Beech_var1.usda
├── European_Beech_var1_NaniteAssembly.usda
├── Norway_Spruce_var1_tree_only.usda
├── Norway_Spruce_var1.usda
└── Norway_Spruce_var1_NaniteAssembly.usda
```

## File Types Explained

### Three USD Files Per Tree

Each tree export creates **three USD files**:

#### 1. Tree-Only USD (`*_tree_only.usda`)

- **Content**: Trunk and branches mesh only
- **No twigs**: Clean tree geometry
- **Use for**: Referenced by other USD files
- **Size**: Small (~100-500 KB)

#### 2. Standard USD (`*.usda`)

- **Content**: Complete tree with inline twig instances
- **Compatible**: Works in Blender, Houdini, Maya, etc.
- **Use for**: DCC preview, editing, non-Unreal workflows
- **Size**: Medium (~500 KB - 2 MB depending on twigs)

#### 3. Nanite Assembly USD (`*_NaniteAssembly.usda`)

- **Content**: Hierarchical assembly with USD references
- **Schema**: Uses `NaniteAssemblyRootAPI` and `NaniteAssemblyExternalRefAPI`
- **References**: Points to tree-only USD and twig USD files
- **Optimized**: PointInstancer for twigs, automatic Nanite conversion
- **Use for**: **Import this into Unreal Engine 5.7+**
- **Size**: Small (~50-200 KB, references do the heavy lifting)

### Which File to Use?

| Use Case | File to Use | Why |
|----------|-------------|-----|
| **Import to Unreal** | `*_NaniteAssembly.usda` | Automatic Nanite, optimized instancing |
| **Preview in Blender** | `*.usda` | Full geometry inline, easy viewing |
| **Edit in Houdini** | `*.usda` | Standard USD, compatible |
| **Reference in other USD** | `*_tree_only.usda` | Clean tree without twigs |
| **Import to Unity/Godot** | `*.fbx` | Standard mesh format |

## Twig Integration Details

### Twig File Discovery

The `get_twig_usd_map_for_species()` function searches for twigs in this order:

1. **`.usda`** (preferred - created by `convert_twigs.py`)
2. **`.usd`** (also good)
3. **`.fbx`** (fallback - original Grove twigs)

### Twig Type Mapping

Grove uses these twig attribute names:

- `twig_long` → Apical/terminal twigs (tree crown ends)
- `twig_short` → Lateral twigs (side branches)
- `twig_upward` → Upward-facing twigs
- `twig_dead` → Dead/winter twigs

The converter creates standardized names:

- `species_apical.usda`
- `species_lateral.usda`
- `species_upward.usda`
- `species_dead.usda`

### Twig Placement

Twigs are placed as **USD PointInstancer** prims:

- **Efficient**: Single prototype, thousands of instances
- **Memory**: Minimal overhead vs copying geometry
- **Performance**: GPU instancing in Unreal
- **Data**: Position, rotation (quaternion), scale per instance

## Quality Presets

### Ultra (Hero Trees)

```bash
--quality ultra --resolution 32
```

- 32 vertices around branches
- Maximum detail
- Full texture resolution
- All branch geometry
- Best for close-up views

### High (Standard)

```bash
--quality high --resolution 24
```

- 24 vertices around branches
- Good detail
- Full textures
- Most branches
- Default recommended

### Medium (Background)

```bash
--quality medium --resolution 16
```

- 16 vertices around branches
- Moderate detail
- Reduced textures
- Major branches only
- Good for mid-distance

### Performance (Distant)

```bash
--quality performance --resolution 8
```

- 8 vertices around branches
- Minimal detail
- Low-res textures
- Trunk + major branches
- Best for far backgrounds

## Unreal Engine Import

### 1. Enable USD Plugin

In Unreal Engine:

1. Edit → Plugins
2. Search "USD"
3. Enable "USD Importer"
4. Restart Unreal

### 2. Verify Schema Registration

Check Output Log after launch:

```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

If not shown:

- Verify `PXR_PLUGINPATH_NAME` environment variable
- Restart Unreal after setting variable

### 3. Import Nanite Assembly

1. Content Browser → Import
2. Select `*_NaniteAssembly.usda`
3. Import Settings:
   - ☑ Import Geometry
   - ☑ Import as Static Meshes
   - ☐ Import Actors (unchecked - we want assets)
   - ☐ Apply World Transform
4. Click Import

### 4. Verify Nanite Conversion

After import, open the Static Mesh:

- Static Mesh Editor → Details
- Check "Enable Nanite Support" is ON
- Check triangle count (should be very high)
- Check LODs (Nanite = automatic)

### 5. Use in Level

**Manual Placement:**

- Drag asset from Content Browser to level
- Scale and position

**PCG (Procedural Content Generation):**

```
PCG Graph:
  Surface Sampler → Spawn Mesh → *_NaniteAssembly
```

**Foliage Tool:**

1. Foliage Mode
2. Add asset as Foliage Type
3. Paint or scatter

## Troubleshooting

### No USD Twigs Found

**Symptom:** Warning during export: "No twig USD files found"

**Solution:**

```bash
# Convert twigs first
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Verify output
ls data/assets/twigs/*/betulaceae*.usda
```

### Twigs Not Appearing in Unreal

**Check:**

1. Twig USD files exist in same directory as tree USD
2. `*_NaniteAssembly.usda` references are correct (open in text editor)
3. `TwigPrototypes` section exists in Nanite Assembly
4. Re-import with "Import Geometry" enabled

### Schema Not Recognized

**Symptom:** Import works but no Nanite conversion

**Solution:**

1. Set `PXR_PLUGINPATH_NAME` environment variable
2. Restart Unreal Engine
3. Check Output Log for schema registration

### Export Fails

**Check:**

```bash
# Verify bpy module
python -c "import bpy; print(bpy.__version__)"

# Verify USD Python
python -c "from pxr import Usd; print('USD OK')"

# Verify Grove core
python -c "import the_grove_22_core as gc; print('Grove OK')"
```

## Performance Tips

### For Hero Trees (Close-Up)

- Quality: Ultra
- Resolution: 32
- Include twigs: Yes
- Nanite: Enabled

### For Background Trees

- Quality: Medium/Performance
- Resolution: 8-16
- Include twigs: Optional
- Nanite: Enabled (for LOD management)

### For Dense Forests

- Use 2-3 variations per species
- Mix quality levels by distance
- Enable GPU instancing in Unreal
- Use PCG for placement

## Summary Commands

```bash
# Complete pipeline from scratch
conda activate the-grove
export PXR_PLUGINPATH_NAME="$(pwd)/data/unreal_schema"

# 1. Prepare (one-time)
python src/growpy/cli/prepare_assets.py

# 2. Convert twigs (one-time per update)
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# 3A. Generate species library
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --resolution 32

# 3B. OR generate forest from CSV
python src/growpy/cli/generate_forest.py forest.csv \
  --formats usda \
  --quality ultra

# 4. Import *_NaniteAssembly.usda into Unreal Engine 5.7+
```

## Next Steps

After successful import:

1. **Verify materials** - Check bark and leaf textures
2. **Test LODs** - Zoom in/out, verify smooth transitions
3. **Measure performance** - FPS with many trees
4. **Create variations** - Export with different seeds
5. **Setup PCG** - Procedural placement system
6. **Configure foliage** - Foliage tool settings

## References

- Full documentation: `docs/growpy/NANITE_ASSEMBLY_GUIDE.md`
- Quick start: `NANITE_ASSEMBLY_README.md`
- Technical details: `NANITE_ASSEMBLY_INTEGRATION.md`
- Schema info: `data/unreal_schema/README.md`

---

**Last Updated:** 2025-01-07  
**Version:** 1.0
