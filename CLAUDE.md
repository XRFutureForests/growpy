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

# Direct growpy usage (run example simulation)
python -m growpy.workflows.simulation

# Test FBX conversion functionality
python -m growpy.io.fbx --input_dir data/output/demo_forest/tree_models --output_dir data/output/fbx

# Run configuration validation
python -m growpy.core.config
```

### Testing & Validation
```bash
# Test individual modules
python src/growpy/workflows/simulation.py        # Runs example simulation
python src/growpy/core/config.py                 # Shows LOD configurations
python src/growpy/io/fbx.py                      # Tests FBX conversion pipeline

# Test core functionality
python src/growpy/core/height.py                 # Tests height curve generation
python src/growpy/core/predict.py                # Tests age prediction

# Test I/O operations
python src/growpy/io/csv.py                      # Tests CSV loading functionality
python src/growpy/io/models.py                   # Tests model export functionality

# Test workflows
python src/growpy/workflows/forest.py            # Tests complete workflow

# Validate CSV format (check species against presets)
python -c "from growpy.core.species import list_species; print(list_species())"
```

## Architecture Overview

### Core Components Architecture

**The Grove 2.2 Core** (`src/the_grove_22/`):
- **Rust-based simulation engine** with Python bindings
- **Platform-specific binaries**: `the_grove_22_core_{platform}.so/.pyd`
- **Species presets**: 50+ JSON files with realistic tree parameters
- **Textures and twigs**: Supporting assets for 3D rendering

**GrowPy Python Interface** (`src/growpy/`):
- **core/**: Core functionality and configuration
  - **config.py**: Configuration management with LOD presets  
  - **species.py**: Species validation and preset loading
  - **grove.py**: Grove object management and operations
  - **height.py**: Height curve generation and analysis
  - **predict.py**: Age prediction from height models
  - **validate.py**: Data validation utilities
- **io/**: Input/output operations
  - **csv.py**: CSV file loading and validation
  - **models.py**: 3D model export (OBJ, USD formats)
  - **grove.py**: Grove JSON serialization for Blender
  - **export.py**: Multi-format export coordination (JSON, USD, FBX)
  - **fbx.py**: Blender-based FBX conversion with LOD combining
- **workflows/**: High-level workflow orchestration
  - **simulation.py**: Main forest generation pipeline with age prediction
  - **forest.py**: Complete forest generation pipeline
  - **analysis.py**: Height curve generation workflow
  - **export.py**: Model export workflow

### Data Flow Architecture

1. **CSV Input** → **Age Prediction Pipeline**:
   - CSV requires: `x, y, z, species, height` (no age column needed)
   - Generates species-specific height curves through simulation
   - Creates linear regression models to predict age from height
   - Applies age predictions to all trees

2. **Forest Simulation** → **Light Competition**:
   - Groups trees by species into separate `Grove` objects
   - Simulates growth with shared light environment
   - Uses delay system to synchronize tree growth to target heights

3. **Multi-Format Export** → **Organized Output**:
   - **JSON files**: For Blender import (`data/output/{input_name}/groves/`)
   - **USD models**: Individual trees with LOD levels (`data/output/{input_name}/tree_models/{species}/`)
   - **FBX models**: Game engine format via Blender conversion
   - **Analysis data**: Height curves and prediction models

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

### Error Handling Strategy
- **Custom exceptions**: `ValidationError`, `ConfigurationError`, `BlenderOperationError`, `ExportError`
- **Comprehensive logging** with structured error messages
- **Input validation** for coordinates, heights, and species names
- **Bounds checking** for array access and model predictions

### Platform Compatibility
- **Windows**: `the_grove_22_core_windows.pyd`
- **macOS (Apple Silicon)**: `the_grove_22_core_macos.so`
- **macOS (Intel)**: `the_grove_22_core_macos_intel.so`
- **Linux**: May need macOS binary renamed to `the_grove_22_core_linux.so`

## Key Configuration Parameters

### Simulation Control
- `height_model_flushes`: Growth cycles for height curve generation (default: 75)
- `age_to_flush_ratio`: Years per growth flush (default: 1.0, don't modify)
- `growth_cycles`: Auto-calculated from predicted ages if not specified

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

## FBX Export Pipeline

**Blender Integration**:
- **Automatic USD→FBX conversion** via `bpy` module
- **LOD combining**: Groups all LOD levels into single FBX files
- **Species organization**: Maintains folder structure during conversion
- **Error handling**: Graceful fallbacks when Blender unavailable

## Common Issues & Solutions

### Import Errors
- **the_grove_22_core not found**: Check `PYTHONPATH` includes `src/the_grove_22/modules`
- **Platform binary missing**: Rename/symlink appropriate binary file

### Performance Optimization
- **Reduce `height_model_flushes`** (not `age_to_flush_ratio`) for faster simulation
- **Use higher LOD levels** (LOD3_Low, LOD4_VeryLow) for lower polygon counts
- **Process species separately** for large forests to manage memory

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

The system is designed to be resilient with comprehensive error handling and validation at each step.