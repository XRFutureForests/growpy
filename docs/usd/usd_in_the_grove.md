# USD in The Grove - Core Implementation and Features

This document covers The Grove's native USD implementation, export capabilities, and Grove-specific USD features. This is the authoritative reference for how The Grove generates USD data, independent of target applications.

## Overview

The Grove Core provides comprehensive USD export functionality through the `the_grove_core.io` module. Each tree is exported as a complete USD scene with proper hierarchies, skeletal animation data, instancing primitives, and rich attribute information.

## Grove USD Export Architecture

### Core USD Functions

The Grove Core exposes these key USD functions:

```python
import the_grove_core as gc

# Convert a single tree model to USD
usda_string = gc.io.model_to_usda_string(model)

# Write directly to file
with open('tree.usda', 'w') as f:
    f.write(usda_string)
```

### Export Process Flow

1. **Simulation Complete**: Grove simulation generates tree structure data
2. **Model Building**: `Grove.build_models()` creates 3D geometry with attributes
3. **Skeleton Generation**: `Grove.build_skeletons()` creates bone hierarchies
4. **USD Conversion**: `model_to_usda_string()` exports to USD format
5. **File Output**: USD data written as .usda text files

## USD Scene Structure

### Grove USD Hierarchy

Each Grove tree exports with this standardized USD structure:

```
/TreeN (UsdGeomXform)
├── /TreeN/Geometry (UsdGeomMesh)
│   ├── Points, faces, UV coordinates
│   ├── Grove custom attributes (primvars)
│   └── Twig duplication triangles
├── /TreeN/Skeleton (UsdSkelSkeleton) 
│   ├── Joint hierarchy from Grove skeleton system
│   ├── Bind transforms and rest poses
│   └── Joint-to-geometry bindings
└── /TreeN/TwigInstances (UsdGeomPointInstancer)
    ├── Instance positions from twig triangles
    ├── Orientations from triangle normals
    ├── Prototype references to twig geometry
    └── Instance-specific attributes
```

### Transform Hierarchy

The Grove uses USD's transform system to position trees in world space:

```usda
def Xform "Tree0"
{
    # Grove automatically sets world transform
    matrix4d xformOp:transform = (
        (1, 0, 0, 0),
        (0, 1, 0, 0),
        (0, 0, 1, 0),
        (x, y, z, 1)  # Tree's grove position
    )
    uniform token[] xformOpOrder = ["xformOp:transform"]
}
```

## Coordinate System Management

### Up-Axis Configuration

The Grove Model class provides coordinate system conversion:

```python
# Set up-axis for target application
model.set_up_axis("Y")  # Houdini, Maya (Y-up)
model.set_up_axis("Z")  # Blender, Unreal Engine (Z-up)

# Export with proper coordinate system
usda_string = the_grove_core.io.model_to_usda_string(model)
```

### Winding Order

The Grove handles polygon winding order for different applications:

```python
# Set winding order for target application
model.set_winding_order("CLOCKWISE")        # Blender default
model.set_winding_order("COUNTER_CLOCKWISE") # Houdini, Maya, Unreal default
```

## Skeletal System USD Export

### Grove Skeleton to USD Schema

The Grove's skeletal system maps directly to USD's skeleton schema:

#### Grove Skeleton Structure

```python
# Grove skeleton data
skeleton = grove.build_skeletons()[0]
skeleton.points          # Joint positions [(x,y,z), ...]
skeleton.poly_lines      # Joint connectivity [[int], ...]
skeleton.location        # Skeleton root position (x,y,z)

# Advanced bone generation with optimization (Blender addon approach)
bones = grove.tag_bone_id(
    length_factor=2.0,     # Bone length multiplier for minimum bone size
    reduce_threshold=0.4,  # Thickness threshold for bone reduction (0.0-1.0)
    bias_factor=0.5,       # Bias toward trunk vs branches (0.0=trunk, 1.0=branches)
    connected=True         # Whether bones should be connected in hierarchy
)

# Bone data structure from Grove
for bone in bones:
    bone_id = bone[0]        # Unique bone identifier
    parent_id = bone[1]      # Parent bone ID (-1 for root)
    head_pos = bone[2]       # Bone head position (Vector)
    tail_pos = bone[3]       # Bone tail position (Vector)
    radius = bone[4]         # Bone radius for influence weighting
```

#### Skeleton Optimization Parameters

**Length Factor** (0.0-5.0): Controls minimum bone length relative to branch segments. Higher values create fewer, longer bones.

**Reduce Threshold** (0.0-1.0): Eliminates bones below thickness threshold. Reduces bone count by merging thin branches into thicker parents.

**Bias Factor** (0.0-1.0): Balances bone density - 0.0 favors trunk bones, 1.0 favors branch bones. 0.5 provides even distribution.

**Connected Bones**: When enabled, child bones connect directly to parent bone tails, creating continuous chains suitable for IK systems.

#### USD Skeleton Export

```usda
def Skeleton "Skeleton"
{
    # Joint names derived from Grove skeleton structure
    uniform token[] joints = [
        "Root",
        "Root/joint_0",
        "Root/joint_0/joint_1",
        "Root/joint_0/joint_1/joint_2"
    ]
    
    # Bind transforms from Grove skeleton.points
    uniform matrix4d[] bindTransforms = [
        # Computed from Grove joint positions
    ]
    
    # Rest transforms for local joint space
    uniform matrix4d[] restTransforms = [
        # Local space transforms
    ]
}
```

### Joint Attributes

Grove skeleton joints export with these USD attributes:

