# GrowPy Package - Optimization and Refactoring Recommendations

**Document Version:** 1.1
**Date:** 2026-01-09 (updated 2026-02-27)
**Purpose:** Actionable recommendations for optimizing and refactoring GrowPy

> **Status as of 2026-02-27**: Priorities 1 (critical cleanup), 2 (structural improvements), 3 (performance), and 4 (external script integration) have been implemented. See `docs/growpy/refactoring-plan.md` for per-phase completion status. This document is retained as an architectural reference.

---

## Executive Summary

Based on comprehensive analysis of the GrowPy codebase, this document provides detailed, prioritized recommendations for optimization and refactoring. The goal is to maintain current functionality while improving maintainability, performance, and code quality.

**Key Findings (at time of analysis)**:

- 84+ print statements in production code (should use logging) — **resolved**
- 50+ fallback code paths (many unnecessary)
- 7 files with deprecated/TODO markers
- Single test file (minimal coverage)
- Multiple configuration systems with overlapping responsibilities

**Estimated Impact**: 15-20% reduction in code size, 10-15% performance improvement, significantly better maintainability

---

## Priority 1: Critical Cleanup (High Impact, Low Risk)

### 1.1 Replace Print Statements with Logging

**Current State**: 84 print statements in CLI scripts alone, 23 files total

**Target Files**:
```
High Priority (20+ print statements each):
- cli/generate_forest.py (78 statements)
- io/assembly_export.py (multiple debug prints)
- io/pve_grove_mapper.py (verbose output)
- core/forest.py (progress messages)

Medium Priority (5-20 statements):
- cli/prepare_assets.py (3 statements)
- cli/convert_twigs.py (2 statements)
- cli/create_growth_models.py (1 statement)
```

**Implementation Plan**:

1. **Create logging configuration** (`src/growpy/utils/logging_config.py`):
```python
import logging
import sys

def setup_logging(verbose: bool = False):
    """Setup package-wide logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger('growpy')
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

def get_logger(name: str):
    """Get logger for module."""
    return logging.getLogger(f'growpy.{name}')
```

2. **Replace print statements systematically**:

**Before**:
```python
print(f"Exporting tree {tree_id}...")
print(f"  Generated {len(twigs)} twig instances")
```

**After**:
```python
logger = get_logger(__name__)
logger.info(f"Exporting tree {tree_id}...")
logger.debug(f"Generated {len(twigs)} twig instances")
```

3. **Update CLI scripts to initialize logging**:
```python
from growpy.utils.logging_config import setup_logging

def main():
    parser = argparse.ArgumentParser(...)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = get_logger(__name__)

    logger.info("Starting forest generation...")
```

**Log Level Guidelines**:
- DEBUG: Detailed diagnostic information (twig counts, bone IDs, file paths)
- INFO: Progress messages, major steps completed
- WARNING: Fallback used, missing optional data
- ERROR: Operation failed but recoverable
- CRITICAL: Fatal errors requiring abort

**Effort**: 2-3 days
**Risk**: Low (backward compatible, gradual rollout)
**Benefit**: Professional logging, better debugging, cleaner output

---

### 1.2 Remove Deprecated Functions and Parameters

**Identified Deprecated Code**:

1. **io/tree_export.py:72** - `export_tree_mesh()` function
   - Marked DEPRECATED
   - Has replacement: `build_tree_mesh()` with `include_skeleton=False`
   - **Action**: Delete function entirely, update any callers

2. **io/tree_export.py:147-150** - Skeleton parameters
   - `skeleton_length`, `skeleton_reduce`, `skeleton_bias`, `skeleton_connected`
   - Marked deprecated if `bones_info` provided
   - **Action**: Remove parameters, use `bones_info` exclusively

3. **io/assembly_export.py:113** - `skeleton_source_usd` parameter
   - Marked deprecated - skeleton now embedded in tree_usd_path
   - **Action**: Remove parameter from function signature

4. **io/pve_grove_mapper.py:1043** - Deprecated parent calculation
   - Function marked DEPRECATED but still present
   - **Action**: Remove function if unused, or mark as internal helper

5. **io/pve_hierarchy_builder.py:84, 164** - Legacy `model` parameter
   - Kept for compatibility but not used
   - **Action**: Remove parameter, update all callers

