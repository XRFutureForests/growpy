# PVE Preset Import Quick Start Guide

Step-by-step guide for importing GrowPy-generated PVE presets into Unreal Engine.

## Prerequisites

1. **Enable PVE Debug Mode FIRST** (before creating any assets)
2. Import USD skeletal meshes
3. Have PVE JSON files from GrowPy

---

## Step 1: Enable PVE Debug Mode (REQUIRED)

**You must do this BEFORE creating the PVE data asset**, otherwise the required properties will be hidden.

### Option A: Persistent (Recommended)

1. Open `<YourProject>/Config/DefaultEditor.ini` in a text editor

2. Scroll to the **very bottom** of the file

3. Add these two lines at the end:

   ```ini
   [ConsoleVariables]
   PV.DebugMode.Enabled=1
   ```

4. Save and restart Unreal Editor

**Note**: Add after all existing content (after the `[/Script/AdvancedPreviewScene.SharedProfiles]` section).

### Option B: Temporary (Current Session Only)

In Unreal Editor console (press `~` key):

```
PV.DebugMode.Enabled 1
```

---

## Step 2: Import USD Skeletal Meshes

1. In Content Browser, navigate to your species folder (create if needed):
   - Example: `Content/Trees/Tree_European_Beech/`

2. Right-click > Import

3. Select USD file:
   - `data/output/forest/european_beech/european_beech_tree_0000_skeletal_nanite_assembly.usda`

4. USD Import creates:
   - `Materials/` folder
   - `SkeletalMeshes/` folder (contains both tree AND foliage meshes)
   - `Textures/` folder

---

## Step 3: Create Instances Folder

In your species folder:

1. Right-click > New Folder
2. Name it: `Instances`

---

## Step 4: Copy PVE JSON Files

Copy JSON files from GrowPy output to Unreal:

**From**: `data/output/forest/pve_presets/european_beech/*.json`
**To**: `Content/Trees/Tree_European_Beech/Instances/`

Example files:
- `european_beech_tree_0000.json`
- `european_beech_tree_0001.json`
- `european_beech_tree_0002.json`

---

## Step 5: Create PVE Data Asset

1. Right-click in species folder (`Tree_European_Beech`)

2. Procedural Vegetation > **Procedural Vegetation Preset**

3. Name it: `PVE_EuropeanBeech_Data`

4. Double-click to open

---

## Step 6: Configure PVE Data Asset

In the Details panel, you should now see **Internal** category (thanks to debug mode):

### Required Settings:

**JsonDirectoryPath**: `./Instances`
- Points to folder with JSON files

**bOverrideFolderPaths**: ✓ (check this box)

**FoliageFolder**: `./SkeletalMeshes`
- Points to where foliage meshes are (from USD import)

**MaterialsFolder**: `./Materials`
- Points to where materials are (from USD import)

**TrunkMaterialName**: `MI_EuropeanBeech_Bark`
- Name of your bark material (no path, no extension)
- Must match actual material asset name

### Optional Settings:

**bCreateProfileDataAsset**: ☐ (leave unchecked for now)

---

## Step 7: Update Data Asset

1. Click **"Update Data Asset"** button in Details panel

2. Check Output Log for success messages:
   ```
   LogProceduralVegetation: Loaded variant : european_beech_tree_0000
   LogProceduralVegetation: Loaded variant : european_beech_tree_0001
   LogProceduralVegetation: Loaded variant : european_beech_tree_0002
   ```

3. Verify **Preset Data** category shows loaded variants

---

## Final Folder Structure

```
Content/Trees/Tree_European_Beech/
├── PVE_EuropeanBeech_Data.uasset       # Your configured data asset
│
├── Instances/                           # JSON files
│   ├── european_beech_tree_0000.json
│   ├── european_beech_tree_0001.json
│   └── european_beech_tree_0002.json
│
├── SkeletalMeshes/                      # From USD import
│   ├── SK_EuropeanBeech_Tree_01.uasset       # Full tree
│   ├── SK_EuropeanBeech_Tree_01_Skeleton.uasset
│   ├── SK_BrLeaf_000.uasset                  # Foliage meshes
│   ├── SK_BrTwig_000.uasset
│   └── ...
│
├── Materials/                           # From USD import
│   ├── MI_EuropeanBeech_Bark.uasset
│   └── MI_EuropeanBeech_Foliage.uasset
│
└── Textures/                            # From USD import
    └── ...
```

---

## Troubleshooting

### "Properties Not Visible"

**Problem**: JsonDirectoryPath, FoliageFolder, etc. are hidden

**Solution**: Enable PVE Debug Mode BEFORE creating the data asset:
- Console: `PV.DebugMode.Enabled 1`
- Or add to `DefaultEditor.ini` (see Step 1)

### "No Variants Loaded"

**Problem**: "Update Data Asset" doesn't load any variants

**Solutions**:
1. Check JsonDirectoryPath points to correct folder (`./Instances`)
2. Verify JSON files are in that folder
3. Check Output Log for JSON parsing errors
4. Ensure JSON files are valid MegaPlants format

### "Material Not Found"

**Problem**: Trunk material not applied

**Solutions**:
1. Check TrunkMaterialName matches material asset name exactly
2. Name should be base name only: `MI_EuropeanBeech_Bark` (not full path)
3. Verify material exists in Materials/ folder
4. Check MaterialsFolder points to `./Materials`

### "Foliage Meshes Missing"

**Problem**: No leaves/twigs on tree

**Solutions**:
1. Check FoliageFolder points to `./SkeletalMeshes`
2. Verify foliage meshes exist in SkeletalMeshes/ folder
3. Ensure mesh names in JSON match asset names
4. Check bOverrideFolderPaths is enabled

---

## Next Steps

After successful import:

1. **Create PVE Graph**: Right-click > Procedural Vegetation > Procedural Vegetation

2. **Add Preset Loader Node**: Reference your `PVE_EuropeanBeech_Data` asset

3. **Test in Level**: Drag PVE graph into level and generate tree

4. **Integrate with PCG**: Use for landscape-scale forests

---

## Key Takeaways

✅ **Always enable debug mode BEFORE creating PVE data asset**
✅ **Keep USD import folder structure** - use `bOverrideFolderPaths` to point to it
✅ **JSON files go in Instances/** - separate from meshes
✅ **FoliageFolder points to SkeletalMeshes/** - where foliage meshes are
✅ **TrunkMaterialName is base name only** - no path or extension

---

## See Also

- [PVE Asset Structure](PVE_ASSET_STRUCTURE.md) - Detailed property reference
- [PVE Preset Workflow](PVE_PRESET_WORKFLOW.md) - Complete workflow guide
- [PVE Attribute Reference](PVE_ATTRIBUTE_REFERENCE.md) - JSON attribute documentation
