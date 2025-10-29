# Skeletal Mesh Import Troubleshooting Guide

## Critical Unreal Engine Settings

According to the Hullabulla video, these settings are **REQUIRED** for skeletal mesh assemblies to work:

### 1. Console Variables (DefaultEngine.ini)

Add these to your `Config/DefaultEngine.ini`:

```ini
[SystemSettings]
r.Nanite.AllowAssemblies=1

[/Script/InterchangeEngine.InterchangeManager]
Interchange.FeatureFlags.Import.USD=0
```

**Location**: `<YourProject>/Config/DefaultEngine.ini`

### 2. Required Plugins

Enable these plugins in Unreal:
- **USD Core** ✅
- **USD Importer** ✅

**DO NOT** enable:
- USD Interchange ❌

Go to `Edit → Plugins`, search for "USD", and verify the correct plugins are enabled.

### 3. Environment Variables (for Houdini/Blender)

The Unreal USD schema must be accessible:

**Path**: `<UnrealInstall>/Engine/Plugins/Importers/USDImporter/Content/Resources/Schemas`

Add to PATH or reference in your DCC tool.

## Required USD Structure

### Assembly Structure (nanite_assembly.usda)

```usda
def Xform "TreeName_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
    kind = "assembly"
)
{
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </TreeName_NaniteAssembly/TreeMesh/TreeSkel>

    def SkelRoot "TreeMesh" (
        prepend references = @./tree_name_tree.usda@</Tree>
    )
    {
        # EMPTY - preserves references from tree.usda
    }
}
```

**Key points**:
1. Root must be `Xform` (not SkelRoot)
2. Must have `kind = "assembly"`
3. Must have both `NaniteAssemblyRootAPI` and `GeomModelAPI`
4. TreeMesh must be `SkelRoot` (for skeletal)
5. TreeMesh must be **EMPTY** (just the reference)

### Tree Structure (tree.usda)

```usda
def SkelRoot "Tree" (
    prepend apiSchemas = ["SkelBindingAPI"]
)
{
    rel skel:skeleton = </Tree/TreeSkel>

    def Skeleton "TreeSkel"
    {
        uniform matrix4d[] bindTransforms = [...]
        uniform token[] joints = [...]
        uniform matrix4d[] restTransforms = [...]
    }

    def Mesh "TreeMesh" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        rel skel:skeleton = <../TreeSkel>
        int[] primvars:skel:jointIndices = [...] (
            elementSize = 2
            interpolation = "vertex"
        )
        float[] primvars:skel:jointWeights = [...] (
            elementSize = 2
            interpolation = "vertex"
        )
    }
}
```

**Key points**:
1. SkelRoot must have `skel:skeleton` relationship
2. Skeleton must have `joints`, `bindTransforms`, `restTransforms`
3. Mesh must have `skel:skeleton` relationship
4. Mesh **MUST** have `primvars:skel:jointIndices` and `primvars:skel:jointWeights`
5. Both must have `elementSize = 2` and `interpolation = "vertex"`

## Verification Checklist

### Project Settings
- [ ] `r.Nanite.AllowAssemblies=1` in DefaultEngine.ini
- [ ] `Interchange.FeatureFlags.Import.USD=0` in DefaultEngine.ini
- [ ] USD Core plugin enabled
- [ ] USD Importer plugin enabled
- [ ] USD Interchange plugin **disabled**

### Assembly USD
- [ ] Root prim is `Xform`
- [ ] Root has `apiSchemas = ["NaniteAssemblyRootAPI", "GeomModelAPI"]`
- [ ] Root has `kind = "assembly"`
- [ ] Root has `unreal:naniteAssembly:meshType = "skeletalMesh"`
- [ ] Root has `unreal:naniteAssembly:skeleton` relationship pointing to TreeSkel
- [ ] TreeMesh is `SkelRoot` type
- [ ] TreeMesh contains only a reference (no overrides)

### Tree USD
- [ ] /Tree is `SkelRoot` type
- [ ] /Tree has `skel:skeleton` relationship
- [ ] /Tree/TreeSkel exists and is `Skeleton` type
- [ ] TreeSkel has `joints` array
- [ ] TreeSkel has `bindTransforms` array
- [ ] TreeSkel has `restTransforms` array
- [ ] /Tree/TreeMesh is `Mesh` type
- [ ] TreeMesh has `skel:skeleton` relationship
- [ ] TreeMesh has `primvars:skel:jointIndices` with correct data
- [ ] TreeMesh has `primvars:skel:jointWeights` with correct data
- [ ] Both primvars have `elementSize = 2` and `interpolation = "vertex"`

## Common Issues

### Issue: Tree imports as static mesh

**Causes**:
1. Missing console variables
2. Wrong plugins enabled
3. Missing or incorrect skeleton structure
4. Missing skinning data (jointIndices/jointWeights)
5. Incorrect USD prim types

**Solution**: Verify ALL items in checklist above

### Issue: "Unable to import skeletal mesh"

**Cause**: Missing skinning data

**Solution**: Ensure tree USD has proper `primvars:skel:jointIndices` and `primvars:skel:jointWeights`

### Issue: Mesh deformations when moving bones

**Cause**: Using spatial proximity instead of topological mapping

**Solution**: Ensure using branch ID mapping (already implemented in latest code)

## Testing Your Export

### Quick Test Script (Python in Unreal)

```python
import unreal

# Check if assembly recognition is enabled
value = unreal.SystemLibrary.execute_console_command(
    None,
    "r.Nanite.AllowAssemblies"
)
print(f"r.Nanite.AllowAssemblies: {value}")
```

### Manual Verification

1. Export your tree with `use_skeletal_mesh=True`
2. Open the tree USD file (`<name>_tree.usda`) in a text editor
3. Search for "jointIndices" - should exist
4. Search for "jointWeights" - should exist
5. Search for "SkelRoot" - should exist at /Tree
6. Search for "Skeleton" - should exist at /Tree/TreeSkel

## Reference Files

Working examples provided in:
- `data/skeletal_nanite_assembly_reference/nanite_assembly.usda`
- `data/skeletal_nanite_assembly_reference/tree.usda`
- `data/skeletal_nanite_assembly_reference/twig.usda`

Compare your exported files to these references using a text editor or USD viewer.
