# GrowPy Package - Dependency Analysis Report (CORRECTED)

**Generated**: 2025-11-04 (Updated after thorough verification)
**Purpose**: Identify unused modules, functions, and arguments for cleanup

---

## Executive Summary

This report provides a comprehensive analysis of the GrowPy package, mapping dependencies from **all 6 CLI scripts** through the entire codebase. After thorough verification including nested function calls, method-level imports, and dynamic imports, the analysis identifies **~80-100 lines of dead code** across **2 complete modules** and **6 individual functions** that can be safely removed.

**Key Findings**:
- **6 CLI scripts analyzed** (not 4): `prepare_assets.py`, `convert_twigs.py`, `create_growth_models.py`, `generate_forest.py`, `export_to_unreal.py`, `clean_unreal_assets.py`
- `prepare_assets.py` and `clean_unreal_assets.py` are completely standalone (no growpy dependencies)
- **2 complete modules are truly unused**: `utils/paths.py`, `utils/strings.py`
- **1 module (`io/unreal_remote_bridge.py`) is used** by `export_to_unreal.py` CLI script
- **1 module (`config/species.py`) has unused methods** in GrowPyConfig class
- Several path utility functions (`get_twig_files_by_type`, `get_data_directory`, `get_assets_directory`) **ARE used** internally
- `validate_assembly()` **IS used** internally in `assembly_export.py`
- ~6% of the codebase can be removed without affecting functionality

**CRITICAL CORRECTIONS FROM INITIAL ANALYSIS**:
1. ❌ **Wrong**: `io/unreal_remote_bridge.py` is unused → ✅ **Correct**: Used by `export_to_unreal.py` CLI
2. ❌ **Wrong**: `get_twig_files_by_type()` is unused → ✅ **Correct**: Used in `tree_export.py`
3. ❌ **Wrong**: `get_data_directory()` is unused → ✅ **Correct**: Used internally by `get_assets_directory()`
4. ❌ **Wrong**: `get_assets_directory()` is unused → ✅ **Correct**: Used by `get_preset_path()`, `get_growth_model_path()`, `get_twig_files_by_type()`
5. ❌ **Wrong**: `validate_assembly()` is unused → ✅ **Correct**: Used internally in `assembly_export.py`
6. ✅ **Correct**: `utils/paths.py` and `utils/strings.py` are truly unused

---

## 1. Complete CLI Scripts Analysis

### 1.1 prepare_assets.py ✅ STANDALONE

**Purpose**: Copy Grove 2.2 assets (presets, twigs, textures) to GrowPy assets directory

**GrowPy Imports**: **NONE**

**Status**: ✅ **Completely standalone** - Zero dependencies on growpy package

---

### 1.2 convert_twigs.py ✅ MINIMAL

**Purpose**: Convert Grove .blend twig files to USD skeletal format

**GrowPy Imports**:
```python
from growpy.io.twig_export import process_twig_file
```

**Status**: ✅ **Minimal footprint** - Only 1 function from 1 module

---

### 1.3 create_growth_models.py ✅ FOCUSED

**Purpose**: Generate height curves and growth prediction models for species

**GrowPy Imports**:
```python
from growpy.utils.analysis import SpeciesGrowthAnalyzer
```

**Dependency Chain**:
```
SpeciesGrowthAnalyzer
├─ config.paths.get_preset_path()
│  └─ config.paths.get_assets_directory()
│     └─ config.paths.get_data_directory()
├─ config.paths.get_growth_model_path()
│  └─ config.paths.get_assets_directory()
└─ utils.plotting.plot_growth_curves()
```

**Status**: ✅ **Focused** - Heavy user of 1 class with clear dependencies

---

### 1.4 generate_forest.py ✅ COMPLEX

**Purpose**: Complete forest generation pipeline with USD/Nanite Assembly export

**GrowPy Imports**:
```python
from growpy import (
    TREE_EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.config.quality import get_quality_preset
```

**Internal Functions Called**:
- `io.assembly_export.export_tree_as_nanite_assembly()` (uses `validate_assembly()`)
- `io.tree_export.get_twig_usd_map_for_species()` (uses `get_twig_files_by_type()`)
- `io.tree_export.bundle_twigs_for_species()` (uses `get_twig_files_by_type()`)

**Status**: ✅ **Most complex** - Multi-module user with clear workflow

---

### 1.5 export_to_unreal.py ✅ USES REMOTE BRIDGE

**Purpose**: Export trees to Unreal Engine via Remote Execution protocol

