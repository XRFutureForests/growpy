# USD Stage Metadata Fix - 2025-01-07

## Problem

When comparing Oak tree USD files in Blender:

- **Tree-only USD** (`Oak_var1_tree_only.usda`): Loaded correctly sized with tree pointing toward +Z
- **Assembly USD** (`Oak_var1.usda`): Tree was much smaller and mesh pointed toward -Y while twigs placed toward -Z

## Root Cause

The assembly USD files were missing critical stage metadata that was present in the tree-only USD:

- `metersPerUnit = 1`
- `upAxis = "Z"`

Without this metadata, Blender (and other DCC tools) would use default values which caused:

- Incorrect scale interpretation (centimeters vs meters)
- Wrong coordinate system orientation (Y-up default vs Z-up)

## Solution

Added stage metadata to USD stage creation in four locations:

### 1. Tree Assembly Creation (`src/growpy/io/twig_placement.py`)

```python
# Create USD stage
stage = Usd.Stage.CreateNew(str(output_path))

# Set stage metadata to match tree-only USD (Z-up, meters)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# Create root
root_prim = stage.DefinePrim("/TreeAssembly", "Xform")
stage.SetDefaultPrim(root_prim)
```

### 2. Nanite Assembly Creation (`src/growpy/io/unreal_nanite_assembly.py`)

```python
# Create new stage
stage = Usd.Stage.CreateNew(str(output_path))

# Set stage metadata to match tree USD (Z-up, meters)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# Root Xform with NaniteAssemblyRootAPI
assembly_name = f"{species_name.replace(' ', '_')}_NaniteAssembly"
root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
stage.SetDefaultPrim(root_prim)
```

### 3. Twig Nanite Assembly (`src/growpy/cli/convert_twigs.py`)

```python
# Create new stage
stage = Usd.Stage.CreateNew(str(nanite_path))

# Set stage metadata to match twig USD (Z-up, meters)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# Root Xform with NaniteAssemblyRootAPI
assembly_name = f"{twig_name.replace(' ', '_')}_NaniteAssembly"
root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
stage.SetDefaultPrim(root_prim)
```

### 4. Blender FBX Assembly (`src/growpy/io/blender_export.py`)

```python
# Create new stage
stage = Usd.Stage.CreateNew(str(output_assembly_path))

# Set stage metadata (Z-up, meters)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# Define root prim with NaniteAssemblyRootAPI
root_prim = stage.DefinePrim(f"/{species_name}_Assembly", "Xform")
stage.SetDefaultPrim(root_prim)
```

## Result

All generated USD files now include proper stage metadata:

```usd
#usda 1.0
(
    defaultPrim = "TreeAssembly"
    metersPerUnit = 1
    upAxis = "Z"
)
```

This ensures:

- Consistent scale interpretation across all DCC tools (Blender, Unreal, Houdini)
- Correct coordinate system (Z-up) matching The Grove's native export
- Tree and twig assemblies load with proper orientation and scale
- Nanite assemblies reference correctly scaled tree/twig assets

## Verification

Generated test files with corrected metadata:

- `Oak_var1_test.usda` - Tree assembly with metadata
- `Oak_var1_test_NaniteAssembly.usda` - Nanite assembly with metadata
- `Oak_var1_fixed.usda` - Final verified assembly
- `Oak_var1_fixed_NaniteAssembly.usda` - Final verified Nanite assembly

All files now load correctly in Blender with proper scale and orientation.

## Technical Notes

- The Grove 2.2's native `model_to_usda_string()` automatically includes these metadata fields
- Referenced tree-only USD files already had correct metadata from Grove export
- Assembly USD files need to explicitly set metadata since they're created programmatically
- USD format requires consistent metadata across all stages in a reference hierarchy
- Unreal Engine 5.7+ Nanite Assemblies respect USD stage metadata for import scale/orientation