**Implementation Steps**:

1. Search for all usages of deprecated functions
2. Update callers to use new API
3. Delete deprecated functions
4. Update tests if any
5. Update documentation to remove references

**Example Refactoring**:

**Before**:
```python
def build_tree_mesh(
    model,
    skeleton=None,
    bones_info=None,
    skeleton_length=2.0,  # DEPRECATED
    skeleton_reduce=0.4,  # DEPRECATED
    skeleton_bias=0.5,    # DEPRECATED
    skeleton_connected=True,  # DEPRECATED
    ...
):
    if bones_info:
        # Use bones_info (new way)
    else:
        # Use skeleton parameters (deprecated fallback)
```

**After**:
```python
def build_tree_mesh(
    model,
    skeleton=None,
    bones_info=None,  # Required if skeleton provided
    ...
):
    if skeleton and not bones_info:
        raise ValueError("bones_info required when skeleton provided")
    if bones_info:
        # Use bones_info (only way)
```

**Effort**: 1-2 days
**Risk**: Medium (requires updating callers)
**Benefit**: Cleaner API, less confusion, smaller codebase

---

### 1.3 Clean Up TODO/FIXME/NOTE Comments

**Current State**: 7 files with TODO/FIXME/NOTE markers

**Target Files**:
- `io/create_minimal_pve_test.py`
- `io/tree_export.py`
- `io/pve_grove_mapper.py`
- `cli/generate_forest.py`
- `io/pve_preset_json.py`
- `io/twig_export.py`
- `io/pve_hierarchy_builder.py`

**Implementation Plan**:

1. **Audit all TODO/FIXME/NOTE comments**:
   ```bash
   grep -rn "TODO\|FIXME\|XXX\|HACK\|NOTE:" src/growpy/
   ```

2. **Categorize by action**:
   - **Resolve**: Implement the TODO
   - **Convert to issue**: Create GitHub/Linear issue
   - **Remove**: Outdated or no longer relevant
   - **Document**: Move to proper documentation

3. **Resolution workflow**:
   - If < 30 min to fix: Do it now
   - If > 30 min: Create issue with context
   - If obsolete: Remove comment

**Example Actions**:

```python
# TODO: Add validation for negative heights
# → Create issue: "Add input validation for height values"

# FIXME: This is a temporary workaround for missing textures
# → Investigate if still needed, remove if textures now required

# NOTE: This algorithm is from the original Grove implementation
# → Move to docstring or architecture documentation
```

**Effort**: 1 day
**Risk**: Low
**Benefit**: Clearer code, better issue tracking

---

## Priority 2: Structural Improvements (Medium Impact, Medium Risk)

### 2.1 Reduce Fallback Complexity in Path Resolution

**Current State**: `config/paths.py` has 8+ fallback attempts per asset lookup

**Problem Areas**:

1. **get_preset_path()**: 4 fallback strategies
   - Standardized name
   - Original Grove name
   - Lookup table derivation
   - Growth model column (legacy)

2. **get_twig_directory()**: 3 fallback strategies
   - Standardized name
   - Original Grove name
   - Without _twig suffix

3. **get_bark_texture_path()**: Similar multi-level fallbacks

**Proposed Simplification**:

**Strategy**: Standardize everything during prepare_assets.py, eliminate fallbacks

1. **Enforce standard naming in prepare_assets.py**:
   - Always convert to snake_case
   - Create symlinks for backward compatibility if needed
   - Generate asset manifest JSON

2. **Create asset manifest** (`data/assets/manifest.json`):
```json
{
    "species": {
        "european_beech": {
            "preset": "data/assets/presets/european_beech.seed.json",
            "twigs": "data/assets/twigs/european_beech_twig",
            "texture": "data/assets/textures/european_beech_60_bark.jpg",
            "growth_model": "data/assets/growth_models/european_beech_growth_model.json",
            "pve_config": "data/assets/pve_configs/european_beech_pve.json"
        }
    }
}
```

3. **Simplify path resolution**:
```python
def get_preset_path(species_name: str) -> Path:
    """Get preset path with single manifest lookup."""
    manifest = load_asset_manifest()

    if species_name not in manifest['species']:
        raise AssetNotFoundError(f"Species '{species_name}' not in manifest")

    preset_path = Path(manifest['species'][species_name]['preset'])

    if not preset_path.exists():
        raise AssetNotFoundError(f"Preset file missing: {preset_path}")

    return preset_path
```

