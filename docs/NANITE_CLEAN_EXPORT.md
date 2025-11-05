# Nanite Clean Export - Material/Texture Removal

**Date:** 2025-01-07  
**Issue:** Nanite assemblies with skeletal meshes have problems with materials, textures, and masks

## Problem Statement

Unreal Engine's Nanite assemblies for skeletal meshes have known issues when USD files contain:

- Materials (USD Shade materials)
- Textures (diffuse, normal, alpha, roughness, etc.)
- Opacity masks
- UV coordinates

These cause import failures, visual artifacts, or incorrect rendering in Unreal Engine 5.7+.

## Solution

All GrowPy exports now produce **clean geometry-only USD files** without any visual appearance data. Materials and textures should be configured entirely in Unreal Engine after import using Material Instances.

## Changes Made

### 1. Tree Export (`src/growpy/io/tree_export.py`)

**Changed:**

- `clean_export` parameter now defaults to `True` (was `False`)
- Removed UV coordinate export
- Disabled material creation in `_add_usd_materials()`
- Disabled texture bundling in `bundle_twigs_for_species()`

**Impact:**

- Tree skeletal meshes export as pure geometry with skeleton only
- No materials, no textures, no UVs in tree USD files

### 2. Twig Export (`src/growpy/io/twig_export.py`)

**Changed:**

- `clean_export` forced to `True` in `add_skeleton_to_usd_file()`
- Material copying from Blender disabled (conditional block set to `if False`)
- `setup_materials_with_textures()` call disabled
- Blender USD export flags updated:
  - `export_materials=False`
  - `export_textures=False`
  - `export_uvmaps=False`
  - `export_mesh_colors=False`
  - `generate_preview_surface=False`

**Impact:**

- Twig skeletal meshes export as pure geometry with skeleton only
- No materials, no textures, no UVs in twig USD files

### 3. Twig Conversion CLI (`src/growpy/cli/convert_twigs.py`)

**Changed:**

- `clean_export` forced to `True` in `process_twig_directory()`
- Added docstring warning about Nanite compatibility

**Impact:**

- All twig conversions produce clean exports by default

### 4. Forest Generation CLI (`src/growpy/cli/generate_forest.py`)

**Changed:**

- Added `quality_params["clean_export"] = True` to quality settings
- Added comment explaining Nanite compatibility requirement

**Impact:**

- All forest generation exports produce clean USD files

### 5. Assembly Export (`src/growpy/io/assembly_export.py`)

**Changed:**

- Updated module docstring with warning about clean exports
- Disabled texture file copying when creating Nanite assemblies

**Impact:**

- Nanite assemblies reference clean USD files only
- No texture files copied to assembly output directories

## File Structure

### Before (with materials/textures)

```
species_name/
├── tree_name_skeletal.usda           # Had materials, UVs, textures
├── twig_apical_skeletal.usda         # Had materials, UVs, textures
├── twig_lateral_skeletal.usda        # Had materials, UVs, textures
├── tree_name_nanite_assembly.usda
└── textures/                          # Texture files copied
    ├── species_bark.png
    ├── twig_diffuse.png
    ├── twig_alpha.png
    └── twig_normal.png
```

### After (clean geometry)

```
species_name/
├── tree_name_skeletal.usda           # Geometry + skeleton only
├── twig_apical_skeletal.usda         # Geometry + skeleton only
├── twig_lateral_skeletal.usda        # Geometry + skeleton only
└── tree_name_nanite_assembly.usda    # References to clean USD files
```

## Unreal Engine Workflow

Since USD files no longer contain visual appearance data:

1. **Import USD** - Skeletal Nanite assemblies import cleanly without errors
2. **Create Materials** - Use Unreal's Material Editor to create bark/leaf materials
3. **Material Instances** - Create Material Instances for each species
4. **Assign Materials** - Apply materials to imported skeletal meshes in Content Browser
5. **Configure Textures** - Use Unreal's texture import and connect to materials

## Benefits

- ✅ No import errors with Nanite assemblies
- ✅ Proper skeletal mesh recognition in Unreal
- ✅ Smaller USD file sizes (geometry only)
- ✅ Better performance (no material parsing overhead)
- ✅ Full control over materials in Unreal Engine
- ✅ Industry-standard workflow (geometry in USD, appearance in engine)

## Backward Compatibility

**Breaking Change:** This is a breaking change for workflows expecting materials/textures in USD.

If you previously relied on USD materials:

- Use Unreal Material Editor to recreate materials
- Textures are still available in `data/assets/textures/` directory
- Prepare assets step (`prepare_assets.py`) still copies textures if needed

## Testing

To verify clean exports:

1. Generate a forest: `python src/growpy/cli/generate_forest.py --quality high`
2. Inspect USD files: `usdview data/output/forest/species_name/tree_skeletal.usda`
3. Verify no Materials scope exists under SkelRoot
4. Import to Unreal Engine - should import without warnings

## Related Documentation

- Unreal Nanite Assembly: <https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine>
- USD in Unreal: <https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine>
- GrowPy Documentation: `docs/guides/cli-reference.md`

## Notes

This change aligns with industry best practices:

- USD for geometry/structure
- Native engine tools for materials/appearance
- Separation of concerns (structure vs. presentation)

All future exports will maintain this clean, geometry-only approach for optimal Nanite compatibility.
