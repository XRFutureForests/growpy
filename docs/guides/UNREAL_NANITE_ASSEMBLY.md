# Unreal Engine Nanite Assembly Export

This guide explains how to export Grove trees as Nanite Assemblies for Unreal Engine 5.7+.

## What is a Nanite Assembly?

Nanite Assemblies are a new USD format introduced in Unreal Engine 5.7 that provides:

- **Optimized Import**: Direct USD import without intermediate conversions
- **Memory Efficiency**: Shared mesh data across instances
- **GPU Acceleration**: Native GPU instancing and streaming
- **Nanite Support**: Full virtualized geometry support
- **Foliage Optimization**: Preserve Area enabled for leaf meshes

## Schema Overview

The Nanite Assembly uses Unreal's custom USD schemas:

```usda
def Xform "TreeName_NaniteAssembly" (
    apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh"

    def Xform "TreeMesh" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        references = @tree.usda@
    )
    {
    }

    def Scope "TwigPrototypes" {
        def Xform "twiglong" (
            apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            instanceable = true
            references = @twig_apical.usda@
        )
        {
        }
    }

    def PointInstancer "TwigInstances" {
        rel prototypes = [</TreeName_NaniteAssembly/TwigPrototypes/twiglong>]
        point3f[] positions = [...]
        quath[] orientations = [...]  # Half-precision quaternions
        float3[] scales = [...]
        int[] protoIndices = [...]
    }
}
```

## Export Workflow

### 1. Standard USD Export (Default)

By default, the export creates TWO USD files:

```bash
python src/growpy/cli/export_tree_usda.py "European Beech"
```

**Outputs:**
- `european_beech_tree.usda` - Standard USD (works in Blender, Maya, Houdini)
- `european_beech_tree_NaniteAssembly.usda` - Nanite Assembly (optimized for Unreal)

### 2. Disable Nanite Assembly

If you only want the standard USD:

```bash
python src/growpy/cli/export_tree_usda.py "European Beech" --no-nanite-assembly
```

### 3. Batch Export All Species

```bash
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --resolution 24
```

This creates both versions for all configured species.

## File Structure Comparison

### Standard USD (Blender-Compatible)

```
output/
├── european_beech_tree.usda           # Complete tree with twigs
├── european_beech_tree_tree_only.usda # Base tree only
└── twigs/
    ├── beech_apical.usda
    └── beech_lateral.usda
```

**Structure:**
- Single stage with all geometry inline or referenced
- Standard USD prims (Xform, Mesh, PointInstancer)
- No Unreal-specific schemas
- Works in all DCC applications

### Nanite Assembly USD (Unreal-Optimized)

```
output/
├── european_beech_tree_NaniteAssembly.usda  # Import this in Unreal!
├── european_beech_tree_tree_only.usda       # Referenced by assembly
└── twigs/
    ├── beech_apical.usda
    └── beech_lateral.usda
```

**Structure:**
- Root with `NaniteAssemblyRootAPI` schema
- Child meshes with `NaniteAssemblyExternalRefAPI`
- PointInstancer for twig instances
- Unreal-specific attributes for optimal import

## Usage in Unreal Engine

### Importing Nanite Assembly

1. **Enable USD Plugin**
   - Edit → Plugins → USD Importer
   - Restart Unreal Engine

2. **Import Settings**
   - Content Browser → Import
   - Select `*_NaniteAssembly.usda` file
   - USD Import Options:
     - ✓ Enable Nanite
     - ✓ Keep Instances
     - ✓ Import Materials
     - ✓ Import Geometry

3. **Verify Import**
   - Check Nanite is enabled on Static Mesh
   - Verify twig instances are present
   - Check material assignments

### Setting USD Schema Path (Important!)

For Unreal to recognize the custom schemas, you need to set the PXR_PLUGINPATH_NAME environment variable:

**Method 1: Environment Variable**
```bash
export PXR_PLUGINPATH_NAME="/path/to/the-grove/data/unreal_schema"
```

**Method 2: Unreal Project Settings**
1. Edit → Project Settings
2. Plugins → USD
3. Additional Schema Paths:
   - Add: `/path/to/the-grove/data/unreal_schema`

**Method 3: System-Wide (macOS)**
```bash
# Add to ~/.zshrc or ~/.bash_profile
export PXR_PLUGINPATH_NAME="/Users/maximiliansperlich/Developer/the-grove/data/unreal_schema"
```

**Method 4: Per-Session (when running Unreal)**
```bash
PXR_PLUGINPATH_NAME="/path/to/the-grove/data/unreal_schema" /path/to/UnrealEngine
```

### Verify Schema Loading

