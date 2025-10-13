# Nanite Skeletal Mesh Fix - C++ Builder Insights

**Date**: 2025-10-13  
**Issue**: Skeletal Nanite Assemblies not recognized by Unreal Engine  
**Root Cause**: Incorrect USD structure - skeleton path not resolvable

## Critical Discovery from C++ Code

Analysis of `NaniteAssemblySkeletalMeshBuilder.cpp` revealed Unreal's strict validation requirements:

### 1. Skeleton Validation

```cpp
if (Mesh == nullptr || Mesh->GetSkeleton() == nullptr)
{
    UE_LOG(LogNaniteAssemblyBuilder, Error,
        TEXT("Target Skeletal Mesh has no valid skeleton"));
    return false;
}
```

**Requirement**: The skeletal mesh MUST have a valid skeleton accessible via `GetSkeleton()`.

### 2. Bone Index Validation

```cpp
const FReferenceSkeleton& RefSkel = TargetMesh->GetSkeleton()->GetReferenceSkeleton();

for (const auto& BoneInfluence : Binding.BoneInfluences)
{
    if(!RefSkel.IsValidIndex(BoneInfluence.BoneIndex))
    {
        UE_LOG(LogNaniteAssemblyBuilder, Error,
            TEXT("Binding with invalid bone index %d encountered"),
            BoneInfluence.BoneIndex);
        return false;
    }
}
```

**Requirement**: All bone bindings must reference **valid indices** from the reference skeleton.

### 3. Bone Influences Required

```cpp
if (Binding.BoneInfluences.Num() == 0)
{
    UE_LOG(LogNaniteAssemblyBuilder, Error,
        TEXT("Invalid binding with 0 bone influences"));
    return false;
}
```

**Requirement**: Each twig binding needs at least one bone influence with non-zero weight.

## The USD Structure Problem

### Original Broken Structure

```usda
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    prepend references = @.../tree_skeletal.usda@</Tree>  ❌ WRONG
)
{
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    custom rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
}
```

**Problem**: The reference brings in `/Tree`, so the actual skeleton path becomes:

- `/Beech_NaniteAssembly/Tree/SkelRoot/Skeleton` (actual)
- `/Beech_NaniteAssembly/SkelRoot/Skeleton` (expected) ❌ PATH DOESN'T EXIST

### Fixed Structure (Matches Static Assembly Pattern)

```usda
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    custom rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/TreeMesh/SkelRoot/Skeleton>

    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @.../tree_skeletal.usda@</Tree>
    )
    {
    }
    
    def PointInstancer "TwigInstances" (
        prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    )
    {
        uniform token[] primvars:unreal:naniteAssembly:bindJoints = [...]
        uniform float[] primvars:unreal:naniteAssembly:bindJointWeights = [...]
    }
}
```

**Solution**: Wrap the tree reference in a `TreeMesh` child Xform, making the skeleton path:

- `/Beech_NaniteAssembly/TreeMesh/SkelRoot/Skeleton` (actual from `/Tree/SkelRoot/Skeleton`)
- `/Beech_NaniteAssembly/TreeMesh/SkelRoot/Skeleton` (expected) ✅ PATH RESOLVES

## Additional Insights from C++ Builder

### Socket Support

```cpp
FTransform SocketTransform;
int32 BoneIndex, SocketIndex;
if (TargetMesh->FindSocketInfo(SocketName, SocketTransform, BoneIndex, SocketIndex))
{
    OutBinding.BoneInfluences.Add({ BoneIndex, 1.0f });
    OutBinding.Transform = Transform;
}
```

Unreal supports **socket-based binding** for precise attachment points (e.g., "leaf_socket_01").

**Future Enhancement**: Export socket definitions from Grove mount points.

### Transform Spaces

```cpp
enum ENaniteAssemblyNodeTransformSpace
{
    BoneRelative,     // Transform relative to bone
    ComponentRelative // Transform relative to component root
};
```

**Current Implementation**: Uses component-relative (world space) transforms.  
**Future Enhancement**: Consider bone-relative transforms for better animation follow-through.

### Multi-Bone Influences

```cpp
for (const auto& BoneInfluence : Binding.BoneInfluences)
{
    // Each instance can bind to multiple bones with weights
    Binding.BoneInfluences.Add({ BoneIndex, Weight });
}
```

**Current Implementation**: Single bone per twig (nearest joint).  
**Future Enhancement**: Multi-bone influences for better deformation (e.g., bind to 2-3 nearest joints).

## Code Changes Applied

### 1. TreeMesh Wrapper for Skeletal Assemblies

**File**: `src/growpy/io/unreal_nanite_assembly.py`  
**Lines**: 105-136

```python
# Handle tree mesh - BOTH static and skeletal use TreeMesh wrapper
tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")
tree_api_schemas = Sdf.TokenListOp()
tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
tree_prim.SetMetadata("apiSchemas", tree_api_schemas)

tree_prim.GetReferences().AddReference(
    str(tree_usd_path.resolve()),
    "/Tree",  # Reference the Tree prim from source USD
)

if use_skeletal_mesh:
    skeleton_rel = root_prim.CreateRelationship(
        "unreal:naniteAssembly:skeleton",
        custom=True,
    )
    # Path now resolves correctly through TreeMesh
    skeleton_rel.AddTarget(f"/{assembly_name}/TreeMesh/SkelRoot/Skeleton")
```

### 2. Improved Skeleton Joint Extraction

**File**: `src/growpy/io/unreal_nanite_assembly.py`  
**Lines**: 611-660

- Validates skeleton prim exists
- Checks joint count matches bind transforms count
- Extracts joint hierarchy (parent-child relationships)
- Returns validated joint data with indices

### 3. Better Bone Binding

**File**: `src/growpy/io/unreal_nanite_assembly.py`  
**Lines**: 665-700

- Uses Euclidean distance for nearest joint
- Validates joint paths match skeleton hierarchy
- Falls back to Root if no valid joints found
- Proper Vec3d math for precision

## Testing Checklist

- [x] Fix TreeMesh wrapper structure
- [x] Update skeleton path to `/{assembly}/TreeMesh/SkelRoot/Skeleton`
- [x] Fix duplicate "via TreeMesh" in print statement
- [ ] Test in Unreal Engine 5.7+
- [ ] Verify skeleton relationship resolves
- [ ] Check twig binding to joints
- [ ] Validate Nanite assembly icon appears
- [ ] Test skeletal animation (wind, growth)

## Expected Behavior After Fix

1. **Unreal Import**: Skeletal assembly recognized with Nanite icon
2. **Skeleton Path**: Resolves to valid UsdSkel::Skeleton prim
3. **Bone Bindings**: All twig instances bound to valid skeleton joints
4. **Animation**: Twigs follow skeleton deformation (wind, procedural animation)
5. **Nanite Rendering**: Efficient LOD with skeletal mesh support

## Key Takeaways

1. **Consistency Matters**: Both static and skeletal assemblies should use identical structure (TreeMesh wrapper)
2. **Path Resolution**: USD reference composition affects prim paths - always validate final paths
3. **Validation Required**: Unreal performs strict validation - all bone indices must be valid
4. **Future Enhancements**: Socket support and multi-bone influences will improve quality

## References

- Unreal C++ Source: `NaniteAssemblySkeletalMeshBuilder.cpp`
- USD Composition: <https://openusd.org/release/glossary.html#usdglossary-composition>
- UsdSkel Specification: <https://openusd.org/release/api/usd_skel_page_front.html>
- Unreal Nanite Assemblies: <https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine>

---

**Status**: Fix applied, awaiting Unreal Engine testing
