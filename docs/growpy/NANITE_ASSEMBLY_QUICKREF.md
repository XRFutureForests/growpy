# Nanite Assembly Quick Reference

## Critical Schema Requirements

### Static Mesh Assembly

```usd
def Xform "Species_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
)
{
    uniform token unreal:naniteAssembly:meshType = "staticMesh"
    
    def Xform "TreeMesh" (
        prepend apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        instanceable = true
        prepend references = @./tree_static.usda@
    )
    
    def PointInstancer "TwigInstances" { ... }
}
```

### Skeletal Mesh Assembly

```usd
def Xform "Species_NaniteAssembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    prepend references = @./tree_skeletal.usda@</Tree>
)
{
    uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
    custom rel unreal:naniteAssembly:skeleton
    prepend rel unreal:naniteAssembly:skeleton = </Species_NaniteAssembly/SkelRoot/Skeleton>
    
    def PointInstancer "TwigInstances" (
        prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]
    )
    {
        uniform token[] primvars:unreal:naniteAssembly:bindJoints = [...]
        int primvars:unreal:naniteAssembly:bindJoints:elementSize = 1
        uniform float[] primvars:unreal:naniteAssembly:bindJointWeights = [...]
    }
}
```

## Python Code

### Create Static Assembly

```python
from growpy.io import create_nanite_assembly_usd

create_nanite_assembly_usd(
    tree_usd_path=Path("tree_static.usda"),
    output_path=Path("Species_NaniteAssembly.usda"),
    species_name="Oak",
    twig_usd_paths={"long": Path("twig_long.usda")},
    use_skeletal_mesh=False,
)
```

### Create Skeletal Assembly

```python
create_nanite_assembly_usd(
    tree_usd_path=Path("tree_skeletal.usda"),  # Must have SkelRoot/Skeleton
    output_path=Path("Species_NaniteAssembly_skeletal.usda"),
    species_name="Oak",
    twig_usd_paths={"long": Path("twig_long.usda")},
    use_skeletal_mesh=True,
)
```

### Validate Assembly

```python
from growpy.io import validate_nanite_assembly

result = validate_nanite_assembly(Path("assembly.usda"))
if result["valid"]:
    print(f"✓ Valid {result['mesh_type']} assembly")
else:
    print("✗ Errors:")
    for error in result["errors"]:
        print(f"  - {error}")
```

## CLI Commands

```bash
# Validate single file
python src/growpy/cli/validate_nanite_assembly.py assembly.usda

# Validate directory
python src/growpy/cli/validate_nanite_assembly.py output/USD/
```

## Checklist

### Before Export

- [ ] Tree USD has proper structure (SkelRoot for skeletal)
- [ ] Twig USD files are static meshes (not skeletal)
- [ ] All USD references use relative paths
- [ ] Textures use relative paths

### After Export

- [ ] Run validation tool
- [ ] Check meshType is correct
- [ ] Verify skeleton relationship (skeletal only)
- [ ] Check prototype count
- [ ] Validate in text editor (check uniform token)

### Unreal Import

- [ ] Set Nanite triangle threshold (2000-5000)
- [ ] Enable "Import Skeletal Animations" (skeletal only)
- [ ] Verify Nanite is enabled on tree mesh
- [ ] Check twig instances work
- [ ] Test skeleton animation (skeletal only)

## Common Mistakes

❌ **Wrong:** `token unreal:naniteAssembly:meshType`  
✓ **Correct:** `uniform token unreal:naniteAssembly:meshType`

❌ **Wrong:** FBX references in prototypes  
✓ **Correct:** USD references only

❌ **Wrong:** Skeletal twigs in skeletal assembly  
✓ **Correct:** Static twigs bound to skeleton

❌ **Wrong:** No skeleton relationship for skeletalMesh  
✓ **Correct:** Always set skeleton relationship

## Attribute Variability Quick Reference

| Attribute | Variability | Why |
|-----------|-------------|-----|
| `unreal:naniteAssembly:meshType` | uniform | Schema requirement |
| `bindJoints` | uniform | Per-instancer, not per-point |
| `bindJointWeights` | uniform | Per-instancer, not per-point |
| `visibility` | varying | Can change per-point |

## File Structure

```
output/
├── Species/
│   ├── USD/
│   │   ├── Species_tree_static.usda
│   │   ├── Species_tree_skeletal.usda
│   │   ├── Species_NaniteAssembly.usda
│   │   └── Species_NaniteAssembly_skeletal.usda
│   └── twigs/
│       ├── twig_long.usda
│       ├── twig_short.usda
│       └── textures/
└── ...
```

## Debugging

### Check Schema in USD File

```bash
grep -A 2 "apiSchemas" assembly.usda
grep "unreal:naniteAssembly" assembly.usda
```

### Verify Uniform Token

Look for this pattern:

```usd
uniform token unreal:naniteAssembly:meshType = "skeletalMesh"
```

NOT:

```usd
token unreal:naniteAssembly:meshType = "skeletalMesh"
```

### Check Skeleton Path

```bash
grep -A 1 "unreal:naniteAssembly:skeleton" assembly.usda
```

Should show:

```usd
custom rel unreal:naniteAssembly:skeleton
prepend rel unreal:naniteAssembly:skeleton = </Path/To/Skeleton>
```

## Performance Tips

1. **Threshold:** Set to 2000-5000 for trees
2. **Instances:** Use instanceable=true on all prototypes
3. **Visibility:** Hide prototypes (visibility="invisible")
4. **Textures:** Use compressed formats (jpg, png)
5. **LODs:** Consider multiple assemblies for distance

## Documentation

- Full Guide: `docs/growpy/unreal-nanite-assembly.md`
- Schema Update: `docs/archive/NANITE_ASSEMBLY_SCHEMA_UPDATE.md`
- Schema Reference: `data/unreal_schema/schema.usda`
