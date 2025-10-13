# Unreal Engine Nanite Assembly Support

GrowPy supports exporting trees as Unreal Engine 5.7+ Nanite Assemblies, enabling efficient rendering of high-polygon tree meshes with Nanite technology.

## Overview

Nanite Assemblies allow you to combine multiple mesh assets into a single, instanced structure that Unreal Engine can render efficiently. GrowPy generates USD files following Unreal's Nanite Assembly schema for both static and skeletal meshes.

## Key Differences: Static vs Skeletal

### Static Mesh Assemblies

Static mesh assemblies are best for:

- Trees without animation
- Background foliage
- Maximum performance
- Simple integration

**Structure:**

```
TreeName_NaniteAssembly (Xform)
├── NaniteAssemblyRootAPI (meshType="staticMesh")
├── TreeMesh (Xform with NaniteAssemblyExternalRefAPI)
│   └── Reference to static tree USD
├── TwigPrototypes (Scope)
│   ├── twigtype1 (Xform with NaniteAssemblyExternalRefAPI)
│   │   └── Reference to static twig USD
│   └── twigtype2 (...)
└── TwigInstances (PointInstancer)
```

### Skeletal Mesh Assemblies

Skeletal mesh assemblies enable:

- Wind animation
- Growth animation
- Dynamic movement
- More complex setup

**Structure:**

```
TreeName_NaniteAssembly (Xform)
├── NaniteAssemblyRootAPI (meshType="skeletalMesh")
├── unreal:naniteAssembly:skeleton → /TreeName_NaniteAssembly/SkelRoot/Skeleton
├── SkelRoot (from referenced skeletal tree)
│   ├── Skeleton (with joints, bindTransforms)
│   ├── Animation (SkelAnimation)
│   └── Mesh (skinned to skeleton)
├── TwigPrototypes (Scope)
│   ├── twigtype1 (Xform with NaniteAssemblyExternalRefAPI)
│   │   └── Reference to static twig USD
│   └── twigtype2 (...)
└── TwigInstances (PointInstancer with NaniteAssemblySkelBindingAPI)
    ├── primvars:unreal:naniteAssembly:bindJoints
    └── primvars:unreal:naniteAssembly:bindJointWeights
```

## Critical Schema Requirements

### 1. NaniteAssemblyRootAPI

Must be applied to the root Xform with:

```usd
def Xform "TreeName_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh"  # or "skeletalMesh"
}
```

**Key Points:**

- `unreal:naniteAssembly:meshType` must be **uniform** variability
- Valid values: `"staticMesh"` or `"skeletalMesh"`

### 2. Skeleton Relationship (Skeletal Only)

For skeletal meshes, specify the skeleton path:

```usd
custom rel unreal:naniteAssembly:skeleton
prepend rel unreal:naniteAssembly:skeleton = </TreeName_NaniteAssembly/SkelRoot/Skeleton>
```

**Key Points:**

- Relationship must point to a valid UsdSkel.Skeleton prim
- Skeleton should be part of the assembly (via reference or direct embedding)

### 3. NaniteAssemblyExternalRefAPI

Apply to mesh prototypes for external references:

```usd
def Xform "TreeMesh" (
    prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    instanceable = true
    prepend references = @./tree_mesh.usda@
)
{
    token visibility = "invisible"  # Prototypes should be invisible
}
```

**Key Points:**

- Only works with **USD references** (.usd, .usda, .usdc)
- FBX references are not supported by Nanite Assembly
- Mark as `instanceable = true` for memory efficiency
- Set `visibility = "invisible"` for prototypes

### 4. NaniteAssemblySkelBindingAPI (Skeletal Only)

Bind instanced meshes to skeleton joints:

```usd
def PointInstancer "TwigInstances" (
    prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
)
{
    uniform token[] primvars:unreal:naniteAssembly:bindJoints = ["Joint_1", "Joint_2", ...]
    int primvars:unreal:naniteAssembly:bindJoints:elementSize = 1
    uniform float[] primvars:unreal:naniteAssembly:bindJointWeights = [1, 1, ...]
}
```

**Key Points:**

- `bindJoints` and `bindJointWeights` must be **uniform** variability
- `elementSize = 1` means one joint per instance
- Joint names must match skeleton joint tokens

## Using GrowPy for Nanite Assembly Export

### Export Static Mesh Assembly

```python
from growpy.io import create_nanite_assembly_usd

success = create_nanite_assembly_usd(
    tree_usd_path=Path("tree_static.usda"),
    output_path=Path("output/TreeName_NaniteAssembly.usda"),
    species_name="Oak",
    twig_usd_paths={
        "twiglong": Path("twigs/oak_long.usda"),
        "twigshort": Path("twigs/oak_short.usda"),
    },
    use_skeletal_mesh=False,
)
```

### Export Skeletal Mesh Assembly

```python
success = create_nanite_assembly_usd(
    tree_usd_path=Path("tree_skeletal.usda"),  # Must have embedded skeleton
    output_path=Path("output/TreeName_NaniteAssembly_skeletal.usda"),
    species_name="Oak",
    twig_usd_paths={
        "twiglong": Path("twigs/oak_long.usda"),
        "twigshort": Path("twigs/oak_short.usda"),
    },
    use_skeletal_mesh=True,
)
```

**Important:**

- For skeletal assemblies, `tree_usd_path` must point to a USD with:
  - `SkelRoot` prim
  - `Skeleton` prim with joints and bind transforms
  - `Mesh` prim with skeletal binding

