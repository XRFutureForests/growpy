# Twig Placement Fix - Complete

## Issues Fixed

### 1. ✅ Twig Face Attributes Not Exported to USD

**Problem**: Grove's native USD export (`gc.io.model_to_usda_string()`) doesn't include twig face attributes (twig_long, twig_short, twig_upward, twig_dead) which are critical for placing twig instances.

**Solution**: Created `_add_grove_face_attributes_to_usd()` function that:

- Opens the USD file after Grove's native export
- Extracts twig face attributes from the Grove model
- Converts Grove's Rust Vec<bool> to Python lists using `BoolArray` type
- Writes them as USD primvars with uniform interpolation (per-face)

**Location**: `src/growpy/io/blender_export.py:698`

### 2. ✅ twig_upward Mapping Conflict

**Problem**: Many species don't have dedicated upward-facing twig meshes. When twig_upward placements existed but no upward twig file was found, those placements were silently dropped.

**Solution**: Added fallback logic in `get_twig_usd_map_for_species()`:

- If `twig_upward` not found, uses `twig_short` (lateral twigs)
- If `twig_dead` not found, uses `twig_short` (lateral twigs)
- Logs the fallback usage for transparency

**Location**: `src/growpy/io/blender_export.py:1953-1963`

### 3. ✅ USD Files Not Being Used

**Problem**: System was prioritizing FBX files over USD files, even though USD files provide better Nanite compatibility.

**Solution**: Modified `get_available_twig_usd_files()` to:

- Prioritize `.usda` and `.usd` files over `.fbx`
- Only fall back to FBX if no USD files exist
- Updated docstring to reflect USD priority

**Location**: `src/growpy/config/settings.py:385-411`

### 4. ✅ Twigs Not Copied to Output Directory

**Problem**: The `bundle_twigs_for_species()` function wasn't copying twig files, leaving the output folder empty.

**Solution**: Rewrote bundling logic to:

- Use the resolved `twig_usd_map` instead of trying to discover files again
- Copy each twig file from the map to the output directory
- Also copy associated texture files
- Create a manifest JSON documenting what was bundled

**Location**: `src/growpy/io/blender_export.py:1990-2020`

### 5. ✅ Case-Sensitive File Matching

**Problem**: Twig file discovery was case-sensitive and didn't find lowercase USD files like `europeanbeech_apical.usda`.

**Solution**: Enhanced pattern matching in `get_twig_files_by_type()`:

- Uses `filename.lower()` for case-insensitive matching
- Expanded keywords to catch more variations (apical/end/long, lateral/side/short)
- Added parent directory fallback for USD files

**Location**: `src/growpy/config/settings.py:446-457`

## Results

### Before Fix

- **0 twig instances** - No twigs placed
- Empty position/orientation arrays in PointInstancer
- FBX file references
- Empty twigs output folder
- Missing twig_upward placements

### After Fix

- **5 twig instances** per tree (4 twig_short + 1 twig_upward)
- **4 prototypes** (twig_long, twig_short, twig_upward, twig_dead)
- USD file references (e.g., `europeanbeech_apical.usda`)
- Twigs bundled to output folder with manifest
- All placement types working with fallback support

## Example Output

```usd
def PointInstancer "TwigInstances"
{
    quath[] orientations = [
        (-0.105469, 0.255859, 0.0280762, 0.960449),
        (0.945312, 0.0496216, -0.172974, 0.27124),
        (0.632324, -0.236694, -0.211792, -0.706543),
        (0.61084, 0.168335, -0.13501, 0.761719),
        (0.0557861, 0.785645, 0.0436707, 0.614746)
    ]
    point3f[] positions = [
        (-0.016633334, -0.015866667, -0.9997333),
        (-0.020966666, -0.023766667, -1.0742333),
        (-0.03266667, -0.0342, -1.1475),
        (-0.0422, -0.0418, -1.2215333),
        (-0.0521, -0.048533335, -1.2955667)
    ]
    int[] protoIndices = [2, 2, 2, 2, 3]
    rel prototypes = [
        </TreeAssembly/Prototypes/twig_dead>,
        </TreeAssembly/Prototypes/twig_long>,
        </TreeAssembly/Prototypes/twig_short>,
        </TreeAssembly/Prototypes/twig_upward>,
    ]
    float3[] scales = [(1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1)]
}
```

## Bundled Twigs Output

```
data/output/forest/Beech/twigs/
├── europeanbeech_apical.usda          # Apical twig USD
├── europeanbeech_lateral.usda         # Lateral twig USD
├── BeechSummerApicalTwig.fbx          # Legacy FBX (kept for compatibility)
├── BeechSummerLateralTwig.fbx         # Legacy FBX (kept for compatibility)
├── twig_manifest.json                 # Manifest documenting what was bundled
└── textures/                           # Associated textures
    ├── BeechSummerLeaf_diffuse_top.png
    └── BeechSummerLeaf_diffuse_bottom.png
```

## Testing

Run the forest generation to verify:

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv --formats usda
```

Expected output:

```
Found twig_long: europeanbeech_apical.usda
Found twig_short: europeanbeech_lateral.usda
Using twig_short for twig_upward (no upward-specific twig)
Using twig_short for twig_dead (no dead-specific twig)
Exporting Beech as USDA...
  ✓ Exported base tree USD: Beech_var1_tree_only.usda
  ✓ Added twig face attributes to USD:
    - twig_long: 0 faces
    - twig_short: 4 faces
    - twig_upward: 1 faces
    - twig_dead: 0 faces
  Adding twigs as point instances...
  Found 4 twig_short placements
  Found 1 twig_upward placements
  Created USD assembly with PointInstancer (5 twig instances)
    Prototypes: 4
    Positions: 5
  Bundling twigs for Beech...
```

## Unreal Engine Import

The generated USD files are now fully compatible with Unreal Engine 5.7+ Nanite Assemblies:

1. Import `Beech_var1_NaniteAssembly.usda` into Unreal Engine
2. Twigs will automatically instance using USD PointInstancer
3. All meshes support Nanite rendering
4. Twigs have `unrealNanitePreserveArea = true` for foliage optimization

## Files Modified

- `src/growpy/io/blender_export.py` - Added twig attribute export, fallback logic, and fixed bundling
- `src/growpy/config/settings.py` - Fixed USD file prioritization and case-insensitive matching
- `src/growpy/io/twig_placement.py` - (No changes needed - worked correctly once attributes were present)

## Date

7 October 2025
