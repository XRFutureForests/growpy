# Nanite Assembly USD Type Error - Fixed

## Problem

When creating Nanite Assembly USD files for twigs, the following error occurred:

```
Warning: Could not create Nanite Assembly: Invalid value '['NaniteAssemblyRootAPI']' 
(type '__1::vector<VtValue, __1::allocator<VtValue>>') for key 'apiSchemas'. 
Expected type 'SdfListOp<TfToken>'
```

## Root Cause

The `SetMetadata("apiSchemas", ...)` calls were passing Python lists directly:

```python
# INCORRECT - Python list
root_prim.SetMetadata("apiSchemas", ["NaniteAssemblyRootAPI"])
```

USD expects `Sdf.TokenListOp` objects, not Python lists, for the `apiSchemas` metadata field.

## Solution

Use `Sdf.TokenListOp()` with `prependedItems` property:

```python
# CORRECT - Sdf.TokenListOp
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)
```

## Files Fixed

### 1. `src/growpy/cli/convert_twigs.py`

Fixed `create_twig_nanite_assembly()` function:

```python
# Root prim - NaniteAssemblyRootAPI
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# Child prim - NaniteAssemblyExternalRefAPI
twig_api_schemas = Sdf.TokenListOp()
twig_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
twig_prim.SetMetadata("apiSchemas", twig_api_schemas)
```

### 2. `src/growpy/io/unreal_nanite_assembly.py`

Fixed `create_nanite_assembly_usd()` function with three `apiSchemas` locations:

```python
# Root prim
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# Tree prim
tree_api_schemas = Sdf.TokenListOp()
tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
tree_prim.SetMetadata("apiSchemas", tree_api_schemas)

# Prototype prims (in loop)
proto_api_schemas = Sdf.TokenListOp()
proto_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
proto_prim.SetMetadata("apiSchemas", proto_api_schemas)
```

## Verification

### Test Command

```bash
conda activate the-grove
python src/growpy/cli/convert_twigs.py data/assets/twigs/PinOakTwig --formats usda
```

### Expected Output

```
Creating Nanite Assemblies...
  ✓ pinoak_apical_NaniteAssembly.usda
  ✓ pinoak_lateral_NaniteAssembly.usda
  ✓ pinoak_dead_var_d_NaniteAssembly.usda
  ✓ pinoak_upward_var_d_NaniteAssembly.usda
```

### Verify File Format

```bash
head -15 data/assets/twigs/PinOakTwig/pinoak_apical_NaniteAssembly.usda
```

Should show:

```usda
#usda 1.0
(
    defaultPrim = "pinoak_apical_NaniteAssembly"
)

def Xform "pinoak_apical_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "staticMesh"

    def Xform "TwigMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @./pinoak_apical.usda@
    )
```

The key indicator is `prepend apiSchemas = [...]` which shows USD correctly formatted the metadata.

## USD Python API Details

### TokenListOp Structure

`Sdf.TokenListOp` is a USD data structure that represents list operations:

- **`prependedItems`** - Items added to the beginning (most common for apiSchemas)
- **`appendedItems`** - Items added to the end
- **`deletedItems`** - Items to remove
- **`explicitItems`** - Complete replacement list

For API schemas, we use `prependedItems` to match Unreal's schema composition.

### Why Not Python Lists?

USD's metadata system is strongly typed. The `apiSchemas` field specifically requires `SdfListOp<TfToken>`:

- **TfToken** - Interned string type for performance
- **SdfListOp** - List operation container supporting composition
- **Python list** - Generic Python type, not compatible

While USD Python bindings convert many types automatically, `apiSchemas` metadata must be a proper list operation object.

## Related Files Updated

Both files that create Nanite Assembly USD now use the correct API:

1. **Twig Conversion**: `src/growpy/cli/convert_twigs.py` (individual twigs)
2. **Tree Export**: `src/growpy/io/unreal_nanite_assembly.py` (full trees)

All Nanite Assembly creation now follows the same pattern for consistency.

## Testing Status

✅ **Pin Oak Twigs** - Successfully created 4 Nanite Assemblies  
✅ **File Format** - Correct `prepend apiSchemas = [...]` syntax  
✅ **No Errors** - All type warnings resolved  

## Next Steps

1. **Test Full Conversion**: Run on all twig directories

   ```bash
   python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda
   ```

2. **Test Tree Export**: Verify trees also create correct Nanite Assemblies

   ```bash
   python src/growpy/cli/generate_species_library.py
   ```

3. **Unreal Import**: Test import in Unreal Engine to verify schema compatibility

## References

- **USD TokenListOp Docs**: <https://openusd.org/dev/api/class_sdf_list_op.html>
- **Unreal Nanite Assembly**: `data/unreal_schema/generatedSchema.usda`
- **API Schema Composition**: <https://openusd.org/dev/api/class_usd_api_schema_base.html>

---

**Fixed:** 2025-01-07  
**Files Modified:** `convert_twigs.py`, `unreal_nanite_assembly.py`  
**Issue:** USD type error for apiSchemas metadata  
**Solution:** Use `Sdf.TokenListOp()` instead of Python lists
