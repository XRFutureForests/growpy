# Export Module Refactoring - Visual Overview

## Before → After

### Module Organization

```
BEFORE (Current)                      AFTER (Refactored)
═══════════════════                   ═══════════════════

io/                                   core/
├── blender_export.py                 ├── forest.py ✓
├── usd_builder.py                    ├── grove.py ✓
├── skeleton_from_bones.py            ├── tree.py ✓
├── twig_placement.py                 ├── skeleton.py ← NEW (pure computation)
├── blender_twig_processor.py         └── twig.py ← NEW (pure computation)
├── unreal_nanite_assembly.py         
├── export.py                         io/
└── usd_validation.py                 ├── tree_export.py ← NEW (merged 2 files)
                                      ├── twig_export.py ← RENAMED
config/                               └── assembly.py ← RENAMED
├── quality.py (LOD only)             
└── ...                               config/
                                      ├── quality.py ← ENHANCED (+ quality presets)
                                      └── ...
```

## Function Name Changes

```
OLD NAME                              NEW NAME
════════════════════════              ════════════════════════

io.blender_export.
  export_grove_tree_as_usda_native()  → io.tree_export.export_tree()

io.usd_builder.
  build_tree_usd()                    → io.tree_export.build_tree_mesh()

io.skeleton_from_bones.
  add_skeleton_to_usd()               → [SPLIT]
                                        ├─ core.skeleton.build_skeleton_structure()
                                        └─ io.tree_export.add_skeleton_to_stage()

io.twig_placement.
  extract_twig_placements_from_mesh() → core.twig.extract_twig_data()

io.unreal_nanite_assembly.
  create_nanite_assembly_usd()        → io.assembly.create_assembly()

io.export.
  get_quality_preset()                → config.quality.get_quality_preset()
```

## Data Flow Comparison

### BEFORE: Tangled Dependencies

```
┌─────────────────────────────────────────────────────────┐
│ generate_forest.py (CLI)                                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├─→ io.export.get_quality_preset()
                 │
                 └─→ io.blender_export.export_grove_tree_as_usda_native()
                      │
                      ├─→ io.usd_builder.build_tree_usd()
                      │    │
                      │    └─→ io.skeleton_from_bones.add_skeleton_to_usd()
                      │         (MIXED: computation + USD I/O)
                      │
                      └─→ io.unreal_nanite_assembly.create_nanite_assembly_usd()
                           │
                           └─→ io.twig_placement.extract_twig_placements_from_mesh()
                                (MIXED: computation + USD I/O)
```

### AFTER: Clean Separation

```
┌─────────────────────────────────────────────────────────┐
│ generate_forest.py (CLI)                                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├─→ config.quality.get_quality_preset()
                 │    (Configuration layer)
                 │
                 └─→ io.tree_export.export_tree()
                      │
                      ├─→ io.tree_export.build_tree_mesh()
                      │    │
                      │    └─→ core.skeleton.build_skeleton_structure()
                      │         (Pure computation, no I/O)
                      │
                      └─→ io.assembly.create_assembly()
                           │
                           └─→ core.twig.extract_twig_data()
                                (Pure computation, no I/O)
```

## Layer Architecture

```
BEFORE: Mixed Concerns                AFTER: Clear Layers
═══════════════════════               ═══════════════════

┌─────────────────────┐               ┌─────────────────────┐
│ CLI Scripts         │               │ CLI Scripts         │
│ (generate_forest)   │               │ (generate_forest)   │
└─────────┬───────────┘               └─────────┬───────────┘
          │                                     │
          ├─→ Config (partial)                 ├─→ Config (complete)
          │                                     │   • quality presets
          ├─→ IO (mixed)                       │   • species data
          │   • computation                    │
          │   • file I/O                       ├─→ Core (pure logic)
          │   • config                         │   • skeleton math
          │                                     │   • twig geometry
          └─→ Core                             │   • forest simulation
              • simulation only                 │
                                                └─→ IO (pure I/O)
                                                    • USD export
                                                    • file operations
```

## Module Responsibility Matrix

| Module | Computation | USD I/O | Config | Dependencies |
|--------|-------------|---------|--------|--------------|
| **BEFORE** |
| io.blender_export | ✓ | ✓ | ✓ | Grove, USD, bpy |
| io.usd_builder | ✓ | ✓ | - | Grove, USD |
| io.skeleton_from_bones | ✓ | ✓ | - | Grove, USD |
| io.twig_placement | ✓ | ✓ | - | USD, bpy |
| io.export | - | - | ✓ | None |
| **AFTER** |
| core.skeleton | ✓ | - | - | None |
| core.twig | ✓ | - | - | None |
| io.tree_export | - | ✓ | - | core, USD, bpy |
| io.twig_export | - | ✓ | - | bpy |
| io.assembly | - | ✓ | - | core.twig, USD |
| config.quality | - | - | ✓ | None |

