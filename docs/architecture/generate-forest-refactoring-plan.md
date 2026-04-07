# generate_forest.py Refactoring Plan

Phase 2 of the `refactor/io-cli-restructure` branch.

## Current State

`src/growpy/cli/generate_forest.py` -- 1,886 lines, 8 functions, no external
callers (CLI-only entry point via `main()`).

### Function Inventory

| Function | Line | Group |
|---|---|---|
| `_handle_bone_limit_error()` | 55 | error handling (skeleton/Unreal-specific) |
| `_is_bone_limit_error()` | 71 | error classification (skeleton-specific) |
| `_derive_static_from_skeletal()` | 78 | USD file derivation |
| `_export_single_tree_from_forest()` | 134 | per-tree export worker (~412 lines) |
| `export_individual_trees()` | 546 | export orchestration over groves (~136 lines) |
| `generate_forest_stages()` | 682 | Pipeline A: multi-stage simulation (~527 lines) |
| `generate_forest_exports()` | 1209 | Pipeline B: standard simulation (~191 lines) |
| `main()` | 1400 | CLI + dispatch |

Two dominant blocks: the per-tree export worker plus its orchestrator
(`_export_single_tree_from_forest` + `export_individual_trees`) and the
multi-stage pipeline (`generate_forest_stages`).

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

### Why not `core/export.py`?

The original plan proposed `core/export.py`, but this conflicts with the
existing package boundaries:

- `core/` is documented as **"Core simulation logic"** and only contains
  simulation primitives: `forest.py`, `grove.py`, `tree.py`, `twig.py`,
  `skeleton.py`. No I/O lives in `core/`.
- `io/` is already organized by output target: `io/usd/`, `io/unreal/`,
  `io/helios/`. This is where file-producing code belongs.
- `_export_single_tree_from_forest` already imports from
  `growpy.io.usd.assembly_export`, `io.usd.tree_export`, `io.usd.preview`,
  and `io.unreal.unreal_scripts`. It is an `io/` consumer/orchestrator,
  not a `core/` primitive.

Putting the export worker in `core/` would invert the dependency direction
(`core` depending on `io`) and break the simulation/IO separation.

### Target: `io/forest_export.py` (new top-level `io/` module)

The per-tree worker is a **multi-format orchestrator** -- it produces USD
meshes, USD assemblies, wind JSON, PVE configs, and previews. It crosses the
`usd/`, `unreal/`, and `helios/` sub-package boundaries, so it belongs at the
`io/` top level (sibling to the format-specific sub-packages), not inside any
single sub-package.

**Functions to extract:**

| Function | New Location | Reason |
|---|---|---|
| `_export_single_tree_from_forest()` | `io/forest_export.py` | Cross-format per-tree orchestrator |
| `export_individual_trees()` | `io/forest_export.py` | Dispatch over groves; pure I/O orchestration |
| `_derive_static_from_skeletal()` | `io/usd/tree_export.py` | Pure USD file operation; co-locate with other USD tree-export logic |
| `_handle_bone_limit_error()` | `io/usd/tree_export.py` | Error guidance for the bone-limit failure raised during USD/skeleton export |
| `_is_bone_limit_error()` | `io/usd/tree_export.py` | Same scope as the handler |

Rationale for splitting bone-limit + static-derivation off into `io/usd/`
rather than dragging them into `forest_export.py`: they're single-format USD
concerns and have natural homes in the existing USD sub-package. Keeping
`io/forest_export.py` focused on the cross-format orchestration makes both
modules easier to reason about.

**Functions that stay in `cli/generate_forest.py`:**

| Function | Reason |
|---|---|
| `generate_forest_stages()` | Pipeline A -- simulation + snapshot control |
| `generate_forest_exports()` | Pipeline B -- simulation + cycle control |
| `main()` | CLI argument parsing + dispatch |

### What Stays vs What Moves

```
cli/generate_forest.py (after)
  main()                          CLI + dispatch
  generate_forest_stages()        Pipeline A (simulation control)
  generate_forest_exports()       Pipeline B (simulation control)
  ~ ~750 lines

io/forest_export.py (new)
  _export_single_tree_from_forest()  Per-tree multi-format export
  export_individual_trees()          Dispatch over groves
  ~ ~550 lines

io/usd/tree_export.py (extended)
  + _derive_static_from_skeletal()   Skeletal USD -> static USD
  + _handle_bone_limit_error()       USD/skeleton bone-limit guidance
  + _is_bone_limit_error()           USD/skeleton bone-limit check
```

