# Assembly Skinning Issue - Root Cause Analysis

## Problem

When importing a skeletal mesh as part of a Nanite Assembly, the mesh deforms incorrectly (jagged, irregular surface) compared to importing the same skeletal mesh standalone (smooth, correct deformation).

## What We've Tested

### Files Created

1. `simple_tree_skel.usda` - Standalone skeletal tree (WORKS - smooth deformation)
2. `simple_assembly.usda` - Assembly with tree + twig instances (BROKEN - jagged deformation)
3. `simple_assembly_no_twigs.usda` - Assembly with only tree, no twigs (BROKEN)

### Fixes Attempted

1. ✗ Fixed negative skinning weights (vertices 216-227) - improved but didn't fix
2. ✗ Added `primvars:skel:geomBindTransform` - no effect
3. ✗ Added skeleton relationship overrides in SkelRoot - made it worse
4. ✗ Matched working assembly structure exactly - still broken
5. ✗ Added `defaultPrim` metadata - no effect
6. ✗ Changed `token[]` to `uniform token[]` - no effect
7. ✗ Removed twig instances entirely - still broken

### Key Observations

- **Skeleton data is identical** in both standalone and assembly contexts (same joints, transforms, weights)
- **Assembly without twigs is still broken** - proves issue is not twig-related
- **Working demo assembly exists** - same USD structure works for other trees
- **Surface appears jagged** in assembly but smooth standalone - indicates weight/transform computation issue

## Root Cause Hypothesis

The issue appears to be in **how Unreal Engine evaluates skeletal binding in Nanite Assembly context**:

1. When loading standalone: Skeleton transforms → Skin deformation (correct)
2. When loading assembly: Assembly transform → Skeleton transforms → Skin deformation (broken)

**Possible causes:**

- Unreal may be applying an extra transform layer for assembly root
- Skeleton bind poses may be evaluated in different coordinate spaces
- Joint hierarchy traversal may differ in assembly context
- Nanite assembly system may cache or precompute skinning differently

## Comparison with Working Assembly

Working demo (`demo_assembly_external_ref.usda`):

- Uses exact same USD structure
- Same skeleton binding approach
- Same API schemas

**Key difference to investigate:**

- Different skeleton joint structure (uses `root/joint_1/...` naming vs `joint_0/joint_1/...`)
- Different mesh topology (triangles vs quads)
- Different weight distribution

## Next Steps to Debug

1. **Export working assembly tree as standalone** - test if demo tree works both ways
2. **Import simple tree with demo tree's joint naming** - test if naming convention matters
3. **Compare FBX export** - check if issue exists outside USD workflow
4. **Test with linear skin weights** - eliminate complex weight blending
5. **Check Unreal import logs** - look for warnings about skeleton binding
6. **Test in UE 5.5 vs 5.4** - check if this is a version-specific bug

## Suspected Unreal Bug

This appears to be a bug in Unreal Engine's Nanite Assembly skeletal mesh import where:

- The skeleton binding evaluation uses wrong transform space when inside assembly
- Could be related to `unreal:naniteAssembly:skeleton` relationship handling
- May need Epic Games support/bug report

## Workaround Attempts Needed

1. Use FBX instead of USD for tree mesh
2. Bake skinning to blend shapes
3. Use static mesh with vertex animation
4. Contact Epic about Nanite Assembly skeletal mesh limitations
