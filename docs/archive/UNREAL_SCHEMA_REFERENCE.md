# Unreal Schema Reference in Nanite Assemblies

## Overview

Nanite Assembly USD files now properly reference the Unreal Engine schema definition to ensure correct import behavior in Unreal Engine 5.7+.

## What Changed

### Before

USD files applied Unreal API schemas (`NaniteAssemblyRootAPI`, `NaniteAssemblyExternalRefAPI`) without referencing the schema definition:

```usda
#usda 1.0
(
    defaultPrim = "Beech_NaniteAssembly"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
```

### After

USD files now include a `subLayers` reference to the Unreal schema definition:

```usda
#usda 1.0
(
    subLayers = [
        @/absolute/path/to/data/unreal_schema/generatedSchema.usda@
    ]
    defaultPrim = "Beech_NaniteAssembly"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
```

## Why This Matters

The `subLayers` reference ensures:

1. **Schema Validation**: Unreal Engine can validate the API schema usage
2. **Correct Import**: Proper recognition of Nanite Assembly attributes
3. **Type Safety**: Attribute types are properly defined (tokens, relationships, etc.)
4. **Documentation**: Schema includes documentation for each attribute

## Schema Files

The Unreal schema is located at:

```
data/unreal_schema/
├── generatedSchema.usda    # Generated schema (used in sublayers)
└── unreal/
    └── schema.usda         # Source schema definition
```

## Implementation

The schema reference is added in two places:

1. **`src/growpy/io/unreal_nanite_assembly.py`**
   - Function: `create_nanite_assembly_usd()`
   - Creates standalone Nanite Assembly files

2. **`src/growpy/io/blender_export.py`**
   - Function: `_create_nanite_assembly_usd()`
   - Creates Nanite Assembly files during Blender export

Both functions now include:

```python
# Reference Unreal schema for Nanite Assembly API schemas
schema_path = Path(__file__).parent.parent.parent / "data" / "unreal_schema" / "generatedSchema.usda"
if schema_path.exists():
    stage.GetRootLayer().subLayerPaths.append(str(schema_path.resolve()))
else:
    print(f"  Warning: Unreal schema not found at {schema_path}")
```

## Supported Schemas

The referenced schema defines these API schemas:

- **`NaniteAssemblyRootAPI`**: Applied to root Xform
  - `unreal:naniteAssembly:meshType` (token): "staticMesh" or "skeletalMesh"
  - `unreal:naniteAssembly:skeleton` (rel): Skeleton reference for skeletal meshes

- **`NaniteAssemblyExternalRefAPI`**: Applied to mesh references
  - `unreal:naniteAssembly:meshAssetPath` (token): Package path to mesh asset

- **`NaniteAssemblySkelBindingAPI`**: Applied to mesh instances
  - `primvars:unreal:naniteAssembly:bindJoints` (token[]): Joint names/paths
  - `primvars:unreal:naniteAssembly:bindJointWeights` (float[]): Joint weights

## Verification

To verify the schema reference is working:

1. Generate a new forest with Nanite assemblies:

   ```bash
   python ./src/growpy/cli/generate_forest.py input.csv --create-nanite-assembly
   ```

2. Check the generated USD file header for `subLayers`:

   ```bash
   head -20 data/output/*/USD/*_NaniteAssembly.usda
   ```

3. Look for this section at the top:

   ```usda
   (
       subLayers = [
           @/path/to/generatedSchema.usda@
       ]
       ...
   )
   ```

## Troubleshooting

### Warning: "Unreal schema not found"

- **Cause**: The `generatedSchema.usda` file is missing
- **Solution**: Ensure `data/unreal_schema/generatedSchema.usda` exists
- **Impact**: Nanite Assembly may still work but without proper schema validation

### Import Issues in Unreal Engine

- **Cause**: Old USD files without schema reference
- **Solution**: Regenerate USD files using the updated export
- **Workaround**: Manually add `subLayers` reference to existing files

## References

- Unreal Engine Documentation: [USD Schemas](https://docs.unrealengine.com/5.7/en-US/usd-schemas-in-unreal-engine/)
- Nanite Assemblies Tutorial: [YouTube Video](https://www.youtube.com/watch?v=-ZGWblVF8Qk)
- ArtStation Tutorial: [Nanite Assemblies Guide](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)

---

**Date**: January 2025  
**Status**: ✅ Implemented  
**Version**: 1.0
