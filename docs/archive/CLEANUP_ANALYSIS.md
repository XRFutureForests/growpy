# GrowPy Cleanup Analysis - Unused Functions and Modules

**Analysis Date:** 30 October 2025  
**Method:** Deep dependency tracing from CLI entry points through full call chain

## Summary

- **Total unused public functions:** 65
- **Files with unused code:** 17
- **Analysis method:** BFS trace from CLI scripts through all function calls

## Completely Unused Modules (Can be DELETED)

### 1. `src/growpy/io/skeleton_from_bones.py` ❌ ENTIRE FILE

**Status:** ZERO usage anywhere  
**Functions:**

- `add_skeleton_from_grove_bones()` - Never called

**Action:** DELETE entire file

---

## Partially Unused Modules (Functions can be REMOVED)

### 2. `src/growpy/config/core.py` (6 unused functions)

**Used:** `GrowPyConfig` class definition  
**Unused:**

- `from_config_file()`
- `get_global_config()`
- `get_lod_configs()`
- `get_species_colors()`
- `set_global_config()` - Exported in `__init__.py` but never used
- `to_config_file()`

### 3. `src/growpy/config/paths.py` (9 unused functions)

**Used:** Basic path resolution  
**Unused:**

- `get_bark_texture_path()`
- `get_best_twig_file_for_type()`
- `get_data_directory()`
- `get_twig_directory_path()`
- `get_twig_for_species()`
- `get_twig_material_path()`
- `get_twig_prototype_path()`
- `get_twig_textures_path()`
- `get_twig_usd_directory_path()`

### 4. `src/growpy/config/quality.py` (2 unused functions)

**Used:** Quality presets  
**Unused:**

- `get_all_lod_configs()`
- `get_lod_configs()`

### 5. `src/growpy/config/species.py` (4 unused functions)

**Used:** Species data lookup  
**Unused:**

- `get_bark_texture()`
- `get_species_colors()`
- `get_standardized_name()`
- `hex_to_rgb()`

### 6. `src/growpy/core/forest.py` (1 unused function)

**Used:** `create_forest()`, `simulate_forest_growth()`  
**Unused:**

- `create_forest_with_attributes()` - Exported but never called

### 7. `src/growpy/core/tree.py` (3 unused functions)

**Used:** `calculate_growth_cycles_from_height()`, `build_skeletons()`  
**Unused:**

- `apply_species_color_settings()` - Exported but never called
- `build_grove_with_all_attributes()` - Imported but never called
- `get_model_attributes()` - Exported but never called

### 8. `src/growpy/io/blender_export.py` (7 unused functions)

**Used:** Many functions (this is a core module)  
**Unused:**

- `add_nanite_attributes_to_usd()` - Duplicate in nanite.py (USED version)
- `batch_export_tree_usd()` - Exported but never called
- `batch_export_trees_for_unreal()` - Exported but never called
- `copy_shader_children()` - Internal helper, unused
- `export_tree_as_usd()` - Exported but never called
- `export_twigs_from_blend()` - Exported but never called
- `validate_mesh_for_nanite()` - Duplicate in nanite.py (USED version)

### 9. `src/growpy/io/blender_twig_processor.py` (6 unused functions)

**Used:** Main processing functions  
**Unused:**

- `add_skeleton_to_usd_file()` - Old implementation
- `classify_texture_from_name()` - Legacy
- `fix_texture_paths_in_usd()` - Legacy
- `process_twig_file()` - Old entry point
- `setup_materials_with_textures()` - Legacy
- `update_material_paths()` - Legacy

### 10. `src/growpy/io/nanite.py` (2 functions - but BOTH ARE USED)

**Status:** ✅ KEEP THIS FILE  
**Used by:** `blender_export.py` (lines 412, 484)

- `add_nanite_attributes_to_usd()` - USED
- `validate_mesh_for_nanite()` - USED

### 11. `src/growpy/io/twig_placement.py` (5 unused functions)

**Used:** `extract_twig_placements_from_mesh()`, `extract_twig_placements_from_usd()`, `export_twig_placements_to_usd()`  
**Unused:**

- `convert_blender_normal_to_ue()` - Legacy
- `convert_blender_to_ue_coords()` - Legacy
- `convert_y_up_normal_to_z_up()` - Legacy
- `convert_y_up_to_z_up()` - Legacy
- `create_geometry_nodes_twig_instancer()` - Exported but never called
- `place_twigs_in_blender()` - Only used if `--place-twigs` flag (optional feature)