**Benefits**:
- Single source of truth (manifest)
- Fast lookups (no file system scanning)
- Clear error messages
- Easy to validate asset completeness
- No silent fallbacks

**Migration Path**:
1. Add manifest generation to prepare_assets.py
2. Update path resolution to check manifest first, fallback to old logic
3. Add warning when fallback used
4. After validation period, remove fallback logic

**Effort**: 2-3 days
**Risk**: Medium (affects all asset loading)
**Benefit**: Faster lookups, clearer errors, easier debugging

---

### 2.2 Consolidate Configuration Systems

**Current State**: Multiple overlapping configuration sources

**Configuration Sources**:
1. Quality presets (`config/quality.py`)
2. Preset overrides (`config/preset_overrides.py`)
3. PVE species overrides (`config/pve_species_overrides.py`)
4. Asset lookup CSV (`config/tree_asset_lookup.csv`)
5. Seed.json files (embedded curves)

**Overlap Examples**:
- Skeleton parameters in quality presets AND preset overrides
- Species-specific values in PVE configs AND seed.json
- Asset paths in lookup CSV AND hardcoded paths

**Proposed Unified System**:

**Create single configuration hierarchy**:

```
Configuration Hierarchy (highest to lowest priority):
1. CLI arguments (--preset-override, --quality, etc.)
2. Per-tree overrides (future feature)
3. Species configuration files (data/assets/species/{name}.yaml)
4. Quality presets (config/quality.py)
5. Global defaults (config/defaults.py)
```

**Species Configuration File** (`data/assets/species/european_beech.yaml`):
```yaml
species:
  common_name: "European beech"
  standardized_name: "european_beech"
  family: "Fagaceae"

assets:
  preset: "presets/european_beech.seed.json"
  twigs: "twigs/european_beech_twig"
  texture: "textures/european_beech_60_bark.jpg"
  growth_model: "growth_models/european_beech_growth_model.json"

simulation:
  # Override default parameters
  drop_decay: 0.15
  light_power: 1.2

  # Interpolated curves
  curves:
    drop_weak:
      - [0, 0.3]
      - [50, 0.2]
      - [100, 0.1]

pve:
  # PVE-specific overrides
  branch_distribution: "monopodial"
  leaf_angle: 45

quality_adjustments:
  ultra:
    skeleton_length: 0.15  # Slightly different from default
  high:
    skeleton_length: 0.3
```

**Configuration Loading**:
```python
class SpeciesConfig:
    """Unified species configuration."""

    def __init__(self, species_name: str):
        self.species_name = species_name
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML."""
        config_path = Path(f"data/assets/species/{self.species_name}.yaml")
        if config_path.exists():
            return yaml.safe_load(config_path.read_text())
        return self._get_defaults()

    def get_simulation_params(self, quality: str, cli_overrides: dict) -> dict:
        """Get final simulation parameters with precedence."""
        params = {}

        # Start with quality preset
        params.update(get_quality_preset(quality))

        # Apply species defaults
        params.update(self.config.get('simulation', {}))

        # Apply quality-specific adjustments
        quality_adj = self.config.get('quality_adjustments', {}).get(quality, {})
        params.update(quality_adj)

        # Apply CLI overrides (highest priority)
        params.update(cli_overrides)

        return params
```

**Migration Strategy**:
1. Generate YAML files from existing sources (prepare_assets.py)
2. Update path resolution to use YAML asset paths
3. Update simulation to load params from YAML
4. Deprecate old configuration files
5. Remove old configuration code after validation

**Effort**: 4-5 days
**Risk**: Medium-High (affects entire configuration system)
**Benefit**: Single source of truth, clearer precedence, easier to understand

---

### 2.3 Improve Error Handling and Fail-Fast Behavior

**Current Issues**:
- Silent failures with default values
- Generic exception catching
- Error messages printed but not raised
- Unclear failure modes

**Implementation Plan**:

