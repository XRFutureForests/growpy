# GrowPy Package Refactoring Plan

**Purpose**: Streamline, simplify, and modernize `src/growpy/` while preserving fragile USD export logic for Unreal Engine Nanite assemblies.

**Critical Constraint**: The USD export pipeline (tree_export.py, assembly_export.py, twig_export.py) is FRAGILE. Unreal Engine 5.7+ requires exact USD structure for Nanite skeletal/static assembly recognition. DO NOT refactor logic in these modules - only code structure improvements.

---

## Executive Summary

The growpy package produces USD Nanite assemblies for Unreal Engine 5.7+ from The Grove 2.2 tree models. Current state shows:

- **Documentation Debt**: Multiple outdated doc references, CLI docstrings with incorrect flags
- **Deprecated Code**: Several parameters marked deprecated but not removed
- **Commented Dead Code**: `if False:` blocks in twig_export.py (line 580)
- **Import Redundancy**: Some modules may have unused imports
- **Complexity Opportunities**: Long functions in CLI scripts could be split for readability

**Completed**: CLI docstring updates (Quick Start examples, corrected flag lists, fixed doc paths)

---

## Phase 1: Documentation Cleanup (SAFE)

### 1.1 CLI Docstring Updates - COMPLETED ✓

- [x] prepare_assets.py: Updated Quick Start, removed unsupported `--assets-dir`, fixed doc path
- [x] create_growth_models.py: Corrected flag list, removed unsupported `--workers`/`--no-parallel`
- [x] convert_twigs.py: Added geometry processing flags, corrected usage path
- [x] generate_forest.py: Fixed doc path to `docs/archive/cli-reference.md`

### 1.2 Archive Stale Docs

**Status**: NOT STARTED

Move outdated documentation to `docs/archive/historical/`:

- Multiple `CLEANUP_*.md` files documenting past refactoring iterations
- Duplicate analysis files (DEPENDENCY_ANALYSIS.md vs DEPENDENCY_ANALYSIS_FINAL.md)
- Fixed bug reports (SKELETAL_MESH_FIX_*.md series)
- Migration strategy docs (BLENDER_EXPORT_MIGRATION_STRATEGY.md)

**Rationale**: Keep `docs/archive/` focused on reference material, archive historical notes separately.

### 1.3 Consolidate Active Docs

**Status**: NOT STARTED

Create unified reference docs in `docs/growpy/`:

- **cli-reference.md**: Complete CLI flag reference (current location: `docs/archive/`)
- **api-reference.md**: Python API for programmatic use
- **assembly-guide.md**: Nanite assembly structure and Unreal import
- **troubleshooting.md**: Common issues and solutions

---

## Phase 2: Remove Deprecated Code (LOW RISK)

### 2.1 Deprecated Parameter Cleanup

**Status**: NOT STARTED  
**Risk**: LOW (parameters are ignored, not used in logic)

**Files to update**:

1. **tree_export.py** (lines 210-213):

   ```python
   # REMOVE deprecated docstring notes:
   skeleton_length: Bone length multiplier (deprecated if bones_info provided)
   skeleton_reduce: Bone reduction factor (deprecated if bones_info provided)
   skeleton_connected: Use connected bone hierarchy (deprecated if bones_info provided)
   ```

   - **Action**: Update docstrings to indicate these are optional when `bones_info` is provided
   - **Impact**: Documentation only, no code change

2. **tree_export.py** (line 889):

   ```python
   twig_placements: Optional twig placement data (deprecated)
   ```

   - **Action**: Remove parameter entirely if unused
   - **Impact**: Check all call sites first (use list_code_usages tool)

3. **tree_export.py** (line 1312):

   ```python
   prefer_nanite_assembly: DEPRECATED - always False, kept for compatibility
   ```

   - **Action**: Remove parameter after verifying no external calls
   - **Impact**: Breaking change if used externally (check with grep_search first)

4. **assembly_export.py** (line 81):

   ```python
   skeleton_source_usd: Deprecated - skeleton is now embedded in tree_usd_path
   ```

   - **Action**: Remove parameter after call site verification
   - **Impact**: Breaking change if used externally

### 2.2 Dead Code Removal

**Status**: NOT STARTED  
**Risk**: LOW (code is explicitly disabled)

**File**: twig_export.py (line 580)

```python
if False:  # Disabled - clean_export always True for Nanite compatibility
    from pxr import UsdShade
    # ~60 lines of material copying code
```

**Action**: Remove entire block (lines 580-640) with clear commit message explaining Nanite compatibility requirement

**Rationale**: Materials/textures cause Unreal import failures for skeletal Nanite assemblies. This block has been disabled permanently.

---

## Phase 3: Code Structure Improvements (MEDIUM RISK)

### 3.1 CLI Script Simplification

**Status**: NOT STARTED  
**Risk**: MEDIUM (logic changes must preserve behavior)

**Target**: generate_forest.py (~800 lines)

**Improvements**:

1. Extract Unreal script generation functions to separate module:
   - `generate_unreal_import_script()` → `growpy.utils.unreal_helpers.py`
   - `generate_unreal_cleanup_script()` → same module

2. Extract tree export batching logic:
   - `_export_single_tree_from_forest()` → `growpy.io.batch_export.py`
   - `export_individual_trees()` → same module

3. Simplify main() function:
   - Current: ~120 lines of argparse + validation
   - Target: ~60 lines (extract validation functions)

**Benefits**:

- Easier testing (isolated functions)
- Reusable Unreal integration helpers
- Clearer separation of concerns

### 3.2 Import Cleanup

**Status**: NOT STARTED  
**Risk**: LOW (automated tooling available)

**Action**: Use VS Code "Organize Imports" on all Python files in `src/growpy/`

