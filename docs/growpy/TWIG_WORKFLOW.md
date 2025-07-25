# Grove Twig USD Conversion Workflow

This document explains how to convert Grove's .blend twig files to USD format for use in GrowPy's twig instancing system.

## Overview

Grove manages twigs as .blend files in `src/the_grove_22/twigs/`. For general use in Blender and Unreal Engine, these should be converted to USD format using the conversion script.

## Directory Structure

```
src/the_grove_22/twigs/           # Source .blend twig files
├── AspenTwig/
│   ├── AspenTwig.blend
│   └── textures/
├── EuropeanBeechTwig/
│   ├── EuropeanBeechSummerTwig.blend
│   └── textures/
└── [50+ other species...]

data/assets/twigs/                # Converted USD assets (created by conversion)
├── prototypes/                   # USD prototype files for instancing
├── materials/                    # USD material definitions  
├── textures/                     # Texture files copied from Grove
├── catalog.json                  # Twig catalog for GrowPy integration
└── conversion_report.json        # Detailed conversion results
```

## Conversion Process

### 1. Install Requirements

```bash
# Install Blender as Python module (required for .blend file reading)
pip install bpy

# Install USD Python bindings (required for USD file creation)
pip install usd-core
```

### 2. Run Conversion Script

```bash
# Convert all Grove twigs to USD (uses default paths)
python src/utils/convert_twigs_to_usd.py

# With custom paths
python src/utils/convert_twigs_to_usd.py --twigs_dir src/the_grove_22/twigs --output_dir data/assets/twigs

# Enable verbose logging
python src/utils/convert_twigs_to_usd.py --verbose
```

### 3. Validate Conversion

```bash
# Check conversion status without running conversion
python src/utils/convert_twigs_to_usd.py --validate-only

# Or test from GrowPy
python -m src.growpy.twig
```

## Conversion Features

### Comprehensive Asset Processing
- **Geometry Extraction**: Extracts mesh data from .blend files using Blender
- **Texture Discovery**: Intelligent texture matching across different naming patterns
- **Material Creation**: USD Preview Surface materials with proper texture mapping
- **Prototype Generation**: Instanceable USD prototypes for efficient rendering

### Texture Support
- **Diffuse Maps**: Color/albedo textures
- **Normal Maps**: Surface detail and bump mapping
- **Alpha Maps**: Transparency and cutout effects
- **Roughness/Metallic**: PBR material properties
- **Translucent Maps**: Subsurface scattering effects

### Species Classification
Twigs are automatically classified into categories:
- **Deciduous**: Oak, Maple, Beech, Birch, Linden, Ash
- **Coniferous**: Pine, Fir, Cedar, Spruce
- **Broadleaf**: Gum, Olive, Magnolia, Cherry
- **Specialty**: Other unique species

## Integration with GrowPy

### Automatic Detection
GrowPy automatically detects converted USD assets:

```python
from growpy import twig

# Check if converted assets are available
if twig.check_twig_assets_available():
    print("Using high-quality USD twig assets")
else:
    print("Using simple fallback prototypes")

# Get conversion status
status = twig.get_twig_conversion_status()
print(f"Available twigs: {status['successful_conversions']}")
```

### Species-Specific Prototypes
```python
# Get species-specific twig prototype
prototype_path = twig.get_species_twig_prototype("Norway spruce")
if prototype_path:
    print(f"Using species-specific twig: {prototype_path}")
```

### Enhanced USD Export
```bash
# Generate basic USD files
python generate_forest.py

# Enhance with converted twig instances
python enhance_usd.py --twigs

# Or enhance with all features
python enhance_usd.py --all
```

## USD Output Structure

Each converted twig becomes a USD prototype:

```
TreeName_prototype.usda
├── /TreeName_Prototype          # Root transform
└── /TreeName_Prototype/Mesh     # Geometry with materials
    ├── Points, faces, normals   # Mesh data
    ├── UV coordinates           # Texture mapping
    └── Material binding         # USD Preview Surface
```

## Performance Benefits

### Instancing Efficiency
- **PointInstancer**: Thousands of twigs with minimal memory overhead
- **Prototype References**: Single geometry shared across all instances
- **GPU Optimization**: Hardware-accelerated instancing in modern engines

### Cross-Platform Compatibility
- **Blender**: Native USD import with materials and instances
- **Unreal Engine**: USD Stage import with full feature support
- **Other Applications**: Standard USD compatibility

## Workflow Integration

### Full Pipeline
1. **Convert Twigs**: `python src/utils/convert_twigs_to_usd.py`
2. **Generate Forest**: `python generate_forest.py`
3. **Enhance USD**: `python enhance_usd.py --all`
4. **Import to Engine**: Use enhanced USD files in Blender/Unreal

### Fallback Behavior
If conversion hasn't been run:
- GrowPy creates simple sphere prototypes as fallback
- Twig instancing still works but with basic geometry
- Conversion can be run later to upgrade to high-quality assets

## Troubleshooting

### Common Issues

**"Blender (bpy) module not available"**
- Install: `pip install bpy`
- Requires significant disk space (~300MB)

**"USD (pxr) module not available"**
- Install: `pip install usd-core`
- Alternative: `pip install usd-python`

**"No .blend files found"**
- Ensure Grove is properly installed with twig assets
- Check path: `src/the_grove_22/twigs/`

### Validation Commands
```bash
# Check conversion status
python src/utils/convert_twigs_to_usd.py --validate-only

# Test twig module
python -m src.growpy.twig

# Test enhancement workflow
python enhance_usd.py --twigs --directory data/output/small_demo
```

## Benefits Summary

✅ **High-Quality Assets**: Real Grove twig geometry and textures
✅ **Performance Optimized**: GPU-friendly instancing with PointInstancer  
✅ **Cross-Platform**: Works in Blender, Unreal, and other USD applications
✅ **Automated Workflow**: One-time conversion with automatic integration
✅ **Fallback Support**: Works even without conversion (simple prototypes)
✅ **Material Support**: Full PBR materials with textures
✅ **Species Variety**: 50+ different twig types with proper classification

The conversion process transforms Grove's proprietary .blend twig assets into industry-standard USD format, enabling high-performance twig instancing across multiple 3D applications while maintaining the visual quality of the original Grove assets.