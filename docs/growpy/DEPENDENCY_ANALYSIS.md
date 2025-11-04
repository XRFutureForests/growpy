# GrowPy Package - Dependency Analysis Report

**Generated**: 2025-11-04
**Purpose**: Identify unused modules, functions, and arguments for cleanup

---

## Executive Summary

This report provides a comprehensive analysis of the GrowPy package, mapping dependencies from the 4 main CLI scripts through the entire codebase. The analysis identifies **~150-200 lines of dead code** across **4 complete modules** and **8+ individual functions** that can be safely removed.

**Key Findings**:
- `prepare_assets.py` is completely standalone (no growpy dependencies)
- 4 complete modules are unused: `config/species.py`, `utils/paths.py`, `utils/strings.py`, `io/unreal_remote_bridge.py`
- 8+ individual functions are never called by any CLI workflow
- ~12% of the codebase can be removed without affecting functionality

---

## 1. CLI Scripts Analysis

### 1.1 prepare_assets.py

**Purpose**: Copy Grove 2.2 assets (presets, twigs, textures) to GrowPy assets directory

**Command Line Arguments**:
```bash
--grove-dir PATH      # Source Grove directory (USED)
--assets-dir PATH     # Target assets directory (USED)
--csv PATH            # Species CSV filter (USED)
--all                 # Copy all 57 species (USED)
```

**GrowPy Imports**: **NONE**

**Status**: ✅ **Completely standalone** - Zero dependencies on growpy package

**Recommendation**: Could be moved to `scripts/` folder as utility script

---

### 1.2 convert_twigs.py

**Purpose**: Convert Grove .blend twig files to USD skeletal format

**Command Line Arguments**:
```bash
path                  # Path to twig directory (USED)
--csv PATH            # Species filter CSV (USED)
--formats {usd,usda}  # Export formats (USED)
--clean-export        # Minimal USD export (USED)
```

**GrowPy Imports**:
```python
from growpy.io.twig_export import process_twig_file
```

**Functions Called**:
- `process_twig_file(blend_file, output_dir, formats, species_name, clean_export)`

**Status**: ✅ **Minimal footprint** - Only 1 function from 1 module

---

### 1.3 create_growth_models.py

**Purpose**: Generate height curves and growth prediction models for species

**Command Line Arguments**:
```bash
--assets-dir PATH               # Assets directory (USED)
--csv PATH                      # Species CSV (USED)
--cycles INT                    # Max growth cycles (USED)
--seeds INT                     # Random seeds for averaging (USED)
--height-threshold FLOAT        # Growth detection threshold (USED)
--max-cycles-without-growth INT # Early stop threshold (USED)
--timeout INT                   # Max simulation time (USED)
--species TEXT                  # Specific species (optional) (USED)
```

**GrowPy Imports**:
```python
from growpy.utils.analysis import SpeciesGrowthAnalyzer
```

**Functions Called**:
- `SpeciesGrowthAnalyzer.__init__(assets_dir, cycles, seeds, ...)`
- `analyzer.get_available_species()`
- `analyzer.generate_height_curve_for_species(species)`
- `analyzer.create_growth_model_for_species(species, height_curve)`
- `analyzer.save_species_results(species)`
- `analyzer.save_growth_models()`
- `analyzer.analyze_all_species(parallel, max_workers, species_filter)`

**Dependency Chain**:
```
SpeciesGrowthAnalyzer
├─ config.paths.get_preset_path()
├─ config.paths.get_growth_model_path()
├─ utils.plotting.plot_growth_curves()
└─ the_grove_22_core (external)
```

**Status**: ✅ **Focused** - Heavy user of 1 class with clear dependencies

---

### 1.4 generate_forest.py

**Purpose**: Complete forest generation pipeline with USD/Nanite Assembly export

