# Species Lookup System Guide

This guide explains how the species lookup system works in GrowPy and how to prepare input files for optimal matching.

## Overview

The species lookup system uses fuzzy matching to map input species names to the standardized names in the lookup table. This allows flexibility in how users specify species names while maintaining consistency in asset resolution.

## Lookup Table Structure

The lookup table (`src/growpy/config/tree_asset_lookup.csv`) contains the following columns:

- **Common Name**: Standard species name used throughout the system
- **Scientific Name**: Botanical Latin name
- **Preset**: Grove 2.2 preset file name
- **Twig**: Associated twig asset name
- **Growth Model**: Growth model directory name
- **Branch Color**: Hex color for branch/bark
- **Leaf Color**: Hex color for foliage
- **Aliases**: Comma-separated alternative names (NEW)

## Species Name Matching Strategy

The lookup system tries multiple matching strategies in order:

### 1. Exact Match (Priority 1)

Case-insensitive exact match with the Common Name:

- Input: `european beech` → Matches: `European beech` ✓

### 2. Alias Match (Priority 2) - NEW

Checks the Aliases column for alternative names:

- Input: `Beech` → Matches: `European beech` (via alias "Beech") ✓
- Input: `Oak` → Matches: `European oak` (via alias "Oak") ✓
- Input: `Common oak` → Matches: `European oak` (via alias) ✓

### 3. Partial Word Match (Priority 3)

Matches if any word from input appears in the species name:

- Input: `silver` → Matches: `Silver birch` ✓
- Input: `red oak` → Matches: `Red oak` ✓

### 4. Contains Match (Priority 4)

Matches if species name contains any word from input:

- Input: `birch` → Matches: `Silver birch` ✓

### 5. Hardcoded Mappings (Priority 5 - Fallback)

Built-in fallback mappings for common names:

- `beech` → `European beech`
- `oak` → `European oak`
- `pine` → `Scots pine`
- `spruce` → `Norway spruce`
- etc.

## Input File Recommendations

### Option 1: Simple Names (Recommended for General Use)

Use short, common names that map via aliases:

```csv
fid,species,x,y,dbh,height,z
1,Beech,416722.57,5346717.97,0.47,8.83,521.55
2,Oak,416723.35,5346714.34,0.17,8.14,521.62
3,Pine,416722.65,5346713.43,0.39,6.18,521.72
```

**Advantages:**

- Easy to read and type
- Consistent with common forestry data
- Works with the Aliases system

### Option 2: Full Common Names (Most Explicit)

Use the exact names from the lookup table:

```csv
fid,species,x,y,dbh,height,z
1,European beech,416722.57,5346717.97,0.47,8.83,521.55
2,European oak,416723.35,5346714.34,0.17,8.14,521.62
3,Scots pine,416722.65,5346713.43,0.39,6.18,521.72
```

**Advantages:**

- No ambiguity
- Exact matches (fastest lookup)
- Clear species specification

### Option 3: Scientific Names (Most Precise)

Use Latin botanical names:

```csv
fid,species,x,y,dbh,height,z
1,Fagus sylvatica,416722.57,5346717.97,0.47,8.83,521.55
2,Quercus robur,416723.35,5346714.34,0.17,8.14,521.62
3,Pinus sylvestris,416722.65,5346713.43,0.39,6.18,521.72
```

**Note:** Currently, scientific names don't match directly. You would need to add them to the Aliases column or use common names.

## Adding Custom Aliases

To add support for new alternative names, edit the lookup table:

```csv
Common Name,Scientific Name,...,Aliases
European beech,Fagus sylvatica,...,"Beech,Common beech,Rotbuche"
```

Multiple aliases are separated by commas. The system will match any of these alternatives.

## Common Species Aliases

The system currently supports these short names:

| Input Name | Maps To |
|------------|---------|
| Beech | European beech |
| Oak | European oak |
| Pine | Scots pine |
| Spruce | Norway spruce |
| Fir | Silver fir |
| Birch | Silver birch / Downy birch |
| Maple | Field maple / Sycamore maple |
| Ash | Common ash |
| Willow | Willow |
| Poplar | Grey poplar |

## Handling Ambiguous Names

Some common names are ambiguous (e.g., "Oak" could be European oak, Red oak, or White oak). The system prioritizes:

1. **First alias match** in the lookup table order
2. **Partial matches** in order of appearance

For precise control:

- Use full common names ("European oak", "Red oak", "White oak")
- Or add specific aliases for regional preferences

## Best Practices

1. **Keep it simple**: Use common short names like "Beech", "Oak", "Pine"
2. **Be consistent**: Use the same naming convention throughout your dataset
3. **Document your choices**: Note which convention you're using in your data README
4. **Add regional aliases**: Edit the lookup table to add region-specific names
5. **Test first**: Run a small sample to verify all species names resolve correctly

## Troubleshooting

### Species Not Found Error

If you see:

```
Species 'X' not found in lookup table
```

Solutions:

1. Check spelling - try a simpler name (e.g., "beech" instead of "beach")
2. Add an alias to the lookup table
3. Use the full common name from the lookup table
4. Check available species: run `python -c "from growpy import get_config; print(get_config().get_available_species())"`

### Wrong Species Matched

If fuzzy matching picks the wrong species:

1. Use the full common name for precise matching
2. Add a more specific alias to differentiate similar species
3. Avoid single-word inputs for species with multiple varieties

## Example: Converting Legacy Data

If you have legacy data with non-standard names:

**Before:**

```csv
species
Common Beech
European Red Oak
Norway Pine
```

**Option A - Quick Fix (add aliases):**
Edit `tree_asset_lookup.csv`:

```csv
European beech,...,"Beech,Common beech,Common Beech"
Red oak,...,"Northern red oak,European Red Oak"
Norway spruce,...,"Spruce,Norway Pine"
```

**Option B - Data Standardization (preferred):**
Convert your input data to use standard names:

```csv
species
European beech
Red oak
Norway spruce
```

## Performance Considerations

- **Exact matches** and **alias matches** are fastest
- **Partial matches** require iteration over all species
- For large datasets, consider preprocessing to standardize names

## Future Enhancements

Potential improvements to the lookup system:

- Add Scientific Name to aliases automatically
- Levenshtein distance for typo tolerance
- Regional preference configuration
- Multi-language alias support
