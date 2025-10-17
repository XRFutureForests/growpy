# Skeletal Twig Deprecation

**Date:** 2025-01-09  
**Status:** Completed

## Summary

Skeletal twig variants have been deprecated and removed from the twig conversion pipeline. Twigs are now exported as static meshes only in both FBX and USD formats.

## Background

Previously, `convert_twigs.py` created both static and skeletal variants of each twig:

- `standard_name.fbx` - Static mesh
- `standard_name_skeletal.fbx` - Single-bone skeletal mesh
- `standard_name.usda` - Static mesh
- `standard_name_skeletal.usda` - Single-bone skeletal mesh

The skeletal variants included a single bone at the origin with all vertices bound to it. This was intended for Nanite Assembly compatibility in Unreal Engine, but testing showed that skeletal twigs are not necessary for static foliage placement.

## Changes Made

### Code Changes

1. **blender_twig_processor.py**
   - Removed `_add_skeleton_to_twig_fbx()` function (~65 lines)
   - Removed `_add_skeleton_to_twig_usd()` function (~140 lines)
   - Twigs now export as static meshes only

2. **convert_twigs.py**
   - Updated docstring to remove references to skeletal variants
   - Added note clarifying tree skeletons remain supported
   - Removed skeletal output documentation

### What Remains Supported

**Tree Skeletons:** Full multi-bone skeletons for main trees are still supported and required for:

- Animation and wind effects
- Skeletal mesh features in Unreal Engine
- Dynamic tree movement

Tree skeletons are exported via `generate_forest.py` with proper bone hierarchies representing the tree structure.

### What Was Removed

**Twig Skeletons:** Single-bone skeletal variants for twig assets, which were:

- Not necessary for static foliage placement
- Added complexity without functional benefit
- Redundant for Nanite mesh workflows

## Impact

### User-Facing Changes

- Running `convert_twigs.py` now only produces static mesh outputs
- Existing skeletal twig files (if any) will not be updated or removed
- No impact on tree skeleton export functionality

### Migration Guide

If you have existing skeletal twig files, they can be safely deleted:

```powershell
# Remove old skeletal twig files (if desired)
Remove-Item data/assets/twigs/*_skeletal.fbx
Remove-Item data/assets/twigs/*_skeletal.usda
```

Re-run twig conversion to generate only static meshes:

```powershell
python src/growpy/cli/convert_twigs.py data/assets/twigs
```

## Technical Details

### Why Single-Bone Skeletons Were Not Needed

1. **Static Placement:** Twigs in foliage systems are typically placed statically using PCG or similar tools
2. **No Animation Required:** Individual twig meshes don't need skeletal animation
3. **Nanite Compatibility:** Static meshes work with Nanite without skeletal mesh complexity
4. **Performance:** Static meshes have lower overhead than skeletal meshes

### Tree Skeletons vs Twig Skeletons

| Feature | Tree Skeletons | Twig Skeletons |
|---------|----------------|----------------|
| **Purpose** | Animation, wind effects | ~~Nanite compatibility~~ (unnecessary) |
| **Bone Structure** | Multi-bone hierarchy | ~~Single bone at origin~~ |
| **Status** | **Supported** | **Deprecated** |
| **Export Script** | `generate_forest.py` | ~~`convert_twigs.py`~~ (removed) |

## Related Documentation

- `SKELETON_BONE_POSITIONING_FIX.md` - Tree skeleton bone positioning fix (still relevant)
- `USD_SKELETON_EXPORT_SUMMARY.md` - Tree skeleton export details (still relevant)
- `convert_twigs.py` - Updated twig conversion script documentation

## Testing

After removing skeletal twig functionality:

- ✅ Twig conversion produces only static meshes
- ✅ Tree skeleton export remains functional
- ✅ No references to skeletal twigs in active code

## Conclusion

This change simplifies the twig conversion pipeline by removing unnecessary skeletal variants. Tree skeletons remain fully supported for their intended purpose of animation and dynamic movement.