**Command Line Arguments**: (All 14 arguments are USED)
```bash
csv_file                    # Forest placement CSV
--output-dir PATH           # Export directory
--quality {ultra,high,...}  # Quality preset
--resolution INT            # Vertex count override
--growth-cycle-limit INT    # Max growth cycles
--height-scale FLOAT        # Height scaling factor
--no-multiprocessing        # Disable parallel export
--max-workers INT           # Worker count
--skeleton-length FLOAT     # Bone length multiplier
--skeleton-reduce FLOAT     # Bone reduction factor
--skeleton-bias FLOAT       # Weight bias
--skeleton-disconnected     # Disconnected bones
--clean-export              # Minimal USD
--import-to-unreal          # Generate Unreal script
--unreal-project-path PATH  # Unreal destination
```

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

**Functions Called**:
1. `create_forest(forest_data)` - Create forest from DataFrame
2. `simulate_forest_growth(forest, max_cycles)` - Simulate with light competition
3. `calculate_growth_cycles_from_height(forest_data)` - Height-to-age conversion
4. `get_config()` - Get global configuration
5. `get_quality_preset(quality)` - Get quality parameters
6. Internal: `export_tree_as_nanite_assembly()`
7. Internal: `get_twig_usd_map_for_species()`
8. Internal: `bundle_twigs_for_species()`

**Dependency Chain**:
```
generate_forest.py
├─ growpy.create_forest()
│  └─ core.grove.create_grove()
│     └─ config.core.get_config()
│        └─ config.paths.get_preset_path()
├─ growpy.simulate_forest_growth()
├─ growpy.calculate_growth_cycles_from_height()
├─ growpy.get_config()
├─ config.quality.get_quality_preset()
└─ [Internal export functions]
   ├─ io.tree_export.export_tree()
   │  └─ io.tree_export.build_tree_mesh()
   │     └─ core.twig.extract_twig_placements_from_model()
   ├─ io.tree_export.get_twig_usd_map_for_species()
   ├─ io.tree_export.bundle_twigs_for_species()
   └─ io.assembly_export.export_tree_as_nanite_assembly()
      └─ core.twig.extract_twig_placements_from_model()
```

**Status**: ✅ **Most complex** - Multi-module user with clear workflow

---

## 2. Module Usage Analysis

### 2.1 Core Module (src/growpy/core/)

| File | Function/Class | Used By | Status |
|------|----------------|---------|--------|
| forest.py | `create_forest()` | generate_forest.py | ✅ USED |
| forest.py | `simulate_forest_growth()` | generate_forest.py | ✅ USED |
| grove.py | `create_grove()` | forest.py (indirect) | ✅ USED |
| grove.py | `add_tree_to_grove()` | forest.py (indirect) | ✅ USED |
| tree.py | `calculate_growth_cycles_from_height()` | generate_forest.py | ✅ USED |
| skeleton.py | `build_skeleton_hierarchy()` | assembly_export.py | ✅ USED |
| skeleton.py | `calculate_vertex_weights()` | tree_export.py | ✅ USED |
| skeleton.py | `get_bone_data_from_grove()` | tree_export.py | ✅ USED |
| skeleton.py | `Vector3` (class) | Internal data structure | ✅ DATA CLASS |
| skeleton.py | `JointTransform` (class) | Internal data structure | ✅ DATA CLASS |
| skeleton.py | `SkeletonHierarchy` (class) | Internal data structure | ✅ DATA CLASS |
| twig.py | `extract_twig_placements_from_model()` | assembly_export.py | ✅ USED |
| twig.py | `calculate_twig_transform()` | Internal use | ✅ USED |
| twig.py | `TwigPlacement` (class) | assembly_export.py | ✅ DATA CLASS |

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
| assembly_export.py | `validate_assembly()` | None | ❌ DIAGNOSTIC |
| twig_export.py | `process_twig_file()` | convert_twigs.py | ✅ USED |
| unreal_remote_bridge.py | (entire module) | None | ❌ UNUSED |

**Summary**:
- ✅ Core export functions are used
- ❌ 2 utility functions not called by main workflows
- ❌ 1 diagnostic function unused
- ❌ Entire `unreal_remote_bridge.py` module unused

---

### 2.3 Config Module (src/growpy/config/)

