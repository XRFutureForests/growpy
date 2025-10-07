# Unreal Engine USD Schema

This directory contains the Unreal Engine custom USD schemas for Nanite Assemblies and other Unreal-specific features.

## What is this?

Unreal Engine 5.7+ introduced custom USD schemas that enable optimized import workflows. These schemas define special attributes and API schemas that the Unreal USD importer recognizes.

## Schemas Included

### NaniteAssemblyRootAPI
Marks the root of a Nanite Assembly, enabling optimized import for static or skeletal meshes.

### NaniteAssemblyExternalRefAPI
Allows child prims to reference external USD or Unreal assets as part of an assembly.

### NaniteAssemblySkelBindingAPI
Binds meshes or instances to skeleton joints for skeletal mesh assemblies.

### Other APIs
- CollapsingAPI - Control USD prim collapsing on import
- SubdivisionAPI - Control mesh subdivision
- LodSubtreeAPI - Define LOD hierarchies
- LiveLinkAPI - Live Link integration
- ControlRigAPI - Control Rig integration
- GroomAPI - Groom (hair) support
- SparseVolumeTextureAPI - Volume texture support

## Usage

### Setting the Schema Path

For Unreal Engine to recognize these schemas, you must set the `PXR_PLUGINPATH_NAME` environment variable:

**macOS/Linux:**
```bash
export PXR_PLUGINPATH_NAME="/path/to/the-grove/data/unreal_schema"
```

**Windows (PowerShell):**
```powershell
$env:PXR_PLUGINPATH_NAME = "C:\path\to\the-grove\data\unreal_schema"
```

**Windows (Command Prompt):**
```cmd
set PXR_PLUGINPATH_NAME=C:\path\to\the-grove\data\unreal_schema
```

### Permanent Setup

**macOS/Linux:**
Add to `~/.zshrc` or `~/.bash_profile`:
```bash
export PXR_PLUGINPATH_NAME="/Users/yourusername/Developer/the-grove/data/unreal_schema"
```

**Windows:**
1. System Properties → Advanced → Environment Variables
2. Add new System Variable:
   - Name: `PXR_PLUGINPATH_NAME`
   - Value: `C:\path\to\the-grove\data\unreal_schema`

### Verifying Schema is Loaded

When launching Unreal Engine, check the Output Log for:
```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

If you don't see these messages, the schema path is not set correctly.

## Files

- `generatedSchema.usda` - Auto-generated schema definitions
- `plugInfo.json` - Plugin metadata for USD
- `unreal/schema.usda` - Human-readable schema definitions
- `README.md` - This file

## Example Usage in Python

```python
from pxr import Usd, UsdGeom, Sdf

stage = Usd.Stage.CreateNew("tree_assembly.usda")

# Create root with NaniteAssemblyRootAPI
root = stage.DefinePrim("/TreeAssembly", "Xform")
root.SetMetadata("apiSchemas", ["NaniteAssemblyRootAPI"])
root.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token
).Set("staticMesh")

# Child mesh with ExternalRefAPI
tree_mesh = stage.DefinePrim("/TreeAssembly/Tree", "Xform")
tree_mesh.SetMetadata("apiSchemas", ["NaniteAssemblyExternalRefAPI"])
tree_mesh.GetReferences().AddReference("tree.usda")

stage.GetRootLayer().Save()
```

## Grove Integration

The Grove's USD export automatically uses these schemas when `create_nanite_assembly=True`:

```python
from growpy.io.blender_export import export_grove_tree_as_usda_native

export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("tree.usda"),
    species_name="European Beech",
    create_nanite_assembly=True,  # Creates *_NaniteAssembly.usda
)
```

This creates TWO USD files:
1. `tree.usda` - Standard USD (works in all DCCs)
2. `tree_NaniteAssembly.usda` - Unreal-optimized (uses these schemas)

## References

- [Unreal USD Documentation](https://docs.unrealengine.com/5.7/en-US/USD/)
- [USD Schema Definition](https://openusd.org/release/api/class_usd_schema_registry.html)
- [Nanite Assemblies Tutorial](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)

## License

These schema files are provided by Epic Games as part of Unreal Engine. See Unreal Engine licensing terms for usage rights.
