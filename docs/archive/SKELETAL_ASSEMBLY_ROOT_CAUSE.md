# Skeletal Assembly Root Cause Analysis

## Date: 2025-01-14

## Problem Summary

Twig meshes deformed incorrectly in Nanite Assembly - tree skeleton joints were affecting twig mesh vertices instead of just positioning twig instances.

## Incorrect Diagnosis (What I Thought)

Initially believed `bindJoints` primvars on the PointInstancer were causing Unreal to override twig's internal skeletal binding with tree skeleton paths. **This was WRONG**.

## Actual Root Cause Discovery

Working demo assembly (`demo_assembly_external_ref.usda`) **DOES** have `bindJoints` and works correctly!

### Key Evidence

**Working Demo Structure:**

```usd
def PointInstancer "TwigInstances" (
    prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
)
{
    uniform token[] primvars:unreal:naniteAssembly:bindJoints = [
        "root/joint_1/twig_1",
        "root/joint_1/joint_2/twig_2",
        "root/joint_1/branch_1/branch_tip/twig_3"
    ]
    uniform float[] primvars:unreal:naniteAssembly:bindJointWeights = [1, 1, 1]
}
```

**Tree Skeleton in Demo:**

```usd
def Skeleton "TreeSkel"
{
    uniform token[] joints = [
        "root",                              # <- Uses "root" prefix
        "root/joint_1",
        "root/joint_1/joint_2",
        "root/joint_1/joint_2/joint_3",
        ...
    ]
}
```

**Generated Tree Skeleton:**

```usd
def Skeleton "Skeleton"
{
    uniform token[] joints = [
        "joint_0",                           # <- Uses "joint_0" prefix
        "joint_0/joint_1",
        "joint_0/joint_1/joint_2",
        ...
    ]
}
```

## Real Problem

The `bindJoints` paths in the PointInstancer **MUST match** the actual joint paths in the tree skeleton.

**Demo**: `bindJoints = ["root/joint_1/twig_1"]` matches `joints = ["root", "root/joint_1", ...]`

**Generated**: `bindJoints = ["joint_0/joint_1/twig_0"]` should match skeleton but working demo proves this approach is correct.

## Additional Findings

### Twig USD Structure Differences

**Working Demo Twig:**

```usd
def SkelRoot "Twig" (
    prepend apiSchemas = ["SkelBindingAPI"]    # <- Has SkelBindingAPI on SkelRoot
)
{
    # NO skeleton relationships here!
    
    def Skeleton "Skel" { ... }
    
    def Mesh "Mesh" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        rel skel:skeleton = </Twig/Skel>        # <- ONLY on mesh
        int[] primvars:skel:jointIndices = ...
        float[] primvars:skel:jointWeights = ...
    }
}
```

**Generated Twig:**

```usd
def SkelRoot "Twig"                             # <- NO SkelBindingAPI on SkelRoot
{
    # Has skeleton relationships here (REDUNDANT):
    rel skel:animationSource = </Twig/Skel>
    rel skel:skeleton = </Twig/Skel>
    
    def Skeleton "Skel" { ... }
    
    def Mesh "Mesh" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        rel skel:skeleton = </Twig/Skel>        # <- Also on mesh
        int[] primvars:skel:jointIndices = ...
        float[] primvars:skel:jointWeights = ...
    }
}
```

## Required Fixes

### 1. Restore bindJoints Creation

The code in `unreal_nanite_assembly.py` that creates `bindJoints` and `bindJointWeights` primvars **MUST be restored**. The removal was based on incorrect diagnosis.

Location: `src/growpy/io/unreal_nanite_assembly.py` lines ~325-350

### 2. Fix Twig USD Export Structure

The twig export in `src/growpy/io/blender_usd_export.py` should:

- Add `SkelBindingAPI` to `SkelRoot` prim
- Remove redundant `skel:skeleton` and `skel:animationSource` from `SkelRoot`
- Keep these relationships **ONLY** on the `Mesh` prim

### 3. Verify Joint Path Correctness

Ensure the joint paths extracted by `_extract_twig_joint_mapping_from_usd()` match the actual skeleton joint names in the tree USD file.

## Conclusion

**bindJoints ARE REQUIRED** - they tell Unreal which tree skeleton joint positions each twig instance. The problem was NOT their presence, but potentially:

1. Mismatched joint path formats
2. Incorrect twig USD structure (missing SkelBindingAPI on SkelRoot)
3. Redundant skeleton relationships causing confusion

The next step is to restore the bindJoints code and fix the twig USD export structure to match the working demo.
