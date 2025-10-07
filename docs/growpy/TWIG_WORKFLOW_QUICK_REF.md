# Quick Reference - Twig Workflow

## TL;DR

**YES - Convert twigs to USD first!**

```bash
# Step 1: Convert twigs (ONE TIME)
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Step 2: Generate trees (uses USD twigs automatically)
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs
```

## Why Convert Twigs?

The code looks for twig files in this order:

1. ✅ **`.usda`** ← Best (created by convert_twigs.py)
2. ✅ **`.usd`** ← Also good
3. ⚠️ **`.fbx`** ← Fallback (original Grove files)

### With USD Twigs (Recommended)

```
European_Beech_NaniteAssembly.usda
├── references → European_Beech_tree_only.usda
└── TwigInstances (PointInstancer)
    └── TwigPrototypes
        ├── apical → betulaceae_european_beech_apical.usda  ✅
        └── lateral → betulaceae_european_beech_lateral.usda ✅
```

**Benefits:**

- Native USD-to-USD references
- Better material preservation
- Smaller file sizes
- Optimal PointInstancer performance
- No conversion overhead in Unreal

### Without USD Twigs (Fallback)

```
European_Beech_NaniteAssembly.usda
├── references → European_Beech_tree_only.usda
└── TwigInstances (PointInstancer)
    └── TwigPrototypes
        ├── apical → Betulaceae_European_Beech_Twig_Long.fbx  ⚠️
        └── lateral → Betulaceae_European_Beech_Twig_Short.fbx ⚠️
```

**Downsides:**

- FBX→USD conversion at export time
- Materials may not translate perfectly
- Slightly larger files
- Less optimal for instancing

## Convert Twigs Command

```bash
# All twigs with Nanite Assemblies (default)
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# Specific species only
python src/growpy/cli/convert_twigs.py data/assets/twigs/Betulaceae_Downy_birch --formats usda

# Multiple formats with Nanite Assemblies
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats fbx usda

# Without Nanite Assemblies (standard USD only)
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda --no-nanite-assembly
```

## What Gets Created

**Before (only .blend files):**

```
data/assets/twigs/Betulaceae_Downy_birch/
├── Betulaceae_Downy_birch_Twig_Short.blend
└── Betulaceae_Downy_birch_Twig_Long.blend
```

**After (with USD files):**

```
**After (with USD files):**
```

data/assets/twigs/Betulaceae_Downy_birch/
├── Betulaceae_Downy_birch_Twig_Short.blend
├── betulaceae_downy_birch_lateral.usda                ← Standard USD ✓
├── betulaceae_downy_birch_lateral_NaniteAssembly.usda ← Nanite Assembly ✓
├── Betulaceae_Downy_birch_Twig_Long.blend
├── betulaceae_downy_birch_apical.usda                 ← Standard USD ✓
├── betulaceae_downy_birch_apical_NaniteAssembly.usda  ← Nanite Assembly ✓
└── twig_manifest.json                                  ← NEW ✓

```
```

## Twig Name Standardization

The converter creates standardized names:

| Original Grove Name | Standardized Name |
|---------------------|-------------------|
| `BeechApicalTwig.blend` | `beech_apical.usda` |
| `BeechLongTwig.blend` | `beech_apical.usda` |
| `BeechLateralTwig.blend` | `beech_lateral.usda` |
| `BeechShortTwig.blend` | `beech_lateral.usda` |
| `BeechUpwardTwig.blend` | `beech_upward.usda` |
| `BeechDeadTwig.blend` | `beech_dead.usda` |
| `BeechVariationCLateralTwig.blend` | `beech_lateral_var_c.usda` |

## Code Reference

From `src/growpy/io/blender_export.py` (lines 1730-1755):

```python
def get_twig_usd_map_for_species(species_name, config):
    """Get mapping of twig types to USD file paths."""
    
    # Map Grove attribute names to twig file types
    type_mapping = {
        "twig_long": ["apical", "long", "end", "terminal"],
        "twig_short": ["lateral", "short", "side"],
        "twig_upward": ["upward", "up"],
        "twig_dead": ["dead", "fall", "winter"],
    }
    
    for grove_type, keywords in type_mapping.items():
        for twig_type, twig_paths in twig_files_by_type.items():
            if any(kw in twig_type.lower() for kw in keywords):
                # Try USDA first, then USD, then FBX
                for ext in [".usda", ".usd", ".fbx"]:  # ← Order matters!
                    usd_file = twig_file.with_suffix(ext)
                    if usd_file.exists():
                        twig_usd_map[grove_type] = usd_file
                        break
```

## Integration Test

```bash
# Verify twigs are converted
ls data/assets/twigs/*/*.usda

# Should see files like:
# betulaceae_downy_birch_apical.usda
# betulaceae_downy_birch_lateral.usda
# etc.

# Generate test tree to verify twig integration
python src/growpy/cli/generate_species_library.py \
  --formats usda \
  --include-twigs \
  --output-dir data/output/test

# Check that Nanite Assembly references USD twigs
grep -A 20 "TwigPrototypes" data/output/test/USD/*_NaniteAssembly.usda
```

## FAQ

### Q: Can I skip converting twigs?

**A:** Yes, but FBX twigs will be used as fallback. USD twigs are strongly recommended for best results.

### Q: Do I need to convert twigs every time?

**A:** No, only once (or when twigs are updated). The USD files persist.

### Q: What if convert_twigs.py fails?

**A:** Trees will still export using FBX twigs. Check:

- bpy module installed: `conda install -c conda-forge bpy`
- USD Python installed: `pip install usd-core`

### Q: Can I use both FBX and USD twigs?

**A:** Yes! Export with `--formats fbx usda` to create both. USD will be used preferentially.

### Q: Do twigs need to be in a specific location?

**A:** Yes, in the same directory as the tree USD files. The Nanite Assembly references them by relative path.

## Summary

✅ **DO THIS:**

```bash
# 1. Convert twigs once
python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

# 2. Generate trees (uses USD twigs automatically)
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs
```

❌ **NOT THIS:**

```bash
# Skip twig conversion - will work but use FBX fallback
python src/growpy/cli/generate_species_library.py --formats usda --include-twigs
```

---

**See also:**

- Complete workflow: `docs/growpy/COMPLETE_WORKFLOW.md`
- Nanite Assembly guide: `docs/growpy/NANITE_ASSEMBLY_GUIDE.md`
