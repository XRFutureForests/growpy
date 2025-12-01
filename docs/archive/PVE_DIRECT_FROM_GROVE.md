# PVE Preset Generation Direct from Grove API

This system generates PVE (Procedural Vegetation Editor) preset JSONs directly from Grove simulations **without requiring Houdini**.

## Overview

PVE preset JSONs are automatically generated during forest export alongside skeletal/static meshes and wind JSONs. The system maps Grove's botanical simulation data to Quixel Megaplants PVE format by:

1. Using a built-in PVE schema (no reference file needed)
2. Extracting skeleton and geometry data from Grove API
3. Mapping Grove data to PVE structure where possible
4. Using the actual growth cycles from the forest simulation

## Integration with Forest Workflow

PVE JSON generation is **automatically integrated** into the forest generation script:

```bash
conda run -n the-grove python src/growpy/cli/generate_forest.py forest.csv --quality high
```

This generates:

- Skeletal mesh assemblies (`.usda`)
- Static mesh assemblies (`.usda`)
- Wind JSONs (`_DynamicWind.json`) - for skeletal meshes
- **PVE preset JSONs (`_PVEPreset.json`)** - for all trees

## Key Components

### 1. PVE Schema (`src/growpy/io/pve_schema.py`)

Built-in PVE structure definition extracted from Quixel Megaplants format:

- **Schema Definition**: `get_pve_schema()` - lightweight schema with structure and types only
- **Template Creation**: `create_empty_pve_preset()` - generates empty preset with proper structure

### 2. PVE Grove Mapper (`src/growpy/io/pve_grove_mapper.py`)

Core mapping engine that converts Grove data to PVE format:

- **Data Mapping**: `map_grove_to_pve()` - fills schema with Grove simulation data
- **Point Mapping**: Maps Grove skeleton points (branch joints) to PVE point cloud
- **Primitive Mapping**: Maps Grove poly_lines (branch connectivity) to PVE primitives
- **Export Function**: `generate_pve_from_grove()` - complete generation workflow

## Data Mapping

### Grove → PVE Mapping Table

| PVE Attribute | Grove Source | Status |
|--------------|--------------|--------|
| **Global Attributes** | | |
| `cycle` | `properties.simulation_steps` | ✓ Mapped |
| `cycleTime` | `properties.cycle_time` | ✓ Mapped |
| `gravitationalForce` | `properties.gravity` | ✓ Mapped |
| Other growth params | Template defaults | ⚠️ Partial |
| **Point Attributes** | | |
| `positions` | `skeleton.points` | ✓ Mapped |
| `pscale` | `skeleton.point_attribute_radius` | ✓ Mapped |
| `generation` | Calculated from poly_lines | ✓ Computed |
| `lengthFromRoot` | Calculated from positions | ✓ Computed |
| `branchGradient` | Calculated per branch | ✓ Computed |
| `P` | Copy of positions (flattened) | ✓ Mapped |
| Other attributes | Template defaults | ⚠️ Empty |
| **Primitive Attributes** | | |
| `points` | `skeleton.poly_lines` | ✓ Mapped |
| `branchNumber` | Sequential index | ✓ Computed |
| `branchGeneration` | Calculated from hierarchy | ✓ Computed |
| `branchParentNumber` | Calculated from connectivity | ✓ Computed |
| `plantNumber` | All 0 (single tree) | ✓ Mapped |
| Other attributes | Template defaults | ⚠️ Empty |

### What Gets Mapped

**Fully Mapped from Grove:**

- Tree skeleton structure (branch hierarchy)
- Point positions (branch joint locations)
- Branch connectivity (poly_lines)
- Branch radius/thickness
- Basic simulation parameters

**Computed from Grove Data:**

- Generation (hierarchy depth)
- Length from root
- Branch gradients
- Parent-child relationships

**Template Defaults (Not Mapped):**

- Houdini-specific LOD attributes
- Bud development states
- UV coordinates
- Light detection data
- Instancer information

## Output Files

For each tree in the forest, the following files are generated:

**Directory structure:**

```
output/
└── european_beech/
    ├── european_beech_tree_0000_skeletal_nanite_assembly.usda
    ├── european_beech_tree_0000_static_nanite_assembly.usda
    ├── european_beech_tree_0000_DynamicWind.json
    ├── european_beech_tree_0000_PVEPreset.json
    ├── european_beech_tree_0001_skeletal_nanite_assembly.usda
    └── ...
```

**Naming pattern:**