1. **Create custom exception hierarchy**:
```python
# src/growpy/exceptions.py

class GrowPyError(Exception):
    """Base exception for all GrowPy errors."""
    pass

class AssetNotFoundError(GrowPyError):
    """Required asset file not found."""
    pass

class InvalidSpeciesError(GrowPyError):
    """Species not recognized or invalid."""
    pass

class SimulationError(GrowPyError):
    """Error during growth simulation."""
    pass

class ExportError(GrowPyError):
    """Error during USD export."""
    pass

class ValidationError(GrowPyError):
    """Data validation failed."""
    pass
```

2. **Replace silent failures**:

**Before**:
```python
def get_preset_path(species_name: str) -> Path:
    # Try multiple fallbacks
    for attempt in fallback_strategies:
        path = attempt(species_name)
        if path and path.exists():
            return path
    # Silent failure - returns None
    return None

# Caller has to check for None
preset_path = get_preset_path(species)
if not preset_path:
    print("Warning: Preset not found, using defaults")
    # Continue with potentially broken state
```

**After**:
```python
def get_preset_path(species_name: str) -> Path:
    """Get preset path - raises if not found."""
    manifest = load_asset_manifest()

    if species_name not in manifest['species']:
        available = list(manifest['species'].keys())
        raise InvalidSpeciesError(
            f"Species '{species_name}' not found. "
            f"Available species: {', '.join(available[:5])}... "
            f"Run 'prepare_assets.py' to add this species."
        )

    preset_path = Path(manifest['species'][species_name]['preset'])

    if not preset_path.exists():
        raise AssetNotFoundError(
            f"Preset file missing: {preset_path}. "
            f"Run 'prepare_assets.py' to regenerate assets."
        )

    return preset_path

# Caller doesn't need to check - exception bubbles up
preset_path = get_preset_path(species)  # Guaranteed to be valid
```

3. **Add validation at entry points**:
```python
def generate_forest_exports(...):
    """Generate forest - validates inputs first."""
    # Validate CSV
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Validate output directory writable
    if output_dir.exists() and not os.access(output_dir, os.W_OK):
        raise PermissionError(f"Output directory not writable: {output_dir}")

    # Validate all species have assets
    forest_data = pd.read_csv(csv_path)
    missing_species = []
    for species in forest_data['species'].unique():
        try:
            get_preset_path(species)
        except (InvalidSpeciesError, AssetNotFoundError) as e:
            missing_species.append((species, str(e)))

    if missing_species:
        error_msg = "Missing assets for species:\n"
        for species, reason in missing_species:
            error_msg += f"  - {species}: {reason}\n"
        raise AssetNotFoundError(error_msg)

    # All validation passed - proceed with generation
```

4. **Use warnings module for non-critical issues**:
```python
import warnings

def export_tree_as_nanite_assembly(...):
    """Export tree - warns about fallbacks."""
    # Example: twig type fallback
    if twig_type not in twig_type_to_proto_idx:
        if twig_type in fallback_map:
            mapped_type = fallback_map[twig_type]
            warnings.warn(
                f"Twig type '{twig_type}' not found, using '{mapped_type}' "
                f"as fallback. Consider adding dedicated '{twig_type}' twig variant.",
                UserWarning
            )
```

**Effort**: 3-4 days
**Risk**: Medium (changes error behavior)
**Benefit**: Easier debugging, clearer failures, better UX

---

## Priority 3: Performance Optimizations (Medium Impact, Low Risk)

### 3.1 Optimize File Operations

**Current Bottlenecks**:

1. **Twig file copying during export**:
   - Copy twig files for each tree even if already copied
   - Partial cache exists but not comprehensive

2. **Texture processing during prepare_assets**:
   - Process same texture multiple times
   - No caching of processed textures

3. **Repeated file existence checks**:
   - Check same path multiple times in loops
   - No memoization

**Proposed Optimizations**:

**1. Expand Twig Copy Cache**:

**Current** (io/assembly_export.py):
```python
# Partial cache - only tracks within single export
_twig_copy_cache = set()

def clear_twig_copy_cache():
    global _twig_copy_cache
    _twig_copy_cache.clear()
```

