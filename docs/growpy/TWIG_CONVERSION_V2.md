# Enhanced Twig Conversion System (v2)

## Overview

The v2 twig converter (`convert_twigs_v2.py`) addresses two critical issues in the original system:

1. **Incomplete Texture Handling** - Original converter only used diffuse textures, ignoring alpha, normal, and translucent maps
2. **Inconsistent Naming** - Twig files use varied naming (Apical/Lateral, Long/Short, A/B/C) making it unclear which connects to which tree attribute

## Key Improvements

### 1. Robust Texture Detection

The v2 system automatically detects and uses ALL available texture types:

#### Supported Texture Types

| Type | Keywords | Purpose | Unreal Usage |
|------|----------|---------|--------------|
| **Diffuse/Albedo** | diffuse, albedo, color, basecolor | Base color | Base Color input |
| **Alpha/Opacity** | alpha, opacity, mask, cutout | Transparency | Opacity Mask |
| **Normal** | normal, norm, bump, height | Surface detail | Normal input |
| **Translucent** | translucent, transmission, sss | Light transmission | Translucency |
| **Roughness** | roughness, rough, gloss | Surface smoothness | Roughness |
| **Metallic** | metallic, metal | Metalness | Metallic |
| **AO** | ao, ambient, occlusion | Ambient occlusion | Multiply with base |
| **Emissive** | emissive, emission, glow | Self-illumination | Emissive Color |

#### Special Patterns

**Leaf Top/Bottom Textures:**

- `diffuse_top` - Top side of leaves (facing sun)
- `diffuse_bottom` - Bottom side of leaves (underside)

### 2. Standardized Naming System

#### Grove Tree Attributes → Standardized Names

The Grove generates tree meshes with face attributes marking twig placement positions:

| Grove Attribute | Original Names (varied) | Standardized Name | Description |
|----------------|------------------------|-------------------|-------------|
| `twig_long` | Apical, End, Long, Terminal, Tip | **apical** | Terminal/end twigs at branch tips |
| `twig_short` | Lateral, Side, Short, Laterall | **lateral** | Side branches along stems |
| `twig_upward` | Upward, Up | **upward** | Upward-facing twigs |
| `twig_dead` | Dead, Fall, Winter, Bare | **dead** | Dead/dormant twigs |

#### Naming Convention

```
{species}_{type}_{variation}_{season}
```

**Examples:**

- `BeechApicalTwig.fbx` → `european_beech_apical.fbx`
- `ScotsPineVariationCLateralTwig.fbx` → `scots_pine_lateral_var_c.fbx`
- `OakEuropeanLongTwig.fbx` → `european_oak_apical.fbx`
- `BeechTwigA.fbx` → `european_beech_var_a.fbx`
- `EuropeanBeechFallLateralTwig.fbx` → `european_beech_lateral_dead.fbx`

### 3. Material Setup

#### Complete PBR Material Creation

For each twig, the system:

1. **Scans for textures** in:
   - `twigs/{species}/textures/`
   - `twigs/{species}/`
   - Parent directories

2. **Classifies each texture** by type (diffuse, alpha, normal, etc.)

3. **Creates Principled BSDF** material with:
   - All found textures properly connected
   - Correct color space settings (Non-Color for data maps)
   - Alpha blending setup (CLIP mode for cutout leaves)
   - Normal map nodes
   - Transmission for translucency

4. **Embeds textures in FBX** using:

   ```python
   path_mode='COPY'
   embed_textures=True
   ```

5. **Copies textures** to output directory for USD reference

## Usage

### Basic Usage

```bash
# Convert all twigs in directory
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs

# Convert with specific formats
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats fbx usd

# Convert single species
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs/EuropeanBeechTwig
```

### Advanced Usage

```bash
# FBX only (faster, includes embedded textures)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats fbx

# USD only (for Houdini/USD workflows)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats usda

# Process single blend file
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs/EuropeanBeechTwig/EuropeanBeechTwig.blend
```

## Output Structure

### File Organization

```
data/assets/twigs/
├── EuropeanBeechTwig/
│   ├── european_beech_apical.fbx          # Standardized name
│   ├── european_beech_apical.usda
│   ├── european_beech_lateral.fbx
│   ├── european_beech_lateral.usda
│   ├── twig_manifest.json                 # Metadata
│   ├── textures/
│   │   ├── BeechDiffuse.jpg              # Copied to output
│   │   ├── BeechAlpha.jpg
│   │   ├── BeechNormal.jpg
│   │   └── BeechTranslucent.jpg
│   └── ...
```

### Manifest File

Each processed directory gets a `twig_manifest.json`:

```json
{
  "european_beech_apical": {
    "original_name": "BeechTwigA",
    "metadata": {
      "species": "European Beech",
      "type": "apical",
      "variation": "a",
      "season": null
    },
    "materials": ["EuropeanBeech_Beech"],
    "export_formats": ["fbx", "usda"]
  },
  "european_beech_lateral": {
    "original_name": "BeechTwigB",
    "metadata": {
      "species": "European Beech",
      "type": "lateral",
      "variation": "b",
      "season": null
    },
    "materials": ["EuropeanBeech_Beech"],
    "export_formats": ["fbx", "usda"]
  }
}
```

## Texture Handling Examples

### Example 1: European Beech (Complete Set)

**Available Textures:**

```
BeechDiffuse.jpg      → diffuse
BeechAlpha.jpg        → alpha
BeechNormal.jpg       → normal
BeechTranslucent.jpg  → translucent
```

**Result:**

- ✅ Full PBR material with all maps
- ✅ Alpha blending for leaf cutout
- ✅ Normal maps for surface detail
- ✅ Translucency for subsurface scattering
- ✅ Textures embedded in FBX

### Example 2: Scots Pine (Partial Set)

**Available Textures:**

```
ScotsPine.png         → diffuse
```

**Result:**

- ⚠️ Basic material with diffuse only
- ❌ Missing: alpha (for needle cutout)
- ❌ Missing: normal (for needle detail)
- ⚠️ Still functional, but less realistic

### Example 3: European Oak (Top/Bottom)

**Available Textures:**

```
OakEuropeanTop.png        → diffuse_top
OakEuropeanBottom.png     → diffuse_bottom
OakEuropeanTopBump.png    → normal
```

**Result:**

- ✅ Top/bottom leaf textures
- ✅ Normal map
- ⚠️ Missing alpha (may need manual addition)

## Mapping to Unreal Engine

### In Unreal PCG/Foliage System

Use standardized names to match tree attributes:

```python
# PCG Graph example
if face_has_attribute("twig_long"):
    spawn_mesh("european_beech_apical.fbx")
elif face_has_attribute("twig_short"):
    spawn_mesh("european_beech_lateral.fbx")
elif face_has_attribute("twig_upward"):
    spawn_mesh("european_beech_upward.fbx")
elif face_has_attribute("twig_dead"):
    spawn_mesh("european_beech_dead.fbx")
```

### Material Instance Setup

1. **Import FBX** - Unreal automatically extracts embedded textures
2. **Check Material** - Verify all texture slots are filled
3. **Create Material Instance** - For easy parameter tweaking
4. **Enable Foliage Settings**:
   - Two-Sided: Yes
   - Blend Mode: Masked (for alpha cutout)
   - Shading Model: Subsurface (for translucency)

## Troubleshooting

### Issue: No Textures in Exported FBX

**Cause:** Textures not found or not embedded
**Solution:**

1. Check `textures/` subfolder exists
2. Verify texture file extensions (png, jpg, etc.)
3. Ensure `embed_textures=True` in export settings
4. Check Blender console output for texture errors

### Issue: Wrong Twig Type Assignment

**Cause:** Ambiguous naming in original blend file
**Solution:**

1. Check `twig_manifest.json` for actual classification
2. Rename objects in Blender blend file if needed
3. Use variation letters (A/B/C) if type is generic

### Issue: Material Shows Only Color

**Cause:** Texture classification failed or wrong color space
**Solution:**

1. Check texture filenames contain recognizable keywords
2. Verify textures are valid image files (not corrupt)
3. Check color space: Non-Color for normal/alpha/data maps
4. Manually inspect material nodes in Blender

## Texture Set Recommendations

### Minimum (Functional)

- ✅ Diffuse/Albedo

### Recommended (Good Quality)

- ✅ Diffuse/Albedo
- ✅ Alpha/Opacity (essential for leaves)
- ✅ Normal

### Optimal (Production Quality)

- ✅ Diffuse/Albedo
- ✅ Alpha/Opacity
- ✅ Normal
- ✅ Translucent/Transmission
- ⭐ Roughness
- ⭐ Metallic (for certain species)

## Migration from v1

### Automated Re-conversion

Simply re-run the v2 converter on your existing twig directories:

```bash
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs
```

This will:

1. Re-export all twigs with standardized names
2. Create proper materials with all available textures
3. Generate manifest files for reference
4. Preserve original blend files

### Updating Unreal Assets

After re-conversion:

1. **Re-import FBX files** into Unreal (overwrites existing)
2. **Check material slots** - should now show all texture maps
3. **Update PCG graphs** to use new standardized names
4. **Test in-game** - verify textures display correctly

## See Also

- [Grove Integration Guide](GROVE_INTEGRATION.md)
- [Texture Implementation](TEXTURE_IMPLEMENTATION.md)
- [Unreal Import Guide](UNREAL_IMPORT_GUIDE.md)
- [Species Lookup Guide](SPECIES_LOOKUP_GUIDE.md)
