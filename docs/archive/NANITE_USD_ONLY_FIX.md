# Nanite Assembly USD-Only Fix

## Date: January 10, 2025

## Issue

Skeletal Nanite Assemblies were incorrectly modified to use FBX references instead of USD references. This violates the Nanite Assembly specification which requires all references to be USD format.

## Root Cause

In attempting to fix the skeletal Nanite Assembly twig import issue, I incorrectly assumed that FBX references would work better than USD references. However, Nanite Assemblies are designed to work exclusively with USD files, and mixing FBX references breaks the proper USD composition and import workflow.

## Correction Applied

Reverted all FBX reference logic from Nanite Assembly creation. Both skeletal and non-skeletal Nanite Assemblies now exclusively use USD references.

### Changes Made

1. **src/growpy/io/unreal_nanite_assembly.py**
   - Removed `tree_fbx_path` parameter from function signature
   - Removed `twig_fbx_paths` parameter from function signature  
   - Removed FBX reference selection logic for tree
   - Removed FBX reference selection logic for twigs
   - Always use USD paths for all references

2. **src/growpy/io/blender_export.py**
   - Removed `get_twig_fbx_map_for_species()` call
   - Removed `tree_fbx_path` calculation
   - Removed FBX path parameters from `create_nanite_assembly_usd()` call
   - Simplified to only pass USD paths

## Actual Root Cause of Skeletal Nanite Issues

The real issues preventing skeletal Nanite Assembly from working properly are:

### 1. USD Skeletal Tree Texture Scale

**Issue**: USD skeletal tree has small/repetitive texture because Blender's USD exporter doesn't preserve Grove's UV aspect ratio scaling.

**Fix Applied**: Manually scale UV V-coordinates by aspect ratio (4.0) when writing UVs to Blender mesh before USD export.

### 2. USD Skeletal Twig Material Binding

**Issue**: Material bindings not properly copied from original mesh to skeletal mesh in `_add_skeleton_to_twig_usd()`.

**Fix Applied**: Check all binding types (direct, collection, purpose-specific) and properly copy material relationships.

### 3. Unreal Import Settings

**Potential Issue**: Unreal may need specific import settings for skeletal Nanite Assemblies that differ from manual skeletal USD import.

**Investigation Needed**:

- Check if Unreal requires specific NaniteAssemblyRootAPI properties for skeletal meshes
- Verify skeleton reference relationship is properly set
- Confirm SkelAnimation prims are present in all skeletal USD files

## Current Nanite Assembly Structure (Correct)

### Static Nanite Assembly

```
/{species}_NaniteAssembly (Xform with NaniteAssemblyRootAPI)
├── meshType = "staticMesh"
├── /TreeMesh (Xform with NaniteAssemblyExternalRefAPI)
│   └── reference → tree_only.usda (USD)
└── /TwigPrototypes (Scope)
    └── /TwigInstances (PointInstancer)
        ├── prototypes → [twig_a.usda, twig_b.usda, ...]
        └── positions, orientations, scales
```

### Skeletal Nanite Assembly

```
/{species}_NaniteAssembly (Xform with NaniteAssemblyRootAPI)
├── meshType = "skeletalMesh"
├── /TreeMesh (Xform with NaniteAssemblyExternalRefAPI)
│   └── reference → tree_only_skeletal.usda (USD, not FBX)
└── /TwigPrototypes (Scope)
    └── /TwigInstances (PointInstancer)
        ├── prototypes → [twig_skeletal.usda, ...] (USD, not FBX)
        └── positions, orientations, scales
```

**Key Point**: All references must be USD format (`.usda` or `.usd`), never FBX.

## Why FBX References Don't Work

1. **USD Composition**: Nanite Assembly uses USD composition system which doesn't understand FBX format
2. **Unreal USD Stage**: Unreal's USD stage loader expects pure USD scene graphs
3. **Schema Validation**: NaniteAssemblyExternalRefAPI expects USD reference paths
4. **Material Propagation**: USD material bindings don't work across FBX boundaries

## Testing After Correction

Export and test in Unreal:

```bash
/Users/maximiliansperlich/miniforge3/envs/the-grove/bin/python ./src/growpy/cli/generate_forest.py ./data/input/test.csv --output-dir ./data/output/nanite_usd_only --quality high --formats fbx usda
```

### Expected Behavior

1. **Static Nanite Assembly**: Works as before (tree + twigs, all USD references)
2. **Skeletal Nanite Assembly**:
   - Uses skeletal USD tree reference (`tree_only_skeletal.usda`)
   - Uses skeletal USD twig references (`*_skeletal.usda`)
   - All references are USD format
   - Should import into Unreal (skeletal recognition depends on proper USD structure)

### If Skeletal Nanite Still Doesn't Work

The issue is likely one of:

1. **SkelAnimation Missing**: Skeletal USD files need SkelAnimation prims for Unreal recognition
2. **Skeleton Reference**: NaniteAssemblyRootAPI skeleton relationship not properly set
3. **Unreal Import Settings**: May need specific import options for skeletal Nanite Assembly
4. **Schema Version**: Unreal's Nanite Assembly schema may not fully support skeletal meshes yet

## Summary

- ✓ Reverted to USD-only references in Nanite Assemblies
- ✓ Removed all FBX reference logic
- ✓ Maintained UV scaling fix for skeletal USD
- ✓ Maintained material binding fix for skeletal twigs
- ✓ Maintained FBX skeletal mesh binding fixes (for direct FBX import)

**Note**: Skeletal Nanite Assembly with USD references may still not fully work in Unreal if the Nanite Assembly system doesn't properly support skeletal meshes yet. If issues persist, the workaround is to import skeletal tree and twigs separately (not via Nanite Assembly).
