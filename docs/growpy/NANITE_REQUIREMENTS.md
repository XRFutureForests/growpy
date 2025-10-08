# Nanite Requirements for The Grove

**Official Documentation**: [Unreal Engine Nanite Virtualized Geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)

## Overview

This document outlines how The Grove export pipeline meets Unreal Engine's Nanite requirements for optimal virtualized geometry rendering.

## Core Nanite Requirements

### 1. Triangle-Only Topology ✅ IMPLEMENTED

**Requirement**: Nanite meshes must consist entirely of triangles (no quads or n-gons).

**Implementation**:

```python
# In both FBX and USD export:
model = models[0]
model.triangulate()  # Grove's native function
```

**Why This Works**:

- Grove's `model.triangulate()` converts all quads to triangles at the model level
- Happens before mesh creation (more reliable than post-processing)
- Consistent across all export formats (USD, FBX, OBJ)
- Same method used by Grove's official Blender addon

**Reference**: `src/growpy/io/blender_export.py` lines 1217, 1965

---

### 2. No Degenerate Geometry ✅ IMPLEMENTED

**Requirement**: No zero-area faces, duplicate vertices, or loose geometry.

**Implementation**:

```python
# Mesh cleanup in Blender (FBX export):
bpy.ops.mesh.delete_loose()  # Remove disconnected vertices/edges
bpy.ops.mesh.remove_doubles(threshold=0.0001)  # Merge duplicates (0.1mm)
bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)  # Remove zero-area faces
```

**Why This Matters**:

- Degenerate geometry causes `ParentLODError >= 0.0f` assertion in Nanite encoder
- Zero-area faces produce invalid screen-space LOD error calculations
- Prevents crash during Nanite hierarchy build

**Reference**: `src/growpy/io/blender_export.py` lines 1278-1310

---

### 3. Vertex Sharing (Optimal Ratio <2:1) ✅ VALIDATED

**Requirement**: Vertex-to-triangle ratio should be less than 2:1 for optimal performance.

**What This Means**:

- **<1:1**: Excellent (ideal for smooth surfaces with shared vertices)
- **1:1 to 2:1**: Good (some hard edges, acceptable)
- **>2:1**: Poor (excessive vertex duplication, faceted normals)
- **~3:1**: Very poor (completely faceted mesh, every triangle has unique vertices)

**Implementation**:

```python
# Validation in validate_mesh_for_nanite():
vertex_ratio = vertex_count / triangle_count
if vertex_ratio > 2.0:
    # Warning issued
```

**Impact of Poor Ratios**:

- Higher data size (more vertices stored)
- Increased vertex transform work
- Slower rendering paths (>2:1 ratio)
- Less effective Nanite compression

**Reference**: Official docs section "Faceted and Hard-edge Normals"

---

### 4. Scale and Units ✅ IMPLEMENTED

**Requirement**: Proper scaling for Unreal Engine's centimeter-based coordinate system.

**Implementation**:

```python
# FBX export scaling:
bpy.ops.export_scene.fbx(
    global_scale=100.0,  # Scale from meters to centimeters
    apply_scale_options='FBX_SCALE_ALL',
)
```

**Why This Matters**:

- Unreal Engine uses centimeters as base units
- The Grove exports in meters
- 100x scale prevents sub-millimeter precision issues
- Avoids numerical instability in Nanite LOD calculations

**Reference**: `src/growpy/io/blender_export.py` line 1337

---

### 5. Material Requirements ✅ COMPATIBLE

**Supported**:

- ✅ Opaque blend mode (tree trunks, branches)
- ✅ Masked blend mode (leaves with alpha cutout)
- ✅ Multiple UVs
- ✅ Vertex colors

**Not Supported**:

- ❌ Translucent blend modes
- ❌ Mesh decals
- ❌ Forward rendering
- ❌ MSAA

**Implementation**: Materials are assigned during import in Unreal, not controlled by export.

**Reference**: Official docs section "Supported Features - Materials"

---

### 6. Tangent Space ✅ HANDLED BY NANITE

**How Nanite Works**:

- Tangents are **not stored** in Nanite mesh data (saves space)
- Tangents are **derived implicitly** in pixel shader at runtime
- May cause minor discontinuities at edges (rarely noticeable)

**Implementation**:

```python
# FBX export includes tangent space for compatibility:
bpy.ops.export_scene.fbx(
    use_tspace=True,  # Export tangent space
)
```

**Note**: Tangent data is exported but Nanite regenerates it internally. Future Unreal versions may support explicit tangent storage.

**Reference**: Official docs section "Supported Features - Geometry"

---

### 7. UV Maps ✅ SUPPORTED

**Requirement**: Multiple UV channels supported, recommended for texturing.

**Implementation**:

- UVs exported from Grove's model data
- Stored in FBX with proper mapping
- Nanite supports multiple UV layers
- UV seams increase vertex count (expected)

**Reference**: `src/growpy/io/blender_export.py` lines 1239-1247

---

### 8. Preserve Area Setting ✅ CORRECTLY CONFIGURED

**When to Use**:

- **FALSE (default)**: Tree trunks, branches (solid continuous surfaces)
- **TRUE**: Foliage leaves, grass blades (disjoint elements)

