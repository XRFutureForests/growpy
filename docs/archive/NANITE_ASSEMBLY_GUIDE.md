# Unreal Engine Nanite Assembly Export Guide

This guide explains how to export trees from The Grove as Unreal Engine 5.7+ Nanite Assemblies using the official Unreal USD schema.

## What is a Nanite Assembly?

Nanite Assemblies are a USD-based workflow introduced in Unreal Engine 5.7 that enables:

- **Optimized Import**: Seamless multi-mesh assemblies with proper hierarchy
- **Automatic Nanite**: Meshes automatically converted to Nanite geometry
- **Skeletal Support**: Optional skeletal mesh assemblies for animation
- **Point Instances**: Efficient twig instances using USD PointInstancer
- **DCC Compatibility**: Standard USD files work in Blender, Houdini, Maya, etc.

## Schema Setup

The Unreal schema files are located in `data/unreal_schema/`. You must set the `PXR_PLUGINPATH_NAME` environment variable for Unreal to recognize them.

### macOS/Linux

```bash
export PXR_PLUGINPATH_NAME="/Users/yourusername/Developer/the-grove/data/unreal_schema"
```

Add to `~/.zshrc` or `~/.bash_profile` for persistence.

### Windows (PowerShell)

```powershell
$env:PXR_PLUGINPATH_NAME = "C:\path\to\the-grove\data\unreal_schema"
```

### Windows (Command Prompt)

```cmd
set PXR_PLUGINPATH_NAME=C:\path\to\the-grove\data\unreal_schema
```

For permanent setup on Windows:

1. System Properties → Advanced → Environment Variables
2. Add System Variable: `PXR_PLUGINPATH_NAME` = `C:\path\to\the-grove\data\unreal_schema`

### Verify Schema Loading

In Unreal's Output Log, look for:

```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

## Export Formats

When exporting with USD formats, The Grove creates **two USD files**:

1. **Standard USD** (`tree.usda`) - Compatible with all DCC applications
   - Works in Blender, Houdini, Maya, etc.
   - Standard USD hierarchy
   - Full twig placement data
   - Can be used for previewing or editing

2. **Nanite Assembly USD** (`tree_NaniteAssembly.usda`) - Optimized for Unreal
   - Uses `NaniteAssemblyRootAPI` schema
   - Child meshes use `NaniteAssemblyExternalRefAPI`
   - Automatic Nanite conversion on import
   - Optimized PointInstancer for twigs
   - Import this file in Unreal Engine 5.7+

## CLI Usage

### Generate Species Library

Export all configured species with Nanite Assembly USD:

```bash
# Default: Creates both standard and Nanite Assembly USD
python src/growpy/cli/generate_species_library.py --formats usda

# With twigs included
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs

# Export both FBX and USD with Nanite Assemblies
python src/growpy/cli/generate_species_library.py --formats fbx usda --include-twigs

# Disable Nanite Assembly creation (standard USD only)
python src/growpy/cli/generate_species_library.py --formats usda --no-nanite-assembly

# High quality with twigs
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --resolution 32 \
  --flushes 15
```

### Generate Forest

Export forest with Nanite Assembly USD:

```bash
# Default: Creates Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv --formats usda

# Ultra quality with Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv --quality ultra --formats usda

# Multiple formats
python src/growpy/cli/generate_forest.py forest.csv --formats fbx usd usda

# Disable Nanite Assembly
python src/growpy/cli/generate_forest.py forest.csv --formats usda --no-nanite-assembly
```

## Output Structure

```
data/output/species_library/
├── USD/
│   ├── European_Beech.usda              # Standard USD (DCC compatible)
│   ├── European_Beech_tree_only.usda    # Tree mesh only (no twigs)
│   ├── European_Beech_NaniteAssembly.usda  # Nanite Assembly for Unreal
│   ├── Norway_Spruce.usda
│   ├── Norway_Spruce_tree_only.usda
│   └── Norway_Spruce_NaniteAssembly.usda
└── FBX/
    ├── European_Beech.fbx
    └── Norway_Spruce.fbx