**Improved**:
```python
# Persistent cache across entire forest export
class TwigCopyCache:
    def __init__(self):
        self.cache = {}  # {(src, dst) -> bool}
        self.hits = 0
        self.misses = 0

    def should_copy(self, src: Path, dst: Path) -> bool:
        """Check if file needs copying."""
        key = (str(src), str(dst))

        if key in self.cache:
            self.hits += 1
            return False

        # Check if destination exists and is newer
        if dst.exists():
            if dst.stat().st_mtime >= src.stat().st_mtime:
                self.cache[key] = True
                self.hits += 1
                return False

        self.misses += 1
        return True

    def mark_copied(self, src: Path, dst: Path):
        """Mark file as copied."""
        key = (str(src), str(dst))
        self.cache[key] = True

    def get_stats(self):
        return f"Cache: {self.hits} hits, {self.misses} misses"
```

**2. Batch Texture Processing**:

**Current** (cli/prepare_assets.py):
```python
# Process textures one at a time
for twig_dir in twig_dirs:
    process_twig_textures(twig_dir)  # Slow
```

**Improved**:
```python
from concurrent.futures import ThreadPoolExecutor

def batch_process_textures(twig_dirs: List[Path], max_workers: int = 4):
    """Process textures in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_twig_textures, twig_dirs))
    return results
```

**3. Memoize File Existence Checks**:

```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def check_file_exists(path_str: str) -> bool:
    """Cached file existence check."""
    return Path(path_str).exists()

# Use in hot loops
for species in species_list:
    preset_path_str = str(get_preset_path(species))
    if check_file_exists(preset_path_str):
        # ... process
```

**Estimated Performance Gain**: 10-15% faster overall pipeline

**Effort**: 2-3 days
**Risk**: Low
**Benefit**: Faster exports, especially for large forests

---

### 3.2 Memory Management Improvements

**Current Issues**:
1. Grove instances kept alive until all exports complete
2. Large model lists held in memory
3. Manual garbage collection only after tree export

**Proposed Improvements**:

**1. Incremental Grove Processing**:

**Current**:
```python
# All groves kept alive
forest = create_forest(forest_data)  # List of groves
simulate_forest_growth(forest, cycles)  # All simulated
export_individual_trees(forest, ...)  # All exported together
# Groves released only after ALL exports complete
```

**Improved**:
```python
# Process groves incrementally
def generate_forest_exports_incremental(...):
    """Generate forest with incremental processing."""
    # Phase 1: Simulate all (inter-species competition requires this)
    forest = create_forest(forest_data)
    simulate_forest_growth(forest, cycles)

    # Phase 2: Export incrementally, release immediately
    for grove, species, count, fids in forest:
        export_grove(grove, species, fids, output_dir)
        del grove  # Release immediately
        gc.collect()

    del forest
```

**2. Streaming for Very Large Forests**:

```python
def generate_forest_streaming(csv_path: Path, chunk_size: int = 100):
    """Process forest in chunks for very large datasets."""
    # Read CSV in chunks
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        # Process chunk
        forest_chunk = create_forest(chunk)
        simulate_forest_growth(forest_chunk, cycles)
        export_individual_trees(forest_chunk, ...)

        # Release chunk
        del forest_chunk
        gc.collect()
```

**3. Memory Profiling**:

```python
# Add memory tracking to profiler
from memory_profiler import profile

@profile
def export_tree_as_nanite_assembly(...):
    """Export with memory profiling."""
    # ... existing code
```

**Estimated Memory Reduction**: 30-40% lower peak memory usage

**Effort**: 2-3 days
**Risk**: Low
**Benefit**: Handle larger forests, fewer crashes

---

## Priority 4: Testing and Quality (Low Impact, Low Risk)

### 4.1 Comprehensive Test Suite

**Current State**: Single test file (tests/test_pve_generation.py)

**Proposed Test Structure**:

```
tests/
├── unit/
│   ├── test_core_tree.py
│   ├── test_core_grove.py
│   ├── test_core_forest.py
│   ├── test_core_skeleton.py
│   ├── test_core_twig.py
│   ├── test_config_quality.py
│   ├── test_config_preset_overrides.py
│   └── test_config_paths.py
├── integration/
│   ├── test_cli_prepare_assets.py
│   ├── test_cli_convert_twigs.py
│   ├── test_cli_create_growth_models.py
│   └── test_cli_generate_forest.py
├── regression/
│   ├── test_usd_export_format.py
│   └── test_pve_json_schema.py
└── fixtures/
    ├── test_assets/
    └── test_data.csv
```

**Test Coverage Goals**:
- Unit tests: 80% coverage
- Integration tests: All CLI scripts
- Regression tests: Export formats

