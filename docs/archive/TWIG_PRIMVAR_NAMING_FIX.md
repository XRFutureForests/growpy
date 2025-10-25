# Twig Primvar Naming Standardization

## Problem

USD files contained duplicate twig face attributes with inconsistent naming:

- **Snake_case bool[] primvars**: `twig_dead`, `twig_long`, `twig_short`, `twig_upward` (Python-added)
- **PascalCase int[] primvars**: `TwigDead`, `TwigEnd`, `TwigSide`, `TwigUpward` (Grove native)

Both sets contained identical semantic information but with different naming conventions and types.

## Root Cause

Two separate export systems were creating the same data:

1. **Grove 2.2 Native USD Exporter** (`gc.io.model_to_usda_string()`):
   - C++ code that exports PascalCase int[] primvars
   - Already exports in Z-up coordinate system (`upAxis="Z"`)
   - Authoritative source for twig placement data

2. **Python Post-Processing** (`_add_grove_face_attributes_to_usd()`):
   - Historical workaround from when Grove exported Y-up USD without twig attributes
   - Converted Y-up to Z-up coordinates (now redundant)
   - Added snake_case bool[] primvars (now redundant)

## Solution

### 1. Removed Redundant Function Call

**File**: `src/growpy/io/blender_export.py` (line 3130)

Removed the call to `_add_grove_face_attributes_to_usd()` that was creating duplicate primvars.

```python
# BEFORE (line 3127-3131)
# CRITICAL: Add twig face attributes from Grove model to USD
# Grove's native USD export doesn't include custom face attributes
_add_grove_face_attributes_to_usd(temp_tree_path, model)

# AFTER
# NOTE: Grove's native USD export already includes twig face attributes
# as PascalCase primvars (TwigDead, TwigUpward, TwigSide, TwigEnd)
# No need to add duplicate snake_case versions
```

### 2. Deprecated Obsolete Function

**File**: `src/growpy/io/blender_export.py` (line 968)

Marked `_add_grove_face_attributes_to_usd()` as deprecated with warning:

- Function now returns immediately (no-op)
- Added deprecation warning when called
- Original implementation kept for reference but never executed
- Both features (primvar creation + coordinate conversion) are now handled by Grove

### 3. Updated Primvar Reader

**File**: `src/growpy/io/twig_placement.py` (line 468)

Updated to read Grove's PascalCase primvar names with fallback for backward compatibility:

```python
# Grove exports twig primvars with PascalCase names - mapping:
# TwigEnd -> twig_long (end of branch twigs)
# TwigSide -> twig_short (side twigs)
# TwigUpward -> twig_upward (upward twigs)
# TwigDead -> twig_dead (dead twigs)
twig_name_map = {
    "twig_long": "TwigEnd",
    "twig_short": "TwigSide", 
    "twig_upward": "TwigUpward",
    "twig_dead": "TwigDead"
}

# Primary: Use Grove's PascalCase naming
primvar = primvars_api.GetPrimvar(grove_name)

# Fallback 1: Try legacy snake_case name
if not primvar or not primvar.HasValue():
    primvar = primvars_api.GetPrimvar(twig_type)

# Fallback 2: Try gr_ prefix (Blender USD exporter)
if not primvar or not primvar.HasValue():
    primvar = primvars_api.GetPrimvar(f"gr_{twig_type}")
```

## Primvar Name Mapping

| Internal Name | Grove PascalCase | Legacy snake_case | Description |
|--------------|------------------|-------------------|-------------|
| twig_long | `TwigEnd` | twig_long | End of branch twigs |
| twig_short | `TwigSide` | twig_short | Side branch twigs |
| twig_upward | `TwigUpward` | twig_upward | Upward facing twigs |
| twig_dead | `TwigDead` | twig_dead | Dead/bare twigs |

## Coordinate System

Grove 2.2's native USD export uses **Z-up coordinate system** (`upAxis="Z"`):

- Matches Blender and Unreal Engine conventions
- No Y-up to Z-up conversion needed
- Python coordinate transformation is obsolete

## Benefits

1. **No Duplication**: Single source of truth for twig primvars (Grove's native export)
2. **Consistent Naming**: Standardized on Grove's PascalCase convention
3. **Smaller Files**: Removed 4 redundant primvars per USD file
4. **Correct Types**: Uses int[] (Grove native) instead of bool[] (Python-added)
5. **Proper Coordinates**: Z-up from Grove, no conversion needed
6. **Backward Compatible**: Fallback logic preserves old file compatibility

## Testing

After regenerating USD files:

1. Verify only PascalCase primvars appear (`TwigDead`, `TwigUpward`, `TwigSide`, `TwigEnd`)
2. Verify no snake_case duplicates (`twig_dead`, `twig_long`, `twig_short`, `twig_upward`)
3. Verify `upAxis="Z"` in USD files
4. Test twig placement functionality still works correctly
5. Verify backward compatibility with old USD files

## Migration Notes

- **New exports**: Will only have PascalCase primvars (clean)
- **Old files**: Still work due to fallback logic in reader
- **No data loss**: Both naming conventions contained identical data
- **Function deprecated**: `_add_grove_face_attributes_to_usd()` should not be called in new code
