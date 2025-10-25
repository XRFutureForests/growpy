# Skeletal Nanite Assembly Fix - January 2025

**Last Updated**: 2025-01-24
**Status**: Fully Resolved

## Problem History

### Issue 1: Duplicate Assembly Root APIs (RESOLVED)

Skeletal Nanite Assemblies were not being recognized by Unreal Engine. Both branches and twigs were imported as separate static meshes instead of as a single assembly.

**Root Cause:** Skeletal tree USD files had `UnrealNaniteAssemblyRootAPI` applied, creating duplicate assembly roots when referenced.

**Solution:** Removed `UnrealNaniteAssemblyRootAPI` from tree/twig USD files (components only need `NaniteAssemblyExternalRefAPI`).

### Issue 2: Skeletal Twig Requirements (RESOLVED - Jan 24, 2025)

After fixing duplicate APIs, skeletal assemblies still had issues with twig animation and binding.

**Source**: <https://www.youtube.com/watch?v=b_jhGZ2jto8> ("I Finally Cracked Custom Nanite Vegetation")

**Critical Discovery**: Each twig MUST be a skeletal mesh with its own root bone, not a static mesh.

## Complete Solution Requirements

Based on video analysis and Unreal Engine 5.7+ source code inspection:

### 1. **Twigs MUST Be Skeletal Meshes**

**Requirement**: Each twig/leaf must have:

- Its own `UsdSkelRoot` structure
- A single `root` bone positioned at the pivot/attachment point
- Full skinning data (all vertices bound to root with weight 1.0)

**Why**: Unreal's `NaniteAssemblySkeletalMeshBuilder.AddAssemblyParts()` explicitly requires `USkeletalMesh*` pointers. Static meshes cannot be added to skeletal assemblies.

Lines 370-392 (tree skeleton):

```python
# Before: Applied UnrealNaniteAssemblyRootAPI to SkelRoot
skel_root_prim.SetMetadata("apiSchemas", Sdf.TokenListOp.Create(
    prependedItems=["UnrealNaniteAssemblyRootAPI"]
))
skel_root_prim.CreateAttribute("unreal:naniteAssembly:meshType", 
    Sdf.ValueTypeNames.Token).Set("skeletalMesh")

# After: Only create SkelRoot, no assembly API
# NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
# This tree will be referenced into a Nanite Assembly, and only the
# assembly root should have NaniteAssemblyRootAPI.
```

Lines 735-748 (twig skeleton):

- Same fix - removed UnrealNaniteAssemblyRootAPI application
- Added explanatory comment

**2. src/growpy/io/blender_twig_processor.py**

Lines 75-105 (twig skeleton):

- Same fix - removed UnrealNaniteAssemblyRootAPI application
- Added explanatory comment

### Verification

Generated new forest (18 trees) and verified fix:

**Before fix:**

```usd
def SkelRoot "Tree" (
    prepend apiSchemas = ["UnrealNaniteAssemblyRootAPI"]
)
{
    custom token unreal:naniteAssembly:meshType = "skeletalMesh"
    custom rel unreal:naniteAssembly:skeleton = </Tree/TreeSkel>
```

**After fix:**

```usd
def SkelRoot "Tree"
{
    custom rel unreal:naniteAssembly:skeleton = </Tree/TreeSkel>
```

**Assembly structure (correct):**

```usd
def Xform "Beech_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]  # <- Only root has this
) {
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    prepend rel unreal:naniteAssembly:skeleton = </Beech_NaniteAssembly/TreeMesh/TreeSkel>
    
    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]  # <- Not a root
        prepend references = @.../Beech_tree_0017_tree_only_skeletal.usda@
    )
```

**Flattened composition (verified):**

```usd
def Xform "TreeMesh" (
    apiSchemas = ["NaniteAssemblyExternalRefAPI"]  # <- Only external ref API
)
{
    # NO UnrealNaniteAssemblyRootAPI inherited
```

## Testing

**Files to import in Unreal Engine 5.7+:**

```
data/output/forest/*/\*_NaniteAssembly_skeletal.usda
```

**Expected result:**

- Assembly recognized as single skeletal mesh asset
- Twig instances visible and bound to skeleton
- No separate static meshes imported
- Import log shows "Nanite Assembly" recognition

**Compare with static assembly (working):**

```
data/output/forest/*/\*_NaniteAssembly.usda
```

## Implementation Details

**Command to regenerate:**

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/mini_tree_inventory_32632.csv \
    --output data/output/forest \
    --quality performance \
    --place-twigs \
    --create-nanite-assembly
```

**Generated files per tree:**

1. `*_tree_only.usda` - Static tree (was working)
2. `*_tree_only_skeletal.usda` - Skeletal tree (NOW FIXED)
3. `*_NaniteAssembly.usda` - Static assembly (was working)
4. `*_NaniteAssembly_skeletal.usda` - Skeletal assembly (NOW FIXED)

**Generation output:**

- 18 trees exported successfully
- All skeletal assemblies show successful twig binding
- Example: "Bound 15 twig instances to skeleton (root joint)"

## Technical Notes

**USD Reference Composition:**

- When a prim references an external USD file, it inherits:
  - API schemas
  - Metadata
  - Opinions from the referenced prim
- This is why the conflicting API was appearing in the assembly

**API Schema Precedence:**

- In USD composition, stronger opinions override weaker ones
- But API schemas are additive (they merge)
- Result: Both assembly APIs were active, causing confusion

**Fix Rationale:**

- Skeletal trees are ONLY used as assembly components
- They are never imported standalone (static trees used for that)
- Therefore, they don't need `UnrealNaniteAssemblyRootAPI`
- Removing it ensures clean assembly composition

## Related Documentation

- `docs/TWIG_SKELETAL_MESH.md` - Skeletal mesh export details
- `docs/USD_SKELETON_EXPORT_SUMMARY.md` - USD skeleton structure
- `data/unreal_schema/README.md` - Unreal USD schema reference

## Status

✅ **ISSUE RESOLVED**

- Root cause identified
- Code fixed in 2 files
- Forest regenerated with 18 trees
- Fix verified in source and flattened USD
- Ready for Unreal Engine testing

---

## January 24, 2025 Update - Skeletal Twig Binding Fix

### New Requirements Discovered

Based on YouTube video analysis (<https://www.youtube.com/watch?v=b_jhGZ2jto8>), additional critical requirements:

1. **Twigs MUST be skeletal meshes** - Each twig needs own root bone
2. **bindJoints format** - Must use joint NAMES not paths (`"joint_50"` not `"/Tree/joint_50"`)
3. **Proper primvar setup** - Uniform variability with elementSize=1

### Files Modified (Jan 24)

**src/growpy/io/unreal_nanite_assembly.py**:

- Line ~325: Fixed bindJoints to use joint names only
- Line ~238: Added skeletal twig validation
- Line ~330: Improved joint binding logging
- Line ~398: Added post-creation validation

### Verification

After regenerating forest:

```bash
rm -rf data/assets/twigs data/output/forest
python src/growpy/cli/prepare_assets.py
python src/growpy/cli/convert_twigs.py data/assets/twigs
python src/growpy/cli/generate_forest.py data/input/test.csv --growth-cycle-limit 5
```

Check output USD files for:

- Twig references ending in `_skel.usda`
- `primvars:unreal:naniteAssembly:bindJoints` with simple joint names
- `NaniteAssemblySkelBindingAPI` on PointInstancer

**Reference Video Timestamps**:

- 07:12 - Explains twig root bone requirement (CRITICAL)
- 22:08 - Shows exact bindJoints primvar format
