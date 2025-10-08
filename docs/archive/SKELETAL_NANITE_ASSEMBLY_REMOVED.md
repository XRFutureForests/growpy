# Skeletal Nanite Assembly Removal - 2025-01-08

## Issue

Skeletal Nanite Assemblies (USD files referencing FBX files) were failing to import into Unreal Engine with errors:

- "Could not open asset @...fbx@ for reference"
- "Cannot determine file format for FBX"
- "Failed to resolve Skeleton prim for Nanite Assembly root"

## Root Cause

**USD cannot reference FBX files directly.** This is a fundamental limitation of the USD format - USD can only reference other USD files, not binary formats like FBX.

## Solution

Removed skeletal Nanite Assembly creation entirely. The workflow for skeletal meshes is now:

### For Static Meshes (USD)

✅ **Use Nanite Assembly USD** - Import `*_NaniteAssembly.usda`

- Tree mesh: USD reference
- Twig instances: USD references via PointInstancer
- Full Nanite support with instancing

### For Skeletal Meshes (FBX with animation)

✅ **Import FBX directly into Unreal** - Import `*.fbx` file

- Contains skeleton/armature for animation
- Materials and textures embedded
- Import using Unreal's FBX importer (not USD importer)
- No Nanite Assembly needed - FBX is a complete skeletal mesh asset

## Changes Made

### 1. Removed Skeletal Assembly Creation

File: `src/growpy/io/blender_export.py` (lines 1773-1780)

**Before:**

```python
# Create FBX-based skeletal mesh Nanite Assembly
if create_nanite_assembly and usd_dir and "usd" in variation_info["files"]:
    # ... 80 lines of code trying to create skeletal assembly with FBX refs
```

**After:**

```python
# Note: Skeletal mesh Nanite Assemblies are not created because:
# - USD cannot reference FBX files directly
# - For skeletal meshes with animation, import FBX directly into Unreal
# - Nanite Assemblies are designed for static mesh instancing with USD files
```

### 2. Added User Guidance

When FBX files are exported, users now see:

```
✓ Exported FBX with skeleton: Oak_var1.fbx
ℹ️  FBX Skeletal Mesh: Import Oak_var1.fbx directly into Unreal
   (Skeletal Nanite Assemblies not supported - USD cannot reference FBX)
```

## Export Output Structure

### Before (Incorrect)

```
Oak/
├── FBX/
│   └── Oak_var1.fbx                          # Skeletal mesh
└── USD/
    ├── Oak_var1.usda                         # Static mesh
    ├── Oak_var1_NaniteAssembly.usda         # ✅ Works (USD refs)
    └── Oak_var1_NaniteAssembly_Skeletal.usda # ❌ FAILED (FBX refs)
```

### After (Correct)

```
Oak/
├── FBX/
│   └── Oak_var1.fbx                          # Import directly for skeletal
└── USD/
    ├── Oak_var1.usda                         # Static mesh
    └── Oak_var1_NaniteAssembly.usda         # ✅ Works (USD refs only)
```

## Import Workflow in Unreal Engine

### Static Mesh Trees (Recommended for most cases)

1. Use USD importer
2. Import `*_NaniteAssembly.usda`
3. Nanite automatically enabled
4. Twigs instanced efficiently

### Skeletal Mesh Trees (For animation)

1. Use FBX importer (standard Unreal import)
2. Import `*.fbx` file
3. Skeleton/armature included
4. Configure skeletal mesh settings as needed
5. No Nanite Assembly needed

## Technical Details

### Why USD Can't Reference FBX

- USD is a scene description format based on ASCII/binary USD files
- USD references work through file path resolution to other USD files
- FBX is a proprietary binary format (Autodesk)
- USD has no plugin/loader for FBX format
- Unreal's USD importer doesn't convert FBX to USD on-the-fly

### Nanite Assembly Purpose

Nanite Assemblies are designed for:

- **Static mesh instancing** (trees, rocks, buildings)
- **USD-based workflows** (DCC → USD → Unreal)
- **Efficient memory usage** via PointInstancer
- **Level assembly** with external references

They are NOT designed for:

- Skeletal mesh animation
- FBX-based workflows
- Runtime animation systems

## Migration Guide

If you have existing `*_NaniteAssembly_Skeletal.usda` files:

1. **Delete them** - They don't work and never will
2. **Import FBX directly** instead:
   - File → Import
   - Select `.fbx` file
   - Use FBX Import Options (not USD)
3. **For static trees**, use `*_NaniteAssembly.usda` (USD only)

## Benefits

✅ **Clearer workflow** - No confusion about which file to import
✅ **Fewer errors** - No broken FBX references in USD
✅ **Better documentation** - Clear guidance on static vs skeletal
✅ **Correct by design** - Only creates assemblies that actually work

## Related Documentation

- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import instructions
- `docs/growpy/NANITE_ASSEMBLY_GUIDE.md` - Nanite Assembly overview
- `docs/growpy/COORDINATE_SYSTEMS.md` - Coordinate transformations

## Export Changes

- **Scale**: Changed from 100x to 1:1 (meters) for both FBX and USD
- **Skeletal Assembly**: No longer generated
- **Static Assembly**: Still generated with USD references only
