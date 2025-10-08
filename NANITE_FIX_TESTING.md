# Testing the Nanite Skeletal Mesh Fix

## Quick Start

### 1. Re-export One Tree to Test

```bash
# Activate environment
conda activate the-grove

# Export a single tree with FBX + Nanite assembly
python src/growpy/cli/generate_forest.py \
    data/input/mini_tree_inventory_32632.csv \
    --formats usda fbx \
    --create-nanite-assembly \
    --limit 1
```

### 2. Check the Output

Look for these files in `data/output/forest/[Species]/`:

```
FBX/
  └── [Species]_var1.fbx          # Tree with skeleton (cleaned mesh)
USD/
  ├── [Species]_var1.usda         # Base tree USD
  ├── [Species]_var1_NaniteAssembly.usda         # Static mesh version
  └── [Species]_var1_NaniteAssembly_Skeletal.usda  # Skeletal mesh version (FIXED)
```

### 3. Verify Mesh Cleanup

Check the export log for:

```
Mesh stats: XXXX verts, YYYY faces
```

This confirms the mesh was processed before export.

### 4. Test in Unreal Engine

1. **Open Unreal Engine 5.x project**
2. **Open USD Stage browser** (Window → USD Stage)
3. **Import the skeletal assembly**:
   - Navigate to `[Species]_var1_NaniteAssembly_Skeletal.usda`
   - Right-click → Import
   - Wait for import to complete

**Expected Result**: ✅ No crash, successful Nanite encoding

**Previous Result**: ❌ Crash with `ParentLODError >= 0.0f` assertion

### 5. Verify Nanite is Active

1. **Select the imported skeletal mesh** in Content Browser
2. **Open in Skeletal Mesh Editor**
3. **Check Details panel**:
   - Look for "Nanite Settings" section
   - Verify "Enable Nanite Support" is checked
   - Check for any warning/error messages

## Full Re-Export

Once you've verified the fix works with one tree:

```bash
# Re-export all trees
python src/growpy/cli/generate_forest.py \
    data/input/mini_tree_inventory_32632.csv \
    --formats usda fbx \
    --create-nanite-assembly
```

This will process all rows in your input CSV.

## What Changed?

The export process now:

1. **Removes degenerate geometry** before triangulation
2. **Merges duplicate vertices** (threshold: 0.1mm)
3. **Dissolves zero-area faces** (threshold: 0.0001m²)
4. **Applies proper scaling** for Unreal's centimeter units (100x)

These changes prevent the Nanite hierarchy builder from encountering invalid geometry.

## Troubleshooting

### If You Still Get a Crash

1. **Check the mesh stats** in export log - look for very high or very low polygon counts
2. **Try exporting without skeleton** first (use static mesh assembly instead)
3. **Check Unreal Output Log** for additional error messages before the crash
4. **Verify you're using the newly exported files** (check file timestamps)

### If Import is Slow

- Nanite encoding is computationally intensive
- Large trees (>100k faces) may take 1-2 minutes per variation
- This is normal and expected

### If Nanite Doesn't Appear Enabled

- Check that you imported the `*_NaniteAssembly_Skeletal.usda` file (not the base `.fbx`)
- Verify your Unreal project supports Nanite (requires UE5+)
- Check Project Settings → Engine → Rendering → Support Nanite

## Performance Notes

With the cleanup operations, expect:

- **+0.5-1 second** per tree export (negligible)
- **Cleaner geometry** with fewer vertices/faces
- **Stable Nanite imports** without crashes
- **Better runtime performance** in Unreal

## Next Steps

After successful testing:

1. ✅ Re-export your full forest dataset
2. ✅ Import skeletal assemblies in Unreal
3. ✅ Test with wind animations (skeletal meshes support Control Rigs)
4. ✅ Compare static vs skeletal mesh performance
5. ✅ Celebrate no more crashes! 🎉

---

**Documentation**: See `docs/archive/NANITE_SKELETAL_CRASH_FIX.md` for full technical details.
