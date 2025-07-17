# Configuration Updates Summary

This document summarizes the updates made to the GrowPy configuration system.

## Key Changes Made

### 1. **Separated Height Model and Simulation Parameters**

- **New**: `height_model_flushes` - Controls how many flushes are used specifically for generating height curves
- **Updated**: `growth_cycles` - Now optional (auto-calculated from tree ages if not set)
- **New**: `age_to_flush_ratio` - Configurable ratio for converting tree age to growth flushes (default: 4.0 years per flush)

### 2. **Added config.ini Support**

- **New**: `from_config_file()` class method to load configuration from INI files
- **New**: `to_config_file()` method to save configuration to INI files
- **Automatic**: Sample config.ini creation when none exists

### 3. **Removed Unused Parameters**

- All configuration parameters are actively used in the current codebase
- LOD (Level of Detail) configurations are properly organized and documented

### 4. **Enhanced Configuration Structure**

#### [simulation] section

- `height_model_flushes`: Number of flushes for height curve generation (default: 15)
- `growth_cycles`: Max simulation cycles (auto-calculated if 'none')
- `random_seed`: Seed for reproducible results (42 or 'none')
- `age_to_flush_ratio`: Years of tree age per flush (default: 4.0)

#### [output] section

- `output_dir`: Base output directory
- `fbx_output_dir`: FBX-specific output directory ('none' for auto)

#### [build] section

- `resolution`: Base polygon resolution (default: 16)
- `resolution_reduce`: Branch thinning factor (default: 0.8)
- `texture_repeat`: Bark texture repetitions (default: 3)
- `build_cutoff_age`: Age cutoff for building (default: 0)
- `build_cutoff_thickness`: Thickness cutoff for building (default: 0.0)
- `build_blend`: Smooth branch transitions (default: true)
- `build_end_cap`: Branch end caps (default: true)

## Usage Examples

### Basic Usage (Default Configuration)

```python
from growpy.config import GrowPyConfig

config = GrowPyConfig()
# Uses all default values
```

### Loading from config.ini

```python
config = GrowPyConfig.from_config_file(Path("config.ini"))
```

### Creating a config.ini

```python
config = GrowPyConfig()
config.to_config_file(Path("my_config.ini"))
```

### LOD Configuration

```python
lod_config = GrowPyConfig.create_lod_config("LOD2_Medium")
```

## Benefits

1. **Better Separation of Concerns**: Height modeling and forest simulation can use different parameters
2. **Easier Customization**: Users can modify config.ini without touching code
3. **More Flexible**: Growth cycles can be auto-calculated or manually set
4. **Reproducible**: Proper seed and ratio management for consistent results
5. **Self-Documenting**: Sample config.ini files are automatically generated with defaults

## Migration Notes

- Existing code using `config.growth_cycles` will continue to work
- The `height_model_flushes` parameter specifically controls height curve generation
- Age calculation now uses the configurable `age_to_flush_ratio` instead of hardcoded division by 4