**Example Unit Test**:

```python
# tests/unit/test_config_paths.py

import pytest
from pathlib import Path
from growpy.config.paths import get_preset_path
from growpy.exceptions import InvalidSpeciesError

def test_get_preset_path_valid_species(tmp_path):
    """Test preset path resolution for valid species."""
    # Setup test manifest
    manifest = {
        'species': {
            'test_species': {
                'preset': str(tmp_path / 'test.seed.json')
            }
        }
    }
    write_manifest(tmp_path, manifest)

    # Create preset file
    preset_path = tmp_path / 'test.seed.json'
    preset_path.write_text('{}')

    # Test
    result = get_preset_path('test_species')
    assert result == preset_path
    assert result.exists()

def test_get_preset_path_invalid_species():
    """Test that invalid species raises clear error."""
    with pytest.raises(InvalidSpeciesError) as exc_info:
        get_preset_path('nonexistent_species')

    assert 'not found' in str(exc_info.value)
    assert 'Available species' in str(exc_info.value)
```

**Effort**: 5-7 days
**Risk**: Low (doesn't affect production code)
**Benefit**: Safer refactoring, fewer regressions, better quality

---

## Implementation Roadmap

### Phase 1: Critical Cleanup (Week 1-2)
- [ ] Replace print statements with logging (Priority 1.1)
- [ ] Remove deprecated functions (Priority 1.2)
- [ ] Clean up TODO/FIXME comments (Priority 1.3)

**Deliverable**: Cleaner codebase with professional logging

### Phase 2: Structural Improvements (Week 3-5)
- [ ] Reduce fallback complexity (Priority 2.1)
- [ ] Consolidate configuration systems (Priority 2.2)
- [ ] Improve error handling (Priority 2.3)

**Deliverable**: Simpler, more maintainable architecture

### Phase 3: Performance Optimizations (Week 6-7)
- [ ] Optimize file operations (Priority 3.1)
- [ ] Improve memory management (Priority 3.2)

**Deliverable**: Faster, more memory-efficient pipeline

### Phase 4: Testing and Quality (Week 8-10)
- [ ] Build comprehensive test suite (Priority 4.1)
- [ ] Set up CI/CD
- [ ] Documentation updates

**Deliverable**: Production-ready, well-tested package

---

## Success Metrics

**Code Quality**:
- [ ] Zero print() statements in library code
- [ ] Zero deprecated function warnings
- [ ] Zero TODO/FIXME in production code
- [ ] 80%+ test coverage

**Performance**:
- [ ] 10-15% faster overall pipeline
- [ ] 30-40% lower peak memory usage
- [ ] 50%+ reduction in file I/O operations

**Maintainability**:
- [ ] 15-20% reduction in code size
- [ ] Single configuration system
- [ ] Clear error messages with actionable suggestions
- [ ] Comprehensive documentation

**User Experience**:
- [ ] Professional logging output
- [ ] Fast failure with clear messages
- [ ] Progress indicators for long operations
- [ ] Helpful error recovery suggestions

---

## Risk Mitigation

### High-Risk Changes
- Configuration consolidation (Priority 2.2)
- Error handling changes (Priority 2.3)

**Mitigation Strategy**:
1. Implement behind feature flag
2. Gradual rollout with fallback to old behavior
3. Comprehensive testing before cutover
4. Clear migration guide
5. Version bump (1.x → 2.0)

### Medium-Risk Changes
- Path resolution simplification (Priority 2.1)
- Deprecated function removal (Priority 1.2)

**Mitigation Strategy**:
1. Add deprecation warnings first
2. Update documentation
3. Provide migration scripts
4. Maintain backward compatibility for 1 release

### Low-Risk Changes
- Logging (Priority 1.1)
- Performance optimizations (Priority 3.1, 3.2)
- Testing (Priority 4.1)

**Mitigation Strategy**:
- Standard testing and review process

---

## Conclusion

These optimizations will significantly improve the GrowPy package while maintaining its current functionality. The incremental approach allows for safe, gradual refactoring with minimal risk.

**Recommended Starting Point**: Priority 1 (Critical Cleanup) - high impact, low risk, fast to implement.

**Long-Term Goal**: Professional, maintainable, performant codebase suitable for production use and future enhancements.
