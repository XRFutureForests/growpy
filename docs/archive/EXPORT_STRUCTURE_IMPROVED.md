# Forest Export Structure Improvements

## Summary

Improved forest export to ensure all assets are properly copied in all requested formats (FBX and USD) with a clearer, species-organized folder structure.

## Date

2025-10-07

## Changes Made

### 1. Fixed Twig Asset Copying

**Problem:** Twigs were only copied in USD format, not FBX format when both formats were requested.

**Solution:** Updated `bundle_twigs_for_species()` function to:

- Respect the `formats` parameter and copy files in all requested formats
- Try multiple extensions (`.usda`, `.usd`, `.fbx`) to find available files
- Avoid duplicate texture copying with a tracking set

### 2. Improved Species Twig Detection

**Problem:** Beech twigs weren't detected because they use `var_a`, `var_b` naming instead of `apical`/`lateral`.

**Solution:** Updated `get_twig_usd_map_for_species()` to:

- Add `var_a`, `var_b`, `var_c`, `var_d`, `var_e` to keyword mapping
- Implement generic fallback that assigns available twigs when no keywords match
- More robust handling of different twig naming conventions

### 3. Restructured Output Folder Hierarchy

**Problem:** Mixed species and format folders at same level was confusing.

**Before:**

```
data/output/forest/
├── FBX/
│   ├── Beech_var1.fbx
│   └── Oak_var1.fbx
├── USD/
│   ├── Beech_var1.usda
│   └── Oak_var1.usda
├── Beech/
│   └── twigs/  (empty!)
├── Oak/
│   └── twigs/  (only USD files)
└── Metadata/
```

**After:**

```
data/output/forest/
├── Beech/
│   ├── FBX/
│   │   └── Beech_var1.fbx
│   ├── USD/
│   │   ├── Beech_var1.usda
│   │   ├── Beech_var1_tree_only.usda
│   │   ├── Beech_var1_NaniteAssembly.usda
│   │   └── Beech_var1_NaniteAssembly_Skeletal.usda
│   └── twigs/
│       ├── europeanbeech_var_a.fbx
│       ├── europeanbeech_var_a.usda
│       ├── europeanbeech_var_a_NaniteAssembly.usda
│       ├── europeanbeech_var_b.fbx
│       ├── europeanbeech_var_b.usda
│       ├── europeanbeech_var_b_NaniteAssembly.usda
│       ├── textures/
│       └── twig_manifest.json
├── Oak/
│   ├── FBX/
│   │   └── Oak_var1.fbx
│   ├── USD/
│   │   ├── Oak_var1.usda
│   │   ├── Oak_var1_tree_only.usda
│   │   ├── Oak_var1_NaniteAssembly.usda
│   │   └── Oak_var1_NaniteAssembly_Skeletal.usda
│   └── twigs/
│       ├── europeanoak_apical.fbx
│       ├── europeanoak_apical.usda
│       ├── europeanoak_lateral.fbx
│       ├── europeanoak_lateral.usda
│       ├── textures/
│       └── twig_manifest.json
└── Metadata/
    ├── Beech_metadata.json
    ├── Oak_metadata.json
    └── import_metadata.json
```

## Benefits

1. **Complete Asset Coverage:** All twigs now copied in both FBX and USD formats when requested
2. **Clear Organization:** Species-based folders with format subfolders make navigation intuitive
3. **Better Portability:** Each species folder is self-contained with all its assets
4. **Robust Detection:** Generic fallback ensures twigs are found even with non-standard naming
5. **Unreal-Friendly:** Structure aligns with typical Unreal Engine asset organization patterns

## Code Changes

### Modified Files

- `src/growpy/io/blender_export.py`:
  - `batch_export_trees_for_unreal()`: Create species-specific directories
  - `bundle_twigs_for_species()`: Copy all requested formats, handle duplicates
  - `get_twig_usd_map_for_species()`: Enhanced keyword matching + generic fallback

## Testing

Verified with command:

```bash
python ./src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats fbx usda
```

**Results:**

- Oak: 8 twig files copied (4 FBX + 4 USD)
- Beech: 6 twig files copied (3 FBX + 3 USD)
- All textures copied correctly
- Clear folder structure maintained

## Next Steps

Consider:

1. Add validation that all requested formats were successfully copied
2. Create symbolic links for duplicate twig assignments (twig_upward → twig_short)
3. Document twig naming conventions for different species
4. Add format-specific subdirectories for textures if needed
