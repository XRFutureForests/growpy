# Unreal Engine 5 Nanite Foliage Workflow

This guide explains how to export tree models from GrowPy and import them into Unreal Engine 5 for use with Nanite foliage.

## Overview

GrowPy exports tree models optimized for Unreal Engine 5's Nanite virtualized geometry system. Nanite allows for extremely detailed foliage with minimal performance impact, making it ideal for realistic forest scenes.

## Supported Export Formats

### FBX (Recommended for General Use)
- **Format Version**: FBX 2020.2
- **Best For**: Standard UE5 workflows, compatibility with other tools
- **Features**: Mesh, skeleton/armature, materials, UVs, tangent space

### USD (Recommended for Nanite Assemblies)
- **Format Version**: USD/USDA
- **Best For**: Advanced Nanite workflows in UE 5.7+, complex hierarchies
- **Features**: Full scene hierarchy, advanced material networks, skeletal data
- **Note**: Requires UE 5.7+ with Nanite Assembly support

## Exporting Trees for Nanite

### Basic Export (FBX)

```python
from growpy import create_grove, export_tree_as_fbx
from pathlib import Path

# Create and simulate a tree
grove = create_grove("Oak")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export as FBX for Unreal Engine
output_path = Path("output/trees/Oak_nanite.fbx")
export_tree_as_fbx(
    grove=grove,
    output_path=output_path,
    species_name="Oak",
    include_skeleton=True,           # Include armature for wind/physics
    export_skeleton_separately=False  # Combine mesh + skeleton
)
```

### Advanced Export (USD for Nanite Assemblies)

```python
from growpy import create_grove, export_tree_as_usd, create_nanite_assembly_usd
from pathlib import Path

# Create and simulate a tree
grove = create_grove("Beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export tree mesh as USD
tree_mesh_path = Path("output/trees/Beech_tree_mesh.usda")
export_tree_as_usd(
    grove=grove,
    output_path=tree_mesh_path,
    species_name="Beech",
    include_skeleton=True,
    export_skeleton_separately=False
)

# Optional: Create Nanite Assembly USD with twig references
# (Requires separate twig USD files)
twig_paths = [
    Path("output/twigs/Beech_twig_01.usda"),
    Path("output/twigs/Beech_twig_02.usda"),
]
assembly_path = Path("output/assemblies/Beech_Assembly.usda")
create_nanite_assembly_usd(
    tree_mesh_path=tree_mesh_path,
    twig_mesh_paths=twig_paths,
    output_assembly_path=assembly_path,
    species_name="Beech"
)
```

### Separate Skeleton Export

For complex rigging workflows, export skeleton separately:

```python
# Export mesh and skeleton as separate files
export_tree_as_fbx(
    grove=grove,
    output_path=Path("output/trees/Oak_mesh.fbx"),
    species_name="Oak",
    include_skeleton=True,
    export_skeleton_separately=True  # Creates Oak_mesh.fbx + Oak_mesh_skeleton.fbx
)
```

## Import Settings in Unreal Engine 5

### FBX Import Settings

1. **Open Unreal Engine 5** and navigate to your Content Browser
2. **Drag and drop** the FBX file or use **Import**
3. **Configure Import Settings**:

```
Mesh:
  ☑ Import Mesh
  ☑ Auto Generate Collision (optional)
  ☑ Generate Lightmap UVs

Transform:
  Import Uniform Scale: 1.0

Mesh > Build Settings:
  ☑ Use Full Precision UVs
  ☑ Build Reversed Index Buffer (for Nanite)

LOD Settings:
  ☐ Auto Compute LOD Distances (Nanite handles LOD)

Nanite Settings:
  ☑ Build Nanite (ENABLE THIS)

Materials:
  ☑ Import Materials
  ☑ Import Textures
  Material Import Method: Create New Materials

Skeleton:
  ☑ Import Skeletal Mesh (if skeleton included)
  Skeleton: Create New / Use Existing
```

### USD Import Settings (UE 5.7+)

