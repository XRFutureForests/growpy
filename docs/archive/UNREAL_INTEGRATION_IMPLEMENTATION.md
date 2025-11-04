# Unreal Integration Implementation Summary

**Date:** 2025-11-04  
**Status:** Implementation Complete

## What Was Added

### 1. Remote Execution Bridge (`src/growpy/io/unreal_remote_bridge.py`)

A Python module that provides clean interface for executing Python code in Unreal Engine without VSCode:

**Features:**

- Asynchronous connection to Unreal Engine via Remote Execution protocol
- Execute Python code strings or files
- Connection management with auto-reconnect
- Project detection and status reporting

**Key Classes:**

- `UnrealRemoteBridge` - Main bridge class for Unreal communication
- `UnrealConnectionConfig` - Configuration for host/port settings
- `execute_in_unreal()` - Convenience function for one-off executions

**Dependencies:**

- `unreal-remote-execution` package (available on PyPI)

### 2. CLI Tool (`src/growpy/cli/export_to_unreal.py`)

Command-line tool for automated Unreal import:

**Features:**

- Export forest data and import to Unreal in single command
- Batch import multiple USD files
- Configurable destination paths in Unreal
- Custom host/port for remote connections

**Usage:**

```bash
python src/growpy/cli/export_to_unreal.py forest.csv \
    --import-to-unreal \
    --unreal-project-path "/Game/GrowPy/Trees"
```

### 3. Documentation

**`docs/growpy/UNREAL_INTEGRATION.md`** - Complete integration guide covering:

- Three integration methods (Manual, VSCode Extension, Remote Execution)
- Setup instructions for Unreal Engine
- Code examples for all use cases
- Troubleshooting section
- Performance tips

**`docs/growpy/UNREAL_QUICK_START.md`** - Quick reference:

- One-page overview of all methods
- Setup checklist
- Complete workflow example
- Troubleshooting tips

## Integration Methods Explained

### Method 1: VSCode Extension (Development)

**What it is:**

- Third-party VSCode extension by Nils Soderman
- Adds commands to execute Python in Unreal
- Uses same Remote Execution protocol internally

**How to use:**

- Install extension: `NilsSoderman.ue-python`
- Open Python script
- Press `Ctrl+Enter` or run command "Unreal Python: Execute"

**Does NOT conflict with IPython:**

- Only activates when .py file is open in editor
- IPython typically used in notebooks (.ipynb)
- Can rebind to different keyboard shortcut if needed

**When to use:**

- Interactive development
- Testing Unreal scripts
- Quick iterations

### Method 2: Programmatic API (Production)

**What it is:**

- Direct Python API using `unreal-remote-execution` package
- Same protocol as VSCode extension, but without VSCode
- Full programmatic control

**How to use:**

```python
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge
bridge = UnrealRemoteBridge()
await bridge.connect()
await bridge.execute_script('...')
```

**When to use:**

- Automated pipelines
- Integration into GrowPy workflows
- Batch operations
- **Recommended for GrowPy integration**

### Method 3: CLI Tool (Convenience)

**What it is:**

- Wrapper around Method 2
- Command-line interface for common operations

**How to use:**

```bash
python src/growpy/cli/export_to_unreal.py forest.csv --import-to-unreal
```

**When to use:**

- One-off imports
- Testing
- Manual workflow automation

## How Remote Execution Works

The VSCode extension and our bridge both use **Unreal's Remote Execution Protocol**:

1. **Multicast Discovery** (port 6766):
   - Unreal broadcasts presence on network
   - Clients discover running Unreal instances

2. **Command Connection** (port 6776):
   - Client opens TCP connection to Unreal
   - Sends Python code to execute
   - Receives output and results

3. **Execution in Unreal**:
   - Code runs in Unreal's Python interpreter
   - Has access to full `unreal` module
   - Runs in Editor (not packaged builds)

## Unreal Setup Required

All methods require enabling Remote Execution in Unreal:

**Project Settings > Plugins > Python:**

- ✅ Enable "Python Editor Script Plugin"
- ✅ Enable "Remote Execution"

**Default Ports:**

- Multicast: 6766
- Command: 6776

**Security Note:** Only enable during development - opens network port

## Integration Points for GrowPy

### Option 1: Add to Existing Scripts

Modify `generate_forest.py` or `export_trees.py` to include Unreal import:

```python
# At end of export script
if args.import_to_unreal:
    from growpy.io.unreal_remote_bridge import UnrealRemoteBridge
    
    bridge = UnrealRemoteBridge()
    if await bridge.connect():
        # Import generated trees
        ...
```

### Option 2: Separate Post-Processing Step

Keep export separate, add optional Unreal import step:

```bash
# Step 1: Generate
python src/growpy/cli/generate_forest.py forest.csv

# Step 2: Import (optional)
python src/growpy/cli/export_to_unreal.py forest.csv --import-to-unreal
```

### Option 3: Pipeline Integration

Add to `run_pipeline.py` as optional step:

```python
# Step 5: Import to Unreal (optional)
if args.import_to_unreal:
    import_to_unreal(output_dir)
```

## Recommendation

For GrowPy, I recommend **Method 2 (Programmatic API)** because:

1. **No VSCode dependency** - Works from any Python script
2. **Automation-friendly** - Can integrate into CLI scripts
3. **Full control** - Programmatic access to all features
4. **Same protocol** - Uses same Remote Execution as VSCode extension

**Implementation:**

- Use `UnrealRemoteBridge` class in `growpy.io.unreal_remote_bridge`
- Add `--import-to-unreal` flag to existing CLI scripts
- Optional dependency: `pip install unreal-remote-execution`

## Installation

```bash
conda activate the-grove

# Install remote execution library (optional)
pip install unreal-remote-execution

# For VSCode extension (optional)
code --install-extension NilsSoderman.ue-python
```

## Example Workflow

```bash
# 1. Generate forest with GrowPy
python src/growpy/cli/generate_forest.py data/input/forest.csv \
    --output-dir data/output/forest

# 2. Import to Unreal (automated)
python src/growpy/cli/export_to_unreal.py data/input/forest.csv \
    --import-to-unreal \
    --unreal-project-path "/Game/GrowPy/Trees"
```

Or programmatically:

```python
import asyncio
from growpy.io.unreal_remote_bridge import execute_in_unreal

# After generating USD files
await execute_in_unreal('''
import unreal
# Import trees into Unreal
task = unreal.AssetImportTask()
task.filename = r"C:/path/to/tree.usda"
task.destination_path = "/Game/Trees"
task.automated = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
''')
```

## Files Created

1. `src/growpy/io/unreal_remote_bridge.py` - Remote execution bridge
2. `src/growpy/cli/export_to_unreal.py` - CLI tool for automated import
3. `docs/growpy/UNREAL_INTEGRATION.md` - Complete integration guide
4. `docs/growpy/UNREAL_QUICK_START.md` - Quick reference

## Next Steps

1. **Test Connection:**

   ```bash
   python src/growpy/io/unreal_remote_bridge.py
   ```

2. **Test Import:**

   ```bash
   python src/growpy/cli/export_to_unreal.py data/input/test.csv \
       --import-to-unreal \
       --output-dir data/output/test
   ```

3. **Integrate into Pipeline:**
   - Add `--import-to-unreal` flag to existing scripts
   - Or keep as separate post-processing step

4. **Optional: Install VSCode Extension**
   - For interactive development
   - Install: `NilsSoderman.ue-python`
   - Configure keybinding if needed

## Support

- **Remote Execution Issues:** See troubleshooting in `UNREAL_INTEGRATION.md`
- **VSCode Extension:** <https://github.com/nils-soderman/vscode-unreal-python>
- **Unreal Python API:** <https://docs.unrealengine.com/en-US/PythonAPI/>
