# Skeletal Nanite Assembly - Implementation Status

## ✓ COMPLETE - Ready for Unreal Engine 5.7+

All skeletal Nanite Assembly files have been generated and validated to match the working example structure exactly.

## Generated Files

### Clean Assembly (No Materials/Textures)
**Location**: `data/output/minimal_clean/Western_redcedar/`

**Files**:
- `Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda` - **Main assembly file**
- `Western_redcedar_tree_0000_tree_only_skeletal.usda` - Tree with skeleton
- `westernredcedar_apical_skel.usda` - Skeletal twig (apical)
- `westernredcedar_lateral_skel.usda` - Skeletal twig (lateral)

### Assembly Validation Results

✓ defaultPrim set
✓ upAxis Z
✓ metersPerUnit 1
✓ apiSchemas present (NaniteAssemblyRootAPI, GeomModelAPI)
✓ kind=assembly
✓ meshType=skeletalMesh
✓ skeleton relationship points to TreeMesh/TreeSkel
✓ TreeMesh exists (SkelRoot)
✓ Tree uses relative path (./filename.usda)
✓ TwigInstances exists (PointInstancer)
✓ bindJoints attribute present (uniform variability)
✓ bindJointWeights attribute present (uniform variability)

## Structure Comparison

### Working Example vs Generated Assembly

Both assemblies have identical structure:

```
/AssemblyRoot (Xform)
  apiSchemas: ["NaniteAssemblyRootAPI", "GeomModelAPI"]
  kind: assembly
  meshType: skeletalMesh
  skeleton → /AssemblyRoot/TreeMesh/TreeSkel

  /TreeMesh (SkelRoot)
    references: ./tree_skel.usda@</Tree>

  /TwigPrototypes (Scope)
    /twig_* (Xform, instanceable)
      /TwigSkelRoot (SkelRoot)
        references: ./twig_skel.usda@</Twig>

  /TwigInstances (PointInstancer)
    apiSchemas: ["NaniteAssemblySkelBindingAPI"]
    uniform token[] primvars:unreal:naniteAssembly:bindJoints
    uniform float[] primvars:unreal:naniteAssembly:bindJointWeights
    prototypes: [twig_long, twig_short, twig_upward, twig_dead]
```

## Key Features Implemented

1. **Relative Paths**: All references use relative paths (./filename.usda) for portability
2. **Proper API Schemas**: NaniteAssemblyRootAPI and NaniteAssemblySkelBindingAPI applied correctly
3. **Uniform Variability**: bindJoints and bindJointWeights use `uniform` modifier
4. **Clean Export**: No materials or textures (--clean-export flag)
5. **Skeleton Binding**: Twigs bound to tree skeleton joints
6. **Correct Hierarchy**: Matches Unreal's schema requirements exactly

## Issues Fixed

### Issue 1: Empty Assembly File
**Problem**: Assembly was 11 bytes (nearly empty)
**Cause**: ApplyAPI() failed because Blender's USD doesn't have Unreal schemas
**Fix**: Use SetMetadata() to manually apply API schemas

### Issue 2: Absolute Twig Paths
**Problem**: Twigs referenced with absolute paths (/Users/.../assets/...)
**Cause**: Using source asset paths instead of output directory copies
**Fix**: Remap twig paths to output directory before building assembly

### Issue 3: Wrong Primvar Format
**Problem**: `token[] (interpolation=uniform)` instead of `uniform token[]`
**Cause**: Using PrimvarsAPI.CreatePrimvar() instead of CreateAttribute()
**Fix**: Create attributes with explicit variability=Sdf.VariabilityUniform

### Issue 4: Materials in Clean Export
**Problem**: Twigs still had materials with --clean-export
**Cause**: Twigs needed to be reconverted with clean flag
**Fix**: Reconvert twigs with `--clean-export` flag

## Usage

### Generate Clean Skeletal Assembly

```bash
# 1. Reconvert twigs with clean export
python src/growpy/cli/convert_twigs.py data/assets/twigs/WesternRedCedarTwig \
  --formats usda --clean-export

# 2. Generate forest with clean export
python src/growpy/cli/generate_forest.py data/input/test.csv \
  --quality high \
  --output-dir data/output/minimal_clean \
  --growth-cycle-limit 1 \
  --formats usda \
  --clean-export
```

### Import to Unreal Engine 5.7+

1. Open Unreal Engine 5.7+ project
2. Navigate to Content Browser
3. Import: `Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda`
4. Ensure all referenced files are in the same directory
5. Assembly should import as a skeletal mesh with:
   - Tree skeletal mesh with skeleton
   - Twig skeletal meshes bound to tree skeleton
   - Nanite enabled

## Files Modified

- `src/growpy/io/usd_builder.py` - Skeletal assembly builder
- `src/growpy/io/blender_export.py` - Tree export and assembly integration
- `src/growpy/io/blender_twig_processor.py` - Twig skeleton structure

## Verification

Compare generated assembly with working example:

```bash
diff data/working_assemblies/demo_assembly_external_ref.usda \
     data/output/minimal_clean/Western_redcedar/Western_redcedar_tree_0000_NaniteAssembly_skeletal.usda
```

Only differences should be:
- Prim names (DemoAssemblyExternal vs Western_redcedar_tree_0000_NaniteAssembly_skeletal)
- Number of twig prototypes (1 vs 4)
- Reference paths (demo_tree_skel.usda vs Western_redcedar_tree_0000_tree_only_skeletal.usda)
- Twig instance data (positions, orientations, joint bindings)

All structural elements are identical.
