# USD Export and Import in Blender for Grove Trees

This document covers how Grove's USD export works specifically with Blender's USD pipeline, focusing on transformations, rigging, and instancing for tree models that include skeletal animation and twig instances.

## Overview

The Grove exports trees as USD files that are fully compatible with Blender's USD import/export system. Each tree includes:

- **Mesh geometry** with proper UV coordinates and custom attributes
- **Skeletal armatures** for wind animation using USD's `UsdSkelSkeleton` schema
- **Twig instances** using USD's `UsdGeomPointInstancer` primitives
- **Transform hierarchies** with proper coordinate system handling

## Grove USD Export Structure

### Tree Hierarchy

Each Grove tree exports as a structured USD hierarchy:

```
/Tree0 (UsdGeomXform)
├── /Tree0/Geometry (UsdGeomMesh)
│   ├── Mesh data with UV coordinates
│   ├── Custom attributes (age, mass, thickness, etc.)
│   └── Twig duplication triangles
├── /Tree0/Skeleton (UsdSkelSkeleton)
│   ├── Joint hierarchy for wind animation
│   ├── Bone weights and influences
│   └── Rest pose transformations
└── /Tree0/TwigInstances (UsdGeomPointInstancer)
    ├── Twig_Long instances
    ├── Twig_Short instances
    ├── Twig_Upward instances
    └── Twig_Dead instances
```

```

### Coordinate System and Transformations

#### Blender Z-Up Conversion
The Grove automatically handles coordinate system conversion when exporting USD for Blender:

```python
# Grove core handles this automatically
model.set_up_axis("Z")  # Convert from Grove's Y-up to Blender's Z-up
```

#### Transform Hierarchy

Each tree's root `Xform` contains the world-space transformation:

```usda
def Xform "Tree0"
{
    matrix4d xformOp:transform = (
        (1, 0, 0, 0),
        (0, 1, 0, 0), 
        (0, 0, 1, 0),
        (x, y, z, 1)  # Tree's world position
    )
    uniform token[] xformOpOrder = ["xformOp:transform"]
}
```

## Skeletal Animation System

### USD Skeleton Schema

Grove trees export with full USD skeleton data compatible with Blender's armature system:

#### Joint Hierarchy

```usda
def Skeleton "Skeleton"
{
    uniform token[] joints = [
        "Root", 
        "Root/Trunk", 
        "Root/Trunk/Branch0",
        "Root/Trunk/Branch0/SubBranch0",
        # ... additional joints
    ]
    
    uniform matrix4d[] bindTransforms = [
        # Rest pose transforms for each joint
    ]
    
    uniform matrix4d[] restTransforms = [
        # Local space rest transforms
    ]
}
```

#### Skeletal Mesh Binding

```usda
def Mesh "Geometry"
{
    # Mesh geometry data
    point3f[] points = [...]
    int[] faceVertexCounts = [...]
    int[] faceVertexIndices = [...]
    
    # UV coordinates
    texCoord2f[] primvars:st = [...] (
        interpolation = "faceVarying"
    )
    
    # Skeleton binding
    rel skel:skeleton = </Tree0/Skeleton>
    int[] primvars:skel:jointIndices = [...] (
        interpolation = "vertex"
    )
    float[] primvars:skel:jointWeights = [...] (
        interpolation = "vertex"
    )
}
```

### Blender Import Behavior

When importing Grove USD files into Blender:

1. **Automatic Armature Creation**: Blender creates armature objects from `UsdSkelSkeleton` primitives
2. **Bone Weights**: Joint weights are imported as vertex groups
3. **Armature Modifiers**: Automatic armature modifiers are applied to mesh objects
4. **Animation Ready**: Skeletons are ready for wind animation or manual posing

#### Advanced Skeletal Features

**Bone Optimization**: Grove's skeletal system supports several optimization parameters that are preserved in USD export:

- **Length Factor** (0.0-5.0): Controls minimum bone length, affects bone count and hierarchy depth
- **Reduce Threshold** (0.0-1.0): Eliminates bones below thickness threshold, merging thin branches
- **Bias Factor** (0.0-1.0): Balances bone density between trunk and branches
- **Connected Bones**: Determines if child bones connect to parent bone tails

**Blender Bone Properties**: Imported bones maintain Grove attributes:

```python
# Accessing Grove bone data in Blender
for bone in armature.bones:
    grove_radius = bone.get('grove_radius', 1.0)    # Original Grove bone radius
    grove_age = bone.get('grove_age', 0)            # Branch age at bone location
    grove_mass = bone.get('grove_mass', 1.0)        # Branch mass for physics
    flexibility = bone.get('flexibility', 1.0)      # Wind responsiveness factor
