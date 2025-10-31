# Twig Reference Fix - Unreal Import Issue

## Problem

When importing skeletal Nanite Assembly USD files into Unreal Engine 5.7+, only the tree mesh and skeleton were imported. The twigs were completely missing, even though:

- Individual twig skeletal meshes imported correctly when tested standalone
- The assembly file structure appeared correct

## Root Cause

**Case mismatch in USD prim references** in `src/growpy/io/usd_builder.py`

The `build_skeletal_nanite_assembly()` function was referencing twigs with lowercase `/twig`:

```python
twig_skelroot.GetReferences().AddReference(twig_ref_path, "/twig")
```

However, the actual twig USDA files use capital `/Twig` as their defaultPrim:

```usda
def SkelRoot "Twig" (
    prepend apiSchemas = ["SkelBindingAPI"]
)
```

**Result**: Unreal couldn't resolve the prim path and silently skipped loading the twig references.

## Solution

Changed line 1636 in `src/growpy/io/usd_builder.py`:

**Before**:

```python
twig_skelroot.GetReferences().AddReference(twig_ref_path, "/twig")
```

**After**:

```python
twig_skelroot.GetReferences().AddReference(twig_ref_path, "/Twig")
```

## Verification

Generated assembly files now correctly reference twigs with `/Twig` (capital T):

```usda
prepend references = @./western_red_cedar_twig_var_a_skeletal.usda@</Twig>
prepend references = @./western_red_cedar_twig_lateral_skeletal.usda@</Twig>
```

## Files Modified

- `src/growpy/io/usd_builder.py` - Line 1636 (in `build_skeletal_nanite_assembly()` function)

## Testing

- Regenerated forest with fixed code: ✓ Passed
- Skeletal validation: ✓ All structures validated successfully
- Assembly file structure: ✓ Correct prim paths now generated

## Next Steps

- Import updated assembly files into Unreal Engine 5.7+ to verify twigs now load correctly
- The twigs should now appear in the scene with proper skeletal binding
