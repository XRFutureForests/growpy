# Nanite Assembly Schema Compliance Update

**Date:** 2025-01-13  
**Status:** Complete  
**Impact:** Critical for Unreal Engine 5.7+ compatibility

## Summary

Updated GrowPy's Nanite Assembly export to ensure proper compliance with Unreal Engine's USD schema requirements. This enables reliable detection of both static and skeletal mesh Nanite Assemblies in Unreal Engine.

## Key Changes

### 1. Uniform Variability for Schema Attributes

**Problem:** Attribute variability was not explicitly set, causing schema validation issues in Unreal.

**Solution:** Applied `variability=Sdf.VariabilityUniform` to critical attributes:

```python
# Before
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token,
    custom=False,
).Set(mesh_type)

# After
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token,
    custom=False,
    variability=Sdf.VariabilityUniform,  # CRITICAL for schema compliance
).Set(mesh_type)
```

### 2. Skeleton Relationship Custom Flag

**Problem:** Skeleton relationship was not properly marked as custom, causing Unreal to ignore it.

**Solution:** Added `custom=True` parameter:

```python
# Before
skeleton_rel = root_prim.CreateRelationship(
    "unreal:naniteAssembly:skeleton"
)

# After
skeleton_rel = root_prim.CreateRelationship(
    "unreal:naniteAssembly:skeleton",
    custom=True,  # Required for custom schema relationships
)
```

### 3. Skeletal Binding Primvars

**Problem:** Binding primvars lacked proper variability specification.

**Solution:** Ensured uniform variability for binding attributes:

```python
bind_joints_attr = instancer_prim.CreateAttribute(
    "primvars:unreal:naniteAssembly:bindJoints",
    Sdf.ValueTypeNames.TokenArray,
    custom=False,
    variability=Sdf.VariabilityUniform,  # One value per point instancer
)
bind_joints_attr.Set(bind_joints)
```

### 4. Validation Tool

Created comprehensive validation utility to verify Nanite Assembly compliance:

**Features:**

- Checks NaniteAssemblyRootAPI application
- Validates meshType attribute
- Verifies skeleton relationship for skeletal meshes
- Checks prototype structure
- Validates skeletal binding on PointInstancer
- Provides detailed error and warning messages

**Usage:**

> **Note:** The CLI tool has been removed. Use the Python function instead:

```python
from growpy.io import validate_nanite_assembly
from pathlib import Path

result = validate_nanite_assembly(Path("tree_assembly.usda"))
if result["valid"]:
    print(f"✓ Valid {result['mesh_type']} assembly")
```

### 5. Comprehensive Documentation

Created detailed documentation covering:

- Static vs skeletal mesh assemblies
- Schema requirements and structure
- Export workflow
- Import to Unreal Engine
- Troubleshooting guide
- Best practices

**Location:** `docs/growpy/unreal-nanite-assembly.md`

## Technical Details

### Schema Requirements Addressed

#### Static Mesh Assemblies

✓ NaniteAssemblyRootAPI with uniform meshType="staticMesh"  
✓ NaniteAssemblyExternalRefAPI on prototypes  
✓ USD references (not FBX)  
✓ Instanceable prototypes  
✓ PointInstancer for twig instances  

#### Skeletal Mesh Assemblies

✓ NaniteAssemblyRootAPI with uniform meshType="skeletalMesh"  
✓ Custom skeleton relationship to UsdSkel.Skeleton  
✓ Embedded skeleton structure (SkelRoot/Skeleton/Animation)  
✓ NaniteAssemblySkelBindingAPI on PointInstancer  
✓ Uniform primvars for joint binding  
✓ Proper joint name references  

### Files Modified

1. **`src/growpy/io/unreal_nanite_assembly.py`**
   - Fixed attribute variability
   - Fixed skeleton relationship
   - Fixed skeletal binding primvars
   - Added `validate_nanite_assembly()` function

2. **`src/growpy/io/__init__.py`**
   - Exported validation function
   - Added NANITE_VALIDATION_AVAILABLE flag

3. ~~**`src/growpy/cli/validate_nanite_assembly.py`**~~ (REMOVED)
   - Validation now available via Python function only
   - Use `validate_nanite_assembly()` from `growpy.io`

4. **`docs/growpy/unreal-nanite-assembly.md`** (NEW)
   - Complete documentation
   - Schema reference
   - Troubleshooting guide

## Testing Recommendations

### Validation Tests

> **Note:** CLI tool has been removed. Use the Python function:

```python
from growpy.io import validate_nanite_assembly
from pathlib import Path

# Validate static mesh assembly
result = validate_nanite_assembly(
    Path("data/output/embedded_skeleton_test222/Beech/USD/Beech_tree_0000_NaniteAssembly_static.usda")
)

# Validate skeletal mesh assembly
result = validate_nanite_assembly(
    Path("data/output/embedded_skeleton_test222/Beech/USD/Beech_tree_0000_NaniteAssembly_skeletal.usda")
)
```

### Unreal Engine Import Tests

1. **Static Assembly:**
   - Drag into level → Should create USD Stage Actor
   - Check Nanite is enabled on tree mesh
   - Verify twig instances

2. **Skeletal Assembly:**
   - Import with skeletal animation enabled
   - Check skeleton is imported
   - Verify twig instances follow skeleton
   - Test animation playback

## Breaking Changes

None. This is a schema compliance fix that improves existing functionality without changing the API.

## Migration Guide

No migration needed. Existing code will continue to work, but newly exported files will be more compliant with Unreal's schema.

To regenerate existing Nanite Assembly files with proper schema:

```python
from growpy.io import create_nanite_assembly_usd

# Regenerate with fixed schema
create_nanite_assembly_usd(
    tree_usd_path=existing_tree_usd,
    output_path=existing_assembly_path,
    species_name="YourSpecies",
    twig_usd_paths=your_twig_paths,
    use_skeletal_mesh=True,  # or False for static
)
```

## Known Issues

None currently identified.

## Future Enhancements

1. **Auto-detect mesh type** from USD structure (presence of skeleton)
2. **Twig LOD support** for distance-based detail reduction
3. **Material parameter binding** for Nanite assembly materials
4. **Animation export** for skeletal assemblies
5. **Per-twig skeletal binding** (currently uses nearest joint)

## References

- [Unreal USD Schema](data/unreal_schema/schema.usda)
- [Nanite Import Example](data/unreal_schema/using_nanite.py)
- [Working Assembly Example](data/output/embedded_skeleton_test222/Beech/USD/Beech_tree_0000_NaniteAssembly_skeletal.usda)

## Verification Checklist

- [x] Uniform variability applied to meshType
- [x] Custom flag on skeleton relationship
- [x] Uniform variability on skeletal binding primvars
- [x] Validation tool created
- [x] Documentation written
- [x] Code comments updated
- [x] Module exports updated
- [ ] Integration tests with Unreal Engine (requires manual testing)

## Conclusion

These changes ensure GrowPy generates USD files that Unreal Engine 5.7+ can reliably recognize as Nanite Assemblies. The validation tool helps catch schema compliance issues before import, reducing iteration time.

The implementation follows the official Unreal USD schema closely, matching the structure of working examples while maintaining GrowPy's flexible export pipeline.
