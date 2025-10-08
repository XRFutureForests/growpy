# Skeletal Nanite Assembly Issue - 2025-01-08

## Problem

Skeletal Nanite Assemblies cause Unreal Engine to crash during Nanite hierarchy building with error:

```
UnrealEditor-NaniteBuilder.dylib!Nanite::BuildHierarchyRecursive
```

## Root Cause

The skeletal Nanite Assembly was referencing the complete tree USD file in two places:

1. `TreeMesh` prim → references full tree USD (contains mesh + skeleton)
2. `Skeleton` prim → references full tree USD (contains mesh + skeleton)

This creates **duplicate mesh geometry** which confuses Nanite's hierarchical builder, causing a crash.

## Why This Happens

USD doesn't have a simple way to reference only the skeleton from a USD file that contains both mesh and skeleton. Options would be:

1. **Sublayers/Variants**: Complex USD composition not well-supported by Unreal's Nanite Assembly importer
2. **Separate Files**: Export skeleton separately, but breaks mesh-skeleton binding
3. **USD Collections**: Advanced feature not supported by Unreal importer

## Solution

**Don't create skeletal Nanite Assemblies.** Instead:

✅ **Base USD file** (`Oak_var1.usda`) contains:

- Tree mesh geometry
- Skeleton (embedded and bound)
- Bark materials with textures
- Twig placement attributes

✅ **Static Nanite Assembly** (`Oak_var1_NaniteAssembly.usda`):

- References base USD for static mesh use
- Includes twig instances via PointInstancer
- Works perfectly for static foliage

❌ **Skeletal Nanite Assembly**: Not created (causes crash)

## Workflow Changes

### For Static Meshes (Most Common)

```
Import: Oak_var1_NaniteAssembly.usda
Result: Static mesh with Nanite + instanced twigs
Use for: Background trees, static foliage, non-animated vegetation
```

### For Skeletal Meshes (Animation)

```
Import: Oak_var1.usda (base USD file)
Result: Skeletal mesh with skeleton + materials
Use for: Hero trees, wind animation, procedural growth
Note: Import as regular USD (not Nanite Assembly)
```

## Export Output

### Before (Crashed)

```
Oak/
└── USD/
    ├── Oak_var1.usda                          # Base with skeleton
    ├── Oak_var1_NaniteAssembly.usda          # Works
    └── Oak_var1_NaniteAssembly_Skeletal.usda # CRASHES
```

### After (Fixed)

```
Oak/
└── USD/
    ├── Oak_var1.usda                          # Base with skeleton - import for animation
    └── Oak_var1_NaniteAssembly.usda          # Static mesh - import for Nanite
```

## User Guidance

When skeleton is exported, users now see:

```
✓ Nanite Assembly USD: Oak_var1_NaniteAssembly.usda
  Import this file in Unreal Engine 5.7+ (static mesh)

ℹ️  For skeletal mesh with animation:
   Import Oak_var1.usda directly (skeleton embedded)
   Skeletal Nanite Assembly not created (Unreal limitation)
```

## Technical Details

### What Was Attempted

```usd
def Xform "Oak_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </Oak_NaniteAssembly/Skeleton>

    def Xform "TreeMesh" (
        prepend references = @Oak_var1.usda@  # Full tree USD
    )
    
    def Xform "Skeleton" (
        prepend references = @Oak_var1.usda@  # Same file - duplicate!
    )
}
```

**Problem**: Both prims reference the same USD file, causing duplicate geometry.

### Why USD Sublayers Don't Help

USD sublayers would allow:

```usd
def Xform "TreeMesh" (
    prepend references = @Oak_var1.usda@</Tree/Tree>  # Just mesh
)

def Skeleton "Skeleton" (
    prepend references = @Oak_var1.usda@</Tree/Skeleton>  # Just skeleton
)
```

**But**: Unreal's Nanite Assembly importer doesn't properly handle:

- Targeted sublayer references
- UsdSkel binding across references
- Complex USD composition

## Implications

✅ **Static trees work perfectly**:

- Nanite Assembly for optimization
- Instanced twigs for efficiency
- Full material support

✅ **Skeletal trees work (different workflow)**:

- Import base USD directly
- Get skeleton + materials
- Set up animation in Unreal
- No Nanite Assembly needed for hero/animated trees

❌ **Skeletal Nanite Assemblies**:

- Not possible with current Unreal Nanite Assembly support
- USD composition limitations
- Not critical (animated trees typically don't use Nanite anyway)

## Future Possibilities

If Epic improves Nanite Assembly USD support:

1. **Proper USD Composition**: Support for targeted references
2. **Skeleton-Only References**: Reference just skeleton prims
3. **Better SkelRoot Handling**: Proper UsdSkel binding across references

Until then, the current workflow (base USD for skeletal, Assembly for static) is the best approach.

## Related Documentation

- `docs/archive/USD_SKELETON_MATERIALS_ADDED.md` - Skeleton implementation
- `docs/archive/SKELETAL_NANITE_ASSEMBLY_REMOVED.md` - FBX issue history
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import workflows
