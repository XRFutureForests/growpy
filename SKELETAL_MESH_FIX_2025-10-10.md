# Skeletal Mesh Recognition Fix - October 10, 2025

## Problem Summary

Multiple issues preventing skeletal mesh recognition in Unreal Engine:

1. **FBX trees** not recognized as skeletal meshes
2. **USD tree_only_skeletal** files not recognized as skeletal meshes  
3. **USD skeletal twigs** missing textures in Unreal
4. **FBX skeletal twigs** failing with "bones could not be connected" error

## Root Causes

### 1. FBX Trees - Missing Animation Data

- **Issue**: `bake_anim=False` in FBX exporter
- **Impact**: Unreal requires animation data to recognize skeletal meshes, even for static bind poses
- **Fix**: Set `bake_anim=True` with single frame bind pose parameters

### 2. USD Trees - Missing SkelAnimation Prim

- **Issue**: Blender's USD exporter with `export_animation=False` doesn't create SkelAnimation prim
- **Impact**: Unreal requires SkelAnimation prim for skeletal mesh detection
- **Fix**: Set `export_animation=True` for skeletal meshes to trigger SkelAnimation creation

### 3. USD Skeletal Twigs - Texture Path Issues  

- **Issue**: Materials already properly configured with relative paths and /root default prim
- **Status**: No fix needed - existing code already handles this correctly

### 4. FBX Skeletal Twigs - Bone Connection Errors

- **Issue 1**: Fixed bone length (0.1m) sometimes too short/long for twig mesh
- **Issue 2**: `bake_anim=False` same as trees
- **Fix 1**: Calculate bone length dynamically from mesh bounds (50% of max extent, 0.05m-0.5m range)
- **Fix 2**: Enable `bake_anim=True` with full parameters

## Changes Made

### File: `src/growpy/io/blender_export.py`

#### Change 1: Enable FBX Animation Baking for Trees (Line ~2500)

```python
# OLD:
bake_anim=False,

# NEW:
bake_anim=True,
bake_anim_use_all_bones=True,
bake_anim_use_nla_strips=False,
bake_anim_step=1.0,
bake_anim_simplify_factor=0.0,
```

**Rationale**: Unreal Engine requires animation data in FBX files to recognize skeletal meshes. Even for static bind poses, the bake_anim flag must be True with proper parameters to include deformation data.

#### Change 2: Enable USD Animation Export for Trees (Line ~460)

```python
# OLD:
"export_animation": False,

# NEW:
"export_animation": (include_skeleton and not export_skeleton_separately),
```

**Rationale**: Blender's USD exporter only creates SkelAnimation prim when export_animation=True. Unreal requires this prim to recognize skeletal meshes.

#### Change 3: Fix Import Error in Vertex Weights (Line ~611)

```python
# REMOVED:
# from growpy.utils.dependencies import gc
```

**Rationale**: Module-level gc import already exists, reimporting causes ModuleNotFoundError in certain contexts.

### File: `src/growpy/cli/convert_twigs.py`

#### Change 1: Dynamic Bone Length Calculation (Line ~285)

```python
# OLD:
bone.tail = (0, 0, 0.1)  # 10cm up

# NEW:
mesh_bounds = [obj.dimensions[i] for i in range(3)]
max_extent = max(mesh_bounds)
bone_length = max(0.05, min(0.5, max_extent * 0.5))
bone.tail = (0, 0, bone_length)  # Proportional to mesh size
```

**Rationale**: Fixed bone length causes connection errors when mesh size varies. Dynamic sizing (50% of max mesh extent, clamped 5-50cm) ensures bone is proportional to twig geometry.

#### Change 2: Enable FBX Animation Baking for Twigs (Line ~570)

```python
# OLD:
bake_anim=False,

# NEW:
bake_anim=True,
bake_anim_use_all_bones=True,
bake_anim_use_nla_strips=False,
bake_anim_step=1.0,
bake_anim_simplify_factor=0.0,
```

**Rationale**: Same as trees - Unreal requires animation data for skeletal mesh detection.

#### Change 3: Add SkelAnimation to USD Twigs (Line ~355)

```python
# NEW CODE BLOCK:
# CRITICAL: Create SkelAnimation for bind pose (required for Unreal skeletal mesh recognition)
anim_path = skel_root_path.AppendChild("Animation")
anim_prim = UsdSkel.Animation.Define(stage, anim_path)

anim_prim.CreateJointsAttr(joints)
anim_prim.CreateTranslationsAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)]))
anim_prim.CreateRotationsAttr(Vt.QuatfArray([Gf.Quatf(1, 0, 0, 0)]))
anim_prim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)]))

skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())
skel_root_binding_api.CreateAnimationSourceRel().SetTargets([anim_path])
```

**Rationale**: USD skeletal twigs need SkelAnimation prim just like trees for Unreal recognition.

## Technical Details

### Unreal Skeletal Mesh Requirements

Both FBX and USD skeletal meshes require animation data structures even for static bind poses:

**FBX Requirements:**

- Armature with bones
- Vertex groups with weights
- **Animation data** (`bake_anim=True`) - CRITICAL
- Proper bone hierarchy and transformations

**USD Requirements:**

- UsdSkel.Root (SkelRoot prim)
- UsdSkel.Skeleton with joints hierarchy  
- UsdSkel.BindingAPI on mesh
- **UsdSkel.Animation prim** with bind pose - CRITICAL
- Joint influences (indices + weights) as primvars

### Why Animation Data is Required

Unreal Engine's importer distinguishes skeletal meshes from static meshes by:

1. **FBX**: Presence of baked animation curves (even single frame)
2. **USD**: Presence of SkelAnimation prim (even with identity transforms)

Without these, Unreal treats meshes as static even if they have skeletons/bones.

### Bone Connection Errors (FBX Twigs)

The "bones could not be connected or aligned" error occurs when:

- Bone dimensions are invalid (too short or degenerate)
- Vertex groups don't match bone names
- Bone hierarchy is malformed

**Solution**: Calculate bone length proportional to mesh size ensures valid bone geometry for all twig sizes.

## Testing Checklist

- [x] FBX trees import as skeletal mesh in Unreal
- [x] USD tree_only_skeletal files import as skeletal mesh in Unreal
- [x] USD skeletal twigs show textures in Unreal
- [x] FBX skeletal twigs import without bone connection errors
- [ ] Re-run full forest export test
- [ ] Verify Nanite compatibility maintained
- [ ] Verify skeletal animation works (if animated in future)

## Known Working Commits

- **Commit 4cea271**: Original working skeletal mesh export (Blender USD)
- **This Fix**: Extends working approach to FBX and adds SkelAnimation requirement

## Related Documentation

- `UNREAL_SCHEMA_REFERENCE.md`: UsdSkel schema requirements
- `COORDINATE_SYSTEM_UPDATE.md`: Coordinate transformations
- `SKELETON_WEIGHTS_IMPLEMENTATION.md`: Vertex weight calculation
- `SKELETAL_MESH_FIX_CRITICAL.md`: Previous skeletal mesh fixes

## Notes

- All fixes maintain backwards compatibility with static mesh exports
- No changes to mesh geometry, UVs, or materials
- Coordinate system handling unchanged
- Twig texture paths already use relative references with /root default prim
- SkelAnimation uses identity transforms (bind pose) - no actual animation data
