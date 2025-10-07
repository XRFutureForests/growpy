# Twig Texture Investigation Summary

**Date:** 2025-10-02  
**Issue:** Inconsistent texture availability and embedding across twig assets

## Investigation Findings

### Texture Availability Analysis

#### Well-Textured Species

**European Beech** - COMPLETE texture set:

```
✅ BeechDiffuse.jpg       (base color)
✅ BeechAlpha.jpg         (transparency/cutout)
✅ BeechNormal.jpg        (surface detail)
✅ BeechTranslucent.jpg   (subsurface scattering)
```

**Status:** Production-ready, optimal quality

**European Beech Fall** - PARTIAL texture set:

```
✅ BeechFallTop.png       (top diffuse)
✅ BeechFallBottom.png    (bottom diffuse)
✅ BeechSummerTop.png     (summer variant)
✅ BeechSummerBottom.png  (summer variant)
❌ Missing: Alpha, Normal, Translucent
```

**Status:** Functional but incomplete

#### Partially Textured Species

**Scots Pine** - SINGLE texture only:

```
✅ ScotsPine.png          (diffuse)
❌ Missing: Alpha, Normal, Translucent
+ 4 duplicate copies with varied names
```

**Issue:** Only diffuse texture, 21.6 MB wasted on duplicates

**European Oak** - PARTIAL set:

```
✅ OakEuropeanTop.png        (diffuse top)
✅ OakEuropeanBottom.png     (diffuse bottom)
✅ OakEuropeanTopBump.png    (normal)
❌ Missing: Alpha, Translucent
```

**Status:** Better than pine, but still incomplete

**Red Oak** - MINIMAL set:

```
✅ RedOakTop.png         (diffuse top)
✅ RedOakBottom.png      (diffuse bottom)
❌ Missing: Alpha, Normal, Translucent
```

**Status:** Basic functionality only

### Critical Discovery: FBX Material Issue

**MAJOR PROBLEM:** Despite complete texture sets being available (like European Beech), the exported FBX files contain only basic colored materials WITHOUT embedded textures.

**Evidence:**

- European Beech FBX files: ~700 KB (geometry only)
- Complete texture set available: 4 texture files
- FBX export settings claim `embed_textures=True`
- Result: Textures NOT actually embedded

**Root Cause:** Materials in Blender not properly connected to textures before FBX export

### Naming Convention Chaos

Original twig files use inconsistent naming:

| Pattern | Examples | Grove Attribute |
|---------|----------|-----------------|
| Apical/Lateral | EuropeanOakApicalTwig | twig_long / twig_short |
| End/Side | (older files) | twig_long / twig_short |
| Long/Short | (Chinese translations) | twig_long / twig_short |
| A/B/C/D/E | BeechTwigA, BeechTwigB | Variations within type |
| Var A/B/C | ScotsPineVariationA | Variations within type |
| Summer/Fall | BeechSummerTwig, BeechFallTwig | Seasonal variants |
| Dead/Winter | (dormant twigs) | twig_dead |

**Problem:** Unclear mapping to Grove's tree attributes for PCG placement in Unreal

## Solution: Enhanced Twig Converter (v2)

### Key Features

1. **Intelligent Texture Detection**
   - Scans multiple directories (textures/, parent folders)
   - Classifies textures by filename keywords
   - Handles top/bottom leaf variants
   - Supports all PBR texture types

2. **Robust Material Creation**
   - Creates Principled BSDF with all available textures
   - Proper color space settings (Non-Color for data maps)
   - Alpha blending setup for leaf cutout
   - Normal map nodes with proper connections
   - Translucency for subsurface effects

3. **Texture Embedding**
   - Copies textures to output directory
   - Embeds in FBX using `path_mode='COPY'` + `embed_textures=True`
   - Creates USD with texture references

4. **Standardized Naming**
   - Apical → `{species}_apical`
   - Lateral → `{species}_lateral`
   - Upward → `{species}_upward`
   - Dead/Fall → `{species}_dead`
   - Variations → `{species}_{type}_var_{a/b/c}`

5. **Metadata Tracking**
   - Generates `twig_manifest.json` per species
   - Maps original names to standardized names
   - Documents detected twig types and variations
   - Lists used materials and textures

### Implementation

**New File:** `src/growpy/cli/convert_twigs_v2.py`

**Features:**

- Drop-in replacement for original converter
- Backward compatible with existing workflows
- Generates both FBX and USD
- Comprehensive error handling
- Progress bars and detailed logging

### Usage Examples

```bash
# Convert all twigs with texture detection
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs

# Convert specific species
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs/EuropeanBeechTwig

# FBX only (with embedded textures)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats fbx

# USD only (for Houdini workflows)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats usda
```

