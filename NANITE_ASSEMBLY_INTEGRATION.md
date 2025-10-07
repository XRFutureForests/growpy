# Nanite Assembly Integration - Complete

## Summary

Successfully integrated Unreal Engine 5.7+ Nanite Assembly schema into The Grove export workflow. Both CLI scripts now support creating optimized Nanite Assembly USD files alongside standard USD exports.

## What Was Added

### 1. Unreal Schema Integration

**Location**: `data/unreal_schema/`

- `generatedSchema.usda` - Official Unreal USD schema definitions
- `plugInfo.json` - USD plugin metadata for schema discovery
- `README.md` - Schema setup and usage instructions
- `unreal/schema.usda` - Human-readable schema documentation

**Key Schemas**:

- `NaniteAssemblyRootAPI` - Marks assembly root
- `NaniteAssemblyExternalRefAPI` - References child meshes
- `NaniteAssemblySkelBindingAPI` - Skeletal mesh binding
- Additional: CollapsingAPI, SubdivisionAPI, LodSubtreeAPI, etc.

### 2. CLI Script Updates

Both `generate_forest.py` and `generate_species_library.py` now support:

**New Parameter**: `--create-nanite-assembly` (default: True)

```bash
# Creates both standard USD and Nanite Assembly USD
python src/growpy/cli/generate_species_library.py --formats usda

# Disable Nanite Assembly creation
python src/growpy/cli/generate_species_library.py --formats usda --no-nanite-assembly

# Forest generation with Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv --formats usda
```

### 3. Export Implementation

**Modified Files**:

- `src/growpy/cli/generate_forest.py` - Added create_nanite_assembly parameter
- `src/growpy/cli/generate_species_library.py` - Added create_nanite_assembly parameter
- `src/growpy/io/blender_export.py` - Added create_nanite_assembly to batch_export_trees_for_unreal

**Existing Implementation** (already in place):

- `src/growpy/io/unreal_nanite_assembly.py` - Nanite Assembly USD creation
- `src/growpy/io/blender_export.py` - export_grove_tree_as_usda_native with create_nanite_assembly support
- `src/growpy/io/twig_placement.py` - PointInstancer for twig instances

### 4. Documentation

**New File**: `docs/growpy/NANITE_ASSEMBLY_GUIDE.md`

Comprehensive guide covering:

- Schema setup and environment variables
- Export formats and file structure
- CLI usage examples
- Unreal Engine import workflow
- Python API usage
- Troubleshooting
- Performance optimization
- Advanced topics (skeletal meshes, quality presets)

## File Structure

When exporting with Nanite Assembly enabled, you get three USD files:

```
output/USD/
├── Species_Name_tree_only.usda        # Tree mesh only (no twigs)
├── Species_Name.usda                  # Standard USD with twigs (DCC compatible)
└── Species_Name_NaniteAssembly.usda  # Nanite Assembly for Unreal (IMPORT THIS)
```

**Standard USD** (`Species_Name.usda`):

- Compatible with all DCC applications (Blender, Houdini, Maya)
- Complete tree + twig data inline
- Use for previewing, editing, or non-Unreal workflows

**Nanite Assembly USD** (`Species_Name_NaniteAssembly.usda`):

- Optimized for Unreal Engine 5.7+
- Uses official Unreal USD schemas
- References external files (tree, twigs)
- Automatic Nanite conversion on import
- Efficient PointInstancer for twigs
- **Import this file in Unreal Engine**

## Nanite Assembly Structure

