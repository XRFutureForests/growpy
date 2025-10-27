# Solution: Using Blender's Bundled USD (pxr) Module

## Problem

When both `bpy` (Blender Python API) and `pxr` (USD) are installed via pip/conda, Windows DLL conflicts occur:

```
ImportError: DLL load failed while importing _tf: The specified procedure could not be found.
```

This happens because both packages have incompatible TBB (Intel Threading Building Blocks) dependencies.
: bpy.utils.expose_bundled_modules()
## Solution

**Starting from Blender 4.4**, the pip-installed `bpy` package includes a bundled, compatible version of USD/pxr. You can expose it using:

```python
import bpy

# Expose Blender's bundled VFX libraries (including USD/pxr)
bpy.utils.expose_bundled_modules()

# Now you can import pxr without DLL conflicts
from pxr import Usd, UsdGeom, UsdSkel
```

### What gets exposed

Blender 4.5.3 bundles these VFX libraries:

- **pxr** (USD/OpenUSD)
- **MaterialX**
- **OpenImageIO**
- **PyOpenColorIO**
- **openvdb**

### Why this works

- The bundled `pxr` is built with the same TBB version as `bpy`
- Both modules share compatible DLLs
- No process isolation or subprocess workarounds needed
- Single-process export works perfectly

## Implementation

### Before (subprocess workaround)

```python
# Phase 1: Export skeleton via subprocess (pxr only, no bpy)
export_skeleton_via_subprocess(grove, grove_json_path, skeleton_path)

# Phase 2: Export tree with Blender (bpy only, no pxr)
export_grove_tree_as_usda_native(grove, output_path, include_skeleton=False)
```

### After (single process with bundled pxr)

```python
import bpy
bpy.utils.expose_bundled_modules()
from pxr import Usd, UsdGeom, UsdSkel

# Now you can use both bpy and pxr in the same script!
# Export skeleton
stage = Usd.Stage.CreateNew(str(skeleton_path))
# ... skeleton export code ...

# Export tree mesh with Blender
# ... bpy mesh export code ...
```

## Requirements

- Blender Python API (bpy) >= 4.4 (pip-installed)
- NO separate `usd-core` or `pxr` package needed
- NO conda-forge USD package needed

## Advantages

1. **Simpler code**: Single-process, no subprocess complexity
2. **Better performance**: No process spawning overhead
3. **Guaranteed compatibility**: Bundled modules are tested together
4. **Cleaner dependencies**: Only need `bpy` package

## Environment Setup

### Remove conflicting USD packages

```powershell
# Remove pip-installed USD (if any)
pip uninstall usd-core

# Remove conda-installed USD (if any)
conda remove usd-core
```

### Keep only bpy

```yaml
# environment.yml
name: the-grove
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pandas
  - numpy
  - scikit-learn
  - matplotlib
  - tqdm
  - pip:
    - bpy>=4.5  # Includes bundled USD
```

## Verification

```python
import bpy
print(f"bpy version: {bpy.app.version_string}")
print(f"Has expose_bundled_modules: {hasattr(bpy.utils, 'expose_bundled_modules')}")

bpy.utils.expose_bundled_modules()
from pxr import Usd
print(f"USD available: {Usd}")
```

Expected output:

```
bpy version: 4.5.3 LTS
Has expose_bundled_modules: True
USD available: <module 'pxr.Usd._usd' from '.../bpy/4.5/python/lib/site-packages/pxr/Usd/_usd.pyd'>
```

## References

- [Blender 4.4 Release Notes - Python API](https://developer.blender.org/docs/release_notes/4.4/python_api/#blender-as-a-python-module)
- [Charles Flèche's blog - Testing USD hooks outside of Blender](https://charlesfleche.net/til/#til-bpy-expose-bundled-modules)

## Migration Path

1. Remove subprocess skeleton export (`export_skeleton_only.py`)
2. Remove Grove JSON serialization (no longer needed)
3. Update `generate_forest.py` to use bundled pxr
4. Simplify to single-phase export
5. Clean up environment.yml dependencies
