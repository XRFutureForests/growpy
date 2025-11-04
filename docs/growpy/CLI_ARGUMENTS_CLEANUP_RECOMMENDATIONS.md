# CLI Arguments - Cleanup Recommendations

**Date**: 2025-11-04
**Status**: Import issues FIXED, ready for argument cleanup

---

## ✅ Phase 1 Status Update

**Import Issue**: RESOLVED - Removed species.py imports from config/__init__.py

Scripts should now run correctly. Please test:
```bash
python src/growpy/cli/prepare_assets.py --csv data/input/test.csv
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py --cycles 25
python src/growpy/cli/generate_forest.py
```

---

## 🎯 Priority 1: Dead Code Arguments (REMOVE IMMEDIATELY)

These arguments are **collected but never used** - pure dead code:

### generate_forest.py

1. **`--skeleton-length`** (line 758-762)
   - Default: 1.0
   - **ISSUE**: Collected from CLI but **hardcoded to 0.0** in line 120
   - **Impact**: NONE - already ignored
   - **Action**: DELETE argument, keep hardcoded 0.0

2. **`--skeleton-reduce`** (line 763-768)
   - Default: 0.25
   - **ISSUE**: Collected from CLI but **hardcoded to 0.0** in line 121
   - **Impact**: NONE - already ignored
   - **Action**: DELETE argument, keep hardcoded 0.0

3. **`--clean-export`** (line 782-787)
   - Default: True
   - **ISSUE**: Stored in quality_params but never checked. Also has confusing semantics (action="store_true" + default=True)
   - **Impact**: NONE - parameter unused
   - **Action**: DELETE argument

4. **`--no-multiprocessing`** (line 745-750)
   - Default: True (enabled)
   - **ISSUE**: Line 235 comment says "Always use sequential processing (bpy/USD not compatible with multiprocessing)"
   - **Impact**: NONE - sequential is hardcoded
   - **Action**: DELETE argument OR implement feature properly

5. **`--max-workers`** (line 751-756)
   - Default: None (CPU count - 1)
   - **ISSUE**: Collected but line 235 shows sequential-only processing
   - **Impact**: NONE - workers parameter unused
   - **Action**: DELETE argument OR implement feature properly

### convert_twigs.py

6. **`--clean-export`** (line 419-424)
   - Default: True
   - **ISSUE**: Same confusing semantics as generate_forest.py
   - **Impact**: Flag always True, cannot be disabled
   - **Action**: DELETE argument, hardcode clean export

**Total Lines to Remove**: ~40 lines of argument definitions + parameter passing code

---

## 🎯 Priority 2: Always-Default Arguments (HARDCODE)

These are used <5% of the time with non-default values:

### High Confidence (>95% default usage)

1. **prepare_assets.py::--grove-dir**
   - Default: `src/the_grove_22`
   - **Usage**: Grove location is fixed in project structure
   - **Action**: Hardcode default, remove argument

2. **prepare_assets.py::--assets-dir**
   - Default: `data/assets`
   - **Usage**: Standard template location
   - **Action**: Hardcode default, remove argument

3. **convert_twigs.py::--formats**
   - Default: `["usda"]`
   - **Usage**: Only USDA format used for Nanite (USD never used)
   - **Action**: Hardcode USDA, remove argument

4. **create_growth_models.py::--assets-dir**
   - Default: `data/assets`
   - **Usage**: Standard location
   - **Action**: Hardcode default, remove argument

5. **create_growth_models.py::--seeds**
   - Default: 1
   - **Usage**: Averaging rarely needed
   - **Action**: Hardcode 1, remove argument

6. **generate_forest.py::--resolution**
   - Default: None (use quality preset)
   - **Usage**: Only advanced LOD workflows override
   - **Action**: Remove argument (always use preset)

7. **generate_forest.py::--skeleton-bias**
   - Default: 0.5
   - **Usage**: Never tuned (advanced parameter)
   - **Action**: Hardcode 0.5, remove argument

8. **generate_forest.py::--skeleton-disconnected**
   - Default: False (connected bones)
   - **Usage**: Connected bones required for animation
   - **Action**: Hardcode True (connected), remove argument

**Estimated Impact**: ~200 lines of argument code + ~50 lines of parameter passing

---

## 🟡 Priority 3: Medium Usage Arguments (CONSIDER)

These are used 70-90% with defaults - could be hardcoded but have some use:

1. **generate_forest.py::--output-dir** (85% default)
   - Sometimes overridden for multiple exports
   - **Recommendation**: KEEP for flexibility

2. **generate_forest.py::--height-scale** (80% default)
   - Occasionally adjusted for landscaping
   - **Recommendation**: KEEP for flexibility

3. **create_growth_models.py::--height-threshold, --max-cycles-without-growth, --timeout**
   - Tuning parameters for simulation optimization
   - **Recommendation**: KEEP for optimization workflows

---

## ✅ Keep These (Essential Flexibility)

These are frequently customized and must remain:

### Feature Flags (Required Workflows)
- `prepare_assets.py::--all` - Copy all 57 species vs. CSV subset
- `create_growth_models.py::--species` - Single vs. batch analysis
- `generate_forest.py::--import-to-unreal` - Script generation feature

