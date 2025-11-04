# Unreal Engine Integration - Quick Start

## Three Ways to Run Python in Unreal

### 1. VSCode Extension (Interactive Development)

**Install:**

```bash
code --install-extension NilsSoderman.ue-python
```

**Use:**

1. Open Python script in VSCode
2. Press `Ctrl+Enter` to execute in Unreal
3. Or: `Ctrl+Shift+P` > "Unreal Python: Execute"

**Note:** Doesn't conflict with IPython - only runs when .py file is active

### 2. Programmatic (For GrowPy Integration)

**Install:**

```bash
pip install unreal-remote-execution
```

**Use:**

```python
import asyncio
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge

async def main():
    bridge = UnrealRemoteBridge()
    if await bridge.connect():
        await bridge.execute_script('unreal.log("Hello!")')
        await bridge.disconnect()

asyncio.run(main())
```

### 3. CLI Tool (Automated Workflow)

**Use:**

```bash
python src/growpy/cli/export_to_unreal.py forest.csv \
    --import-to-unreal \
    --unreal-project-path "/Game/Trees"
```

## Unreal Setup (Required for All Methods)

1. **Enable Python Plugin:**
   - Edit > Plugins > Search "Python"
   - Enable "Python Editor Script Plugin"
   - Restart

2. **Enable Remote Execution:**
   - Edit > Project Settings > Plugins > Python
   - Check "Enable Remote Execution"

3. **Enable USD:**
   - Edit > Plugins > Search "USD"
   - Enable "USD Importer" and "USD Core"

## Complete Workflow Example

```bash
# 1. Generate forest
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/forest.csv

# 2. Import to Unreal (automated)
python src/growpy/cli/export_to_unreal.py data/input/forest.csv \
    --import-to-unreal \
    --output-dir data/output/forest
```

## Recommendation for GrowPy

Use **Method 2 (Programmatic)** because:

- ✅ No manual intervention
- ✅ Integrates directly into pipeline
- ✅ Can be called from other Python scripts
- ✅ Full control over import process

**Example Integration:**

```python
# In your forest generation script
from growpy.io.unreal_remote_bridge import execute_in_unreal

# After exporting USD files
await execute_in_unreal(f'''
import unreal
# Import your trees
task = unreal.AssetImportTask()
task.filename = r"{usd_path}"
task.destination_path = "/Game/Trees"
task.automated = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
''')
```

## Troubleshooting

**"Failed to connect":**

- Unreal running?
- Remote Execution enabled? (See step 2 above)
- Firewall blocking ports 6766/6776?

**VSCode extension not working:**

- Remote Execution must be enabled in Unreal
- Check Output panel: "UE Python" for errors

**For more details:** See [UNREAL_INTEGRATION.md](UNREAL_INTEGRATION.md)