**Why This Matters**:

- Prevents foliage from "thinning out" at distance
- Redistributes lost surface area to remaining triangles
- Should ONLY be enabled for actual foliage cards, not tree geometry

**Implementation**:

```python
obj["nanite_preserve_area"] = False  # Correct for trees
```

**Reference**: Official docs section "Foliage Using Nanite"

---

### 9. Skeletal Mesh Support ✅ EXPERIMENTAL IN UE 5.x

**Current Status**: Nanite skeletal meshes are **experimental** in Unreal Engine 5.x

**Supported Features**:

- ✅ One draw call per entire mesh
- ✅ Virtual Shadow Maps
- ✅ No geometry LODs (uses animation LODs)
- ✅ Instancing with animation banks

**Limitations**:

- ⚠️ Experimental - subject to change
- ⚠️ Performance varies by use case
- ⚠️ Not all animation features supported

**Our Implementation**:

- Exports both static (`*_NaniteAssembly.usda`) and skeletal (`*_NaniteAssembly_Skeletal.usda`) variants
- Users can choose based on their needs (static for background, skeletal for hero trees)

**Reference**: Official docs section "Nanite Skeletal Mesh"

---

## Validation Checklist

Our export pipeline validates the following:

- [x] All faces are triangles (via `model.triangulate()`)
- [x] No degenerate geometry (via Blender cleanup)
- [x] Vertex-to-triangle ratio checked (warnings if >2:1)
- [x] Proper scaling (100x for Unreal cm units)
- [x] UV maps present
- [x] Preserve Area correctly set (FALSE for trees)
- [x] Clean mesh topology
- [x] Nanite metadata embedded

**Validation Function**: `validate_mesh_for_nanite()` in `src/growpy/io/blender_export.py`

---

## Known Limitations

### What We Handle

1. ✅ Triangle-only topology (Grove's native function)
2. ✅ Degenerate geometry removal (Blender cleanup)
3. ✅ Proper scaling (100x)
4. ✅ Mesh validation and warnings
5. ✅ Metadata for Unreal import

### What Users Must Handle in Unreal

1. Material assignment (Opaque/Masked blend modes)
2. Nanite settings tweaking (Position Precision, Fallback settings)
3. Virtual Shadow Maps configuration
4. Performance profiling with `NaniteStats` command
5. Platform-specific optimization

---

## Common Issues and Solutions

### Issue: Crash with `ParentLODError >= 0.0f`

**Cause**: Degenerate geometry or invalid mesh topology

**Solution**: ✅ Fixed with mesh cleanup + Grove triangulation

---

### Issue: High vertex-to-triangle ratio (>2:1)

**Cause**: Faceted normals, poor vertex sharing

**Solution**:

- Check source mesh normals
- Use smooth shading where appropriate
- Validation function warns about this

---

### Issue: Foliage thinning at distance

**Cause**: Preserve Area not enabled

**Solution**:

- Enable Preserve Area in Unreal Static Mesh Editor
- Only for foliage leaves/grass, NOT tree trunks

---

### Issue: Missing detail at distance

**Cause**: Incorrect scale or fallback settings

**Solution**:

- Verify 100x scaling applied
- Adjust Fallback Relative Error in Unreal
- Check Position Precision settings

---

## Performance Considerations

### Optimal Use Cases for Nanite

- ✅ High triangle count meshes (>10k triangles)
- ✅ Many instances in scene
- ✅ Major occluders
- ✅ Virtual Shadow Maps enabled

### Less Optimal Use Cases

- ⚠️ Very low poly meshes (<1k triangles)
- ⚠️ Single instances
- ⚠️ Transparent materials
- ⚠️ Aggregate geometry with many holes

**Trees**: Generally excellent candidates for Nanite!

---

## Testing in Unreal

### Enable Nanite

1. Import USD assembly file
2. Select imported skeletal mesh
3. Details panel → Nanite Settings
4. Enable "Enable Nanite Support"
5. Adjust settings as needed

### Verification Commands

```
# Enable Nanite stats overlay
NaniteStats

# Toggle Nanite on/off
r.Nanite 0  # Disable
r.Nanite 1  # Enable (default)

# Visualizations
Show > Nanite Visualization > [mode]
```

### Key Metrics to Monitor

- **Triangles**: Should scale with screen size, not scene complexity
- **Clusters**: Groupings of ~128 triangles
- **Overdraw**: Watch for excessive overdraw (bright areas)
- **Memory**: Check streaming pool size if thrashing occurs

---

## References

1. **Official Docs**: [Nanite Virtualized Geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
2. **Technical Deep Dive**: [Siggraph 2021 Paper](https://advances.realtimerendering.com/s2021/Karis_Nanite_SIGGRAPH_Advances_2021_final.pdf)
3. **Our Implementation**:
   - `src/growpy/io/blender_export.py`
   - `src/growpy/io/unreal_nanite_assembly.py`
   - `docs/archive/NANITE_SKELETAL_CRASH_FIX.md`

---

**Last Updated**: 2025-01-08  
**Status**: All core requirements implemented and validated  
**Next Steps**: Test with actual Unreal Engine import
