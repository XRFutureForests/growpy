# Unreal Import Guide - Updated 2025-01-08

## Quick Reference

### Static Trees (Background/Foliage)

**Import**: `*_NaniteAssembly.usda`

- ✅ Nanite optimization
- ✅ Instanced twigs
- ✅ Materials with textures
- ✅ Perfect for mass foliage

### Animated Trees (Hero/Wind)

**Import**: `*.usda` (base file, NOT Assembly)

- ✅ Skeleton for animation
- ✅ Materials with textures
- ✅ Ready for wind/procedural animation
- ⚠️ Don't use Nanite Assembly

## Files Explained

```
Oak/
├── FBX/
│   └── Oak_var1.fbx              # Legacy skeletal mesh (use if USD fails)
└── USD/
    ├── Oak_var1.usda             # ⭐ Base file with skeleton - USE FOR ANIMATION
    └── Oak_var1_NaniteAssembly.usda  # ⭐ Static mesh - USE FOR NANITE
```

## Import Steps

### Static Mesh (Nanite)

1. **File** → **Import**
2. Select `Oak_var1_NaniteAssembly.usda`
3. **Import Options**:
   - USD Importer (automatically selected)
   - Enable Nanite: ✅ (auto-enabled)
   - Import Actors: ✅
4. **Result**: Static mesh asset with instanced twigs

### Skeletal Mesh (Animation)

1. **File** → **Import**
2. Select `Oak_var1.usda` (NOT the Assembly file)
3. **Import Options**:
   - USD Importer (automatically selected)
   - Import Skeleton: ✅
   - Import Materials: ✅
4. **Result**: Skeletal mesh asset with skeleton

## Common Mistakes

❌ **Don't import** `*_NaniteAssembly_Skeletal.usda` (causes crash)
❌ **Don't use** FBX for Nanite (no assembly support)
✅ **Do use** base USD for animation
✅ **Do use** Nanite Assembly for static

## Workflow Recommendations

### Mass Foliage (100+ trees)

```
Import: *_NaniteAssembly.usda
Setup: Foliage Type asset
Use: Procedural Content Generation (PCG)
Why: Nanite + instancing = optimal performance
```

### Hero Trees (5-10 featured trees)

```
Import: *.usda (base file)
Setup: Skeletal mesh with wind animation
Use: Placed actors with animation
Why: Full animation control, skeleton support
```

### Mixed Approach

```
Background: Nanite Assembly (static)
Foreground: Base USD (animated)
Result: Best of both worlds
```

## Animation Setup

After importing skeletal mesh from base USD:

1. **Create Animation Blueprint**
   - Target skeleton: TreeSkeleton
   - Add wind procedural animation
   - Control via animation variables

2. **Wind System**
   - Use skeleton to drive wind
   - Branch weights from skeleton mass
   - Procedural sway/bend

3. **Growth Animation**
   - Morph targets or skeletal scale
   - Time-based growth curves
   - Season transitions

## Troubleshooting

### "Failed to create asset" on Skeletal Assembly

**Cause**: Skeletal Nanite Assemblies not supported (duplicate geometry)
**Fix**: Import base USD file instead (`Oak_var1.usda`)

### No textures on import

**Cause**: Texture paths not resolved
**Fix**: Textures should be embedded, check Materials folder

### Skeleton not found

**Cause**: Imported Nanite Assembly (static) instead of base USD
**Fix**: Import `Oak_var1.usda` for skeletal mesh

### Crash on import

**Cause**: Importing `*_NaniteAssembly_Skeletal.usda`
**Fix**: Don't import these files (they cause Nanite builder crash)

## Performance Tips

1. **Use Nanite Assembly for distant trees** - Automatic LOD
2. **Use skeletal mesh for near trees** - Full detail with animation
3. **Mix both types** - Transition at medium distance
4. **PCG scatter** - Use metadata for intelligent placement
5. **Foliage tool** - Paint both static and animated types

## File Format Comparison

| Format | Use Case | Pros | Cons |
|--------|----------|------|------|
| `*_NaniteAssembly.usda` | Static foliage | Nanite, instancing, optimal | No animation |
| `*.usda` (base) | Animated trees | Skeleton, materials, flexible | No Nanite (yet) |
| `*.fbx` | Legacy/fallback | Universal format | No Nanite, larger files |

## Future Updates

Epic is working on:

- Nanite for skeletal meshes (experimental)
- Better USD composition support
- Skeletal Nanite Assemblies (when USD support improves)

Until then, current workflow is optimal.
