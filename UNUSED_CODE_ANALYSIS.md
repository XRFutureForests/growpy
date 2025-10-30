# GrowPy Code Cleanup Summary

Analysis and cleanup of unused functions and modules in the growpy package.

## Cleanup Results

### Before Cleanup

- **Total exported functions in `__init__.py`**: 19
- **Functions imported by CLI scripts**: 19 (7 actually used, 12 unused)
- **Unused public functions**: 65 functions across 17 modules
- **Total unused exports**: 12 functions exported but not used by CLI

### After Cleanup

- **Total exported functions in `__init__.py`**: 7 (reduced by 63%)
- **Unused public functions**: 41 (reduced from 65, -37%)
- **Files with unused functions**: 12 (reduced from 17, -29%)
- **Modules removed**: 5 completely unused modules deleted

## Changes Made

### 1. Deleted Unused Modules (5 files)

- `io/unreal_metadata.py` - All 7 functions unused
- `io/nanite.py` - Duplicate functions (already in blender_export.py)
- `config/quality.py` - All 2 LOD functions unused
- `config/species.py` - All 4 color/texture functions unused
- `config/paths.py` - All 9 path functions unused

### 2. Cleaned Main API (`__init__.py`)

Reduced from 19 exports to 7 essential functions:

- `GrowPyConfig` - Configuration class
- `get_config` - Config accessor
- `create_forest` - Forest creation
- `simulate_forest_growth` - Growth simulation
- `create_grove` - Single-species grove
- `calculate_growth_cycles_from_height` - Height-to-age conversion
- `EXPORT_AVAILABLE` - Export capability flag

### 3. Streamlined Module Exports

