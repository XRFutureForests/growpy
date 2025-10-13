# Nanite Assembly Twig Reference Issue - Root Cause Analysis

**Date:** 2025-01-10  
**Status:** CRITICAL ISSUE IDENTIFIED  
**Issue:** Skeletal twigs not loading in Nanite Assembly

## Problem Statement

Skeletal Nanite Assemblies are not displaying twig meshes in Unreal Engine, even though:

- Twig placement data is correctly extracted
- PointInstancer with skeleton binding is created
- Twig prototypes are defined with references

## Root Cause

**We're using USD references instead of Unreal's `NaniteAssemblyExternalRefAPI` attribute!**

### Current Implementation (INCORRECT)

```python
# Apply ExternalRefAPI but don't use its attributes
proto_api_schemas = Sdf.TokenListOp()
proto_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
proto_prim.SetMetadata("apiSchemas", proto_api_schemas)

# Using USD reference (not recognized by Unreal)
proto_prim.GetReferences().AddReference(str(twig_ref_path.resolve()))
```

Generated USD:

```usda
def Xform "twigdead" (
    prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    instanceable = true
    prepend references = @/path/to/europeanbeech_var_b_skeletal.usda@
)
{
    token visibility = "invisible"
}
```

**Problem:** Unreal Engine **ignores** USD references for Nanite Assemblies!

### Correct Implementation (from Unreal Schema)

From `data/unreal_schema/unreal/schema.usda`:

```usda
class "NaniteAssemblyExternalRefAPI" {
    uniform token unreal:naniteAssembly:meshAssetPath = "" (
        doc = "Package path of either a static mesh or skeletal mesh asset 
        to be embedded as a part of the Nanite assembly 
        (ex: /Game/Assets/Meshes/MyMeshAsset.MyMeshAsset)"
    )
}
```

**Solution:** Use `meshAssetPath` attribute with Unreal package path!

## Two Possible Approaches

### Approach 1: Use Relative USD References (Simple, May Work)

Try using relative paths in USD references:

```python
# Reference with relative path
proto_prim.GetReferences().AddReference(f"./{twig_ref_path.name}")
```

**Pros:**

- Minimal code changes
- USD workflow-compatible
- May work if Unreal auto-imports USD references

**Cons:**

- Not documented in Unreal schema
- Uncertain if Unreal recognizes USD references in assemblies
- May still fail

### Approach 2: Use meshAssetPath Attribute (Correct, But Complex)

Follow Unreal schema and use `meshAssetPath`:

```python
# Apply ExternalRefAPI
proto_api_schemas = Sdf.TokenListOp()
proto_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
proto_prim.SetMetadata("apiSchemas", proto_api_schemas)

# Set meshAssetPath attribute (Unreal package path)
# This path is used AFTER twigs are imported into Unreal
proto_prim.CreateAttribute(
    "unreal:naniteAssembly:meshAssetPath",
    Sdf.ValueTypeNames.Token,
    variability=Sdf.VariabilityUniform
).Set(f"/Game/Trees/{species_name}/Twigs/{twig_type}")
```

**Pros:**

- Follows Unreal's official schema
- Documented behavior
- Guaranteed to work

**Cons:**

- Requires pre-importing twigs into Unreal
- Two-step workflow: import twigs → create assembly
- Package paths must match actual Unreal asset paths

## Additional Issue: Skeletal vs Static Twigs

### Current Twig Structure

**Static Twig USD** (`europeanbeech_var_a.usda`):

```usda
def Mesh "BeechTwigA" {
    # Simple mesh geometry
    # No skeleton
}
```

**Skeletal Twig USD** (`europeanbeech_var_a_skeletal.usda`):

```usda
def SkelRoot "SkelRoot" {
    def Skeleton "Skeleton" {
        uniform token[] joints = ["Root"]
        uniform matrix4d[] bindTransforms = [...]
    }
    def Mesh "BeechTwigA" (
        prepend apiSchemas = ["SkelBindingAPI"]
    ) {
        int[] primvars:skel:jointIndices = [0, 0, ...] 
        float[] primvars:skel:jointWeights = [1, 1, ...]
        rel skel:skeleton = </root/.../Skeleton>
    }
}
```

### Problem with Skeletal Twigs

