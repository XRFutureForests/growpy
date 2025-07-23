# Grove Model Building System (From Blender Addon Analysis)

Based on analysis of `OperatorBuild.py` and related files, this document outlines the comprehensive 3D model building system used by Grove.

## Model Building Pipeline

### 1. Core Build Process

```python
def build(context, properties, grove, grove_collection, rebuild=False, root_id=-1, origin=None):
    # Clean previous builds
    if not properties.record_enabled:
        clean_record(grove_collection)
    clean_grove(grove_collection)
    
    # Update grove properties and physics
    if rebuild:
        grove.set_properties(properties.convert_to_core_properties())
        grove.weigh_and_bend()
    grove.remember_orig_pos()
    
    # Build 3D models
    models = grove.build_models(build_parameters)
    
    # Optional triangulation
    if properties.build_triangulate:
        for model in models:
            model.triangulate()
```

### 2. Build Parameters

The `build_models()` function accepts a comprehensive parameter dictionary:

```python
build_parameters = {
    "resolution": properties.build_resolution,              # Cross-section sides (4-24, default: 16)
    "resolution_reduce": properties.build_resolution_reduce, # Thickness-based reduction (0.0-1.0, default: 0.78)
    "texture_repeat": properties.texture_repeat,            # Texture repetitions (default: 3)
    "build_cutoff_age": properties.build_cutoff_age,       # Minimum age to build (default: 0)
    "build_cutoff_thickness": properties.build_cutoff_thickness, # Minimum thickness (default: 0.0)
    "build_blend": properties.build_blend,                 # Blend branch joints (default: True)
    "build_end_cap": properties.build_end_cap,            # Cap branch ends (default: True)
}
```

## Model Data Structure

### Geometry Access Methods
```python
# Vertex positions
points = model.get_points_as_tuples()
points_flat = model.get_points_flat()

# Face indices  
faces = model.faces

# UV coordinates
uvs_flat = model.get_uvs_flat()
uv_islands_flat = model.get_uv_islands_flat()

# Face direction vectors
directions_flat = model.get_directions_flat()
```

### Vertex Attributes
Models provide rich per-vertex and per-face attribute data:

**Point (Vertex) Attributes:**
- `point_attribute_age`: Age of each vertex
- `point_attribute_thickness`: Branch thickness at vertex
- `point_attribute_pitch`: Branch pitch angle
- `point_attribute_photosynthesis`: Photosynthesis efficiency
- `point_attribute_shade`: Shade level at vertex
- `point_attribute_vigor`: Growth vigor
- `point_attribute_bone_id`: Bone ID for skeletal animation

**Face Attributes:**
- `face_attribute_branch_id`: Branch identifier
- `face_attribute_branch_id_parent`: Parent branch identifier
- `face_attribute_dead`: Whether face represents dead wood
- `face_attribute_twig_long`: Long twig attachment points
- `face_attribute_twig_short`: Short twig attachment points  
- `face_attribute_twig_upward`: Upward twig attachment points
- `face_attribute_twig_dead`: Dead twig attachment points
- `face_attribute_end`: Branch end faces

### Model Properties
```python
# Model location in 3D space
location = Vector((model.location.x, model.location.y, model.location.z))

# Apply UV aspect ratio correction
model.apply_uv_aspect_ratio(properties.texture_aspect_ratio)
```

## Blender Mesh Creation

### Mesh Data Setup
```python
def create_tree_object(model, properties, context, roots=False):
    # Create Blender mesh
    mesh = bpy.data.meshes.new(str(properties.preset_name))
    mesh.from_pydata(
        model.get_points_as_tuples(), 
        [], 
        model.faces, 
        shade_flat=False
    )
    
    # Create Blender object
    obj = bpy.data.objects.new(str(properties.preset_name), mesh)
    obj.location = location * properties.simulation_scale
```

### Attribute Transfer
The system transfers all Grove attributes to Blender mesh attributes:

```python
# Transfer vertex attributes
mesh.attributes.new("gr_age", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_age)
mesh.attributes.new("gr_thickness", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_thickness)
mesh.attributes.new("gr_photosynthesis", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_photosynthesis)

# Transfer face attributes  
mesh.attributes.new("gr_branch_id", 'INT', 'FACE').data.foreach_set("value", model.face_attribute_branch_id)
mesh.attributes.new("gr_dead", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_dead)
mesh.attributes.new("gr_twig_long", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_long)

# Transfer UV coordinates
mesh.attributes.new("UVMap", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uvs_flat())
mesh.attributes.new("UVMapIslands", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uv_islands_flat())
```

## Growth Animation Support

### Spring Shape Generation
For growth animation, Grove generates "spring shapes" - compressed versions of new growth:

```python
models_spring = grove.build_spring_shape({
    "resolution": properties.build_resolution,
    "resolution_reduce": properties.build_resolution_reduce,
    # ... other parameters
})

def add_spring_shape(properties, model_spring, obj):
    # Add base shape key
    obj.shape_key_add(name='Base', from_mix=False)
    
    # Add spring shape key with compressed growth
    shape_key = obj.shape_key_add(name='SpringShape', from_mix=False).data
    shape = model_spring.get_points_flat()
    shape_key.foreach_set("co", shape)
    
    # Add spring UV map
    obj.data.attributes.new("UVMapSpring", 'FLOAT2', 'CORNER').data.foreach_set(
        "vector", model_spring.get_uvs_flat()
    )
```