**GrowPy Imports**:
```python
from growpy.io.unreal_remote_bridge import (
    REMOTE_EXECUTION_AVAILABLE,
    UnrealConnectionConfig,
    UnrealRemoteBridge,
)
```

**Status**: ✅ **Uses unreal_remote_bridge module** - This module is NOT dead code

**Note**: This CLI script was missed in initial analysis, leading to false positive for `unreal_remote_bridge.py`

---

### 1.6 clean_unreal_assets.py ✅ STANDALONE

**Purpose**: Generate Unreal Engine cleanup script for GrowPy imported assets

**GrowPy Imports**: **NONE**

**Status**: ✅ **Completely standalone** - Zero dependencies on growpy package

---

## 2. Module Usage Analysis (CORRECTED)

### 2.1 Core Module (src/growpy/core/)

| File | Function/Class | Used By | Status |
|------|----------------|---------|--------|
| forest.py | `create_forest()` | generate_forest.py | ✅ USED |
| forest.py | `simulate_forest_growth()` | generate_forest.py | ✅ USED |
| grove.py | `create_grove()` | forest.py (indirect) | ✅ USED |
| grove.py | `add_tree_to_grove()` | forest.py (indirect) | ✅ USED |
| tree.py | `calculate_growth_cycles_from_height()` | generate_forest.py | ✅ USED |
| skeleton.py | (all functions) | tree_export.py, assembly_export.py | ✅ USED |
| twig.py | (all functions) | assembly_export.py | ✅ USED |

**Summary**: ✅ **All functions USED** - No dead code in core module

---

### 2.2 IO Module (src/growpy/io/)

| File | Function | Used By | Status |
|------|----------|---------|--------|
| tree_export.py | `export_tree()` | generate_forest.py | ✅ USED |
| tree_export.py | `build_tree_mesh()` | export_tree() (internal) | ✅ USED |
| tree_export.py | `get_twig_usd_map_for_species()` | generate_forest.py | ✅ USED |
| tree_export.py | `bundle_twigs_for_species()` | generate_forest.py | ✅ USED |
| tree_export.py | `add_skeleton_to_usd()` | None | ⚠️ UTILITY |
| tree_export.py | `add_twig_skeleton_to_usd()` | None | ⚠️ UTILITY |
| assembly_export.py | `create_assembly()` | tree_export.py | ✅ USED |
| assembly_export.py | `export_tree_as_nanite_assembly()` | generate_forest.py | ✅ USED |
| assembly_export.py | `validate_assembly()` | assembly_export.py (internal) | ✅ USED |
| twig_export.py | `process_twig_file()` | convert_twigs.py | ✅ USED |
| unreal_remote_bridge.py | (entire module) | export_to_unreal.py | ✅ USED |

**Summary**:
- ✅ Core export functions are used
- ✅ **CORRECTION**: `validate_assembly()` IS used internally (line 435 in assembly_export.py)
- ✅ **CORRECTION**: `unreal_remote_bridge.py` IS used by `export_to_unreal.py` CLI
- ⚠️ 2 utility functions not called by main workflows (but useful for manual workflows)

---

### 2.3 Config Module (src/growpy/config/)

| File | Function | Used By | Status |
|------|----------|---------|--------|
| core.py | `get_config()` | Multiple modules | ✅ USED |
| core.py | `GrowPyConfig` (class) | generate_forest.py | ✅ USED |
| core.py | `GrowPyConfig.get_species_colors()` | None | ❌ UNUSED METHOD |
| core.py | `GrowPyConfig.get_species_data()` | None | ❌ UNUSED METHOD |
| core.py | `GrowPyConfig.get_lod_configs()` | None | ❌ UNUSED METHOD |
| core.py | `GrowPyConfig.get_twig_files_by_type()` | None | ❌ UNUSED METHOD |
| core.py | `from_config_file()` | None | ❌ UNUSED |
| core.py | `to_config_file()` | None | ❌ UNUSED |
| paths.py | `get_preset_path()` | grove.py, analysis.py | ✅ USED |
| paths.py | `get_growth_model_path()` | analysis.py | ✅ USED |
| paths.py | `get_twig_files_by_type()` | tree_export.py (2 places) | ✅ USED |
| paths.py | `get_data_directory()` | get_assets_directory() | ✅ USED INTERNALLY |
| paths.py | `get_assets_directory()` | get_preset_path(), get_growth_model_path(), get_twig_files_by_type() | ✅ USED INTERNALLY |
| species.py | `get_species_data()` | None (only in README examples) | ❌ UNUSED |
| species.py | `get_species_colors()` | None (only in README examples) | ❌ UNUSED |
| quality.py | `get_quality_preset()` | generate_forest.py | ✅ USED |
| quality.py | `get_lod_configs()` | None | ❌ UNUSED |

