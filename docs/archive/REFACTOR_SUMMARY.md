# Export Module Refactoring Summary

## Overview

This refactoring reorganizes GrowPy's export modules to create a cleaner separation between **computation** (core/) and **I/O** (io/), removes technology-specific naming, and consolidates duplicate configuration.

## Final Structure

```
src/growpy/
├── core/                      # Pure computation, no I/O
│   ├── forest.py              # (existing) Forest simulation
│   ├── grove.py               # (existing) Grove wrappers
│   ├── tree.py                # (existing) Tree class
│   ├── skeleton.py            # NEW - Bone hierarchy & vertex weights
│   └── twig.py                # NEW - Twig placement calculations
│
├── io/                        # File I/O operations
│   ├── tree_export.py         # NEW - Tree USD export (blender_export + usd_builder)
│   ├── twig_export.py         # RENAMED - Twig export from .blend (was blender_twig_processor)
│   └── assembly.py            # RENAMED - Assembly composition (was unreal_nanite_assembly)
│
└── config/                    # Configuration & presets
    ├── quality.py             # ENHANCED - Consolidated quality presets
    └── ...
```

## Key Changes

### 1. New Core Modules (Pure Computation)

**`core/skeleton.py`** - Moved from io/skeleton_from_bones.py

- Bone hierarchy building
- Joint indices calculation
- Vertex weight computation
- No USD dependencies - pure Python

**`core/twig.py`** - Moved from io/twig_placement.py  

- Twig placement extraction from Grove models
- Transform calculations
- Data structures (TwigPlacement)
- No USD dependencies - pure geometry

### 2. New IO Module (USD Export)

**`io/tree_export.py`** - Combines blender_export.py + usd_builder.py

- `export_tree()` - Main entry (was `export_grove_tree_as_usda_native()`)
- `build_tree_mesh()` - Mesh creation (was `build_tree_usd()`)
- `add_skeleton_to_stage()` - USD skeleton integration (uses `core.skeleton`)
- `add_tree_materials()` - Material handling
- Grove API orchestration (tag_bone_id, build_models)

### 3. Renamed Modules

**`io/twig_export.py`** - Was blender_twig_processor.py

- Clearer name: "export" indicates I/O operation
- Processes .blend files to USD

**`io/assembly.py`** - Was unreal_nanite_assembly.py

- Technology-agnostic name
- `create_assembly()` - Was `create_nanite_assembly_usd()`
- Uses `core.twig` for twig placement data

### 4. Enhanced Config

**`config/quality.py`** - Enhanced with quality presets

- Added `get_quality_preset()` from io/export.py
- Consolidates with existing `get_lod_configs()`
- Single source of truth for quality settings

### 5. Removed Modules

- ❌ `io/export.py` - Quality presets moved to config/
- ❌ `io/blender_export.py` - Merged into tree_export.py
- ❌ `io/usd_builder.py` - Merged into tree_export.py
- ❌ `io/skeleton_from_bones.py` - Split: computation → core/, USD I/O → tree_export.py
- ❌ `io/twig_placement.py` - Moved to core/twig.py
- ❌ `io/blender_twig_processor.py` - Renamed to twig_export.py
- ❌ `io/unreal_nanite_assembly.py` - Renamed to assembly.py
- ❌ `io/usd_validation.py` - Inline validation where needed

## Benefits

### 1. Clearer Separation of Concerns

