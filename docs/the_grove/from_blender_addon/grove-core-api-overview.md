# Grove Core API Overview (From Blender Addon Analysis)

Based on analysis of the Blender addon code at `src/the_grove_22/addons/the_grove_22_in_blender/`, this document outlines key Grove Core API usage patterns.

## Core Module Import Pattern

```python
from ..Core import import_core
the_grove_core = import_core()
```

The addon uses a core import function that handles platform-specific module loading with fallback:

```python
def import_core():
    try:
        return __import__("the_grove_22_core")
    except ImportError:
        return import_module(".Fallback", package=__package__)
```

## Key API Modules and Functions

### 1. Grove Simulation Core

**Grove Object Creation and Management:**
- `grove.simulate(steps)` - Simulate growth for specified number of steps
- `grove.set_properties(properties)` - Apply simulation properties to grove
- `grove.get_properties()` - Get current grove properties
- `grove.weigh_and_bend()` - Calculate weight and bending forces
- `grove.remember_orig_pos()` - Store original positions for transformations

**Properties Conversion:**
- `the_grove_core.io.properties_from_json_string(json_string)` - Convert JSON properties to core properties
- Properties are converted using a dictionary mapping in the addon's `Properties.py`

### 2. Serialization and I/O

**Grove Serialization:**
```python
# Save grove
data = the_grove_core.io.grove_to_json_string(grove)
compressed_data = gzip.compress(data.encode('utf-8'), compresslevel=1)
data_string = base64.b64encode(compressed_data).decode('utf-8')

# Load grove  
data = gzip.decompress(base64.b64decode(data_string)).decode('utf-8')
grove = the_grove_core.io.grove_from_json_string(data)
```

### 3. Multi-Grove Light Competition

**Shade Calculation for Multiple Groves:**
```python
# Create shade geometry from all groves
coords = []
for grove in groves:
    grove.set_properties(properties.convert_to_core_properties())
    coords.extend(grove.create_shade_geometry_coords())

# Apply shared shade calculation
for grove in groves:
    grove.calculate_shade_together(coords)
    grove.simulate(1)
```

### 4. 3D Model Building

**Mesh Generation:**
```python
models = grove.build_models({
    "resolution": properties.build_resolution,
    "resolution_reduce": properties.build_resolution_reduce,
    "texture_repeat": properties.texture_repeat,
    "build_cutoff_age": properties.build_cutoff_age,
    "build_cutoff_thickness": properties.build_cutoff_thickness,
    "build_blend": properties.build_blend,
    "build_end_cap": properties.build_end_cap,
})

# Optional triangulation
for model in models:
    model.triangulate()
```

**Model Data Access:**
- `model.get_points_as_tuples()` - Get vertex positions
- `model.faces` - Get face indices
- `model.get_uvs_flat()` - Get UV coordinates
- `model.get_directions_flat()` - Get face direction vectors
- Various attribute arrays: `point_attribute_age`, `face_attribute_dead`, etc.

### 5. Growth Animation Support

**Spring Shape Generation:**
```python
models_spring = grove.build_spring_shape({
    "resolution": properties.build_resolution,
    "resolution_reduce": properties.build_resolution_reduce,
    # ... other parameters
})
```

### 6. Environmental Interactions

**React Objects (Environmental Forces):**
```python
# Convert mesh to coordinate arrays for environmental interactions
def mesh_to_coords(obj, properties):
    coords = []
    obj.data.calc_loop_triangles()
    for triangle in obj.data.loop_triangles:
        for vert_index in triangle.vertices:
            co = environment_transform @ obj.data.vertices[vert_index].co / properties.simulation_scale
            coords.extend([co.x, co.y, co.z])
    return coords

# Apply environmental forces
grove.set_react_block_triangles_from_coords(coords)
grove.set_react_shade_triangles_from_coords(coords)
grove.set_react_attract_triangles_from_coords(coords)
grove.set_react_deflect_triangles_from_coords(coords)
```

### 7. Visual Debugging and Previews

**2D Sketch Generation:**
```python
m = bpy.context.area.spaces.active.region_3d.perspective_matrix
m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
(tri_strip, tri_strip_dead) = grove.build_sketch_2d(
    0, grove.get_properties().simulation_scale, m, 
    bpy.context.region.width, bpy.context.region.height
)
```

**Surround Preview:**
```python
(points, indices) = grove.build_surround_preview_2d(
    height, perspective_matrix, region_width, region_height
)
```

## Key Properties and Configuration

### Core Properties List (from Properties.py)
The addon defines 80+ core properties that are converted and passed to the Grove core:
- Simulation: `simulation_scale`
- Growth: `grow_nodes`, `grow_length`
- Branching: `add_side_branches`, `add_chance`, `add_angle`
- Physics: `bend_mass`, `bend_reaction`
- Shading: `shade_area`, `shade_branches`
- Pruning: `auto_prune_enabled`, `auto_prune_low`
- And many more...

### Property Conversion Pattern
```python
def convert_to_core_properties(self):
    properties_dictionary = {}
    for parameter in self.core_properties:
        if parameter in ['auto_prune_low', 'auto_prune_dangling', 'stake_height']:
            # Scale-dependent properties
            properties_dictionary[parameter] = getattr(self, parameter) / self.simulation_scale
        else:
            properties_dictionary[parameter] = getattr(self, parameter)
    
    json_string = json.dumps(properties_dictionary)
    return the_grove_core.io.properties_from_json_string(json_string)
```

## Architecture Insights

1. **Memory Management**: The addon uses careful memory management with garbage collection control during intensive operations
2. **Platform Compatibility**: Core module loading handles different platforms (Windows .pyd, macOS .so)
3. **Blender Integration**: Deep integration with Blender's data structures, modifiers, and animation system
4. **Multi-Species Support**: The "Grow Together" operator demonstrates how to simulate multiple grove species with shared light competition
5. **Performance Optimization**: Uses coordinate arrays instead of vector objects for better performance in shade calculations