- **config/**init**.py**: Reduced from 28 to 2 exports
- **core/**init**.py**: Reduced from 9 to 4 exports
- **io/**init**.py**: Reduced from 28 to 20 exports (removed metadata/nanite)

## Summary (Original Analysis)

## Unused Exports in `__init__.py`

These functions are exported in the main `__init__.py` but never imported by any CLI script:

1. `add_tree_to_grove` - Tree addition helper
2. `apply_species_color_settings` - Color configuration
3. `batch_export_tree_usd` - Batch USD export
4. `batch_export_trees_for_unreal` - Batch Unreal export
5. `build_grove_with_all_attributes` - Grove building with attributes
6. `build_skeletons` - Skeleton generation
7. `create_forest_with_attributes` - Forest creation with attributes
8. `create_nanite_assembly_usd` - Nanite assembly creation
9. `export_tree_as_usd` - Single tree USD export
10. `export_twigs_from_blend` - Twig conversion from Blender
11. `get_model_attributes` - Model attribute retrieval
12. `set_global_config` - Configuration setter

## Functions Used but Not Exported

These functions are used by CLI scripts but not in the public API (`__all__`):

1. `SpeciesGrowthAnalyzer` - Growth analysis class
2. `_get_gc` - Grove core accessor
3. `bundle_twigs_for_species` - Twig bundling helper
4. `export_grove_tree_as_usda_native` - Native USDA export
5. `export_twig_placements_to_usd` - Twig placement export
6. `extract_twig_placements_from_mesh` - Twig placement extraction
7. `get_quality_preset` - Quality settings
8. `get_twig_usd_map_for_species` - Twig USD mapping
9. `place_twigs_in_blender` - Blender twig placement
10. `print_validation_results` - Validation output
11. `validate_skeletal_structure` - Skeleton validation
12. `validate_twig_skeletal_structure` - Twig skeleton validation

## Unused Functions by Module

### config/core.py (6 unused)

- `from_config_file()` - Load config from file
- `get_global_config()` - Get global configuration
- `get_lod_configs()` - Get LOD configurations
- `get_species_colors()` - Get species color mapping
- `set_global_config()` - Set global configuration
- `to_config_file()` - Save config to file

### config/paths.py (9 unused)

- `get_bark_texture_path()` - Bark texture path resolution
- `get_best_twig_file_for_type()` - Twig file selection
- `get_data_directory()` - Data directory path
- `get_twig_directory_path()` - Twig directory path
- `get_twig_for_species()` - Species twig lookup
- `get_twig_material_path()` - Twig material path
- `get_twig_prototype_path()` - Twig prototype path
- `get_twig_textures_path()` - Twig texture path
- `get_twig_usd_directory_path()` - Twig USD directory path

### config/quality.py (2 unused)

- `get_all_lod_configs()` - All LOD configurations
- `get_lod_configs()` - LOD configurations

### config/species.py (4 unused)

- `get_bark_texture()` - Bark texture retrieval
- `get_species_colors()` - Species color lookup
- `get_standardized_name()` - Name standardization
- `hex_to_rgb()` - Color conversion

### core/forest.py (1 unused)

- `create_forest_with_attributes()` - Forest creation with attributes

### core/tree.py (3 unused)

- `apply_species_color_settings()` - Apply color settings
- `build_grove_with_all_attributes()` - Build grove with attributes
- `get_model_attributes()` - Get model attributes

### io/blender_export.py (7 unused)

- `add_nanite_attributes_to_usd()` - Add Nanite metadata
- `batch_export_tree_usd()` - Batch USD export
- `batch_export_trees_for_unreal()` - Batch Unreal export
- `copy_shader_children()` - Shader copying
- `export_tree_as_usd()` - Single tree USD export
- `export_twigs_from_blend()` - Twig conversion
- `validate_mesh_for_nanite()` - Nanite validation

### io/blender_twig_processor.py (6 unused)

- `add_skeleton_to_usd_file()` - Add skeleton to USD
- `classify_texture_from_name()` - Texture classification
- `fix_texture_paths_in_usd()` - Fix texture paths
- `process_twig_file()` - Process twig file
- `setup_materials_with_textures()` - Material setup
- `update_material_paths()` - Material path updates

### io/nanite.py (2 unused)

- `add_nanite_attributes_to_usd()` - Add Nanite attributes
- `validate_mesh_for_nanite()` - Validate Nanite mesh

### io/skeleton_from_bones.py (1 unused)

- `add_skeleton_from_grove_bones()` - Skeleton from bones

### io/twig_placement.py (6 unused)

- `convert_blender_normal_to_ue()` - Normal conversion
- `convert_blender_to_ue_coords()` - Coordinate conversion
- `convert_y_up_normal_to_z_up()` - Normal conversion
- `convert_y_up_to_z_up()` - Coordinate conversion
- `create_geometry_nodes_twig_instancer()` - Geometry nodes
- `place_twigs_in_blender()` - Twig placement

### io/unreal_metadata.py (7 unused)

- `calculate_density_from_spacing()` - Density calculation
- `calculate_spacing_from_crown_radius()` - Spacing calculation
- `create_forest_metadata()` - Forest metadata
- `create_metadata_from_growth_data()` - Metadata from growth
- `load_metadata()` - Load metadata
- `save()` - Save metadata
- `to_json()` - JSON export

### io/unreal_nanite_assembly.py (2 unused)

- `copy_prim_hierarchy()` - Copy USD prim hierarchy
- `export_tree_as_nanite_assembly()` - Nanite assembly export

### io/usd_builder.py (3 unused)

- `add_twig_skeleton_to_usd()` - Add twig skeleton
- `create_material()` - Create USD material
- `to_tuple()` - Tuple conversion

### utils/analysis.py (2 unused)

- `generate_lookup_table_summary()` - Lookup table summary
- `update_lookup_table_with_new_models()` - Update lookup table

### utils/paths.py (2 unused)

- `ensure_dir()` - Directory creation
- `ensure_parent_dir()` - Parent directory creation

### utils/strings.py (2 unused)

- `sanitize_filename()` - Filename sanitization
- `sanitize_species_name()` - Species name sanitization

## Recommendations

### Critical: Keep (Core Functionality)

These are internal/implementation details used indirectly:

- All validation functions (used via CLI imports)
- Grove core accessors (`_get_gc`)
- Quality presets (`get_quality_preset`)
- Twig helpers (`bundle_twigs_for_species`, `get_twig_usd_map_for_species`)

### Cleanup: Remove or Mark Private

These appear to be unused legacy code:

1. **Config Module**: Most path resolution functions could be internalized or removed
2. **Export Module**: `batch_export_*` functions are unused, replaced by parallel processing in CLI
3. **Metadata Module**: `unreal_metadata.py` functions appear unused
4. **Utils**: Path and string utilities have minimal usage

### Potential Consolidation

- Merge `config/paths.py` into `config/core.py`
- Merge `config/quality.py` into `io/blender_export.py` (where it's used)
- Merge `config/species.py` functions into lookup table handling

## Module Structure Analysis

### Active Modules (Used by CLI)

- `config/core.py` - Configuration management
- `core/forest.py` - Forest creation
- `core/grove.py` - Grove management
- `io/blender_export.py` - Export functionality
- `io/usd_validation.py` - Validation tools
- `io/twig_placement.py` - Twig placement
- `utils/analysis.py` - Growth analysis

### Underutilized Modules

- `config/paths.py` - Most functions unused (9/9)
- `config/quality.py` - Most functions unused (2/2)
- `config/species.py` - Most functions unused (4/4)
- `io/unreal_metadata.py` - All functions unused (7/7)
- `io/nanite.py` - Duplicates functions in blender_export (2/2)

### Total Unused Code

- **65 public functions** across 17 files
- **12 exported functions** in main API but not used
- **4 entire modules** with all functions unused (quality.py, species.py, unreal_metadata.py, nanite.py)

## Next Steps

1. Review unused exports and remove from `__all__` if not part of public API
2. Consider making internal functions private (prefix with `_`)
3. Remove completely unused modules (unreal_metadata.py, nanite.py duplicates)
4. Consolidate underutilized config modules
5. Update documentation to reflect actual public API surface
