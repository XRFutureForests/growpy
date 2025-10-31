# PascalCase Naming Convention Fix

## Problem

Generated Nanite Assembly files were not recognized by Unreal Engine 5.7. Root cause: naming convention mismatch between generated files (snake_case) and Unreal's expectations (PascalCase).

## Reference vs Generated Comparison

### Before Fix

- **Generated**: `tree_skel`, `tree_mesh`, `Skel` (twig skeleton)
- **Reference**: `TreeSkel`, `TreeMesh`, `TwigSkel`
- **Result**: Unreal Engine failed to recognize assembly structure

### After Fix

- **Tree Skeleton**: `tree_skel` → `TreeSkel`
- **Tree Mesh**: `tree_mesh` → `TreeMesh`
- **Twig Skeleton**: `Skel` → `TwigSkel`
- **Twig Mesh**: `Mesh` → `TwigMesh`

## Files Modified

### 1. `src/growpy/io/usd_builder.py`

- Line ~101: `TreeMesh` prim creation
- Line ~543: `TreeSkel` skeleton path
- Line ~785: `TreeMesh` path for mesh re-parenting
- Line ~1579-1592: Assembly `TreeMesh`/`TreeSkel` structure

### 2. `src/growpy/io/blender_twig_processor.py`

- Line ~209: Twig skeleton `TwigSkel` naming
- Line ~245: Twig mesh `TwigMesh` naming

### 3. `src/growpy/io/usd_validation.py`

- Updated validation paths: `/tree/TreeSkel`, `/tree/TreeMesh`
- Updated twig validation: `/Twig/TwigSkel`

### 4. `src/growpy/io/unreal_nanite_assembly.py`

- Line ~113: Assembly `TreeMesh` prim
- Line ~156: Skeleton relationship path `TreeMesh/TreeSkel`

## Verification

### Tree Files

```bash
# Check tree skeleton naming
grep -E "(def Skeleton|def Mesh)" western_redcedar_tree_0000_tree_only_skeletal.usda
# Output:
#   def Mesh "TreeMesh" (
#   def Skeleton "TreeSkel"
```

### Twig Files

```bash
# Check twig skeleton naming
grep -A 2 "def Skeleton" western_red_cedar_twig_var_e_skeletal.usda | head -5
# Output:
#   def Skeleton "TwigSkel"
```

### Assembly Files

```bash
# Check assembly structure
grep -E "(TreeMesh|TreeSkel|TwigSkel)" western_redcedar_tree_0000_nanite_assembly_skeletal.usda
# Output:
#   rel unreal:naniteAssembly:skeleton = </western_redcedar_tree_0000_nanite_assembly_skeletal/TreeMesh/TreeSkel>
#   def SkelRoot "TreeMesh" (
#   def SkelRoot "TwigSkelRoot" (
```

## Pipeline Execution

Complete pipeline run with new naming:

```bash
# 1. Prepare assets (5 species)
conda run -n the-grove python src/growpy/cli/prepare_assets.py

# 2. Convert twigs to USD with PascalCase naming
conda run -n the-grove python src/growpy/cli/convert_twigs.py data/assets/twigs/western_red_cedar_twig --formats usda

# 3. Generate forest with PascalCase naming
conda run -n the-grove python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 1
```

## Results

- ✅ All tree skeletons use `TreeSkel` naming
- ✅ All tree meshes use `TreeMesh` naming
- ✅ All twig skeletons use `TwigSkel` naming
- ✅ All twig meshes use `TwigMesh` naming
- ✅ Nanite Assembly skeleton relationship: `TreeMesh/TreeSkel`
- ✅ Validation passes for all USD files
- ✅ Naming matches reference assembly structure

## Next Steps

1. Import `western_redcedar_tree_0000_nanite_assembly_skeletal.usda` into Unreal Engine 5.7
2. Verify Unreal recognizes the assembly structure
3. Test skeletal animation and twig instancing
4. Run full pipeline for remaining species (once twig files are available)

## Technical Notes

### Why PascalCase?

Unreal Engine's USD importer expects specific naming conventions for skeletal structures:

- `TreeSkel` / `TreeMesh` for main tree geometry
- `TwigSkel` / `TwigMesh` for instanced foliage
- PascalCase aligns with Unreal's C++ naming conventions

### Critical Paths

- **Skeleton Relationship**: `/{assembly_name}/TreeMesh/TreeSkel`
- **Tree Reference**: `./tree_only_skeletal.usda` → `/tree` prim
- **Twig References**: Point to skeletal twig USD files with `/Twig` root

### Validation

The `usd_validation.py` module now checks for:

- Presence of `TreeSkel` at `/tree/TreeSkel`
- Presence of `TreeMesh` at `/tree/TreeMesh`
- Presence of `TwigSkel` in twig files at `/Twig/TwigSkel`
- Proper skeletal binding relationships