```usda
def Skeleton "Skeleton"
{
    # Grove-specific joint attributes
    int[] primvars:gr_skeleton_joint_id = [...] (
        interpolation = "varying"
    )
    float[] primvars:age = [...] (
        interpolation = "varying"
    )
    float[] primvars:mass = [...] (
        interpolation = "varying"
    )
    float[] primvars:radius = [...] (
        interpolation = "varying"
    )
}
```

### Skinning Data

The Grove automatically generates USD skinning data:

```usda
def Mesh "Geometry" (
    prepend apiSchemas = ["SkelBindingAPI"]
)
{
    # Skeleton binding
    rel skel:skeleton = </Tree0/Skeleton>
    
    # Joint indices (which joints influence each vertex)
    int[] primvars:skel:jointIndices = [...] (
        interpolation = "vertex"
    )
    
    # Joint weights (influence strength)
    float[] primvars:skel:jointWeights = [...] (
        interpolation = "vertex"
    )
    
    # Grove-specific: joint ID attribute for mapping
    int[] primvars:gr_skeleton_joint_id = [...] (
        interpolation = "vertex"
    )
}
```

## Wind Animation System

### Grove Wind Implementation

The Grove implements wind animation through shape keys and skeletal deformation, supporting both mesh deformation and bone-based animation systems:

#### Wind Shape Generation

```python
# Generate wind shapes for animation
wind_vector = the_grove_core.Vector(0.5, 0.0, 0.0)  # Wind direction
wind_shapes = grove.build_wind_shape({
    "resolution": 32,
    "resolution_reduce": 0.8,
    "texture_repeat": 1.0,
    "build_cutoff_age": 0,
    "build_blend": True,
    "build_end_cap": True
}, 
shape_count=50,        # Number of wind frames
current_shape=0,       # Current shape index
wind_vector,           # Wind direction vector
turbulence=1.0)        # Wind strength/turbulence
```

#### Skeletal Wind Deformation

The Grove applies wind through bone-based noise systems:

```python
# Apply wind noise to skeleton bones
for bone in skeleton_bones:
    # Calculate flexibility based on bone radius
    flexibility = bone.radius ** 0.9
    flexibility = 1.0 / flexibility / 100.0
    
    # Wind deformation strength modulated by branch thickness
    deform_strength = flexibility * turbulence_factor
    
    # Apply noise with bone-specific parameters
    noise_frequency = 17.0 * (1.0 / flexibility) ** 0.3
    noise_strength = deform_strength
    noise_phase = random_phase  # Unique per bone for variation
```

#### Wind Animation Parameters

**Shape Count** (10-240): Number of wind animation frames. More shapes provide smoother animation but increase memory usage.

**Turbulence** (0.0-5.0): Wind strength multiplier. Higher values create more dramatic movement.

**Wind Vector**: 2D direction vector controlling primary wind direction. X and Y components define horizontal wind direction.

**Frequency Modulation**: Thin branches receive higher frequency noise for realistic flutter, thick branches get lower frequency for stability.

#### USD Wind Export

Wind animation exports as time-varying geometry:

```usda
def Mesh "Geometry"
{
    # Base geometry at rest pose
    point3f[] points = [...] (
        timeSamples = {
            0: [/* rest positions */],
            1: [/* wind frame 1 */],
            2: [/* wind frame 2 */],
            # ... additional wind frames
        }
    )
    
    # Wind-specific attributes
    float primvars:wind_strength = 1.0
    vector3f primvars:wind_direction = (0.5, 0.0, 0.0)
    float primvars:turbulence_frequency = 17.0
}
```

## Twig Instancing System

### Grove Twig Distribution

The Grove generates twig instances from specialized geometry using a sophisticated triangle-based duplication system:

#### Twig Classification System

Grove supports four distinct twig types with specific botanical functions:

- **Long Twigs** (`twig_long`): Primary lateral branches, typically apical/terminal twigs
- **Short Twigs** (`twig_short`): Secondary lateral branches, side/lateral twigs  
- **Upward Twigs** (`twig_upward`): Vertical growth twigs for light competition
- **Dead Twigs** (`twig_dead`): Deceased branches, adds realism to mature trees

#### Twig Triangle Generation

```python
# Grove creates twig duplication triangles during model building
model = grove.build_models()[0]

# Twig triangles are marked with face attributes
model.face_attribute_twig_long    # Boolean array for long twigs
model.face_attribute_twig_short   # Boolean array for short twigs  
model.face_attribute_twig_upward  # Boolean array for upward twigs
model.face_attribute_twig_dead    # Boolean array for dead twigs

# Triangle normals determine twig orientation
model.face_attribute_direction    # Original growth direction per face
```

#### Twig Density and Distribution

Twig placement is controlled by density parameters and biological constraints:

```python
# Twig density controls instance count
twig_density = 0.75  # Range 0.0-1.0, affects overall twig population

# Biological distribution factors
branch_age_threshold = 2     # Minimum branch age for twig placement
branch_thickness_min = 0.05  # Minimum thickness for twig support
light_exposure_factor = 0.8  # Light-dependent twig distribution
```

#### Twig Naming Convention

Grove uses standardized naming for twig identification:

- Lateral twigs: Names containing "lateral", "side", "short"
- Apical twigs: Names containing "apical", "end", "long"
- Upward twigs: Names containing "upward", "vertical"
- Dead twigs: Names containing "dead"
- Generic twigs: Names containing "twig" (used for both long and short if no specific type found)

#### Twig Geometry Creation

```python
# Grove creates twig duplication triangles during model building
model = grove.build_models()[0]

# Twig triangles are marked with face attributes
model.face_attribute_twig_long    # Boolean array for long twigs
model.face_attribute_twig_short   # Boolean array for short twigs  
model.face_attribute_twig_upward  # Boolean array for upward twigs
model.face_attribute_twig_dead    # Boolean array for dead twigs
```

