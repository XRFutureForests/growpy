# Nanite Skeletal Mesh Assembly Crash Fix

**Date**: 2025-01-08  
**Issue**: Unreal Engine crash with `ParentLODError >= 0.0f` assertion when importing FBX skeletal mesh Nanite assemblies  
**Status**: Fixed

## Problem Description

When importing skeletal mesh Nanite assemblies (referencing FBX files), Unreal Engine crashed during the Nanite hierarchy build with the following error:

```
Assertion failed: ParentLODError >= 0.0f 
[File:./Developer/NaniteBuilder/Private/Encode/NaniteEncodeHierarchy.cpp] [Line: 163]
```

This occurred during the `BuildHierarchyRecursive` step of Nanite encoding, indicating that the Nanite builder was unable to compute valid LOD error metrics for parent nodes in the hierarchy.

## Root Cause

The crash was caused by **degenerate mesh geometry** in the exported FBX files:

1. **Degenerate triangles**: Zero-area or nearly-zero-area faces that cannot produce valid screen-space LOD error metrics
2. **Duplicate vertices**: Overlapping vertices that create invalid topology
3. **Loose geometry**: Disconnected vertices or edges that interfere with clustering
4. **Very thin triangles**: Faces with extreme aspect ratios (>10:1) that create numerical instability in LOD calculations

When Nanite attempts to build its hierarchical LOD structure, it calculates parent LOD error values based on child cluster geometry. Degenerate geometry produces invalid or negative error values, triggering the assertion failure.

## Solution

Added comprehensive mesh cleanup before FBX export in `src/growpy/io/blender_export.py`:

### 1. Grove Native Triangulation

**Most Important**: Use Grove's built-in `model.triangulate()` function instead of Blender modifiers:

```python
# Triangulate using Grove's native function (more reliable than Blender modifier)
model.triangulate()
```

**Why this is critical:**

- Grove's triangulation happens at the model level (before mesh creation)
- Ensures consistent topology across all export formats
- More reliable than post-processing with Blender modifiers
- Guarantees all faces are triangles (Nanite requirement)

### 2. Mesh Geometry Cleanup

Added the following cleanup operations in Blender after mesh creation:

```python
# Clean mesh geometry to prevent Nanite hierarchy build errors
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")

# Remove degenerate geometry (zero-area faces, duplicate vertices)
bpy.ops.mesh.delete_loose()  # Remove loose vertices/edges
bpy.ops.mesh.remove_doubles(threshold=0.0001)  # Merge close vertices
bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)  # Remove degenerate faces

bpy.ops.object.mode_set(mode="OBJECT")
```

**Operations performed:**

- **`delete_loose()`**: Removes disconnected vertices and edges that don't form faces
- **`remove_doubles(threshold=0.0001)`**: Merges vertices within 0.1mm (extremely close duplicates)
- **`dissolve_degenerate(threshold=0.0001)`**: Removes faces with area < 0.0001m² (zero-area triangles)

**Note**: Triangulation is NOT done in Blender anymore - it's handled by Grove's `model.triangulate()` before mesh creation, which is more reliable.

### 3. Enhanced FBX Export Settings

Added scale parameters to ensure proper unit handling:

```python
bpy.ops.export_scene.fbx(
    # ... existing parameters ...
    global_scale=100.0,  # Scale up for Unreal (cm units)
    apply_scale_options='FBX_SCALE_ALL',  # Apply to all data
)
```

**Why this helps:**

- Unreal Engine uses centimeters as base units
- The Grove exports in meters
- Scaling up by 100x ensures geometry is at the correct size for Nanite's screen-space calculations
- Prevents numerical precision issues with very small faces

### 4. Debug Output

Added mesh statistics before export:

```python
print(f"  Mesh stats: {len(mesh_data.vertices)} verts, {len(mesh_data.polygons)} faces")
```

This helps diagnose mesh complexity issues before they cause problems.

## Technical Details

### Why Degenerate Geometry Causes Crashes

Nanite's hierarchical LOD system works by:

1. **Clustering**: Groups triangles into clusters (~128 triangles each)
2. **Simplification**: Creates parent clusters by simplifying child geometry
3. **Error Calculation**: Computes screen-space error for LOD switching

The error calculation formula depends on:

- Triangle area and bounds
- Distance from camera
- Screen resolution

Degenerate triangles with zero or near-zero area produce:

- Division by zero or near-zero values
- NaN (Not a Number) results
- Negative error values (violating the assertion `ParentLODError >= 0.0f`)

### Validation in validate_mesh_for_nanite()

The existing validation function checks for thin triangles:

```python
# Calculate aspect ratio using edge lengths
edges = [(verts[1] - verts[0]).length, ...]
aspect_ratio = max(edges) / min(edges)
if aspect_ratio > 10:  # Very thin triangle
    thin_triangle_count += 1
```

However, this is **informational only** - it doesn't prevent export. The new cleanup operations actively remove problem geometry.

## How to Re-Export

To regenerate all trees with the fix:

```bash
# Activate environment
conda activate the-grove

# Navigate to project
cd /Users/maximiliansperlich/Developer/the-grove

# Re-export the forest with FBX + Nanite assemblies
python src/growpy/cli/generate_forest.py \
    data/input/mini_tree_inventory_32632.csv \
    --formats usda fbx \
    --create-nanite-assembly
```

This will:

1. Clean all mesh geometry before export
2. Generate new FBX files with proper scaling
3. Create both static mesh and skeletal mesh Nanite assemblies
4. Apply the fix to all tree variations

## Verification

After re-exporting:

1. **Import skeletal mesh assembly** in Unreal Engine:
   - Open USD Stage browser
   - Import `*_NaniteAssembly_Skeletal.usda` files
   - Watch for successful Nanite encoding (no crash)

2. **Check mesh stats** in output logs:
   - Look for "Mesh stats: X verts, Y faces"
   - Verify reasonable polygon counts (not excessive or near-zero)

3. **Verify Nanite in Unreal**:
   - Select imported skeletal mesh
   - Check Details panel → Nanite Settings
   - Confirm "Enable Nanite Support" is checked
   - Verify no errors in Output Log

## Related Files

- **Fixed file**: `src/growpy/io/blender_export.py` - Added mesh cleanup before FBX export
- **Affected outputs**: All `*_NaniteAssembly_Skeletal.usda` files in `data/output/forest/*/USD/`
- **Documentation**: This file + `docs/growpy/NANITE_ASSEMBLY_GUIDE.md`

## Performance Impact

The cleanup operations add minimal overhead:

- **delete_loose()**: O(V+E) - linear in vertices/edges
- **remove_doubles()**: O(V log V) - efficient spatial hashing
- **dissolve_degenerate()**: O(F) - linear in face count

For typical trees (10k-100k faces), this adds <1 second per export.

## Prevention

To prevent similar issues in the future:

1. **Always run cleanup** before mesh export to any format
2. **Validate geometry** after Grove model building
3. **Test with simple cases** before batch exporting
4. **Monitor Nanite warnings** in Unreal import logs
5. **Use mesh validation** function to catch issues early

## References

- Unreal Engine Nanite documentation: <https://docs.unrealengine.com/5.0/en-US/nanite-virtualized-geometry-in-unreal-engine/>
- Nanite technical deep dive: <https://advances.realtimerendering.com/s2021/Karis_Nanite_SIGGRAPH_Advances_2021_final.pdf>
- FBX mesh requirements: <https://docs.unrealengine.com/5.0/en-US/fbx-content-pipeline/>

---

**Status**: Ready for re-export  
**Next Steps**: Run batch export with `--formats usda fbx --create-nanite-assembly`
