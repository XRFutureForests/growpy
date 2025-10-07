# Quick Guide: Fixing Twig Textures

## The Problem

Your twig FBX exports have **materials without textures** even though texture files exist.

Example: European Beech has complete textures (Diffuse, Alpha, Normal, Translucent) but FBX only shows solid color.

## The Solution

Use the new **v2 twig converter** which:

1. Finds ALL available textures automatically
2. Creates proper Blender materials
3. Embeds textures in FBX files
4. Standardizes twig names (Apical/Lateral/etc)

## Quick Start

### Re-convert All Twigs

```bash
conda activate the-grove
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs
```

This will:

- Process all twig blend files
- Detect and use all available textures
- Export FBX with embedded textures
- Create standardized filenames
- Generate metadata manifest

### Convert Single Species

```bash
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs/EuropeanBeechTwig
```

### Export Formats

```bash
# FBX only (recommended for Unreal)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats fbx

# USD only (for Houdini)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats usda

# Both (default)
python src/growpy/cli/convert_twigs_v2.py data/assets/twigs --formats fbx usda
```

## What Gets Fixed

### Before (Original Converter)

```
BeechTwigA.fbx - 700 KB
└─ Material: Beech (solid color only)
   └─ No textures embedded
```

### After (V2 Converter)

```
european_beech_apical.fbx - 3.2 MB
└─ Material: EuropeanBeech_Beech
   ├─ Diffuse: BeechDiffuse.jpg ✓
   ├─ Alpha: BeechAlpha.jpg ✓
   ├─ Normal: BeechNormal.jpg ✓
   └─ Translucent: BeechTranslucent.jpg ✓
```

## Standardized Names

Old names → New names:

| Original | Standardized | Grove Attribute |
|----------|-------------|-----------------|
| BeechApicalTwig | european_beech_apical | twig_long |
| BeechLateralTwig | european_beech_lateral | twig_short |
| BeechTwigA | european_beech_var_a | (variation) |
| ScotsPineVariationCLateral | scots_pine_lateral_var_c | twig_short |
| OakEuropeanLongTwig | european_oak_apical | twig_long |

## Texture Types Detected

The v2 converter automatically finds and uses:

- **Diffuse/Albedo** - Base color
- **Alpha/Opacity** - Transparency cutout
- **Normal/Bump** - Surface detail
- **Translucent** - Light transmission
- **Roughness** - Surface smoothness
- **Metallic** - Metalness
- **AO** - Ambient occlusion

Plus special patterns:

- **Top/Bottom** - Leaf two-sided textures

## Verify Success

After conversion, check:

1. **File size increased** - FBX should be larger (textures embedded)
2. **Import in Unreal** - All material slots filled
3. **Manifest created** - `twig_manifest.json` in each folder
4. **Texture files copied** - Textures in output directory

## Troubleshooting

### No textures found

- Check `textures/` subfolder exists
- Verify texture file extensions (.png, .jpg)
- Look for typos in filenames

### Material still shows color only

- Check Blender console output for errors
- Verify texture files are not corrupt
- Re-run conversion with verbose output

### Wrong twig type assigned

- Check `twig_manifest.json` for classification
- Rename objects in blend file if needed
- Use variation letters (A/B/C) appropriately

## Next Steps

1. **Test on one species** - Start with European Beech
2. **Verify in Unreal** - Import and check materials
3. **Convert all species** - If successful
4. **Update PCG graphs** - Use new standardized names

## Documentation

- Full guide: `docs/growpy/TWIG_CONVERSION_V2.md`
- Investigation: `docs/TWIG_TEXTURE_AUDIT.md`
- Texture guide: `docs/growpy/TEXTURE_IMPLEMENTATION.md`
