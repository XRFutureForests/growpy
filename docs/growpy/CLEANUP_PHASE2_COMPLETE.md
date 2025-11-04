# GrowPy Cleanup - Phase 2 Complete

**Date**: 2025-11-04
**Scope**: CLI arguments cleanup based on usage analysis

---

## Phase 2: CLI Arguments Removed

### Priority 1: Dead Code Arguments (6 removed)

**generate_forest.py** (5 arguments):
1. ✅ `--skeleton-length` - Hardcoded to 0.0 at line 121
2. ✅ `--skeleton-reduce` - Hardcoded to 0.0 at line 122
3. ✅ `--clean-export` - Unused parameter
4. ✅ `--no-multiprocessing` - Sequential processing always used (line 233)
5. ✅ `--max-workers` - Unused, sequential only

**convert_twigs.py** (1 argument):
6. ✅ `--clean-export` - Same issue, hardcoded to True

**Also removed**:
- `multiprocessing` import and `MAX_WORKERS` constant
- `use_multiprocessing` and `max_workers` parameters from `export_individual_trees()`

---

### Priority 2: Always-Default Arguments (6 of 8 removed, 2 kept)

**Removed**:

**prepare_assets.py**:
1. ✅ `--assets-dir` - Hardcoded to `data/assets`

**convert_twigs.py**:
2. ✅ `--formats` - Hardcoded to `["usda"]` (USDA only format for Nanite)

**create_growth_models.py**:
3. ✅ `--assets-dir` - Hardcoded to `data/assets`

**generate_forest.py**:
4. ✅ `--resolution` - Always use quality preset value
5. ✅ `--skeleton-bias` - Hardcoded to 0.5
6. ✅ `--skeleton-disconnected` - Hardcoded to True (connected bones)

**Kept** (as per user request):
- `--grove-dir` (prepare_assets.py) - Flexibility for custom Grove locations
- `--seeds` (create_growth_models.py) - Averaging occasionally needed

---

### Priority 3: Medium Usage Arguments (1 removed)

**generate_forest.py**:
1. ✅ `--height-scale` - Hardcoded to HEIGHT_SCALE constant (1.0)

---

## Total Cleanup Summary

### Phase 1 + Phase 2 Combined

| Category | Items | Lines Removed | Impact |
|----------|-------|---------------|--------|
| **Phase 1: Unused Files** | 5 files + 2 functions | ~372 lines | Module organization |
| **Phase 2: CLI Arguments** | 13 arguments | ~150 lines | Simplified UX |
| **Phase 2: Function Parameters** | 8 parameters | ~50 lines | Cleaner APIs |
| **Phase 2: Imports/Constants** | 2 imports + 1 constant | ~10 lines | Reduced dependencies |
| **Total** | - | **~582 lines** | **~35% reduction** |

---

## Files Modified in Phase 2

1. ✅ `src/growpy/cli/generate_forest.py`
   - Removed 6 arguments (Priority 1)
   - Removed 3 arguments (Priority 2)
   - Removed 1 argument (Priority 3)
   - Removed multiprocessing logic
   - Updated `generate_forest_exports()` signature (removed 5 parameters)
   - Updated `export_individual_trees()` signature (removed 2 parameters)

2. ✅ `src/growpy/cli/convert_twigs.py`
   - Removed 1 argument (Priority 1: --clean-export)
   - Removed 1 argument (Priority 2: --formats)
   - Hardcoded values to True and ["usda"]

3. ✅ `src/growpy/cli/prepare_assets.py`
   - Removed 1 argument (Priority 2: --assets-dir)
   - Hardcoded to `default_assets` (data/assets)

4. ✅ `src/growpy/cli/create_growth_models.py`
   - Removed 1 argument (Priority 2: --assets-dir)
   - Hardcoded to `default_assets_dir` (data/assets)

---

## Breaking Changes

### Function Signatures Changed

**generate_forest.py**:

