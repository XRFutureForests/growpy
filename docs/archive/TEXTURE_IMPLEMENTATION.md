# Growpy USD Texture Implementation Guide

## Current Issue Analysis

### Problem Statement
Textures work when twig USD files are loaded individually in Blender but fail to render when used as instances through growpy's PointInstancer system. This is due to material inheritance scope issues in USD's referencing system.

### Root Cause
The current growpy implementation relies on external USD file references for twig prototypes, where materials are defined within the referenced files. When these files are used as prototypes in a PointInstancer, the material scope inheritance chain breaks, preventing proper texture rendering in instances.

## Current vs Required Implementation

### Current Growpy Approach
```python
# In twig.py - write_usd_pointinstancer_to_stage()
prototype = stage.DefinePrim(prototype_path, "Xform")
prototype.GetReferences().AddReference(twig_usd_file_path)
# Materials defined in external file - scope inheritance issues
```

### Grove's Working Approach
Grove exports create self-contained material definitions within the tree structure:

```usda
def Material "MaterialName" {
    token outputs:surface.connect = </path/to/MaterialName/Diffuse_BSDF.outputs:surface>
    
    def Shader "Diffuse_BSDF" {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </path/to/MaterialName/Image_Texture.outputs:rgb>
        float inputs:roughness = 0
        token outputs:surface
    }
    
    def Shader "Image_Texture" {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/texture_file.png@
        token inputs:sourceColorSpace = "sRGB"
        float2 inputs:st.connect = </path/to/MaterialName/uvmap.outputs:result>
        token inputs:wrapS = "repeat"
        token inputs:wrapT = "repeat"
        float3 outputs:rgb
    }
    
    def Shader "uvmap" {
        uniform token info:id = "UsdPrimvarReader_float2"
        string inputs:varname = "st"
        float2 outputs:result
    }
}
```

## Implementation Strategy

### Phase 1: Material Extraction and Embedding

1. **Extract Materials from Twig USD Files**
   - Parse existing twig USD files to extract material definitions
   - Create material extraction function in `twig.py`
   - Store material data for embedding in main tree structure

2. **Embed Materials in Tree Structure**
   - Modify `write_usd_pointinstancer_to_stage()` to include materials
   - Create materials at tree level rather than prototype level
   - Maintain proper scope inheritance

### Phase 2: Material Binding Updates

1. **Update GeomSubset Binding**
   - Ensure GeomSubsets reference embedded materials
   - Update MaterialBindingAPI calls to use tree-level material paths

2. **Texture Path Management**
   - Copy or reference texture files relative to main tree USD
   - Update texture file paths in embedded materials

### Phase 3: PointInstancer Modifications

1. **Prototype Reference Changes**
   - Keep geometry references but remove material dependencies
   - Ensure prototype geometry maintains UV coordinates (primvar "st")

2. **Instance Material Assignment**
   - Bind materials at instancer or instance level
   - Leverage USD's material inheritance system properly

## Detailed Implementation Steps

### Step 1: Material Extraction Function

Create new function in `twig.py`:

```python
def extract_materials_from_usd(usd_file_path):
    """
    Extract material definitions from a USD file.
    Returns dict with material data including shaders and connections.
    """
    stage = Usd.Stage.Open(usd_file_path)
    materials = {}
    
    for prim in stage.Traverse():
        if prim.IsA(UsdShade.Material):
            material_data = {
                'name': prim.GetName(),
                'shaders': {},
                'connections': {}
            }
            
            # Extract UsdPreviewSurface shader
            surface_shader = UsdShade.Shader(prim.GetChild("Diffuse_BSDF"))
            if surface_shader:
                material_data['shaders']['surface'] = {
                    'info:id': 'UsdPreviewSurface',
                    'inputs': surface_shader.GetInputs()
                }
            
            # Extract UsdUVTexture shader
            texture_shader = UsdShade.Shader(prim.GetChild("Image_Texture"))
            if texture_shader:
                texture_file = texture_shader.GetInput("file").Get()
                material_data['shaders']['texture'] = {
                    'info:id': 'UsdUVTexture',
                    'file': texture_file,
                    'inputs': texture_shader.GetInputs()
                }
            
            # Extract UV mapping shader
            uv_shader = UsdShade.Shader(prim.GetChild("uvmap"))
            if uv_shader:
                material_data['shaders']['uvmap'] = {
                    'info:id': 'UsdPrimvarReader_float2',
                    'varname': 'st'
                }
            
            materials[prim.GetName()] = material_data
    
    return materials
```