Legend: ✓ = Primary responsibility, - = Not responsible

## Testability Improvement

### BEFORE: Hard to Test

```
io.skeleton_from_bones.add_skeleton_to_usd()
├─ Requires USD stage (file I/O)
├─ Requires Grove instance
├─ Mixes computation with I/O
└─ Cannot unit test skeleton logic alone

Test Setup Required:
• Create temp USD file
• Mock USD operations
• Set up Grove instance
• Clean up files after
```

### AFTER: Easy to Test

```
core.skeleton.build_skeleton_structure()
├─ Pure function: bones_info → joint_hierarchy
├─ No file I/O
├─ No external dependencies
└─ Easy to unit test

Test Setup Required:
• Create simple bones_info dict
• Call function
• Assert output
(No mocking, no cleanup, no USD)
```

## Import Migration Guide

### Step 1: Update Quality Presets

```python
# OLD
from growpy.io.blender_export import get_quality_preset

# NEW
from growpy.config.quality import get_quality_preset
```

### Step 2: Update Skeleton Usage

```python
# OLD
from growpy.io.skeleton_from_bones import add_skeleton_to_usd
add_skeleton_to_usd(stage, grove, skeleton_params)

# NEW - If you need USD integration
from growpy.io.tree_export import add_skeleton_to_stage
add_skeleton_to_stage(stage, grove, skeleton_params)

# NEW - If you need pure computation
from growpy.core.skeleton import build_skeleton_structure
hierarchy = build_skeleton_structure(bones_info)
```

### Step 3: Update Tree Export

```python
# OLD
from growpy.io.blender_export import export_grove_tree_as_usda_native
export_grove_tree_as_usda_native(grove, output_path, ...)

# NEW
from growpy.io.tree_export import export_tree
export_tree(grove, output_path, ...)
```

### Step 4: Update Twig Processing

```python
# OLD
from growpy.io.blender_twig_processor import export_twigs_from_blend
from growpy.io.twig_placement import extract_twig_placements_from_mesh

# NEW
from growpy.io.twig_export import export_twigs_from_blend
from growpy.core.twig import extract_twig_data
```

### Step 5: Update Assembly Creation

```python
# OLD
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd
create_nanite_assembly_usd(tree_path, twig_paths, output_path)

# NEW
from growpy.io.assembly import create_assembly
create_assembly(tree_path, twig_paths, output_path)
```

## Files Requiring Updates

```
✓ Documentation (Complete)
  ├── DEPENDENCY_DIAGRAM.md
  ├── REFACTOR_PLAN.md
  └── REFACTOR_SUMMARY.md

⏳ Code Files (Pending)
  ├── src/growpy/config/quality.py (add get_quality_preset)
  ├── src/growpy/core/skeleton.py (create new)
  ├── src/growpy/core/twig.py (create new)
  ├── src/growpy/io/tree_export.py (create new)
  ├── src/growpy/io/twig_export.py (rename)
  ├── src/growpy/io/assembly.py (rename)
  ├── src/growpy/io/__init__.py (update exports)
  ├── src/growpy/cli/generate_forest.py (update imports)
  └── src/growpy/cli/export_trees.py (update imports)

⏳ Cleanup (After testing)
  ├── Delete: src/growpy/io/export.py
  ├── Delete: src/growpy/io/blender_export.py
  ├── Delete: src/growpy/io/usd_builder.py
  ├── Delete: src/growpy/io/skeleton_from_bones.py
  ├── Delete: src/growpy/io/twig_placement.py
  ├── Delete: src/growpy/io/blender_twig_processor.py
  ├── Delete: src/growpy/io/unreal_nanite_assembly.py
  └── Delete: src/growpy/io/usd_validation.py
```

## Success Criteria

- ✅ All tests pass
- ✅ Pipeline runs: `python src/growpy/cli/run_pipeline.py`
- ✅ Forest generation works: `python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 2`
- ✅ USD output identical to pre-refactor
- ✅ No import errors
- ✅ Core modules have no USD dependencies
- ✅ Documentation updated

## Rollback Plan

If issues arise:

1. Keep old files until fully tested
2. Use feature branch: `refactor/export-modules`
3. Git revert if needed
4. Test incrementally before deleting files