### Animation Keyframing
The system automatically creates keyframes for smooth growth animation:

```python
# Keyframe spring shape values
channel = obj.data.shape_keys.key_blocks[-1]
channel.value = 1.0  # Start compressed
channel.keyframe_insert("value", frame=frame_last_year)
channel.value = 0.0  # End expanded
channel.keyframe_insert("value", frame=frame_this_year)
```

## Material System

### Bark Material Creation
```python
def create_bark_material(img, properties, context):
    bark_material = bpy.data.materials.new("TheGroveBranches")
    bark_material.use_nodes = True
    node_tree = bark_material.node_tree
    
    # Create shader nodes
    uv_node = node_tree.nodes.new('ShaderNodeAttribute')
    texture_node = node_tree.nodes.new('ShaderNodeTexImage')
    bark_normal_node = node_tree.nodes.new('ShaderNodeTexImage')
    normal_map_node = node_tree.nodes.new('ShaderNodeNormalMap')
    
    # Connect nodes for realistic bark shading
    node_tree.links.new(texture_node.inputs['Vector'], uv_node.outputs['Vector'])
    node_tree.links.new(normal_map_node.inputs['Color'], bark_normal_node.outputs['Color'])
```

### Thickness-Based Shading
The material system uses branch thickness for realistic shading:

```python
# Create thickness-based color mixing
attribute_node = node_tree.nodes.new('ShaderNodeAttribute')
attribute_node.attribute_name = 'gr_thickness'

# Invert thickness for color mixing
math_node = node_tree.nodes.new('ShaderNodeMath')
math_node.operation = 'SUBTRACT'
math_node.inputs[0].default_value = 1.0
node_tree.links.new(math_node.inputs[1], attribute_node.outputs['Fac'])
```

## Geometry Nodes Integration

### Modifiers Setup
Grove integrates with Blender's Geometry Nodes for advanced features:

```python
def create_geometry_nodes(properties, obj):
    node_trees = ['GroveGNScale', 'GroveGNTwig', 'GroveGNBreeze']
    
    for node_tree in node_trees:
        # Load geometry node group from external file
        with bpy.data.libraries.load(geometry_nodes_file) as (library_file, this_file):
            this_file.node_groups.append(library_file.node_groups[node_tree])
        
        # Add modifier to tree object
        modifier = obj.modifiers.new(type='NODES', name=node_tree.split('GroveGN')[1])
        modifier.node_group = bpy.data.node_groups[node_tree + grove_id]
```

### Twig System Integration
```python
def update_twigs(properties, grove_collection):
    for obj in tree_objects:
        if 'Twig' in obj.modifiers:
            mod = obj.modifiers['Twig']
            interface = mod.node_group.interface.items_tree
            
            # Update twig density
            mod[interface['Density'].identifier] = properties.twig_density
            
            # Set twig objects or collections
            if properties.do_twig_collections:
                mod[interface['Long Twig Collection'].identifier] = properties.twig_collection_long
            else:
                mod[interface['Long Twig'].identifier] = properties.twig_object_end
```

## Performance Optimizations

### Edition-Based Features
The system adapts features based on Grove edition:

```python
if context.preferences.addons[package].preferences.edition == 'STARTER':
    # Simplified building for starter edition
    models = grove.build_models(basic_parameters)
else:
    # Full feature set for professional edition
    models = grove.build_models(full_parameters)
    # Add advanced attributes
    mesh.attributes.new("gr_branch_id", 'INT', 'FACE')
```

### Memory Management
```python
def build(context, properties, grove, grove_collection, rebuild=False):
    disable_garbage_collection()
    try:
        # Perform intensive building operations
        models = grove.build_models(parameters)
        # ... create meshes and objects
    finally:
        enable_garbage_collection()
```

### Object Cleanup
```python
def clean_grove(grove_collection, roots=False):
    objects_to_delete = []
    
    for obj in grove_collection.objects:
        if obj.type == 'MESH' and 'grove' in obj.data:
            objects_to_delete.append(obj)
    
    # Remove objects and clean up unused mesh data
    for obj in objects_to_delete:
        mesh = obj.data
        grove_collection.objects.unlink(obj)
        bpy.data.objects.remove(obj)
        if not mesh.users:
            bpy.data.meshes.remove(mesh)
```

## Key Insights for GrowPy

1. **Attribute Rich Models**: Grove models contain extensive per-vertex and per-face attribute data beyond just geometry
2. **Multi-LOD Support**: The system supports multiple levels of detail through resolution parameters
3. **Animation Integration**: Built-in support for growth animation via shape keys and spring shapes
4. **Material Intelligence**: Materials use vertex attributes for procedural shading
5. **Geometry Nodes Ready**: Models are designed to work with Blender's Geometry Nodes system
6. **Performance Conscious**: Memory management and edition-based feature sets optimize performance