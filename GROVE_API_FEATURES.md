# Grove API Features and UV Mapping Fixes

## Summary

Fixed UV mapping issues and identified extensive Grove API features for enhanced tree generation. The problem was that UV coordinates needed texture aspect ratio correction and proper extraction from Grove's model methods.

## UV Mapping Issues Fixed

### **Problem**: Tiny Textures on Tree Meshes

- **Root Cause**: UV coordinates not properly scaled for texture aspect ratios
- **Grove Solution**: `model.apply_uv_aspect_ratio(aspect_ratio)` method available
- **Default Fix**: Applied 2.0 aspect ratio (typical for bark textures - taller than wide)

### **Grove UV Methods Available**

```python
# UV coordinate extraction
uvs = model.get_uvs_flat()           # Primary UV map: [u1, v1, u2, v2, ...]
uv_islands = model.get_uv_islands_flat()  # UV islands: separate texture regions
uvws = model.get_uvws_flat()         # UVW coordinates (with W=0.0): [u1, v1, w1, u2, v2, w2, ...]

# UV manipulation  
model.apply_uv_aspect_ratio(2.0)    # Stretch V coordinates for texture aspect ratio
```

## Additional Grove API Features Discovered

### **Model Coordinate System Control**

```python
# Set up-axis for target application
model.set_up_axis("Z")      # Blender/Unreal Engine (Z-up)
model.set_up_axis("Y")      # Houdini/Maya (Y-up)

# Set face winding order
model.set_winding_order("COUNTER_CLOCKWISE")  # Blender/Unreal standard
model.set_winding_order("CLOCKWISE")          # Grove default
```

### **Enhanced Geometry Data**

```python
# Vertex positions
points = model.get_points_flat()           # [x, y, z, x, y, z, ...] - fastest
points_tuples = model.get_points_as_tuples()  # [(x,y,z), (x,y,z), ...] - readable
shapes = model.get_shape_as_tuples()       # Alternative geometry method

# Face direction vectors (for advanced shading)
directions = model.get_directions_flat()   # [dx, dy, dz, dx, dy, dz, ...] - face normals
```

### **Model Manipulation**

```python
# Geometry processing
model.triangulate()                        # Convert quads to triangles (Grove native method)

# Direct face/vertex access
faces = model.faces                        # List[List[int]] - face vertex indices
points = model.points                      # List[Vector] - vertex positions
```

### **Native USD Export**

```python
# Grove's built-in USD export (preserves all attributes)
from growpy.utils.dependencies import gc
usda_string = gc.io.model_to_usda_string(model)

# Also available: OBJ export
obj_string = gc.io.model_to_obj_string(model)
```

## Physics Data Integration (Covered in Previous Updates)

### **Structural Physics**

- `point_attribute_mass` - Mass distribution for physics-based weighting
- `point_attribute_thickness` - Branch diameter (structural importance)
- `point_attribute_vigor` - Growth energy and health

### **Biological Data**

- `point_attribute_photosynthesis` - Light capture efficiency
- `point_attribute_shade` - Ambient occlusion (0.0 = full light, 1.0 = full shade)
- `point_attribute_age` - Growth age (older = more structural)

### **Spatial Data**

- `point_attribute_pitch` - Vertical orientation (0.0 = down, 1.0 = up)
- `point_attribute_orientation` - Branch direction quaternions

### **Face Attributes**

- `face_attribute_branch_id` - Branch membership for each face
- `face_attribute_dead` - Dead wood identification
- `face_attribute_twig_*` - Twig placement markers (long, short, upward, dead)
- `face_attribute_end` - Branch end caps

## Implementation Status

### ✅ **Completed Optimizations**

1. **UV Aspect Ratio Correction**: Applied `model.apply_uv_aspect_ratio()` to both USD and FBX exports
2. **Enhanced UV Extraction**: Using `get_uvs_flat()` and `get_uv_islands_flat()` with proper error handling
3. **Physics-Based Weight Calculation**: 5-tier optimization system using Grove's physics data
4. **Coordinate System Control**: Applied `set_up_axis("Z")` and `set_winding_order("COUNTER_CLOCKWISE")`

### 🚧 **Partially Implemented**

1. **Face Direction Vectors**: `get_directions_flat()` extracted but not yet applied as vertex colors
2. **UV Islands**: Secondary UV map extracted but needs integration in USD export
3. **Native Grove Triangulation**: `model.triangulate()` called but validation needed

### 📋 **Available for Future Enhancement**

1. **Grove Native USD Export**: `gc.io.model_to_usda_string()` for full attribute preservation
2. **UVW Coordinates**: `get_uvws_flat()` for applications requiring W component
3. **Shape Variants**: `get_shape_as_tuples()` alternative geometry access
4. **Advanced Physics Combinations**: Multi-attribute weighting for vertex assignment

## Testing and Validation

### **UV Mapping Test**

```python
# Before fix: tiny repeated textures
# After fix: properly scaled textures with correct aspect ratio

# Test command
python generate_forest.py test.csv --quality ultra --formats fbx usda
```

### **Validation Points**

1. **Texture Scale**: Tree bark textures should appear at natural scale (not tiny/repeated)
2. **UV Coordinates**: Two UV maps available - primary and islands
3. **Coordinate System**: Z-up orientation for Blender/Unreal compatibility
4. **Physics Integration**: Vertex weights using Grove's mass/thickness/vigor data

## Grove API Documentation References

- **Model Class**: `docs/the_grove/the_grove_core.Model.md`
- **IO Module**: `docs/the_grove/the_grove_core.io.md`
- **Physics Attributes**: `src/the_grove_22/modules/the_grove_22_core/__init__.pyi`
- **Blender Integration**: `src/the_grove_22/addons/the_grove_22_in_blender/Operators/OperatorBuild.py`

## Usage Examples

### **Proper UV Application**

```python
# Extract and apply UV coordinates
model.apply_uv_aspect_ratio(2.0)  # Fix texture scaling
uvs = model.get_uvs_flat()
uv_islands = model.get_uv_islands_flat()

# Apply to Blender mesh
mesh.uv_layers.new(name="UVMap")
mesh.uv_layers.new(name="UVMapIslands")
```

### **Advanced Model Configuration**

```python
# Configure for optimal export
model.set_up_axis("Z")
model.set_winding_order("COUNTER_CLOCKWISE")
model.triangulate()

# Extract all data
points = model.get_points_flat()
faces = model.faces
uvs = model.get_uvs_flat()
directions = model.get_directions_flat()
```

### **Physics-Enhanced Export**

```python
# Use Grove's physics for intelligent vertex weighting
if hasattr(model, 'point_attribute_mass'):
    masses = model.point_attribute_mass
    # Apply mass-based bone weighting

if hasattr(model, 'point_attribute_thickness'):
    thickness = model.point_attribute_thickness  
    # Use for structural importance weighting
```

---

**UV Mapping Fixed and Grove API Enhanced**: Tree textures now display at proper scale with comprehensive Grove physics and geometry data integration.
