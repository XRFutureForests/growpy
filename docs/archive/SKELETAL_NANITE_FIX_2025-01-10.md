# Skeletal Nanite Assembly - Critical Reference Bug Fixed

## Date: 2025-01-10

## Problem

Skeletal Nanite Assemblies were importing static and skeletal meshes in Unreal Engine 5.7+, but the Nanite Assembly itself was not being created. After extensive debugging and schema verification, the root cause was identified:

**The skeletal Nanite Assembly was referencing the wrong USD file** - it referenced `tree_only.usda` (geometry-only, no skeleton) instead of `tree_only_skeletal.usda` (geometry + skeleton).

## Root Cause Analysis

### USD Composition and Skeleton Relationships

According to Unreal Engine's USD schema (`NaniteAssemblyRootAPI`):

- When `meshType="skeletalMesh"`, a `skeleton` relationship is REQUIRED
- The skeleton relationship MUST point to "a descendant prim"
- **After USD composition**, this path must exist in the composed hierarchy

### The Bug

In `src/growpy/io/blender_export.py` line 3569:

```python
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=temp_tree_path,  # ❌ BUG: Points to tree_only.usda (no skeleton)
    ...
)
```

Where:

- `temp_tree_path` = `tree_only.usda` (130KB, geometry only, NO skeleton)
- `skeletal_tree_path` = `tree_only_skeletal.usda` (143KB, geometry + skeleton)

### USD Composition Failure

When the assembly referenced `tree_only.usda`:

```usd
def Xform "Beech_NaniteAssembly" (
    prepend references = @Beech_tree_0000_tree_only.usda@</Tree>  # ❌ No skeleton in this file
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    prepend rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>  # ❌ Path doesn't exist after composition
}
```

After USD composition, the path `</Beech_NaniteAssembly/SkelRoot/Skeleton>` didn't exist because:

1. Referenced file (`tree_only.usda`) contains NO skeleton structure
2. Only has `def Mesh "Mesh"` - pure geometry
3. Skeleton relationship points to non-existent path

## The Fix

Changed line 3569 in `src/growpy/io/blender_export.py`:

```python
skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,  # ✅ FIX: Points to tree_only_skeletal.usda (has skeleton)
    output_path=skeletal_nanite_path,
    species_name=species_name,
    twig_usd_paths=static_twig_paths,  # Static twigs (geometry only) - CORRECT
    use_skeletal_mesh=True,
    skeleton_source_usd=skeletal_tree_path,
    twig_placement_source_usd=temp_tree_path,
)
```

## USD File Structure Verification

### ✅ CORRECT: tree_only_skeletal.usda (143KB)

```usd
def Xform "Tree"
{
    def Material "BarkMaterial" { ... }
    
    def SkelRoot "SkelRoot" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        def Skeleton "Skeleton"
        {
            uniform matrix4d[] bindTransforms = [...]
            uniform token[] joints = ["Root", "Joint_0", ...]
            uniform matrix4d[] restTransforms = [...]
            custom rel skel:animationSource = </Tree/SkelRoot/Animation>
        }
        
        def SkelAnimation "Animation" { ... }
        
        def Mesh "Mesh" (
            prepend apiSchemas = ["MaterialBindingAPI", "SkelBindingAPI"]
        )
        {
            int[] primvars:skel:jointIndices = [...]
            float[] primvars:skel:jointWeights = [...]
            rel skel:skeleton = </Tree/SkelRoot/Skeleton>
        }
    }
}
```

### ✅ CORRECT: Twig Files (Static Meshes, No Skeleton)

```usd
def Xform "root"
{
    def Xform "europeanbeech_var_a_mount"
    {
        def Xform "BeechTwigA"
        {
            def Mesh "BeechTwigA" (
                prepend apiSchemas = ["MaterialBindingAPI"]  # NO SkelBindingAPI
            )
            {
                # Pure geometry - no skeleton, no joint indices, no joint weights
                int[] faceVertexCounts = [...]
                int[] faceVertexIndices = [...]
                point3f[] points = [...]
                normal3f[] normals = [...]
                texCoord2f[] primvars:st = [...]
            }
        }
    }
}
```

**Twigs are CORRECTLY static meshes** per Unreal schema:

- No SkelRoot, no Skeleton, no SkelAnimation
- Pure geometry with materials
- Will be bound to assembly skeleton via `NaniteAssemblySkelBindingAPI` in assembly file
- Used by PointInstancer for twig placement