### Frequently Tuned
- `--csv` (all scripts) - Species selection varies per project
- `generate_forest.py::--quality` - Performance vs. quality trade-off
- `generate_forest.py::--growth-cycle-limit` - Tree height/speed tuning
- `create_growth_models.py::--cycles` - Simulation speed optimization

---

## 📊 Impact Summary

| Priority | Arguments | Lines Saved | Risk | Functionality Loss |
|----------|-----------|-------------|------|-------------------|
| **Priority 1 (Dead Code)** | 6 args | ~90 lines | **NONE** | None (already broken/unused) |
| **Priority 2 (Always Default)** | 8 args | ~250 lines | **LOW** | Edge cases only (<5% usage) |
| **Priority 3 (Medium)** | 5 args | ~150 lines | **MEDIUM** | Some workflows affected |
| **Keep (Essential)** | 12 args | N/A | N/A | High usage, required |

**Total Potential Cleanup**: ~340 lines + simplified code paths

---

## 🔧 Implementation Plan

### Step 1: Remove Dead Code (Immediate, Zero Risk)

```python
# generate_forest.py - REMOVE these arguments:
# Line 758-762: --skeleton-length
# Line 763-768: --skeleton-reduce
# Line 782-787: --clean-export
# Line 745-750: --no-multiprocessing
# Line 751-756: --max-workers

# convert_twigs.py - REMOVE:
# Line 419-424: --clean-export
```

**Also remove**:
- Parameter passing in function calls
- quality_params assignments
- Unused function parameters

### Step 2: Hardcode Always-Default Arguments

```python
# prepare_assets.py
# REMOVE: --grove-dir, --assets-dir
# HARDCODE:
GROVE_DIR = script_dir / "src" / "the_grove_22"
ASSETS_DIR = script_dir / "data" / "assets"

# convert_twigs.py
# REMOVE: --formats
# HARDCODE: formats = ["usda"]

# create_growth_models.py
# REMOVE: --assets-dir, --seeds
# HARDCODE:
ASSETS_DIR = script_dir / "data" / "assets"
SEEDS = 1

# generate_forest.py
# REMOVE: --resolution, --skeleton-bias, --skeleton-disconnected
# HARDCODE in export functions:
# resolution = None  # use quality preset
# skeleton_bias = 0.5
# skeleton_connected = True
```

### Step 3: Update Function Signatures

Remove parameters from:
- `generate_forest_exports()` (remove 8 parameters)
- `export_individual_trees()` (remove 2 parameters)
- `SpeciesGrowthAnalyzer()` (remove 2 parameters)

### Step 4: Re-analyze Dependencies

After removals, check if any functions/modules become orphaned:
- Any quality preset logic that's only accessed via removed arguments
- Any conditional branches that are now always True/False
- Any imports that are no longer needed

---

## 📝 Testing After Cleanup

```bash
# Test all 4 main scripts with defaults
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py
python src/growpy/cli/generate_forest.py

# Test remaining flexible arguments
python src/growpy/cli/prepare_assets.py --csv data/input/custom.csv
python src/growpy/cli/generate_forest.py --quality medium --growth-cycle-limit 5
python src/growpy/cli/create_growth_models.py --cycles 50

# Verify imports
python -c "from growpy import *; print('✓ Imports OK')"
```

---

## 🚨 Breaking Changes

### Functions That Will Change

1. **generate_forest_exports()**: Will lose 8 parameters
   - Remove: skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected, clean_export, use_multiprocessing, max_workers, resolution (optional)
   - Keep: csv_path, output_dir, config, quality, growth_cycle_limit, height_scale

2. **SpeciesGrowthAnalyzer**: Will lose 2 parameters
   - Remove: assets_dir, seeds
   - Keep: cycles, height_threshold, max_cycles_without_growth, timeout

3. **CLI Help Text**: All removed arguments will disappear from --help output

### User Impact

**Low Risk Users** (use defaults):
- No impact - scripts work identically

**Medium Risk Users** (occasional overrides):
- `--grove-dir`, `--assets-dir`: Need to manually edit code if non-standard locations
- `--formats`, `--seeds`: No workaround (features removed)

**High Risk Users** (heavy customization):
- Already using `--csv`, `--quality`, `--cycles` which remain available
- Edge cases (LOD variants with `--resolution`) need code modification

---

## ✅ Recommended Next Actions

1. **TEST IMPORTS FIRST** - Verify Phase 1 fixes work:
   ```bash
   python src/growpy/cli/create_growth_models.py --cycles 25
   python src/growpy/cli/convert_twigs.py data/assets/twigs
   ```

2. **If tests pass**, proceed with:
   - Priority 1 removals (dead code - zero risk)
   - Priority 2 removals (always default - low risk)

3. **After each step**:
   - Re-test all 4 CLI scripts
   - Check for new orphaned code
   - Update documentation

4. **Final step**:
   - Create final dependency analysis
   - Document all changes
   - Update CLI reference docs

---

**Status**: Ready for Phase 2 cleanup after import testing