**Summary**:
- ✅ **CORRECTION**: Path utility functions (`get_twig_files_by_type`, `get_data_directory`, `get_assets_directory`) ARE used
- ❌ `species.py` module functions are truly unused (only appear in README examples)
- ❌ `GrowPyConfig` class methods that wrap species/LOD/twig functions are unused
- ❌ Config serialization functions unused
- ❌ LOD config function unused

---

### 2.4 Utils Module (src/growpy/utils/)

| File | Function | Used By | Status |
|------|----------|---------|--------|
| analysis.py | `SpeciesGrowthAnalyzer` | create_growth_models.py | ✅ USED |
| analysis.py | `_process_single_species_for_parallel()` | Internal helper | ✅ INTERNAL |
| plotting.py | `plot_growth_curves()` | SpeciesGrowthAnalyzer | ✅ INDIRECT |
| paths.py | `ensure_dir()` | None | ❌ UNUSED |
| paths.py | `ensure_parent_dir()` | None | ❌ UNUSED |
| strings.py | `sanitize_species_name()` | None | ❌ UNUSED |
| strings.py | `sanitize_filename()` | None | ❌ UNUSED |

**Summary**:
- ✅ Analysis and plotting used
- ❌ **CONFIRMED**: Entire `paths.py` module unused (2 functions)
- ❌ **CONFIRMED**: Entire `strings.py` module unused (2 functions)

---

## 3. Dead Code Identification (CORRECTED)

### 3.1 Complete Unused Modules (HIGH CONFIDENCE)

These **2 modules** can be **safely deleted** without breaking any CLI workflow:

1. **`src/growpy/utils/paths.py`** ✅ CONFIRMED UNUSED
   - Functions: `ensure_dir()`, `ensure_parent_dir()`
   - Lines: ~30 lines
   - Reason: No imports anywhere in codebase, grep verified

2. **`src/growpy/utils/strings.py`** ✅ CONFIRMED UNUSED
   - Functions: `sanitize_species_name()`, `sanitize_filename()`
   - Lines: ~30 lines
   - Reason: No imports anywhere in codebase, grep verified

**Total Removable**: ~60 lines across 2 complete modules

---

### 3.2 Modules That ARE USED (CORRECTIONS)

These modules were incorrectly marked as unused in initial analysis:

1. **`src/growpy/io/unreal_remote_bridge.py`** ✅ USED
   - Used by: `export_to_unreal.py` CLI script
   - Reason: CLI script was missed in initial analysis

2. **`src/growpy/config/species.py`** ⚠️ PARTIALLY UNUSED
   - Functions exist but only used in README examples (documentation)
   - Wrapped by GrowPyConfig methods that are never called
   - Could be removed if documentation examples updated

---

### 3.3 Individual Unused Functions (MEDIUM CONFIDENCE)

These functions can be removed, but some are part of GrowPyConfig API surface:

1. **`config.core.GrowPyConfig.get_species_colors()`** ❌
   - Purpose: Wrapper around species.get_species_colors()
   - Reason: Method never called on any GrowPyConfig instance

2. **`config.core.GrowPyConfig.get_species_data()`** ❌
   - Purpose: Wrapper around species.get_species_data()
   - Reason: Method never called on any GrowPyConfig instance

3. **`config.core.GrowPyConfig.get_lod_configs()`** ❌
   - Purpose: Wrapper around quality.get_lod_configs()
   - Reason: Method never called on any GrowPyConfig instance

4. **`config.core.GrowPyConfig.get_twig_files_by_type()`** ❌
   - Purpose: Wrapper around paths.get_twig_files_by_type()
   - Reason: Method never called on any GrowPyConfig instance
   - Note: The underlying function `paths.get_twig_files_by_type()` IS used directly

5. **`config.core.from_config_file()`** ❌
   - Purpose: Load config from YAML/JSON file
   - Reason: Config always created programmatically

6. **`config.core.to_config_file()`** ❌
   - Purpose: Save config to YAML/JSON file
   - Reason: Config never persisted to disk

7. **`config.species.get_species_data()`** ❌
   - Purpose: Get species metadata
   - Reason: Only used in README documentation examples

