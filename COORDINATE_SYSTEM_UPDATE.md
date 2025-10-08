# Coordinate System Documentation Update

## Summary

Added comprehensive documentation and code comments to clarify how coordinate systems are handled throughout the export pipeline from The Grove to Unreal Engine.

## Changes Made

### 1. New Documentation: `docs/growpy/COORDINATE_SYSTEMS.md`

Comprehensive reference document covering:

- **Three Coordinate Systems**:
  - Grove internal (Y-up per documentation)
  - Blender (Z-up, right-handed)
  - Unreal Engine (Z-up, left-handed)

- **Transformation Pipeline**:
  - Grove Y-up → Blender Z-up conversion
  - Blender right-handed → Unreal left-handed conversion
  - Scale transformations (meters → centimeters)

- **Current Implementation Status**:
  - ✅ FBX export with 100x scale and axis settings
  - ✅ USD stage metadata (Z-up, meters)
  - ✅ Twig placement coordinate conversion
  - ⚠️ Grove's actual vertex coordinate orientation (needs validation)
  - ⚠️ Twig model pre-rotation requirements (undocumented)

- **Testing Checklist**: How to verify correct orientation in Unreal
- **Known Issues & Future Work**: Areas requiring investigation

### 2. Code Documentation Updates

#### `blender_export.py` - FBX Export Function

Added coordinate system section to `_export_fbx_internal()` docstring:

```python
Coordinate System Handling:
    Grove → Blender → Unreal Engine transformation pipeline:
    
    1. Grove builds model (internal coordinate system)
    2. Blender creates mesh from Grove model (Blender Z-up, right-handed)
       - Mesh vertices: X-right, Y-forward, Z-up
    3. FBX export transforms to Unreal (Z-up, left-handed)
       - axis_forward="-Z", axis_up="Y" in FBX exporter
       - global_scale=100.0: Meters → centimeters for Unreal
       - Handedness conversion handled by FBX exporter
    
    Result in Unreal: X-forward, Y-right, Z-up (left-handed), cm scale
```

#### `blender_export.py` - USD Export Function

Added coordinate system section to `export_grove_tree_as_usda_native()` docstring:

```python
Coordinate System Handling:
    Grove → USD transformation pipeline:
    
    1. Grove exports model via model_to_usda_string()
       - Documented to export in Y-up coordinate system
       - Vertex coordinates: (x, y, z) where Y is vertical
    
    2. We wrap Grove's USD in Z-up stage
       - Stage metadata: UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
       - Stage scale: UsdGeom.SetStageMetersPerUnit(stage, 1.0)
       - Face attributes converted: Y-up → Z-up via _add_grove_face_attributes_to_usd()
    
    3. Twigs added with convert_to_ue flag
       - If True: Blender Z-up → Unreal Z-up (handedness conversion)
       - Transformation: (x, y, z) → (y, -x, z)
    
    4. Unreal import
       - Reads Z-up USD correctly
       - Scale: Meters (USD) handled automatically
       - Handedness: Left-handed (if convert_to_ue=True)
```

#### `twig_placement.py` - Coordinate Conversion

Enhanced `convert_blender_to_ue_coords()` docstring with pipeline context:

```python
This is ONLY applied when convert_to_ue=True flag is set.
The base tree USD remains in Blender Z-up coordinates (right-handed).
See docs/growpy/COORDINATE_SYSTEMS.md for full transformation pipeline.
```

### 3. Inline Comments

Added clarifying comment when triangulating:

```python
# Triangulate using Grove's native function for consistent topology
# This ensures compatibility with Nanite and other triangle-only pipelines
# Note: Triangulation preserves coordinate system (no transformation here)
model.triangulate()
```

## Key Findings from Grove Documentation

From <https://www.thegrove3d.com/learn-more/plays-well-with-others/>:

1. **Different Software Requires Different Twig Rotations**:
   - 3DS Max: X:-90, Y:-90, Z:0
   - LightWave: Heading:-90, Pitch:180, Banking:-90
   - This suggests twigs need software-specific pre-rotation

