# Forest Generation Performance Optimizations

Based on profiling results from `--profile` flag (197s total for 8 trees at 25 cycles):

## Profiling Summary

```
Step                                          Total   Calls        Avg       %
--------------------------------------------------------------------------------
total_forest_generation                     197.43s       1   197.433s  100.0%
  export_trees                              190.97s       1   190.967s   96.7%
    grove_export                            190.96s       8    23.871s   96.7%
      export_nanite_assembly_skeletal        96.04s       8    12.005s   48.6%
      generate_wind_json                     74.44s       8     9.305s   37.7%
      export_nanite_assembly_static          13.28s       8     1.660s    6.7%
      generate_pve_json                       6.48s       8     0.810s    3.3%
      build_models                            0.17s       8     0.021s    0.1%
      tag_bone_id                             0.08s       8     0.010s    0.0%
      build_skeletons                         0.04s       8     0.005s    0.0%
  simulate_forest_growth                      6.13s       1     6.135s    3.1%
```

---

## Critical Bottlenecks

### 1. `generate_wind_json` - 37.7% (74.44s)

**Status**: [x] Implemented

**Root Cause**:
The function calls `_extract_joint_names_from_usd()` which re-opens and re-reads the USD file that was just written by `export_nanite_assembly`. This is redundant since we already have the skeleton and bones_info data in memory.

**Solution Implemented**:

- Added `extract_joint_names_from_bones_info()` function to extract joint names directly from bones_info
- Added `joint_names` parameter to `generate_wind_json()` to skip USD reading when provided
- Updated `generate_forest.py` to extract and pass joint names directly

**Current Flow**:

1. `export_tree_as_nanite_assembly()` writes skeletal USD with skeleton
2. `generate_wind_json()` opens the USD file again to extract joint names
3. Joint names are extracted by traversing the USD stage

**Proposed Fix**:

- Pass joint names directly from the skeleton/bones_info rather than re-reading from USD
- Add `joint_names: Optional[List[str]] = None` parameter to `generate_wind_json()`
- Extract joint names during `build_tree_mesh()` and pass through

**Files to modify**:

- `src/growpy/io/wind_json.py` - Add joint_names parameter
- `src/growpy/io/tree_export.py` - Extract and return joint names
- `src/growpy/cli/generate_forest.py` - Pass joint names through

**Estimated Improvement**: 90%+ reduction (9.3s -> <1s per tree)

---

### 2. `export_nanite_assembly_skeletal` - 48.6% (96.04s)

**Status**: [x] Partially Implemented (caching + validation skip)

**Root Causes**:

- a) `build_tree_mesh()` writes skeletal USD with full mesh + skeleton
- b) Texture file copying happens for every tree (even if already copied) - **FIXED: Added caching**
- c) `shutil.copy2()` called repeatedly for same twig files - **FIXED: Added caching**
- d) `_fix_api_schemas_in_assembly()` does regex text processing on saved USD
- e) `validate_assembly()` re-opens USD to validate structure - **FIXED: Added --skip-validation flag**

**Proposed Fixes**:

#### 2a. Cache twig file copying per species

- Move twig file copying to `bundle_twigs_for_species()` (already done once)
- Remove redundant copy logic from `export_tree_as_nanite_assembly()`
- Track copied files in a set to avoid re-copying

**Files to modify**:

- `src/growpy/io/assembly_export.py` - Add copied files cache

#### 2b. Skip validation in production mode

- Add `--skip-validation` CLI flag
- Pass `validate=False` to `export_tree_as_nanite_assembly()`

**Files to modify**:

- `src/growpy/cli/generate_forest.py` - Add CLI flag
- `src/growpy/io/assembly_export.py` - Add validate parameter

#### 2c. Optimize `_fix_api_schemas_in_assembly()`

- Currently reads entire file, does regex, writes back
- Consider using USD API to set metadata directly instead of post-processing

**Estimated Improvement**: 20-30% reduction in skeletal export time

---

## Quick Wins (Implementation Priority)

