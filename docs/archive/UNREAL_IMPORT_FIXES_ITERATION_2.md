# Unreal Import Fixes - Iteration 2

## Date: January 10, 2025

## New Issues Reported After First Fix

1. **FBX Skeletal Still Crashes**: FBX skeletal mesh still hangs/crashes Unreal on import
2. **USD Skeletal Texture Too Small**: USD skeletal tree texture is now even smaller and more repetitive than before
3. **USD Skeletal Twig No Material**: Skeletal twig USD imports but texture/material not mapped
4. **Skeletal Nanite No Twigs**: Skeletal Nanite Assembly still only imports tree as static mesh, no twigs

## Root Cause Analysis - Iteration 2

### Issue 1: FBX Skeletal Crash (Persistent)

**New Discovery**: The issue is not just animation baking, but the complete skeleton-mesh binding setup.

**Problems Found**:

1. Mesh not parented to armature (only modifier-based binding)
2. Armature not set to rest position before export
3. FBX export applying mesh modifiers (breaking armature deformation)
4. Missing deform-only bone export flag

**Solution**:

- Parent mesh to armature with `obj.parent = armature_obj`
- Clear pose transforms to ensure rest position
- Disable `use_mesh_modifiers` in FBX export (preserve armature deformation)
- Enable `use_armature_deform_only` to export only deform bones
- Use minimal single-frame bake with simplification

### Issue 2: USD Skeletal Texture Too Small

**Root Cause**: Grove's `apply_uv_aspect_ratio(4.0)` modifies the Grove model, but Blender's USD exporter creates UVs from the Blender mesh, which doesn't have the scaled UVs. The aspect ratio scaling is lost during USD export.

**Evidence**:

- Line 363: `model.apply_uv_aspect_ratio(aspect_ratio)` modifies Grove model
- Line 381: UVs extracted from Grove with `model.get_uvs_flat()`
- Line 470: Blender's USD exporter (`bpy.ops.wm.usd_export`) re-exports UVs from Blender mesh
- Blender mesh UVs don't have aspect ratio applied - they're the original 1:1 UVs

**Solution**: Manually scale UV V-coordinates by aspect ratio when writing to Blender mesh, so Blender's USD exporter preserves the correct scale.

### Issue 3: USD Skeletal Twig Material Not Mapped

**Root Cause**: Material binding not properly copied from original mesh to skeletal mesh in `_add_skeleton_to_twig_usd()`.

**Problems**:

- Only checking `GetDirectBinding()`
- Not handling collection bindings or inherited material paths
- Material may exist but binding relationship not established

**Solution**: Check multiple binding types (direct, collection, purpose-specific) and properly copy all material binding relationships.

### Issue 4: Skeletal Nanite No Twigs

**Root Cause**: Even though we added FBX twig path support, the Nanite Assembly creation wasn't actually using them. Also, the tree reference needs to be FBX for skeletal mesh.

**Problems**:

1. Tree reference still using USD path (`tree_usd_path`) instead of FBX
2. Twig references defaulting to USD even when FBX available
3. No tree FBX path being passed to `create_nanite_assembly_usd()`

**Solution**:

- Pass `tree_fbx_path` parameter to Nanite Assembly creation
- Ensure FBX path is used for skeletal mesh (both tree and twigs)
- Add logging to show which reference type is used (FBX vs USD)

## Changes Applied - Iteration 2

### Fix 1: FBX Skeletal Mesh Proper Binding

**File**: `src/growpy/io/blender_export.py` line ~905

**Changed**:

```python
# Parent mesh to armature for proper FBX skeletal mesh export
# This is CRITICAL for Unreal to recognize as skeletal mesh
obj.parent = armature_obj
obj.parent_type = 'OBJECT'

# Add armature modifier for proper deformation
modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
modifier.object = armature_obj
modifier.use_vertex_groups = True
```

### Fix 2: Set Rest Pose Before FBX Export

**File**: `src/growpy/io/blender_export.py` line ~2420

**Added**:

```python
# Set armature to rest position for clean FBX export
if armature_obj and armature_obj.pose:
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.loc_clear()
    bpy.ops.pose.rot_clear()
    bpy.ops.pose.scale_clear()
    bpy.ops.object.mode_set(mode='OBJECT')
```