**Skeletal twigs have their own skeleton** (single root joint). But for Nanite Assembly animation:

- Twigs should bind to **tree skeleton joints**, not their own skeleton
- The `NaniteAssemblySkelBindingAPI` on PointInstancer binds instances to tree joints
- Having a skeleton inside each twig is unnecessary and may cause conflicts

### Recommendation

**For skeletal Nanite Assemblies:**

1. Use **static (non-skeletal) twig USD files** as prototype references
2. Binding to tree skeleton is done at **PointInstancer level** via `NaniteAssemblySkelBindingAPI`
3. Individual twigs don't need their own skeletons

This matches how skeletal instancing works:

- Main mesh has skeleton
- Instanced meshes don't have skeletons
- PointInstancer binds instances to main skeleton joints

## Recommended Fix

### Step 1: Use Static Twigs for Skeletal Assemblies

```python
# In create_nanite_assembly_usd()
if use_skeletal_mesh:
    # Use static twigs (no skeleton)
    # Binding happens at PointInstancer level
    twig_ref_paths = {
        k: v.parent / v.name.replace("_skeletal", "")  # Remove _skeletal suffix
        for k, v in twig_usd_paths.items()
    }
else:
    twig_ref_paths = twig_usd_paths
```

### Step 2: Add USD References with Relative Paths

```python
# Reference twig mesh with relative path
twig_relative_path = Path(".").joinpath(*twig_ref_path.parts[-3:])
proto_prim.GetReferences().AddReference(str(twig_relative_path))
```

### Step 3: Optionally Add meshAssetPath for Unreal

```python
# For Unreal workflow: set meshAssetPath
# This is used if twigs are pre-imported into Unreal
if use_skeletal_mesh:
    mesh_type = "SkeletalMesh"
else:
    mesh_type = "StaticMesh"

proto_prim.CreateAttribute(
    "unreal:naniteAssembly:meshAssetPath",
    Sdf.ValueTypeNames.Token,
    variability=Sdf.VariabilityUniform
).Set(f"/Game/Trees/{species_name}/Twigs/{twig_type}_{mesh_type}")
```

## Expected Outcome

**Before Fix:**

```usda
def Xform "twigdead" (
    apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    references = @/absolute/path/europeanbeech_var_b_skeletal.usda@
)
```

- **Result:** Unreal ignores reference, no twigs visible

**After Fix:**

```usda
def Xform "twigdead" (
    apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    references = @../../../data/assets/twigs/EuropeanBeechTwig/europeanbeech_var_b.usda@
)
{
    uniform token unreal:naniteAssembly:meshAssetPath = "/Game/Trees/Beech/Twigs/twigdead"
    token visibility = "invisible"
}
```

- **Result:** Unreal can resolve reference OR use pre-imported asset

## Testing Plan

1. **Test with static twigs in skeletal assembly**
   - Use `europeanbeech_var_a.usda` instead of `europeanbeech_var_a_skeletal.usda`
   - Verify twigs appear in Unreal

2. **Test with relative paths**
   - Change absolute paths to relative
   - Check if Unreal resolves references

3. **Test with meshAssetPath**
   - Pre-import twigs into Unreal
   - Set meshAssetPath to match Unreal package paths
   - Verify Nanite Assembly uses imported assets

## Implementation Priority

1. **High Priority:** Use static twigs for skeletal assemblies
2. **High Priority:** Use relative USD references instead of absolute
3. **Medium Priority:** Add meshAssetPath attribute for Unreal workflow
4. **Low Priority:** Document two-workflow support (USD-only vs Unreal-asset)

## Related Files

- `src/growpy/io/unreal_nanite_assembly.py` - Nanite Assembly creation
- `data/unreal_schema/unreal/schema.usda` - Unreal USD schema
- `data/assets/twigs/*/` - Twig USD files (static and skeletal)

## Next Steps

1. Modify `create_nanite_assembly_usd()` to use static twigs for skeletal assemblies
2. Change USD references from absolute to relative paths
3. Test in Unreal Engine
4. If still not working, implement full meshAssetPath workflow

---

**Status:** Implementation required  
**Impact:** CRITICAL - blocks skeletal Nanite Assembly functionality  
**Estimated Fix Time:** 30-60 minutes
