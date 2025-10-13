# Nanite Assembly: Skeletal vs Static Mesh Separation

**Date:** 2025-01-10  
**Issue:** Ensuring Nanite Assemblies correctly use skeletal or static USD references  
**Status:** IMPLEMENTED

## Overview

Nanite Assemblies in Unreal Engine 5.7+ require strict separation between skeletal and static mesh workflows. This document explains the requirements and implementation.

## Unreal Engine Requirements

Based on official documentation:

- <https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine>
- <https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine>

### Skeletal Mesh USD Requirements

1. **UsdSkel Hierarchy**
   - Must have `SkelRoot` prim as container
   - Must have `Skeleton` prim with joint hierarchy
   - Should have `SkelAnimation` prim for animation data
   - Mesh must be bound to skeleton via `UsdSkel.BindingAPI`

2. **Vertex Weights**
   - Must have proper joint influences per vertex
   - Weights should be normalized (sum to 1.0)
   - Maximum 4 influences per vertex recommended

3. **Animation Data**
   - SkelAnimation prim enables proper skeletal mesh recognition
   - Even without animation, the prim should exist for Unreal import

### Static Mesh USD Requirements

1. **No Skeleton Data**
   - Must NOT have `SkelRoot` or `Skeleton` prims
   - No joint weights or bindings
   - Pure geometry mesh only

2. **Simpler Structure**
   - Just `Mesh` prim with geometry
   - Materials and textures
   - No animation or deformation data

## Nanite Assembly Schema

From `data/unreal_schema/schema.usda`:

```usda
class "NaniteAssemblyRootAPI"
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh" (
        allowedTokens = ["staticMesh", "skeletalMesh"]
    )
    rel unreal:naniteAssembly:skeleton
}
```

### Static Mesh Assembly

```usda
def Xform "TreeName_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh"
    
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @./tree_static.usda@
    )
    
    def Scope "TwigPrototypes"
    {
        def Xform "TwigLong" (
            apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            references = @./twig_long_static.usda@
        )
    }
}
```

### Skeletal Mesh Assembly

```usda
def Xform "TreeName_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    rel unreal:naniteAssembly:skeleton = </TreeName_NaniteAssembly/TreeMesh/SkelRoot/Skeleton>
    
    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @./tree_skeletal.usda@  # MUST have embedded skeleton
    )
    
    def Scope "TwigPrototypes"
    {
        def Xform "TwigLong" (
            apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            references = @./twig_long_skeletal.usda@  # MUST have embedded skeleton
        )
    }
}
```

## Implementation

### Export Functions

**Static Nanite Assembly** (`blender_export.py` line ~3265):

```python
# Get static twig paths explicitly
static_twig_paths = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=False
)

nanite_success = create_nanite_assembly_usd(
    tree_usd_path=temp_tree_path,      # Static tree (no skeleton)
    output_path=nanite_path,
    species_name=species_name,
    twig_usd_paths=static_twig_paths,  # Static twigs
    use_skeletal_mesh=False,
)
```

**Skeletal Nanite Assembly** (`blender_export.py` line ~3294):

```python
# Get skeletal twig paths explicitly
skeletal_twig_paths = get_twig_usd_map_for_species(
    species_name, config, prefer_skeletal=True
)

skeletal_nanite_success = create_nanite_assembly_usd(
    tree_usd_path=skeletal_tree_path,     # Skeletal tree with skeleton
    output_path=skeletal_nanite_path,
    species_name=species_name,
    twig_usd_paths=skeletal_twig_paths,   # Skeletal twigs
    use_skeletal_mesh=True,
)
```

### Twig Lookup Function

`get_twig_usd_map_for_species()` with `prefer_skeletal` parameter:

```python
def get_twig_usd_map_for_species(
    species_name: str,
    config: Optional[Any] = None,
    prefer_skeletal: bool = False,
) -> Dict[str, Path]:
```

- `prefer_skeletal=False`: Returns static twigs (e.g., `twig_long.usda`)
- `prefer_skeletal=True`: Returns skeletal twigs (e.g., `twig_long_skeletal.usda`)

**Filtering Logic:**