```
TreeSpecies_NaniteAssembly/
├── [apiSchemas: NaniteAssemblyRootAPI]
├── unreal:naniteAssembly:meshType = "staticMesh"
│
├── TreeMesh/ [apiSchemas: NaniteAssemblyExternalRefAPI]
│   └── references → Species_Name_tree_only.usda
│
└── TwigInstances/ (PointInstancer)
    ├── TwigPrototypes/
    │   ├── twiglong/ [apiSchemas: NaniteAssemblyExternalRefAPI, instanceable]
    │   │   └── references → twig_long.usda
    │   └── twigshort/ [apiSchemas: NaniteAssemblyExternalRefAPI, instanceable]
    │       └── references → twig_short.usda
    │
    ├── positions: (x, y, z) array
    ├── orientations: quaternion array
    ├── scales: uniform array
    └── protoIndices: instance type mapping
```

## Usage Examples

### Species Library

```bash
# Default: Creates standard USD + Nanite Assembly
python src/growpy/cli/generate_species_library.py --formats usda

# With twigs included as PointInstancer
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs

# Export all formats (FBX, standard USD, Nanite Assembly)
python src/growpy/cli/generate_species_library.py --formats fbx usda --include-twigs

# Ultra quality with Nanite Assemblies
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --resolution 32 \
  --flushes 15

# Disable Nanite Assembly (standard USD only)
python src/growpy/cli/generate_species_library.py --formats usda --no-nanite-assembly
```

### Forest Generation

```bash
# Default: Creates Nanite Assemblies for all species
python src/growpy/cli/generate_forest.py forest.csv --formats usda

# Ultra quality with Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv --quality ultra --formats usda

# Multiple formats
python src/growpy/cli/generate_forest.py forest.csv --formats fbx usd usda

# Disable Nanite Assembly
python src/growpy/cli/generate_forest.py forest.csv --formats usda --no-nanite-assembly
```

### Python API

```python
from pathlib import Path
from growpy import create_grove, get_config
from growpy.io.blender_export import export_grove_tree_as_usda_native
import the_grove_22_core as gc

config = get_config()
grove = create_grove("European Beech")

# Add and simulate tree
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export with Nanite Assembly (default: True)
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("data/output/beech.usda"),
    species_name="European Beech",
    include_twigs=True,
    create_nanite_assembly=True,  # Creates *_NaniteAssembly.usda
    resolution=32,
)

# Disable Nanite Assembly creation
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("data/output/beech.usda"),
    species_name="European Beech",
    create_nanite_assembly=False,  # Standard USD only
    resolution=32,
)
```

## Unreal Engine Setup

### 1. Set Environment Variable

**macOS/Linux**:

```bash
export PXR_PLUGINPATH_NAME="/Users/yourusername/Developer/the-grove/data/unreal_schema"
```

**Windows**:

```
System Properties → Environment Variables
Add: PXR_PLUGINPATH_NAME = C:\path\to\the-grove\data\unreal_schema
```

### 2. Verify in Unreal

Launch Unreal Engine and check Output Log:

```
LogUsd: Registered Unreal schema plugin
LogUsd: Found NaniteAssemblyRootAPI schema
```

### 3. Import Nanite Assembly

1. Content Browser → Import
2. Select `*_NaniteAssembly.usda`
3. Import Settings:
   - ✅ Import Geometry
   - ✅ Import as Static Meshes
   - ❌ Import Actors (we want assets)
   - ❌ Apply World Transform
4. Click Import

**Result**: Static Mesh asset with:

- Automatic Nanite conversion
- Twig instances as HISM/ISM
- Material instances
- Optimized hierarchy

## Benefits

### Performance

- **Automatic LODs**: Nanite generates runtime LODs
- **GPU-Driven**: Culling entirely GPU-side
- **Streaming**: Meshes stream based on visibility
- **Instancing**: PointInstancer = minimal memory overhead

### Workflow

- **Single Asset**: Import once, use everywhere
- **Hierarchical**: Parent-child relationships preserved
- **No Manual Setup**: Schema drives automatic optimization
- **Variations**: Multiple variations for procedural variety

### Quality

- **No Pop**: Smooth LOD transitions
- **High Detail**: Millions of triangles supported
- **Preserve Area**: Foliage doesn't thin at distance
- **Two-Sided**: Leaf materials render correctly

