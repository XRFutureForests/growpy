# Quick Fix for Skeletal Nanite Assembly

**Date**: 2025-01-24
**Issue**: Skeletal Nanite Assemblies not working in Unreal Engine 5.7+
**Solution**: Based on <https://www.youtube.com/watch?v=b_jhGZ2jto8>

## TL;DR

Twigs MUST be skeletal meshes (not static) for skeletal Nanite Assemblies. Your code already creates them, just need to clean and regenerate.

## Quick Fix Steps

```bash
# 1. Delete old assets (REQUIRED)
rm -rf ./data/assets/twigs
rm -rf ./data/output/forest

# 2. Regenerate everything
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/generate_forest.py data/input/test.csv \
  --quality high \
  --growth-cycle-limit 5

# 3. Verify skeletal twigs were created
ls data/assets/twigs/*/*.usda | grep _skel
# Should see files like: downy_birch_apical_skel.usda

# 4. Check assembly references skeletal twigs
grep "twig.*_skel.usda" data/output/forest/*/*_NaniteAssembly.usda
# Should see: references = @./some_twig_skel.usda@
```

## What Changed

**Fixed in code (you don't need to change anything)**:

1. `bindJoints` now uses joint names like `"joint_50"` (not paths)
2. Added validation to warn if static twigs used in skeletal assembly
3. Better logging to debug joint bindings

**What you need to do**:

1. Delete old assets (step 1 above)
2. Re-run pipeline (steps 2-3 above)
3. Verify output (step 4 above)

## Unreal Engine Settings

**Required** (add to `DefaultEngine.ini`):

```ini
[/Script/Engine.RendererSettings]
r.Nanite.AllowAssemblies=1

[/Script/InterchangeCore.InterchangeManager]
InterchangeFeatureFlags.ImportUSD=0
```

**Plugins**:

- ✅ Enable: USD Core, USD Importer
- ❌ Disable: USD Interchange

## Verification

After import in Unreal, check:

- [ ] Assembly shows instance count (not separate meshes)
- [ ] Tree imports as `SK_` prefix (skeletal)
- [ ] Twigs import as `SK_` prefix (skeletal)
- [ ] Skeleton visible with joints

## Troubleshooting

**Twigs not appearing?**

```bash
# Verify skeletal twigs exist
find data/assets/twigs -name "*_skel.usda"
# If empty, regenerate with step 2 above
```

**Still using static twigs?**

```bash
# Check what the assembly references
grep "references.*twig" data/output/forest/*/*_NaniteAssembly.usda
# Look for _skel.usda in the output
```

**Want to understand why?**

- Read: `docs/SKELETAL_NANITE_ASSEMBLY_FIX.md` (full details)
- Watch: <https://www.youtube.com/watch?v=b_jhGZ2jto8> at timestamp 07:12

## Key Insight from Video

> "This took a long time to figure out that you needed like a skeletal mesh even for each leaf."
>
> - HullaBulla, 07:12

Each twig/leaf needs a root bone because Unreal's skeletal Nanite Assembly builder (`NaniteAssemblySkeletalMeshBuilder.AddAssemblyParts()`) requires `USkeletalMesh*` pointers. Static meshes are rejected.