```

#### Blender-Specific Considerations

- **Bone Naming**: Blender converts USD joint names to valid bone names (numerical IDs by default)
- **Coordinate Conversion**: Z-up orientation is maintained from USD during import
- **Weight Painting**: Imported vertex groups can be edited with Blender's weight painting tools
- **Driver Support**: Bone properties can drive material or geometry node parameters
- **IK/FK Ready**: Connected bone chains support inverse kinematics for animation
- **Constraint System**: Blender bone constraints can be applied to imported armatures

## Twig Instancing System

### Point Instancer Implementation

Grove uses USD's `UsdGeomPointInstancer` for efficient twig distribution:

```usda
def PointInstancer "TwigInstances"
{
    # Instance positions (centers of twig triangles)
    point3f[] positions = [...]
    
    # Instance orientations (from triangle normals)
    quath[] orientations = [...]
    
    # Instance scales
    float3[] scales = [...]
    
    # Prototype indices (which twig type to instance)
    int[] protoIndices = [...]
    
    # References to twig prototypes
    rel prototypes = [
        </TwigPrototypes/TwigLong>,
        </TwigPrototypes/TwigShort>,
        </TwigPrototypes/TwigUpward>,
        </TwigPrototypes/TwigDead>
    ]
}
```

### Blender Point Instancer Support

Blender's USD importer converts `UsdGeomPointInstancer` to:

1. **Point Clouds**: Instance positions become point cloud geometry
2. **Geometry Nodes**: Automatic geometry nodes modifier with "Instance on Points"
3. **Collection Instances**: Prototype references become collection instances

#### Instance Attributes

Grove exports additional per-instance attributes:

```usda
# Custom attributes for each instance
float[] primvars:age = [...] (
    interpolation = "varying"
)
float[] primvars:vigor = [...] (
    interpolation = "varying"
)
bool[] primvars:dead = [...] (
    interpolation = "varying"
)
```

### Geometry Nodes Integration

The imported point cloud with instances integrates seamlessly with Blender's Geometry Nodes:

```python
# Example geometry nodes setup for additional processing
modifier = obj.modifiers.new("GeometryNodes", 'NODES')
modifier.node_group = create_twig_processing_nodegroup()