**Note:** This module is needed for twig placement functionality, but some functions are unused

### 12. `src/growpy/io/unreal_metadata.py` (7 functions)

**Status:** ✅ PARTIALLY USED  
**Used by:** `blender_export.py` line 2887 calls `create_metadata_from_growth_data()`  
**Unused:**

- `calculate_density_from_spacing()` - Only called by `create_metadata_from_growth_data()`
- `calculate_spacing_from_crown_radius()` - Only called by `create_metadata_from_growth_data()`
- `create_forest_metadata()` - Never called
- `load_metadata()` - Never called
- `save()` - Method, never called
- `to_json()` - Method, never called

**Verdict:** Keep `create_metadata_from_growth_data()` and its helper functions. Remove others.

### 13. `src/growpy/io/unreal_nanite_assembly.py` (2 unused functions)

**Used:** `create_nanite_assembly_usd()` - Core function used by blender_export.py  
**Unused:**

- `copy_prim_hierarchy()` - Internal, may be used
- `export_tree_as_nanite_assembly()` - Old API

### 14. `src/growpy/io/usd_builder.py` (3 unused functions)

**Used:** Many core functions  
**Unused:**

- `add_twig_skeleton_to_usd()` - Never called
- `create_material()` - May be internal helper
- `to_tuple()` - Utility, may be internal

### 15. `src/growpy/utils/analysis.py` (2 unused functions)

**Used:** `SpeciesGrowthAnalyzer` class - Core functionality  
**Unused:**

- `generate_lookup_table_summary()` - Never called
- `update_lookup_table_with_new_models()` - Never called

### 16. `src/growpy/utils/paths.py` (2 unused functions)

**Unused:**

- `ensure_dir()` - Exported but never called
- `ensure_parent_dir()` - Exported but never called

### 17. `src/growpy/utils/strings.py` (2 unused functions)

**Unused:**

- `sanitize_filename()` - Exported but never called
- `sanitize_species_name()` - Exported but never called

---

## Recommended Actions

### PRIORITY 1: Delete Entire Files

1. ❌ `src/growpy/io/skeleton_from_bones.py` - Zero usage

### PRIORITY 2: Remove Unused Exports from `__init__.py`

Remove from `src/growpy/__init__.py`:

- `add_tree_to_grove` (only used internally)
- `apply_species_color_settings`
- `batch_export_tree_usd`
- `batch_export_trees_for_unreal`
- `build_grove_with_all_attributes`
- `build_skeletons` (only used internally)
- `create_forest_with_attributes`
- `create_nanite_assembly_usd` (only used internally)
- `export_tree_as_usd`
- `export_twigs_from_blend`
- `get_model_attributes`
- `set_global_config`

### PRIORITY 3: Clean Up Function Definitions

Can safely delete these function definitions (after confirming no internal usage):

- All functions listed in config/core.py, config/paths.py, config/quality.py, config/species.py
- Utility functions in utils/paths.py and utils/strings.py
- Legacy functions in io/blender_twig_processor.py
- Coordinate conversion functions in io/twig_placement.py

### DO NOT DELETE (Despite Not Being in CLI)

✅ **Keep these modules/functions - they ARE used:**

- `src/growpy/io/nanite.py` - BOTH functions used by blender_export.py
- `src/growpy/io/unreal_metadata.py` - `create_metadata_from_growth_data()` and helpers
- `src/growpy/io/unreal_nanite_assembly.py` - Core Nanite assembly creation
- `src/growpy/io/usd_builder.py` - Core USD building functions
- `src/growpy/io/twig_placement.py` - Extract/export functions used for twigs
- `src/growpy/utils/plotting.py` - Used by SpeciesGrowthAnalyzer

---

## Verification Commands

To verify these findings:

```bash
# Check if a function is called anywhere
grep -r "function_name(" src/growpy/

# Check imports
grep -r "from.*import.*function_name" src/growpy/
```

## Notes

- This analysis traces the FULL call chain from CLI entry points
- Functions marked as "unused" may still be called internally within their module
- Some "unused" functions might be part of a public API for future use
- Consider keeping documented public API functions even if currently unused
