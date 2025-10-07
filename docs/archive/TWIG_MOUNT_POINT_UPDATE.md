# Twig Mount Point Implementation

**Date**: October 2, 2025  
**Update**: Added mount point/pivot at origin for Unreal Engine PCG integration

## Overview

All converted twigs now include a mount point (empty object) at the world origin (0,0,0) that defines where the twig connects to the tree mesh. This is essential for proper PCG (Procedural Content Generation) placement in Unreal Engine.

## Technical Implementation

### Mount Point Creation

Each twig now exports with the following hierarchy:

```
<twig_name>_mount (Empty at 0,0,0) - ROOT
  └─ <twig_mesh> (Parented to mount point)
```

**Example**:

```
europeanbeech_var_a_mount (Empty)
  └─ BeechTwigA (Mesh)
```

### Blender Processing

The converter adds these steps during export:

1. **Create Empty Object**: `bpy.data.objects.new(f"{standardized_name}_mount", None)`
2. **Position at Origin**: `mount_point.location = (0, 0, 0)`
3. **Set Display Type**: Small sphere (0.01 units) for visibility
4. **Parent Mesh**: `obj.parent = mount_point` - establishes hierarchy
5. **Export Both**: FBX export includes both mount point and mesh

### FBX Export Configuration

Updated export settings:

```python
bpy.ops.export_scene.fbx(
    object_types={'MESH', 'EMPTY'},  # Now includes EMPTY for mount point
    use_selection=True,               # Exports selected hierarchy
    # ... other settings unchanged
)
```

## Unreal Engine Integration

### PCG Usage

The mount point enables accurate twig placement in Unreal's PCG system:

1. **Pivot-Based Placement**: PCG can use the mount point as the attachment transform
2. **Rotation Reference**: Mount point defines the base orientation
3. **Consistent Origin**: All twigs share the same reference point (0,0,0)
4. **Hierarchical Transform**: Parent-child relationship maintains proper offset

### Example PCG Workflow

```cpp
// Pseudo-code for Unreal PCG
FTransform TreeAttachmentPoint = GetTwigPlacementTransform();
FTransform TwigMountPoint = TwigAsset->GetRootTransform(); // Gets mount point at origin

// Compose transforms
FTransform FinalTransform = TwigMountPoint * TreeAttachmentPoint;
SpawnTwigInstance(TwigAsset, FinalTransform);
```

### Nanite Compatibility

Mount points are compatible with Unreal's Nanite virtualized geometry:

- Empty objects don't add geometry overhead
- Hierarchy preserved in FBX import
- Transform data maintained for instancing

## File Structure Changes

### Before Mount Point Update

```
europeanbeech_var_a.fbx
  └─ BeechTwigA (Mesh at arbitrary position)
```

### After Mount Point Update

```
europeanbeech_var_a.fbx
  ├─ europeanbeech_var_a_mount (Empty at 0,0,0)
  └─ BeechTwigA (Mesh parented to mount)
```

## Verification

### File Size Check

Textures remain properly embedded (no size change from mount point addition):

```powershell
Get-ChildItem "data/assets/twigs/EuropeanBeechTwig/*.fbx" | 
    Select-Object Name, @{Name='Size(MB)';Expression={[math]::Round($_.Length/1MB,2)}}
```

**Expected Output**:

- Mount point adds negligible file size (< 1KB)
- Textures still embedded (~8-13 MB per twig)
- Total file size: **8.7-8.8 MB** (same as before)

### Visual Verification in Unreal

Import an FBX twig into Unreal and check:

1. **Root Node**: Should be named `<twig>_mount`
2. **Position**: Mount point at (0, 0, 0)
3. **Hierarchy**: Mesh is child of mount point
4. **Pivot**: When rotating in viewport, rotation happens around origin

### Blender Verification

Open an FBX in Blender to inspect:

```python
import bpy
# After importing FBX
for obj in bpy.context.scene.objects:
    if obj.type == 'EMPTY':
        print(f"Mount point: {obj.name} at {obj.location}")
    elif obj.parent and obj.parent.type == 'EMPTY':
        print(f"Mesh: {obj.name} parented to {obj.parent.name}")
```

## Conversion Command

To re-convert all twigs with mount points:

```powershell
# Single species
python src/growpy/cli/convert_twigs.py data/assets/twigs/EuropeanBeechTwig --formats fbx

# All species
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats fbx
```

## Migration Notes

### Re-export Required

Existing twigs without mount points need to be re-converted:

- Previous exports (before Oct 2, 2025) lack mount points
- Re-run conversion on all twig directories
- Verify mount point creation in log output: "Created mount point at origin"

### Backward Compatibility

If using twigs without mount points:

- Unreal will import mesh only (no hierarchy)
- PCG placement will use mesh pivot (may be off-center)
- **Recommendation**: Re-convert all twigs for consistency

## Benefits

1. **Precise Placement**: Mount point ensures twigs attach at exact origin
2. **Consistent Reference**: All twigs share the same attachment convention
3. **PCG Integration**: Direct compatibility with Unreal's point-based spawning
4. **Transform Clarity**: Clear parent-child relationship in scene hierarchy
5. **Artist-Friendly**: Mount point visible in 3D viewport for alignment verification

## Next Steps

1. ✅ Mount point implementation complete
2. ⏭️ Re-convert all 163 twigs with mount points
3. ⏭️ Update forest generation to use mount-point-based twigs
4. ⏭️ Test PCG placement in Unreal with new hierarchy
5. ⏭️ Document PCG blueprint setup for twig instancing

## Related Documentation

- `docs/TWIG_CONVERSION_VERIFICATION.md` - Texture embedding verification
- `docs/growpy/TWIG_CONVERSION_V2.md` - Enhanced converter features
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Unreal Engine import workflow
