# GrowPy Refactoring Progress

**Date:** 2025-10-17
**Status:** Phase 1 Complete

## ✅ Phase 1: Utility Modules & Core Cleanup

### Created Utility Modules

1. **`src/growpy/utils/strings.py`**
   - `sanitize_species_name()` - Convert species names to filesystem-safe format
   - `sanitize_filename()` - General filename sanitization

2. **`src/growpy/utils/paths.py`**
   - `ensure_dir()` - Create directory if needed
   - `ensure_parent_dir()` - Ensure parent directory exists

3. **Updated `src/growpy/utils/__init__.py`**
   - Exported all new utilities

### Cleaned Core Modules

1. **`src/growpy/core/grove.py`** (67 → 48 lines, -28%)
   - ✅ Removed try/except for Grove import (assume always available)
   - ✅ Added complete type hints
   - ✅ Simplified docstrings (Google style, no examples/exceptions)
   - ✅ Removed unnecessary error messages

2. **`src/growpy/core/forest.py`** (133 → 94 lines, -29%)
   - ✅ Removed try/except for Grove import
   - ✅ Added type hints to all functions
   - ✅ Simplified docstrings
   - ✅ Removed validation and error checks

3. **`src/growpy/core/tree.py`** (207 → 142 lines, -31%)
   - ✅ Removed try/except blocks
   - ✅ Added type hints throughout
   - ✅ Simplified get_model_attributes() - removed excessive error handling
   - ✅ Simplified apply_species_color_settings() - removed fallback logic
   - ✅ Cleaned build functions

### Code Metrics

**Lines of Code Reduction:**
- `core/grove.py`: -19 lines (-28%)
- `core/forest.py`: -39 lines (-29%)
- `core/tree.py`: -65 lines (-31%)
- **Total Core Reduction:** -123 lines (-30%)

**Type Hints Added:** 9 function signatures now fully typed

**Complexity Reduced:**
- Removed 7 try/except blocks from core/
- Removed 3 Grove availability checks
- Simplified 3 docstrings

## 📋 Phase 2: Pending Large Refactorings

### Config Module Split (High Impact)

**Current:** `config/settings.py` = 905 lines

**Proposed Structure:**
```
config/
├── __init__.py          # Exports
├── core.py              # GrowPyConfig class (~100 lines)
├── species.py           # Species lookup (~150 lines)
├── paths.py             # Path resolution (~300 lines)
├── quality.py           # LOD presets (~100 lines)
└── tree_asset_lookup.csv
```

**Benefits:**
- Each module <300 lines
- Clear responsibilities
- Easier to maintain
- Better caching opportunities

**Risk:** Medium - changes affect many modules

### Blender Export Split (Very High Impact)

**Current:** `io/blender_export.py` = 4116 lines (!!)

**Proposed Structure:**
```
io/
├── export/
│   ├── usd.py           # USD export (~800 lines)
│   ├── fbx.py           # FBX export (~600 lines)
│   ├── skeleton.py      # Skeleton creation (~400 lines)
│   ├── quality.py       # Quality presets (~200 lines)
│   └── blender_utils.py # Scene management (~300 lines)
├── nanite/
│   ├── attributes.py    # USD attributes (~200 lines)
│   └── validation.py    # Mesh validation (~300 lines)
└── twig/
    ├── bundling.py      # Twig bundling (~400 lines)
    ├── placement.py     # Twig placement (existing)
    └── processor.py     # Twig processor (existing)
```

**Benefits:**
- 10x improvement in file sizes
- Logical organization by function
- Easier to find code
- Better testability

**Risk:** High - extensive changes, many import updates needed

### CLI Improvements (Medium Impact)

**Changes:**
- Extract common argparse code to `cli/common.py`
- Use utility functions (sanitize_species_name, etc.)
- Simplify main() functions
- Update help text with correct paths

**Risk:** Low - mostly internal to CLI

## 🎯 Next Steps

### Option A: Continue with Config Split
- Split settings.py into 4 focused modules
- Update all imports
- Add LRU caching for species lookup
- Create config.ini template

**Time:** 2-3 hours
**Risk:** Medium
**Impact:** High

### Option B: Tackle Blender Export Split
- Create new io/ submodule structure
- Move functions to appropriate modules
- Update all imports
- Test exports still work

**Time:** 4-5 hours
**Risk:** High
**Impact:** Very High

### Option C: Quick Wins First
- Create config.ini template
- Add caching to existing code
- Update CLI with utilities
- Write documentation

**Time:** 2-3 hours
**Risk:** Low
**Impact:** Medium

## Recommendation

**Start with Option C (Quick Wins), then A, then B**

Rationale:
1. Config.ini provides immediate user value
2. Caching improves performance without restructuring
3. CLI updates use new utilities
4. Documentation captures current state
5. **Then** tackle config split (affects fewer files)
6. **Finally** tackle blender_export split (most complex)

This approach delivers value incrementally while building confidence before the big refactorings.

## Questions for Review

1. **Should we proceed with config split?**
   - How important is keeping the current import structure?
   - Are there any external tools importing from config.settings?

2. **Should we proceed with blender_export split?**
   - This is the most impactful but also riskiest change
   - Would you prefer to test exports after each sub-module split?

3. **Config.ini location?**
   - Project root? (recommended)
   - data/config.ini?
   - User home directory?

4. **Which settings should be in config.ini?**
   - Random seed?
   - Output directory?
   - LOD levels?
   - Asset paths?
   - All of the above?

Please advise on how you'd like to proceed!
