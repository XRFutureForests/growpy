# Nanite Compatibility Guide

## Overview

All GrowPy tree and twig exports are now Nanite-compatible for Unreal Engine 5.7+. This guide explains what Nanite requirements are implemented, how to validate meshes, and how to import them into Unreal Engine with optimal settings.

## What is Nanite?

Nanite is Unreal Engine 5's virtualized geometry system that enables rendering of film-quality assets with millions of polygons while maintaining real-time performance. It automatically manages LODs, streaming, and culling without manual setup.

## Nanite Requirements Implemented

### 1. **Single Smoothing Group** ✓
- All FBX exports use `mesh_smooth_type='FACE'`
- Ensures consistent shading for Nanite clustering
- Required for optimal Nanite performance

### 2. **Triangulation** ✓
- Automatic triangulation modifier applied to all meshes
- Uses 'BEAUTY' method for optimal triangle distribution
- Ensures consistent topology across variations

### 3. **Preserve Area (Foliage)** ✓
- **Trees**: `preserve_area = False` (branches/trunk don't need it)
- **Twigs**: `preserve_area = True` (CRITICAL - prevents leaf thinning at distance)
- Automatically set based on mesh type

### 4. **Full Precision UVs** ✓
- `use_tspace=True` in all exports
- Tangent space enabled for normal maps
- UV maps exported with full precision

### 5. **Opaque Materials** ✓
- All materials use Opaque blend mode (2-3x faster than Masked)
- Principled BSDF with proper roughness/metallic values
- Embedded textures in FBX, proper UV mapping in USD

### 6. **Mesh Topology Validation** ✓
- Automatic validation for:
  - Triangle count (<1M recommended)
  - Thin triangle detection (aspect ratio > 10:1)
  - UV seam count (continuity check)
  - Material assignment

### 7. **USD Attributes** ✓
- `unrealNanite = "enable"` on all meshes
- `unrealNanitePreserveArea = true` on foliage/twigs
- Proper Unreal-specific metadata

## Export Formats and Nanite

### FBX Export (Universal Compatibility)

**Nanite Features:**
```python
# Automatic settings applied during export:
mesh_smooth_type='FACE'           # Single smoothing group
use_mesh_modifiers=True           # Apply triangulation
use_mesh_edges=False              # Clean mesh (no edge data)
use_tspace=True                   # Tangent space for normal maps
use_custom_props=True             # Nanite metadata in custom properties
```

**Custom Properties Added:**
- `nanite_compatible = True`
- `nanite_preserve_area = True/False` (depending on mesh type)
- `unreal_nanite = "enable"`

### USD Export (Nanite Native)

**Nanite Attributes:**
```usda
def Mesh "TreeMesh" {
    custom token unrealNanite = "enable"
    custom bool unrealNanitePreserveArea = true  # For foliage only
}
```

USD is the recommended format for Nanite as it has native support in Unreal Engine 5.7+.

## Mesh Validation

All exported meshes are automatically validated for Nanite compatibility. Validation checks:

### Triangle Count
```
✓ Good: < 1,000,000 triangles
⚠ Warning: > 1,000,000 triangles (may impact performance)
```

### UV Continuity
```
✓ Good: UV seams < 30% of triangle count
⚠ Warning: High UV seam count (increases vertex count)
```

### Topology
```
✓ Good: Thin triangles < 10% of total
⚠ Warning: Many thin/degenerate triangles (aspect ratio > 10:1)
```

### Materials
```
✓ Good: Materials assigned
⚠ Warning: No materials (may cause import issues)
```

## Unreal Engine Import

### FBX Import Settings

1. **Enable Nanite** in import dialog:
   - ☑ Enable Nanite Support
   - Fallback Relative Error: `1.0` (default)
   - Fallback Triangle Percent: `100` (no fallback)

2. **Static Mesh Settings**:
   - Build Reversed Index Buffer: ☑ (automatic)
   - Full Precision UVs: ☑ (automatic)
   - Generate Lightmap UVs: ☐ (Nanite handles lighting)

3. **Material Settings**:
   - Import Materials: ☑
   - Import Textures: ☑
   - Material Search Location: `All Assets`

### USD Import Settings

1. **USD Stage Options**:
   - Import Actors: ☑
   - Import Geometry: ☑
   - Import Skeletal Animations: ☐

2. **Nanite** (automatic from USD attributes):
   - Meshes with `unrealNanite = "enable"` automatically get Nanite
   - `unrealNanitePreserveArea` automatically applied to foliage

3. **Instancing**:
   - Collapse Mode: `Keep Instances` (for forests)
   - Use `Flatten` for single trees

## Foliage Setup with Nanite

### Creating Foliage Types

1. **Right-click Static Mesh** → Create Foliage Type
2. **Nanite Settings** (already configured via metadata):
   - Nanite: Enabled
   - Preserve Area: ☑ (twigs only)

3. **Culling Settings**:
   - Cull Distance Min: `0` (no min)
   - Cull Distance Max: `20000` (200m)
   - Instance Start/End Cull Distance: Use PCG metadata values

4. **Density Settings** (from PCG metadata):
   - Density Scaling: `1.0`
   - Min/Max Spacing: Use metadata values

### PCG Scatter with Nanite

```blueprint
PCG Graph:
├─ Surface Sampler
│  ├─ Points Per Square Meter: [from metadata]
│  ├─ Point Extent Min/Max: [from metadata min/max_spacing]
│  └─ Looseness: 1.0
├─ Static Mesh Spawner
│  ├─ Meshes: [3 variations with weighted random]
│  ├─ Scale Min/Max: [0.8-1.2 from metadata]
│  └─ Rotation: Random Z (yaw)
└─ Attribute Mapper
   └─ Map twig_* attributes to twig instance spawning
```

## Performance Optimization

### Nanite Visualization

Use these console commands to validate Nanite is working:

```
r.Nanite.ViewMode 1            # Show Nanite mesh clustering
r.Nanite.ShowStats 1           # Display Nanite statistics
stat GPU                       # GPU performance stats
```

### Expected Performance

- **Million Triangle Tree**: 60 FPS with Nanite (vs <10 FPS without)
- **Forest (10,000 trees)**: Real-time with automatic streaming
- **Overdraw**: Minimal due to Nanite's visibility culling

### Memory Usage

- **Nanite Enabled**: Shared mesh data, streamed on demand
- **Instancing**: HISM automatically used for identical variations
- **Streaming Pool**: Adjust `r.Nanite.StreamingPoolSize` if needed

## Troubleshooting

### Trees Look Low-Poly in Distance

**Cause**: Preserve Area not enabled for foliage
**Fix**: Re-import with `unrealNanitePreserveArea = true` or enable in Static Mesh settings

### Nanite Not Enabling on Import

**Cause**: Mesh exceeds Nanite triangle limits or has unsupported features
**Fix**:
1. Check mesh validation warnings in export logs
2. Reduce triangle count with lower resolution preset
3. Verify import settings have "Enable Nanite Support" checked

### Performance Issues with Many Trees

**Cause**: Not using instancing or streaming
**Fix**:
1. Use USD import with "Keep Instances" mode
2. Enable HISM for foliage
3. Set appropriate cull distances
4. Use World Partition for large levels

### Materials Look Incorrect

**Cause**: Texture paths or material setup issues
**Fix**:
1. Verify textures are embedded (FBX) or properly referenced (USD)
2. Check material blend mode is Opaque
3. Reassign materials if needed using Material Override

### Thin Triangles Warning

**Cause**: Branch topology has very elongated triangles
**Fix**:
1. Increase `resolution` parameter in export (e.g., 32 instead of 16)
2. Decrease `resolution_reduce` to maintain detail on thin branches
3. Warning is informational - Nanite handles it well in most cases

## Validation Checklist

Before using meshes in Unreal:

- [ ] Export completed without errors
- [ ] Mesh validation shows no critical warnings
- [ ] Triangle count < 1M (or acknowledged if higher)
- [ ] UV maps present and continuous
- [ ] Materials assigned with textures
- [ ] Nanite metadata present (check custom properties or USD attributes)
- [ ] Preserve Area correctly set (True for twigs, False for trees)
- [ ] Import test in Unreal shows Nanite enabled
- [ ] Foliage Type created with correct settings
- [ ] Performance test shows acceptable frame rates

## Advanced: Manual Nanite Configuration

If you need to manually adjust Nanite settings in Unreal:

1. **Open Static Mesh Editor**
2. **Nanite Settings**:
   - Enable: ☑
   - Preserve Area: ☑ (foliage only)
   - Fallback Relative Error: `1.0`
   - Fallback Triangle Percent: `100`

3. **LOD Settings**:
   - Number of LODs: `1` (Nanite handles LODs)
   - Auto Compute LOD Distances: ☐

4. **Collision**:
   - Collision Complexity: `Use Simple Collision as Complex`
   - Generate Simple Collision: ☑

## Resources

- [Unreal Engine Nanite Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- [USD Import Guide](./UNREAL_IMPORT_GUIDE.md)
- [PCG Workflow Guide](./UNREAL_PCG_WORKFLOW.md)
- [Mesh Validation Details](./UNREAL_IMPORT_GUIDE.md#nanite-validation)

## Summary

GrowPy exports are fully Nanite-compatible with:
- ✓ Proper smoothing groups and triangulation
- ✓ Preserve Area for foliage meshes
- ✓ Full-precision UVs and tangent space
- ✓ Opaque materials with embedded textures
- ✓ Automatic mesh validation
- ✓ Nanite USD attributes
- ✓ FBX custom properties for Nanite metadata

Import USD files for native Nanite support or use FBX with manual Nanite enable. Both formats are production-ready for large-scale forest generation in Unreal Engine 5.7+.