```

## Nanite Assembly Structure

The Nanite Assembly USD follows this hierarchy:

```
TreeSpecies_NaniteAssembly
├── apiSchemas = ["NaniteAssemblyRootAPI"]
├── unreal:naniteAssembly:meshType = "staticMesh"
│
├── TreeMesh (Xform)
│   ├── apiSchemas = ["NaniteAssemblyExternalRefAPI"]
│   └── references → European_Beech_tree_only.usda
│
└── TwigInstances (PointInstancer)
    ├── prototypes → TwigPrototypes/*
    ├── positions (array)
    ├── orientations (quaternions)
    ├── scales (array)
    └── protoIndices (array)
        │
        └── TwigPrototypes (Scope)
            ├── twiglong (Xform)
            │   ├── apiSchemas = ["NaniteAssemblyExternalRefAPI"]
            │   ├── instanceable = True
            │   └── references → twig_long.usda
            │
            └── twigshort (Xform)
                ├── apiSchemas = ["NaniteAssemblyExternalRefAPI"]
                ├── instanceable = True
                └── references → twig_short.usda
```

## Importing into Unreal Engine

### Step 1: Enable USD Plugin

1. Edit → Plugins
2. Search for "USD"
3. Enable "USD Importer"
4. Restart Unreal Engine

### Step 2: Verify Schema

Check Output Log for schema registration:

```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

If not found, check `PXR_PLUGINPATH_NAME` environment variable.

### Step 3: Import Nanite Assembly

1. Content Browser → Import
2. Select `*_NaniteAssembly.usda` file
3. Import Settings:
   - **Import Actors**: Unchecked (we want assets, not level actors)
   - **Import Geometry**: Checked
   - **Apply World Transform**: Unchecked
   - **Import as Static Meshes**: Checked
   - **Generate Nanite**: Automatically enabled (schema-driven)

4. Click Import

### What Gets Created

- **Static Mesh Asset**: Main tree mesh automatically converted to Nanite
- **Twig Static Meshes**: Individual twig assets (if included)
- **Material Instances**: Bark and leaf materials
- **Hierarchical Instanced Static Mesh (HISM)** or **Instanced Static Mesh (ISM)** component for twigs

### Step 4: Use in Level

#### Manual Placement

1. Drag `*_NaniteAssembly` asset into level
2. Scale and position as needed
3. Twigs automatically instanced

#### PCG (Procedural Content Generation)

```
PCG Graph:
  Generate Points → Spawn Mesh Instances → *_NaniteAssembly asset
```

#### Foliage Tool

1. Foliage Mode
2. Add `*_NaniteAssembly` as Foliage Type
3. Paint or scatter in level

## Python API Usage

```python
from pathlib import Path
from growpy import create_grove, get_config
from growpy.io.blender_export import export_grove_tree_as_usda_native

config = get_config()
grove = create_grove("European Beech")

# Add and simulate tree
import the_grove_22_core as gc
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export with Nanite Assembly (default)
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("data/output/beech.usda"),
    species_name="European Beech",
    include_twigs=True,
    create_nanite_assembly=True,  # Creates *_NaniteAssembly.usda
    resolution=32,
)
```

This creates:

- `beech_tree_only.usda` - Tree mesh only
- `beech.usda` - Standard USD with twigs
- `beech_NaniteAssembly.usda` - Nanite Assembly for Unreal

## Benefits of Nanite Assembly Workflow

### Performance

- **Automatic LODs**: Nanite generates runtime LODs automatically
- **Streaming**: Meshes stream in/out based on visibility
- **Instancing**: Twig PointInstancer = minimal memory overhead
- **GPU-Driven**: Culling and rendering entirely GPU-side

### Workflow

- **Single Asset**: Import once, use everywhere
- **Hierarchical**: Proper parent-child relationships preserved
- **Metadata**: All attributes preserved through import
- **Variations**: Multiple variations for procedural variety

### Quality

- **No Pop**: Smooth LOD transitions
- **High Detail**: Millions of triangles supported
- **Preserve Area**: Foliage doesn't thin at distance (when enabled)
- **Two-Sided**: Leaf materials render correctly

## Comparison: Standard vs Nanite Assembly

| Feature | Standard USD | Nanite Assembly USD |
|---------|--------------|---------------------|
| DCC Compatible | ✅ Yes | ⚠️ Unreal-optimized |
| Blender Preview | ✅ Yes | ⚠️ References need resolution |
| Houdini Compatible | ✅ Yes | ⚠️ May need adjustment |
| Unreal Import | ✅ Manual setup | ✅ Automatic optimization |
| Nanite Conversion | ⚠️ Manual | ✅ Automatic |
| Twig Instancing | ⚠️ Manual | ✅ Automatic |
| File Size | Larger (inline data) | Smaller (references) |

**Recommendation**: Export both formats. Use standard USD for DCC work, Nanite Assembly for Unreal.

## Troubleshooting

### Schema Not Recognized

**Symptom**: Unreal doesn't create Nanite meshes, logs show no schema registration

**Solution**:

1. Verify `PXR_PLUGINPATH_NAME` environment variable
2. Restart Unreal Engine after setting variable
3. Check Output Log for "Registered Unreal schema plugin" message
4. Ensure `data/unreal_schema/plugInfo.json` exists

### Twigs Not Appearing

**Symptom**: Tree imports but no twig instances

**Solutions**:

1. Verify twig USD files exist in output directory
2. Check Nanite Assembly references point to correct paths
3. Open `*_NaniteAssembly.usda` in text editor, verify `TwigPrototypes` section
4. Try reimporting with `--include-twigs` flag

### Import Fails

**Symptom**: Unreal import fails with error

**Solutions**:

1. Check USD file validity: `usdchecker tree_NaniteAssembly.usda`
2. Verify all referenced files exist (tree, twigs)
3. Try importing standard USD first to isolate issue
4. Check Unreal version (requires 5.7+)

### Performance Issues

**Symptom**: Low framerate in Unreal with many trees

**Solutions**:

1. Enable Nanite Override in Static Mesh settings
2. Reduce `Preserve Area` for background trees
3. Use LOD0 reduction in build settings
4. Consider lower resolution exports for distant trees

## References

- [Unreal USD Documentation](https://docs.unrealengine.com/5.7/en-US/USD/)
- [Nanite Assemblies Video Tutorial](https://www.youtube.com/watch?v=-ZGWblVF8Qk)
- [ArtStation Nanite Assembly Blog](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)
- [USD Schema Definition](https://openusd.org/release/api/class_usd_schema_registry.html)
- [Grove Documentation](docs/the_grove/)

## Advanced Topics

### Skeletal Mesh Assemblies

For animated trees (wind, growth animation):

```python
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("animated_tree.usda"),
    species_name="European Beech",
    create_nanite_assembly=True,
    use_skeletal_mesh=True,  # Enable skeletal mesh type
)
```

Nanite Assembly will use `unreal:naniteAssembly:meshType = "skeletalMesh"`

### Custom Quality Presets

```bash
# Ultra quality for hero trees
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --resolution 32 \
  --include-twigs

# Performance for background
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --resolution 8 \
  --no-twigs
```

### Batch Processing

```python
from growpy.io.blender_export import batch_export_trees_for_unreal

results = batch_export_trees_for_unreal(
    forest_data=forest_df,
    output_dir=Path("data/output/forest"),
    config=config,
    num_variations=3,
    export_formats=["fbx", "usda"],
    create_nanite_assembly=True,  # Enable Nanite Assemblies
    include_twigs_in_usd=True,
)
```

## License

Unreal schema files are provided by Epic Games. See Unreal Engine licensing for usage rights.

The Grove integration code is part of the GrowPy project.