### Fix 3: FBX Export Settings for Skeletal Mesh

**File**: `src/growpy/io/blender_export.py` line ~2505

**Changed**:

```python
bpy.ops.export_scene.fbx(
    # ... existing params ...
    use_mesh_modifiers=False,  # Don't apply modifiers - preserve armature deformation
    use_armature_deform_only=include_skeleton,  # Export only deform bones
    bake_anim=include_skeleton,  # Bake for skeletal mesh
    bake_anim_use_all_bones=False,  # Only deform bones
    bake_anim_simplify_factor=1.0,  # Simplify to single frame
    # ... rest of params ...
)
```

### Fix 4: Scale UVs in Blender Mesh for USD Export

**File**: `src/growpy/io/blender_export.py` line ~381

**Changed**:

```python
if uvs and len(uvs) >= len(faces) * 6:
    mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    # Apply UVs with aspect ratio scaling for proper texture size
    # Grove applies UV aspect ratio to model, but Blender USD export resets it
    # So we need to manually scale UVs in Blender to preserve the ratio
    uv_scale_y = aspect_ratio if 'aspect_ratio' in locals() else 4.0
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            uv_index = loop_index * 2
            if uv_index + 1 < len(uvs):
                # Scale V coordinate by aspect ratio to match texture size
                u = uvs[uv_index]
                v = uvs[uv_index + 1] * uv_scale_y
                uv_layer[loop_index].uv = (u, v)
```

### Fix 5: Copy All Material Bindings for Skeletal Twigs

**File**: `src/growpy/cli/convert_twigs.py` line ~412

**Changed**:

```python
# Copy ALL material bindings (direct, collection, and inherited)
# This ensures textures are properly mapped in Unreal
old_mat_api = UsdShade.MaterialBindingAPI(mesh_prim)

# Try direct binding first
mat_binding = old_mat_api.GetDirectBinding()
if mat_binding and mat_binding.GetMaterial():
    new_mat_api = UsdShade.MaterialBindingAPI.Apply(new_mesh_prim)
    new_mat_api.Bind(mat_binding.GetMaterial())
else:
    # Try collection binding
    for purpose in [UsdShade.Tokens.allPurpose, UsdShade.Tokens.preview, UsdShade.Tokens.full]:
        collection_binding = old_mat_api.GetCollectionBinding(purpose)
        if collection_binding:
            new_mat_api = UsdShade.MaterialBindingAPI.Apply(new_mesh_prim)
            new_mat_api.Bind(collection_binding.GetMaterial(), purpose)
            break
```

### Fix 6: Use FBX References in Skeletal Nanite Assembly

**File**: `src/growpy/io/unreal_nanite_assembly.py` line ~108

**Changed**:

```python
# CRITICAL: For skeletal mesh, MUST use FBX reference for proper Unreal import
# USD skeletal meshes in Nanite Assembly don't properly import as skeletal
if use_skeletal_mesh and tree_fbx_path and tree_fbx_path.exists():
    tree_prim.GetReferences().AddReference(str(tree_fbx_path.resolve()))
    tree_ref_name = tree_fbx_path.name
    print(f"    Using skeletal FBX tree reference: {tree_ref_name}")
else:
    tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))
    tree_ref_name = tree_usd_path.name
```

**And for twigs** (line ~135):

```python
# For skeletal mesh, MUST use FBX if available
twig_ref_path = None
if use_skeletal_mesh and twig_fbx_paths and twig_type in twig_fbx_paths:
    twig_ref_path = twig_fbx_paths[twig_type]
    if not twig_ref_path.exists():
        print(f"    Warning: Skeletal FBX twig not found: {twig_ref_path.name}, trying USD...")
        twig_ref_path = twig_path if twig_path.exists() else None
else:
    twig_ref_path = twig_path
```

### Fix 7: Pass Tree FBX Path to Nanite Assembly

**File**: `src/growpy/io/blender_export.py` line ~3308

**Changed**:

```python
# Find skeletal FBX tree file
tree_fbx_path = output_path.parent.parent / "FBX" / f"{output_path.stem}_skeletal.fbx"

skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,  # USD fallback
    output_path=skeletal_nanite_path,
    species_name=species_name,
    tree_fbx_path=tree_fbx_path if tree_fbx_path.exists() else None,  # FBX preferred
    twig_usd_paths=skeletal_twig_paths,  # USD fallback
    twig_fbx_paths=skeletal_twig_fbx_paths,  # FBX preferred
    use_skeletal_mesh=True,
)
```

