# Twig Skeletal Mesh Support

This document describes the skeletal mesh support for twigs in The Grove project, enabling dynamic foliage with wind effects and animation in Unreal Engine.

## Overview

Twigs are now exported in two variants:

1. **Static Mesh** (`standard_name.usda`) - No skeleton, optimized for distant/static foliage
2. **Skeletal Mesh** (`standard_name_skel.usda`) - Root joint skeleton for animation/wind

The skeletal mesh variant includes a single root joint positioned at the twig's pivot point (origin), with all vertices bound to this joint. This minimal skeleton structure enables:

- Wind effects and animation in Unreal Engine
- Physics-based foliage motion
- Dynamic LOD transitions between static and skeletal variants
- Efficient performance (single joint has minimal overhead)

## Pipeline Workflow

### Two-Step Process

The twig export requires two steps because skeleton addition needs the main conda environment while Blender export runs in Blender's Python environment:

```bash
# Step 1: Export base USD files (run by Blender Python)
python src/growpy/cli/convert_twigs.py data/assets/twigs

# Step 2: Add skeletons to _skel variants (run by conda Python)
python src/growpy/cli/add_twig_skeletons.py data/assets/twigs
```

### Complete Pipeline

```bash
# Convert all species twigs
cd /path/to/the-grove
conda activate the-grove

# Step 1: Export static and skeletal base files
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Step 2: Add root joint skeletons to skeletal variants
python src/growpy/cli/add_twig_skeletons.py data/assets/twigs --update-manifests

# Result: Each twig has both static and skeletal variants
# - beech_apical.usda (static)
# - beech_apical_skel.usda (skeletal with root joint)
```

## Skeleton Structure

### Root Joint Properties

Each skeletal twig has a simple skeleton structure:

```
/Twig (SkelRoot)
├── TwigSkel (Skeleton)
│   └── root (Joint at origin)
└── TwigMesh (Mesh bound to skeleton)
```

**Joint Details:**

- **Name:** `root`
- **Position:** `(0, 0, 0)` (twig pivot/attachment point)
- **Bind Transform:** World space position at origin
- **Rest Transform:** Local space (same as bind, no parent)
- **Influence:** All mesh vertices bound with weight 1.0

### Unreal Engine Metadata

The skeletal variants include Unreal-specific metadata:

```python
# SkelRoot metadata
unreal:naniteAssembly:meshType = "skeletalMesh"
unreal:naniteAssembly:skeleton -> /Twig/TwigSkel
```

This ensures proper recognition as skeletal mesh in Unreal's import pipeline.

## Usage in Unreal Engine

### Import Settings

When importing skeletal twig USD files into Unreal Engine:

1. **Skeletal Mesh Import:**
   - Skeletal Mesh: ✓ Enabled
   - Create Physics Asset: ✗ Disabled (not needed)
   - Import Morph Targets: ✗ Disabled
   - Import Mesh LODs: ✓ Enabled (if available)

2. **Materials:**
   - Import Materials: ✓ Enabled
   - Import Textures: ✓ Enabled
   - Material Instance: ✓ Create instances

3. **Transform:**
   - Import Uniform Scale: 1.0
   - Convert Scene: ✓ Enabled (handles coordinate conversion)

### PCG Integration

Use skeletal variants for dynamic near-foliage, static for distant:

```
PCG Spawner Rules:
- Distance < 50m: Use _skel variant (skeletal mesh with wind)
- Distance >= 50m: Use static variant (no animation)
```

### Wind Animation Setup

1. **Import skeletal twig** into Unreal content browser
2. **Create AnimBP** for twig wind motion:
   - Single bone animation
   - Wind parameters (speed, strength, direction)
3. **Apply to foliage** in PCG/Foliage tool:
   - Set skeletal mesh variant
   - Enable AnimBP
   - Configure wind zones

### Material Setup

Both variants share the same materials and textures:

- Diffuse/Albedo (color + alpha mask)
- Normal map (optional)
- Roughness (optional)
- Two-sided rendering enabled

## Technical Implementation

### Code Structure

**USD Builder (`usd_builder.py`):**

```python
from growpy.io import add_twig_skeleton_to_usd

# Add root joint skeleton to twig USD
add_twig_skeleton_to_usd(
    usd_path=Path("beech_apical_skel.usda"),
    pivot_point=(0.0, 0.0, 0.0)  # Origin (attachment point)
)
```

**Blender Processor (`blender_twig_processor.py`):**

- Exports base USD files (both static and skeletal variants)
- Materials and textures applied to both variants
- Skeletal variants flagged for post-processing

**Post-Processor (`add_twig_skeletons.py`):**

- Finds all `*_skel.usda` files
- Adds root joint skeleton at origin
- Binds all vertices to root joint
- Updates manifests with skeleton info

### Skeleton Data Structure

**UsdSkel Attributes:**

```python
# Joint hierarchy
joints: ["root"]

# Bind transforms (world space)
bindTransforms: [
    Matrix4d((0,0,0) translation)  # Root at origin
]

# Rest transforms (local space)
restTransforms: [
    Matrix4d((0,0,0) translation)  # Same as bind (no parent)
]

# Skinning (per-vertex)
jointIndices: [0, 0, 0, ...]  # All vertices use joint 0 (root)
jointWeights: [1.0, 1.0, 1.0, ...]  # Full influence from root
```