#### USD PointInstancer Export

Grove converts twig triangles to USD PointInstancer:

```usda
def PointInstancer "TwigInstances"
{
    # Instance positions (triangle centers)
    point3f[] positions = [
        # Computed from twig triangle centroids
    ]
    
    # Instance orientations (from triangle normals)
    quath[] orientations = [
        # Quaternions from triangle normal directions
    ]
    
    # Instance scales (uniform or varied)
    float3[] scales = [
        # Scale factors per instance
    ]
    
    # Prototype selection (which twig type)
    int[] protoIndices = [
        # Index into prototypes array
        0, 1, 0, 2, 3, 1  # 0=long, 1=short, 2=upward, 3=dead
    ]
    
    # References to twig prototypes  
    rel prototypes = [
        </TwigPrototypes/TwigLong>,
        </TwigPrototypes/TwigShort>,
        </TwigPrototypes/TwigUpward>,
        </TwigPrototypes/TwigDead>
    ]
    
    # Grove-specific instance attributes
    float[] primvars:age = [...] (
        interpolation = "varying"
    )
    float[] primvars:vigor = [...] (
        interpolation = "varying"  
    )
    bool[] primvars:dead = [...] (
        interpolation = "varying"
    )
    vector3f[] primvars:direction = [...] (
        interpolation = "varying"
    )
}
```

### Twig Prototype Management

Grove supports external twig references:

```usda
# Separate twig prototype definitions
def "TwigPrototypes"
{
    def Mesh "TwigLong" (
        prepend references = @./twigs/long_twig.usda@
    )
    {
        # External twig geometry file
    }
    
    def Mesh "TwigShort" (
        prepend references = @./twigs/short_twig.usda@
    )
    {
        # Different twig variation
    }
}
```

## Grove Attribute System

### Model Attributes to USD Primvars

The Grove's rich attribute system maps to USD primvars:

#### Point Attributes (Vertex Data)

```usda
def Mesh "Geometry"
{
    # Grove point attributes → USD vertex primvars
    int[] primvars:age = [...] (
        interpolation = "vertex"
        doc = "Number of cycles/years the node has existed"
    )
    
    float[] primvars:mass = [...] (
        interpolation = "vertex"
        doc = "Mass of branch continuation and sub-branches"
    )
    
    float[] primvars:thickness = [...] (
        interpolation = "vertex"
        doc = "Diameter mapped to 0.0-1.0 range"
    )
    
    float[] primvars:vigor = [...] (
        interpolation = "vertex"
        doc = "Growth power of the branch"
    )
    
    float[] primvars:photosynthesis = [...] (
        interpolation = "vertex"
        doc = "Combined photosynthesis value"
    )
    
    float[] primvars:shade = [...] (
        interpolation = "vertex"
        doc = "Ambient occlusion (0.0=exposed, 1.0=shaded)"
    )
    
    float[] primvars:pitch = [...] (
        interpolation = "vertex"
        doc = "Vertical orientation (0.0=down, 0.5=horizontal, 1.0=up)"
    )
    
    # Orientation as quaternions
    quatf[] primvars:orientation = [...] (
        interpolation = "vertex"
        doc = "Branch/twig orientation quaternion"
    )
}
```

#### Face Attributes (Primitive Data)

```usda
def Mesh "Geometry"
{
    # Grove face attributes → USD primitive primvars
    int[] primvars:tree_index = [...] (
        interpolation = "face"
        doc = "Tree index when multiple trees in one mesh"
    )
    
    int[] primvars:branch_index = [...] (
        interpolation = "face"
        doc = "Branch identification number"
    )
    
    int[] primvars:branch_index_parent = [...] (
        interpolation = "face"
        doc = "Parent branch identification"
    )
    
    bool[] primvars:dead = [...] (
        interpolation = "face"
        doc = "Whether branch is dead"
    )
    
    bool[] primvars:end = [...] (
        interpolation = "face"
        doc = "Branch end cap polygons"
    )
    
    # Twig duplication markers
    bool[] primvars:twig_long = [...] (
        interpolation = "face"
    )
    
    bool[] primvars:twig_short = [...] (
        interpolation = "face"
    )
    
    bool[] primvars:twig_upward = [...] (
        interpolation = "face"
    )
    
    bool[] primvars:twig_dead = [...] (
        interpolation = "face"
    )
    
    # Growth direction vectors
    vector3f[] primvars:direction = [...] (
        interpolation = "face"
        doc = "Original growth direction before deformation"
    )
}
```

## UV Coordinate System

### Grove UV Generation

The Grove generates UV coordinates with specific features:

```python
# UV coordinate access in Grove
model = grove.build_models()[0]

# Get UV data in different formats
uvs_nested = model.uvs                    # List of (u,v) tuples
uvs_flat = model.get_uvs_flat()           # Flat [u1,v1,u2,v2,...] array
uvws_flat = model.get_uvws_flat()         # With W component [u1,v1,w1,...]

# UV aspect ratio adjustment for bark textures
model.apply_uv_aspect_ratio(2.0)  # For 2:1 aspect ratio texture
```

### USD UV Export

Grove UV coordinates export as standard USD primvars:

```usda
def Mesh "Geometry"
{
    # UV coordinates as faceVarying primvars
    texCoord2f[] primvars:st = [
        # UV coordinates for each face vertex
    ] (
        interpolation = "faceVarying"
    )
    
    # UV islands for texture atlasing
    int[] primvars:uv_islands = [...] (
        interpolation = "faceVarying" 
        doc = "UV island identification for atlas textures"
    )
}
```