2. **No Explicit Unreal Engine Instructions**:
   - Grove documentation doesn't specify twig rotation for UE
   - Current implementation assumes twigs work without pre-rotation
   - **Recommendation**: Test and document required rotation if any

3. **Grove's Internal Coordinate System**:
   - Documentation confirms USD export is Y-up
   - No information about Grove's internal vertex coordinates
   - May already be in target format before USD export

## Areas Requiring Validation

### 1. Grove Vertex Coordinates vs USD Metadata

**Question**: Does Grove's `model_to_usda_string()` export Y-up vertex data or just Y-up metadata?

**Test approach**:

```python
# Open Grove-exported USD
stage = Usd.Stage.Open("tree.usda")
mesh = UsdGeom.Mesh.Get(stage, "/Tree")
points = mesh.GetPointsAttr().Get()

# Check coordinate distribution
# If points have large Y values: actual Y-up data
# If points have large Z values: Z-up data with Y-up metadata
```

**Impact**:

- If Y-up data: Our Y→Z conversion in `_add_grove_face_attributes_to_usd()` is correct
- If Z-up data: Conversion is unnecessary and may cause double transformation

### 2. Twig Orientation in Unreal

**Question**: Do twigs imported via our pipeline orient correctly in Unreal?

**Test checklist**:

- [ ] Twigs point away from trunk (not into it)
- [ ] Leaves/needles face outward
- [ ] No visible 90° rotations in transform properties
- [ ] Natural appearance when viewed from all angles

**If incorrect**: Add pre-rotation similar to 3DS Max approach:

```python
twig_obj.rotation_euler = (math.radians(-90), math.radians(-90), 0)
bpy.ops.object.transform_apply(rotation=True)
```

### 3. FBX Axis Mapping

**Question**: Do current FBX settings correctly map to Unreal's coordinate system?

**Current settings**:

- `axis_forward="-Z"`: Forward = -Z in Blender
- `axis_up="Y"`: Up = Y in Blender

**Expected result**: X-forward, Y-right, Z-up in Unreal

**Test approach**:

- Import FBX skeletal mesh in Unreal
- Check transform properties (should be identity)
- Verify trunk grows in +Z direction
- Verify no unexpected rotations

## Recommendations

### Immediate Actions

1. **Test Current Implementation**:
   - Export a tree with the fixed Nanite crash solution
   - Import into Unreal Engine
   - Verify orientation is correct (trunk grows upward in +Z)
   - Check if twigs point in correct direction

2. **Document Test Results**:
   - Update `COORDINATE_SYSTEMS.md` with findings
   - Note any required twig pre-rotations
   - Confirm or correct transformation pipeline

### Future Improvements

1. **Add Runtime Validation**:

   ```python
   def validate_coordinate_transformation(
       grove_usd: Path,
       blender_mesh: Any,
       unreal_import: Path
   ) -> Dict[str, bool]:
       """Verify transformations at each stage."""
       # Check bounding boxes, up vectors, etc.
   ```

2. **Visual Debugging Tools**:
   - Export coordinate axes with trees
   - Overlay X/Y/Z arrows in Unreal for verification
   - Compare Grove → Blender → Unreal transformations

3. **Automated Testing**:
   - Unit tests for transformation functions
   - Known-good reference trees for comparison
   - Automated Unreal import and orientation checks

## References

- **Documentation**: `docs/growpy/COORDINATE_SYSTEMS.md`
- **Grove Export Guide**: <https://www.thegrove3d.com/learn-more/plays-well-with-others/>
- **Code Functions**:
  - `convert_y_up_to_z_up()` in `twig_placement.py`
  - `convert_blender_to_ue_coords()` in `twig_placement.py`
  - `_export_fbx_internal()` in `blender_export.py`
  - `export_grove_tree_as_usda_native()` in `blender_export.py`

## Next Steps

1. Test the current Nanite crash fix implementation
2. Verify tree and twig orientation in Unreal Engine
3. Update documentation with test results
4. Add twig pre-rotation if needed
5. Create validation functions for coordinate transformations

---

**Status**: Documentation complete, awaiting test results from Unreal import