| File | Function | Used By | Status |
|------|----------|---------|--------|
| core.py | `get_config()` | Multiple modules | ✅ USED |
| core.py | `GrowPyConfig` (class) | generate_forest.py | ✅ USED |
| core.py | `from_config_file()` | None | ❌ UNUSED |
| core.py | `to_config_file()` | None | ❌ UNUSED |
| paths.py | `get_preset_path()` | grove.py, analysis.py | ✅ USED |
| paths.py | `get_growth_model_path()` | analysis.py | ✅ USED |
| paths.py | `get_twig_files_by_type()` | None | ❌ UNUSED |
| paths.py | `get_data_directory()` | None | ❌ UNUSED |
| paths.py | `get_assets_directory()` | None | ❌ UNUSED |
| species.py | `get_species_data()` | None | ❌ UNUSED |
| species.py | `get_species_colors()` | None | ❌ UNUSED |
| quality.py | `get_quality_preset()` | generate_forest.py | ✅ USED |
| quality.py | `get_lod_configs()` | None | ❌ UNUSED |

**Summary**:
- ✅ Core config functions used
- ❌ Entire `species.py` module unused (2 functions)
- ❌ 3 path utility functions unused
- ❌ 2 config serialization functions unused
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
- ❌ Entire `paths.py` module unused (2 functions)
- ❌ Entire `strings.py` module unused (2 functions)

---

## 3. Dead Code Identification

### 3.1 Complete Unused Modules (HIGH CONFIDENCE)

These modules can be **safely deleted** without breaking any CLI workflow:

1. **`src/growpy/config/species.py`**
   - Functions: `get_species_data()`, `get_species_colors()`
   - Lines: ~34 lines
   - Reason: No imports anywhere in codebase

2. **`src/growpy/utils/paths.py`**
   - Functions: `ensure_dir()`, `ensure_parent_dir()`
   - Lines: ~30 lines
   - Reason: No imports anywhere in codebase

3. **`src/growpy/utils/strings.py`**
   - Functions: `sanitize_species_name()`, `sanitize_filename()`
   - Lines: ~30 lines
   - Reason: No imports anywhere in codebase

4. **`src/growpy/io/unreal_remote_bridge.py`**
   - Lines: ~50+ lines (estimate)
   - Reason: No imports anywhere in codebase

**Total Removable**: ~144+ lines across 4 complete modules

---

### 3.2 Individual Unused Functions (HIGH CONFIDENCE)

These functions can be **safely removed** without breaking any CLI workflow:

1. **`config.core.from_config_file()`**
   - Purpose: Load config from YAML/JSON file
   - Reason: Config is always created programmatically, never loaded from file

2. **`config.core.to_config_file()`**
   - Purpose: Save config to YAML/JSON file
   - Reason: Config is never persisted to disk

3. **`config.paths.get_twig_files_by_type()`**
   - Purpose: Discover twig files by semantic type
   - Reason: Twig discovery happens via direct directory scanning

4. **`config.paths.get_data_directory()`**
   - Purpose: Get data directory path
   - Reason: Paths are always constructed directly in CLI scripts

5. **`config.paths.get_assets_directory()`**
   - Purpose: Get assets directory path
   - Reason: Paths are always constructed directly in CLI scripts

6. **`config.quality.get_lod_configs()`**
   - Purpose: Get LOD (Level of Detail) configurations
   - Reason: Only `get_quality_preset()` is used, LOD configs unused

7. **`io.assembly_export.validate_assembly()`**
   - Purpose: Validate USD assembly structure
   - Reason: Diagnostic utility never called in production workflow

**Total Removable**: ~50+ lines across 7 functions

---

### 3.3 Conditional Usage Functions (KEEP FOR NOW)

These functions are not called by main CLI workflows but may be useful for custom workflows:

1. **`io.tree_export.add_skeleton_to_usd()`**
   - Purpose: Post-processing utility to add skeleton to existing USD
   - Recommendation: Keep as utility function for manual workflows