| Priority | Optimization | Time Saved | Effort | Status |
|----------|-------------|------------|--------|--------|
| 1 | Skip wind JSON with `--skip-wind-json` | ~74s | Done | [x] |
| 2 | Skip PVE JSON with `--skip-pve-json` | ~6s | Done | [x] |
| 3 | Skip static mesh with `--include-static` (default off) | ~13s | Done | [x] |
| 4 | Pass joint names to wind_json directly | ~70s | Done | [x] |
| 5 | Cache twig file copies per species | ~10-20s | Done | [x] |
| 6 | Skip assembly validation in production | ~5-10s | Done | [x] |
| 7 | Add `--fast` flag combining skip options | Variable | Done | [x] |
| 8 | Profile `build_tree_mesh` for breakdown | - | Medium | [ ] |

---

### 3. `export_nanite_assembly_static` - 6.7% (13.28s)

**Status**: [x] Implemented

**Root Cause**:
Static mesh assemblies are generated for every tree even when not needed. Many use cases only require skeletal meshes (for wind animation). Static meshes are 7x faster than skeletal but still add unnecessary overhead when not used.

**Current Behavior**:

- Both skeletal AND static assemblies are always generated for every tree
- Static export happens in a separate pass after skeletal

**Proposed Fix**:

- Add `--skeletal-only` CLI flag to skip static mesh generation
- Make skeletal-only the default behavior
- Add `--include-static` flag for users who need both mesh types
- Update `--fast` flag to also imply `--skeletal-only`

**Files to modify**:

- `src/growpy/cli/generate_forest.py` - Add CLI flags, modify task generation
- `src/growpy/io/assembly_export.py` - No changes needed (already conditional)

**Estimated Improvement**: ~13s saved (6.7% of total time)

---

## Code Changes Required

### Optimization 3: Pass joint names directly

**wind_json.py**:

```python
def generate_wind_json(
    tree_usd_path: Path,
    skeleton: Optional[Any] = None,
    bones_info: Optional[List] = None,
    joint_names: Optional[List[str]] = None,  # NEW
    output_path: Optional[Path] = None,
) -> Dict:
    # Use passed joint_names if available, otherwise read from USD
    if joint_names is None:
        joint_names = _extract_joint_names_from_usd(tree_usd_path)
```

### Optimization 4: Cache twig copies

**assembly_export.py**:

```python
# Module-level cache
_copied_twig_files: Set[Path] = set()

def export_tree_as_nanite_assembly(...):
    # Check cache before copying
    if twig_path not in _copied_twig_files:
        shutil.copy2(twig_path, dest_path)
        _copied_twig_files.add(twig_path)
```

### Optimization 5: Skeletal-only mode (static mesh optional)

**generate_forest.py** - Add CLI flags:

```python
parser.add_argument(
    "--skeletal-only",
    action="store_true",
    default=True,  # Make skeletal-only the default
    help="Only generate skeletal meshes (default behavior)",
)

parser.add_argument(
    "--include-static",
    action="store_true",
    help="Also generate static mesh assemblies",
)
```

**generate_forest.py** - Modify task generation in `export_individual_trees()`:

```python
for grove, species_name, tree_count, fids in forest:
    # Always create skeletal task
    grove_tasks.append(
        (fids, grove, species_name, output_dir, quality_params, "skeletal", verbose, timer)
    )
    
    # Only create static task if explicitly requested
    if quality_params.get("include_static", False):
        grove_tasks.append(
            (fids, grove, species_name, output_dir, quality_params, "static", verbose, timer)
        )
```

### Optimization 6: Fast mode flag (enhanced)

**generate_forest.py**:

```python
parser.add_argument(
    "--fast",
    action="store_true",
    help="Fast mode: skip wind JSON, PVE JSON, validation, and static meshes",
)

# In main():
if args.fast:
    args.skip_wind_json = True
    args.skip_pve_json = True
    args.skip_validation = True
    # skeletal-only is already default
```

---

## Future Considerations

### Batch USD Operations

- Create single stage with multiple tree prims instead of N separate stages
- Would require significant refactoring of export pipeline
- Potential 50%+ improvement but high complexity

### Parallel Export

- Currently sequential due to bpy/USD thread safety
- Could potentially use multiprocessing with separate Python processes
- Would require serializing Grove data between processes

---

## Changelog

- 2024-12-16: Initial profiling analysis
- 2024-12-16: Added `--skip-wind-json` and `--skip-pve-json` flags
