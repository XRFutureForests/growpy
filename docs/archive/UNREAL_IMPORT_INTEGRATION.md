# Unreal Import Integration - Implementation Summary

**Date:** 2025-11-04  
**Status:** Complete and Integrated

## What Was Implemented

Integrated Unreal Engine import directly into the `generate_forest.py` script as the final pipeline step.

## Changes Made

### 1. Modified `generate_forest.py`

Added Unreal import functionality as an optional step:

**New Imports:**

- `asyncio` - For async Unreal communication

**New Function:**

- `import_forest_to_unreal()` - Async function that:
  - Connects to running Unreal Engine via Remote Execution
  - Searches for `*nanite_assembly.usda` files in output directory
  - Generates and executes import script in Unreal
  - Imports to Content Browser (not level)
  - Reports success/failure with detailed feedback

**New Arguments:**

- `--import-to-unreal` - Enable automatic import to Unreal
- `--unreal-project-path` - Destination path (default: `/Game/GrowPy/Trees`)
- `--unreal-host` - Unreal host address (default: `127.0.0.1`)
- `--unreal-port` - Command port (default: `6776`)

**Updated Documentation:**

- Module docstring with import examples
- Argparse epilog with Unreal integration examples

### 2. Created Documentation

**`docs/growpy/PIPELINE_WORKFLOW.md`** - Complete pipeline guide:

- Step-by-step workflow
- Per-script options and examples
- Unreal Engine setup instructions
- Import behavior details
- Troubleshooting section
- Quick commands for common scenarios

## Usage

### Complete Pipeline (Recommended)

```bash
# Steps 1-3: Setup (run once)
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/create_growth_models.py

# Step 4-5: Generate and import in one command
python src/growpy/cli/generate_forest.py \
    --quality high \
    --growth-cycle-limit 15 \
    --import-to-unreal
```

### Custom Destination

```bash
python src/growpy/cli/generate_forest.py \
    --quality high \
    --import-to-unreal \
    --unreal-project-path "/Game/MyProject/Trees"
```

### Without Unreal Import

```bash
# Default behavior - just export USD files
python src/growpy/cli/generate_forest.py --quality high
```

## Pipeline Flow

```
1. prepare_assets.py      → Copy species data from Grove 2.2
2. convert_twigs.py       → Export .blend to USD with skeletons
3. create_growth_models.py → Generate height prediction models
4. generate_forest.py     → Simulate forest & export Nanite Assembly USD
   └─> [--import-to-unreal] → Import to Unreal Content Browser ✨ NEW
```

## Import Behavior

When `--import-to-unreal` is used:

1. **After forest export completes**, automatically:
   - Connects to running Unreal Engine
   - Searches for `*nanite_assembly.usda` files
   - Imports each file to Content Browser

2. **Import Configuration:**
   - `import_actors = False` (Content Browser only, not level)
   - `import_geometry = True`
   - `import_materials = True`
   - `replace_existing = True`
   - `automated = True`

3. **Error Handling:**
   - If Unreal not running: Prints error, continues (USD files still exported)
   - If package not installed: Prints installation instructions
   - If no files found: Reports warning with expected file pattern

## Requirements for Unreal Import

### Python Package

```bash
pip install unreal-remote-execution
```

**Note:** This is an optional dependency - forest export works without it.

### Unreal Engine Setup

1. **Enable Python Plugin:**
   - Edit > Plugins > "Python Editor Script Plugin"

2. **Enable Remote Execution:**
   - Edit > Project Settings > Plugins > Python
   - Check "Enable Remote Execution"

3. **Enable USD Plugins:**
   - Edit > Plugins > "USD Importer" and "USD Core"

## Benefits of This Approach

### ✅ Integrated Workflow

- Single command generates and imports
- No separate post-processing script needed
- Natural pipeline progression

### ✅ Optional & Backwards Compatible

- Default behavior unchanged (just export)
- Opt-in with `--import-to-unreal` flag
- Graceful degradation if Unreal not available

### ✅ Clean Error Handling

- Clear error messages
- Installation instructions provided
- Continues on error (USD files still available)

### ✅ Flexible Configuration

- Custom Unreal paths
- Custom host/port for remote setups
- Works with existing quality presets

## Comparison: Standalone vs Integrated

