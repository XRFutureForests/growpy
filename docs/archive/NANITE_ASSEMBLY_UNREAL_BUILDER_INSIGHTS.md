# Nanite Assembly - Unreal Builder System Insights

**Date**: 2025-10-13  
**Critical Discovery**: Nanite Assemblies require C++ builder execution, not just USD schema compliance

## The Fundamental Misunderstanding

We initially believed that properly structured USD files with correct schema would automatically be recognized as Nanite Assemblies when imported to Unreal Engine. **This is incorrect.**

### What We Thought

```
USD File (correct schema) → Import to UE → Automatic Nanite Assembly ✅
```

### What Actually Happens

```
USD File (correct schema) → Import to UE → Skeletal Mesh ❌
                                         ↓
                                  (requires)
                                         ↓
                        Nanite Assembly Builder Execution
                                         ↓
                                   Nanite Assembly ✅
```

## Evidence from Unreal Source Code

### 1. Nanite Assembly is a Build-Time Feature

From `SkeletalMesh.h` (lines 1096-1112):

```cpp
/**
 * Returns true if this skeletal mesh is a Nanite Assembly
 */
ENGINE_API bool IsNaniteAssembly() const;

/**
 * Caches the meshes referenced by the Nanite Assembly data for the mesh to be used for build. Must
 * be called on the game thread before any asynchronous building. You should only need to call this externally
 * if caching render data manually (as opposed to using CacheDerivedData on the game thread or async mesh build).
 */
ENGINE_API void RecacheNaniteAssemblyReferences(bool bWaitForAsyncCompile = true);

/**
 * Retrieves the cached array of static meshes referenced by the Nanite Assembly data.
 * NOTE: This array is only meant to contain anything during static mesh build.
 */
ENGINE_API const TArray<TObjectPtr<USkeletalMesh>>& GetCachedNaniteAssemblyReferences() const;
```

**Key Insight**: Nanite Assembly requires **caching references** and **build-time processing**. It's not just a property - it's a **compilation step**.

### 2. Builder-Based Assembly Creation

From `NaniteAssemblySkeletalMeshBuilder.cpp`:

```cpp
UNaniteAssemblySkeletalMeshBuilder* UNaniteAssemblySkeletalMeshBuilder::BeginNewSkeletalMeshAssemblyBuild(
 const FNaniteAssemblyCreateNewParameters& Parameters,
 const USkeletalMesh* BaseMesh
)
{
 if (!ValidateValidMeshAndSkeleton(TEXT("BeginNewSkeletalMeshAssemblyBuild"), BaseMesh))
 {
  return nullptr;
 }
 
 if (USkeletalMesh* TargetMesh = CreateNewMeshForAssemblyBuild<USkeletalMesh>(Parameters, BaseMesh))
 {
  return BeginEditSkeletalMeshAssemblyBuild(TargetMesh);
 }
 
 return nullptr;
}

bool UNaniteAssemblySkeletalMeshBuilder::FinishAssemblyBuild(USkeletalMesh*& OutSkeletalMesh)
{
 // ...
 TargetMesh->NaniteSettings.bEnabled = true;
 TargetMesh->PostEditChange();
 // ...
}
```

**Key Insight**: Nanite Assemblies are created through a **builder pattern** that:

1. Creates a new skeletal mesh
2. Adds assembly parts programmatically
3. Validates bone bindings
4. Enables Nanite explicitly
5. Finalizes with `PostEditChange()`

### 3. The Import Process

The USD importer likely follows this flow:

```
USD Import → Create USkeletalMesh → Parse USD attributes → (Missing Step) → Finish Import
```

The **missing step** is calling the Nanite Assembly builder. Without it, you get a regular skeletal mesh with USD data but **no assembly processing**.

## Why Static Meshes Work But Skeletal Don't

Looking at your earlier statement: *"the static mesh version is recognized as nanite assembly"*

This suggests:

- **Static Mesh Nanite Assemblies** have simpler import path (or better importer support)
- **Skeletal Mesh Nanite Assemblies** require additional builder execution that USD importer doesn't trigger

## Potential Solutions

### Solution 1: Post-Import Python Script

Create a Python script that runs after USD import to build the assembly:

```python
import unreal

def build_nanite_assembly_from_imported_mesh(skeletal_mesh_path):
    """
    Takes an imported skeletal mesh with USD nanite assembly metadata
    and rebuilds it as a proper Nanite Assembly using the builder.
    """
    mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    
    if not mesh:
        unreal.log_error(f"Failed to load mesh: {skeletal_mesh_path}")
        return False
    
    # Check if it has nanite assembly metadata from USD
    # (You'd need to check for custom properties or USD metadata)
    
    # Create builder parameters
    params = unreal.NaniteAssemblyCreateNewParameters()
    # Configure params based on USD data...
    
    # Begin assembly build
    builder = unreal.NaniteAssemblySkeletalMeshBuilder.begin_new_skeletal_mesh_assembly_build(
        params, mesh
    )
    
    if not builder:
        unreal.log_error("Failed to create assembly builder")
        return False
    
    # Add assembly parts (would need to parse from USD)
    # builder.add_assembly_parts(...)
    
    # Finish build
    out_mesh = unreal.SkeletalMesh()
    if builder.finish_assembly_build(out_mesh):
        unreal.log("Successfully built Nanite Assembly")
        return True
    
    return False
```

