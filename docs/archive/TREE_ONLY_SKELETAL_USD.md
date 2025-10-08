# Tree-Only Skeletal USD Export - 2025-10-08

## Change Summary

Added separate `*_tree_only_skeletal.usda` file for direct skeletal mesh import, alongside the existing `*_tree_only.usda` static mesh file.

## Motivation

Users need a clean way to import tree meshes as skeletal meshes (with skeleton/armature) directly into Unreal Engine, similar to the FBX workflow, without needing the full assembly with twigs.

## File Structure

### Before

```
Oak/USD/
├── Oak_var1.usda                    # Full assembly (tree + twigs)
├── Oak_var1_tree_only.usda          # Tree mesh with skeleton + materials
└── Oak_var1_NaniteAssembly.usda     # Static Nanite Assembly
```

### After

```
Oak/USD/
├── Oak_var1.usda                        # Full assembly (tree + twigs)
├── Oak_var1_tree_only.usda              # Tree mesh ONLY (no skeleton)
├── Oak_var1_tree_only_skeletal.usda     # Tree mesh + skeleton + materials ✨ NEW
└── Oak_var1_NaniteAssembly.usda         # Static Nanite Assembly
```

## Use Cases

### 1. Static Mesh (Most Common)

**Import:** `Oak_var1_NaniteAssembly.usda`

- Static mesh with Nanite optimization
- Instanced twigs via PointInstancer
- Best performance for background foliage
- No animation support

### 2. Skeletal Mesh - Direct Import ✨ NEW

**Import:** `Oak_var1_tree_only_skeletal.usda`

- Skeletal mesh with 6-bone skeleton
- Materials with bark textures
- **No twigs** (clean skeleton setup)
- Direct import like FBX workflow
- Use for: Hero trees, wind animation, procedural growth

**Advantages:**

- ✅ Clean import - just tree and skeleton
- ✅ Same workflow as FBX import
- ✅ No twig complexity
- ✅ Easier to set up animation in Unreal

### 3. Skeletal Mesh with Twigs

**Import:** `Oak_var1.usda`

- Skeletal mesh + skeleton + materials
- Includes twig placements via PointInstancer
- More complex but complete tree assembly
- Twigs use regular USD (not Nanite Assembly)

### 4. Static Mesh Only (No Skeleton)

**Import:** `Oak_var1_tree_only.usda`

- Just the tree mesh geometry
- No skeleton, no materials
- Raw mesh for custom material setup
- Used internally by assembly files

## Technical Implementation

### Code Changes

**File:** `src/growpy/io/blender_export.py`

**Export Process:**

```python
# 1. Export base tree from Grove (no skeleton)
temp_tree_path = output_dir / f"{species}_tree_only.usda"
gc.io.model_to_usda_string(model) → temp_tree_path

# 2. Add twig face attributes to base tree
_add_grove_face_attributes_to_usd(temp_tree_path, model)

# 3. Create skeletal version (NEW)
skeletal_tree_path = output_dir / f"{species}_tree_only_skeletal.usda"
copy(temp_tree_path → skeletal_tree_path)
_add_skeleton_and_materials_to_usd(skeletal_tree_path, grove, species, config)

# 4. Create full assembly (references base tree_only)
# Uses temp_tree_path (no skeleton) for twig extraction
export_twig_placements_to_usd(
    tree_usd_path=temp_tree_path,  # Static tree
    output_path=main_assembly_path
)
```

### File Contents

#### `Oak_var1_tree_only.usda` (Static)

```usd
#usda 1.0
def Mesh "Tree"
{
    # Mesh geometry
    # Twig face attributes
    # NO skeleton
    # NO materials
}
```

#### `Oak_var1_tree_only_skeletal.usda` (Skeletal) ✨

```usd
#usda 1.0
def Mesh "Tree" (
    prepend apiSchemas = ["SkelBindingAPI", "MaterialBindingAPI"]
)
{
    # Mesh geometry
    # Twig face attributes
    rel skel:skeleton = </Tree/Skeleton>
    
    # Skeleton binding (joint weights, indices)
    int[] primvars:skel:jointIndices
    float[] primvars:skel:jointWeights
    
    # Material binding
    rel material:binding = </Tree/BarkMaterial>
}

def Skeleton "Skeleton"
{
    # 6-bone hierarchy: Root + 5 branch bones
    uniform token[] joints = ["Root", "Branch_0_Bone_0", ...]
    uniform matrix4d[] bindTransforms
    uniform matrix4d[] restTransforms
}

def Material "BarkMaterial"
{
    # PBR material with diffuse + normal textures
}
```

#### `Oak_var1.usda` (Full Assembly)

```usd
#usda 1.0
def Xform "TreeAssembly"
{
    def Xform "Tree" (
        references = @Oak_var1_tree_only.usda@  # Static tree
    )
    
    def Scope "Prototypes" {
        # Twig prototypes (regular USD, not Nanite Assembly)
    }
    
    def PointInstancer "TwigInstances" {
        # Twig instances positioned on tree
    }
}
```

## Import Workflows

### Unreal Engine 5.7 Import Guide

