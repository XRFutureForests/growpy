# Nanite Skeletal Assembly - Critical Bug Found

**Date**: 2025-01-11  
**Status**: Bug identified - ready to fix

## The Issue

After comparing the generated Nanite Assembly with the Unreal schema, the critical bug has been identified:

**The Nanite Assembly is referencing the wrong USD file - it's pointing to geometry-only USD instead of the skeletal USD that contains the skeleton.**

### Current Output (Broken)

**File**: `Beech_tree_0000_NaniteAssembly_skeletal.usda`

```usda
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    prepend references = @Beech_tree_0000_tree_only.usda@</Tree>  # ❌ WRONG FILE!
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
}
```

**Problem**:

- References `tree_only.usda` which contains ONLY `def Mesh "Tree"`
- No `SkelRoot`, no `Skeleton`, no skeletal structure
- The skeleton relationship points to `</Beech_NaniteAssembly/SkelRoot/Skeleton>` but this path doesn't exist after USD composition!

### Available Files

```bash
$ ls -lh data/output/test/Beech/USD/

Beech_tree_0000_tree_only.usda              (130KB) - Geometry only, NO skeleton
Beech_tree_0000_tree_only_skeletal.usda     (143KB) - Geometry + SkelRoot + Skeleton ✅
Beech_tree_0000_NaniteAssembly_skeletal.usda (3.3KB) - The assembly file
```

### Verification

**`Beech_tree_0000_tree_only.usda`** (currently referenced):

```usda
def Xform "Tree"
{
    def Mesh "Tree" {
        # Just geometry, no skeleton
    }
}
```

**`Beech_tree_0000_tree_only_skeletal.usda`** (should be referenced):

```usda
def Xform "Tree"
{
    def SkelRoot "SkelRoot" (
        prepend apiSchemas = ["SkelBindingAPI"]
    ) {
        def Skeleton "Skeleton" {
            # Skeleton data (joints, bind transforms, etc.)
        }
        def SkelAnimation "Animation" {
            # Animation data
        }
        def Mesh "BranchMesh" (
            prepend apiSchemas = ["MaterialBindingAPI", "SkelBindingAPI"]
        ) {
            rel skel:skeleton = </Tree/SkelRoot/Skeleton>
            # Skinned mesh data
        }
    }
}
```

## Schema Requirement

From `data/unreal_schema/unreal/schema.usda`:

```usda
rel unreal:naniteAssembly:skeleton (
    doc = """The skeleton to consider as the base of this Nanite assembly root 
    (Valid for meshType=skeletalMesh only, and must be a descendant prim)."""
)
```

**"must be a descendant prim"** - The skeleton must exist in the composed USD hierarchy after references are resolved.

### Current Structure (After Composition)

```
Beech_NaniteAssembly/
├── (from reference to tree_only.usda)
│   └── Mesh "Tree"  ❌ No skeleton!
│
└── (skeleton relationship points to)
    └── </Beech_NaniteAssembly/SkelRoot/Skeleton>  ❌ Doesn't exist!
```

### Required Structure (After Composition)

```
Beech_NaniteAssembly/
├── (from reference to tree_only_skeletal.usda)
│   └── SkelRoot "SkelRoot"  ✅
│       ├── Skeleton "Skeleton"  ✅
│       ├── SkelAnimation "Animation"
│       └── Mesh "BranchMesh" (skinned)
│
└── (skeleton relationship points to)
    └── </Beech_NaniteAssembly/SkelRoot/Skeleton>  ✅ EXISTS!
```

## The Fix

### Code Location

The bug is in how `tree_usd_path` is passed to `create_nanite_assembly_usd()`:

**Problem**: The code is passing the path to the geometry-only tree USD
**Solution**: For skeletal assemblies, pass the path to the skeletal tree USD instead

### File

 Code Change Needed

In the export logic (likely in `generate_forest.py` or `export_trees.py`):

**Current (Wrong)**:

```python
create_nanite_assembly_usd(
    tree_usd_path=tree_path,  # Points to geometry-only USD
    use_skeletal_mesh=True,
    # ...
)
```

**Fixed**:

```python
# For skeletal assemblies, use the skeletal USD path
tree_ref_path = skeletal_tree_path if use_skeletal_mesh else static_tree_path

create_nanite_assembly_usd(
    tree_usd_path=tree_ref_path,  # Points to USD with skeleton
    use_skeletal_mesh=True,
    # ...
)
```

### Expected Result

After fix, the assembly will reference the correct file:

```usda
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    prepend references = @Beech_tree_0000_tree_only_skeletal.usda@</Tree>  # ✅ CORRECT!
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>
    # Now the skeleton path will exist after composition!
}
```

## Why This Matters

1. **USD Composition**: When Unreal imports the assembly, it resolves the reference and composes the prims
2. **Skeleton Must Exist**: The skeleton relationship must point to an actual prim in the composed hierarchy
3. **Current State**: The skeleton path doesn't exist because we're referencing the wrong file
4. **After Fix**: The skeleton path will resolve correctly to the embedded skeleton

## Next Steps

1. Find where `tree_usd_path` is set when creating skeletal assemblies
2. Change it to point to `*_tree_only_skeletal.usda` instead of `*_tree_only.usda`
3. Re-export and verify the skeleton relationship resolves correctly
4. Test import in Unreal Engine

## File Naming Pattern

From the output, it looks like:

- `{species}_tree_{index}_tree_only.usda` - Geometry only
- `{species}_tree_{index}_tree_only_skeletal.usda` - Geometry + skeleton
- `{species}_tree_{index}_NaniteAssembly_skeletal.usda` - Assembly (should reference skeletal)

The fix is simple: use the `_skeletal.usda` variant when creating skeletal Nanite Assemblies.