## Expected Behavior After Iteration 2

### FBX Skeletal Mesh

- ✓ Should import without crashing (mesh properly parented to armature)
- ✓ Unreal recognizes as skeletal mesh (proper binding and rest pose)
- ✓ Smooth shading preserved (from iteration 1)
- ✓ Texture scale 4.0 (from iteration 1)

### USD Skeletal Tree

- ✓ Texture scale now matches non-skeletal USD (4.0 aspect ratio preserved)
- ✓ Less repetitive bark texture
- ✓ Imports as skeletal mesh (SkelAnimation from iteration 1)

### USD Skeletal Twigs

- ✓ Material and texture properly mapped in Unreal
- ✓ All binding types checked (direct, collection, purpose-specific)

### Skeletal Nanite Assembly

- ✓ Tree imports as skeletal mesh (using FBX reference)
- ✓ Twigs import as skeletal meshes (using FBX references)
- ✓ Both tree and twig geometry visible
- ✓ Proper skeletal mesh structure throughout

## Testing Checklist - Iteration 2

Run new export:

```bash
/Users/maximiliansperlich/miniforge3/envs/the-grove/bin/python ./src/growpy/cli/generate_forest.py ./data/input/test.csv --output-dir ./data/output/import_test_v2 --quality high --formats fbx usda
```

### Test in Unreal Engine

1. **FBX Skeletal** (`Beech_tree_0000_skeletal.fbx`):
   - [ ] Imports without crash/hang
   - [ ] Recognized as skeletal mesh
   - [ ] Smooth appearance (not faceted)
   - [ ] Texture scale appropriate (not too small/repetitive)

2. **USD Skeletal Tree** (`Beech_tree_0000_tree_only_skeletal.usda`):
   - [ ] Texture size matches non-skeletal version
   - [ ] Not smaller or more repetitive than before
   - [ ] Imports as skeletal mesh

3. **USD Skeletal Twig** (e.g., `europeanbeech_var_a_skeletal.usda`):
   - [ ] Material applied correctly
   - [ ] Texture visible (not missing)
   - [ ] Imports as skeletal mesh

4. **Skeletal Nanite Assembly** (`Beech_tree_0000_NaniteAssembly_skeletal.usda`):
   - [ ] Tree imports as skeletal mesh (not static)
   - [ ] Twigs visible in viewport
   - [ ] Twigs import as skeletal meshes
   - [ ] All materials/textures applied

## Files Modified - Iteration 2

1. **src/growpy/io/blender_export.py**
   - Line ~381: Scale UVs in Blender mesh for USD export
   - Line ~905: Parent mesh to armature
   - Line ~2420: Set armature rest pose before export
   - Line ~2505: Updated FBX export settings (use_mesh_modifiers=False, use_armature_deform_only, simplified bake)
   - Line ~3308: Pass tree FBX path to Nanite Assembly

2. **src/growpy/cli/convert_twigs.py**
   - Line ~412: Copy all material binding types (direct, collection, purpose-specific)

3. **src/growpy/io/unreal_nanite_assembly.py**
   - Line ~108: Use FBX tree reference for skeletal mesh
   - Line ~135: Use FBX twig references for skeletal mesh with fallback logic

## Technical Notes

### UV Scaling in Blender

The key insight is that Grove's `apply_uv_aspect_ratio()` only modifies the Grove model's internal UV data. When Blender's USD exporter runs, it re-exports UVs from the Blender mesh object, which has the original 1:1 UVs. Solution: Scale the V-coordinate when writing UVs to Blender mesh.

### FBX Skeletal Mesh Requirements

Unreal's FBX importer needs:

1. Mesh parented to armature (not just modifier)
2. Armature in rest position (no pose transforms)
3. Modifiers NOT applied (preserve armature deformation)
4. Only deform bones exported (no helper/control bones)

### Nanite Assembly FBX References

USD files can reference FBX files, but Unreal needs the references to be absolute or relative paths that resolve correctly. The FBX files must exist alongside the USD Nanite Assembly file for Unreal to load them during import.
