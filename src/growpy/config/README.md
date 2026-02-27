# GrowPy Configuration Module

This module handles configuration for the GrowPy pipeline.

## Central Configuration: growpy.toml

All pipeline defaults are defined in `src/growpy/growpy.toml` (co-located with the package). CLI arguments override TOML values.

**Resolution order:** dataclass defaults -> growpy.toml -> CLI arguments

**TOML file discovery:**

1. `GROWPY_CONFIG` environment variable
2. `src/growpy/growpy.toml` (package directory)
3. `./growpy.toml` (current working directory fallback)

## Files

### core.py

Central configuration class (`GrowPyConfig`) providing:

- TOML loading via `from_toml(path)`
- CLI argument merging via `resolve(args)`
- Species lookup functionality
- Asset path resolution
- Growth model access
- Color settings
- LOD configurations

### tree_asset_lookup.csv

**Master species lookup table** mapping tree species to their assets and configurations.

**Location**: This file should be placed here (`src/growpy/config/tree_asset_lookup.csv`) as the default configuration.

**Why Here?**

- ✅ **Packaged with Code** - Distributed as part of the module
- ✅ **Co-located** - Lives with the config code that uses it
- ✅ **Default Config** - Provides out-of-the-box functionality
- ✅ **Version Controlled** - Configuration is part of the codebase

**Override Locations:**
Users can override this file by placing a custom version at:

1. `config/tree_asset_lookup.csv` (project root)
2. `data/tree_asset_lookup.csv` (legacy)

See `config/README.md` for override instructions.

## CSV Format

```csv
Common Name,Scientific Name,Preset,Twig,Growth Model,Branch Color,Leaf Color
European beech,Fagus sylvatica,Fagaceae - Beech.seed.json,EuropeanBeechTwig,Fagaceae_Beech,#b2a599,#4c9933
```

**Columns:**

- `Common Name` - Human-readable species name for API calls
- `Scientific Name` - Scientific nomenclature
- `Preset` - Grove preset JSON filename
- `Twig` - Twig asset identifier (or "—" if none)
- `Growth Model` - Growth model directory name
- `Branch Color` - Hex color for branches (e.g., "#b2a599")
- `Leaf Color` - Hex color for leaves (e.g., "#4c9933")

## Usage

```python
from growpy import get_config

config = get_config()

# Get all species
species = config.get_available_species()

# Get species details
beech = config.get_species_data("European beech")

# Get specific paths
preset = config.get_preset_path("European beech")
model = config.get_growth_model_path("European beech")
twig = config.get_twig_for_species("European beech")

# Get colors (hex converted to RGB tuples 0-1 range)
colors = config.get_species_colors("European beech")
# Returns: {'branch_color': (0.698, 0.647, 0.6), 'leaf_color': (0.298, 0.6, 0.2)}
```

## Adding New Species

To add a new species to the lookup table:

1. Ensure you have the Grove preset file
2. (Optional) Prepare twig assets
3. Add entry to `tree_asset_lookup.csv`:

```csv
Douglas fir,Pseudotsuga menziesii,Pinaceae - Douglas fir.seed.json,DouglasFirTwig,Pinaceae_Douglas_fir,#6b5447,#2d6b28
```

1. Run growth model creation:

```bash
python src/growpy/cli/create_growth_models.py --species "Douglas fir"
```

The growth model will be created and the `Growth Model` column will be auto-updated.

## Auto-Update

The `create_growth_models.py` script automatically updates the `Growth Model` column when generating new models. A backup is created before any updates.

## Fuzzy Matching

The config supports fuzzy species name matching:

```python
# All of these work:
config.get_preset_path("European beech")  # Exact
config.get_preset_path("beech")           # Partial
config.get_preset_path("Beech")           # Case insensitive
```

## Color Format

Colors are stored as hex strings but returned as RGB tuples (0-1 range) for use with rendering engines:

```python
# In CSV: "#b2a599"
# Returned: (0.698, 0.647, 0.6)
```

This format is compatible with:

- Blender materials
- Grove color settings
- Most 3D engines
