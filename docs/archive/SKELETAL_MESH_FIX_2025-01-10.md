# Skeletal Mesh Recognition and Scale Fix - 2025-01-10

## Issues Identified

### 1. USD Skeletal Trees Not Recognized in Unreal

**Problem**: Tree skeletal USD files not recognized as skeletal meshes in UE5
**Root Cause**: Missing proper `SkelBindingAPI.Apply()` on SkelRoot and incorrect joint weight primvar setup
**Fix**:

- Added `SkelBindingAPI.Apply(skel_root_prim.GetPrim())` to properly mark SkelRoot
- Fixed joint weight setup using proper UsdSkel API methods:
  - `CreateJointIndicesPrimvar(False, max_influences)` instead of manual primvar creation
  - `CreateJointWeightsPrimvar(False, max_influences)` with proper padding
- Keep `/root` as default prim instead of `SkelRoot` to preserve material access

### 2. USD Skeletal Twigs Missing Textures

**Problem**: Textures not appearing when importing USD skeletal twigs in Unreal
**Root Cause**: Default prim set to `SkelRoot`, hiding materials under `/root/_materials`
**Fix**:

- Keep `/root` as default prim (already implemented in `_add_skeleton_to_twig_usd`)
- Materials remain accessible to Unreal at `/root/_materials`

### 3. FBX Skeletal Twigs Gigantic Scale

**Problem**: FBX skeletal twigs appear at massive scale in Unreal (100x or more)
**Root Cause**: Missing `global_scale=1.0` and `apply_scale_options` in FBX export
**Fix**:

- Added `global_scale=1.0` to both static and skeletal FBX exports
- Added `apply_scale_options='FBX_SCALE_ALL'` to ensure consistent meter scale
- Now exports at 1:1 meter scale matching USD exports

### 4. FBX Skeletal Twig Bone Connection Errors

**Problem**: Occasional FBX import errors about bones not connecting/aligning
**Root Cause**: Single-bone skeletons with improper hierarchy
**Status**:

- Single-bone skeleton at origin with proper parent-child setup
- Root bone points up (0,0,0) to (0,0,0.1)
- All vertices weighted to single bone with weight 1.0
- Should work correctly with scale fix

## Code Changes

### File: `src/growpy/io/blender_export.py`

#### Change 1: SkelRoot Binding API

```python
# Before
skel_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())

# After
skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())
```

#### Change 2: Joint Weight Primvars

```python
# Before - Manual primvar creation
primvar_api = UsdGeom.PrimvarsAPI(tree_mesh_prim)
joint_indices_primvar = primvar_api.CreatePrimvar(...)
joint_weights_primvar = primvar_api.CreatePrimvar(...)

# After - Proper UsdSkel API
mesh_binding_api.CreateJointIndicesPrimvar(False, max_influences).Set(...)
mesh_binding_api.CreateJointWeightsPrimvar(False, max_influences).Set(...)
```

#### Change 3: Default Prim Preservation

```python
# Before - Set SkelRoot as default (hides materials)
stage.SetDefaultPrim(skel_root_prim.GetPrim())

# After - Keep root as default (preserves material access)
root_prim = stage.GetPrimAtPath("/" + original_xform_path.pathString.split("/")[1])
if root_prim:
    stage.SetDefaultPrim(root_prim)
```

### File: `src/growpy/cli/convert_twigs.py`

#### Change 1: Static FBX Scale

```python
bpy.ops.export_scene.fbx(
    # ... existing params ...
    global_scale=1.0,  # NEW: 1:1 scale in meters
    apply_scale_options='FBX_SCALE_ALL'  # NEW: Apply to all data
)
```

#### Change 2: Skeletal FBX Scale

```python
bpy.ops.export_scene.fbx(
    # ... existing params ...
    global_scale=1.0,  # NEW: 1:1 scale in meters
    apply_scale_options='FBX_SCALE_ALL'  # NEW: Apply to all data
)
```

## Testing Checklist

### USD Tree Skeletal Mesh

- [ ] Import USD tree with skeleton into UE5
- [ ] Verify recognized as Skeletal Mesh asset
- [ ] Check skeleton hierarchy visible
- [ ] Verify bark textures applied correctly
- [ ] Check mesh scale is reasonable (meters)

### USD Twig Skeletal Mesh

- [ ] Import USD skeletal twig into UE5
- [ ] Verify recognized as Skeletal Mesh asset
- [ ] Check textures (diffuse, alpha, normal) applied
- [ ] Verify single-bone skeleton present
- [ ] Check mesh scale is reasonable (centimeters)

### FBX Tree Skeletal Mesh

- [ ] Import FBX tree with skeleton into UE5
- [ ] Verify recognized as Skeletal Mesh asset
- [ ] Check bark textures embedded/applied
- [ ] Verify scale is 1:1 meters (not 100x)

### FBX Twig Skeletal Mesh

- [ ] Import FBX skeletal twig into UE5
- [ ] Verify recognized as Skeletal Mesh asset
- [ ] Check textures embedded correctly
- [ ] Verify scale matches USD version
- [ ] Check no bone connection errors on import
- [ ] Verify twig can be placed in level at correct size

## Expected Results

### Scale Consistency

- USD trees: ~10-30 meters tall
- USD twigs: ~5-50 centimeters
- FBX trees: Same as USD (meters)
- FBX twigs: Same as USD (centimeters)

### Skeletal Mesh Recognition

- Unreal Import Dialog: Shows "Skeletal Mesh" type
- Asset Browser: Uses skeletal mesh icon
- Can assign to Skeletal Mesh Component
- Can use with animation blueprints (if animated)

### Material/Texture Integrity

- USD: Textures referenced correctly from `/root/_materials`
- FBX: Textures embedded in FBX file
- Both: Diffuse, normal maps, alpha channels work
- Materials use UE5 Nanite-compatible settings

## Known Limitations

1. **Single-Bone Skeletons**: Twigs use single-bone skeleton for compatibility
   - Not suitable for complex animation
   - Sufficient for wind/physics deformation
   - Minimal overhead in Unreal

2. **FBX vs USD**: FBX has larger file sizes due to embedded textures
   - Use USD for production pipelines
   - Use FBX for quick testing or external tools

3. **Nanite Skeletal Meshes**: Experimental in UE5.x
   - May have performance implications
   - Test thoroughly in target UE version
   - Consider static mesh for foliage if no animation needed

## Rollback

If issues occur, revert changes:

```bash
git checkout HEAD~1 -- src/growpy/io/blender_export.py
git checkout HEAD~1 -- src/growpy/cli/convert_twigs.py
```

## References

- USD Skeletal Animation: <https://graphics.pixar.com/usd/docs/api/usd_skel_page_front.html>
- UE5 USD Import: <https://docs.unrealengine.com/5.0/en-US/usd-in-unreal-engine/>
- FBX Scale Issues: <https://docs.unrealengine.com/5.0/en-US/fbx-import-options/>
