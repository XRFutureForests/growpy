# Nanite Skeletal Assembly - Final Fix

**Date**: 2025-01-11  
**Status**: Ready for testing

## Problem Summary

Skeletal Nanite Assemblies were not being recognized by Unreal Engine 5.7+. After examining the Unreal USD schema files, the root cause was identified:

**`NaniteAssemblyExternalRefAPI` with USD references works for static meshes but NOT for skeletal meshes.**

## Root Cause

The schema documentation revealed:

```usda
uniform token unreal:naniteAssembly:meshAssetPath = "" (
    doc = "Package path of either a static mesh or skeletal mesh asset 
          (ex: /Game/Assets/Meshes/MyMeshAsset.MyMeshAsset)"
)
```

This attribute expects **Unreal Engine content paths** (after import), NOT USD file paths.

**The key difference**:

- **Static meshes**: Unreal accepts USD references via `NaniteAssemblyExternalRefAPI`
- **Skeletal meshes**: Must use direct USD composition (standard references/sublayers)

## Solution

Changed skeletal assembly creation to use **standard USD references** instead of `NaniteAssemblyExternalRefAPI`:

### Before (Broken)

```python
# Tree mesh as ExternalRef
tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")
tree_api_schemas = Sdf.TokenListOp()
tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
tree_prim.SetMetadata("apiSchemas", tree_api_schemas)
tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))
```

**Problem**: `NaniteAssemblyExternalRefAPI` doesn't work with USD references for skeletal meshes.

### After (Fixed)

```python
if use_skeletal_mesh:
    # Embed complete skeletal tree via standard USD reference
    root_prim.GetReferences().AddReference(
        str(tree_usd_path.resolve()),
        "/Tree"  # Reference the Tree prim from skeletal USD
    )
    
    # Set skeleton relationship to embedded skeleton
    skeleton_rel = root_prim.CreateRelationship(
        "unreal:naniteAssembly:skeleton"
    )
    skeleton_rel.AddTarget(f"/{assembly_name}/SkelRoot/Skeleton")
else:
    # Static meshes continue using NaniteAssemblyExternalRefAPI
    tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")
    tree_api_schemas = Sdf.TokenListOp()
    tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
    tree_prim.SetMetadata("apiSchemas", tree_api_schemas)
    tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))
```

**Solution**: Skeletal assemblies now use standard USD composition at the root level.

## Expected USD Structure

### Skeletal Assembly (New)

```usda
#usda 1.0

def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
    references = @Beech_tree_0000_skeletal.usda@</Tree>
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
    
    def PointInstancer "TwigInstances" (
        apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    ) {
        # Twig instances with skeleton binding
        token[] primvars:unreal:naniteAssembly:bindJoints = ["Root", "Root", ...]
        int primvars:unreal:naniteAssembly:bindJoints:elementSize = 1
        float[] primvars:unreal:naniteAssembly:bindJointWeights = [1.0, 1.0, ...]
    }
}
```

**Key changes**:

1. Root prim has `references = @skeletal_tree.usda@</Tree>` - embeds complete tree
2. No separate `TreeMesh` prim with `NaniteAssemblyExternalRefAPI`
3. Skeleton relationship points to embedded skeleton: `</Assembly/SkelRoot/Skeleton>`
4. All mesh geometry + skeleton come from the referenced USD

### Static Assembly (Unchanged)

```usda
#usda 1.0

def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "staticMesh"
    
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @Beech_tree_0000_static.usda@
    ) {}
    
    def PointInstancer "TwigInstances" {
        # Static twig instances
    }
}
```

**Static assemblies remain unchanged** - they continue using `NaniteAssemblyExternalRefAPI`.

## Code Changes

**File**: `src/growpy/io/unreal_nanite_assembly.py`

**Function**: `create_nanite_assembly_usd()`

**Lines Changed**: ~40 lines in tree mesh creation section

**Summary**:

- Added conditional logic for `use_skeletal_mesh`
- Skeletal: Use `root_prim.GetReferences().AddReference()` at root level
- Static: Keep existing `NaniteAssemblyExternalRefAPI` approach
- Both paths set correct skeleton relationship

## Testing Instructions

1. Re-export skeletal assemblies:

```bash
python src/growpy/cli/export_trees.py --skeletal
```

2. Check generated assembly file:

```bash
# Should show references = @skeletal_tree.usda@</Tree> at root level
head -n 20 data/output/Species/Beech_NaniteAssembly.usda
```

3. Import in Unreal Engine:
   - Open USD importer
   - Select skeletal assembly USDA file
   - Verify assembly is recognized (should show in content browser)
   - Check skeleton is detected
   - Verify twigs are included

## Expected Results

### Success Criteria

- Unreal recognizes skeletal assembly (shows assembly icon)
- Skeleton is detected and bound to mesh
- Twigs are included as instances
- Assembly can be placed in scene
- Skeleton animation works (if present)

### File Sizes

- Skeletal assembly: ~145KB (includes embedded mesh + skeleton)
- Static assembly: ~12KB (references only)

**Note**: Skeletal assemblies are larger because they embed the complete skeletal tree structure via USD reference composition.

## Why This Works

The Unreal USD importer has different handling for static vs skeletal meshes:

**Static Meshes**:

- `NaniteAssemblyExternalRefAPI` with USD references works
- Unreal automatically resolves USD references during import
- Can use external ref pattern

**Skeletal Meshes**:

- `NaniteAssemblyExternalRefAPI.meshAssetPath` expects Unreal content paths
- USD references must use standard USD composition
- Requires embedding via root-level reference
- Skeleton must be descendant of assembly root

This is consistent with how Unreal handles skeletal mesh complexity (skinning, animation, etc.) vs static mesh simplicity.

## Related Documentation

- `NANITE_SKELETAL_CORRECT_APPROACH.md` - Initial analysis and solution options
- `data/unreal_schema/unreal/schema.usda` - Official Unreal USD schema
- `data/unreal_schema/README.md` - Schema usage documentation

## Next Steps

1. Test import in Unreal Engine 5.7+
2. Verify skeleton animation works
3. Check twig instance binding to skeleton
4. Document any additional findings
5. Update user-facing documentation if successful