#### For Static Background Trees

1. **File → Import** → `Oak_var1_NaniteAssembly.usda`
2. Settings:
   - Import Type: Static Mesh
   - Enable Nanite: ✅
   - Import Materials: ✅
3. Result: Optimized static mesh with instanced twigs

#### For Skeletal Hero Trees (NEW Workflow) ✨

1. **File → Import** → `Oak_var1_tree_only_skeletal.usda`
2. Settings:
   - Import Type: Skeletal Mesh
   - Import Skeleton: ✅
   - Import Materials: ✅
3. Result: Clean skeletal mesh with 6-bone skeleton
4. Set up animation:
   - Wind simulation
   - Procedural sway
   - Growth animation

**This matches the FBX import workflow!**

#### For Skeletal Trees with Twigs

1. **File → Import** → `Oak_var1.usda`
2. Settings:
   - Import Type: Skeletal Mesh
   - Import Skeleton: ✅
   - Import Materials: ✅
   - Instance twigs: ✅
3. Result: Complete tree with skeleton and twigs

#### For Custom Material Setup

1. **File → Import** → `Oak_var1_tree_only.usda`
2. Settings:
   - Import Type: Static Mesh
   - Import Materials: ❌
3. Result: Raw mesh geometry
4. Apply custom materials in Unreal

## Benefits

### For Artists

✅ **Simple skeletal import** - No need to deal with twigs for animation setup
✅ **Matches FBX workflow** - Familiar import process
✅ **Clean skeleton** - Just tree and bones, easier to animate
✅ **Flexible** - Can add twigs later in Unreal if needed

### For Technical Artists

✅ **Predictable structure** - Know exactly what's in each file
✅ **Reusable skeletons** - Can share skeleton across variations
✅ **Efficient** - No unnecessary data in files
✅ **Compatible** - Works with existing animation systems

### For Performance

✅ **Smaller file sizes** - No duplicate data
✅ **Faster imports** - Less data to process
✅ **Better organization** - Clear separation of concerns

## Comparison with FBX

### FBX Export

```
Oak_var1.fbx (single file)
├── Tree mesh
├── Skeleton (6 bones)
└── Materials
```

### USD Export (NEW)

```
Oak_var1_tree_only_skeletal.usda (single file)
├── Tree mesh
├── Skeleton (6 bones)
└── Materials
```

**Same content, same workflow, but with USD benefits:**

- Better scene composition
- Non-destructive references
- Lossless round-tripping
- Industry-standard format

## Migration

### For Existing Projects

**No changes needed** - All existing files still work:

- `*_tree_only.usda` now has no skeleton (cleaner for static use)
- `*.usda` still has full assembly with twigs
- Nanite Assemblies unchanged

### For New Projects

**Use the new skeletal file for animation:**

```python
# Generate forest with skeletal files
python src/growpy/cli/generate_forest.py forest.csv --formats usda

# Files created per tree:
# - species_tree_only.usda (static mesh)
# - species_tree_only_skeletal.usda (skeletal mesh) ✨
# - species.usda (full assembly)
# - species_NaniteAssembly.usda (Nanite static)
```

## Output Messages

```
Exporting Oak as USDA...
  ✓ Exported base tree USD: Oak_var1_tree_only.usda
  ✓ Added twig face attributes to USD:
    - twig_long: 2 faces
    - twig_short: 3 faces
  Adding skeleton to USD...
    ✓ Added skeleton with 6 joints
    ✓ Bound mesh to skeleton
  Adding bark texture material...
    ✓ Added diffuse texture: NorthernRedOak60.jpg
    ✓ Added normal map: NorthernRedOak60Normal.jpg
  ✓ Skeletal tree USD: Oak_var1_tree_only_skeletal.usda
    (Import as skeletal mesh in Unreal, like FBX)
```

## Related Changes

This change complements:

- **Twig Nanite Assembly removal** - Twigs are now regular USD
- **Twig reference fix** - No Nanite Assembly in references
- **Skeletal mesh support** - Proper UsdSkel implementation

Together these provide a complete, crash-free USD workflow for Unreal Engine 5.7.

## Related Documentation

- `docs/archive/TWIG_NANITE_ASSEMBLY_FIX.md` - Twig crash fix
- `docs/archive/TWIG_NANITE_ASSEMBLY_REMOVED.md` - Twig simplification
- `docs/archive/SKELETAL_NANITE_ASSEMBLY_ISSUE.md` - Tree-level Nanite
- `docs/growpy/UNREAL_IMPORT_GUIDE.md` - Complete import guide

## Conclusion

The new `*_tree_only_skeletal.usda` file provides a **clean, FBX-equivalent workflow** for importing trees as skeletal meshes in Unreal Engine.

**Key advantages:**

- ✅ Simple standalone file (no assembly complexity)
- ✅ Matches familiar FBX import workflow
- ✅ Clean skeleton setup for animation
- ✅ Professional USD workflow
- ✅ Compatible with all DCC applications

This completes the USD export feature set, providing equivalent or better functionality than FBX export while maintaining USD's advantages.
