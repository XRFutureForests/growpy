# Unreal Engine Integration Guide - VSCode Extension Method

This guide explains how to use GrowPy's Unreal Engine integration via standalone Python scripts executed with the VSCode Unreal Python extension.

## Overview

GrowPy generates standalone Unreal Python scripts that you can execute directly in Unreal Engine without needing socket connections or Remote Execution services. This is the simplest and most reliable method.

## Setup

### 1. Install VSCode Extension

Install the **Unreal Python** extension by Nils Soderman:

- Open VSCode Extensions (Ctrl+Shift+X)
- Search for "Unreal Python"
- Install extension

### 2. Enable Unreal Plugins

In Unreal Engine, enable these plugins:

1. Edit > Plugins
2. Enable:
   - **Python Editor Script Plugin** (built-in)
   - **Editor Scripting Utilities** (built-in)
   - **USD Importer** (for USD imports)
3. Restart Unreal Editor

## Workflow

### Step 1: Generate Forest with Import Script

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 3 --import-to-unreal
```

This creates:

- USD tree files in `data/output/forest/`
- Unreal import script in `data/output/forest/unreal_scripts/import_forest.py`

### Step 2: Execute Import Script in Unreal

**Method A: VSCode Extension (Recommended)**

1. Open `data/output/forest/unreal_scripts/import_forest.py` in VSCode
2. Make sure Unreal Engine is running
3. Right-click anywhere in the file
4. Select **"Execute Python File in Unreal"**
5. Watch Unreal's Output Log for progress

**Method B: Unreal Python Console**

1. In Unreal: Window > Developer Tools > Python Console
2. Execute:

   ```python
   exec(open(r'C:\path\to\import_forest.py').read())
   ```

### Step 3: Verify Import

Check Unreal Content Browser:

- Default location: `/Game/GrowPy/Trees/`
- Trees are imported as assets (not placed in level)
- Ready to use with PCG or manual placement

### Step 4: (Optional) Cleanup

Generate cleanup script:

```bash
python src/growpy/cli/clean_unreal_assets.py --dry-run
```

This creates `src/growpy/io/unreal_scripts/clean_assets_generated.py`

Execute in Unreal (same methods as import):

- Right-click in VSCode > "Execute Python File in Unreal"
- Or use Unreal Python console

## Command Reference

### Generate Forest with Unreal Script

```bash
# Basic usage
python src/growpy/cli/generate_forest.py --import-to-unreal

# High quality with custom destination
python src/growpy/cli/generate_forest.py --quality high --import-to-unreal --unreal-project-path /Game/MyProject/Trees

# Ultra quality for hero trees
python src/growpy/cli/generate_forest.py --quality ultra --growth-cycle-limit 15 --import-to-unreal

# Custom CSV input
python src/growpy/cli/generate_forest.py my_forest.csv --quality high --import-to-unreal
```

### Generate Cleanup Script

```bash
# Dry run (preview only)
python src/growpy/cli/clean_unreal_assets.py --dry-run

# Live mode (will delete assets)
python src/growpy/cli/clean_unreal_assets.py

# Custom location
python src/growpy/cli/clean_unreal_assets.py --unreal-project-path /Game/MyProject/Trees

# Custom output path
python src/growpy/cli/clean_unreal_assets.py --output-path my_cleanup.py
```

## Script Templates

GrowPy provides reusable script templates in `src/growpy/io/unreal_scripts/`:

### import_forest.py (Template)

- Generic import script
- Edit `USD_FILES_DIR` and `IMPORT_PATH` before using
- Good for manual/custom imports

### clean_assets.py (Template)

- Generic cleanup script
- Edit `CLEANUP_PATH` and `DRY_RUN` before using
- Reusable for different projects

## Troubleshooting

### "Import unreal could not be resolved" Error in VSCode

This is expected - the `unreal` module only exists inside Unreal Engine. The script will work fine when executed in Unreal.

### Script Execution Shows No Output

1. Check Unreal Output Log is visible: Window > Developer Tools > Output Log
2. Enable "Python" category in Output Log filter
3. Verify Python plugin is enabled: Edit > Project Settings > Plugins > Python

### Import Fails

- Verify USD Importer plugin is enabled
- Check file paths in generated script are correct
- Ensure USD files exist at specified paths

### Assets Not Appearing in Content Browser

- Check destination path: `/Game/GrowPy/Trees/` by default
- Refresh Content Browser (right-click > Refresh)
- Verify import completed successfully in Output Log

### VSCode Extension Not Working

- Verify Unreal Engine is running
- Check extension is installed and enabled
- Try restarting VSCode

## Advantages vs Socket Method

**Standalone Scripts:**

- ✅ No connection setup required
- ✅ No port configuration needed
- ✅ Works with standard VSCode extension
- ✅ Reliable execution
- ✅ Easy to debug
- ✅ Can be version controlled

**Socket Method (Old):**

- ❌ Required port 6776 open
- ❌ Needed Remote Execution service
- ❌ Connection troubleshooting
- ❌ More complex setup

## Best Practices

1. **Always use --dry-run first** when generating cleanup scripts
2. **Check Output Log** in Unreal for detailed feedback
3. **Use absolute paths** in scripts for reliability
4. **Generate fresh scripts** for each export (paths are baked in)
5. **Keep Unreal running** before executing scripts
6. **Enable all required plugins** before first use

## Example Complete Workflow

```bash
# 1. Generate forest with import script
conda activate the-grove
python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 5 --import-to-unreal

# 2. Open generated script in VSCode
code data/output/forest/unreal_scripts/import_forest.py

# 3. In VSCode, right-click > "Execute Python File in Unreal"
# Watch Unreal Output Log for progress

# 4. Verify trees in Content Browser at /Game/GrowPy/Trees/

# 5. (Later) Generate cleanup script if needed
python src/growpy/cli/clean_unreal_assets.py --dry-run

# 6. Open cleanup script
code src/growpy/io/unreal_scripts/clean_assets_generated.py

# 7. Execute to preview deletions (DRY_RUN=True)
# Then edit script to set DRY_RUN=False and execute again to delete
```

## Additional Resources

- **VSCode Extension**: [Unreal Python by Nils Soderman](https://marketplace.visualstudio.com/items?itemName=nils-soderman.unreal-python)
- **Script Templates**: `src/growpy/io/unreal_scripts/`
- **Generated Scripts**: `data/output/forest/unreal_scripts/` (import) and `src/growpy/io/unreal_scripts/` (cleanup)
- **Unreal Python Docs**: [Official Unreal Engine Python API](https://docs.unrealengine.com/en-US/PythonAPI/)
