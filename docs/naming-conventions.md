# GrowPy Naming Conventions and Standards

## Overview

This document defines the standardized naming conventions used across all GrowPy scripts to ensure consistency when creating files, directories, and referencing species.

## Species Name Formats

### 1. Common Name (from CSV/lookup table)
- **Format**: Human-readable with spaces
- **Examples**: `"European beech"`, `"Norway spruce"`, `"Scots pine"`
- **Usage**: User input, CSV files, lookup table
- **Source**: `tree_asset_lookup.csv` "Common Name" column

### 2. Cleaned Name (for file/directory creation)
- **Format**: Alphanumeric with underscores, lowercase or mixed case
- **Transformation**: `"".join(c for c in species if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")`
- **Examples**:
  - `"European beech"` → `"European_beech"`
  - `"Scots pine"` → `"Scots_pine"`
- **Usage**: Directory names, file prefixes
- **Used by**:
  - `generate_forest.py` (line 184-188)
  - `generate_species_library.py` (line 169-173)
  - `blender_export.py` (line 2041-2045, 2150-2154)

### 3. Twig Name (from lookup table)
- **Format**: PascalCase with "Twig" suffix
- **Examples**: `"EuropeanBeechTwig"`, `"ScotsPineTwig"`, `"PacificSilverFirTwig"`
- **Usage**: Twig directory names, twig asset references
- **Source**: `tree_asset_lookup.csv` "Twig" column
- **CRITICAL**: The suffix "Twig" is ALREADY included in the lookup table

## Directory Structure

### Tree Output Directories
```
data/output/forest/
├── European_beech/
│   └── USD/
│       ├── European_beech_tree_0001.usda
│       └── European_beech_tree_0002.usda
├── Scots_pine/
│   └── USD/
│       └── Scots_pine_tree_0001.usda
```

### Twig Asset Directories
```
data/assets/twigs/
├── EuropeanBeechTwig/        # ✓ Correct - matches lookup table
│   ├── EuropeanBeech_Apical_Twig.usda
│   ├── EuropeanBeech_Lateral_Twig.usda
│   └── textures/
├── ScotsPineTwig/             # ✓ Correct
└── PacificSilverFirTwig/      # ✓ Correct
```

## File Naming Patterns

### Tree Files
- **Pattern**: `{species_clean}_tree_{index:04d}.{ext}`
- **Examples**:
  - `European_beech_tree_0001.usda`
  - `Scots_pine_tree_0042.fbx`
- **Used in**:
  - `generate_forest.py` (line 194)
  - Individual tree exports

### Variation Files (Species Library)
- **Pattern**: `{species_clean}_f{flush:02d}_var{variant}.{ext}`
- **Examples**:
  - `European_beech_f10_var1.usda`
  - `Scots_pine_f15_var3.fbx`
- **Used in**: `generate_species_library.py` (line 195)

### Twig Files (New Standard)
- **Pattern**: `{species_clean}_{type}[_var_{x}].{ext}`
- **Examples**:
  - `europeanbeech_apical.usda`
  - `europeanbeech_lateral_var_a.usda`
- **Used in**: `convert_twigs.py` (line 119-124, 547-555)

## Common Pitfalls and Fixes

### ❌ Double Suffix Bug (FIXED)
**Problem**: Adding "Twig" suffix when it's already in the lookup table

```python
# WRONG - Creates "EuropeanBeechTwigTwig"
twig_name = get_twig_for_species(species)  # Returns "EuropeanBeechTwig"
twig_dir = assets_dir / "twigs" / f"{twig_name}Twig"  # ❌ Double suffix!

# CORRECT
twig_name = get_twig_for_species(species)  # Returns "EuropeanBeechTwig"
twig_dir = assets_dir / "twigs" / twig_name  # ✓ Use as-is
```

**Fixed in**: `settings.py:345`, `settings.py:367`

### ✓ Correct Pattern
All twig directory lookups should use `GrowPyConfig.get_twig_directory_path()` which handles the naming correctly.

## Function Reference

### Species Name Sanitization
```python
# Standard pattern used across all scripts
species_clean = (
    "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
    .strip()
    .replace(" ", "_")
)
```

### Twig Directory Lookup
```python
# Always use the config method
from growpy.config import GrowPyConfig

twig_dir = GrowPyConfig.get_twig_directory_path(species_name)
# Returns: Path("data/assets/twigs/EuropeanBeechTwig")
```

### Twig Files Lookup
```python
from growpy.io.blender_export import get_twig_usd_map_for_species

twig_map = get_twig_usd_map_for_species(species_name, config)
# Returns: {
#   'twig_long': Path('data/assets/twigs/EuropeanBeechTwig/apical.usda'),
#   'twig_short': Path('data/assets/twigs/EuropeanBeechTwig/lateral.usda'),
# }
```

## Species Name Matching

The system uses fuzzy matching in this order:
1. **Exact match** (case-insensitive)
2. **Alias match** (from lookup table "Aliases" column)
3. **Partial word match** (any word from input matches species name)
4. **Contains match** (species name contains input word)
5. **Hardcoded mappings** (common abbreviations like "beech" → "European beech")

See `settings.py:124-200` for implementation.

## Best Practices

### DO ✓
- Use `GrowPyConfig.get_twig_directory_path()` for twig lookups
- Use `GrowPyConfig.get_twig_for_species()` to get twig names
- Use `get_twig_usd_map_for_species()` for getting twig USD files
- Clean species names consistently using the standard pattern
- Include descriptive warnings when species/twigs not found

### DON'T ❌
- Add "Twig" suffix when using values from `get_twig_for_species()`
- Create custom twig path construction logic
- Use hardcoded twig directory patterns
- Mix naming conventions between scripts

## Testing Checklist

When modifying species/twig handling code:
- [ ] Verify no double suffix issues
- [ ] Check species name sanitization matches standard pattern
- [ ] Test with species that have spaces, hyphens, special characters
- [ ] Verify twig lookup works for species with configured twigs
- [ ] Verify appropriate warnings for species without twigs
- [ ] Test with species names that need alias/fuzzy matching

## Scripts Audited

All scripts verified for naming consistency (2025-01-09):
- ✓ `cli/generate_forest.py`
- ✓ `cli/generate_species_library.py`
- ✓ `cli/convert_twigs.py`
- ✓ `cli/prepare_assets.py`
- ✓ `config/settings.py`
- ✓ `io/blender_export.py`
- ✓ `io/unreal_nanite_assembly.py`
- ✓ `io/twig_placement.py`
- ✓ `io/unreal_metadata.py`
