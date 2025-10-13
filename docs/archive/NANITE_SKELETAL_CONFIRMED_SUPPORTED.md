# Skeletal Nanite Assemblies - Confirmed Supported by Schema

**Date**: 2025-01-11  
**Status**: Schema analysis confirms skeletal assemblies are fully supported

## Schema Evidence

The Unreal USD schema (`data/unreal_schema/unreal/schema.usda`) provides clear evidence that **skeletal mesh Nanite Assemblies are fully supported and intentional**:

### NaniteAssemblyRootAPI Schema

```usda
class "NaniteAssemblyRootAPI" (
    inherits = </APISchemaBase>
    customData = {
        token apiSchemaType = "singleApply"
        token[] apiSchemaCanOnlyApplyTo = ["Xform"]
    }
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh" (
        customData = {
            string apiName = "meshType"
        }
        allowedTokens = [ "staticMesh", "skeletalMesh" ]  # ← EXPLICIT SUPPORT
        doc = """Specifies the type of Nanite Assembly this prim represents. Valid values are:
        * "staticMesh" - This is the root of a static mesh Nanite assembly.
        * "skeletalMesh" - This is the root of a skeletal mesh Nanite assembly.
        """
    )

    rel unreal:naniteAssembly:skeleton (
        customData = {
            string apiName = "skeleton"
        }
        doc = """The skeleton to consider as the base of this Nanite assembly root 
        (Valid for meshType=skeletalMesh only, and must be a descendant prim)."""
    )
}
```

## Key Schema Requirements

### 1. Skeletal Mesh Type is Explicitly Allowed

```usda
allowedTokens = [ "staticMesh", "skeletalMesh" ]
```

This is not a workaround - `"skeletalMesh"` is a **first-class supported value**.

### 2. Dedicated Skeleton Relationship

```usda
rel unreal:naniteAssembly:skeleton
```

The schema includes a **dedicated relationship** for skeletal assemblies. This wouldn't exist if skeletal assemblies weren't fully supported.

### 3. Clear Requirements

The documentation states the skeleton:

- Is **valid for `meshType=skeletalMesh` only**
- **Must be a descendant prim** of the assembly root

This tells us exactly how to structure skeletal assemblies:

```
Xform "Tree_NaniteAssembly" (apiSchemas = ["NaniteAssemblyRootAPI"])
    ├── meshType = "skeletalMesh"
    ├── skeleton → points to descendant skeleton
    │
    └── SkelRoot (descendant)
        └── Skeleton (this is what skeleton relationship targets)
```

## Why Our Previous Approaches Failed

### Attempt 1: Separate Skeleton + Static Mesh Reference

**Problem**: Embedded mesh geometry in skeleton file  
**Status**: Fixed by skipping Mesh prims during copy

### Attempt 2: Skeleton-Only Assembly with External Mesh

**Problem**: Used `NaniteAssemblyExternalRefAPI` with USD file reference  
**Status**: Doesn't work - `meshAssetPath` expects Unreal content paths

### Attempt 3: Embedded Skeletal Tree (Current)

**Solution**: Use standard USD reference at root to embed complete skeletal structure  
**Status**: Matches schema requirements - skeleton is descendant prim

## Correct Implementation Pattern

Based on schema requirements:

```python
# Create assembly root with NaniteAssemblyRootAPI
root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# Set mesh type to skeletal
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType", 
    Sdf.ValueTypeNames.Token
).Set("skeletalMesh")

# Embed skeletal tree using standard USD reference
# This makes the skeleton a DESCENDANT of the assembly root
root_prim.GetReferences().AddReference(
    str(skeletal_tree_usd_path.resolve()),
    "/Tree"
)

# Set skeleton relationship to descendant skeleton
skeleton_rel = root_prim.CreateRelationship("unreal:naniteAssembly:skeleton")
skeleton_rel.AddTarget(f"/{assembly_name}/SkelRoot/Skeleton")
```

## Expected USD Structure

```usda
#usda 1.0

def Xform "Beech_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
    references = @Beech_tree_0000_skeletal.usda@</Tree>  # ← Embeds complete tree
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
    
    # The referenced skeletal USD contains:
    # - def SkelRoot "SkelRoot"
    #   - def Skeleton "Skeleton"
    #   - def Mesh "BranchMesh" (skinned to skeleton)
    
    # Additional assembly content:
    def PointInstancer "TwigInstances" (
        apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    ) {
        # Twig instances bound to skeleton joints
    }
}
```

## Why This Works

1. **Schema Compliance**:
   - `meshType = "skeletalMesh"` ✓
   - Skeleton is descendant prim ✓
   - Skeleton relationship points to descendant ✓

2. **USD Composition**:
   - Root-level reference embeds the complete skeletal tree
   - All descendant prims (SkelRoot, Skeleton, Mesh) become part of assembly
   - Skeleton relationship can target these descendants

3. **Unreal Import**:
   - Recognizes `NaniteAssemblyRootAPI` with `meshType="skeletalMesh"`
   - Follows skeleton relationship to find embedded skeleton
   - Imports as skeletal Nanite Assembly with animation support

## Comparison: Static vs Skeletal Assemblies

### Static Assembly (Working)

```usda
def Xform "Tree_NaniteAssembly" (apiSchemas = ["NaniteAssemblyRootAPI"])
{
    token unreal:naniteAssembly:meshType = "staticMesh"
    
    # External mesh using ExternalRefAPI
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @tree_static.usda@
    ) {}
}
```

### Skeletal Assembly (New Approach)

```usda
def Xform "Tree_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
    references = @tree_skeletal.usda@</Tree>  # ← Different: root-level reference
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Tree_NaniteAssembly/SkelRoot/Skeleton>
    
    # No separate TreeMesh prim - embedded via root reference
}
```

**Key Difference**:

- Static: Uses child prim with `NaniteAssemblyExternalRefAPI`
- Skeletal: Uses root-level USD reference to embed complete tree as descendant

## Conclusion

The schema proves that **skeletal mesh Nanite Assemblies are fully supported**. Our implementation now correctly follows the schema requirements:

1. ✓ Assembly root is Xform with `NaniteAssemblyRootAPI`
2. ✓ `meshType` is set to `"skeletalMesh"` (explicitly allowed token)
3. ✓ Skeleton is embedded as descendant prim (via USD reference)
4. ✓ Skeleton relationship points to descendant skeleton
5. ✓ Twigs use `NaniteAssemblySkelBindingAPI` for joint binding

This is not a workaround - **it's the intended design pattern for skeletal Nanite Assemblies**.

## Next Test

Re-export with the corrected implementation and verify Unreal recognizes the skeletal assembly:

```bash
python src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/skeletal_assembly_test \
    --quality high \
    --formats usda \
    --skeletal
```

Expected result: Unreal USD importer recognizes the skeletal Nanite Assembly and creates proper skeletal mesh asset with animation support.
