# Export Module Refactoring Plan

## Overview

Refactor the GrowPy export modules to have a cleaner, more logical structure that separates concerns and removes technology-specific naming (Blender, Unreal).

## Current Structure

```
src/growpy/io/
├── blender_export.py       # Orchestration + twig export + material handling
├── usd_builder.py          # USD creation with mesh geometry
├── skeleton_from_bones.py  # Skeleton creation and binding
├── unreal_nanite_assembly.py  # Assembly composition
├── twig_placement.py       # Twig data extraction
└── usd_validation.py       # Validation utilities
```

## New Structure

```
src/growpy/
├── core/
│   ├── forest.py           # Forest simulation (existing)
│   ├── grove.py            # Grove wrapper (existing)
│   ├── tree.py             # Tree class (existing)
│   ├── skeleton.py         # NEW - Moved from io/skeleton_from_bones.py
│   └── twig.py             # NEW - Moved from io/twig_placement.py
│
## Module Responsibilities

### Core Modules (src/growpy/core/)

#### 1. `skeleton.py` (NEW - moved from io/skeleton_from_bones.py)

**Purpose**: Skeleton structure creation and vertex skinning (core logic, no I/O)

**Key Functions**:
- `build_skeleton_structure(bones_info)` - Build joint hierarchy from bone data
- `calculate_vertex_weights(model, bones_info)` - Skinning weight calculation
- `create_joint_hierarchy(bones_info)` - Create parent-child relationships

**Why in core/**: Pure computation on bone data structures, no file I/O

#### 2. `twig.py` (NEW - moved from io/twig_placement.py)
**Key Functions**:
- `export_tree(grove, output_path, ...)` - Main entry point (replaces `export_grove_tree_as_usda_native()`)
- `build_tree_mesh(model, output_path, ...)` - Creates mesh geometry (replaces `build_tree_usd()`)
- `add_tree_materials(stage, material_path, ...)` - Material setup
- `add_skeleton_to_stage(stage, grove, skeleton_builder)` - Add skeleton to USD (uses core/skeleton.py)
- `get_twig_usd_map_for_species(species, ...)` - Twig asset lookup

**Consolidates**:
- Grove API orchestration (tag_bone_id, build_models, triangulate)
- USD stage creation and mesh geometry export
- Material and texture handling
- Inline skeleton creation (uses `core.skeleton` for computation)er)
│   └── assembly.py         # RENAMED from unreal_nanite_assembly.py
│
└── config/
    ├── quality.py          # Quality presets (existing, consolidate export.py here)
    └── ...
```

## Module Responsibilities

### 1. `tree_export.py` (NEW - combines blender_export + usd_builder)

**Purpose**: Export skeletal tree meshes from pre-simulated groves

**Key Functions**:

#### 4. `twig_export.py` (RENAMED from blender_twig_processor.py)

**Purpose**: Export twig meshes from .blend files to USD

**Key Functions**:

- `export_twigs_from_blend(blend_path, output_dir)` - Twig export from .blend files
- `create_single_bone_skeleton()` - Add root skeleton to twig
- `process_twig_directory(twig_dir, output_dir)` - Batch twig processing

**Changes**:

- Rename file: `blender_twig_processor.py` → `twig_export.py`
- Keep all Blender .blend file processing logic

#### 5. `assembly.py` (RENAMED from unreal_nanite_assembly.py)

- Move `export_twigs_from_blend()` → keep as-is
- Move material handling logic → consolidate in `add_tree_materials()`

**Purpose**: Compose final assembly from tree + twig meshes

**Key Functions**:

- `create_assembly(tree_usd_path, twig_usd_paths, ...)` - Main assembly creation (replaces `create_nanite_assembly_usd()`)
- `validate_assembly(assembly_path)` - Assembly validation (replaces `validate_nanite_assembly()`)
- `add_twig_instances(stage, twig_placements, ...)` - PointInstancer setup (uses core/twig.py)

**Changes**:

- Rename file: `unreal_nanite_assembly.py` → `assembly.py`
- Rename function: `create_nanite_assembly_usd()` → `create_assembly()`
- Keep Unreal-specific schema application (NaniteAssemblyRootAPI) but make it optional
- Uses `core.twig` for twig placement calculations

### Config Module (src/growpy/config/)

#### 6. `quality.py` (ENHANCED - consolidate io/export.py)

