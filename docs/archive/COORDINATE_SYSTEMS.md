# Coordinate System Handling in GrowPy

## Overview

GrowPy deals with three different coordinate systems when exporting trees for Unreal Engine. Understanding these systems and their transformations is critical for correct asset orientation.

## The Three Coordinate Systems

### 1. The Grove Internal System

- **Orientation**: Unknown from documentation
- **USD Export**: Y-up (confirmed in code comments)
- **Handedness**: Right-handed (assumed based on USD/OpenGL conventions)
- **When used**: Inside Grove's `model_to_usda_string()` function

### 2. Blender System

- **Orientation**: Z-up
- **Axes**: X right, Y forward, Z up
- **Handedness**: Right-handed
- **When used**:
  - FBX export via bpy
  - Mesh manipulation operations
  - Our USD files (we set `UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)`)

### 3. Unreal Engine System

- **Orientation**: Z-up
- **Axes**: X forward, Y right, Z up
- **Handedness**: Left-handed
- **Scale**: Centimeters (vs meters in Blender/Grove)
- **When used**: Final import target

## Transformation Pipeline

### Grove → Blender (Y-up to Z-up)

When Grove exports USD with `model_to_usda_string()`, it uses Y-up coordinates. We need to transform these to Z-up:

```python
def convert_y_up_to_z_up(pos, scale=1.0):
    """Rotate -90° around X-axis: (x, y, z) → (x, -z, y)"""
    return (pos[0] * scale, -pos[2] * scale, pos[1] * scale)
```

**Applied in:**

- `_add_grove_face_attributes_to_usd()` - transforms vertex positions from Grove's Y-up USD
- Tree mesh coordinates when extracted from Grove's native USD export

### Blender → Unreal (Right-handed to Left-handed)

Both use Z-up, but different handedness requires coordinate swap:

```python
def convert_blender_to_ue_coords(pos):
    """Swap X↔Y, negate Y: (x, y, z) → (y, -x, z)"""
    return (pos[1], -pos[0], pos[2])
```

**Applied in:**

- Twig instance positions in USD PointInstancer
- Twig normal vectors for orientation
- Only when `convert_to_ue=True` flag is set

### Scale Transformations

**Blender → Unreal (Meters to Centimeters)**

FBX export uses 100x scale factor:

```python
bpy.ops.export_scene.fbx(
    global_scale=100.0,  # Blender meters → Unreal centimeters
    apply_scale_options='FBX_SCALE_ALL'
)
```

**USD exports remain in meters** - Unreal handles the conversion on import.

## Current Implementation Status

### ✅ Correctly Handled

1. **FBX Export** (`_export_fbx_internal`)
   - 100x scale for Unreal centimeters
   - Blender axis configuration: `axis_forward="-Z"`, `axis_up="Y"`
   - Orientation handled by FBX exporter

2. **USD Stage Metadata**
   - All USD files set to Z-up: `UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)`
   - Meters per unit: `UsdGeom.SetStageMetersPerUnit(stage, 1.0)`

3. **Grove Y-up to Blender Z-up**
   - Applied in `_add_grove_face_attributes_to_usd()`
   - Converts vertex positions from Grove's Y-up export

4. **Twig Placement Coordinates**
   - `convert_to_ue=True` applies Blender→UE transformation
   - Used in PointInstancer positions/orientations

### ⚠️ Potential Issues

1. **Grove's Native `model_to_usda_string()` Export**
   - Exports in Y-up (per documentation)
   - We immediately wrap it with Z-up stage metadata
   - **Question**: Are the vertex coordinates themselves transformed, or just the metadata?
   - **Current approach**: We transform coordinates in `_add_grove_face_attributes_to_usd()`

2. **FBX Skeletal Mesh Orientation**
   - Uses `axis_forward="-Z"`, `axis_up="Y"`
   - **Question**: Does this correctly map Blender Z-up to Unreal Z-up with handedness conversion?
   - **Current approach**: Relies on FBX exporter's built-in handling

3. **Twig Model Orientation in Blender**
   - Grove documentation mentions different rotations needed for different software
   - Example for 3DS Max: "X: -90, Y: -90, Z: 0 degrees"
   - **Current approach**: No pre-rotation applied, assumes Grove twigs are already compatible
   - **Risk**: Twigs may be rotated incorrectly in Unreal