## Material System

### Grove Material Attributes

The Grove can export material information through USD Preview Surface:

```usda
def Material "BarkMaterial"
{
    token outputs:surface.connect = </BarkMaterial/PreviewSurface.outputs:surface>
    
    def Shader "PreviewSurface"
    {
        uniform token info:id = "UsdPreviewSurface"
        
        # Base material properties
        color3f inputs:diffuseColor = (0.6, 0.4, 0.2)
        float inputs:roughness = 0.8
        float inputs:metallic = 0.0
        float inputs:specular = 0.5
        
        # Texture connections
        asset inputs:diffuseColor.connect = </BarkMaterial/BarkTexture.outputs:rgb>
        asset inputs:normal.connect = </BarkMaterial/NormalTexture.outputs:rgb>
        asset inputs:roughness.connect = </BarkMaterial/RoughnessTexture.outputs:r>
    }
    
    # Bark diffuse texture
    def Shader "BarkTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bark_diffuse.jpg@
        token inputs:sourceColorSpace = "sRGB"
        float2 inputs:st.connect = </BarkMaterial/PrimvarReader.outputs:result>
    }
    
    # Normal map texture  
    def Shader "NormalTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bark_normal.jpg@
        token inputs:sourceColorSpace = "raw"
        float2 inputs:st.connect = </BarkMaterial/PrimvarReader.outputs:result>
    }
    
    # UV coordinate reader
    def Shader "PrimvarReader"
    {
        uniform token info:id = "UsdPrimvarReader_float2"
        token inputs:varname = "st"
    }
}
```

### Attribute-Driven Materials

Grove attributes can drive material parameters:

```usda
def Shader "AttributeDrivenShader"
{
    uniform token info:id = "UsdPreviewSurface"
    
    # Use Grove age attribute to drive material color
    color3f inputs:diffuseColor.connect = </Materials/AgeColorRamp.outputs:result>
    
    # Use health/vigor for material properties
    float inputs:roughness.connect = </Materials/HealthRoughness.outputs:result>
}

def Shader "AgeColorRamp"
{
    # Custom shader that reads Grove age attribute
    uniform token info:id = "grove:AgeColorRamp"
    token inputs:ageAttribute = "age"
    color3f inputs:youngColor = (0.4, 0.8, 0.2)
    color3f inputs:oldColor = (0.6, 0.4, 0.2)
}
```

## Blender Addon Implementation Details

### Geometry Nodes Integration

The Grove Blender addon uses Geometry Nodes for advanced twig instancing and scaling:

#### Twig Geometry Nodes System

```python
# Grove creates three main geometry node systems
node_trees = ['GroveGNScale', 'GroveGNTwig', 'GroveGNBreeze']

# Each tree gets unique node groups per grove
grove_id = str(properties.unique_id)
for node_tree in node_trees:
    unique_name = node_tree + grove_id
    modifier = obj.modifiers.new(type='NODES', name=node_tree.split('GroveGN')[1])
    modifier.node_group = bpy.data.node_groups[unique_name]
```

#### Twig Modifier Parameters

The Grove exposes these parameters through Geometry Nodes:

- **Use Collections**: Toggle between object and collection-based twig instancing
- **Density**: Controls twig population (0.0-1.0)
- **Long Twig Collection/Object**: Primary twig prototypes
- **Short Twig Collection/Object**: Secondary twig prototypes  
- **Upward Twig Collection/Object**: Vertical growth twig prototypes
- **Dead Twig Collection/Object**: Dead branch twig prototypes
- **Hide Twigs**: Viewport visibility toggle for performance

#### Scale Modifier System

```python
# Scale modifier interface parameters
scale_interface = scale_modifier.node_group.interface.items_tree
scale_modifier[scale_interface['Scale'].identifier] = simulation_scale

# Applies to both tree geometry and skeleton
if 'grove_skeleton' in skeleton_object:
    skeleton_object.scale = (scale, scale, scale)
```

### Skeletal Animation Implementation

#### Armature Creation Process

```python
# Create Blender armature from Grove skeleton data
skeleton = bpy.data.armatures.new('Skeleton')
skeleton.display_type = 'STICK'
armature_obj = bpy.data.objects.new(skeleton.name, skeleton)
armature_obj['grove_skeleton'] = True  # Grove identification tag

# Build bone hierarchy
bpy.ops.object.mode_set(mode='EDIT', toggle=False)
edit_bones = armature_obj.data.edit_bones

for i, bone_data in enumerate(bones):
    bone = edit_bones.new(str(i))
    bone.head = bone_data[2].as_tuple()  # Head position
    bone.tail = bone_data[3].as_tuple()  # Tail position
    bone.head_radius = bone_data[4]      # Head radius
    bone.tail_radius = bone_data[4]      # Tail radius
    
    # Set parent relationship
    parent_bone_name = str(bone_data[1])
    if parent_bone_name in edit_bones:
        bone.parent = edit_bones[parent_bone_name]
```

#### Vertex Group Assignment

```python
# Convert Grove bone_id attribute to Blender vertex groups
bone_data = tree_object.data.attributes["gr_bone_id"].data
values = np.empty(len(tree_object.data.vertices), dtype=np.int32)
bone_data.foreach_get("value", values)

# Create vertex group for each bone
for i in range(len(bones)):
    vertex_group = tree_object.vertex_groups.new(name=str(i))
    indices = np.where(values == i)[0]
    vertex_group.add(indices.tolist(), 1.0, 'REPLACE')

# Apply armature modifier
armature_modifier = tree_object.modifiers.new(name="Skeleton", type='ARMATURE')
armature_modifier.object = armature_obj
```

