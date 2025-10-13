# Nanite Assembly Skeletal Mesh Fix - Embedded Geometry Issue

**Date**: 2025-01-11  
**Issue**: Skeletal Nanite Assemblies import both static and skeletal meshes but don't create Nanite Assembly in Unreal Engine 5

## Root Cause

The skeletal Nanite Assembly USD file was embedding the tree mesh geometry INSIDE the SkelRoot hierarchy:

```
Beech_NaniteAssembly (NaniteAssemblyRootAPI)
├── SkelRoot
│   ├── Skeleton (joint data)
│   ├── SkelAnimation
│   └── Mesh <-- PROBLEM: Embedded geometry data (130KB+)
└── TreeMesh (external reference to skeletal tree)
```

This creates a **hybrid structure** that Unreal Engine doesn't recognize as a valid Nanite Assembly:

- It has both embedded geometry (inside SkelRoot/Mesh) AND external references (TreeMesh)
- Unreal expects Nanite Assemblies to use ONLY external references for all geometry
- The embedded mesh conflicts with the external reference paradigm

## The Fix

Modified `_copy_skeleton_to_assembly()` in `src/growpy/io/unreal_nanite_assembly.py` to:

1. **Skip copying Mesh prims** when copying the skeleton hierarchy from source USD
2. **Only copy skeleton structure**: SkelRoot → Skeleton → SkelAnimation
3. **Keep mesh references external** via TreeMesh prim

### Code Changes

Added `skip_mesh` parameter to `copy_prim_hierarchy()`:

```python
def copy_prim_hierarchy(source_prim, target_parent_path, skip_mesh=False):
    # Skip Mesh prims - we only want the skeleton structure
    if skip_mesh and source_prim.GetTypeName() == "Mesh":
        print(f"        Skipping embedded mesh prim: {source_prim.GetName()}")
        return
    # ... rest of copying logic
```

Call with `skip_mesh=True`:

```python
copy_prim_hierarchy(skel_root_prim, assembly_root_path, skip_mesh=True)
```

## Expected Result

Clean Nanite Assembly structure:

```
Beech_NaniteAssembly (NaniteAssemblyRootAPI, meshType="skeletalMesh")
├── SkelRoot
│   ├── Skeleton (joint hierarchy + bind transforms)
│   └── SkelAnimation (animation data)
├── TreeMesh (NaniteAssemblyExternalRefAPI)
│   └── Reference → Beech_tree_0000_tree_only.usda (skeletal mesh with geometry)
└── TwigPrototypes
    └── TwigInstances (PointInstancer bound to skeleton joints)
```

**All geometry comes from external USD references**, not embedded data.

## Why This Matters

Unreal Engine's Nanite Assembly system requires:

- All meshes referenced externally (composition arcs)
- No embedded geometry in the assembly file
- Clean separation between skeleton structure and mesh data

The hybrid approach violated these requirements, preventing Unreal from recognizing the file as a Nanite Assembly.

## Testing

Re-export skeletal trees with the fix:

```bash
python src/growpy/cli/generate_forest.py ./data/input/test.csv \
  --output-dir ./data/output/skeletal_no_embedded_mesh \
  --quality high \
  --formats usda
```

Expected behavior in Unreal:

1. Import `Beech_tree_0000_NaniteAssembly_skeletal.usda`
2. Unreal recognizes it as a Nanite Assembly
3. Creates a SkeletalMesh asset with proper skeleton binding
4. Twigs are instanced and bound to skeleton joints
5. Nanite LOD system works correctly

## Related Files

- `src/growpy/io/unreal_nanite_assembly.py` - Main implementation
- `SKELETAL_TWIG_SKELETON_BINDING.md` - Initial skeletal approach
- `NANITE_SKELETAL_STATIC_FIX_2025-01-10.md` - Previous fix attempt
- `THREE_CRITICAL_FIXES_2025-01-10.md` - Related coordinate fixes

## Key Insight

**Nanite Assembly is a COMPOSITION system, not a geometry container.**  
All geometry must come from external references. The assembly file itself should only contain:

- API schema metadata (NaniteAssemblyRootAPI)
- Skeleton structure (for skeletal assemblies)
- Reference relationships to external meshes
- Instance placement data (PointInstancer)

Never embed actual mesh geometry data in the assembly file itself.