In Unreal's Output Log, look for:
```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

If you don't see these messages, the schema path is not set correctly.

## Testing Both Versions

### Test in Blender

```bash
# Import standard USD (NOT the Nanite Assembly)
blender --python -c "
import bpy
bpy.ops.wm.usd_import(filepath='european_beech_tree.usda')
"
```

The standard USD should load with:
- Tree mesh with proper geometry
- Twig instances visible
- All materials assigned

### Test in Unreal Engine

1. Import the Nanite Assembly file: `european_beech_tree_NaniteAssembly.usda`
2. Check Static Mesh details:
   - Nanite: Enabled
   - LODs: Auto-generated
   - Twig instances: Present as child components

### Test in USD View (Optional)

```bash
usdview european_beech_tree_NaniteAssembly.usda
```

Check:
- Root prim has `NaniteAssemblyRootAPI` in API schemas
- Tree mesh references external USD
- Twig prototypes are instanceable
- PointInstancer has correct counts

## Advantages of Nanite Assembly

### For Trees
- **Automatic LODs**: Nanite generates virtualized LODs
- **Memory Efficiency**: Single tree mesh shared across instances
- **Streaming**: Automatic level streaming and data loading
- **GPU Culling**: Per-triangle culling for optimal performance

### For Twigs/Foliage
- **Preserve Area**: Prevents foliage from thinning at distance
- **Instancing**: PointInstancer provides GPU-driven instancing
- **Memory**: Millions of twig instances with minimal overhead
- **Visibility**: Proper occlusion culling per instance

## Performance Comparison

| Metric | Standard Import | Nanite Assembly |
|--------|----------------|-----------------|
| Import Time | 10-30 seconds | 5-15 seconds |
| Memory Usage | Higher | Lower (shared data) |
| Runtime FPS | Lower | Higher (Nanite) |
| LOD Generation | Manual | Automatic |
| Twig Instances | Limited | Unlimited |
| Streaming | Manual setup | Automatic |

## API Reference

### Python Functions

#### `export_grove_tree_as_usda_native()`

```python
from growpy.io.blender_export import export_grove_tree_as_usda_native

success = export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("tree.usda"),
    species_name="European Beech",
    twig_usd_paths=twig_map,
    include_twigs=True,
    create_nanite_assembly=True,  # Creates *_NaniteAssembly.usda
)
```

#### `create_nanite_assembly_usd()`

```python
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd

success = create_nanite_assembly_usd(
    tree_usd_path=Path("tree.usda"),
    output_path=Path("tree_NaniteAssembly.usda"),
    species_name="European Beech",
    twig_usd_paths=twig_map,
    use_skeletal_mesh=False,
)
```

## Troubleshooting

### Schema Not Recognized in Unreal

**Problem**: Import works but Nanite Assembly features missing

**Solution**: Set PXR_PLUGINPATH_NAME environment variable (see above)

### Twigs Not Appearing

**Problem**: Tree imports but twigs are invisible

**Checks**:
1. Verify twig USD files exist and are referenced correctly
2. Check PointInstancer has positions/orientations data
3. Verify prototype references are valid paths
4. Check Unreal import settings have "Keep Instances" enabled

### Missing Nanite

**Problem**: Mesh imports as regular static mesh

**Checks**:
1. Verify Unreal Engine is 5.7 or later
2. Check "Enable Nanite" is checked on import
3. Verify mesh has sufficient triangle count (Nanite requires >10k tris)
4. Check Output Log for Nanite warnings

### Standard USD Works, Nanite Assembly Doesn't

**Problem**: Standard USD imports fine in Blender but Nanite Assembly fails in Unreal

**Solution**: This is expected! The Nanite Assembly uses Unreal-specific schemas:
- Import `*_NaniteAssembly.usda` in Unreal Engine only
- Import `*.usda` (without _NaniteAssembly) in Blender/Maya/Houdini

### Performance Issues

**Problem**: Frame rate drops with many tree instances

**Checks**:
1. Verify Nanite is enabled on meshes
2. Check foliage has `unrealNanitePreserveArea = true`
3. Enable GPU Scene in Unreal Project Settings
4. Verify World Partition streaming is active

## References

- [Unreal USD Documentation](https://docs.unrealengine.com/5.7/en-US/USD/)
- [Nanite Assemblies Video](https://www.youtube.com/watch?v=-ZGWblVF8Qk)
- [Nanite Assemblies Tutorial](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)
- [USD PointInstancer Spec](https://openusd.org/dev/api/class_usd_geom_point_instancer.html)

## Examples

See:
- `src/growpy/cli/export_tree_usda.py` - Single tree export with Nanite Assembly
- `src/growpy/cli/generate_species_library.py` - Batch export all species
- `src/growpy/io/unreal_nanite_assembly.py` - Nanite Assembly creation code
