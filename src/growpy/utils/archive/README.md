# Archive - Experimental Twig Export Versions

This directory contains experimental and developmental versions of the twig export functionality that were created during the development process.

## Final Version

The main export functionality is now consolidated in: `../export_twigs.py`

## Archived Versions

These scripts represent the iterative development process:

1. **export_twigs.py** - Original basic version
2. **export_twigs_subprocess.py** - Added subprocess isolation
3. **export_twigs_manual_textures.py** - Manual texture copying
4. **export_twigs_simple_materials.py** - Simple Principled BSDF approach
5. **export_twigs_principled_materials.py** - Enhanced Principled BSDF
6. **export_twigs_fixed.py** - Object centering fixes
7. **export_twigs_smart_textures.py** - Smart texture selection
8. **export_twigs_auto_texture_match.py** - Automatic texture matching
9. **export_twigs_complete_materials.py** - Complete texture type support
10. **export_twigs_preserve_materials.py** - Complex material preservation

## Development Journey

The development progressed through these key improvements:

- **Memory crash fixes** - Subprocess isolation
- **Texture preservation** - Manual copying and material creation
- **Object positioning** - Centering at origin (0,0,0)
- **Texture classification** - Smart detection of diffuse/alpha/normal/translucent
- **FBX compatibility** - Optimized material setup for FBX export/import
- **Varied naming support** - Handling top/bottom, bump, and single texture scenarios

## Final Solution

The final `export_twigs.py` combines all successful features:
- FBX-optimized Principled BSDF materials
- Automatic texture discovery and classification
- Support for all texture naming conventions
- Proper material connections for FBX compatibility
- Object centering and transform application
- Subprocess isolation for stability