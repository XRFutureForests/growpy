# FBX-Based Nanite Assembly Support

## Overview

The Grove now creates **two Nanite Assembly variants** when exporting both USD and FBX formats:

1. **Static Mesh Assembly** (`*_NaniteAssembly.usda`) - References USD files
2. **Skeletal Mesh Assembly** (`*_NaniteAssembly_Skeletal.usda`) - References FBX files

This allows you to choose between static meshes (USD) for better performance or skeletal meshes (FBX) for animation support in Unreal Engine.

## Why Two Assemblies?

### Static Mesh Assembly (USD-based)
- **Purpose**: High-performance static foliage
- **Format**: References `.usda` files
- **Mesh Type**: `staticMesh`
- **Use Case**: Non-animated background trees, forests, dense foliage
- **Advantages**:
  - Better Nanite compression
  - Lower memory footprint
  - Faster rendering
  - Optimized for static scenes

### Skeletal Mesh Assembly (FBX-based)
- **Purpose**: Animated/deformable trees
- **Format**: References `.fbx` files
- **Mesh Type**: `skeletalMesh`
- **Use Case**: Wind animation, growth animation, interactive trees
- **Advantages**:
  - Supports skeletal animation
  - Compatible with Control Rigs
  - Vertex animation ready
  - Wind system integration

## Export Command

To generate both assemblies, export with both formats:

```bash
python src/growpy/cli/generate_forest.py input.csv --formats usda fbx
```

## Output Files

For each tree variation, you'll get:

```
forest/
├── USD/
│   ├── Beech_var1.usda                          # Tree mesh (static)
│   ├── Beech_var1_tree_only.usda                # Tree without twigs
│   ├── Beech_var1_NaniteAssembly.usda          # STATIC MESH ASSEMBLY
│   └── Beech_var1_NaniteAssembly_Skeletal.usda # SKELETAL MESH ASSEMBLY
└── FBX/
    └── Beech_var1.fbx                           # Tree with skeleton
```

## Nanite Assembly Structure

### Static Mesh Assembly
```usd
#usda 1.0
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "staticMesh"
    
    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @Beech_var1.usda@  # USD reference
    )
    
    def PointInstancer "TwigInstances"
    {
        # Twig instances with USD prototypes
    }
}
```

### Skeletal Mesh Assembly
```usd
#usda 1.0
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    token unreal:naniteAssembly:meshType = "skeletalMesh"
    
    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        prepend references = @../FBX/Beech_var1.fbx@  # FBX reference
    )
    
    def PointInstancer "TwigInstances"
    {
        # Twig instances (can use FBX or USD prototypes)
    }
}
```

## Importing into Unreal Engine 5.7+

### Static Mesh Workflow

1. **Import Assembly**:
   - Drag `Beech_var1_NaniteAssembly.usda` into Content Browser
   - USD importer recognizes Nanite Assembly schema
   - Imports as Blueprint with Static Mesh components

2. **Use in Level**:
   - Place blueprint instances in level
   - Nanite automatically handles LOD
   - Use for background forests, dense vegetation

3. **PCG/Foliage Tool**:
   - Add to Foliage Type palette
   - Paint with Foliage Mode
   - Use in PCG graphs for procedural placement

### Skeletal Mesh Workflow

1. **Import Assembly**:
   - Drag `Beech_var1_NaniteAssembly_Skeletal.usda` into Content Browser
   - Imports FBX with skeleton/bones
   - Creates Skeletal Mesh asset

2. **Setup Animation**:
   - Open Skeletal Mesh
   - Add Animation Blueprint
   - Configure Control Rig for wind/growth

3. **Wind Animation**:
   - Connect to Unreal's Wind system
   - Use vertex animation for leaves
   - Blend between static and animated states

## Technical Details

### Mesh Type Differences

| Feature | Static Mesh | Skeletal Mesh |
|---------|------------|---------------|
| Nanite Support | Full | Full |
| Animation | No | Yes |
| Performance | Faster | Moderate |
| Memory | Lower | Higher |
| Bones/Skeleton | No | Yes |
| Wind System | Vertex WPO | Skeletal animation |
| Use Case | Background | Foreground/Hero |

### Twig References

Both assemblies support twigs via `PointInstancer`:

- **Static Assembly**: Twigs reference USD files (static meshes)
- **Skeletal Assembly**: Twigs can reference FBX files (if available) or fall back to USD

Twig instances are positioned at branch attachment points using face attributes from The Grove.

### Coordinate System

Both assemblies use **Z-up** coordinates (Unreal/Blender standard):
- Tree geometry transformed from Grove's Y-up to Z-up
- Twig positions converted during extraction
- All references use absolute paths (resolved at export time)

## Performance Comparison

### Static Mesh Assembly
```
✓ 100% Nanite compression
✓ Instanced rendering
✓ Minimal draw calls
✓ LOD handled automatically
✓ Best for distant/background trees
```

### Skeletal Mesh Assembly
```
✓ Nanite support maintained
✓ Animation-ready bones
✓ Control Rig compatible
✓ Wind deformation
✓ Best for hero/interactive trees
```

## Workflow Recommendations

### Large Forests (1000+ trees)
- Use Static Mesh Assembly
- Import once, instance thousands of times
- Let Nanite handle detail level
- Paint with Foliage Tool

### Hero Trees (< 10 trees)
- Use Skeletal Mesh Assembly
- Add wind animation blueprint
- Configure Control Rig
- Manual placement for best visual impact

### Mixed Approach
- Background: Static Mesh Assembly (90% of trees)
- Foreground: Skeletal Mesh Assembly (10% of trees)
- Transition distance: 50-100m from player

## Troubleshooting

### Issue: FBX references not found
**Solution**: Ensure FBX files are in the correct relative path (`../FBX/` from USD directory)

### Issue: Skeleton not importing
**Solution**: Use Skeletal Assembly (`*_Skeletal.usda`), not Static Assembly

### Issue: Twigs not appearing
**Solution**: Check that twig USD/FBX files exist in `data/assets/twigs/`

### Issue: Assembly not recognized as Nanite
**Solution**: Verify Unreal Engine 5.7+ is being used (earlier versions don't support Nanite Assemblies)

## Related Documentation

- `docs/growpy/NANITE_ASSEMBLY_GUIDE.md` - Detailed Nanite Assembly workflow
- `docs/growpy/UNREAL_ENGINE_NANITE.md` - Nanite compatibility guide
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Import pipeline documentation
- `TREE_USD_Z_UP_COMPLETE.md` - Coordinate system conversion

## Date

October 7, 2025