### Solution 2: Custom USD Importer Plugin

Extend the USD importer to recognize `NaniteAssemblyRootAPI` and automatically trigger builder:

```cpp
// In custom USD importer plugin

void FCustomUSDImporter::ImportSkeletalMesh(const pxr::UsdPrim& Prim)
{
    USkeletalMesh* ImportedMesh = ImportBaseSkeletalMesh(Prim);
    
    // Check for NaniteAssemblyRootAPI
    if (Prim.HasAPI<pxr::UsdNaniteAssemblyRootAPI>())
    {
        BuildNaniteAssembly(ImportedMesh, Prim);
    }
}

void FCustomUSDImporter::BuildNaniteAssembly(USkeletalMesh* BaseMesh, const pxr::UsdPrim& Prim)
{
    // Create builder
    FNaniteAssemblyCreateNewParameters Params;
    // Parse parameters from USD...
    
    UNaniteAssemblySkeletalMeshBuilder* Builder = 
        UNaniteAssemblySkeletalMeshBuilder::BeginNewSkeletalMeshAssemblyBuild(Params, BaseMesh);
    
    // Parse and add assembly parts from USD PointInstancer
    // ...
    
    USkeletalMesh* OutMesh;
    Builder->FinishAssemblyBuild(OutMesh);
}
```

### Solution 3: Blueprint Post-Import Processor

Create a Blueprint that processes imported meshes:

1. Detect USD files with Nanite Assembly metadata
2. Call assembly builder through Blueprint nodes (if exposed)
3. Save the rebuilt asset

### Solution 4: Manual Builder Execution

For testing, manually execute the builder in Unreal:

1. Import your USD file (creates skeletal mesh)
2. Open Skeletal Mesh Editor
3. Use Python console or C++ to call builder API
4. Save the rebuilt assembly

## Recommended Immediate Action

**Test with Python Script First**:

1. Import your fixed USD file to Unreal
2. Verify it creates a skeletal mesh (even if not recognized as assembly)
3. Run a Python script to:
   - Load the imported mesh
   - Create a Nanite Assembly builder
   - Add the mesh as the base
   - Add twig parts from USD metadata
   - Finish build
   - Check if assembly is now recognized

## Code Example: Minimal Python Test

```python
import unreal

# After importing your USD file
mesh_path = "/Game/Trees/Beech/Beech_tree_0000_NaniteAssembly_skeletal"
mesh = unreal.load_asset(mesh_path)

# Check current state
print(f"Is Nanite Assembly: {mesh.is_nanite_assembly()}")
print(f"Nanite Enabled: {mesh.get_nanite_settings().b_enabled}")

# If not assembly, would need to rebuild using builder
# (Requires exposed Blueprint/Python API for NaniteAssemblySkeletalMeshBuilder)
```

## Critical Questions to Answer

1. **Does the USD importer have any flags/options for Nanite Assembly processing?**
   - Check import dialog for "Build Nanite Assembly" checkbox
   - Look for USD-specific importer settings

2. **Is `UNaniteAssemblySkeletalMeshBuilder` exposed to Python/Blueprint?**
   - Check `unreal` Python module for assembly builder classes
   - Look in Blueprint library for assembly nodes

3. **What metadata does Procedural Vegetation use?**
   - Compare Procedural Vegetation assets to your USD imports
   - Check for custom metadata or flags set by PCG system

4. **Are there example USD files that successfully import as assemblies?**
   - Look in Unreal sample projects for working examples
   - Check Epic Games marketplace assets

## Next Steps

1. **Verify USD structure is correct** (already done ✅)
2. **Import USD to Unreal** - Check what gets created
3. **Inspect imported asset** - Look for any metadata that made it through
4. **Test manual builder** - Try calling builder API directly
5. **Create post-import automation** - Script the builder execution
6. **Report findings** - Document what works for future reference

## Key Takeaway

**Nanite Assembly is a compilation target, not an import format.** The USD files provide the **data**, but Unreal must **build** the assembly using its internal builder system. Think of it like:

- USD = Source Code
- Nanite Assembly Builder = Compiler
- Assembly Asset = Compiled Binary

Without running the compiler (builder), you just have source code sitting in the project.

---

**Status**: Hypothesis formed - requires testing in Unreal Engine with builder API access
