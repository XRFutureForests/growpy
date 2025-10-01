# Unreal Engine Import Guide for GrowPy Trees

## Quick Start

Export trees for Unreal with procedural variations:

```bash
./.conda/python.exe src/growpy/cli/export_for_unreal.py data/input/mini_tree_inventory_32632.csv --variations 3
```

## What Are The 3 Variations?

Each species is exported with 3 distinct variations for procedural diversity:

### Variation 1: **Standard Tree**
- Normal growth pattern
- Balanced branch distribution
- 10 growth flushes
- **Use for:** Main tree population

### Variation 2: **Leaning Dense Tree**
- 15° lean angle (more natural/wind-affected look)
- 20% more branch density
- Slightly thinner branches (0.9x)
- 11 growth flushes
- **Use for:** Edge trees, forest borders, varied terrain

### Variation 3: **Upright Thick Tree**
- Minimal lean (5°, very upright)
- Thicker trunk and branches (1.1x)
- 12 growth flushes (more mature)
- **Use for:** Hero trees, focal points, ancient specimens

Each variation also uses a different random seed, ensuring unique branch patterns.

## Export Formats

### FBX (Legacy)
- `output/unreal_assets/FBX/*.fbx`
- For traditional Static Mesh import
- Includes skeleton for potential animation
- Compatible with all UE versions

### USD (Nanite)
- `output/unreal_assets/USD/*.usda`
- For Nanite-enabled assets (UE 5.7+)
- Better for high-polygon tree meshes
- Supports Nanite Assemblies for optimal performance

## Importing to Unreal Engine

### Method 1: FBX Import (All UE Versions)

1. **Import FBX files:**
   - Drag FBX files into Content Browser
   - Import as Static Mesh
   - Enable "Generate Collision" for foliage collision

2. **Create Foliage Types:**
   - Right-click each mesh → Create Foliage Type
   - Set LOD settings
   - Configure cull distance (recommend: 20000)

3. **Setup Foliage Mode:**
   - Window → Foliage
   - Add all 3 variations per species
   - Set density/scatter settings
   - Use rotation randomization

### Method 2: USD Import (UE 5.7+)

1. **Import USD files:**
   - Enable USD Importer plugin
   - Drag USDA files into Content Browser
   - Choose "Import as Static Mesh" with Nanite enabled

2. **Create Nanite Assembly (Optional):**
   - For best performance with thousands of trees
   - Use USD assembly workflow
   - Reference documentation in `import_metadata.json`

### Method 3: PCG (Procedural Content Generation)

Use the metadata JSON files to drive PCG scatter attributes:

```json
{
  "min_spacing": 3.0,
  "max_spacing": 8.0,
  "scale_min": 0.8,
  "scale_max": 1.2,
  "rotation_random": true
}
```

1. Create PCG Volume
2. Add PCG Surface Sampler
3. Add Static Mesh Spawner
4. Use 3 variations with weighted random selection
5. Apply scale/rotation variation from metadata

## Fixed Issues

### ✅ Armature Parenting Warning
**Fixed:** Removed parent relationship between mesh and armature. Now uses modifier-only approach, which FBX exporter supports properly.

**Before:** "Sorry, ARMATURE parenting type is not supported"
**After:** Clean export with no warnings

### ✅ Limited Variation
**Fixed:** Added proper procedural variation with:
- Different random seeds per variation
- Varied growth parameters (lean, density, thickness)
- Different growth stages
- Documented variation types in metadata

## Recommended Workflow

1. **Export with 3-5 variations per species**
   ```bash
   ./.conda/python.exe src/growpy/cli/export_for_unreal.py forest.csv --variations 5
   ```

2. **Import all variations to Unreal**

3. **Create Foliage Types for each variation**

4. **Use PCG or Foliage Mode to scatter**
   - Random selection from variations
   - Scale variation: 0.8-1.2x
   - Full rotation randomization
   - Align to terrain normal

5. **Optimize with Nanite (UE 5.7+)**
   - Use USD import for Nanite
   - Create Nanite Assemblies for LOD-free rendering
   - Handle 100,000+ tree instances easily

## Files Generated

```
output/unreal_assets/
├── FBX/                       # Legacy FBX meshes
│   ├── Oak_var1.fbx           # Standard
│   ├── Oak_var2.fbx           # Leaning dense
│   └── Oak_var3.fbx           # Upright thick
├── USD/                       # Nanite USD meshes
│   ├── Oak_var1.usda
│   ├── Oak_var2.usda
│   └── Oak_var3.usda
├── Metadata/                  # Import configuration
│   └── Oak_metadata.json      # Per-species settings
└── import_metadata.json       # Master import guide
```

## Performance Tips

- **Nanite (UE 5.7+):** Use USD import for automatic Nanite support
- **LODs:** Generate LODs in Unreal (FBX) or use Nanite (USD)
- **Instancing:** Use Hierarchical Instanced Static Meshes (HISM) for non-Nanite
- **Culling:** Set appropriate cull distances (10000-20000 units)
- **Collision:** Use simple collision proxies, not full mesh collision

## Common Issues

**Q: Trees look identical**
A: Make sure you imported all 3 variations and are using random selection

**Q: Performance is poor**
A: Use Nanite (USD) or enable LODs and instancing (FBX)

**Q: Skeleton not working**
A: The skeleton is for potential wind animation. If not needed, you can skip skeleton export with `export_skeleton_separately=False`

**Q: Want more variation**
A: Export with more variations: `--variations 5` or `--variations 10`