**Files to check**:

- `src/growpy/cli/*.py` (4 files)
- `src/growpy/core/*.py` (5 files)
- `src/growpy/io/*.py` (3 files)
- `src/growpy/utils/*.py` (4 files)

**Process**:

1. Run pylance/pyright import analysis
2. Remove unused imports (must verify no dynamic imports)
3. Group imports: standard library → third-party → local

---

## Phase 4: Function Complexity Reduction (HIGH RISK)

### 4.1 Large Function Analysis

**Status**: NOT STARTED  
**Risk**: HIGH (USD export logic is fragile)

**DO NOT REFACTOR** these critical export functions:

- `tree_export.py:build_tree_mesh()` - Core USD mesh builder
- `tree_export.py:add_skeleton_to_usd()` - Skeleton integration
- `assembly_export.py:export_tree_as_nanite_assembly()` - Assembly builder
- `twig_export.py:process_twig_file()` - Twig USD converter

**Rationale**: These functions contain precise USD structure requirements that Unreal Engine validates on import. Any logic change risks breaking Nanite assembly recognition.

**Safe to simplify** (non-export logic):

- `create_growth_models.py:main()` - Growth analysis CLI
- `prepare_assets.py:load_species_csv()` - CSV validation
- `convert_twigs.py:process_twig_directory()` - Directory traversal

### 4.2 Extract Validation Logic

**Status**: NOT STARTED  
**Risk**: LOW (pure validation functions)

**Candidates**:

1. CSV validation in prepare_assets.py:

   ```python
   def validate_forest_csv(df: pd.DataFrame) -> bool:
       """Check for required columns: x, y, species, height."""
       required = ["x", "y", "species", "height"]
       return all(col in df.columns for col in required)
   ```

2. Species name standardization:
   - Extract `standardize_species_name()` and `camel_to_snake()` to `growpy.utils.naming.py`
   - Reuse across prepare_assets.py, convert_twigs.py

---

## Phase 5: Testing and Validation (MANDATORY)

### 5.1 Regression Testing

**Before ANY refactoring in io/ modules**:

1. **Export Test Suite**:

   ```bash
   # Generate reference outputs
   python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 3
   
   # After refactoring: compare outputs byte-by-byte
   diff -r data/output/forest/ data/output/forest_reference/
   ```

2. **Unreal Import Test**:
   - Import skeletal assembly → check skeleton recognition
   - Import static assembly → check material binding
   - Verify no import errors in Unreal log

3. **USD Validation**:

   ```bash
   # Check USD structure
   usdview data/output/forest/species/tree_0000_skeletal_nanite_assembly.usda
   usdcat data/output/forest/species/tree_0000_skeletal_nanite_assembly.usda | grep "def Skeleton"
   ```

### 5.2 CLI Smoke Tests

**After CLI refactoring**:

```bash
# Test each CLI script with minimal inputs
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/create_growth_models.py --cycles 5
python src/growpy/cli/convert_twigs.py data/assets/twigs --csv ""
python src/growpy/cli/generate_forest.py --quality medium --growth-cycle-limit 2
```

---

## Phase 6: Modern Python Practices (OPTIONAL)

### 6.1 Type Hints Expansion

**Status**: NOT STARTED  
**Risk**: LOW (documentation improvement)

**Current state**: Some functions have partial type hints  
**Target**: Full type coverage for public APIs

**Priority files**:

- `growpy/__init__.py` - Public API exports
- `growpy/config/__init__.py` - Configuration classes
- `growpy/core/*.py` - Forest/Grove/Tree classes

### 6.2 Error Handling Improvements

**Status**: NOT STARTED  
**Risk**: MEDIUM (behavior change)

**Current**: Many functions silently fail or use `sys.exit(1)`  
**Target**: Explicit exceptions with clear messages

**Example**:

```python
# Current (prepare_assets.py)
if not csv_path.exists():
    return 1

# Better
if not csv_path.exists():
    raise FileNotFoundError(f"CSV file not found: {csv_path}")
```

---

## Implementation Order

1. **Phase 1** (Documentation) - SAFE, immediate value
2. **Phase 2** (Deprecated code) - LOW RISK, cleanup
3. **Phase 3** (CLI structure) - MEDIUM RISK, test thoroughly
4. **Phase 5** (Testing) - Run after each phase
5. **Phase 4** (Function complexity) - HIGH RISK, optional
6. **Phase 6** (Modern practices) - OPTIONAL, long-term

---

## Success Criteria

- [ ] All CLI scripts have accurate docstrings with working examples
- [ ] No `if False:` blocks or commented-out code
- [ ] Deprecated parameters removed (if safe)
- [ ] Imports organized and unused removed
- [ ] USD export produces byte-identical outputs before/after refactoring
- [ ] All CLI smoke tests pass
- [ ] Unreal Engine imports skeletal + static assemblies without errors

---

## Rollback Plan

For any refactoring that breaks exports:

1. **Git revert** to last working commit
2. **Re-run validation** suite to confirm rollback
3. **Document failure** in `docs/growpy/refactoring-failures.md`
4. **Update this plan** to mark areas as DO NOT REFACTOR

**Git strategy**: One commit per phase, with descriptive messages linking to this plan

---

## Notes

- **Fragile Code Areas**: tree_export.py (skeleton binding), assembly_export.py (Nanite structure), twig_export.py (mesh binding)
- **Safe Refactor Areas**: CLI scripts, CSV validation, config handling, plotting utilities
- **Testing Critical**: USD output must be byte-identical (or semantically equivalent via USD diff)
- **Documentation First**: Update docs before code to clarify intent

**Last Updated**: 2025-11-15  
**Status**: Phase 1 CLI docstrings completed, rest pending