### ❌ Original Approach (export_to_unreal.py)

```bash
# Step 1: Generate forest
python src/growpy/cli/generate_forest.py --quality high

# Step 2: Import to Unreal (separate script)
python src/growpy/cli/export_to_unreal.py forest.csv --import-to-unreal
```

**Issues:**

- Two-step process
- Need to remember separate script
- Duplicate CSV parsing logic
- Less intuitive

### ✅ New Approach (Integrated)

```bash
# One command does both
python src/growpy/cli/generate_forest.py --quality high --import-to-unreal
```

**Benefits:**

- Single command
- Natural workflow
- No duplication
- Consistent with other CLI flags

## Example Outputs

### Success

```
================================================================
Exporting groves: 100%|████████████████████| 5/5
Export completed successfully!

================================================================
UNREAL ENGINE IMPORT
================================================================
Connecting to Unreal Engine...
Connected to project: MyProject

Found 23 Nanite Assembly USD files to import
Destination: /Game/GrowPy/Trees

Executing import script in Unreal Engine...

================================================================
IMPORT COMPLETED SUCCESSFULLY
================================================================
Assets imported to Content Browser: /Game/GrowPy/Trees
Trees are ready to place in level or use with PCG
```

### Unreal Not Running

```
================================================================
Exporting groves: 100%|████████████████████| 5/5
Export completed successfully!

================================================================
UNREAL ENGINE IMPORT
================================================================
Connecting to Unreal Engine...

ERROR: Failed to connect to Unreal Engine
Make sure:
  1. Unreal Engine is running
  2. Python Remote Execution is enabled:
     Edit > Project Settings > Plugins > Python
     > Enable Remote Execution
  3. Editor Scripting Utilities plugin is enabled

Warning: Unreal import failed, but forest export completed successfully.
USD files are available in: data/output/forest
```

## Files Modified

1. `src/growpy/cli/generate_forest.py`
   - Added `import_forest_to_unreal()` function
   - Added command-line arguments
   - Integrated into main workflow
   - Updated documentation

2. `docs/growpy/PIPELINE_WORKFLOW.md` (NEW)
   - Complete pipeline guide
   - All script options documented
   - Unreal setup instructions
   - Troubleshooting section

## Testing

### Test Without Unreal

```bash
# Should export USD files normally
python src/growpy/cli/generate_forest.py --quality performance
```

### Test With Unreal (if running)

```bash
# Should export and import
python src/growpy/cli/generate_forest.py --quality performance --import-to-unreal
```

### Verify Import in Unreal

1. Open Content Browser
2. Navigate to `/Game/GrowPy/Trees`
3. Should see imported tree assets
4. Drag to viewport to test

## Migration from export_to_unreal.py

The standalone `export_to_unreal.py` is still available for reference but is superseded by the integrated approach:

**Old way:**

```bash
python src/growpy/cli/export_to_unreal.py forest.csv --import-to-unreal
```

**New way:**

```bash
python src/growpy/cli/generate_forest.py --import-to-unreal
```

## Next Steps

1. **Test the integration:**

   ```bash
   python src/growpy/cli/generate_forest.py \
       --quality performance \
       --growth-cycle-limit 3 \
       --import-to-unreal
   ```

2. **Verify in Unreal:**
   - Check Content Browser at `/Game/GrowPy/Trees`
   - Drag trees to level to test
   - Verify Nanite mesh properties

3. **Update workflow:**
   - Use integrated `--import-to-unreal` flag
   - Optionally remove standalone `export_to_unreal.py`
   - Update any scripts or documentation referencing old workflow

## Documentation

- **Pipeline Guide:** `docs/growpy/PIPELINE_WORKFLOW.md`
- **Unreal Integration:** `docs/growpy/UNREAL_INTEGRATION.md`
- **Quick Start:** `docs/growpy/UNREAL_QUICK_START.md`
- **Remote Bridge API:** `src/growpy/io/unreal_remote_bridge.py`

## Conclusion

The Unreal import is now seamlessly integrated into the forest generation pipeline. Simply add `--import-to-unreal` to `generate_forest.py` to complete the entire workflow from CSV to Unreal Content Browser in one command.

This provides a clean, intuitive workflow that follows the natural progression:

**prepare → convert → model → generate → import** ✨
