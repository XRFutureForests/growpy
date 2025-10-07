# Bark Texture Lookup - Update Summary

## Changes Made

### Added Bark Texture Column to Lookup Table

The species lookup table (`src/growpy/config/tree_asset_lookup.csv`) now includes a **Bark Texture** column that explicitly maps each species to its appropriate bark texture file.

### Column Structure

```csv
Common Name,Scientific Name,Preset,Twig,Growth Model,Branch Color,Leaf Color,Aliases,Bark Texture
European beech,Fagus sylvatica,...,Beech60.jpg
European oak,Quercus robur,...,NorthernRedOak60.jpg
Scots pine,Pinus sylvestris,...,Fir70.jpg
```

### Texture Mappings

All 56 species in the lookup table have been mapped to appropriate bark textures:

- **Deciduous trees**: Species-specific textures (Beech, Oak, Ash, Maple, etc.)
- **Conifers**: Appropriate conifer textures (Fir70.jpg for most pines and firs)
- **Special cases**: Unique textures for distinctive species (Birch, Willow, Poplar, etc.)

### Code Updates

#### 1. Enhanced `_find_bark_texture()` Function

The texture lookup function in `src/growpy/io/blender_export.py` now:

- **First** checks the Bark Texture column in the lookup table (fastest, most accurate)
- **Then** falls back to pattern matching if lookup table doesn't have the texture
- Handles both normal naming conventions (e.g., `Beech60Normal.jpg` and `Birch70_normal.jpg`)

#### 2. New GrowPyConfig Methods

Added three new helper methods to `src/growpy/config/settings.py`:

**`get_bark_texture(common_name: str)`**

- Returns the bark texture filename for a species
- Example: `get_bark_texture("Beech")` → `"Beech60.jpg"`

**`get_bark_texture_path(common_name: str)`**

- Returns the full Path object to the texture file
- Validates that the file exists
- Example: `get_bark_texture_path("Oak")` → `Path("data/assets/textures/NorthernRedOak60.jpg")`

**`get_species_data(common_name: str)`**

- Enhanced to include Bark Texture in returned dictionary

## Benefits

### 1. Explicit Mapping

No more guessing or pattern matching - each species has a defined texture

### 2. Performance

Direct lookup is faster than glob pattern matching

### 3. Consistency

Same species always uses the same texture across all exports

### 4. Maintainability

Easy to update or customize textures - just edit the CSV

### 5. Fallback Support

Original pattern matching still works as a fallback for edge cases

## Example Usage

### In Python Code

```python
from growpy.config import GrowPyConfig

# Get texture filename
texture = GrowPyConfig.get_bark_texture("European beech")
# Returns: "Beech60.jpg"

# Get full path
texture_path = GrowPyConfig.get_bark_texture_path("Oak")
# Returns: Path("data/assets/textures/NorthernRedOak60.jpg")

# Get all species data including texture
species_data = GrowPyConfig.get_species_data("Beech")
# Returns: {'Common Name': 'European beech', ..., 'Bark Texture': 'Beech60.jpg'}
```

### During Export

The material assignment in `_add_material_with_textures()` automatically uses the Bark Texture column:

1. Looks up species in lookup table
2. Gets Bark Texture value
3. Loads the specified texture file
4. Creates material with diffuse and normal maps

## Texture File Naming Conventions

The system handles both standard normal map naming conventions:

- **Standard**: `Beech60.jpg` + `Beech60Normal.jpg`
- **Alternative**: `Birch70.jpg` + `Birch70_normal.jpg`

Both formats are automatically detected and loaded.

## Customization

### Changing a Species Texture

Edit the CSV file:

```csv
Common Name,...,Bark Texture
European beech,...,AntarcticBeech36.jpg  # Changed from Beech60.jpg
```

### Adding Custom Textures

1. Add your texture files to `data/assets/textures/`:
   - `MyCustomBark.jpg` (diffuse)
   - `MyCustomBarkNormal.jpg` (normal map)

2. Update the lookup table:

   ```csv
   Common Name,...,Bark Texture
   European beech,...,MyCustomBark.jpg
   ```

### Texture Quality Variants

You can create quality tiers by changing textures:

```csv
# High quality
European beech,...,Beech60.jpg

# Medium quality
European beech,...,Beech30.jpg

# Low quality
European beech,...,Beech15.jpg
```

## Available Textures

The `data/assets/textures/` directory contains:

- **Deciduous bark**: Beech, Oak, Ash, Maple, Birch, Willow, Poplar, etc.
- **Conifer bark**: Fir, Pine, Cypress
- **Special textures**: Magnolia, Ginkgo, Eucalyptus (Gum), Plane Tree
- **Dead/burnt variants**: DeadTree, Burnt, HalfBurnt textures

Each texture includes a matching normal map for realistic bark detail.

## Testing

Run your forest generation to verify textures are correctly assigned:

```powershell
conda activate the-grove
python .\src\growpy\cli\generate_forest.py data\input\mini_tree_inventory_32632.csv
```

Expected behavior:

- No "No materials assigned" warnings
- Textures load from Bark Texture column
- Correct species-texture mapping
- Both diffuse and normal maps applied

## Migration Notes

### From Previous System

- Old behavior (pattern matching) still works as fallback
- No breaking changes to existing code
- New explicit mappings take priority over pattern matching
- All existing species already have texture mappings

### Performance Impact

- Slightly faster texture lookup (direct CSV column vs glob pattern matching)
- Reduced file system operations
- More predictable behavior

## Future Enhancements

Potential improvements:

- Season-specific textures (summer/fall/winter bark variations)
- Age-specific textures (young vs mature bark)
- Quality preset support (high/medium/low resolution variants)
- Regional texture variations
- Texture atlas support for Nanite optimization
