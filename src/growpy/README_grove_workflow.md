w# Grove Data Export/Import Workflow

This guide explains how to export grove simulation data from the Python API and import it into Blender's Grove add-on for further editing and animation.

## Overview

The workflow allows you to:

1. Create and simulate forests using the Python API
2. Export grove simulation data (not just static models)
3. Import the grove data into Blender
4. Use Blender's Grove add-on features (animation, wind, advanced materials, etc.)

## Step 1: Export Grove Data from Python

The `grow_forest.py` script now includes grove data export functionality:

```python
# Your existing simulation code
forest = []
forest = add_trees(forest, csv_path, config)
grow_forest(forest, config)

# Export grove data for Blender import
export_grove_data_only(forest, config)
```

This creates JSON files like:

- `Fagaceae___Beech_grove.json`
- `Pinaceae___Scots_pine_grove.json`
- etc.

Each file contains the complete simulation state including:

- Tree structures and branching
- Growth parameters
- Simulation history
- All node data (positions, thickness, age, etc.)

## Step 2: Import into Blender

### Method 1: Using the Import Script

1. Open Blender with The Grove add-on installed
2. Go to the Scripting workspace
3. Open `import_to_blender.py` in the text editor
4. Update the `output_directory` path to your export location
5. Run the script

### Method 2: Manual Import (Advanced)

```python
import gzip
import the_grove_22_core as gc

# Read grove data
with open('path/to/your/grove.json', 'r') as f:
    grove_json = f.read()

# Create collection and store grove data
collection = bpy.data.collections.new("My_Grove")
bpy.context.scene.collection.children.link(collection)

# Compress and store (like Grove add-on expects)
compressed_grove = gzip.compress(bytes(grove_json.encode('utf-8')), compresslevel=1)
collection['grove'] = compressed_grove
```

## Step 3: Use in Blender

After importing:

1. **Select the Grove Collection**: Make sure the imported collection is active
2. **Rebuild**: Use The Grove's "Rebuild" button to generate the 3D geometry
3. **Modify**: You can now modify growth parameters in Blender's Grove panel
4. **Animate**: Use "Build > Animate" to create wind animation
5. **Export Animation**: Export as Alembic for use in other software

## Benefits of This Workflow

### Python API Advantages

- Batch processing multiple species
- Data-driven forest generation from CSV files
- Automated LOD generation
- Integration with scientific data
- Scripted parameter variation

### Blender Add-on Advantages

- Interactive editing and refinement
- Wind animation and shape keys
- Advanced material setup
- Alembic export for animation
- Visual feedback and adjustment
- Manual pruning and editing

## File Types Explained

### Grove JSON Files (`*_grove.json`)

- Complete simulation state
- Can be imported into Blender
- Allows further simulation and editing
- Preserves all growth parameters

### Static OBJ Files (`*_LOD*.obj`)

- Pre-built geometry at specific detail levels
- Static meshes only (no animation)
- Ready for immediate use in other software
- Multiple LOD levels for performance optimization

### Future: USD Export

- The Python API also supports USD export
- USD files could potentially support animation data
- More flexible format for complex pipelines

## Troubleshooting

### Grove Import Issues

- Ensure The Grove add-on is installed and enabled in Blender
- Check that the JSON file is valid and not corrupted
- Verify file paths are correct

### Performance

- Large forests may take time to rebuild in Blender
- Consider importing species separately for easier management
- Use LOD models for viewport performance

### Animation Export

- Wind animation requires rebuilding in Blender first
- Use Alembic export with "Face Sets" enabled for materials
- Match frame ranges for proper animation loops

## Example Workflow

```bash
# 1. Run Python simulation
cd /path/to/grove/src/growpy
python grow_forest.py

# 2. Files created in data/output/:
# - Fagaceae___Beech_grove.json
# - Pinaceae___Scots_pine_grove.json
# - Various LOD OBJ files

# 3. Open Blender, run import script
# 4. Select imported grove collection
# 5. Click "Rebuild" in Grove panel
# 6. Adjust parameters as needed
# 7. Create wind animation
# 8. Export as Alembic
```

This workflow gives you the best of both worlds: the power and automation of the Python API for initial forest generation, combined with Blender's interactive tools for refinement and animation.
