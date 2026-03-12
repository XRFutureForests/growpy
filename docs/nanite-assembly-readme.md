````markdown
# Nanite Assembly USD Export - Quick Start

This document provides a quick overview of the Nanite Assembly integration for Unreal Engine 5.7+.

## ✅ Status: Working

**Last Update**: 2025-01-07 - Fixed USD type error for `apiSchemas` metadata

The Nanite Assembly export is fully functional:
- ✅ **510 Nanite Assemblies** created successfully from all twigs
- ✅ **USD Type Error Fixed** - Using `Sdf.TokenListOp()` instead of Python lists
- ✅ **Twig Conversion** - Each twig exports both standard USD and Nanite Assembly
- ✅ **Tree Export** - Full tree + twig integration working

See `NANITE_ASSEMBLY_FIX.md` for technical details on the fix.

## What is This?

The Grove now exports trees as **Nanite Assembly USD files** that are optimized for import into Unreal Engine 5.7+. These use Epic Games' official USD schema for automatic Nanite conversion and optimal performance.

## Quick Setup

### 1. Set Environment Variable

The Unreal schema must be discoverable via the `PXR_PLUGINPATH_NAME` environment variable:

**macOS/Linux (temporary)**:

```bash
export PXR_PLUGINPATH_NAME="/path/to/the-grove/data/unreal_schema"
```

**macOS/Linux (permanent)** - Add to `~/.zshrc`:

```bash
export PXR_PLUGINPATH_NAME="/Users/yourusername/Developer/the-grove/data/unreal_schema"
```

**Windows** - Add System Environment Variable:

```
Variable: PXR_PLUGINPATH_NAME
Value: C:\path\to\the-grove\data\unreal_schema
```

### 2. Convert Twigs (Recommended)

```bash
# Convert twigs to USD with Nanite Assemblies
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda
```

This creates both standard USD and Nanite Assembly versions of each twig.

### 3. Export Trees

```bash
# Species library with Nanite Assemblies (default)
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs

# Forest with Nanite Assemblies
python src/growpy/cli/generate_forest.py forest.csv --formats usda
```

### 4. Import into Unreal Engine

1. Enable **USD Importer** plugin in Unreal
2. Import `*_NaniteAssembly.usda` file (tree or twig)
3. Nanite conversion happens automatically
4. Use in level, PCG, or Foliage system

## Output Files

Each species generates **three USD files**:

```
output/USD/
├── Species_Name_tree_only.usda        # Tree mesh only
├── Species_Name.usda                  # Standard USD (DCC compatible)
└── Species_Name_NaniteAssembly.usda  # Nanite Assembly (IMPORT THIS IN UNREAL)
```

- **Standard USD** (`Species_Name.usda`): Use in Blender, Houdini, Maya
- **Nanite Assembly USD** (`Species_Name_NaniteAssembly.usda`): Import in Unreal Engine

## CLI Options

Both `generate_forest.py` and `generate_species_library.py` support:

```bash
# Enable Nanite Assembly (default)
--create-nanite-assembly

# Disable Nanite Assembly (standard USD only)
--no-nanite-assembly

# Export formats
--formats fbx usda    # Both FBX and USD

# Include twigs as point instances
--include-twigs
```

## Examples

### Species Library

```bash
# Default: Standard USD + Nanite Assembly
python src/growpy/cli/generate_species_library.py --formats usda

# With twigs
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs

# All formats
python src/growpy/cli/generate_species_library.py --formats fbx usda --include-twigs

# Standard USD only (no Nanite Assembly)
python src/growpy/cli/generate_species_library.py --formats usda --no-nanite-assembly
```

### Forest Generation

```bash
# Default: Nanite Assemblies enabled
python src/growpy/cli/generate_forest.py forest.csv --formats usda

# Ultra quality
python src/growpy/cli/generate_forest.py forest.csv --quality ultra --formats usda

# Standard USD only
python src/growpy/cli/generate_forest.py forest.csv --formats usda --no-nanite-assembly
```