### Follow-up: Decompose `_export_single_tree_from_forest` (optional)

After the extraction, the worker can be further split into smaller helpers
within `io/forest_export.py`:

- `_build_tree_skeleton()` -- skeleton building + bone tagging (~50 lines)
- `_export_tree_variant()` -- per-density-variant export loop body (~200 lines)
- `_generate_tree_preview()` -- preview image generation (~50 lines)

This is a separate follow-up and should NOT be combined with the initial
extraction to minimize risk.

## Risks

| Risk | Mitigation |
|---|---|
| `_export_single_tree_from_forest` takes a packed-tuple `args` | Keep exact same signature, just move the function |
| `generate_forest_stages` calls `_derive_static_from_skeletal` directly | Import from new location (`io/usd/tree_export.py`) |
| No external callers of any function | File is CLI-only, safe to reorganize |
| bpy crash in pytest on Windows | Pre-existing, unrelated to this work |
| Subtle cross-function state (logger, config) | All passed explicitly or via module logger |
| `forest_export.py` will need bpy at import time | Wrap with the same `try/except ImportError` pattern used by `io/__init__.py` for tree/assembly modules; expose a `FOREST_EXPORT_AVAILABLE` flag |

## Implementation Steps

1. Add `_derive_static_from_skeletal`, `_handle_bone_limit_error`, and
   `_is_bone_limit_error` to `src/growpy/io/usd/tree_export.py` (preserve
   signatures). Export them via `io/usd/tree_export.py` public surface as
   needed.
2. Create `src/growpy/io/forest_export.py` with module docstring.
3. Move `_export_single_tree_from_forest` and `export_individual_trees` into
   `io/forest_export.py`. Update their internal imports to pull
   `_derive_static_from_skeletal` / `_is_bone_limit_error` /
   `_handle_bone_limit_error` from `io.usd.tree_export`.
4. Update `cli/generate_forest.py` to import from the new locations:

   ```python
   from growpy.io.forest_export import export_individual_trees
   from growpy.io.usd.tree_export import (
       _derive_static_from_skeletal,
       _is_bone_limit_error,
   )
   ```

5. Add `forest_export` to `io/__init__.py` with the same try/except guard used
   for `tree_export` and `assembly_export`, plus a `FOREST_EXPORT_AVAILABLE`
   flag.
6. Verify: `conda run -n growpy python -m growpy.cli.generate_forest data/input/test_single.csv`
7. Commit: `"Extract export orchestration from generate_forest into io/forest_export"`

## Testing

- Import verification: all moved functions importable from
  `growpy.io.forest_export` and `growpy.io.usd.tree_export`.
- Dry run: `python -m growpy.cli.generate_forest data/input/test_single.csv`
  (validates import chain end-to-end).
- No new unit tests needed for the extraction itself (behavior unchanged).

## Decision

This is a **move-only refactoring** -- no logic changes, no API changes. The
functions keep their exact signatures, parameters, and behavior. The only change
is file location and import paths.

Priority: **medium** -- improves readability and sets up future decomposition,
but carries regression risk on the most critical pipeline file.

---

## Phase 3: Fix `io/__init__.py` inconsistency

### Phase 3 Problem

`io/__init__.py` advertises three sub-packages (`usd/`, `unreal/`, `helios/`)
but only re-exports symbols from `usd/` and `helios/`. The Unreal sub-package
(`unreal_scripts`, `wind_json`, `pve_*`, `ue_remote`) is reachable only via
fully-qualified imports. The half-and-half surface is misleading.

### Decision

**Shrink `io/__init__.py` to a layout description** rather than expanding it.
Reasons:

- The current re-exports (`build_tree_mesh`, `create_assembly`, etc.) are not
  used as `from growpy.io import build_tree_mesh` anywhere in the codebase --
  callers already use the fully-qualified `from growpy.io.usd.tree_export
  import build_tree_mesh` form.
- The `*_AVAILABLE` flags also have no internal callers; bpy/USD availability
  is checked at the call site via `try/except ImportError` directly.
- Re-exports at the package root force eager imports of bpy-dependent modules
  for anyone who touches `growpy.io`, which is the wrong default.

### Phase 3 Steps

1. Audit usages: `grep -rn "from growpy.io import" src/ tests/` and
   `grep -rn "growpy\.io\.[A-Z_]*_AVAILABLE" src/ tests/` to confirm no
   callers depend on the re-exports.