## Recommendations

### Immediate Actions

1. **Re-convert all twigs** using v2 converter to get proper texture embedding
2. **Audit texture sets** - identify which species need additional texture maps
3. **Update Unreal imports** - re-import FBX files to get embedded textures
4. **Test PCG placement** - verify standardized names work with tree attributes

### Short-Term Improvements

1. **Create missing texture maps:**
   - Generate alpha maps from diffuse (via Photoshop/Substance)
   - Create normal maps from diffuse (via CrazyBump/xNormal)
   - Add translucent maps for key species

2. **Standardize texture naming:**
   - Use consistent pattern: `{Species}{Type}.{ext}`
   - Example: `BeechDiffuse.jpg`, `BeechAlpha.jpg`, `BeechNormal.jpg`

3. **Document texture requirements:**
   - Create template texture set for new species
   - Specify resolution targets (2K/4K)
   - Define quality standards

### Long-Term Goals

1. **Texture Library Management:**
   - Central texture repository
   - Version control for texture updates
   - Automated quality checks

2. **Material Presets:**
   - Standard material templates for Unreal
   - PCG-compatible material instances
   - LOD-aware texture usage

3. **Automated Validation:**
   - Check for missing texture types
   - Verify FBX embedding worked
   - Test import in Unreal automatically

## Technical Details

### Texture Classification Algorithm

```python
def classify_texture_type(filename):
    name_lower = filename.lower()
    
    # Handle modifiers (top/bottom)
    if 'top' in name_lower:
        return 'diffuse_top'
    if 'bottom' in name_lower:
        return 'diffuse_bottom'
    
    # Standard types
    keywords = {
        'diffuse': ['diffuse', 'albedo', 'color'],
        'alpha': ['alpha', 'opacity', 'mask'],
        'normal': ['normal', 'norm', 'bump'],
        'translucent': ['translucent', 'sss'],
        'roughness': ['roughness', 'rough'],
        'metallic': ['metallic', 'metal'],
    }
    
    for tex_type, kw_list in keywords.items():
        if any(kw in name_lower for kw in kw_list):
            return tex_type
    
    return 'diffuse'  # default
```

### Name Standardization Logic

```python
def standardize_name(original, species):
    name_lower = original.lower()
    parts = [species.lower().replace(' ', '_')]
    
    # Detect type
    if any(kw in name_lower for kw in ['apical', 'end', 'long']):
        parts.append('apical')
    elif any(kw in name_lower for kw in ['lateral', 'side', 'short']):
        parts.append('lateral')
    elif 'upward' in name_lower:
        parts.append('upward')
    elif any(kw in name_lower for kw in ['dead', 'fall', 'winter']):
        parts.append('dead')
    
    # Detect variation
    for letter in ['a', 'b', 'c', 'd', 'e']:
        if f'var{letter}' in name_lower or f'twig{letter}' in name_lower:
            parts.append(f'var_{letter}')
            break
    
    return '_'.join(parts)
```

## Testing Checklist

After conversion with v2:

- [ ] FBX files larger than before (textures embedded)
- [ ] Import FBX in Unreal - all material slots filled
- [ ] Check material preview - textures visible
- [ ] Alpha masking works (leaves have clean edges)
- [ ] Normal maps add surface detail
- [ ] Translucency visible in backlit conditions
- [ ] Manifest JSON generated and accurate
- [ ] Standardized names match tree attributes
- [ ] PCG placement uses correct twig types

## Files Created

1. **`src/growpy/cli/convert_twigs_v2.py`**
   - Enhanced converter with texture detection
   - Standardized naming system
   - Material setup automation

2. **`docs/growpy/TWIG_CONVERSION_V2.md`**
   - Complete documentation
   - Usage examples
   - Troubleshooting guide
   - Unreal Engine integration

3. **`docs/TWIG_TEXTURE_AUDIT.md`** (this file)
   - Investigation findings
   - Problem analysis
   - Solution overview
   - Recommendations

## Next Steps

1. **Test the v2 converter** on a sample species (European Beech)
2. **Verify texture embedding** in FBX output
3. **Import into Unreal** and check materials
4. **If successful, convert all species**
5. **Document any issues** encountered
6. **Update main pipeline** to use v2 by default

## References

- [Twig Conversion V2 Documentation](TWIG_CONVERSION_V2.md)
- [Texture Implementation Guide](TEXTURE_IMPLEMENTATION.md)
- [Grove Integration Patterns](GROVE_INTEGRATION.md)
- [Unreal Import Guide](UNREAL_IMPORT_GUIDE.md)