# Access instance attributes in geometry nodes
# Use "Named Attribute" nodes to read custom USD attributes
# Apply additional transformations, materials, or effects
```

## Material and Shading

### USD Preview Surface

Grove exports material information compatible with Blender's Principled BSDF:

```usda
def Material "BarkMaterial"
{
    token outputs:surface.connect = </BarkMaterial/PreviewSurface.outputs:surface>
    
    def Shader "PreviewSurface"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.8, 0.6, 0.4)
        float inputs:roughness = 0.8
        float inputs:metallic = 0.0
        normal3f inputs:normal.connect = </BarkMaterial/NormalTexture.outputs:rgb>
    }
    
    def Shader "NormalTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bark_normal.jpg@
        token inputs:sourceColorSpace = "raw"
    }
}
```

### Blender Material Import

When importing USD materials:

1. **Preview Surface Conversion**: USD Preview Surface maps to Principled BSDF
2. **Texture References**: File paths are resolved relative to USD file
3. **UV Coordinate Mapping**: Automatic UV map connections
4. **Custom Attributes**: Additional material data from Grove attributes

## Animation and Time-Varying Data

### Growth Animation

Grove can export time-varying geometry for growth animation:

```usda
def Mesh "Geometry"
{
    # Frame 1
    point3f[] points.timeSamples = {
        1: [...],  # Initial growth state
        24: [...], # One year later
        48: [...], # Two years later
    }
    
    # Face topology changes over time
    int[] faceVertexIndices.timeSamples = {
        1: [...],
        24: [...],
        48: [...],
    }
}
```

#### Blender Animation Import

Blender imports time-varying USD data as:

1. **Mesh Sequence Cache**: Automatic modifier for animated geometry
2. **Shape Keys**: Conversion to Blender's shape key system when appropriate
3. **Keyframe Animation**: Traditional keyframes for simple property animation

### Wind Animation

Skeletal wind animation uses USD's animation system with Grove's sophisticated bone-based deformation:

```usda
def Skeleton "Skeleton"
{
    # Animated joint transforms with noise-based wind deformation
    matrix4d[] jointTransforms.timeSamples = {
        1: [...],  # Rest pose
        2: [...],  # Wind frame 1
        3: [...],  # Wind frame 2
    }
    
    # Grove-specific wind attributes
    float primvars:flexibility = [...] (
        interpolation = "varying"
        doc = "Branch flexibility based on radius"
    )
    float primvars:wind_frequency = [...] (
        interpolation = "varying" 
        doc = "Noise frequency per joint"
    )
    float primvars:wind_strength = [...] (
        interpolation = "varying"
        doc = "Deformation strength per joint"
    )
}
```

#### Blender Wind Animation Import

Blender processes Grove wind animation through several systems:

1. **Armature Modifiers**: USD skeleton becomes Blender armature with automatic weights
2. **Noise F-Curve Modifiers**: Wind noise becomes Blender noise modifiers on bone rotations
3. **Shape Key Alternative**: When USD lacks skeleton, wind animation imports as shape keys
4. **Flexibility Mapping**: Branch thickness drives animation intensity

**Wind Import Process:**

```python
# Blender automatically converts USD skeleton animation
import bpy

def import_grove_wind_animation(usd_file):
    # Import USD with skeleton
    bpy.ops.wm.usd_import(filepath=usd_file)
    
    # Blender processes skeleton to armature
    skeleton_obj = bpy.context.selected_objects[0]  # Skeleton object
    tree_obj = bpy.context.selected_objects[1]      # Tree mesh
    
    # Automatic armature modifier setup
    armature_mod = tree_obj.modifiers.new(name="Skeleton", type='ARMATURE')
    armature_mod.object = skeleton_obj
    
    # Wind noise conversion from USD animation data
    for bone in skeleton_obj.pose.bones:
        # Blender reads USD joint animation as keyframes
        # Converts to noise modifiers for real-time wind
        for fcurve in skeleton_obj.animation_data.action.fcurves:
            if bone.name in fcurve.data_path:
                # Add noise modifier matching Grove's wind system
                noise_mod = fcurve.modifiers.new(type='NOISE')
                # Import wind parameters from USD custom attributes
                noise_mod.scale = bone.get('wind_frequency', 17.0)
                noise_mod.strength = bone.get('wind_strength', 1.0)