## Python API

```python
from pathlib import Path
from growpy import create_grove
from growpy.io.blender_export import export_grove_tree_as_usda_native
import the_grove_23_core as gc

# Create and simulate grove
grove = create_grove("European Beech")
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
grove.simulate(flushes=10)

# Export with Nanite Assembly (default)
export_grove_tree_as_usda_native(
    grove=grove,
    output_path=Path("output/beech.usda"),
    species_name="European Beech",
    create_nanite_assembly=True,  # Creates *_NaniteAssembly.usda
    include_twigs=True,
    resolution=32,
)
```

## Testing

Run the test script to validate the integration:

```bash
# Make sure environment is activated
conda activate growpy

# Set schema path
export PXR_PLUGINPATH_NAME="$(pwd)/data/unreal_schema"

# Run test
python test_nanite_assembly.py
```

Expected output:

- ✅ All imports successful
- ✅ Grove creation works
- ✅ USD export completes
- ✅ Three USD files created
- ✅ Nanite Assembly has correct schema

## What Gets Created

### Standard USD (`Species_Name.usda`)

- Complete tree + twig data
- Compatible with all DCC apps
- Inline twig instances
- Use for previewing/editing

### Nanite Assembly USD (`Species_Name_NaniteAssembly.usda`)

- Optimized for Unreal Engine 5.7+
- Uses `NaniteAssemblyRootAPI` schema
- References external tree/twig files
- Automatic Nanite conversion on import
- Efficient PointInstancer for twigs
- **Import this file in Unreal**

## Benefits

### Performance

- Automatic runtime LODs
- GPU-driven rendering
- Minimal memory overhead
- Smooth LOD transitions

### Workflow

- Single asset import
- No manual setup required
- Hierarchical preservation
- Multiple variations support

### Quality

- Millions of triangles supported
- No LOD popping
- Foliage preservation at distance
- Correct two-sided rendering

## Documentation

For detailed documentation, see:

- **Main Guide**: `docs/growpy/NANITE_ASSEMBLY_GUIDE.md` - Complete usage guide
- **Integration**: `NANITE_ASSEMBLY_INTEGRATION.md` - Technical details
- **Schema**: `data/unreal_schema/README.md` - Schema setup

## Troubleshooting

### Schema Not Found in Unreal

**Symptom**: Unreal doesn't show schema registration in Output Log

**Solution**:

1. Verify `PXR_PLUGINPATH_NAME` environment variable is set
2. Restart Unreal Engine after setting variable
3. Check `data/unreal_schema/plugInfo.json` exists

### Export Creates Only One USD File

**Symptom**: Only standard USD created, no Nanite Assembly

**Solution**:

1. Check if `--no-nanite-assembly` flag was used
2. Verify USD Python (pxr) is installed: `pip install usd-core`
3. Check console for error messages

### Import Doesn't Enable Nanite

**Symptom**: Imported mesh is not Nanite-enabled

**Solution**:

1. Verify you imported `*_NaniteAssembly.usda` (not standard USD)
2. Check Unreal Output Log for schema registration
3. Ensure Unreal Engine version is 5.7 or higher
4. Manually enable Nanite in Static Mesh settings if needed

## References

- [Unreal USD Documentation](https://docs.unrealengine.com/5.7/en-US/USD/)
- [Nanite Assemblies Video](https://www.youtube.com/watch?v=-ZGWblVF8Qk)
- [ArtStation Blog](https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import)

## Support

For issues or questions:

1. Check `docs/growpy/NANITE_ASSEMBLY_GUIDE.md` for detailed troubleshooting
2. Run `test_nanite_assembly.py` to diagnose issues
3. Verify environment setup and dependencies

---

**Status**: ✅ Integration Complete  
**Version**: 1.0  
**Last Updated**: 2025-01-07