```python
is_skeletal = "_skeletal" in usd_file.stem

if prefer_skeletal and not is_skeletal:
    # Looking for skeletal, this is static - check for skeletal variant
    skeletal_file = usd_file.parent / f"{usd_file.stem}_skeletal{usd_file.suffix}"
    if skeletal_file.exists():
        twig_usd_map[grove_type] = skeletal_file
        break
    continue
elif not prefer_skeletal and is_skeletal:
    # Looking for static, this is skeletal - skip it
    continue
```

## File Naming Convention

### Static Assets

- `tree_static.usda` or `tree.usda` (without "_skeletal" suffix)
- `twig_long.usda`
- `twig_short.usda`
- Used for: Static Nanite Assembly, non-animated imports

### Skeletal Assets

- `tree_skeletal.usda` (with "_skeletal" suffix)
- `twig_long_skeletal.usda`
- `twig_short_skeletal.usda`
- Used for: Skeletal Nanite Assembly, animated imports

## Export Directory Structure

```
output/
├── FBX/
│   ├── tree.fbx              # Static FBX (direct import)
│   └── tree_skeletal.fbx     # Skeletal FBX (direct import)
├── USD/
│   ├── tree.usda                           # Static tree
│   ├── tree_skeletal.usda                  # Skeletal tree with skeleton
│   ├── tree_NaniteAssembly.usda           # Static Nanite Assembly
│   └── tree_NaniteAssembly_skeletal.usda  # Skeletal Nanite Assembly
└── Twigs/
    ├── twig_long.usda           # Static twig
    ├── twig_long_skeletal.usda  # Skeletal twig
    ├── twig_short.usda
    └── twig_short_skeletal.usda
```

## Testing Checklist

### Static Nanite Assembly Import

- [ ] Imports as static mesh in Unreal
- [ ] Tree mesh visible
- [ ] Twig instances visible
- [ ] No skeleton present
- [ ] Nanite enabled
- [ ] Materials applied correctly

### Skeletal Nanite Assembly Import

- [ ] Imports as skeletal mesh in Unreal
- [ ] Tree mesh recognized as skeletal
- [ ] Skeleton present and valid
- [ ] Twig instances visible
- [ ] Twigs recognized as skeletal (if applicable)
- [ ] Animation data accessible
- [ ] Materials applied correctly

### Verification Commands

**Static Assembly:**

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/static_test \
    --quality high \
    --formats usda
```

**Skeletal Assembly:**

```bash
python ./src/growpy/cli/generate_forest.py ./data/input/test.csv \
    --output-dir ./data/output/skeletal_test \
    --quality high \
    --formats usda \
    --include-skeleton
```

## Common Issues

### Issue: Static Nanite Assembly uses skeletal twigs

**Cause:** `prefer_skeletal=False` not specified in twig lookup  
**Solution:** Explicitly call `get_twig_usd_map_for_species(species, config, prefer_skeletal=False)`

### Issue: Skeletal Nanite Assembly uses static tree

**Cause:** Using `temp_tree_path` instead of `skeletal_tree_path`  
**Solution:** Use `skeletal_tree_path` from `export_tree_as_usd_with_skeleton()` result

### Issue: Unreal doesn't recognize as skeletal mesh

**Cause:** Missing UsdSkel hierarchy or SkelAnimation prim  
**Solution:** Ensure USD has proper SkelRoot > Skeleton > SkelAnimation structure

### Issue: Mixed skeletal/static twigs in assembly

**Cause:** Twig lookup finding wrong variants  
**Solution:** Check file naming convention includes "_skeletal" suffix consistently

## References

1. **Unreal Engine Documentation**
   - Skeletal Mesh Assets: <https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine>
   - USD in Unreal: <https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine>

2. **USD Schema Files**
   - `data/unreal_schema/schema.usda` - Unreal's custom schemas
   - `data/unreal_schema/generatedSchema.usda` - Generated schema definitions

3. **Implementation Files**
   - `src/growpy/io/unreal_nanite_assembly.py` - Nanite Assembly creation
   - `src/growpy/io/blender_export.py` - Export functions with skeletal/static logic
   - `src/growpy/config/settings.py` - Twig file lookup

## Conclusion

The separation between skeletal and static meshes is critical for proper Unreal Engine import. The implementation now ensures:

1. Static Nanite Assemblies use only static USD references
2. Skeletal Nanite Assemblies use only skeletal USD references
3. Proper UsdSkel hierarchy in all skeletal USD files
4. Clear file naming convention for asset identification

This matches Unreal Engine's requirements and ensures optimal import workflow.