1. **Enable USD Plugin** in Edit → Plugins → USD Importer
2. **Import via Content Browser**: Right-click → Import to /Game/
3. **Configure USD Stage Settings**:

```
Import Options:
  ☑ Import Meshes
  ☑ Import Materials
  ☑ Import Skeletal Data

Nanite:
  ☑ Enable Nanite for Static Meshes

Materials:
  Material Purpose: Preview (default)
```

## Enabling Nanite Foliage

### Project Settings

1. **Edit → Project Settings → Engine → Rendering**
2. Enable the following:
   - ☑ **Support Nanite**
   - ☑ **Nanite Foliage** (Beta feature)

### Static Mesh Settings

After importing, configure each tree mesh:

1. **Open Static Mesh** in the editor
2. **Details Panel → Nanite Settings**:
   - ☑ **Enable Nanite Support**
   - ☑ **Preserve Area** (prevents thinning on foliage)
   - Position Precision: Auto
   - Fallback Percent Triangles: 100%

### Material Setup for Nanite

Nanite works best with opaque materials. For foliage:

1. **Material Settings**:
   - Blend Mode: **Opaque** (preferred for Nanite)
   - Shading Model: Default Lit
   - ☐ Two Sided (avoid if possible for performance)

2. **Avoid Masked Materials**: Nanite doesn't efficiently support opacity masks
   - Use full geometry instead of alpha-masked cards
   - GrowPy exports solid branch/trunk geometry optimized for this

3. **Texture Setup**:
   - Base Color: Bark texture
   - Normal: Bark normal map (uses tangent space from export)
   - Roughness: Surface roughness
   - Ambient Occlusion: For additional detail

## Creating Foliage Types

### Setup for Foliage Tool

1. **Content Browser** → Right-click imported mesh
2. **Create → Foliage Type**
3. **Configure Foliage Type**:

```
Mesh:
  Static Mesh: [Your imported tree]

Placement:
  Align to Normal: Yes
  Random Yaw: Yes
  Ground Slope Angle: 0-45°

Instance Settings:
  Density: 10-100 per 1000 units
  Scale: Uniform 0.8-1.2 (for variation)

Nanite:
  ☑ Use Nanite Foliage System
  Cull Distance: 10000+ (let Nanite handle culling)
```

### Using Foliage Paint Mode

1. **Mode Panel** → **Foliage Mode**
2. **Add your Foliage Type** from content browser
3. **Paint Settings**:
   - Brush Size: 512-2048
   - Paint Density: 0.5-1.0
   - Erase Density: 0.0-0.5

4. **Paint foliage** in your level
   - Nanite will automatically handle LOD and streaming
   - No manual LOD setup needed

## Wind Animation (Using Skeleton)

If you exported with skeleton:

1. **Import Skeleton** alongside mesh
2. **Create Control Rig** in Unreal:
   - Right-click skeleton → Create → Control Rig
3. **Use Blueprint or Control Rig** for wind:
   - Animate bones using sine waves
   - Apply wind force based on world wind actor
4. **Apply to Foliage Instances**:
   - Use Instanced Foliage with skeletal mesh
   - Or use Niagara for custom wind effects

## Performance Tips

1. **Use Full Geometry**: Don't use alpha-masked leaf cards—Nanite handles millions of triangles efficiently
2. **Enable Preserve Area**: Critical for foliage to prevent over-thinning
3. **Opaque Materials**: Significantly faster than masked materials with Nanite
4. **Let Nanite Handle LODs**: Don't create manual LOD chains
5. **World Partition**: Use for large forests with many instances

## Troubleshooting

### Mesh Appears Too Dark
- Check normal map import (should use tangent space)
- Verify material has proper lighting model
- Enable two-sided if needed (but impacts performance)

### Nanite Not Enabled
- Confirm "Enable Nanite Support" checked in Static Mesh settings
- Check Project Settings → Rendering → Support Nanite
- Verify GPU supports Nanite (requires DX12/Vulkan)