- `{species}_{tree_number}_{skeletal|static}_nanite_assembly.usda` - Tree mesh assemblies
- `{species}_tree_{number}_DynamicWind.json` - Wind animation data (skeletal only)
- `{species}_tree_{number}_PVEPreset.json` - PVE preset data (all trees)

## Usage Example

```bash
# Generate forest with all export formats
conda run -n the-grove python src/growpy/cli/generate_forest.py \
  data/input/forest.csv \
  --quality high

# Output includes PVE JSONs automatically
# Check output/species_name/ for *_PVEPreset.json files
```

## Output Structure

Generated JSON follows Quixel Megaplants format:

```json
{
  "globalAttributes": {
    "cycle": {"isArray": false, "size": 1, "type": "int", "value": 30},
    "cycleTime": {"isArray": false, "size": 1, "type": "float", "value": 1.25},
    ...
  },
  "points": {
    "attributes": {
      "generation": {"isArray": false, "size": 1, "type": "int", "value": [0, 0, 1, 1, ...]},
      "pscale": {"isArray": false, "size": 1, "type": "float", "value": [0.004, 0.003, ...]},
      ...
    },
    "positions": [[0.0, 0.0, 0.0], [0.99, 1.99, 1.0], ...]
  },
  "primitives": {
    "attributes": {
      "branchNumber": {"isArray": false, "size": 1, "type": "int", "value": [0, 1, 2, ...]},
      "branchGeneration": {"isArray": false, "size": 1, "type": "int", "value": [0, 1, 1, ...]},
      ...
    },
    "points": [[0, 1, 2, 3, ...], [1, 10, 11, 12], ...]
  }
}
```

## Validation

Check generated JSON:

```bash
python -c "
import json
data = json.load(open('output.json'))
print(f'Points: {len(data[\"points\"][\"positions\"])}')
print(f'Branches: {len(data[\"primitives\"][\"points\"])}')
print(f'Has globalAttributes: {\"globalAttributes\" in data}')
"
```

## Advantages Over Houdini Workflow

1. **No Houdini Required**: Pure Python using Grove API
2. **Faster Iteration**: Direct data extraction
3. **Scriptable**: Easy integration in pipelines
4. **Consistent Structure**: Template-based ensures format compliance
5. **Minimal Dependencies**: Only requires Grove 2.2 + Python

## Limitations

1. **Template-Dependent**: Requires existing PVE JSON as reference
2. **Partial Mapping**: Many PVE attributes are Houdini-specific and remain empty
3. **No Twig Instances**: Instance placement not yet implemented
4. **No UV Data**: UV coordinates not generated from Grove
5. **Basic LOD**: Level-of-detail attributes use template defaults

## Future Improvements

- [ ] Map more Grove properties to PVE growth parameters
- [ ] Implement twig instance placement from Grove twig data
- [ ] Generate UV coordinates from Grove mesh
- [ ] Add LOD calculations based on branch hierarchy
- [ ] Support root system export
- [ ] Add wind JSON generation integration
- [ ] Validate against Unreal Engine PVE import requirements

## Reference Files

- **Template Source**: `data/megaplant/json/Broadleaf_Hazel_01.json` (Quixel Megaplants reference)
- **Mapper**: `src/growpy/io/pve_grove_mapper.py`
- **CLI**: `src/growpy/cli/generate_pve_from_grove.py`
- **Grove Demo**: `src/the-grove-output-complete.py` (shows all available Grove data)

## Technical Notes

### Grove Skeleton Structure

Grove's skeleton system provides:

- `skeleton.points`: List of (x, y, z) tuples for branch joints
- `skeleton.poly_lines`: List of lists defining branch connectivity
- `skeleton.point_attribute_age`: Age per point
- `skeleton.point_attribute_mass`: Mass per point
- `skeleton.point_attribute_radius`: Radius per point

### PVE Structure Requirements

PVE expects:

- **globalAttributes**: Growth parameters (curves and values)
- **points.positions**: 3D coordinates of all points
- **points.attributes**: Per-point botanical data
- **primitives.points**: Arrays of point indices defining curves
- **primitives.attributes**: Per-branch metadata

### Coordinate Systems

- Grove uses Z-up by default
- PVE/Unreal may expect Y-up
- Coordinate conversion not yet implemented (TODO)

## See Also

- [Wind JSON Implementation](WIND_JSON_IMPLEMENTATION.md)
- [Nanite Clean Export](NANITE_CLEAN_EXPORT.md)
- [Grove API Documentation](the_grove/the_grove_core.md)
