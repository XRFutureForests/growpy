# Nanite Skeletal Assembly - Correct Approach

**Date**: 2025-01-11  
**Issue**: All skeletal Nanite Assembly approaches have failed - no assembly created in Unreal

## Root Cause Analysis

After reviewing the Unreal USD schema files, the issue is clear:

### `NaniteAssemblyExternalRefAPI` is NOT for USD file references

The schema documentation states:

```usda
uniform token unreal:naniteAssembly:meshAssetPath = "" (
    doc = "Package path of either a static mesh or skeletal mesh asset 
          to be embedded as a part of the Nanite assembly 
          (ex: /Game/Assets/Meshes/MyMeshAsset.MyMeshAsset)"
)
```

**Key insight**: `meshAssetPath` expects a **Unreal Engine content path** like `/Game/Assets/MyMesh.MyMesh`, NOT a USD file path!

This means:

- **Static mesh assemblies**: Work with USD references because Unreal handles them specially
- **Skeletal mesh assemblies**: MUST use embedded geometry OR Unreal asset paths

## The Problem with Our Current Approach

We're doing:

```usda
def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
    
    # PROBLEM: Embedded skeleton but external mesh reference
    def SkelRoot "SkelRoot" {
        def Skeleton "Skeleton" { ... }
        def SkelAnimation "Animation" { ... }
    }
    
    # This doesn't work for skeletal meshes!
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @tree.usda@  # ❌ USD file reference not supported for skeletal
    )
}
```

## Three Possible Solutions

### Option 1: Embed Everything (Simplest)

Don't use `NaniteAssemblyExternalRefAPI` at all. Directly embed the skeletal mesh using standard USD composition:

```usda
def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
    references = @Beech_tree_skeletal.usda@</Tree>  # Direct USD sublayer
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
    
    # Everything else (twigs, etc.) as PointInstancer
    def PointInstancer "TwigInstances" (
        apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    ) {
        # Twig instances bound to skeleton joints
    }
}
```

**Pros**:

- Single file contains everything
- No chicken-and-egg problem with asset paths
- Standard USD composition

**Cons**:

- Larger file size
- Can't reuse the skeletal mesh across multiple assemblies easily

### Option 2: Two-Step Import Workflow

1. Import the skeletal tree USD to create Unreal skeletal mesh asset
2. Create assembly that references the Unreal asset:

```usda
def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/TreeMesh/SkelRoot/Skeleton>
    
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    ) {
        uniform token unreal:naniteAssembly:meshAssetPath = "/Game/Trees/Beech_SkeletalMesh.Beech_SkeletalMesh"
    }
}
```

**Pros**:

- Reusable skeletal mesh assets
- Smaller assembly files

**Cons**:

- Requires knowing Unreal asset path beforehand
- Two-step import process
- More complex workflow

### Option 3: Payload/Reference Pattern

Use USD payload to defer loading:

```usda
def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
    payload = @Beech_tree_skeletal.usda@</Tree>
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
}
```

**Pros**:

- Deferred loading for performance
- Clean separation

**Cons**:

- Similar to Option 1 but with USD payload overhead

## Recommended Solution: Option 1 (Embed with References)

**Rationale**:

- Simplest to implement
- No workflow changes required
- Works with existing USD files
- Single file for complete tree + twigs + skeleton

## Implementation Plan

Modify `create_nanite_assembly_usd()`:

1. **Remove `NaniteAssemblyExternalRefAPI` for skeletal assemblies**
2. **Use direct USD reference to embed skeletal tree**
3. **Keep skeleton relationship pointing to embedded skeleton**
4. **Keep twig PointInstancer with skeletal binding**

### Code Changes

```python
def create_nanite_assembly_usd(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    use_skeletal_mesh: bool = False,
    ...
):
    if use_skeletal_mesh:
        # For skeletal: embed the tree mesh directly via reference
        # NO NaniteAssemblyExternalRefAPI - just standard USD composition
        
        # Add the skeletal tree as a sublayer/reference at root level
        root_prim.GetReferences().AddReference(
            str(tree_usd_path.resolve()), 
            "/Tree"  # Reference the Tree prim from skeletal USD
        )
        
        # Skeleton relationship already points to embedded skeleton
        skeleton_rel = root_prim.CreateRelationship("unreal:naniteAssembly:skeleton")
        skeleton_rel.AddTarget(f"/{assembly_name}/SkelRoot/Skeleton")
        
    else:
        # For static: use external ref API (existing code)
        tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")
        tree_api_schemas = Sdf.TokenListOp()
        tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
        tree_prim.SetMetadata("apiSchemas", tree_api_schemas)
        tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))
```

## Key Differences from Current Code

| Current (Broken) | Correct (Working) |
|-----------------|-------------------|
| Embed skeleton structure only | Embed complete skeletal tree |
| Use `NaniteAssemblyExternalRefAPI` with USD reference | Use direct USD reference/sublayer |
| Separate skeleton from mesh | Keep skeletal USD structure intact |

## Expected Result

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
    }
}
```

**All mesh geometry + skeleton comes from the referenced USD file.**  
The assembly just adds:

- Nanite Assembly API schema
- Skeleton relationship
- Twig instances with binding

This follows the same pattern as static assemblies but uses direct USD composition instead of the External Ref API.