2. Replace `io/__init__.py` body with just the docstring describing the
   sub-package layout (no imports, no `__all__`).
3. If the audit finds any caller depending on the re-exports, update it to use
   the fully-qualified path.
4. Verify: `python -m growpy.cli.generate_forest data/input/test_single.csv`.
5. Commit: `"Slim io/__init__.py to layout description; drop unused re-exports"`.

---

## Phase 4: Move pipeline orchestration out of `cli/`

### Phase 4 Problem

`cli/` is documented as the command-line interface layer but currently holds
substantial pipeline-orchestration logic that has nothing to do with argument
parsing:

- [cli/step_runner.py](../../src/growpy/cli/step_runner.py) -- multi-step
  pipeline runner with state tracking.
- [cli/dataset_pipeline.py](../../src/growpy/cli/dataset_pipeline.py),
  [cli/dataset_csv_planner.py](../../src/growpy/cli/dataset_csv_planner.py),
  [cli/dataset_job_planner.py](../../src/growpy/cli/dataset_job_planner.py) --
  dataset-generation orchestration.
- `generate_forest_stages()` and `generate_forest_exports()` inside
  [cli/generate_forest.py](../../src/growpy/cli/generate_forest.py) --
  simulation control flow with no CLI concerns.

The `cli/` modules also act as console-script entry points (registered in
`pyproject.toml` as `growpy-generate-forest`, `growpy-create-models`, etc.),
which conflates "what the CLI does" with "how the work is organized."

### Target Structure

Introduce a new top-level `pipelines/` package as a sibling of `core/` and
`io/`:

```text
src/growpy/
  core/         simulation primitives
  io/           file format I/O
  pipelines/    multi-step orchestration (NEW)
    forest_stages.py    Pipeline A: height-threshold snapshots
    forest_exports.py   Pipeline B: standard cycle exports
    step_runner.py      generic step runner
    dataset.py          dataset generation pipeline
  cli/          thin argparse + dispatch (shrunk)
    generate_forest.py  argparse -> pipelines.forest_*
    dataset.py          argparse -> pipelines.dataset
    ...
  tools/        operator utilities
  utils/        shared helpers
```

### Phase 4 Steps

1. Create `src/growpy/pipelines/__init__.py` with a layout docstring (no
   eager imports).
2. Move `generate_forest_stages` to `pipelines/forest_stages.py` and
   `generate_forest_exports` to `pipelines/forest_exports.py`. Preserve
   signatures.
3. Move `cli/step_runner.py` to `pipelines/step_runner.py`. Update its
   importers via grep.
4. Move dataset pipeline modules:
   - `cli/dataset_pipeline.py` -> `pipelines/dataset_pipeline.py`
   - `cli/dataset_csv_planner.py` -> `pipelines/dataset_csv_planner.py`
   - `cli/dataset_job_planner.py` -> `pipelines/dataset_job_planner.py`
5. Reduce `cli/generate_forest.py` to argparse + dispatch only:

   ```python
   from growpy.pipelines.forest_stages import generate_forest_stages
   from growpy.pipelines.forest_exports import generate_forest_exports

   def main():
       args = _parse_args()
       if args.stages:
           generate_forest_stages(...)
       else:
           generate_forest_exports(...)
   ```

6. Audit other `cli/*.py` modules for the same shape (heavy logic vs thin
   dispatch). Anything that's pure orchestration moves to `pipelines/`.
7. Update `pyproject.toml` console-script entry points only if module paths
   changed; the `cli.*:main` entry points should stay where they are so the
   user-facing command surface is unchanged.
8. Verify all entry points still work:

   ```bash
   growpy-generate-forest data/input/test_single.csv
   growpy-create-models --help
   ```

9. Commit in stages (one per moved module) so each step is reviewable.

### Risk

This is the largest of the three phases. It touches ~6 files and changes
import paths used by console-script entry points. Recommend completing
Phase 2 (export extraction) and Phase 3 (`io/__init__.py` slim) first, then
Phase 4 on its own commit/branch.

---

## Recommended Sequence

1. **Phase 2**: extract export orchestration into `io/forest_export.py`
   (this document, sections above).
2. **Phase 3**: slim `io/__init__.py`.
3. **Phase 4**: introduce `pipelines/` package, move orchestration out of
   `cli/`.

Each phase is independently shippable and independently revertible.