### Wind Animation Implementation

#### Shape Key Animation System

```python
# Wind animation through shape keys
tree_object.shape_key_add(name='Base', from_mix=False)  # Rest pose

# Generate wind shapes
for shape_index in range(shape_count):
    wind_models = grove.build_wind_shape(
        build_params, shape_count, shape_index, wind_vector, turbulence)
    
    # Add shape key for this wind frame
    shape_key = tree_object.shape_key_add(name='WindShape', from_mix=False)
    flat_data = np.array(wind_models[0].get_shape_as_tuples()).ravel()
    shape_key.data.foreach_set("co", flat_data)
    
    # Keyframe animation with interval timing
    channel = tree_object.data.shape_keys.key_blocks[-1]
    channel.value = 1.0
    channel.keyframe_insert("value", frame=shape_index * interval)
    channel.value = 0.0
    channel.keyframe_insert("value", frame=shape_index * interval - width)
    channel.keyframe_insert("value", frame=shape_index * interval + width)
```

#### Blender Skeletal Wind System

```python
# Apply wind through bone noise modifiers
bpy.ops.object.mode_set(mode='POSE')

for bone in armature_obj.pose.bones:
    bone.rotation_mode = 'XYZ'
    
    # Calculate flexibility based on bone radius
    flexibility = bone.bone.head_radius ** 0.9
    flexibility = 1.0 / flexibility / 100.0
    deform_strength = flexibility * turbulence
    
    # Insert keyframes for each rotation axis
    for axis in range(3):  # X, Y, Z
        bone.keyframe_insert(data_path="rotation_euler", frame=1, index=axis)
    
    # Apply noise modifiers to f-curves
    for curve in armature_obj.animation_data.action.fcurves:
        if curve.data_path == bone.path_from_id("rotation_euler"):
            noise_mod = curve.modifiers.new(type='NOISE')
            noise_mod.scale = 17.0 * (1.0 / flexibility) ** 0.3  # Higher frequency for thin branches
            noise_mod.strength = deform_strength
            noise_mod.phase = random.uniform(0, 20 * 3.14159)  # Random phase per bone
```

### Attribute System Implementation

#### Grove Attribute Export

```python
# Export Grove attributes as Blender mesh attributes
mesh.attributes.new("gr_thickness", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_thickness)
mesh.attributes.new("gr_pitch", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_pitch)
mesh.attributes.new("gr_photosynthesis", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_photosynthesis)
mesh.attributes.new("gr_shade", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_shade)
mesh.attributes.new("gr_vigor", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_vigor)
mesh.attributes.new("gr_bone_id", 'INT', 'POINT').data.foreach_set("value", model.point_attribute_bone_id)

# Face attributes for twig marking
mesh.attributes.new("gr_twig_long", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_long)
mesh.attributes.new("gr_twig_short", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_short)
mesh.attributes.new("gr_twig_upward", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_upward)
mesh.attributes.new("gr_twig_dead", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_dead)
mesh.attributes.new("gr_end", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_end)
mesh.attributes.new("gr_direction", 'FLOAT_VECTOR', 'FACE').data.foreach_set("vector", model.get_directions_flat())

# UV coordinates
mesh.attributes.new("UVMap", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uvs_flat())
mesh.attributes.new("UVMapIslands", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uv_islands_flat())
```

#### Material Index Assignment

```python
# Assign material indices based on geometry type
material_indices = []
for face_index in range(len(model.faces)):
    if model.face_attribute_twig_long[face_index]:
        material_indices.append(1)  # Long twig material
    elif model.face_attribute_twig_short[face_index]:
        material_indices.append(2)  # Short twig material
    elif model.face_attribute_twig_upward[face_index]:
        material_indices.append(3)  # Upward twig material
    elif model.face_attribute_twig_dead[face_index]:
        material_indices.append(4)  # Dead twig material
    else:
        material_indices.append(0)  # Branch material

mesh.polygons.foreach_set("material_index", material_indices)
```

## Animation and Time-Varying Data

### Growth Animation Export

The Grove can export time-varying geometry for growth animation:

```python
# Export growth animation
grove = the_grove_core.Grove()
grove.simulate(1)  # Start state

# Record growth over time
growth_frames = []
for year in range(1, 11):  # 10 years of growth
    grove.simulate(1)
    models = grove.build_models()
    growth_frames.append(models[0])

# Export time-varying USD
# (Implementation would require custom time-sampling export)
```

#### Time-Sampled USD Data

```usda
def Mesh "Geometry"
{
    # Time-varying points for growth
    point3f[] points.timeSamples = {
        1: [...],   # Year 1 geometry
        24: [...],  # Year 2 geometry  
        48: [...],  # Year 3 geometry
    }
    
    # Time-varying face connectivity
    int[] faceVertexIndices.timeSamples = {
        1: [...],   # Year 1 topology
        24: [...],  # Year 2 topology
        48: [...],  # Year 3 topology
    }
    
    # Time-varying attributes
    float[] primvars:age.timeSamples = {
        1: [...],   # Age values year 1
        24: [...],  # Age values year 2
        48: [...],  # Age values year 3
    }
}
```

### Wind Animation Export

The Grove skeleton system supports wind animation export:

```usda
def Skeleton "Skeleton"
{
    # Animated joint transforms for wind
    matrix4d[] jointTransforms.timeSamples = {
        1: [...],   # Rest pose
        2: [...],   # Wind frame 1
        3: [...],   # Wind frame 2
        50: [...],  # Wind cycle
        51: [...]   # Loop back to start
    }
}
```

## Multi-Tree USD Export

### Forest Scene Assembly

The Grove supports exporting multiple trees to a single USD scene:

```python
# Create forest with multiple trees
grove = the_grove_core.Grove()

# Add multiple trees at different positions
grove.add_new_tree(
    the_grove_core.Vector(0.0, 0.0, 0.0),    # Position
    the_grove_core.Vector(0.0, 0.0001, 0.1),  # Direction
    0  # Growth delay
)

grove.add_new_tree(
    the_grove_core.Vector(5.0, 0.0, 0.0),    # Position
    the_grove_core.Vector(0.0, 0.0001, 0.1),  # Direction  
    0  # Growth delay
)

# Simulate and build all trees
grove.simulate(30)
models = grove.build_models()

# Export each tree separately, then combine
for i, model in enumerate(models):
    usda_string = the_grove_core.io.model_to_usda_string(model)
    with open(f'tree_{i}.usda', 'w') as f:
        f.write(usda_string)
```

### Forest USD Assembly

```usda
#usda 1.0

def Xform "Forest"
{
    # Reference individual trees
    def "Tree0" (
        prepend references = @./tree_0.usda@
    )
    {
        # Tree 0 positioned at origin
        matrix4d xformOp:transform = (
            (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)
        )
    }
    
    def "Tree1" (
        prepend references = @./tree_1.usda@
    )
    {
        # Tree 1 positioned offset
        matrix4d xformOp:transform = (
            (1,0,0,0), (0,1,0,0), (0,0,1,0), (5,0,0,1)
        )
    }
    
    # Additional trees...
}
```

## Grove USD Metadata

### Custom USD Metadata

The Grove can embed custom metadata in USD files:

```usda
def Xform "Tree0" (
    customData = {
        dictionary grove = {
            string version = "22.0"
            string species = "Oak"
            int simulation_years = 30
            float simulation_scale = 1.0
            dictionary growth_parameters = {
                float grow_nodes = 3.0
                float grow_length = 0.8
                float add_chance = 0.4
                # ... other Grove parameters
            }
        }
    )
    doc = "Grove tree exported from simulation"
)
```

### Version and Compatibility

```usda
#usda 1.0
(
    customLayerData = {
        dictionary grove = {
            string exporter = "the_grove_core"
            string version = "22.0"
            string export_date = "2025-07-24"
            bool has_skeleton = true
            bool has_instances = true
            string coordinate_system = "Z_UP"
            string winding_order = "COUNTER_CLOCKWISE"
        }
    }
    doc = "Grove USD export with full feature set"
)
```

## Performance Optimizations

### Efficient USD Generation

The Grove optimizes USD export for performance:

#### Lazy Evaluation

```python
# Grove builds geometry only when needed
grove.simulate(30)  # Simulation is lightweight
models = grove.build_models()  # Geometry built on demand
usda_string = the_grove_core.io.model_to_usda_string(models[0])  # USD on demand
```

#### Memory Management

```python
# Efficient data access
model = grove.build_models()[0]

# Flat arrays for performance
points_flat = model.get_points_flat()      # [x,y,z,x,y,z,...]
uvs_flat = model.get_uvs_flat()           # [u,v,u,v,...]
directions_flat = model.get_directions_flat()  # [x,y,z,x,y,z,...]
```

#### Instancing Optimization

- Grove creates minimal twig prototype geometry
- Thousands of instances reference single prototypes
- Instance attributes stored efficiently in arrays
- Automatic culling support through USD PointInstancer

## File Format Considerations

### USDA vs USDC

The Grove exports USD ASCII (.usda) format by default:

**Advantages of USDA:**

- Human readable and editable
- Version control friendly
- Debugging and inspection
- Cross-platform compatibility

**Converting to USDC:**

```bash
# Convert to binary format for production
usdcat tree.usda -o tree.usdc
```

### File Size Optimization

For large forests, consider:

1. **External References**: Use USD references for shared geometry
2. **Payload System**: USD payloads for on-demand loading
3. **Compression**: USDC binary format with compression
4. **LOD Systems**: Multiple detail levels in single USD

## Integration Examples

### Basic Export Workflow

```python
import the_grove_core as gc

# Create and simulate tree
grove = gc.Grove()
grove.simulate(25)

# Build model with proper settings
models = grove.build_models()
model = models[0]

# Configure for target application
model.set_up_axis("Z")  # For Blender/Unreal
model.set_winding_order("COUNTER_CLOCKWISE")

# Export to USD
usda_content = gc.io.model_to_usda_string(model)

# Write to file
with open('grove_tree.usda', 'w') as f:
    f.write(usda_content)
```

### Batch Forest Export

```python
import the_grove_core as gc
import os

def export_forest(grove, output_dir, name_prefix="tree"):
    """Export all trees in grove to separate USD files"""
    
    models = grove.build_models()
    skeletons = grove.build_skeletons()
    
    os.makedirs(output_dir, exist_ok=True)
    
    tree_files = []
    for i, model in enumerate(models):
        # Configure model
        model.set_up_axis("Z")
        model.set_winding_order("COUNTER_CLOCKWISE")
        
        # Export to USD
        usda_content = gc.io.model_to_usda_string(model)
        
        # Write file
        filename = f"{name_prefix}_{i:03d}.usda"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(usda_content)
            
        tree_files.append(filename)
    
    # Create master scene file
    create_forest_scene(output_dir, tree_files)
    
    return tree_files

def create_forest_scene(output_dir, tree_files):
    """Create master USD scene referencing all trees"""
    
    scene_content = "#usda 1.0\n\n"
    scene_content += 'def Xform "Forest"\n{\n'
    
    for i, tree_file in enumerate(tree_files):
        scene_content += f'    def "Tree{i:03d}" (\n'
        scene_content += f'        prepend references = @./{tree_file}@\n'
        scene_content += '    )\n    {\n'
        scene_content += '        # Transform can be modified here\n'
        scene_content += '    }\n\n'
    
    scene_content += '}\n'
    
    with open(os.path.join(output_dir, 'forest.usda'), 'w') as f:
        f.write(scene_content)

# Usage
grove = gc.Grove()
grove.simulate(30)
export_forest(grove, './forest_export')
```

