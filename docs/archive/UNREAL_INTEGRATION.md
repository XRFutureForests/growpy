# Unreal Engine Integration for GrowPy

This guide explains how to integrate GrowPy tree generation with Unreal Engine using multiple approaches.

## Overview

GrowPy can export trees in USD format that can be imported into Unreal Engine. There are three main integration methods:

1. **Manual Import** - Export USD files, manually import into Unreal
2. **VSCode Extension** - Use Unreal Engine Python extension for development
3. **Remote Execution** - Programmatic import via Python (automated workflow)

## Prerequisites

### Unreal Engine Setup

1. **Enable Python Plugin**
   - Edit > Plugins > Search "Python"
   - Enable "Python Editor Script Plugin"
   - Restart Unreal Engine

2. **Enable Remote Execution** (for automated workflows)
   - Edit > Project Settings > Plugins > Python
   - Check "Enable Remote Execution"
   - Default ports: Multicast 6766, Command 6776

3. **Enable USD Support**
   - Edit > Plugins > Search "USD"
   - Enable "USD Importer"
   - Enable "USD Core"

## Method 1: Manual Import

### Export Trees

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/forest.csv \
    --formats usda \
    --output-dir data/output/forest
```

### Import to Unreal

1. In Unreal Editor: File > Import
2. Navigate to `data/output/forest/`
3. Select USD files
4. Configure import settings:
   - Check "Import Meshes"
   - Check "Import Skeletal Animations" (for skeletal trees)
   - Check "Enable Nanite" (for Nanite assemblies)
5. Click Import

## Method 2: VSCode Extension (Development)

### Installation

1. Install extension in VSCode:
   - Search: "Unreal Engine Python" by Nils Soderman
   - Or: `ext install NilsSoderman.ue-python`

2. Extension provides:
   - Code completion for `unreal` module
   - Execute selection: `Ctrl+Enter`
   - Debug support
   - Documentation browser

### Usage

Create Unreal Python scripts in your workspace:

```python
# scripts/import_growpy_trees.py
import unreal

def import_usd_tree(usd_path: str, destination: str = "/Game/Trees"):
    """Import a single USD tree"""
    
    # Create import task
    task = unreal.AssetImportTask()
    task.filename = usd_path
    task.destination_path = destination
    task.replace_existing = True
    task.automated = True
    
    # Use USD factory
    factory = unreal.UsdStageImporterFactory()
    task.factory = factory
    
    # Execute import
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset_tools.import_asset_tasks([task])
    
    unreal.log(f"Imported {usd_path} to {destination}")

# Example usage
import_usd_tree(
    "C:/path/to/the-grove/data/output/forest/beech_001.usda",
    "/Game/GrowPy/Trees"
)
```

**Execute in Unreal:**

1. Open script in VSCode
2. Press `Ctrl+Enter` (or Cmd: `Unreal Python: Execute`)
3. Script runs in Unreal Editor

**Note:** The extension uses Unreal's Remote Execution, so ensure it's enabled in project settings.

### Customizing Keybindings

If `Ctrl+Enter` conflicts with IPython:

1. Open VSCode: File > Preferences > Keyboard Shortcuts
2. Search: "Unreal Python: Execute"
3. Change to different binding (e.g., `Ctrl+Shift+U`)

**Or via Command Palette:**

- `Ctrl+Shift+P` > "Unreal Python: Execute"

## Method 3: Remote Execution (Automated)

### Installation

```bash
conda activate the-grove
pip install unreal-remote-execution
```

### Python API Usage

```python
import asyncio
from pathlib import Path
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge

async def import_forest():
    # Connect to Unreal
    bridge = UnrealRemoteBridge()
    
    if await bridge.connect():
        print(f"Connected to: {bridge.project_name}")
        
        # Execute import script
        result = await bridge.execute_script('''
import unreal

# Import a single tree
task = unreal.AssetImportTask()
task.filename = r"C:/path/to/tree.usda"
task.destination_path = "/Game/Trees"
task.replace_existing = True
task.automated = True

factory = unreal.UsdStageImporterFactory()
task.factory = factory

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
asset_tools.import_asset_tasks([task])

unreal.log("Import completed")
        ''')
        
        if result and result['success']:
            print("Import successful!")
        
        await bridge.disconnect()

# Run
asyncio.run(import_forest())
```

### CLI Tool

Use the provided CLI tool for automated import:

```bash
# Export and import to Unreal in one step
python src/growpy/cli/export_to_unreal.py data/input/forest.csv \
    --import-to-unreal \
    --unreal-project-path "/Game/GrowPy/Trees" \
    --output-dir data/output/forest
```

**Options:**

- `--import-to-unreal` - Enable automatic import
- `--unreal-project-path` - Target path in Unreal (default: /Game/GrowPy/Trees)
- `--host` - Unreal host (default: localhost)
- `--port` - Command port (default: 6776)

## Integration Examples

### Example 1: Batch Import All Trees

```python
import asyncio
from pathlib import Path
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge

async def batch_import_trees(output_dir: Path, destination: str):
    bridge = UnrealRemoteBridge()
    
    if not await bridge.connect():
        print("Failed to connect")
        return
    
    # Find all USD files
    usd_files = list(output_dir.glob("**/*.usda"))
    
    for usd_file in usd_files:
        usd_path = str(usd_file.resolve()).replace("\\", "/")
        
        script = f'''
import unreal
task = unreal.AssetImportTask()
task.filename = r"{usd_path}"
task.destination_path = "{destination}"
task.replace_existing = True
task.automated = True
task.factory = unreal.UsdStageImporterFactory()
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log("Imported {usd_file.name}")
        '''
        
        await bridge.execute_script(script)
    
    await bridge.disconnect()

# Run
asyncio.run(batch_import_trees(
    Path("data/output/forest"),
    "/Game/GrowPy/Trees"
))
```

### Example 2: Import with Progress Tracking

```python
import asyncio
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge

async def import_with_progress():
    bridge = UnrealRemoteBridge()
    
    if await bridge.connect():
        # Create slow task for progress UI
        script = '''
import unreal

with unreal.ScopedSlowTask(10, "Importing GrowPy Trees") as slow_task:
    slow_task.make_dialog(True)
    
    for i in range(10):
        if slow_task.should_cancel():
            break
        
        slow_task.enter_progress_frame(1, f"Importing tree {i+1}/10")
        
        # Import tree logic here
        import time
        time.sleep(0.5)
    
    unreal.log("Import completed")
        '''
        
        await bridge.execute_script(script)
        await bridge.disconnect()

asyncio.run(import_with_progress())
```

### Example 3: Create Foliage Type for PCG

```python
import asyncio
from growpy.io.unreal_remote_bridge import UnrealRemoteBridge

async def create_foliage_type():
    bridge = UnrealRemoteBridge()
    
    if await bridge.connect():
        script = '''
import unreal

# Load imported tree mesh
tree_mesh = unreal.EditorAssetLibrary.load_asset("/Game/Trees/Beech_001")

# Create foliage type
foliage_type = unreal.FoliageType_InstancedStaticMesh()
foliage_type.mesh = tree_mesh

# Configure density and scale
foliage_type.density = unreal.FloatInterval(min=0.5, max=2.0)
foliage_type.scaling = unreal.FoliageVertexColorChannelMask.FOLIAGE_VERTEX_COLOR_CHANNEL_MAX_COLOR_BLUE

# Save as asset
package_path = "/Game/Foliage/FT_Beech_001"
unreal.EditorAssetLibrary.save_asset(package_path)
unreal.log(f"Created foliage type: {package_path}")
        '''
        
        await bridge.execute_script(script)
        await bridge.disconnect()

asyncio.run(create_foliage_type())
```

## Troubleshooting

### Connection Issues

**Error: "Failed to connect to Unreal Engine"**

1. Check Unreal is running
2. Verify Remote Execution enabled:
   - Edit > Project Settings > Plugins > Python
   - Enable Remote Execution
3. Check firewall settings (ports 6766, 6776)
4. Try custom port:

   ```python
   from growpy.io.unreal_remote_bridge import UnrealConnectionConfig
   config = UnrealConnectionConfig(command_port=6777)
   bridge = UnrealRemoteBridge(config)
   ```

### Import Issues

**USD files not importing correctly:**

1. Enable USD plugins (USD Core, USD Importer)
2. Disable USD Interchange:
   - Edit > Project Settings > Plugins > USD
   - Uncheck "USD Interchange"
3. Check Nanite Assembly settings:
   - Edit > Project Settings > Engine > Rendering
   - Enable "Support Nanite Assemblies"

**Skeletal meshes not recognized:**

1. Check USD contains SkelRoot/Skeleton hierarchy
2. Verify joint bindings in USD file
3. Re-export with `--include-skeleton` flag

### VSCode Extension Issues

**Ctrl+Enter not working:**

1. Check extension installed and enabled
2. Verify Unreal Remote Execution enabled
3. Check Output panel: "UE Python" for error messages
4. Try Command Palette: `Ctrl+Shift+P` > "Unreal Python: Execute"

**Code completion not working:**

1. Run command: "Unreal Python: Setup code completion"
2. Restart VSCode
3. Check Python interpreter points to correct environment

## Performance Tips

1. **Batch Imports**: Import multiple files in one script to reduce overhead
2. **Disable UI**: Use `task.automated = True` for background imports
3. **Nanite Assemblies**: Enable for high-poly forests (5.7+)
4. **LODs**: Generate LODs during import for better performance

## Security Notes

- Remote Execution opens a network port - only enable during development
- Do not enable in shipping builds
- Firewall may block connections - add exception if needed
- Use localhost (127.0.0.1) for local development

## Resources

- [Unreal Python API](https://docs.unrealengine.com/en-US/PythonAPI/)
- [USD in Unreal](https://docs.unrealengine.com/en-US/WorkingWithContent/UnrealSceneDescription/)
- [VSCode Extension Wiki](https://github.com/nils-soderman/vscode-unreal-python/wiki)
- [Remote Execution Protocol](https://docs.unrealengine.com/en-US/ProductionPipelines/ScriptingAndAutomation/Python/)

## Next Steps

1. Generate forest: `python src/growpy/cli/generate_forest.py`
2. Choose integration method based on workflow:
   - Development: VSCode extension
   - Production: Remote Execution API
   - One-off: Manual import
3. Set up PCG for procedural placement
4. Configure materials and wind animation
