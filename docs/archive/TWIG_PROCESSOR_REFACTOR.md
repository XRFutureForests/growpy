# Twig Processor Refactoring Summary

**Date:** 2025-01-14

## Overview

Refactored the `create_processor_script()` function from `convert_twigs.py` into a standalone module for improved debuggability and to avoid Blender C++ memory issues.

## Changes Made

### 1. Created New Module: `src/growpy/io/blender_twig_processor.py`

Extracted all Blender-specific processing logic into a dedicated module that:

- Runs directly as a standalone script in Blender's Python environment
- Contains all twig processing functions (skeleton creation, material setup, export)
- Is self-contained with no imports from the main growpy package (avoids import cycles)
- Can be debugged independently with proper IDE support

**Key Functions:**

- `_add_skeleton_to_twig_fbx()` - Add single-bone skeleton for FBX skeletal meshes
- `_add_skeleton_to_twig_usd()` - Add single-bone skeleton for USD skeletal meshes
- `standardize_twig_name()` - Standardize twig naming conventions
- `classify_texture_from_name()` - Classify texture types from filenames
- `setup_materials_with_textures()` - Setup Blender materials with PBR textures
- `process_twig_file()` - Main processing function for converting .blend files

### 2. Updated `convert_twigs.py`

Replaced the embedded script generation with:

- `get_processor_script_path()` - Returns path to the processor module
- Removed `create_processor_script()` function (900+ lines of embedded string code)
- Removed temporary file creation/cleanup logic
- Simplified subprocess execution to use the module directly

## Benefits

1. **Debuggability**: The processor module can now be debugged with proper IDE support, breakpoints, and stack traces
2. **Memory Management**: No longer creates temporary files or holds large strings in memory
3. **Maintainability**: Code is now in a proper Python module with syntax highlighting and linting
4. **Testability**: Functions can be tested independently when bpy module is available
5. **Code Quality**: Proper module structure with docstrings and type hints

## Technical Details

### Before

```python
def create_processor_script() -> str:
    return '''
    # 900+ lines of embedded Python code as string
    '''
```

### After

```python
# src/growpy/io/blender_twig_processor.py - standalone module
def process_twig_file(blend_file, output_dir, formats, species_name):
    """Process a single twig blend file."""
    # Proper Python code with IDE support
```

## Usage

No changes to the CLI interface - the tool works exactly the same:

```bash
python convert_twigs.py data/assets/twigs --formats fbx usda
```

The only difference is that the Blender processor is now a proper module instead of a dynamically generated string.

## Compatibility

- **Blender Python Environment**: The processor module runs in Blender's Python (with bpy)
- **Main Environment**: The convert_twigs.py CLI runs in the conda environment
- **No Import Cycles**: The processor module is completely self-contained

## Files Modified

- `src/growpy/cli/convert_twigs.py` - Simplified to use module path
- `src/growpy/io/blender_twig_processor.py` - New processor module (created)

## Testing

Test the refactored tool with:

```bash
# Convert sample twigs
python src/growpy/cli/convert_twigs.py data/assets/twigs/Betulaceae_Downy_birch --formats fbx usda

# Verify output and check for errors
```

## Notes

The processor module must remain self-contained (no growpy imports) to avoid circular dependencies when run by Blender's Python interpreter.