## Validation

Validate your Nanite Assembly files before importing to Unreal:

```bash
python src/growpy/cli/validate_nanite_assembly.py output/TreeName_NaniteAssembly.usda
```

Or validate an entire directory:

```bash
python src/growpy/cli/validate_nanite_assembly.py output/USD/
```

The validator checks:

- ✓ NaniteAssemblyRootAPI is applied
- ✓ meshType attribute is present and valid
- ✓ Skeleton relationship (for skeletal meshes)
- ✓ Prototypes with NaniteAssemblyExternalRefAPI
- ✓ PointInstancer skeletal binding (for skeletal meshes)

## Importing to Unreal Engine

### Method 1: USD Stage Actor (Recommended)

1. In Unreal Editor, drag the `.usda` file into the level
2. A USD Stage Actor will be created
3. Set Nanite triangle threshold (default: 2000)
4. The assembly will be automatically recognized

### Method 2: Import as Asset

1. Content Browser → Import
2. Select the `.usda` file
3. In import options:
   - Enable "Import Actors"
   - Enable "Import Geometry"
   - Enable "Import Skeletal Animations" (for skeletal meshes)
   - Set Nanite Triangle Threshold (default: 2000)
4. Click Import

### Nanite Triangle Threshold

The threshold determines which meshes use Nanite:

- Meshes with **more triangles** than threshold → Nanite enabled
- Meshes with **fewer triangles** → Standard rendering

**Recommended values:**

- Trees: 2000-5000 triangles
- Twigs: 500-1000 triangles (usually below threshold)

You can override the threshold per-prim using:

```usd
uniform token unrealNanite = "enable"  # Force Nanite
uniform token unrealNanite = "disable"  # Disable Nanite
```

## Troubleshooting

### Static Mesh Assembly Not Recognized

**Symptoms:**

- Unreal imports as separate meshes instead of assembly
- No Nanite applied

**Solutions:**

1. Validate with `validate_nanite_assembly.py`
2. Check `meshType` is "staticMesh" with uniform variability
3. Ensure prototypes use USD references (not FBX)
4. Verify NaniteAssemblyRootAPI is applied

### Skeletal Mesh Assembly Not Working

**Symptoms:**

- No animation or skeleton
- Twigs don't follow skeleton
- Import errors

**Solutions:**

1. Validate skeleton structure in source USD
2. Check skeleton relationship points to valid Skeleton prim
3. Verify `meshType` is "skeletalMesh"
4. Ensure NaniteAssemblySkelBindingAPI is on PointInstancer
5. Check joint names in bindJoints match skeleton joints

### Twigs Not Instancing

**Symptoms:**

- Twigs appear multiple times as unique meshes
- High memory usage

**Solutions:**

1. Ensure prototypes are marked `instanceable = true`
2. Check NaniteAssemblyExternalRefAPI is applied
3. Verify PointInstancer has valid prototype relationships
4. Use USD references (not payload or sublayer)

### Performance Issues

**Symptoms:**

- Slow import or rendering
- High memory usage

**Solutions:**

1. Lower Nanite triangle threshold
2. Reduce twig instance counts
3. Use simpler twig meshes for distant LODs
4. Enable Nanite for tree mesh but not twigs
5. Check for duplicate geometry (not instanced)

## Best Practices

### File Organization

```
project/
├── trees/
│   ├── Oak_tree_static.usda
│   ├── Oak_tree_skeletal.usda
│   └── Oak_NaniteAssembly.usda
├── twigs/
│   ├── oak_long.usda
│   ├── oak_short.usda
│   └── oak_dead.usda
└── textures/
    ├── Oak_bark_diffuse.jpg
    └── Oak_bark_normal.jpg
```

### Naming Conventions

- Assembly: `{Species}_NaniteAssembly.usda` or `{Species}_NaniteAssembly_skeletal.usda`
- Tree mesh: `{Species}_tree_static.usda` or `{Species}_tree_skeletal.usda`
- Twigs: `{species}_{variation}.usda` (lowercase)

### Coordinate Systems

- USD uses Z-up by default (matches Blender)
- Unreal uses Z-up
- No coordinate conversion needed

### Texture Paths

Use relative paths in USD:

```usd
asset inputs:file = @./textures/Oak_bark.jpg@
```

This ensures textures are found when moving files.

## Advanced: Manual Schema Application

If you need to manually apply schemas in your own USD files:

```python
from pxr import Sdf, Usd

stage = Usd.Stage.Open("tree.usda")
root_prim = stage.GetDefaultPrim()

# Apply NaniteAssemblyRootAPI
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# Set mesh type
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token,
    custom=False,
    variability=Sdf.VariabilityUniform,
).Set("staticMesh")

# For skeletal: add skeleton relationship
skeleton_rel = root_prim.CreateRelationship(
    "unreal:naniteAssembly:skeleton",
    custom=True,
)
skeleton_rel.AddTarget("/TreeName_NaniteAssembly/SkelRoot/Skeleton")

stage.Save()
```

## References

- [Unreal Engine USD Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine)
- [Unreal Engine Skeletal Mesh Assets](https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine)
- [Nanite Assemblies Tutorial](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)
- [USD Schema for Unreal](data/unreal_schema/)

## See Also

- [Export Pipeline](export-pipeline.md) - Complete tree export workflow
- [Twig Placement](twig-placement.md) - How twigs are positioned
- [Coordinate Systems](coordinate-systems.md) - Understanding coordinate transformations