2. **`io.tree_export.add_twig_skeleton_to_usd()`**
   - Purpose: Post-processing utility to add twig skeleton
   - Recommendation: Keep as utility function for manual workflows

---

## 4. Cleanup Recommendations

### Phase 1: Immediate Safe Removal (HIGH CONFIDENCE)

**Delete these 4 complete modules**:
```bash
rm src/growpy/config/species.py
rm src/growpy/utils/paths.py
rm src/growpy/utils/strings.py
rm src/growpy/io/unreal_remote_bridge.py
```

**Update `__init__.py` files** to remove imports:
- [src/growpy/config/__init__.py](src/growpy/config/__init__.py): Remove `get_species_data`, `get_species_colors`
- [src/growpy/utils/__init__.py](src/growpy/utils/__init__.py): Remove `ensure_dir`, `ensure_parent_dir`, `sanitize_species_name`, `sanitize_filename`

**Remove individual functions**:
- [src/growpy/config/core.py](src/growpy/config/core.py): Remove `from_config_file()`, `to_config_file()`
- [src/growpy/config/paths.py](src/growpy/config/paths.py): Remove `get_twig_files_by_type()`, `get_data_directory()`, `get_assets_directory()`
- [src/growpy/config/quality.py](src/growpy/config/quality.py): Remove `get_lod_configs()`
- [src/growpy/io/assembly_export.py](src/growpy/io/assembly_export.py): Remove `validate_assembly()`

**Estimated impact**: ~150-200 lines removed, ~12% codebase reduction

---

### Phase 2: Optional Reorganization

**Consider moving `prepare_assets.py`**:
- Current: `src/growpy/cli/prepare_assets.py`
- Proposed: `scripts/prepare_assets.py` (since it has zero growpy dependencies)
- Benefit: Clearer separation of standalone utilities vs. package-dependent CLI tools

**Consider keeping utility functions**:
- `add_skeleton_to_usd()` - May be useful for custom post-processing
- `add_twig_skeleton_to_usd()` - May be useful for custom post-processing

---

## 5. Import Summary

### Complete list of growpy imports across all 4 CLI scripts:

```python
# prepare_assets.py
# (NONE - completely standalone)

# convert_twigs.py
from growpy.io.twig_export import process_twig_file

# create_growth_models.py
from growpy.utils.analysis import SpeciesGrowthAnalyzer

# generate_forest.py
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

**Total unique imports**: 8 functions/classes from 4 modules

---

## 6. Final Metrics

- **Total Python files analyzed**: 33 files
- **Total files used by CLI workflows**: ~15 files
- **Dead code modules**: 4 complete modules
- **Dead code functions**: 8+ individual functions
- **Total removable lines**: ~150-200 lines
- **Cleanup potential**: ~12% of codebase

---

## 7. Testing Recommendations

Before removing code, verify with:

```bash
# Run all 4 CLI scripts with test data
python src/growpy/cli/prepare_assets.py --csv data/input/test.csv
python src/growpy/cli/convert_twigs.py data/assets/twigs --csv data/input/test.csv
python src/growpy/cli/create_growth_models.py --cycles 25
python src/growpy/cli/generate_forest.py data/input/test.csv --quality high --growth-cycle-limit 5

# Check for import errors
python -c "from growpy import *; print('All imports successful')"
```

---

## Appendix: Complete Dependency Graph

```
CLI Scripts
├─ prepare_assets.py (STANDALONE - no growpy imports)
├─ convert_twigs.py
│  └─ io.twig_export.process_twig_file()
├─ create_growth_models.py
│  └─ utils.analysis.SpeciesGrowthAnalyzer
│     ├─ config.paths.get_preset_path()
│     ├─ config.paths.get_growth_model_path()
│     └─ utils.plotting.plot_growth_curves()
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
      ├─ io.tree_export.bundle_twigs_for_species()
      └─ io.assembly_export.export_tree_as_nanite_assembly()
         ├─ core.skeleton.build_skeleton_hierarchy()
         └─ core.twig.extract_twig_placements_from_model()
```

---

**Report End** - Ready for cleanup implementation
