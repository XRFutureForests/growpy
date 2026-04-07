# generate_forest.py Refactoring Plan

Phase 2 of the `refactor/io-cli-restructure` branch.

## Current State

`src/growpy/cli/generate_forest.py` -- 1,655 lines, 8 functions, no external
callers (CLI-only entry point via `main()`).

### Function Inventory

| Function | Lines | Size | Group |
|---|---|---|---|
| `_handle_bone_limit_error()` | 52-69 | 18 | error handling |
| `_is_bone_limit_error()` | 72-76 | 5 | error handling |
| `_derive_static_from_skeletal()` | 79-161 | 83 | USD derivation |
| `_export_single_tree_from_forest()` | 164-779 | 616 | export worker |
| `export_individual_trees()` | 782-898 | 117 | export orchestration |
| `generate_forest_stages()` | 901-1433 | 533 | multi-stage pipeline |
| `generate_forest_exports()` | 1436-1585 | 150 | standard pipeline |
| `main()` | 1588-1655 | 67 | CLI + dispatch |

Two dominant functions: `_export_single_tree_from_forest` (37% of file) and
`generate_forest_stages` (32% of file). Together they account for 69%.

### Architectural Observation

The file implements **two distinct forest generation pipelines** selected at
runtime:

- **Pipeline A** (multi-stage): `generate_forest_stages()` -- height-threshold
  snapshots at intervals (e.g. every 4m). Exports trees at each milestone.
- **Pipeline B** (standard): `generate_forest_exports()` -- single growth
  simulation, exports trees by growth cycle.

Both pipelines delegate to the same export worker
(`_export_single_tree_from_forest`) but differ substantially in simulation
control flow and snapshot management.

## Problems

1. **`_export_single_tree_from_forest` is 616 lines** -- mixes skeleton
   building, mesh export, wind JSON, PVE generation, preview, and memory
   cleanup in one function.

2. **`generate_forest_stages` is 533 lines** -- mixes simulation orchestration,
   height-threshold logic, variant management, and post-export assembly/PVE
   generation.

3. **No unit testability** -- everything chains through massive functions with
   many side effects (file I/O, Grove API calls, bpy operations).

4. **Duplicated post-export logic** -- both pipelines generate wind JSON,
   PVE presets, Unreal scripts, and Helios exports with slightly different
   calling patterns.

## Proposed Extraction

### Target Module: `core/export.py`

Extract **export-related functions** that are independent of simulation control
flow. These operate on already-simulated grove data and produce output files.

**Functions to extract:**

| Function | Current | New Location | Reason |
|---|---|---|---|
| `_handle_bone_limit_error()` | generate_forest | core/export.py | Pure error messaging |
| `_is_bone_limit_error()` | generate_forest | core/export.py | Pure error classification |
| `_derive_static_from_skeletal()` | generate_forest | core/export.py | USD file operation |
| `_export_single_tree_from_forest()` | generate_forest | core/export.py | Core export worker |
| `export_individual_trees()` | generate_forest | core/export.py | Export orchestration |

**Functions that stay in `generate_forest.py`:**

| Function | Reason |
|---|---|
| `generate_forest_stages()` | Pipeline A -- simulation + snapshot control |
| `generate_forest_exports()` | Pipeline B -- simulation + cycle control |
| `main()` | CLI argument parsing + dispatch |

### What Stays vs What Moves

```
generate_forest.py (after)
  main()                          CLI + dispatch (67 lines)
  generate_forest_stages()        Pipeline A (533 lines)
  generate_forest_exports()       Pipeline B (150 lines)
  TOTAL: ~750 lines

core/export.py (new)
  _handle_bone_limit_error()      Error guidance (18 lines)
  _is_bone_limit_error()          Error check (5 lines)
  _derive_static_from_skeletal()  Skeletal -> static (83 lines)
  _export_single_tree_from_forest()  Per-tree export (616 lines)
  export_individual_trees()       Dispatch over groves (117 lines)
  TOTAL: ~839 lines
```

### Follow-up: Decompose `_export_single_tree_from_forest` (optional)

After the extraction, the 616-line worker can be further split into smaller
functions within `core/export.py`:

- `_build_tree_skeleton()` -- skeleton building + bone tagging (~50 lines)
- `_export_tree_variant()` -- per-density-variant export loop body (~200 lines)
- `_generate_tree_preview()` -- preview image generation (~50 lines)

This is a separate follow-up and should NOT be combined with the initial
extraction to minimize risk.

## Risks

| Risk | Mitigation |
|---|---|
| `_export_single_tree_from_forest` has 15+ parameters | Keep exact same signature, just move the function |
| `generate_forest_stages` calls `_derive_static_from_skeletal` directly | Import from new location |
| No external callers of any function | File is CLI-only, safe to reorganize |
| bpy crash in pytest on Windows | Pre-existing, unrelated to this work |
| Subtle cross-function state (logger, config) | All passed explicitly or via module logger |

## Implementation Steps

1. Create `src/growpy/core/export.py` with module docstring
2. Move the 5 functions (preserve exact signatures and logic)
3. Update `generate_forest.py` imports:
   `from growpy.core.export import export_individual_trees, _derive_static_from_skeletal, _is_bone_limit_error`
4. Move associated imports (bpy, pxr, etc.) to `core/export.py`
5. Verify: `conda run -n growpy python src/growpy/cli/generate_forest.py data/input/test_single.csv`
6. Commit: `"Extract export functions from generate_forest into core/export"`

## Testing

- Import verification: all moved functions importable from `growpy.core.export`
- Dry run: `generate_forest.py` with test CSV (validates import chain)
- No new unit tests needed for the extraction itself (behavior unchanged)

## Decision

This is a **move-only refactoring** -- no logic changes, no API changes. The
functions keep their exact signatures, parameters, and behavior. The only change
is file location and import paths.

Priority: **medium** -- improves readability and sets up future decomposition,
but carries regression risk on the most critical pipeline file.

Recommendation: execute on a clean branch after the current refactoring branch
is merged and verified in production.
