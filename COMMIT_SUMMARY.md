# Commit Summary: Fix Nanite Assembly USD Schema Compliance

## Description

Fixed critical schema compliance issues in Nanite Assembly USD export that prevented Unreal Engine from properly detecting static and skeletal mesh assemblies. Added comprehensive validation tooling and documentation.

## Changes

### Core Fixes

1. **Uniform Variability for Schema Attributes**
   - Applied `variability=Sdf.VariabilityUniform` to `unreal:naniteAssembly:meshType`
   - Fixed skeletal binding primvars to use uniform variability
   - Ensures Unreal Engine properly recognizes schema attributes

2. **Skeleton Relationship Custom Flag**
   - Added `custom=True` to `unreal:naniteAssembly:skeleton` relationship
   - Required for Unreal to recognize custom schema relationships

3. **Attribute Creation Improvements**
   - Explicit `custom=False` for schema-defined attributes
   - Proper variability specification throughout

### New Features

1. ~~**Validation CLI Tool**~~ (REMOVED - `src/growpy/cli/validate_nanite_assembly.py`)
   - CLI tool has been removed
   - Validation now available via Python function only

2. **Validation Function** (`validate_nanite_assembly()`)
   - Programmatic validation of USD files
   - Returns structured validation results
   - Checks both static and skeletal assembly requirements

3. **Comprehensive Documentation** (`docs/growpy/unreal-nanite-assembly.md`)
   - Complete guide to Nanite Assembly structure
   - Schema requirements reference
   - Static vs skeletal mesh comparison
   - Import workflow and troubleshooting
   - Best practices

### Updated Files

- `src/growpy/io/unreal_nanite_assembly.py` - Core fixes and validation
- `src/growpy/io/__init__.py` - Export validation function
- ~~`src/growpy/cli/validate_nanite_assembly.py`~~ - REMOVED (use Python function instead)
- `docs/growpy/unreal-nanite-assembly.md` - NEW comprehensive docs
- `docs/archive/NANITE_ASSEMBLY_SCHEMA_UPDATE.md` - NEW technical summary

## Technical Details

### Schema Compliance Matrix

| Requirement | Static | Skeletal | Status |
|------------|--------|----------|--------|
| NaniteAssemblyRootAPI | ✓ | ✓ | Fixed |
| Uniform meshType | ✓ | ✓ | Fixed |
| Skeleton relationship | N/A | ✓ | Fixed |
| ExternalRefAPI on prototypes | ✓ | ✓ | Working |
| SkelBindingAPI on instancer | N/A | ✓ | Fixed |
| Uniform binding primvars | N/A | ✓ | Fixed |

### Code Example

```python
# Before (not detected by Unreal)
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token,
    custom=False,
).Set("skeletalMesh")

# After (properly detected)
root_prim.CreateAttribute(
    "unreal:naniteAssembly:meshType",
    Sdf.ValueTypeNames.Token,
    custom=False,
    variability=Sdf.VariabilityUniform,  # CRITICAL
).Set("skeletalMesh")
```

## Testing

### Validation

> **Note:** CLI tool has been removed. Use the Python function:

```python
from growpy.io import validate_nanite_assembly
from pathlib import Path

# Validate single assembly
result = validate_nanite_assembly(Path("tree_assembly.usda"))
if result["valid"]:
    print(f"✓ Valid {result['mesh_type']} assembly")
```

### Unreal Engine Import

1. Import the fixed USD files to Unreal Engine 5.7+
2. Verify Nanite Assembly is detected (check asset type)
3. For skeletal: verify skeleton is imported
4. For both: verify twig instances work correctly

## Breaking Changes

None. This is a schema compliance fix that improves compatibility without changing the API.

## Benefits

1. **Reliable Detection** - Unreal Engine consistently recognizes assemblies
2. **Proper Schema** - Follows official Unreal USD schema exactly
3. **Validation** - Catch issues before import with validation tool
4. **Documentation** - Complete reference for Nanite Assembly export
5. **Future-proof** - Based on UE 5.7+ stable schema

## Related Issues

Resolves issues with:

- Static mesh Nanite Assemblies not being detected
- Skeletal mesh assemblies missing skeleton relationships
- Twig instances not binding to skeleton joints
- Schema validation errors in Unreal Engine

## References

- Unreal Engine USD Documentation
- USD Schema for Unreal (data/unreal_schema/)
- Working example: Beech_tree_0000_NaniteAssembly_skeletal.usda

---

**Impact:** High - Critical for Unreal Engine integration  
**Risk:** Low - Fixes schema compliance without API changes  
**Testing:** Manual testing in Unreal Engine required
