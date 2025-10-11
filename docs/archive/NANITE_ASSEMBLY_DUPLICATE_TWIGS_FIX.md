# Nanite Assembly Structure Fix

**Date:** 2025-01-09  
**Status:** Fixed

## Problem History

### Initial Issue: Duplicate Twigs

The Nanite Assembly USD files were showing duplicate twigs at the tree origin in Unreal Engine, but not when opening the base USD file in Blender.

**Root Cause:** The assembly was referencing `Oak_var1.usda` (which includes twigs) AND extracting/re-adding those same twigs.

### Second Issue: Assembly Not Recognized

After fixing duplicates by not passing twig paths, Unreal Engine stopped recognizing the file as a Nanite Assembly.

**Root Cause:** Unreal expects explicit component structure in the assembly, not implicit through references.

## Final Solution

Modified `src/growpy/io/blender_export.py` at line 2669 to use **tree-only USD** (without twigs) and **explicitly add twigs** in the assembly:

```python
# Final (correct):
nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,  # Tree mesh only, no twigs
    output_path=nanite_path,
    species_name=species_name,
    twig_usd_paths=twig_usd_paths if include_twigs else None,  # Add twigs explicitly
    use_skeletal_mesh=False,
)
```

## Result

The static mesh Nanite Assembly USD now has the proper explicit structure:

```usd
def Xform "Oak_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "staticMesh"
    
    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @Oak_var1_tree_only_skeletal.usda@  # Tree only
    ) {}
    
    def Scope "TwigPrototypes"  # Explicit twig definitions
    {
        def Xform "twiglong" (
            prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            instanceable = true
            prepend references = @europeanoak_apical.usda@
        ) {}
        ...
    }
    
    def PointInstancer "TwigInstances"  # Explicit placement
    {
        positions = [(0.029, 0.010, 0.999), ...]
        orientations = [...]
        protoIndices = [2, 2, 2, 2, 3]
        prototypes = [...]
    }
}
```

## Key Architectural Points

1. **Tree-Only Reference**: The assembly references `*_tree_only_skeletal.usda` (tree mesh with materials, no twigs)
2. **Explicit Components**: All components (tree, twigs, instances) are explicitly defined in the assembly
3. **NaniteAssemblyExternalRefAPI**: Applied to both tree and twig prototypes for proper Unreal recognition
4. **PointInstancer**: Twig placement data extracted from base mesh and added explicitly to assembly

## File Structure

After export, each species has:

- `Oak_var1_tree_only.usda` - Base tree mesh with materials
- `Oak_var1_tree_only_skeletal.usda` - Skeletal tree mesh (used by assembly)
- `Oak_var1.usda` - Complete assembly with twigs (legacy format)
- `Oak_var1_NaniteAssembly.usda` - **Import this in Unreal** (proper Nanite Assembly)
- `Oak_var1_skeletal.usda` - Skeletal assembly with skeletal twigs
- `Oak_var1_NaniteAssembly_skeletal.usda` - Skeletal Nanite Assembly

## Files Modified

- `src/growpy/io/blender_export.py` (line 2669-2677)

## Testing

Verified with:

```bash
python ./src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda
```

**Result:** Proper Nanite Assembly USD with explicit tree and twig components, recognized by Unreal Engine 5.7+
