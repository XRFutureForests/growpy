# GrowPy Refactoring Plan

**Status:** In Progress
**Date:** 2025-10-17

## Completed

### ✅ Utility Modules Created
- `src/growpy/utils/strings.py` - String sanitization functions
- `src/growpy/utils/paths.py` - Path utilities
- Updated `src/growpy/utils/__init__.py` with exports

### ✅ Core Module Cleanup
- `src/growpy/core/grove.py` - Removed try/except, added type hints, simplified docstrings
- `src/growpy/core/forest.py` - Removed try/except, added type hints, cleaned up

## In Progress

### Config Module Refactoring

**Current State:**
- `config/settings.py`: 905 lines - too large
- Mix of concerns: settings, species lookup, path resolution, LOD configs
- Global singleton pattern

**Proposed Structure:**
```
src/growpy/config/
├── __init__.py                 # Exports and config loading
├── core.py                     # Core GrowPyConfig class (~150 lines)
├── species.py                  # Species lookup and matching (~200 lines)
├── paths.py                    # Asset path resolution (~200 lines)
├── quality.py                  # LOD/quality presets (~100 lines)
└── tree_asset_lookup.csv       # (unchanged)
```

**Changes:**

1. **config/core.py** - Core configuration
   - GrowPyConfig dataclass with essential settings
   - Config file loading (config.ini support)
   - No asset path logic (delegated to paths.py)

2. **config/species.py** - Species operations
   - load_species_lookup() with caching
   - find_species_match() with LRU cache
   - get_species_colors(), get_bark_texture()

3. **config/paths.py** - Path resolution
   - AssetPathResolver class
   - All get_*_path() methods
   - get_twig_files_by_type(), etc.

4. **config/quality.py** - Quality presets
   - get_all_lod_configs()
   - get_quality_preset()
   - Quality parameter validation

### Blender Export Module Decomposition

**Current State:**
- `io/blender_export.py`: 4116 lines - way too large

**Proposed Structure:**
```
src/growpy/io/
├── __init__.py                      # Main exports
├── export/
│   ├── __init__.py                  # Export function exports
│   ├── usd.py                       # USD export (~800 lines)
│   ├── fbx.py                       # FBX export (~600 lines)
│   ├── skeleton.py                  # Skeleton creation (~400 lines)
│   ├── quality.py                   # Quality presets (~200 lines)
│   └── blender_utils.py             # Blender scene mgmt (~300 lines)
├── nanite/
│   ├── __init__.py
│   ├── attributes.py                # Nanite USD attributes (~300 lines)
│   └── validation.py                # Mesh validation (~300 lines)
├── twig/
│   ├── __init__.py
│   ├── bundling.py                  # Twig bundling (~400 lines)
│   ├── placement.py                 # (rename from twig_placement.py)
│   └── processor.py                 # (rename from blender_twig_processor.py)
├── unreal_metadata.py               # (unchanged)
└── unreal_nanite_assembly.py        # (unchanged)
```

## Pending

### Remaining Core Cleanup
- [ ] `core/tree.py` - Simplify, add type hints

### Remaining IO Cleanup
- [ ] Remove print statements from all io/ modules
- [ ] Simplify try/except blocks

### CLI Refactoring
- [ ] Create `cli/common.py` with shared utilities
- [ ] Simplify `generate_forest.py`
- [ ] Simplify `convert_twigs.py`
- [ ] Simplify `create_growth_models.py`

### Config File System
- [ ] Create default `config.ini` template
- [ ] Support loading from project root
- [ ] Document configuration options

### Performance
- [ ] Add LRU caching to species lookup
- [ ] Lazy load species CSV
- [ ] Cache growth models

### Documentation
- [ ] Update all Google-style docstrings
- [ ] Create module documentation in `docs/growpy/`
- [ ] Update CLI help text with proper paths

## Risks & Considerations

### Breaking Changes
- Import paths will change for internal modules
- Config singleton removal may affect existing code
- File structure changes may break tools that hardcode paths

### Migration Strategy
1. Create new modules alongside old ones
2. Update imports module by module
3. Test each module independently
4. Remove old modules once all imports updated
5. Update documentation last

### Testing Strategy
- Manual testing with existing forest CSV files
- Verify export outputs match previous versions
- Check all CLI commands still work

## Decision Points

### Q: Keep backward compatibility?
**A:** No - this is internal refactoring, clean break is fine

### Q: Update __init__.py exports?
**A:** Yes - maintain same public API from top-level growpy module

### Q: How to handle config migration?
**A:** Provide config.ini template, document in README

## Next Steps

1. Create config module split first (most impactful)
2. Test config changes thoroughly
3. Create blender_export split
4. Update all imports
5. CLI improvements
6. Documentation pass

## Estimated Timeline

- Config refactoring: 2-3 hours
- Blender export split: 4-5 hours
- Import updates: 1 hour
- CLI improvements: 1-2 hours
- Documentation: 2-3 hours

**Total: 10-14 hours**
