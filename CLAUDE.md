# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is **The Grove 2.2** - a procedural tree generation system with a Python interface. The project combines a Rust-based core (`the_grove_22_core`) with a Python wrapper (`growpy`) to generate realistic 3D tree models from CSV forest data.

## Key Commands

### Environment Setup
```bash
# Setup conda environment
conda env create --prefix ./.conda -f environment.yml
conda activate ./.conda

# The environment automatically sets PYTHONPATH for the_grove_22_core module
```

### Primary Development Commands
```bash
# Generate forest from demo data
python generate_forest.py
```


## Architecture Overview

### Core Components Architecture

**The Grove 2.2 Core** (`src/the_grove_22/`):
- **Rust-based simulation engine** with Python bindings
- **Platform-specific binaries**: `the_grove_22_core_{platform}.so/.pyd`
- **Species presets**: 50+ JSON files with realistic tree parameters
- **Textures and twigs**: Supporting assets for 3D rendering

**GrowPy Python Interface** (`src/growpy/`) - **Simplified and Cleaned**:
- **core/**: Essential functionality only
  - **config.py**: Configuration management with LOD presets  
  - **species.py**: Species validation and preset loading
  - **grove.py**: Grove object management and operations
  - **validate.py**: Data validation utilities
- **io/**: USD multi-LOD export only
  - **models.py**: USD model export with multi-LOD variants and twig instancing

**Utilities** (`src/utils/`):
- **species_growth_analysis.py**: Generate species-wide height curves and age prediction models (run once for all species)
- **convert_twigs_to_usd.py**: Convert Grove twig .blend files to USD prototypes for instancing

### Data Flow Architecture

1. **Utilities Setup** (run once):
   - **Species Growth Analysis**: `python src/utils/species_growth_analysis.py` generates growth models for all species
   - **USD Twig Conversion**: `python src/utils/convert_twigs_to_usd.py` converts .blend twigs to USD prototypes

2. **CSV Input** → **Age Prediction** (`generate_forest.py`):
   - CSV requires: `x, y, z, species, height` (no age column needed)
   - Loads pre-generated species growth models from utils
   - Applies age predictions to all trees using cached linear regression models

3. **Forest Simulation** → **Light Competition**:
   - Groups trees by species into separate `Grove` objects
   - Simulates growth with shared light environment
   - Uses delay system to synchronize tree growth to target heights

4. **USD Multi-LOD Export** → **Game Engine Ready**:
   - **JSON files**: For Blender import (`data/output/{input_name}/groves/`)
   - **USD multi-LOD files**: Single files per tree with all LOD variants and twig instances (`data/output/{input_name}/usd_trees_multi_lod/{species}/`)
   - **No FBX needed**: Game engines (Unity 2024+, Unreal 5+) support USD natively

### Configuration System Architecture

**Three-tier configuration**:
1. **Default values** in `GrowPyConfig` dataclass
2. **config.ini file** with validation and error handling
3. **Runtime overrides** in code

**LOD (Level of Detail) system**: 6 predefined levels (LOD0_Ultra to LOD5_Minimal) with automatic polygon reduction estimation.

## Critical Implementation Details

### Memory Management (Rust-Python Boundary)
The Grove core is Rust-based with different ownership semantics:
```python
# ❌ This creates copies and won't persist changes
grove.trees[0].some_property = value

# ✅ Always use getter/setter pattern
props = grove.get_properties()
props.some_property = value
grove.set_properties(props)
```

### Species Preset System
- **50+ species** with scientific names (e.g., "Fagaceae - European oak")
- **Preset validation** against available species list
- **JSON-based properties** applied via `gc.io.properties_from_json_string()`

### Platform Compatibility
- **Windows**: `the_grove_22_core_windows.pyd`
- **macOS (Apple Silicon)**: `the_grove_22_core_macos.so`
- **macOS (Intel)**: `the_grove_22_core_macos_intel.so`

## Key Configuration Parameters

### Simulation Control
- `height_model_flushes`: Growth cycles for height curve generation (default: 75)

### Build Quality Control
- `resolution`: Branch cross-section sides (4-24, default: 16)
- `resolution_reduce`: Thickness-based reduction rate (0.0-1.0, default: 0.8)
- `build_cutoff_thickness`: Minimum branch thickness to build (default: 0.0)
- `build_blend`/`build_end_cap`: Quality vs performance trade-offs

## Working with Forest Data

### CSV Format Requirements
```csv
x,y,z,species,height
0.0,0.0,0.0,Fagaceae - European oak,12.5
10.0,0.0,0.0,Pinaceae - Scots pine,8.2
```

### Age Prediction Process
1. **Height curve generation**: Simulates individual trees of each species
2. **Linear regression**: Maps height to required growth flushes
3. **Delay calculation**: Synchronizes growth so all trees reach target heights simultaneously

### Multi-Species Forest Simulation
- **Separate groves per species** (required for proper preset application)
- **Shared light environment** via `grove.calculate_shade_together()`
- **Synchronized growth cycles** with species-specific delays

## USD Multi-LOD Export Pipeline

**Native Game Engine Support**:
- **USD variants**: Multiple LOD levels in single files (LOD0_Ultra through LOD5_Minimal)
- **Twig instancing**: Efficient USD prototypes with references for massive performance gains
- **Direct import**: Unity 2024+ and Unreal 5+ support USD natively

## Common Issues & Solutions

### Import Errors
- **the_grove_22_core not found**: Check `PYTHONPATH` includes `src/the_grove_22/modules`

### Data Validation
- **Species names** must match preset files exactly (case-sensitive)
- **Coordinates** must be finite numbers (no inf/nan)
- **Heights** must be positive values
- **Duplicate positions** generate warnings but don't fail

## Development Workflow

When modifying the codebase:
1. **Test individual modules** using their `if __name__ == "__main__"` blocks
2. **Validate configuration changes** with `config.py` validation
3. **Run complete pipeline** with `generate_forest.py`
4. **Check output structure** in `data/output/{input_name}/`

The system is designed to be resilient and efficient with:
- **Clean, minimal API** without verbose logging or complex exception handling
- **Separated concerns**: Analysis utilities run once, forest generation uses cached models
- **USD-focused**: Eliminates FBX pipeline complexity while providing superior performance