- **core/** = Pure computation (testable without USD)
- **io/** = File I/O operations (USD export/import)
- **config/** = Configuration & presets

### 2. Technology-Agnostic Naming

- No "Blender" in tree export (implementation detail)
- No "Unreal Nanite" in assembly (can be used for other engines)
- Module names describe function, not technology

### 3. Easier Testing

- Core modules can be unit tested without USD dependencies
- Mock-free testing of computational logic
- Clearer test organization

### 4. Better Code Organization

- Related code grouped together
- Fewer files to navigate (8 → 5 in io/)
- Clear function responsibilities

### 5. Reduced Duplication

- Single quality preset source (config/quality.py)
- No duplicate skeleton logic
- Consolidated material handling

## Migration Impact

### Import Changes

```python
# OLD
from growpy.io.blender_export import export_grove_tree_as_usda_native, get_quality_preset
from growpy.io.usd_builder import build_tree_usd
from growpy.io.skeleton_from_bones import add_skeleton_to_usd
from growpy.io.twig_placement import extract_twig_placements_from_mesh
from growpy.io.blender_twig_processor import export_twigs_from_blend
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd

# NEW
from growpy.config.quality import get_quality_preset
from growpy.core.skeleton import build_skeleton_structure, calculate_vertex_weights
from growpy.core.twig import extract_twig_data, TwigPlacement
from growpy.io.tree_export import export_tree, build_tree_mesh, add_skeleton_to_stage
from growpy.io.twig_export import export_twigs_from_blend
from growpy.io.assembly import create_assembly
```

### Function Renames

| Old | New |
|-----|-----|
| `export_grove_tree_as_usda_native()` | `export_tree()` |
| `build_tree_usd()` | `build_tree_mesh()` |
| `add_skeleton_to_usd()` | `add_skeleton_to_stage()` (in tree_export) |
| `create_nanite_assembly_usd()` | `create_assembly()` |
| `validate_nanite_assembly()` | `validate_assembly()` |

### Files Affected

Need import updates:

- `src/growpy/cli/generate_forest.py`
- `src/growpy/cli/export_trees.py`
- `src/growpy/io/__init__.py`
- `tests/` - All test files

## Design Rationale

### Why Move to core/?

**Problem**: io/ mixed computation with I/O operations

**Solution**: Separate concerns

- `core/skeleton.py` - Pure bone math (no USD)
- `core/twig.py` - Pure geometry (no USD)
- `io/tree_export.py` - USD I/O only

**Benefits**:

- Unit testable without USD dependencies
- Reusable in non-USD contexts
- Clearer mental model: core = logic, io = files

### Why Merge blender_export + usd_builder?

**Problem**: Two modules for one operation (export tree)

**Solution**: Single `tree_export.py` module

**Benefits**:

- All tree export logic in one place
- No jumping between files
- Clearer entry point

### Why Rename?

**Problem**: Technology-specific names

**Solution**: Function-based names

- `twig_export.py` describes what it does
- `assembly.py` describes what it creates
- Not tied to Blender or Unreal

**Benefits**:

- Future-proof naming
- Easier to understand purpose
- Less cognitive load

### Why Remove usd_validation.py?

**Problem**: One-file, one-use module

**Solution**: Inline validation in convert_twigs.py

**Benefits**:

- Fewer files to maintain
- Simpler structure
- Validation logic close to use

## Implementation Order

1. ✅ Update documentation (DEPENDENCY_DIAGRAM.md, REFACTOR_PLAN.md)
2. ⏳ Move quality presets to config/
3. ⏳ Create core/skeleton.py
4. ⏳ Create core/twig.py
5. ⏳ Create io/tree_export.py
6. ⏳ Rename io modules
7. ⏳ Update all imports
8. ⏳ Test thoroughly
9. ⏳ Delete old files
10. ⏳ Commit changes

## Testing Strategy

### Unit Tests (New)

- Test `core/skeleton.py` functions independently
- Test `core/twig.py` functions independently
- Mock-free testing of pure computation

### Integration Tests (Update)

- Update existing tree export tests
- Update assembly creation tests
- Verify USD output unchanged

### End-to-End Tests

- Run full pipeline: `python src/growpy/cli/run_pipeline.py`
- Generate forest: `python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 2`
- Verify output files identical to pre-refactor

## Timeline

- Documentation: ✅ Complete
- Implementation: ~7-11 hours
- Testing: ~2 hours
- **Total**: ~9-13 hours

## Next Steps

1. Review and approve this plan
2. Create branch: `refactor/export-modules`
3. Implement step-by-step
4. Test incrementally
5. Merge when all tests pass