## Best Practices

### File Organization

```
project/
├── scenes/
│   └── forest.usda          # Master scene
├── trees/
│   ├── oak_001.usda         # Individual trees
│   ├── oak_002.usda
│   └── pine_001.usda
├── twigs/
│   ├── oak_twig.usda        # Twig prototypes
│   └── pine_needle.usda
├── materials/
│   ├── oak_bark.usda        # Material definitions
│   └── pine_bark.usda
└── textures/
    ├── oak_bark_diffuse.jpg # Texture assets
    ├── oak_bark_normal.jpg
    └── pine_bark_diffuse.jpg
```

### Naming Conventions

- Use descriptive names: `Oak_Mature_25Years` not `Tree_001`
- Include species and age information in USD metadata
- Use consistent coordinate system across all exports
- Document Grove version and parameters in USD metadata

### Performance Guidelines

1. **Instance Management**: Keep twig prototype count reasonable (< 10 types)
2. **Attribute Optimization**: Only export needed Grove attributes
3. **Coordinate Systems**: Set up-axis once before export
4. **File References**: Use USD references for shared assets
5. **Validation**: Test USD files with `usdview` before production use

## Level of Detail (LOD) System

Grove provides comprehensive LOD capabilities that map effectively to USD's VariantSet system for optimal performance across different rendering contexts.

### Grove LOD Parameters

Grove includes several parameters that control geometric complexity and viewport optimization:

#### Build Resolution Controls

```python
# Primary resolution parameters
build_resolution: int = 16        # Range: 3-64, controls mesh complexity
build_resolution_reduce: float = 0.78  # Polygon reduction factor (0.0-1.0)

# Usage in Grove Core API
model.set_resolution(build_resolution)
model.apply_reduction(build_resolution_reduce)
```

#### Viewport Optimization

```python
# Twig detail optimization
twig_view_detail: float = 0.3     # Controls twig decimation for viewport (0.0-1.0)

# Automatic decimation system
def set_view_detail(detail_level):
    """Apply Decimate modifiers for viewport optimization"""
    for twig_object in twig_objects:
        decimate_modifier = twig_object.modifiers.new("Decimate", 'DECIMATE')
        decimate_modifier.ratio = detail_level
        decimate_modifier.use_collapse_triangulate = True
```

#### Resolution Impact

- **Low Resolution (3-8)**: Minimal polygons, suitable for distant objects
- **Medium Resolution (16-32)**: Balanced detail and performance
- **High Resolution (48-64)**: Maximum detail for close-up rendering

### USD LOD Integration Strategy

Grove's LOD system should be implemented using USD VariantSets to provide multiple detail levels that work seamlessly across Blender and Unreal Engine:

#### VariantSet Structure

```usda
def Xform "TreeAsset" (
    variants = {
        string lodVariant = "High"
    }
    prepend variantSets = "lodVariant"
    customData = {
        dictionary grove = {
            string species = "Oak"
            int age = 25
            string version = "Grove_2.2"
        }
    }
) {
    variantSet "lodVariant" = {
        "High" {
            # build_resolution: 64, twig_view_detail: 1.0
            def Mesh "Trunk" {
                # Full resolution trunk geometry
                int[] faceVertexCounts = [...]  # Dense mesh
                point3f[] points = [...]        # Full vertex data
            }
            def "Twigs" {
                # Full twig density with all instances
                def "TwigInstancer" (
                    prepend apiSchemas = ["PointInstancer"]
                ) {
                    int[] protoIndices = [...]  # All twig instances
                    point3f[] positions = [...] # Full density placement
                }
            }
        }
        "Medium" {
            # build_resolution: 32, twig_view_detail: 0.5
            def Mesh "Trunk" {
                # Reduced resolution trunk
                int[] faceVertexCounts = [...]  # 50% polygon reduction
                point3f[] points = [...]        # Simplified geometry
            }
            def "Twigs" {
                # Reduced twig count
                def "TwigInstancer" (
                    prepend apiSchemas = ["PointInstancer"]
                ) {
                    int[] protoIndices = [...]  # Culled instances
                    point3f[] positions = [...] # Reduced density
                }
            }
        }
        "Low" {
            # build_resolution: 8, twig_view_detail: 0.1
            def Mesh "Trunk" {
                # Minimal detail trunk
                int[] faceVertexCounts = [...]  # Basic cylinder
                point3f[] points = [...]        # Essential vertices only
            }
            def "Twigs" {
                # Essential twigs only
                def "TwigInstancer" (
                    prepend apiSchemas = ["PointInstancer"]
                ) {
                    int[] protoIndices = [...]  # Critical instances only
                    point3f[] positions = [...] # Sparse placement
                }
            }
        }
        "Proxy" {
            # Ultra-low detail for very distant viewing
            def Mesh "Billboard" {
                # Simple quad with tree texture
                int[] faceVertexCounts = [4]
                point3f[] points = [(-1,0,-1), (1,0,-1), (1,0,1), (-1,0,1)]
                texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)]
            }
        }
    }
}
```

#### LOD Variant Benefits