## Recommendations

### 1. Verify Grove's Native USD Export

Test whether Grove's `model_to_usda_string()` actually outputs Y-up vertex coordinates or if it's just metadata:

```python
# Extract vertex positions from Grove USD
stage = Usd.Stage.Open(str(grove_usd_path))
mesh = UsdGeom.Mesh.Get(stage, "/path/to/mesh")
points = mesh.GetPointsAttr().Get()

# Check if conversion is needed
# If points have Y >> Z, it's Y-up data
# If points have Z >> Y, it's already Z-up despite metadata
```

### 2. Add Twig Pre-Rotation for Unreal

Based on Grove documentation pattern, may need to rotate twig models before export:

```python
# Potential rotation needed for Unreal (similar to 3DS Max pattern)
# Test different rotations to find correct orientation
twig_obj.rotation_euler = (math.radians(-90), math.radians(-90), 0)
bpy.ops.object.transform_apply(rotation=True)
```

### 3. Document FBX Axis Mapping

Current FBX settings:

- `axis_forward="-Z"` → Forward faces -Z in Blender
- `axis_up="Y"` → Up is Y in Blender

Needs verification:

- Does this correctly map to UE's X-forward, Y-right, Z-up?
- Should we use different settings for skeletal vs static meshes?

### 4. Add Coordinate System Validation

```python
def validate_coordinate_systems(
    grove_usd: Path,
    blender_mesh: Any,
    unreal_import: Path
) -> Dict[str, str]:
    """Validate coordinate transformations through pipeline.
    
    Returns warnings for any coordinate mismatches.
    """
    # Check Grove USD up axis
    # Verify Blender mesh orientation
    # Test import in Unreal to confirm orientation
```

## Testing Checklist

When exporting a tree, verify:

- [ ] Tree trunk grows upward (+Z) in Unreal viewport
- [ ] Twigs point away from trunk (not toward it)
- [ ] Root system faces downward (-Z)
- [ ] Branches follow natural growth patterns
- [ ] No 90° rotations visible in Unreal transform properties
- [ ] Nanite LOD transitions smoothly (no orientation pops)

## References

### Internal Code

- `src/growpy/io/twig_placement.py` - Coordinate conversion functions
- `src/growpy/io/blender_export.py` - FBX/USD export with transformations
- `src/growpy/io/unreal_nanite_assembly.py` - Assembly creation

### External Documentation

- **Grove Coordinate Systems**: <https://www.thegrove3d.com/learn-more/plays-well-with-others/>
  - Documents required rotations for different software
  - Confirms twig orientation varies by target application
  - Examples: 3DS Max (X:-90, Y:-90, Z:0), LightWave (Heading:-90, Pitch:180, Banking:-90)

- **USD Specification**: <https://graphics.pixar.com/usd/docs/api/group___usd_geom_up_axis__group.html>
  - Y-up vs Z-up conventions
  - Stage metadata vs actual vertex coordinates

- **Unreal Engine Coordinate System**: <https://docs.unrealengine.com/5.3/en-US/coordinate-space-terminology-in-unreal-engine/>
  - Left-handed Z-up system
  - X-forward, Y-right, Z-up axes
  - Centimeter scale units

- **FBX Coordinate Systems**: <https://help.autodesk.com/view/FBX/2020/ENU/?guid=FBX_Developer_Help_nodes_and_scene_graph_fbx_scenes_html>
  - Axis conversion during export
  - Handedness transformations

## Known Issues

1. **Grove USD Export Ambiguity**: Grove's `model_to_usda_string()` documentation unclear about whether vertex coordinates are Y-up or just metadata
2. **Twig Rotation**: No explicit rotation applied to twigs for Unreal Engine target
3. **FBX Axis Validation**: Current axis settings (`-Z` forward, `Y` up) not verified against Unreal import results

## Future Work

1. Add runtime validation of coordinate transformations
2. Test and document twig pre-rotation requirements
3. Create visual debugging tools (coordinate axes overlays)
4. Add unit tests for transformation functions
5. Document actual vs expected coordinates at each pipeline stage