### ✅ CORRECT: Assembly Structure After Fix

```usd
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    prepend references = @Beech_tree_0000_tree_only_skeletal.usda@</Tree>  # ✅ References skeletal file
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    prepend rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/SkelRoot/Skeleton>  # ✅ Path exists after composition
    
    def Scope "TwigPrototypes"
    {
        def Xform "twiglong" (
            prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            instanceable = true
            prepend references = @europeanbeech_var_a.usda@  # Static twig
        )
        {
            token visibility = "invisible"
        }
    }
    
    def PointInstancer "TwigInstances" (
        prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    )
    {
        uniform token[] primvars:unreal:naniteAssembly:bindJoints = [...]  # Binds static twigs to skeleton
        int[] protoIndices = [...]
        point3f[] positions = [...]
    }
}
```

## Schema Compliance Verification

### NaniteAssemblyRootAPI Requirements

Per `data/unreal_schema/unreal/schema.usda`:

```usd
class "NaniteAssemblyRootAPI" (
    customData = {
        token[] apiSchemaCanOnlyApplyTo = ["Xform"]
    }
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh" (
        allowedTokens = [ "staticMesh", "skeletalMesh" ]  # ✅ Skeletal is EXPLICITLY supported
    )

    rel unreal:naniteAssembly:skeleton (
        doc = """The skeleton to consider as the base of this Nanite assembly root
        (Valid for meshType=skeletalMesh only, and must be a descendant prim)."""  # ✅ Must exist after composition
    )
}
```

**Key Points**:

1. `skeletalMesh` is explicitly supported by schema
2. Skeleton relationship MUST point to descendant prim
3. "Descendant prim" means after USD composition/reference resolution
4. If referenced file has no skeleton, the path won't exist

### Why Twigs Don't Need Skeletons

Per schema design:

- `NaniteAssemblySkelBindingAPI` binds prims to skeleton
- PointInstancer instances (static twigs) are bound via `bindJoints`
- Skeleton is in assembly root, controls both branch and twig transforms
- Static twigs gain animation from skeleton binding, don't need their own skeletons

## Expected Behavior After Fix

1. **USD Composition**:
   - Assembly references skeletal tree file
   - Tree prim includes SkelRoot/Skeleton/SkelAnimation hierarchy
   - Skeleton relationship points to existing path

2. **Unreal Import**:
   - Recognizes skeletal Nanite Assembly
   - Creates skeletal mesh from branch geometry
   - Imports skeleton with correct bone hierarchy
   - Binds twig instances to skeleton joints
   - Nanite Assembly appears in Content Browser

3. **Runtime**:
   - Tree and twigs animate together
   - Skeleton drives all geometry
   - Nanite virtualized geometry for efficient rendering

## Testing

To verify the fix:

1. **Generate Test Assembly**:

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/test.csv --output-dir data/output/skeletal_test_fixed --quality high --formats usda
```

2. **Verify Assembly Structure**:

```bash
# Check assembly references skeletal file
grep "prepend references" data/output/skeletal_test_fixed/*/USD/*_NaniteAssembly_skeletal.usda

# Should show: @..._tree_only_skeletal.usda@</Tree>
# NOT: @..._tree_only.usda@</Tree>
```

3. **Import in Unreal Engine 5.7+**:
   - Import the skeletal Nanite Assembly USD file
   - Verify Nanite Assembly is created
   - Check skeleton is recognized
   - Confirm twigs are included with skeletal binding

## Related Files

- **Fixed**: `src/growpy/io/blender_export.py` (line 3569)
- **Schema**: `data/unreal_schema/unreal/schema.usda`
- **Assembly Generator**: `src/growpy/io/unreal_nanite_assembly.py`
- **USD Files**:
  - `*_tree_only.usda` (static geometry only)
  - `*_tree_only_skeletal.usda` (geometry + skeleton)
  - `*_NaniteAssembly_skeletal.usda` (skeletal assembly)
  - Twig files: `*.usda` (static meshes)

## Summary

This was a **critical file reference bug** where the skeletal Nanite Assembly was unknowingly referencing a file that didn't contain the skeleton structure it was trying to reference. The fix ensures USD composition can resolve the skeleton relationship path, allowing Unreal to properly recognize and import skeletal Nanite Assemblies.

The twig files are correctly structured as static meshes per schema requirements - they don't need skeletons because they're bound to the assembly's skeleton via `NaniteAssemblySkelBindingAPI`.