### Step 2: Material Embedding Function

```python
def embed_materials_in_stage(stage, materials, base_path="/materials"):
    """
    Embed extracted materials into the main stage.
    """
    materials_scope = stage.DefinePrim(base_path, "Scope")
    
    for material_name, material_data in materials.items():
        material_path = f"{base_path}/{material_name}"
        material_prim = UsdShade.Material.Define(stage, material_path)
        
        # Create UsdPreviewSurface shader
        surface_shader_path = f"{material_path}/Diffuse_BSDF"
        surface_shader = UsdShade.Shader.Define(stage, surface_shader_path)
        surface_shader.CreateIdAttr("UsdPreviewSurface")
        
        # Create UsdUVTexture shader
        texture_shader_path = f"{material_path}/Image_Texture"
        texture_shader = UsdShade.Shader.Define(stage, texture_shader_path)
        texture_shader.CreateIdAttr("UsdUVTexture")
        
        # Set texture file
        texture_file = material_data['shaders']['texture']['file']
        texture_shader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_file)
        texture_shader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.String).Set("sRGB")
        texture_shader.CreateInput("wrapS", Sdf.ValueTypeNames.String).Set("repeat")
        texture_shader.CreateInput("wrapT", Sdf.ValueTypeNames.String).Set("repeat")
        
        # Create UV mapping shader
        uv_shader_path = f"{material_path}/uvmap"
        uv_shader = UsdShade.Shader.Define(stage, uv_shader_path)
        uv_shader.CreateIdAttr("UsdPrimvarReader_float2")
        uv_shader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
        
        # Connect shaders
        surface_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            texture_shader.ConnectableAPI(), "rgb"
        )
        texture_shader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            uv_shader.ConnectableAPI(), "result"
        )
        
        # Connect material output
        material_prim.CreateSurfaceOutput().ConnectToSource(
            surface_shader.ConnectableAPI(), "surface"
        )
```

### Step 3: Update PointInstancer Function

Modify `write_usd_pointinstancer_to_stage()`:

```python
def write_usd_pointinstancer_to_stage(stage, twig_data, output_path):
    """
    Updated function to embed materials and create proper instancer.
    """
    
    # 1. Extract materials from all twig files
    all_materials = {}
    for twig_file in unique_twig_files:
        materials = extract_materials_from_usd(twig_file)
        all_materials.update(materials)
    
    # 2. Embed materials in main stage
    embed_materials_in_stage(stage, all_materials)
    
    # 3. Create prototypes with geometry only (no materials)
    prototypes_scope = stage.DefinePrim("/prototypes", "Scope")
    prototype_paths = []
    
    for i, twig_file in enumerate(unique_twig_files):
        prototype_path = f"/prototypes/prototype_{i}"
        prototype = stage.DefinePrim(prototype_path, "Xform")
        
        # Reference geometry only, materials are now embedded at tree level
        prototype.GetReferences().AddReference(twig_file)
        
        # Remove material bindings from prototype if they exist
        # This ensures instances use tree-level materials
        clear_material_bindings(stage, prototype_path)
        
        prototype_paths.append(prototype_path)
    
    # 4. Create PointInstancer with material bindings
    instancer_path = "/twig_instancer"
    instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)
    
    # Set instancer data (positions, orientations, etc.)
    setup_instancer_data(instancer, twig_data)
    
    # 5. Bind materials to instances
    bind_materials_to_instances(stage, instancer_path, twig_data, all_materials)
    
    return instancer
```

### Step 4: Material Binding for Instances

