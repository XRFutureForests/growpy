# Configuration Directory (Optional Override)

This directory is for **optional project-level configuration overrides**.

The default configuration files are located in `src/growpy/config/` (distributed with the package).
Place custom configuration files here to override the defaults.

## Files

### tree_asset_lookup.csv (Optional Override)

**Purpose**: Master lookup table mapping tree species to their assets and configurations.

**Default Location**: `src/growpy/config/tree_asset_lookup.csv` (distributed with code)

**Override Location**: `config/tree_asset_lookup.csv` (this directory - for customization)

**Columns**:
- `Common Name` - Human-readable species name (e.g., "European beech")
- `Scientific Name` - Scientific name (e.g., "Fagus sylvatica")
- `Preset` - Grove preset filename (e.g., "Fagaceae - Beech.seed.json")
- `Twig` - Twig asset name (e.g., "EuropeanBeechTwig")
- `Growth Model` - Growth model directory name (e.g., "Fagaceae_Beech")
- `Branch Color` - Hex color for branches (e.g., "#b2a599")
- `Leaf Color` - Hex color for leaves (e.g., "#4c9933")

**Usage**:
```python
from growpy import get_config

config = get_config()

# Get all available species
species = config.get_available_species()

# Get species data
beech_data = config.get_species_data("European beech")

# Get preset path
preset = config.get_preset_path("European beech")

# Get growth model path
model = config.get_growth_model_path("European beech")

# Get species colors
colors = config.get_species_colors("European beech")
# Returns: {'branch_color': (0.698, 0.647, 0.6), 'leaf_color': (0.298, 0.6, 0.2)}
```

**Auto-Update**:
The `create_growth_models.py` script automatically updates the `Growth Model` column when new models are created.

**Backup**:
A backup (`tree_asset_lookup.csv.backup`) is automatically created before any updates.

## Location Hierarchy

The code checks for the lookup table in this order:

1. **`src/growpy/config/tree_asset_lookup.csv`** ⭐ (Default - distributed with package)
2. **`config/tree_asset_lookup.csv`** (This directory - for overrides)
3. **`data/tree_asset_lookup.csv`** (Legacy location - backward compatibility)

## Why `src/growpy/config/`?

The default location is `src/growpy/config/` because:

✅ **Co-located with Code** - Config data lives with config module
✅ **Package Distribution** - Gets distributed with the package
✅ **Tightly Coupled** - Lookup table is core to config functionality
✅ **Version Control** - Configuration is part of the codebase
✅ **Default Values** - Users get working config out-of-the-box

## When to Use This Directory?

Use `config/tree_asset_lookup.csv` (this directory) when you want to:

- 🔧 **Override default species** without modifying the package
- 🎨 **Customize species colors** for your project
- ➕ **Add new species** without changing source code
- 🔄 **Switch configurations** between projects

## Migration from `data/`

If you have `data/tree_asset_lookup.csv`, you have two options:

**Option 1: Move to package (recommended for distribution)**
```bash
mv data/tree_asset_lookup.csv src/growpy/config/tree_asset_lookup.csv
```

**Option 2: Keep for project override**
```bash
mkdir -p config
mv data/tree_asset_lookup.csv config/tree_asset_lookup.csv
```

The code will automatically find it in any location.

## Customization

You can customize the lookup table to:
- Add new species entries
- Change species colors
- Update growth model mappings
- Map different twigs to species

**Example**: Adding a new species
```csv
Common Name,Scientific Name,Preset,Twig,Growth Model,Branch Color,Leaf Color
Douglas fir,Pseudotsuga menziesii,Pinaceae - Douglas fir.seed.json,DouglasFirTwig,Pinaceae_Douglas_fir,#6b5447,#2d6b28
```

After editing, the changes take effect immediately (lookup table is cached per session).