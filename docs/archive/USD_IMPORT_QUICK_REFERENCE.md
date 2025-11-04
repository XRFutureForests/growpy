# USD File Import Quick Reference

## File Types Overview

| File | Import As | Has Skeleton | Has Twigs | Best For |
|------|-----------|--------------|-----------|----------|
| `*_tree_only_skeletal.usda` ✨ | Skeletal Mesh | ✅ Yes (6 bones) | ❌ No | **Hero trees, animation** |
| `*_NaniteAssembly.usda` | Static Mesh | ❌ No | ✅ Yes | **Background foliage, performance** |
| `*.usda` | Skeletal Mesh | ✅ Yes | ✅ Yes | Full tree with twigs |
| `*_tree_only.usda` | Static Mesh | ❌ No | ❌ No | Raw mesh for custom materials |

## Quick Workflow Guide

### For Animated Trees (Wind, Sway, Growth) ✨ RECOMMENDED

**Import:** `Oak_var1_tree_only_skeletal.usda`

1. Drag file into Unreal Content Browser
2. Import Type: **Skeletal Mesh**
3. Enable: **Import Skeleton**, **Import Materials**
4. Result: Clean tree with 6-bone skeleton, ready for animation

**Skeleton Structure:**

- Root (base)
- Branch_0_Bone_0 through Branch_0_Bone_4 (5 branch bones)

**This is the FBX-equivalent workflow!**

### For Background Static Trees (Best Performance)

**Import:** `Oak_var1_NaniteAssembly.usda`

1. Drag file into Unreal Content Browser
2. Import Type: **Static Mesh**
3. Enable: **Nanite**, **Import Materials**
4. Result: Optimized static mesh with auto-instanced twigs

### For Complete Tree with Skeleton + Twigs

**Import:** `Oak_var1.usda`

1. Drag file into Unreal Content Browser  
2. Import Type: **Skeletal Mesh**
3. Enable: **Import Skeleton**, **Import Materials**
4. Result: Full tree assembly with skeleton and twig instances

### For Custom Material Setup

**Import:** `Oak_var1_tree_only.usda`

1. Drag file into Unreal Content Browser
2. Import Type: **Static Mesh**
3. Disable: **Import Materials**
4. Result: Raw mesh, apply your own materials

## Animation Setup (Skeletal Mesh)

After importing `*_tree_only_skeletal.usda`:

### Wind Animation

1. Open Skeletal Mesh
2. Add Animation Blueprint
3. Use Skeletal Controls:
   - **Rotate Bone** nodes for branch sway
   - **Spring Controller** for procedural motion
   - Target bones: Branch_0_Bone_0 through Branch_0_Bone_4

### Procedural Sway

```
Timeline → Sine Wave → Rotate Bone (Branch_0_Bone_0)
   ↓
   + Random offset per bone
   + Wind direction input
```

### Growth Animation

1. Animate bone scales from 0 to 1
2. Sequence through bones (root to tips)
3. Add material parameter for leaf appearance

## Comparison Chart

### Static vs Skeletal Import

| Feature | Static (`_NaniteAssembly`) | Skeletal (`_skeletal`) |
|---------|---------------------------|------------------------|
| Animation | ❌ No | ✅ Yes |
| Nanite | ✅ Yes | ❌ No* |
| Performance | 🟢 Best | 🟡 Good |
| File Size | Smaller | Larger |
| Twigs | Auto-instanced | Separate import |
| Use Case | Background | Hero trees |

*Skeletal meshes don't support Nanite in UE 5.7

### With Twigs vs Without

| File | Has Twigs | Advantage |
|------|-----------|-----------|
| `*_skeletal.usda` | ❌ No | Clean skeleton, easier animation setup |
| `*.usda` | ✅ Yes | Complete tree, one-click import |

## File Size Reference

Example for Oak tree:

```
Oak_var1_tree_only.usda              57KB  (mesh only)
Oak_var1_tree_only_skeletal.usda     57KB  (mesh + skeleton + materials)
Oak_var1.usda                        2.5KB (assembly, references above)
Oak_var1_NaniteAssembly.usda         2.6KB (assembly, references above)
```

Assembly files are small because they reference the main tree file.

## Troubleshooting

### "Skeleton Import Failed"

✅ **Solution:** Make sure you're importing `*_tree_only_skeletal.usda`, not `*_tree_only.usda`

### "Twigs Not Showing"

✅ **Solution:** Import `*_NaniteAssembly.usda` or `*.usda` (full assembly)

### "Nanite Doesn't Work"

✅ **Solution:** Use `*_NaniteAssembly.usda` as **Static Mesh**, not skeletal

### "Crash on Import"

✅ **Solution:** Make sure twigs don't use `_NaniteAssembly.usda` files (fixed in latest version)

## Terminal Commands

### Generate Trees with All USD Formats

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py forest.csv --formats usda
```

### Output Structure

```
Oak/
├── FBX/
│   └── Oak_var1.fbx                         # FBX skeletal mesh
└── USD/
    ├── Oak_var1_tree_only.usda              # Static mesh only
    ├── Oak_var1_tree_only_skeletal.usda     # Skeletal mesh (use this!) ✨
    ├── Oak_var1.usda                        # Full assembly with twigs
    └── Oak_var1_NaniteAssembly.usda         # Static Nanite Assembly
```

## Best Practices

### ✅ DO

- Use `*_skeletal.usda` for hero/animated trees
- Use `*_NaniteAssembly.usda` for background foliage
- Test import settings with one tree first
- Keep source USD files for re-import

### ❌ DON'T

- Try to apply Nanite to skeletal meshes
- Import twigs individually (use assembly files)
- Modify imported meshes (re-import instead)
- Delete intermediate USD files

## Performance Tips

### For Large Forests

1. **Background trees:** Import as Static Mesh with Nanite
   - File: `*_NaniteAssembly.usda`
   - Auto LODs, excellent performance

2. **Hero trees:** Import as Skeletal Mesh (1-5 trees)
   - File: `*_tree_only_skeletal.usda`
   - Add wind animation

3. **Medium distance:** Static mesh with simple animation
   - Import skeletal, bake animation to static

### Memory Optimization

- Nanite Assemblies share geometry automatically
- Skeletal meshes: Use LODs for distant trees
- Material instances: Share base materials

## Related Documentation

- `TREE_ONLY_SKELETAL_USD.md` - Detailed technical documentation
- `UNREAL_IMPORT_GUIDE.md` - Complete import workflows
- `COORDINATE_SYSTEMS.md` - Coordinate system handling

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════╗
║  IMPORT CHEAT SHEET                                       ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  🎬 ANIMATION (Hero Trees)                                ║
║     File: *_tree_only_skeletal.usda                       ║
║     Type: Skeletal Mesh                                   ║
║     Import: Skeleton ✅  Materials ✅  Twigs ❌             ║
║                                                           ║
║  🌲 STATIC (Background)                                   ║
║     File: *_NaniteAssembly.usda                           ║
║     Type: Static Mesh                                     ║
║     Import: Nanite ✅  Materials ✅  Twigs ✅               ║
║                                                           ║
║  🌳 COMPLETE (Everything)                                 ║
║     File: *.usda                                          ║
║     Type: Skeletal Mesh                                   ║
║     Import: Skeleton ✅  Materials ✅  Twigs ✅             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

---

**Last Updated:** 2025-10-08  
**Applies to:** The Grove USD Export v2.0+, Unreal Engine 5.7+