1. **Performance Scaling**: Automatic performance optimization based on camera distance
2. **Memory Efficiency**: Load only required detail level, reducing memory usage
3. **Cross-Platform Compatibility**: Works with both Blender and Unreal Engine LOD systems
4. **Skeletal Consistency**: All LOD levels maintain identical skeletal structure for animation
5. **Artist Control**: Manual LOD selection available for specific use cases

#### Implementation Workflow

```python
def export_grove_with_lod(grove, output_path, lod_levels=[8, 16, 32, 64]):
    """Export Grove tree with multiple LOD levels as USD VariantSet"""
    
    import the_grove_core as gc
    
    # Create base USD structure
    usda_content = "#usda 1.0\n\n"
    usda_content += 'def Xform "TreeAsset" (\n'
    usda_content += '    variants = {\n'
    usda_content += '        string lodVariant = "High"\n'
    usda_content += '    }\n'
    usda_content += '    prepend variantSets = "lodVariant"\n'
    usda_content += ') {\n'
    usda_content += '    variantSet "lodVariant" = {\n'
    
    lod_names = ["Proxy", "Low", "Medium", "High"]
    
    for i, resolution in enumerate(lod_levels):
        lod_name = lod_names[min(i, len(lod_names)-1)]
        
        # Build model with specific resolution
        model = grove.build_models(resolution=resolution)[0]
        model.set_up_axis("Z")
        
        # Generate LOD-specific geometry
        usda_content += f'        "{lod_name}" {{\n'
        
        # Add model geometry to variant
        model_usda = gc.io.model_to_usda_string(model)
        
        # Extract geometry content (skip headers)
        geometry_lines = model_usda.split('\n')[2:]  # Skip #usda header
        for line in geometry_lines:
            if line.strip():
                usda_content += f'            {line}\n'
        
        usda_content += '        }\n'
    
    usda_content += '    }\n'
    usda_content += '}\n'
    
    # Write final USD file
    with open(output_path, 'w') as f:
        f.write(usda_content)
    
    return output_path
```

### Blender LOD Integration

Blender's USD import can utilize VariantSets for comprehensive LOD management:

#### Manual LOD Selection

- **Viewport Performance**: Use "Low" or "Medium" variants for complex scenes with many trees
- **Animation Previews**: Medium detail provides good balance for animation work
- **Final Renders**: Switch to "High" variant for production quality output
- **Background Elements**: "Proxy" variants for distant forest elements

#### Automatic Optimization

```python
# Blender Python script for automatic LOD selection
import bpy

def set_lod_by_distance(tree_objects, camera_location, lod_distances=[50, 20, 5]):
    """Automatically set LOD based on distance from camera"""
    
    for obj in tree_objects:
        if obj.get("USD_VariantSets"):
            distance = (obj.location - camera_location).length
            
            if distance > lod_distances[0]:
                lod_variant = "Proxy"
            elif distance > lod_distances[1]:
                lod_variant = "Low"
            elif distance > lod_distances[2]:
                lod_variant = "Medium"
            else:
                lod_variant = "High"
            
            # Set USD variant selection
            obj["USD_VariantSets"]["lodVariant"] = lod_variant
```

### Unreal Engine LOD Integration

Unreal's USD Stage system provides sophisticated automatic LOD handling:

#### HLOD Integration

```cpp
// C++ integration with Unreal's Hierarchical LOD system
void SetupGroveTreeHLOD(AUSDStageActor* StageActor, const FString& TreePath)
{
    // Get USD prim
    UE::FUsdPrim TreePrim = StageActor->GetUsdStage().GetPrimAtPath(*TreePath);
    
    if (TreePrim.HasVariantSets())
    {
        // Configure HLOD based on USD variants
        auto VariantSet = TreePrim.GetVariantSet("lodVariant");
        TArray<FString> VariantNames = VariantSet.GetVariantNames();
        
        // Map USD variants to Unreal LOD levels
        for (int32 LODIndex = 0; LODIndex < VariantNames.Num(); ++LODIndex)
        {
            FString VariantName = VariantNames[LODIndex];
            
            // Set distance thresholds based on variant
            float ScreenSize = 1.0f;
            if (VariantName == "High") ScreenSize = 0.8f;
            else if (VariantName == "Medium") ScreenSize = 0.4f;
            else if (VariantName == "Low") ScreenSize = 0.1f;
            else if (VariantName == "Proxy") ScreenSize = 0.05f;
            
            // Configure automatic switching
            SetLODScreenSize(LODIndex, ScreenSize);
        }
    }
}
```

#### Performance Features

- **Distance-Based Culling**: Automatic variant switching based on camera distance
- **Screen Space Metrics**: LOD selection based on rendered screen size
- **HISM Optimization**: Hierarchical Instanced Static Meshes work across all LOD levels
- **Memory Streaming**: Large scenes can stream appropriate LOD variants as needed
- **Cluster Culling**: GPU-driven rendering with LOD-aware culling

#### Integration Best Practices

1. **LOD Distance Thresholds**:
   - High: 0-20 meters (close-up hero trees)
   - Medium: 20-50 meters (mid-ground forest)
   - Low: 50-200 meters (background trees)
   - Proxy: 200+ meters (distant forest silhouettes)

2. **Memory Management**:
   - Only load required LOD levels
   - Use USD payloads for LOD data streaming
   - Implement aggressive culling for off-screen trees

3. **Animation Consistency**:
   - Maintain skeletal structure across all LOD levels
   - Scale bone count appropriately (High: full skeleton, Low: simplified)
   - Preserve key animation bones (trunk, major branches)

This comprehensive documentation covers The Grove's native USD implementation with advanced LOD support, providing the foundation for understanding how Grove trees integrate with any USD-compatible application through their standardized USD export system with optimal performance characteristics.