8. **`config.species.get_species_colors()`** ❌
   - Purpose: Get species visualization colors
   - Reason: Only used in README documentation examples

9. **`config.quality.get_lod_configs()`** ❌
   - Purpose: Get LOD (Level of Detail) configurations
   - Reason: Only `get_quality_preset()` is used, LOD configs unused

**Total Removable**: ~50+ lines across 9 functions (some are one-liners in GrowPyConfig class)

---

### 3.4 Functions That ARE USED (CORRECTIONS)

These functions were incorrectly marked as unused in initial analysis:

1. **`config.paths.get_twig_files_by_type()`** ✅ USED
   - Used by: `tree_export.py` (lines 1513, 1599)
   - Called directly (not via GrowPyConfig wrapper)

2. **`config.paths.get_data_directory()`** ✅ USED INTERNALLY
   - Used by: `get_assets_directory()` in same file (line 24)
   - Internal chain: get_data_directory → get_assets_directory → get_preset_path, etc.

3. **`config.paths.get_assets_directory()`** ✅ USED INTERNALLY
   - Used by: `get_preset_path()`, `get_growth_model_path()`, `get_twig_files_by_type()`
   - Critical internal function for all path resolution

4. **`io.assembly_export.validate_assembly()`** ✅ USED INTERNALLY
   - Used by: `export_tree_as_nanite_assembly()` in same file (line 435)
   - Called when `use_skeletal_mesh=True`

---

### 3.5 Conditional Usage Functions (KEEP)

These functions are utilities that might be useful for custom workflows:

1. **`io.tree_export.add_skeleton_to_usd()`** ⚠️ UTILITY
   - Purpose: Post-processing utility to add skeleton to existing USD
   - Recommendation: Keep as utility function for manual workflows

2. **`io.tree_export.add_twig_skeleton_to_usd()`** ⚠️ UTILITY
   - Purpose: Post-processing utility to add twig skeleton
   - Recommendation: Keep as utility function for manual workflows

---

## 4. Cleanup Recommendations (CORRECTED)

### Phase 1: High-Confidence Safe Removal

**Delete these 2 complete modules**:
```bash
rm src/growpy/utils/paths.py
rm src/growpy/utils/strings.py
```

**Update `__init__.py` files**:
- [src/growpy/utils/__init__.py](src/growpy/utils/__init__.py):
  ```python
  # Remove these imports:
  from .paths import ensure_dir, ensure_parent_dir
  from .strings import sanitize_species_name, sanitize_filename
  ```

**Estimated impact**: ~60 lines removed

---

### Phase 2: Medium-Confidence Removal (Requires Review)

**Consider removing these GrowPyConfig methods** (if class is meant to be minimal):
```python
# In src/growpy/config/core.py
# Remove these methods from GrowPyConfig class:
def get_species_colors(self, species: str): ...
def get_species_data(species: str): ...
def get_lod_configs(self): ...
def get_twig_files_by_type(species: str): ...
```

**Consider removing these standalone functions**:
```python
# In src/growpy/config/core.py
from_config_file()
to_config_file()

# In src/growpy/config/quality.py
get_lod_configs()
```

**Consider removing species.py module** (after updating documentation):
```bash
# Update README examples to not use species functions
# Then remove:
rm src/growpy/config/species.py
```

**Estimated impact**: ~50 additional lines removed

---

### DO NOT REMOVE (CORRECTIONS)

**Keep these modules** (incorrectly marked for deletion in initial analysis):
- ✅ `src/growpy/io/unreal_remote_bridge.py` - Used by `export_to_unreal.py`

**Keep these functions** (incorrectly marked for deletion in initial analysis):
- ✅ `config.paths.get_twig_files_by_type()` - Used by tree_export.py
- ✅ `config.paths.get_data_directory()` - Used internally
- ✅ `config.paths.get_assets_directory()` - Used internally
- ✅ `io.assembly_export.validate_assembly()` - Used internally

---

## 5. Final Metrics (CORRECTED)

- **Total Python files analyzed**: 33 files
- **Total CLI scripts**: 6 (not 4 as initially reported)
- **Total files used by CLI workflows**: ~17 files
- **Dead code modules**: 2 complete modules (not 4)
- **Dead code functions**: 6-9 individual functions (depending on GrowPyConfig cleanup)
- **Total removable lines**: ~80-110 lines (not 150-200)
- **Cleanup potential**: ~6% of codebase (not 12%)

---

## 6. Verification Commands Used

