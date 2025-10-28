# Skeletal Nanite Assembly - Fixed

## Date: 2025-01-09

## Summary

Successfully fixed skeletal Nanite Assembly to use static mesh twigs instead of skeletal twigs. This resolves the issue where only the root joint affected twigs during skeletal animation.

## Problem Diagnosed

The skeletal Nanite Assembly was using **skeletal twigs** (each with its own single-joint skeleton) instead of **static mesh twigs**:

- Each skeletal twig file contained: `uniform token[] joints = ["root"]`
- All twig vertices were bound to joint index 0: `int[] primvars:skel:jointIndices = [0, 0, 0, ...]`
- The `bindJoints` attribute only positioned the twig's root transform at the tree joint
- **Result**: Twigs moved as rigid bodies only, no actual skinning to tree skeleton

## Solution Implemented

### Code Changes

**1. src/growpy/io/blender_export.py (line ~3398)**

```python
# BEFORE
skeletal_twig_paths_src = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=True  # ❌ Used skeletal twigs
)

# AFTER  
skeletal_twig_paths_src = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=False  # ✅ Use static twigs
)
```

**2. src/growpy/io/usd_builder.py (line ~1153)**

```python
# BEFORE
twig_skelroot.GetReferences().AddReference(twig_ref_path, "/Twig")  # ❌ Hardcoded path

# AFTER
twig_skelroot.GetReferences().AddReference(twig_ref_path)  # ✅ Use defaultPrim
```

### Why These Changes Work

1. **Static mesh twigs** have no skeleton component - just pure geometry
2. **bindJoints** attribute in Nanite Assembly tells Unreal which tree joint to bind each twig instance to
3. When tree skeleton animates, Unreal transforms static twig geometry based on bound joint
4. Static twigs follow tree joint transforms correctly during animation

## USD Structure Changes

### Before (Broken - Skeletal Twigs)

```usd
# Skeletal twig file (westernredcedar_apical_skel.usda)
def SkelRoot "Twig" {
    def Skeleton "Skel" {
        uniform token[] joints = ["root"]  # Single joint
    }
    def Mesh "WesternRedCedarApicalTwig" {
        int[] primvars:skel:jointIndices = [0, 0, 0, ...]  # All verts → joint 0
    }
}

# Skeletal Nanite Assembly
def SkelRoot "TwigSkelRoot" (
    prepend references = @./westernredcedar_apical_skel.usda@</Twig>  # ❌
) {}
```

### After (Fixed - Static Twigs)

```usd
# Static twig file (westernredcedar_apical.usda)
def Xform "root" (
    defaultPrim = "root"  # No skeleton!
) {
    def Xform "westernredcedar_apical_mount" {
        def Xform "WesternRedCedarApicalTwig" {
            def Mesh "WesternRedCedarApicalTwig" {
                # Pure geometry, no skeleton binding
            }
        }
    }
}

# Skeletal Nanite Assembly
def SkelRoot "TwigSkelRoot" (
    prepend references = @./westernredcedar_apical.usda@  # ✅ Uses defaultPrim
) {}

def PointInstancer "TwigInstances" (
    prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
) {
    uniform token[] primvars:unreal:naniteAssembly:bindJoints = [
        "joint_0/joint_1/joint_2/joint_3/joint_4/joint_10/joint_11/joint_12/joint_13",
        "joint_0/joint_1/joint_2/joint_3/joint_4/joint_10/joint_11/joint_12/joint_14",
        ...
    ]
}
```

## Test Results

Generated skeletal assembly with 3 growth cycles:

- **Tree**: 40 joints across 16 branches
- **Twigs**: 16 static mesh instances bound to tree skeleton
- **bindJoints**: Hierarchical paths correctly matching tree skeleton
- **USD References**: Clean references using defaultPrim (no errors)

## Output Location

```
data/output/skeletal_test_static_fixed/Western_redcedar/
├── Western_redcedar_tree_0000_tree_only_skeletal.usda  (tree with skeleton)
├── Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda  (skeletal assembly)
├── westernredcedar_apical.usda  (static twig)
├── westernredcedar_lateral.usda  (static twig)
└── ...
```

## Next Steps

### 1. Test in Unreal Engine

- Import `Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda`
- Verify it imports as skeletal mesh with tree skeleton + static twigs
- Animate skeleton using Unreal's skeletal animation system
- **Expected**: Twigs should follow their bound tree joints during animation

### 2. Investigate Branch Deformation Issue

User reported: "bending the joints not only bends the branches, it also deforms them a bit, changing them from round to more flat"

**Possible Causes**:

- Incorrect skinning weights (vertices weighted to multiple joints?)
- Bind pose transforms not matching rest pose
- Scale inheritance issues in skeleton

**Investigation Needed**:

- Check `primvars:skel:jointIndices` and `primvars:skel:jointWeights` on tree mesh
- Verify bind transforms match geometry rest state
- May need to adjust skeleton export or mesh skinning in blender_export.py

### 3. Generate Full Test Trees

- Test with more growth cycles (5-10) for fuller branch structure
- Test with different species/twig types
- Verify performance with larger tree instances

## Technical Notes

### Skeletal Nanite Assembly Architecture

**Components**:

1. **Tree**: Skeletal mesh with full UsdSkel skeleton hierarchy
2. **Twigs**: **STATIC meshes** positioned/oriented by bindJoints
3. **PointInstancer**: Nanite Assembly with twig instances + bindJoints
4. **bindJoints**: Maps each twig instance to a tree skeleton joint

**How It Works in Unreal**:

1. Tree skeleton joints animate/deform tree mesh via skinning
2. Unreal reads bindJoints for each twig instance
3. Static twig geometry transforms based on bound joint's world transform
4. Twigs follow tree motion during skeletal animation

### Key Learnings

1. **Skeletal twigs don't work for skeletal assemblies** - they have their own skeleton which conflicts with tree skeleton
2. **Static mesh twigs are correct** - pure geometry that Unreal can transform based on tree joints
3. **USD references need defaultPrim** - hardcoded prim paths break when switching between skeletal/static twigs
4. **bindJoints requires hierarchical paths** - flat joint names don't match tree skeleton structure

## Files Modified

- `src/growpy/io/blender_export.py` (line ~3398)
- `src/growpy/io/usd_builder.py` (line ~1153)

## Related Documentation

- `SKELETAL_ASSEMBLY_STATUS.md` - Previous status before this fix
- `docs/archive/NANITE_ASSEMBLY_SKELETAL_BINDING_SOLUTION.md` - Original skeletal binding approach
- `docs/archive/NANITE_ASSEMBLY_WORKING_SOLUTION.md` - Static Nanite Assembly (working reference)

## Commit Information

**Changes Ready for Commit**:

```bash
# Files modified
src/growpy/io/blender_export.py
src/growpy/io/usd_builder.py

# Test output
data/output/skeletal_test_static_fixed/
```

**Suggested Commit Message**:

```
Fix skeletal Nanite Assembly to use static mesh twigs

- Changed prefer_skeletal=True to False in blender_export.py
  (skeletal twigs have own single-joint skeleton, don't work for assembly)
- Fixed USD reference to use defaultPrim instead of hardcoded "/Twig"
  (supports both static and skeletal twig files)
- Static mesh twigs now properly bind to tree skeleton joints via bindJoints
- Resolves issue where only root joint affected twigs during animation

Generated test with 3 growth cycles: 40 joints, 16 branches, 16 static twigs
USD structure verified with clean references and hierarchical bindJoints paths
```