## Testing

To test the integration:

```bash
# 1. Set schema environment variable
export PXR_PLUGINPATH_NAME="/Users/maximiliansperlich/Developer/the-grove/data/unreal_schema"

# 2. Generate test species with Nanite Assembly
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --output-dir data/output/test_nanite

# 3. Check output files
ls -la data/output/test_nanite/USD/

# Expected files per species:
# - SpeciesName_tree_only.usda
# - SpeciesName.usda
# - SpeciesName_NaniteAssembly.usda

# 4. Validate USD file
usdchecker data/output/test_nanite/USD/*_NaniteAssembly.usda

# 5. Import into Unreal Engine 5.7+ and verify Nanite conversion
```

## References

- **Video Tutorial**: [Nanite Assemblies in UE 5.7](https://www.youtube.com/watch?v=-ZGWblVF8Qk)
- **Blog Post**: [Nanite Assemblies: DCC to UE Import](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)
- **Unreal Docs**: [USD in Unreal Engine](https://docs.unrealengine.com/5.7/en-US/USD/)
- **USD Docs**: [Schema Definition](https://openusd.org/release/api/class_usd_schema_registry.html)

## Implementation Details

### Schema Location

- `data/unreal_schema/generatedSchema.usda` contains all Unreal API schemas
- `PXR_PLUGINPATH_NAME` must point to this directory
- Unreal automatically discovers and registers schemas on startup

### Export Flow

1. Grove builds tree mesh
2. Export tree as USD using Grove's native `model_to_usda_string()`
3. Save tree-only USD (`*_tree_only.usda`)
4. Create standard USD with twigs using twig placement system (`*.usda`)
5. If `create_nanite_assembly=True`:
   - Create new USD stage with NaniteAssemblyRootAPI
   - Reference tree-only USD with NaniteAssemblyExternalRefAPI
   - Add twig prototypes with NaniteAssemblyExternalRefAPI
   - Create PointInstancer with twig instances
   - Save as `*_NaniteAssembly.usda`

### Coordinate System

- Blender: Z-up, right-handed
- Unreal: Z-up, left-handed
- Conversion applied: (X, Y, Z) → (X, -Y, Z)
- Normals converted: (X, Y, Z) → (X, -Y, Z)
- Rotations converted to Unreal space

## Next Steps

1. **Test in Unreal Engine**: Import Nanite Assembly USD and verify automatic Nanite conversion
2. **Performance Testing**: Compare standard USD vs Nanite Assembly import performance
3. **Workflow Integration**: Test with PCG (Procedural Content Generation) and Foliage tools
4. **Quality Presets**: Create optimized presets for hero vs background trees
5. **Documentation**: Add Unreal import workflow screenshots/video

## Status

✅ Schema integration complete  
✅ CLI scripts updated  
✅ Export implementation complete  
✅ Documentation created  
⏳ Testing in Unreal Engine pending  
⏳ Performance benchmarking pending  

## Files Modified/Created

**Modified**:

- `src/growpy/cli/generate_forest.py`
- `src/growpy/cli/generate_species_library.py`
- `src/growpy/io/blender_export.py`

**Created**:

- `data/unreal_schema/generatedSchema.usda`
- `data/unreal_schema/plugInfo.json`
- `data/unreal_schema/README.md`
- `data/unreal_schema/unreal/` (directory)
- `docs/growpy/NANITE_ASSEMBLY_GUIDE.md`
- `NANITE_ASSEMBLY_INTEGRATION.md` (this file)

**Existing** (already implemented):

- `src/growpy/io/unreal_nanite_assembly.py`
- `src/growpy/io/twig_placement.py`

---

**Integration by**: GitHub Copilot  
**Date**: 2025-01-07  
**References**: YouTube tutorial, ArtStation blog, Unreal Engine 5.7 USD documentation
