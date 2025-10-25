# IMMEDIATE FIXES NEEDED - Skeletal Nanite Assembly

Based on video analysis (<https://www.youtube.com/watch?v=b_jhGZ2jto8>), here are the CRITICAL missing pieces in your current implementation.

---

## 🔴 CRITICAL: Missing GeomModelAPI

**What Video Shows:**

```usd
def Xform "AwesomeTree" (
    apiSchemas = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
    kind = "group"
)
```

**Your Current Code:**

```python
# File: src/growpy/io/unreal_nanite_assembly.py, line 92
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]  # ❌ Missing GeomModelAPI
root_prim.SetMetadata("apiSchemas", api_schemas)
```

**Fix Required:**

```python
# Add BOTH schemas
api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
```

---

## 🔴 CRITICAL: Missing `kind = "group"` Metadata

**What Video Shows:**

```usd
def Xform "AwesomeTree" (
    kind = "group"  # ← Required for Unreal
)
```

**Your Current Code:**

```python
# File: src/growpy/io/unreal_nanite_assembly.py, line 90-92
root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
# ❌ No kind metadata set
```

**Fix Required:**

```python
root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")

# Import UsdGeom for Kind
from pxr import UsdGeom

# Set kind to "group"
UsdGeom.ModelAPI.Apply(root_prim)
UsdGeom.ModelAPI(root_prim).SetKind("group")

# OR directly:
# root_prim.SetMetadata("kind", "group")
```

---

## ⚠️ VERIFY: Joint Name Casing

**What Video Shows:**

```usd
uniform token[] joints = ["root", "root/joint0", "root/joint0/joint1", ...]
```

**Your Current Code:**

```python
# File: src/growpy/io/blender_export.py, line 1834
joints.append("Root")  # ← Capital 'R'
joint_name = f"Root/Branch_{i}_Bone_{j}"  # ← Capital 'R'
```

**Potential Issue:**

- Video uses lowercase `"root"`
- You use uppercase `"Root"`
- Unreal may be case-sensitive for skeleton binding

**Action:**
Test import in Unreal. If skeleton doesn't bind correctly, change all joint names to lowercase:

```python
joints.append("root")  # lowercase
joint_name = f"root/branch_{i}_bone_{j}"  # lowercase
```

---

## ⚠️ VERIFY: Primvar Interpolation Mode

**What Video Shows:**

```usd
def Mesh "_11" (
    apiSchemas = ["SkelBindingAPI"]
)
{
    int[] primvars:skel:jointIndices = [...]
    float[] primvars:skel:jointWeights = [...]
    string interpolation = "vertex"  # ← Vertex interpolation
}
```

**Your Current Code:**

```python
# File: src/growpy/io/skeleton_from_bones.py, line 256-259
binding.CreateJointIndicesPrimvar(False, 1).Set(Vt.IntArray(joint_indices_array))
binding.CreateJointWeightsPrimvar(False, 1).Set(Vt.FloatArray(joint_weights_array))
# First arg: False = "constant" interpolation
# Should it be True for "vertex" interpolation?
```

**USD Skel Documentation:**

- `CreateJointIndicesPrimvar(constant, elementSize)`
- `constant=False` → vertex interpolation ✅
- `constant=True` → constant interpolation ❌

**Your code is CORRECT** if `False` = vertex interpolation. Verify by checking output USD file for `interpolation = "vertex"`.

---

## ⚠️ OPTIONAL: SkelRoot Prepend Reference

**What Video Shows:**

```usd
def SkelRoot "SkelRoot" (
    prepend references = </AwesomeTree/SkelRoot/Skeleton>
)
```

**Your Current Code:**

```python
# File: src/growpy/io/blender_export.py, line 1843
skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)
# ❌ No prepend reference to Skeleton child
```

**Unclear from video if this is required or auto-generated.** Test without it first. If skeleton doesn't work, add:

```python
# After creating Skeleton prim
skel_root_prim.GetPrim().GetReferences().AddInternalReference(
    skel_path,
    layerOffset=Sdf.LayerOffset(),
    position=Usd.ListPositionFrontOfPrependList
)
```

---

## 📋 Implementation Checklist

Apply these fixes in order:

### 1. Add GeomModelAPI (CRITICAL)

**File**: `src/growpy/io/unreal_nanite_assembly.py`  
**Line**: ~92

```python
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]  # Add GeomModelAPI
root_prim.SetMetadata("apiSchemas", api_schemas)
```

### 2. Set `kind = "group"` (CRITICAL)

**File**: `src/growpy/io/unreal_nanite_assembly.py`  
**Line**: ~94 (after api_schemas)

```python
# Import at top of file
from pxr import UsdGeom

# After setting apiSchemas
root_prim.SetMetadata("kind", "group")
```

### 3. Test Export

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/test.csv \
    --quality high \
    --output-dir data/output/test_skeletal \
    --growth-cycle-limit 3 \
    --formats usda
```

### 4. Validate USD File

```bash
# Check for required attributes
grep "GeomModelAPI" data/output/test_skeletal/**/*_NaniteAssembly.usda
grep "kind = \"group\"" data/output/test_skeletal/**/*_NaniteAssembly.usda
grep "primvars:skel:jointIndices" data/output/test_skeletal/**/*tree*.usda
grep "interpolation = \"vertex\"" data/output/test_skeletal/**/*tree*.usda
```

### 5. Import to Unreal Engine

- Import skeletal tree USD
- Verify skeleton shows up in Unreal's Skeleton Editor
- Check if bones are recognized and named correctly
- Test if twig instances follow skeleton

### 6. If Skeleton Doesn't Bind

Try lowercase joint names:

- Change `"Root"` → `"root"`
- Change `"Branch_0_Bone_0"` → `"branch_0_bone_0"`
- Re-export and test

---

## Quick Fix Script

Here's the exact change needed in `unreal_nanite_assembly.py`:

```python
# Around line 90-95, replace this:
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# With this:
api_schemas = Sdf.TokenListOp()
api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
root_prim.SetMetadata("apiSchemas", api_schemas)

# Set kind metadata
root_prim.SetMetadata("kind", "group")
```

---

## Testing Plan

1. ✅ Apply GeomModelAPI + kind fixes
2. ✅ Export single test tree
3. ✅ Inspect USD file manually (text editor or usdview)
4. ✅ Import to Unreal Engine
5. ✅ Verify skeleton recognition
6. ✅ If fails, try lowercase joint names
7. ✅ Document findings in VIDEO_ANALYSIS_SKELETAL_FOLIAGE.md

---

## Reference

- Video: <https://www.youtube.com/watch?v=b_jhGZ2jto8>
- Full analysis: `docs/VIDEO_ANALYSIS_SKELETAL_FOLIAGE.md`
- Your implementation: `src/growpy/io/unreal_nanite_assembly.py`