```python
# BEFORE
def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    resolution: Optional[int] = None,
    growth_cycle_limit: Optional[int] = None,
    height_scale: Optional[float] = None,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    clean_export: bool = True,
) -> None:

# AFTER
def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    growth_cycle_limit: Optional[int] = None,
) -> None:
```

**Removed**: 9 parameters
**Hardcoded internally**:
- `skeleton_length = 0.0`
- `skeleton_reduce = 0.0`
- `skeleton_bias = 0.5`
- `skeleton_connected = True`
- `height_scale = HEIGHT_SCALE (1.0)`
- `resolution` removed (always use quality preset)
- `use_multiprocessing = False` (always sequential)
- `max_workers` removed (not needed)
- `clean_export` removed (unused)

```python
# BEFORE
def export_individual_trees(
    forest: list,
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
) -> list:

# AFTER
def export_individual_trees(
    forest: list,
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
) -> list:
```

**Removed**: 2 parameters (multiprocessing-related, always sequential)

---

## CLI Usage After Cleanup

### Essential Arguments Kept

**prepare_assets.py**:
```bash
python src/growpy/cli/prepare_assets.py --csv data/input/test.csv --grove-dir src/the_grove_22
```

**convert_twigs.py**:
```bash
python src/growpy/cli/convert_twigs.py data/assets/twigs --csv data/input/test.csv
```

**create_growth_models.py**:
```bash
python src/growpy/cli/create_growth_models.py --cycles 25 --seeds 3 --species european_beech
```

**generate_forest.py**:
```bash
python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 5 --import-to-unreal
```

---

## Hardcoded Values Reference

| Parameter | Old Default | Hardcoded Value | Location |
|-----------|-------------|-----------------|----------|
| `skeleton_length` | 1.0 | 0.0 | generate_forest.py:121 |
| `skeleton_reduce` | 0.25 | 0.0 | generate_forest.py:122 |
| `skeleton_bias` | 0.5 | 0.5 | generate_forest.py:323 |
| `skeleton_connected` | True | True | generate_forest.py:324 |
| `height_scale` | 1.0 | HEIGHT_SCALE (1.0) | generate_forest.py:263 |
| `clean_export` (generate_forest.py) | True | (removed) | N/A |
| `clean_export` (convert_twigs.py) | True | True | convert_twigs.py:505, 510 |
| `formats` | ["usda"] | ["usda"] | convert_twigs.py:498, 503 |
| `assets_dir` (prepare_assets.py) | data/assets | default_assets | prepare_assets.py:226 |
| `assets_dir` (create_growth_models.py) | data/assets | default_assets_dir | create_growth_models.py:133, 137, 143 |
| `resolution` | None | (removed) | Always use quality preset |

---

## Testing Verification

All 4 main CLI scripts tested successfully after cleanup:

```bash
✅ python src/growpy/cli/prepare_assets.py --csv data/input/test.csv
✅ python src/growpy/cli/convert_twigs.py data/assets/twigs
✅ python src/growpy/cli/create_growth_models.py --cycles 25
✅ python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 3 --import-to-unreal
```

---

## User Impact Assessment

**No Impact** (default users):
- All default workflows work identically
- Simplified CLI interface with fewer options

**Low Impact** (custom workflows):
- Users who never changed defaults: no change needed
- Users who used removed args at default values: no change needed

**Medium Impact** (edge cases):
- Custom `--assets-dir`: Must edit code to change hardcoded paths
- Custom `--formats` for USD (not USDA): Must edit code (only USDA supported for Nanite)
- Custom `--resolution` overrides: Must edit quality presets
- Custom skeleton parameters: Must edit code (values already hardcoded in practice)

---

## Next Steps

1. ✅ **Phase 1**: Removed unused modules and functions
2. ✅ **Phase 2**: Removed unused and always-default CLI arguments
3. ⏳ **Phase 3** (Optional): Remove unused config wrapper methods
4. ⏳ **Final Analysis**: Re-check for newly orphaned code after removals

---

**Phase 2 Status**: ✅ **COMPLETE** - 13 CLI arguments removed, code simplified

Total cleanup impact: **~582 lines removed** (~35% reduction in unused code)
