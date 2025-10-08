# USD Skeleton and Materials Enhancement - 2025-01-08

## Summary

Extended the native USD export to include:

1. **UsdSkel skeleton hierarchy** for skeletal animation support
2. **Bark texture materials** (diffuse + normal maps) directly in USD
3. **Skeletal Nanite Assembly** USD files (referencing USD, not FBX)

## Changes Made

### 1. New Function: `_add_skeleton_and_materials_to_usd()`

Location: `src/growpy/io/blender_export.py` (line ~920)

**Purpose**: Enhances Grove's basic USD export with skeleton and materials

**Features**:

- **Skeleton Export**:
  - Converts Grove skeleton to UsdSkel format
  - Creates joint hierarchy from poly_lines
  - Binds mesh to skeleton for animation
  - Supports multiple branches with parent/child relationships

- **Material Export**:
  - Finds bark textures via species lookup
  - Creates UsdPreviewSurface shader
  - Adds diffuse texture (base color)
  - Adds normal map for detail
  - Sets bark-appropriate material properties (roughness: 0.8, metallic: 0.0)
  - Binds material to mesh geometry

### 2. Updated `export_grove_tree_as_usda_native()`

**New Parameters**:

- `include_skeleton: bool = True` - Add skeleton to USD
- `config: Optional[Any] = None` - Config for texture lookup

**New Behavior**:

- Calls `_add_skeleton_and_materials_to_usd()` after base export
- Creates skeletal Nanite Assembly in addition to static assembly
- Both assemblies reference USD files only (no FBX dependencies)

### 3. Skeletal Nanite Assembly Creation

**Files Generated**:

```
Oak/
└── USD/
    ├── Oak_var1.usda                          # Tree with skeleton + materials
    ├── Oak_var1_NaniteAssembly.usda          # Static mesh (as before)
    └── Oak_var1_NaniteAssembly_Skeletal.usda # NEW: Skeletal mesh (USD refs)
```

**Key Difference from Previous Implementation**:

- ❌ Old: Referenced FBX files (failed - USD can't reference FBX)
- ✅ New: References USD files (works - skeleton embedded in USD)

## Export Output Example

```
Exporting Oak as USDA...
  ✓ Exported base tree USD: Oak_var1_tree_only.usda
  Adding skeleton to USD...
    ✓ Added skeleton with 127 joints
    ✓ Bound mesh to skeleton
  Adding bark texture material...
    ✓ Added diffuse texture: EuropeanOak60.jpg
    ✓ Added normal map: EuropeanOak60Normal.jpg
    ✓ Bound material to mesh
  Adding twigs as point instances...
    ✓ Created complete USDA with twigs: Oak_var1.usda

  Creating Unreal Nanite Assembly (USD/Static)...
    ✓ Nanite Assembly USD: Oak_var1_NaniteAssembly.usda
    Import this file in Unreal Engine 5.7+ (static mesh)

  Creating Unreal Nanite Assembly (USD/Skeletal)...
    ✓ Skeletal Nanite Assembly USD: Oak_var1_NaniteAssembly_Skeletal.usda
    Import this file in Unreal Engine 5.7+ (skeletal mesh with animation)
```

## USD Structure

### Tree USD File (with skeleton + materials)

```
#usda 1.0
(
    defaultPrim = "Tree"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "Tree"
{
    def Mesh "Tree"
    {
        # Mesh geometry (from Grove)
        # Twig face attributes
        # Material binding
    }
    
    def Skeleton "Skeleton"  # NEW
    {
        # Joint hierarchy
        # Bind transforms
        # Rest transforms
    }
    
    def Material "BarkMaterial"  # NEW
    {
        def Shader "Shader"
        {
            # UsdPreviewSurface
        }
        def Shader "DiffuseTexture"
        {
            # Bark diffuse texture
        }
        def Shader "NormalTexture"
        {
            # Bark normal map
        }
    }
}
```

### Skeletal Nanite Assembly

```
#usda 1.0
(
    defaultPrim = "Oak_NaniteAssembly"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "Oak_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"  # Changed from static
    rel unreal:naniteAssembly:skeleton = </Oak_NaniteAssembly/Skeleton>

    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @Oak_var1.usda@  # USD reference (not FBX!)
    )
    {
    }

    def Scope "TwigPrototypes" { ... }
    def PointInstancer "TwigInstances" { ... }
}
```

## Import Workflow in Unreal Engine

### Static Mesh Trees (Optimized)

1. Import `*_NaniteAssembly.usda`
2. USD importer loads tree + twigs
3. Nanite enabled automatically
4. Materials with textures ready to use

### Skeletal Mesh Trees (Animation)

1. Import `*_NaniteAssembly_Skeletal.usda`
2. USD importer loads skeletal mesh
3. Skeleton hierarchy imported
4. Ready for animation systems (wind, growth, etc.)
5. Nanite support (experimental in UE 5.x for skeletal meshes)

## Technical Details

### Skeleton Conversion

- **Grove Skeleton Format**:
  - `points`: [(x, y, z), ...] - Joint positions
  - `poly_lines`: [[idx, idx, ...], ...] - Branch chains
  - `location`: (x, y, z) - Root position

- **USD Skeleton Format**:
  - `joints`: [token, ...] - Joint names
  - `bindTransforms`: [matrix4d, ...] - Bind pose
  - `restTransforms`: [matrix4d, ...] - Rest pose
  - Topology via parent indices

- **Conversion Process**:
  1. Create root joint at skeleton location
  2. For each poly_line (branch):
     - Create bone chain from consecutive points
     - Set parent relationships
     - Calculate transform matrices
  3. Bind mesh to skeleton via UsdSkel.BindingAPI

### Material System

- **UsdPreviewSurface**: Standard USD material
- **Texture Handling**:
  - Absolute paths resolved at export time
  - Textures referenced from `data/assets/textures/`
  - Unreal copies textures on import
- **PBR Properties**:
  - Diffuse color from texture
  - Normal map for surface detail
  - Roughness: 0.8 (bark-like)
  - Metallic: 0.0 (non-metallic)

## Benefits

✅ **Complete USD Workflow** - Skeleton and materials in USD (no FBX dependency)
✅ **Skeletal Nanite Assemblies** - Now functional (USD references work)
✅ **Textured Tree Meshes** - Bark materials embedded in USD
✅ **Animation Ready** - Skeleton hierarchy for wind/growth
✅ **Single Format** - USD for everything (static and skeletal)
✅ **DCC Compatible** - USD works in Houdini, Maya, Blender, etc.

## Known Limitations

1. **Skeleton Complexity**: Grove skeletons have many joints (one per branch segment)
   - May need optimization for real-time animation
   - Consider joint reduction for performance-critical cases

2. **Material Textures**: Absolute paths in USD
   - Works for local import
   - May need path remapping for shared assets

3. **Animation Data**: USD contains skeleton, but no animation clips
   - Animation created in Unreal (wind systems, procedural)
   - Not for baked keyframe animation

## Testing

Test the new export:

```bash
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda
```

Expected output:

- Tree USD with skeleton + materials
- Static Nanite Assembly
- Skeletal Nanite Assembly (NEW)

Import in Unreal:

1. Static: `Oak_var1_NaniteAssembly.usda` → Static Mesh
2. Skeletal: `Oak_var1_NaniteAssembly_Skeletal.usda` → Skeletal Mesh

## Related Documentation

- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import workflow
- `docs/growpy/NANITE_ASSEMBLY_GUIDE.md` - Nanite Assembly details
- `docs/archive/SKELETAL_NANITE_ASSEMBLY_REMOVED.md` - Previous FBX issue

## Future Enhancements

1. **Joint Optimization**: Reduce skeleton complexity for performance
2. **LOD Skeletons**: Different skeleton detail levels
3. **Animation Clips**: Export basic wind animation
4. **Material Variants**: Season-based material switching
5. **Texture Baking**: Bake vertex colors for additional detail