**Purpose**: Quality preset configuration for tree building

**Changes**:

- Move `get_quality_preset()` from `io/export.py` to here
- Consolidate with existing `get_lod_configs()`
- Delete `io/export.py` after migration

### Files to Remove

- `io/export.py` - Quality presets moved to config/quality.py
- `io/usd_validation.py` - Only used once, inline the validation logic where needednces(stage, twig_data, ...)` - PointInstancer setup

**Changes**:

- Rename file: `unreal_nanite_assembly.py` → `assembly.py`
- Rename function: `create_nanite_assembly_usd()` → `create_assembly()`
- Rename function: `validate_nanite_assembly()` → `validate_assembly()`
- Keep Unreal-specific schema application (NaniteAssemblyRootAPI) but make it optional
- Keep PointInstancer logic for twig placement
- Keep USD composition (references, prototypes)

### 4. `twig_placement.py` (UNCHANGED)

**Purpose**: Extract twig placement data from USD primvars

**Key Functions**:

- `extract_twig_placements(tree_usd_path)` - Extract twig data from tree mesh

**Changes**: None - this module is already well-named

### 5. `usd_validation.py` (UNCHANGED)

**Purpose**: USD file validation utilities

**Changes**: None

## Migration Steps

### Step 1: Move quality presets to config

1. Add `get_quality_preset()` to `src/growpy/config/quality.py`
2. Update imports in `cli/generate_forest.py` and `io/__init__.py`
3. Delete `src/growpy/io/export.py`

### Step 2: Move skeleton logic to core

1. Create `src/growpy/core/skeleton.py`
2. Move pure computation functions from `io/skeleton_from_bones.py`:
   - Bone hierarchy building
   - Joint indices calculation
   - Vertex weight calculation
3. Keep these as pure functions (no USD I/O)

### Step 3: Move twig logic to core

1. Create `src/growpy/core/twig.py`
2. Move twig placement extraction from `io/twig_placement.py`:
   - Twig data structures
   - Transform calculations
   - Pure geometric operations
3. Keep these as pure functions (no USD I/O)

### Step 4: Create `tree_export.py`

1. Create new file `src/growpy/io/tree_export.py`
2. Copy and merge content from:
   - `blender_export.py` (orchestration, export_grove_tree_as_usda_native)
   - `usd_builder.py` (build_tree_usd, geometry extraction)
3. Rename functions:
   - `export_grove_tree_as_usda_native()` → `export_tree()`
   - `build_tree_usd()` → `build_tree_mesh()`
4. Update to use `core.skeleton` and `core.twig` for computations
5. Keep only USD I/O logic here

### Step 5: Rename `blender_twig_processor.py` → `twig_export.py`

1. Rename file
**Import changes**:

```python
# OLD
from growpy.io.blender_export import export_grove_tree_as_usda_native, get_quality_preset
from growpy.io.usd_builder import build_tree_usd
from growpy.io.skeleton_from_bones import add_skeleton_to_usd
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd
from growpy.io.twig_placement import extract_twig_placements_from_mesh
from growpy.io.blender_twig_processor import export_twigs_from_blend

# NEW
from growpy.config.quality import get_quality_preset
from growpy.core.skeleton import build_skeleton_structure, calculate_vertex_weights
from growpy.core.twig import extract_twig_data, TwigPlacement
from growpy.io.tree_export import export_tree, build_tree_mesh
from growpy.io.twig_export import export_twigs_from_blend
from growpy.io.assembly import create_assembly
```

### Step 8: Update Documentationm the old modules

**Files to update**:

- `src/growpy/cli/generate_forest.py` - Main CLI
- `src/growpy/cli/export_trees.py` - Export CLI
- Any test files in `tests/`

**Import changes**:

```python
# OLD
from growpy.io.blender_export import export_grove_tree_as_usda_native
from growpy.io.usd_builder import build_tree_usd
from growpy.io.skeleton_from_bones import add_skeleton_to_usd
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd

# NEW
from growpy.io.tree_export import export_tree, build_tree_mesh
from growpy.io.skeleton import add_skeleton_to_stage
from growpy.io.assembly import create_assembly
```

### Step 5: Update Documentation

Update these documentation files:

### Step 9: Remove Old Files

After verifying all imports and tests pass:

1. Delete `src/growpy/io/export.py`
2. Delete `src/growpy/io/blender_export.py`
3. Delete `src/growpy/io/usd_builder.py`
4. Delete `src/growpy/io/skeleton_from_bones.py`
5. Delete `src/growpy/io/unreal_nanite_assembly.py`
6. Delete `src/growpy/io/twig_placement.py` (moved to core)
7. Delete `src/growpy/io/blender_twig_processor.py` (renamed)
8. Delete `src/growpy/io/usd_validation.py` (inline where needed)

### Step 10: Test Everythingender_export.py`

2. Delete `src/growpy/io/usd_builder.py`
3. Delete `src/growpy/io/skeleton_from_bones.py`
4. Delete `src/growpy/io/unreal_nanite_assembly.py`

### Step 7: Test Everything

Run full test suite:

```bash
# Activate environment
conda activate the-grove

# Run tests
pytest tests/

# Test pipeline
python src/growpy/cli/run_pipeline.py

# Test forest generation
python src/growpy/cli/generate_forest.py --quality medium --growth-cycle-limit 2
```

## Benefits of This Refactor

1. **Clearer Separation of Concerns**:
   - Tree export is self-contained
   - Skeleton creation is isolated
   - Assembly composition is separate

2. **Technology-Agnostic Naming**:
   - No "Blender" in tree export (implementation detail)
   - No "Unreal Nanite" in assembly (can be used for other engines)

3. **Easier to Maintain**:

## Implementation Checklist

- [ ] Move `get_quality_preset()` to `config/quality.py`
- [ ] Create `core/skeleton.py` with pure computation logic
- [ ] Create `core/twig.py` with pure computation logic
- [ ] Create `io/tree_export.py` with merged blender_export + usd_builder
- [ ] Rename `io/blender_twig_processor.py` → `io/twig_export.py`
- [ ] Rename `io/unreal_nanite_assembly.py` → `io/assembly.py`
- [ ] Update all function names for consistency
- [ ] Update imports in `cli/generate_forest.py`
- [ ] Update imports in `cli/export_trees.py`
- [ ] Update imports in `io/__init__.py`
- [ ] Update imports in test files
- [ ] Update module docstrings
- [ ] Run full test suite
- [ ] Verify forest generation works
- [ ] Delete old files
- [ ] Update remaining documentation (DEPENDENCY_DIAGRAM.md)
- [ ] Commit changes

## Timeline Estimate

- Step 1 (Quality presets): 30 minutes
- Steps 2-3 (Move to core/): 1-2 hours
- Step 4 (Create tree_export.py): 2-3 hours
- Steps 5-6 (Rename modules): 30 minutes
- Step 7 (Update imports): 1-2 hours
- Step 8 (Update docs): 1 hour
- Steps 9-10 (Testing & cleanup): 1-2 hours

**Total**: ~7-11 hours for complete refactor

## Timeline Estimate

## Key Design Decisions

1. **Why move skeleton and twig to core/?**
   - These contain pure computational logic (bone hierarchy, vertex weights, twig transforms)
   - No file I/O operations
   - Can be unit tested without USD dependencies
   - Clearer separation: core = computation, io = file operations

2. **Why separate twig_export.py from tree_export.py?**
   - Different input format (.blend files vs Grove objects)
   - Different processing pipeline (Blender API vs Grove API)
   - Keeps tree_export.py focused on tree-specific logic

3. **Why consolidate quality presets in config/?**
   - Avoids duplication between `io/export.py` and `config/quality.py`
   - Configuration belongs in config/, not io/
   - Easier to maintain single source of truth

4. **Why remove usd_validation.py?**
   - Only used once in `convert_twigs.py`
   - Simple validation logic can be inlined
   - Reduces module count

5. **Do we need backward compatibility?**
   - No - internal API only
   - Clean break is better than deprecated shims
   - All imports are within growpy package
If issues arise:
1. Keep old files until all tests pass
2. Use git to revert changes if needed
3. Test incrementally - one module at a time

## Questions to Consider

1. Should `export_twigs_from_blend()` stay in `tree_export.py` or move to separate `twig_export.py`?
   - **Recommendation**: Keep in `tree_export.py` for now, can separate later if needed

2. Should we make assembly creation engine-agnostic with a config parameter?
   - **Recommendation**: Yes, add `engine="unreal"` parameter with schema selection

3. Do we need backward compatibility for old function names?
   - **Recommendation**: No, internal API only, clean break is fine
