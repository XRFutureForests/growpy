# PVE Preset Implementation Summary

## Changes Implemented

### New Modules Created

1. **`pve_growth_defaults.py`**
   - Contains Hazel reference growth parameters as defaults
   - Provides `get_default_growth_params()` and `merge_growth_params()`
   - Ensures `phyllotaxyLeaf` (REQUIRED by Unreal) is always populated

2. **`pve_hierarchy_builder.py`**
   - Builds parent/child arrays from Grove skeleton
   - Extracts branch hierarchy from `poly_line.parent_index`
   - Calculates generation numbers

3. **`pve_foliage_extractor.py`**
   - Extracts twig instances from `grove.build_models(build_twigs=True)`
   - Converts Grove coordinates (Z-up meters) to PVE (Y-up centimeters)
   - Groups twigs by branch and generates all instancer_* arrays
   - Maps Grove twig types to Unreal asset names

### Updated Modules

**`pve_grove_mapper.py`**

- Added new parameters to `generate_pve_from_grove()`:
  - `use_default_growth_params`: Enable Hazel defaults (default: True)
  - `twig_density`: Control foliage density (default: 1.0)
  - `custom_growth_params`: Manual parameter overrides
- Enabled twig generation in `build_models()` with `build_twigs=True`
- Integrated foliage extraction into primitives mapping
- Added hierarchy arrays (parents/children) to primitives
- Populated growth parameter curves with Hazel defaults

## What's Now Populated

### ✅ Foliage Data (Previously Empty)

```json
"instancer_name": { "value": [["SM_Oak_Twig_01"], ["SM_Oak_Twig_02"]] }
"instancer_pivot": { "value": [[x1, z1, y1, x2, z2, y2], [...]] }
"instancer_UP": { "value": [[ux1, uz1, uy1], [...]] }
"instancer_N": { "value": [[nx1, nz1, ny1], [...]] }
"instancer_scale": { "value": [[s1, s2], [...]] }
"instancer_LFR": { "value": [[lfr1, lfr2], [...]] }
```

### ✅ Branch Hierarchy (Previously Empty)

```json
"parents": { "value": [[-1], [0], [0], [1], [1]] }
"children": { "value": [[1,2], [3,4], [], [], []] }
```

### ✅ Growth Parameters (Previously Empty)

```json
"phyllotaxyLeaf": { "value": [0.0, 198.39, 51.63, ...] }  // REQUIRED!
"phototropism": { "value": [0.2465, 0.6691, ...] }
"phyllotaxy": { "value": [0.0, 202.7, 50.21, ...] }
// ... all other curves from Hazel
```

## Testing

Run the test script:

```bash
conda activate the-grove
python src/growpy/tests/test_pve_generation.py
```

This will generate a test PVE preset and verify:

- Twig instances are created
- Branch hierarchy is correct
- Growth parameters are populated

## Using in Unreal Engine

### Step 1: Import Tree Assets

1. Export your tree using the forest generation script:

   ```bash
   python src/growpy/cli/generate_forest.py your_forest.csv
   ```

2. This generates in `data/output/forest/species_name/`:
   - `species_tree_0000_PVEPreset.json` ← The PVE JSON
   - `species_twig_apical_static.usda` ← Twig meshes
   - `species_twig_lateral_static.usda`
   - Trunk mesh USD files

3. Import USD files into Unreal:
   - Import twigs as Static Meshes
   - Import trunk as Static or Skeletal Mesh
   - Name them to match the JSON (e.g., `SM_European_Oak_Twig_Apical`)

### Step 2: Create PVE Data Asset

1. In Unreal Content Browser, right-click → **Miscellaneous → Data Asset**
2. Select **ProceduralVegetationPreset** class
3. Name it `DA_Oak_PVE` or similar

### Step 3: Configure Data Asset

1. Open the Data Asset
2. Set **Json Directory Path** to folder containing your JSON files
3. Set **Trunk Material Name** (e.g., `M_Oak_Bark`)
4. Optionally set **Foliage Folder** and **Materials Folder** paths
5. Click **Update Data Asset** button

The plugin will:

- Load all JSON files in the directory
- Parse foliage mesh names from `instancer_name`
- Create references to your imported Static Meshes
- Build internal data structures for PCG

### Step 4: Use in PCG or Blueprint

**In PCG Graph:**

1. Add **PVE Preset Loader** node
2. Connect your `DA_Oak_PVE` asset
3. Use output for tree placement/spawning

**In Blueprint:**

- Use the Data Asset as a reference
- Access variation data through the asset

## Important Notes

### Asset Naming

Your twig Static Meshes in Unreal MUST match the names in JSON:

- JSON: `"SM_European_Oak_Twig_Apical"`
- Unreal: Asset named exactly `SM_European_Oak_Twig_Apical`

The naming convention is:

```
SM_{Species}_{Twig}_{Variant}
```

### Coordinate System

Already handled automatically:

- Grove: Z-up, meters
- PVE/Unreal: Y-up, centimeters
- Conversion: `[x*100, z*100, y*100]`

### Custom Growth Parameters

Override specific parameters:

```python
custom_params = {
    "phyllotaxyLeaf": {
        "value": [0.0, 137.5, 45.0, ...]  # Custom values
    }
}

generate_pve_from_grove(
    grove=grove,
    output_path=path,
    species_name="oak",
    custom_growth_params=custom_params
)
```

### Twig Density Control

Adjust foliage density:

```python
generate_pve_from_grove(
    grove=grove,
    output_path=path,
    species_name="oak",
    twig_density=0.5  # Half density
)
```

## Next Steps

1. **Test with Unreal:**
   - Generate PVE preset for a species
   - Import twig meshes
   - Create Data Asset
   - Load in PCG and verify foliage appears

2. **Compare with Hazel:**
   - Load both Hazel and your preset in Unreal
   - Compare behavior and adjust parameters

3. **Optimize:**
   - Tune twig density for performance
   - Adjust growth parameters for desired aesthetics

4. **Document:**
   - Note any parameter adjustments needed
   - Document species-specific settings
