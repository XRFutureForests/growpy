# Twig Nanite Assembly Removal - 2025-10-08

## Change Summary

Removed Nanite Assembly USD file creation from twig conversion process. Twigs now only export as regular static USD meshes.

## Rationale

### Problem with Nanite Assembly Twigs

Using Nanite Assembly USD files as references within tree USD files causes Unreal Engine 5.7 to crash on import. This was discovered when:

1. **Beech trees crashed** - Referenced `europeanbeech_var_b_NaniteAssembly.usda`
2. **Oak trees worked** - Referenced `europeanoak_lateral.usda` (regular USD)

### Root Cause

**Nanite Assembly is designed for top-level imports only**, not for USD composition (references, sublayers, payloads). When used as a reference:

- Creates nested Nanite Assembly contexts
- Conflicts with skeletal mesh binding
- Causes material duplication issues
- Triggers Unreal's Nanite hierarchy builder to crash

### Correct Usage Pattern

```
✅ CORRECT:
TreeAssembly (Nanite Assembly at top level)
├─ Tree mesh (regular USD reference)
└─ Twigs (regular USD references)
   └─ twig.usda

❌ INCORRECT:
TreeAssembly
├─ Tree mesh
└─ Twigs
   └─ twig_NaniteAssembly.usda  ← CRASH!
```

## Changes Made

### File: `src/growpy/cli/convert_twigs.py`

#### Removed

1. **Function**: `create_twig_nanite_assembly()` - Entire function removed
2. **Parameter**: `create_nanite_assemblies` from `process_twig_directory()`
3. **Arguments**: `--create-nanite-assembly` and `--no-nanite-assembly` CLI flags
4. **Logic**: Nanite Assembly creation loop after twig export
5. **Summary**: Nanite Assembly count in output summary

#### Simplified

- Export process now only creates regular USD files
- Command line interface streamlined
- Documentation updated to reflect single USD output per twig

## Output Changes

### Before

Each twig produced two USD files:

```
europeanbeech_var_a.usda                  # 38K - Regular USD mesh
europeanbeech_var_a_NaniteAssembly.usda   # 438B - Wrapper (UNUSED)
```

### After

Each twig produces one USD file:

```
europeanbeech_var_a.usda                  # 38K - Regular USD mesh
```

## Impact

### For Users

✅ **Simpler workflow** - One USD file per twig instead of two
✅ **No crashes** - Twigs work correctly in all tree contexts
✅ **Faster conversion** - No Nanite Assembly generation step
✅ **Clearer intent** - Twigs are obviously regular meshes

### For Unreal Import

✅ **Skeletal trees** - Work correctly with regular USD twigs
✅ **Static trees** - Nanite applied at tree level, not twig level
✅ **Nanite Assembly** - Only used for top-level tree assembly
✅ **Individual twigs** - Can be imported directly if needed

## Migration

### Existing Twig Files

**No action needed** - Both file types exist:

- Regular USD files (`.usda`) are used by tree assemblies
- Nanite Assembly files (`_NaniteAssembly.usda`) are ignored
- Old Nanite Assembly files can be safely deleted

### Regenerating Twigs

To clean up and regenerate twigs without Nanite Assembly files:

```bash
# Remove old Nanite Assembly files
find data/assets/twigs -name "*_NaniteAssembly.usda" -delete

# Regenerate twigs (will only create regular USD)
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda
```

## Technical Details

### Why One USD is Sufficient

**Regular USD meshes support all required features:**

- Static mesh geometry
- Materials with PBR textures
- UV mapping
- Normals and tangents
- Efficient instancing via PointInstancer

**Nanite optimization happens at import:**

- Unreal applies Nanite to geometry at import time
- No special USD metadata required
- Works for both static and skeletal contexts
- User can enable/disable Nanite per static mesh in Unreal

### Nanite Assembly Use Cases

**Only use Nanite Assembly USD at top level for:**

1. Complete tree assemblies (tree + twigs combined)
2. Large prop assemblies (multiple components)
3. Environment assemblies (rocks, plants, structures)

**Never use Nanite Assembly USD for:**

1. Individual component meshes (twigs, leaves, etc.)
2. Referenced geometry within other USD files
3. Instanced objects via PointInstancer
4. Skeletal mesh components

## Related Changes

This change complements the twig reference fix in `src/growpy/io/blender_export.py`:

```python
# Always skip Nanite Assembly files when selecting twig references
if "_NaniteAssembly" not in usd_file.name and usd_file.exists():
    twig_usd_map[grove_type] = usd_file
```

Together these changes ensure:

- Twigs are exported as regular USD only
- Tree assemblies reference regular USD twigs
- No Nanite Assembly nesting or conflicts

## Verification

After regenerating forest with updated code:

```bash
# Check Beech tree references
grep "references" data/output/forest/Beech/USD/Beech_var1.usda

# Should show only regular USD files:
# prepend references = @.../europeanbeech_var_a.usda@
# prepend references = @.../europeanbeech_var_b.usda@

# No "_NaniteAssembly" in output
```

## Related Documentation

- `docs/archive/TWIG_NANITE_ASSEMBLY_FIX.md` - Initial crash fix
- `docs/archive/SKELETAL_NANITE_ASSEMBLY_ISSUE.md` - Tree-level Nanite Assembly
- `docs/growpy/TWIG_CONVERSION_V2.md` - Twig conversion process
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import workflows

## Conclusion

Removing Nanite Assembly creation from twig conversion:

- ✅ Fixes Unreal Engine crashes
- ✅ Simplifies workflow and codebase
- ✅ Improves clarity of USD usage
- ✅ Maintains all required functionality

Twigs are now regular static USD meshes, as they should be. Nanite optimization is applied at the tree assembly level or during Unreal import, not at the individual twig level.
