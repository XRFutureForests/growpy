# GrowPy Quick Reference - New Structure

## Import Cheat Sheet

### Config
```python
# Core config
from growpy.config import GrowPyConfig, get_config

# Species lookup (with LRU caching!)
from growpy.config import find_species_match, get_available_species

# Paths
from growpy.config import get_preset_path, get_growth_model_path

# Quality
from growpy.config import get_all_lod_configs
```

### Core
```python
# Forest & Grove
from growpy.core import create_forest, simulate_forest_growth
from growpy.core import create_grove, add_tree_to_grove

# Tree functions
from growpy.core import (
    calculate_growth_cycles_from_height,
    build_grove_with_all_attributes,
    build_skeletons,
)
```

### Export
```python
# Main exports
from growpy.io.export import (
    export_tree_as_usd,
    export_grove_tree_as_usda_native,
    batch_export_trees_for_unreal,
    get_quality_preset,
)

# Nanite
from growpy.io.nanite import (
    add_nanite_attributes_to_usd,
    validate_mesh_for_nanite,
)

# Twigs
from growpy.io.twig import (
    bundle_twigs_for_species,
    export_twigs_from_blend,
    process_twig_file,
)
```

### Utilities
```python
# String utils
from growpy.utils import sanitize_species_name, sanitize_filename

# Path utils
from growpy.utils import ensure_dir, ensure_parent_dir
```

## Configuration

### Using config.ini
```python
from pathlib import Path
from growpy.config import GrowPyConfig

# Load from file
config = GrowPyConfig.from_config_file(Path("config.ini"))

# Or use defaults
config = GrowPyConfig()
```

### config.ini Template
```ini
[simulation]
random_seed = 42

[output]
output_dir = output

[build]
lod_levels = all
```

## Common Patterns

### Forest Generation
```python
from growpy import create_forest, simulate_forest_growth
import pandas as pd

# Load forest data
df = pd.read_csv("forest.csv")  # x, y, species, height

# Create forest
forest = create_forest(df)

# Simulate growth
simulate_forest_growth(forest, cycles=10)
```

### Tree Export
```python
from growpy.io.export import export_tree_as_usd, get_quality_preset

# Get quality settings
quality = get_quality_preset("high")

# Export tree
export_tree_as_usd(
    grove,
    output_path=Path("tree.usda"),
    species_name="European Beech",
    **quality
)
```

### Species Lookup (Cached!)
```python
from growpy.config import find_species_match

# First call: ~10ms
species = find_species_match("beech")  # "European beech"

# Second call: <0.1ms (cached!)
species = find_species_match("beech")  # "European beech"
```

## Module Organization

```
growpy/
├── core/          # Forest/Grove/Tree simulation
├── config/        # Configuration & species lookup
├── io/            # Import/Export
│   ├── export/    # USD/FBX export
│   ├── nanite/    # Nanite support
│   └── twig/      # Twig processing
└── utils/         # Shared utilities
```

## Backward Compatibility

All old imports still work:
```python
# Old way (still works)
from growpy.io.blender_export import export_tree_as_usd

# New way (recommended)
from growpy.io.export import export_tree_as_usd
```