### Skeleton Not Importing
- Check FBX export included armature
- Verify Unreal import settings have "Import Skeletal Mesh" enabled
- Try exporting skeleton separately

### Materials Missing
- Re-export with material data
- Manually assign materials in Unreal
- Check texture paths are accessible

## Example: Complete Workflow

### Basic Workflow (FBX + USD)

```python
from growpy import (
    create_grove,
    export_tree_as_fbx,
    export_tree_as_usd
)
from pathlib import Path

# Species to export
species_list = ["Oak", "Beech", "Douglas_Fir"]

for species in species_list:
    # Create grove
    grove = create_grove(species)
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    grove.simulate(flushes=10)

    # Export FBX (general use)
    fbx_path = Path(f"output/ue5_nanite/{species}_tree.fbx")
    export_tree_as_fbx(
        grove=grove,
        output_path=fbx_path,
        species_name=species,
        include_skeleton=True,
        export_skeleton_separately=False
    )

    # Export USD (Nanite Assemblies)
    usd_path = Path(f"output/ue5_nanite/{species}_tree.usda")
    export_tree_as_usd(
        grove=grove,
        output_path=usd_path,
        species_name=species,
        include_skeleton=True,
        export_skeleton_separately=False
    )

    print(f"Exported {species} for UE5 Nanite")
```

### Advanced Workflow (USD Assembly with Twigs)

```python
from growpy import (
    create_grove,
    export_tree_as_usd,
    export_twigs_from_blend,
    create_nanite_assembly_usd
)
from pathlib import Path

species = "Oak"

# 1. Export tree trunk/branches as USD
grove = create_grove(species)
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

tree_mesh_path = Path(f"output/meshes/{species}_trunk.usda")
export_tree_as_usd(
    grove=grove,
    output_path=tree_mesh_path,
    species_name=species,
    include_skeleton=True,
    export_skeleton_separately=False
)

# 2. Export twigs from blend file
# (Convert FBX to USD externally or use USD-compatible export)
twig_blend = Path(f"assets/twigs/{species}Twig.blend")
twig_fbx_dir = Path(f"output/twigs/{species}")
twig_fbx_files = export_twigs_from_blend(twig_blend, twig_fbx_dir)

# Convert FBX twigs to USD (requires external tool or pxr)
# For now, assume USD twig files exist
twig_usd_paths = [
    Path(f"output/twigs/{species}/twig_01.usda"),
    Path(f"output/twigs/{species}/twig_02.usda"),
]

# 3. Create Nanite Assembly USD
assembly_path = Path(f"output/assemblies/{species}_Assembly.usda")
create_nanite_assembly_usd(
    tree_mesh_path=tree_mesh_path,
    twig_mesh_paths=twig_usd_paths,
    output_assembly_path=assembly_path,
    species_name=species
)

print(f"Created Nanite Assembly for {species}: {assembly_path}")
```

## Next Steps in Unreal Engine

1. **Import all tree meshes** using settings above
2. **Enable Nanite** on each Static Mesh
3. **Create Foliage Types** for each tree species
4. **Paint forests** using Foliage Mode
5. **Add wind animation** using Control Rigs or Niagara
6. **Optimize materials** for opaque rendering
7. **Test performance** with large instance counts

## Additional Resources

- [Unreal Engine Nanite Documentation](https://docs.unrealengine.com/5.0/en-US/RenderingFeatures/Nanite/)
- [USD Import in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/usd-ue-format-support)
- [Foliage Mode Documentation](https://docs.unrealengine.com/5.0/en-US/foliage-mode-in-unreal-engine/)

## Summary

GrowPy exports are optimized for Unreal Engine 5 Nanite foliage:
- **FBX 2020.2** for broad compatibility
- **USD/USDA** for advanced Nanite Assembly workflows
- Full geometry (no masked cards) for optimal Nanite performance
- Skeletal support for wind/physics animation
- Tangent space normals for correct lighting

The result: realistic, high-detail forests with minimal performance impact using Nanite's revolutionary streaming technology.