```

**Wind Animation Workflow:**

1. **USD Import**: Skeleton with time-sampled joint transforms
2. **Armature Creation**: Blender converts USD skeleton to armature
3. **Weight Assignment**: Automatic vertex weights from USD skinning data
4. **Animation Conversion**: Joint animation becomes bone keyframes or noise modifiers
5. **Real-time Playback**: Interactive wind animation in Blender viewport

## Custom Attributes and Metadata

### Grove-Specific Attributes

Grove exports custom attributes that are preserved in Blender:

```usda
def Mesh "Geometry"
{
    # Point attributes
    int[] primvars:age = [...] (
        interpolation = "vertex"
    )
    float[] primvars:mass = [...] (
        interpolation = "vertex"
    )
    float[] primvars:thickness = [...] (
        interpolation = "vertex"
    )
    float[] primvars:photosynthesis = [...] (
        interpolation = "vertex"
    )
    
    # Face attributes  
    int[] primvars:branch_id = [...] (
        interpolation = "face"
    )
    bool[] primvars:twig_long = [...] (
        interpolation = "face"
    )
    bool[] primvars:dead = [...] (
        interpolation = "face"
    )
}
```

### Accessing Attributes in Blender

Custom attributes can be accessed through:

1. **Attribute Nodes**: In Geometry Nodes or Shader Nodes
2. **Python API**: Via `mesh.attributes` collection
3. **Custom Properties**: Some attributes converted to custom properties

```python
# Access custom attributes in Python
import bpy

obj = bpy.context.active_object
mesh = obj.data

# Read Grove-specific attributes
age_attr = mesh.attributes.get("age")
if age_attr:
    age_values = [age_attr.data[i].value for i in range(len(age_attr.data))]

thickness_attr = mesh.attributes.get("thickness") 
if thickness_attr:
    thickness_values = [thickness_attr.data[i].value for i in range(len(thickness_attr.data))]
```

## Performance Considerations

### Efficient Instancing

Grove's instancing system is designed for performance:

- **Prototype Sharing**: Multiple instances reference the same twig geometry
- **Level of Detail**: Different twig types for various detail levels
- **Culling Support**: Instance visibility can be controlled programmatically

### Memory Management

- **On-Demand Loading**: USD supports payload-based loading for large forests
- **Compression**: USD files can be compressed for smaller file sizes
- **Streaming**: Large tree datasets can be streamed as needed

## Workflow Examples

### Basic Tree Import

```python
import bpy

# Import Grove USD file
bpy.ops.wm.usd_import(
    filepath="/path/to/grove_tree.usda",
    import_usd_preview=True,
    import_armatures=True,
    import_meshes=True,
    scene_instancing=True
)

# Result: Complete tree with skeleton, mesh, and instanced twigs
```

### Forest Scene Assembly

```python
# Import multiple trees and assemble forest
for i in range(10):
    bpy.ops.wm.usd_import(
        filepath=f"/path/to/trees/tree{i}.usda",
        import_meshes=True,
        scene_instancing=True
    )
    
    # Position trees in forest layout
    tree_obj = bpy.context.selected_objects[0]
    tree_obj.location = forest_positions[i]
```

### Animation Setup

```python
# Setup wind animation from USD skeleton
tree_obj = bpy.context.active_object
armature = tree_obj.modifiers["Armature"].object

# USD skeleton data is automatically imported
# Additional animation can be added to bones
for bone in armature.pose.bones:
    bone.keyframe_insert(data_path="rotation_quaternion", frame=1)
    # Add wind animation keyframes
```

## Troubleshooting

### Common Import Issues

1. **Missing Attributes**: Some custom attributes may not import in older Blender versions
2. **Coordinate System**: Ensure USD was exported with correct up-axis
3. **Texture Paths**: Verify texture file paths are relative to USD file
4. **Instance Performance**: Large numbers of instances may impact viewport performance

### Solutions

- **Update Blender**: Use Blender 3.6+ for best USD support
- **Check Console**: Review console output for import warnings
- **Validate USD**: Use `usdview` to verify USD file structure
- **Optimize Instances**: Use viewport display settings to manage performance

## Best Practices

1. **File Organization**: Keep USD files and textures in organized directory structure
2. **Relative Paths**: Use relative paths for textures and references
3. **Naming Conventions**: Use consistent naming for materials and objects
4. **Testing**: Validate USD files in both `usdview` and Blender before production use
5. **Performance**: Consider LOD systems for large forest scenes
6. **Version Control**: USD text format (.usda) works well with version control systems