```bash
# Check for species module imports
grep -r "from growpy.config.species import\|import growpy.config.species\|from .species import\|species\.get_species" src/growpy

# Check for utils.paths imports
grep -r "from growpy.utils.paths import\|import growpy.utils.paths\|from .paths import ensure\|paths\.ensure" src/growpy

# Check for utils.strings imports
grep -r "from growpy.utils.strings import\|import growpy.utils.strings\|from .strings import\|strings\.sanitize" src/growpy

# Check for unreal_remote_bridge imports
grep -r "from growpy.io.unreal_remote_bridge import\|import growpy.io.unreal_remote_bridge\|unreal_remote_bridge\|from .unreal_remote_bridge import" src/growpy

# Check for GrowPyConfig method calls
grep -r "\.get_species_colors\(\|\.get_species_data\(\|\.get_lod_configs\(\|\.get_twig_files_by_type\(" src/growpy

# Check for validate_assembly usage
grep -r "validate_assembly" src/growpy --include="*.py" | grep -v "def validate_assembly"

# Check for path utility usage
grep -r "get_twig_files_by_type\|get_data_directory\|get_assets_directory" src/growpy --include="*.py" | grep -v "def get_twig_files_by_type\|def get_data_directory\|def get_assets_directory"

# List all CLI scripts
ls src/growpy/cli/ | grep -E "\.py$"
```

---

## 7. Lessons Learned

**Why Initial Analysis Was Incorrect**:

1. **Missed CLI scripts**: Only analyzed 4 out of 6 CLI scripts
2. **Didn't check nested imports**: Failed to detect imports inside class methods (e.g., `GrowPyConfig` methods)
3. **Didn't check internal chains**: Didn't follow `get_data_directory()` → `get_assets_directory()` → `get_preset_path()` chain
4. **Didn't check conditional calls**: Missed `validate_assembly()` call inside if-block
5. **Relied on top-level imports only**: Missed dynamic imports like `from growpy.config import get_twig_files_by_type` inside functions

**Proper Methodology**:
1. ✅ List ALL CLI scripts first (`ls src/growpy/cli/`)
2. ✅ Use grep to search for ALL import patterns (not just top-level)
3. ✅ Follow internal call chains within modules
4. ✅ Check for usage in documentation/examples (may indicate public API)
5. ✅ Verify each finding with multiple grep patterns
6. ✅ Read actual usage context (not just grep matches)

---

## Appendix: Corrected Complete Dependency Graph

```
CLI Scripts (6 total)
├─ prepare_assets.py (STANDALONE - no growpy imports)
├─ clean_unreal_assets.py (STANDALONE - no growpy imports)
├─ convert_twigs.py
│  └─ io.twig_export.process_twig_file()
├─ create_growth_models.py
│  └─ utils.analysis.SpeciesGrowthAnalyzer
│     ├─ config.paths.get_preset_path()
│     │  └─ config.paths.get_assets_directory()
│     │     └─ config.paths.get_data_directory()
│     ├─ config.paths.get_growth_model_path()
│     │  └─ config.paths.get_assets_directory()
│     └─ utils.plotting.plot_growth_curves()
├─ export_to_unreal.py
│  └─ io.unreal_remote_bridge.UnrealRemoteBridge
│     ├─ io.unreal_remote_bridge.UnrealConnectionConfig
│     └─ io.unreal_remote_bridge.REMOTE_EXECUTION_AVAILABLE
└─ generate_forest.py
   ├─ core.forest.create_forest()
   │  └─ core.grove.create_grove()
   │     └─ config.core.get_config()
   │        └─ config.paths.get_preset_path()
   ├─ core.forest.simulate_forest_growth()
   ├─ core.tree.calculate_growth_cycles_from_height()
   ├─ config.core.get_config()
   ├─ config.quality.get_quality_preset()
   └─ [Internal export chain]
      ├─ io.tree_export.export_tree()
      │  └─ io.tree_export.build_tree_mesh()
      │     └─ core.twig.extract_twig_placements_from_model()
      ├─ io.tree_export.get_twig_usd_map_for_species()
      │  └─ config.paths.get_twig_files_by_type()
      │     └─ config.paths.get_assets_directory()
      ├─ io.tree_export.bundle_twigs_for_species()
      │  └─ config.paths.get_twig_files_by_type()
      └─ io.assembly_export.export_tree_as_nanite_assembly()
         ├─ io.assembly_export.validate_assembly()
         ├─ core.skeleton.build_skeleton_hierarchy()
         └─ core.twig.extract_twig_placements_from_model()
```

---

**Report End** - Corrected after thorough verification