```python
def bind_materials_to_instances(stage, instancer_path, twig_data, materials):
    """
    Bind embedded materials to specific instances.
    """
    instancer_prim = stage.GetPrimAtPath(instancer_path)
    
    for instance_idx, twig_info in enumerate(twig_data):
        twig_species = twig_info.get('species', 'default')
        
        # Find matching material
        material_name = find_material_for_species(twig_species, materials)
        
        if material_name:
            material_path = f"/materials/{material_name}"
            
            # Create instance-specific material binding
            # This approach varies based on USD version and requirements
            # Option 1: Use MaterialBindingAPI on instancer
            binding_api = UsdShade.MaterialBindingAPI.Apply(instancer_prim)
            material_prim = UsdShade.Material(stage.GetPrimAtPath(material_path))
            binding_api.Bind(material_prim)
            
            # Option 2: Use GeomSubset for per-instance materials (if needed)
            # This is more complex but allows different materials per instance
```

## File Structure Changes

### Required Updates

1. **twig.py**
   - Add material extraction functions
   - Modify `write_usd_pointinstancer_to_stage()`
   - Update material binding logic

2. **Material Management**
   - Create material utility module if needed
   - Handle texture file path resolution
   - Manage material naming conventions

3. **Testing Framework**
   - Add tests for material extraction
   - Verify texture rendering in target applications
   - Test both individual and instanced rendering

## Texture File Management

### Path Resolution Strategy

1. **Copy Textures to Output Directory**
   ```python
   def copy_texture_files(materials, output_dir):
       texture_dir = os.path.join(output_dir, "textures")
       os.makedirs(texture_dir, exist_ok=True)
       
       for material_data in materials.values():
           if 'texture' in material_data['shaders']:
               src_path = resolve_texture_path(material_data['shaders']['texture']['file'])
               dst_path = os.path.join(texture_dir, os.path.basename(src_path))
               shutil.copy2(src_path, dst_path)
               
               # Update material reference
               material_data['shaders']['texture']['file'] = f"./textures/{os.path.basename(src_path)}"
   ```

2. **Relative Path Updates**
   - Ensure texture paths are relative to main USD file
   - Handle both absolute and relative source paths
   - Maintain texture organization

## Testing and Validation

### Test Cases

1. **Individual Twig Loading**
   - Verify textures still work when loading twig files individually
   - Ensure backward compatibility

2. **Instanced Rendering**
   - Test texture rendering in PointInstancer context
   - Verify different materials on different instances

3. **Application Compatibility**
   - Test in Blender USD import
   - Test in other USD-compatible applications
   - Verify material inheritance behavior

### Validation Checklist

- [ ] Materials extracted correctly from twig USD files
- [ ] Materials embedded properly in tree structure
- [ ] Texture paths resolved and copied correctly
- [ ] PointInstancer instances render with textures
- [ ] No regression in individual twig file rendering
- [ ] Performance impact within acceptable range

## Performance Considerations

### Optimization Strategies

1. **Material Deduplication**
   - Identify and merge identical materials
   - Reduce memory footprint

2. **Texture Sharing**
   - Share textures between similar materials
   - Optimize texture resolution for use case

3. **Lazy Loading**
   - Consider lazy material loading for large scenes
   - Implement material caching if needed

## Implementation Timeline

### Phase 1 (Week 1)
- Implement material extraction functions
- Create basic material embedding system
- Update PointInstancer creation

### Phase 2 (Week 2) 
- Add texture file management
- Implement material binding for instances
- Create test cases

### Phase 3 (Week 3)
- Performance optimization
- Cross-application testing
- Documentation and examples

## Conclusion

This implementation strategy addresses the core issue of material scope inheritance in USD PointInstancer systems by embedding materials at the tree level rather than relying on external references. The approach maintains compatibility with existing twig files while enabling proper texture rendering in instanced contexts.

The key insight is that Grove's approach works because it creates self-contained material definitions within the tree structure, ensuring proper scope inheritance for all USD applications that consume the files.