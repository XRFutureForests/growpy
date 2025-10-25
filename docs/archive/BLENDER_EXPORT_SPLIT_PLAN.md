# Blender Export Split Plan

**File:** `src/growpy/io/blender_export.py`
**Size:** 4116 lines
**Target:** Split into ~10-12 focused modules

## Function Analysis

### Line Ranges by Category

**Imports & Utilities** (1-55)
- Imports, bpy/gc availability checks
- `_get_gc()`, `_check_bpy_available()`, `ensure_grove_available()`

**Nanite Functions** (56-215)
- `add_nanite_attributes_to_usd()` (56-100)
- `validate_mesh_for_nanite()` (102-214)

**Quality Presets** (216-279)
- `get_quality_preset()` (216-278)

**USD Export - Main** (281-493)
- `export_tree_as_usd()` (281-492)

**USD Assembly** (494-575)
- `create_nanite_assembly_usd()` (494-574)

**Skeleton Functions** (576-2087)
- `_calculate_vertex_weights()` (576-667)
- `_add_skeleton_to_object()` (668-851)
- `_add_skeleton_only_to_usd()` (1313-1666)
- `_add_skeleton_and_materials_to_usd()` (1667-2087)
- `_add_skeleton_to_twig_usd()` (2088-2224)

**Grove Attributes** (852-1068)
- `_add_grove_attributes_to_mesh()` (852-972)
- `_add_grove_face_attributes_to_usd()` (973-1068)
- `_add_blender_attributes_as_usd_primvars()` (1069-1166)

**Materials** (1167-2419)
- `_add_materials_to_usd()` (1167-1312)
- `_find_bark_texture()` (2225-2310)
- `_add_material_with_textures()` (2311-2390)
- `_add_simple_material()` (2391-2419)

**Twig Export** (2420-2521)
- `export_twigs_from_blend()` (2420-2521)

**FBX Export** (2522-2877)
- `_export_fbx_internal()` (2522-2876)

**Batch Export** (2878-3351)
- `batch_export_tree_usd()` (2878-2965)
- `batch_export_trees_for_unreal()` (2966-3351)

**Native USD Export** (3352-3712)
- `export_grove_tree_as_usda_native()` (3352-3712)

**Twig Utilities** (3713-4116)
- `get_twig_fbx_map_for_species()` (3713-3779)
- `get_twig_usd_map_for_species()` (3780-3942)
- `copy_bark_textures_for_species()` (3943-3988)
- `bundle_twigs_for_species()` (3989-4116)

## Proposed Module Structure

```
src/growpy/io/
├── export/
│   ├── __init__.py          # Main exports
│   ├── quality.py           # Quality presets (~70 lines) ✅ DONE
│   ├── usd.py               # USD export main functions (~800 lines)
│   ├── fbx.py               # FBX export (~400 lines)
│   ├── batch.py             # Batch export functions (~500 lines)
│   ├── skeleton.py          # Skeleton creation (~600 lines)
│   ├── attributes.py        # Grove attributes to mesh/USD (~300 lines)
│   └── materials.py         # Material and texture handling (~300 lines)
├── nanite/
│   ├── __init__.py
│   ├── attributes.py        # USD Nanite attributes (~50 lines)
│   └── validation.py        # Mesh validation (~120 lines)
├── twig/
│   ├── __init__.py
│   ├── bundling.py          # Twig bundling (~400 lines)
│   ├── placement.py         # (existing file)
│   └── processor.py         # (existing file)
└── blender_utils.py         # Shared Blender utilities (~100 lines)
```

## Implementation Strategy

### Phase 1: Extract Simple Modules (Done)
- ✅ `export/quality.py` - Quality presets

### Phase 2: Extract Nanite Functions
- `nanite/attributes.py` - add_nanite_attributes_to_usd()
- `nanite/validation.py` - validate_mesh_for_nanite()

### Phase 3: Extract Twig Functions
- `twig/bundling.py` - All twig bundle/map functions

### Phase 4: Extract Material Functions
- `export/materials.py` - All material-related functions

### Phase 5: Extract Skeleton Functions
- `export/skeleton.py` - All skeleton-related functions

### Phase 6: Extract Attributes
- `export/attributes.py` - Grove attribute functions

### Phase 7: Create Blender Utils
- `blender_utils.py` - Shared utilities (bpy checks, gc access)

### Phase 8: Extract Export Functions
- `export/usd.py` - Main USD export
- `export/fbx.py` - Main FBX export
- `export/batch.py` - Batch export functions

### Phase 9: Update Imports
- Update all files that import from blender_export
- Create compatibility layer in blender_export.py

### Phase 10: Test & Cleanup
- Test exports work
- Remove old blender_export.py
- Update documentation

## Import Dependencies

**Internal:**
- All modules need: `bpy`, `pxr` (USD), `the_grove_22_core`
- config module for paths
- utils for sanitize_species_name

**External:**
- pathlib, typing, json
- numpy (for skeleton weights)

## Backward Compatibility

Create `blender_export.py` compatibility shim:
```python
# Backward compatibility - re-export all functions
from .export import *
from .nanite import *
from .twig.bundling import *

# Mark as deprecated
import warnings
warnings.warn(
    "Importing from blender_export is deprecated. "
    "Use specific modules instead.",
    DeprecationWarning
)
```

## Testing Checklist

After split:
- [ ] Import all modules successfully
- [ ] USD export works
- [ ] FBX export works
- [ ] Skeleton export works
- [ ] Twig bundling works
- [ ] Nanite attributes work
- [ ] Batch export works
- [ ] CLI tools work

## Risk Assessment

**Low Risk:**
- Quality presets (standalone)
- Nanite functions (standalone)
- Twig bundling (standalone)

**Medium Risk:**
- Material functions (some interdependencies)
- Skeleton functions (complex but isolated)

**High Risk:**
- USD/FBX export (main functions, many dependencies)
- Batch export (calls many other functions)

## Execution Plan

1. Extract low-risk modules first
2. Test each module independently
3. Extract medium-risk modules
4. Extract high-risk modules last
5. Create compatibility layer
6. Full integration test
7. Remove old file

## Estimated Effort

- Phase 1-3 (Low risk): 1 hour
- Phase 4-6 (Medium risk): 2 hours
- Phase 7-8 (High risk): 2 hours
- Phase 9-10 (Testing): 1 hour

**Total:** ~6 hours