### Performance Characteristics

**Static Mesh:**

- Draw calls: 1 per instance
- CPU overhead: Minimal
- GPU overhead: Standard static mesh
- Best for: Distant foliage, dense vegetation

**Skeletal Mesh:**

- Draw calls: 1 per instance
- CPU overhead: Single joint transform (negligible)
- GPU overhead: Vertex skinning (single weight)
- Best for: Near foliage, hero vegetation, wind zones

## Testing

### Validation Script

Test skeleton generation with `test_twig_skeleton.py`:

```bash
conda activate the-grove
python test_twig_skeleton.py
```

**Checks:**

- ✓ SkelRoot present at `/Twig`
- ✓ Skeleton present at `/Twig/TwigSkel`
- ✓ Single `root` joint
- ✓ Mesh bound to skeleton
- ✓ All vertices bound to root (weight 1.0)
- ✓ Unreal metadata present

### Visual Verification in Unreal

1. **Import skeletal twig USD** into Unreal
2. **Open Skeletal Mesh Editor:**
   - Check skeleton hierarchy (should show single root joint)
   - Verify all vertices painted to root
   - Check bone transform at origin
3. **Test animation:**
   - Create simple AnimBP with root bone rotation
   - Apply to mesh, verify all vertices move together
4. **Test in level:**
   - Place in world
   - Enable wind
   - Verify foliage moves as expected

## Migration from Static-Only

If you have existing static twig exports:

```bash
# Re-export with skeletal support
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda
python src/growpy/cli/add_twig_skeletons.py data/assets/twigs --update-manifests

# Result: Existing static files preserved, skeletal variants added
```

No code changes needed - both variants exported automatically.

## Best Practices

### When to Use Each Variant

**Static Mesh (`_skel` suffix):**

- Background foliage (>50m from camera)
- Dense vegetation areas
- Static hero trees with minimal wind
- Performance-critical scenarios

**Skeletal Mesh (`_skel` suffix):**

- Foreground foliage (<50m from camera)
- Hero vegetation with wind
- Interactive foliage
- Cinematic shots

### LOD Strategy

Combine with Unreal LOD system:

```
LOD 0 (0-25m):   Skeletal mesh, full detail, wind animation
LOD 1 (25-50m):  Skeletal mesh, reduced detail, wind animation
LOD 2 (50-100m): Static mesh, reduced detail, no animation
LOD 3 (100m+):   Static mesh, minimal detail, billboards
```

### Performance Optimization

1. **Use static variants for bulk foliage** (>80% of instances)
2. **Reserve skeletal for hero foliage** (<20% of instances)
3. **Adjust wind zones** to only affect skeletal meshes
4. **Disable animation** beyond view distance
5. **Use instancing** for both static and skeletal variants

## Troubleshooting

### Skeleton Not Found in Unreal

**Symptoms:** Unreal imports as static mesh, no skeleton visible

**Solutions:**

1. Verify `_skel.usda` file has skeleton (open in usdview)
2. Re-run `add_twig_skeletons.py` on the file
3. Check import settings: "Skeletal Mesh" should be enabled
4. Ensure file opened with correct USD stage

### All Vertices Not Moving

**Symptoms:** Only some vertices animate, rest are static

**Solutions:**

1. Check skinning data: all joints should be index 0
2. Check weights: all should be 1.0
3. Re-run skeleton addition script
4. Verify in USD: `jointIndices` and `jointWeights` arrays

### Animation Too Stiff/Loose

**Symptoms:** Wind animation doesn't look natural

**Solutions:**

1. This is expected - single root joint has uniform motion
2. For more natural motion, use Unreal's vertex animation
3. Or use shader-based wind (material animation)
4. Skeletal animation best for global motion, not leaf flutter

## Future Enhancements

Potential improvements to twig skeleton system:

1. **Multi-joint skeletons** for large twigs (branch + leaves)
2. **Per-leaf joints** for hero vegetation
3. **Automatic joint placement** from twig geometry analysis
4. **Weight painting** for gradual falloff from pivot
5. **Integration with cloth simulation** for realistic leaf flutter

## Related Documentation

- `docs/guides/cli-reference.md` - Complete CLI documentation
- `docs/USD_BUILDER.md` - USD export technical details
- `docs/QUICK_REFERENCE.md` - Quick command reference
- `src/growpy/cli/convert_twigs.py` - Twig conversion script
- `src/growpy/cli/add_twig_skeletons.py` - Skeleton addition script

## Summary

Twig skeletal mesh support enables dynamic foliage in Unreal Engine with minimal performance overhead. The two-variant approach (static + skeletal) allows optimal performance through LOD-based selection while maintaining visual quality for near-camera foliage.

**Key Points:**

- Two variants: static (no skeleton) and skeletal (root joint)
- Two-step pipeline: export USD, then add skeletons
- Single root joint at origin for minimal overhead
- Compatible with Unreal wind and animation systems
- Performance-friendly for large-scale foliage
