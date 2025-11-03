# Debug Breakpoints for Mapping and Skinning

This document describes all debug breakpoints added to GrowPy to trace mesh-to-skeleton binding.

## Overview

The mapping/skinning process happens in these phases:

1. **Phase 1A**: `grove.tag_bone_id()` - Tags vertices with bone assignments
2. **Phase 1B**: `grove.build_models()` - Builds mesh WITH bone_id/bone_weight attributes
3. **Phase 2B**: `grove.build_skeletons()` - Extracts skeleton hierarchy
4. **Phase 3**: USD export receives model with bone attributes
5. **Phase 4**: `calculate_vertex_weights()` - Converts bone_id to USD joint indices

## Breakpoint Locations

### Breakpoint 1: Before Building Models

**File**: `src/growpy/cli/generate_forest.py` (line ~115)  
**Function**: `_export_single_tree_from_forest()`  
**Purpose**: Shows grove state before calling `build_skeletons()` and `build_models()`

```python
print(f"\n[DEBUG] PHASE 1A: About to call grove.tag_bone_id() internally via build_skeletons")
print(f"[DEBUG] Grove has {len(grove.all_trees)} trees")
```

**What to inspect**:

- Number of trees in grove
- Grove simulation state (flushes completed)

---

### Breakpoint 2: After Building Skeletons

**File**: `src/growpy/cli/generate_forest.py` (line ~122)  
**Function**: `_export_single_tree_from_forest()`  
**Purpose**: Confirms skeleton building and internal bone tagging completed

```python
skeletons = grove.build_skeletons()
print(f"[DEBUG] PHASE 1A COMPLETE: Skeleton tagging done, {len(skeletons)} skeletons created")
```

**What to inspect**:

- Number of skeletons returned
- Skeleton structure (use debugger to inspect `skeletons[0]`)

---

### Breakpoint 3: After Building Models

**File**: `src/growpy/cli/generate_forest.py` (line ~137)  
**Function**: `_export_single_tree_from_forest()`  
**Purpose**: Shows models were built WITH bone attributes

```python
models = grove.build_models({...})
print(f"[DEBUG] PHASE 1B COMPLETE: {len(models)} models created")
```

**What to inspect**:

- Number of models returned
- Use debugger to check `models[0].point_attribute_bone_id` exists

---

### Breakpoint 4: Model Bone Attributes Inspection

**File**: `src/growpy/cli/generate_forest.py` (line ~150)  
**Function**: `_export_single_tree_from_forest()` (inside export loop)  
**Purpose**: Detailed inspection of bone mapping data

```python
print(f"\n[DEBUG] === MODEL {model_idx} BONE ATTRIBUTES ===")
if hasattr(model, 'point_attribute_bone_id'):
    bone_ids = model.point_attribute_bone_id
    print(f"[DEBUG] ✓ Model has bone_id mapping: {len(bone_ids)} vertices")
    print(f"[DEBUG]   Unique bone IDs: {sorted(set(bone_ids))}")
    print(f"[DEBUG]   Sample bone_ids (first 10 vertices): {bone_ids[:10]}")
```

**What to inspect**:

- Number of vertices with bone assignments
- Which bone IDs are used (should see 0, 1, 2, ... matching skeleton)
- Sample bone_id values for first few vertices
- Bone weights (should be mostly 1.0 for simple binding)
- Number of joints in skeleton
- Number of bone chains in skeleton

**Key insight**: If `point_attribute_bone_id` is missing here, the mapping NEVER happened.

---

### Breakpoint 5: get_bone_data_from_grove()

**File**: `src/growpy/core/skeleton.py` (line ~150)  
**Function**: `get_bone_data_from_grove()`  
**Purpose**: Shows bone hierarchy extraction from grove

```python
print(f"\n[DEBUG] PHASE 2B: get_bone_data_from_grove called")
print(f"[DEBUG] Parameters: length={skeleton_length}, reduce={skeleton_reduce}, ...")
bones_info = grove.tag_bone_id(skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected)
print(f"[DEBUG] ✓ tag_bone_id returned {len(bones_info)} bones")
```

**What to inspect**:

- Parameters passed to `tag_bone_id()` (should be length=0.0, reduce=0.0)
- Number of bones returned
- Bone structure (bone_idx, parent_idx, head position, tail position, radius)
- Sample bones showing parent-child relationships

**Key insight**: This shows the SKELETON structure that vertices are mapped to.

---

### Breakpoint 6: export_tree() Entry Point

**File**: `src/growpy/io/tree_export.py` (line ~193)  
**Function**: `export_tree()`  
**Purpose**: Confirms model WITH bone attributes reached export

```python
print(f"\n[DEBUG] PHASE 3: export_tree called for {species_name}")
if hasattr(model, 'point_attribute_bone_id'):
    print(f"[DEBUG] ✓ Model received with bone_id mapping: {len(bone_ids)} vertices")
else:
    print(f"[DEBUG] ✗ Model received WITHOUT bone_id mapping")
```

**What to inspect**:

- Model has bone_id attribute (should always be True)
- Model has bone_weight attribute
- Number of vertices

**Key insight**: If bone_id is missing here, export will fail or produce broken skinning.

---

### Breakpoint 7: calculate_vertex_weights()

**File**: `src/growpy/core/skeleton.py` (line ~232)  
**Function**: `calculate_vertex_weights()`  
**Purpose**: Shows conversion from Grove bone_id to USD joint indices

```python
print(f"\n[DEBUG] PHASE 4: calculate_vertex_weights called")
print(f"[DEBUG] Converting {len(bone_ids)} vertices from bone_id to joint indices")
print(f"[DEBUG] Bone-to-joint mapping has {len(bone_to_joint_map)} entries")
print(f"[DEBUG] Sample bone_to_joint_map: {dict(list(bone_to_joint_map.items())[:5])}")
```

**What to inspect**:

- Number of vertices being converted
- Bone-to-joint map: `{0: 0, 1: 1, 2: 2, ...}` (usually 1:1 mapping)
- Sample bone_id values from model
- Output joint_indices array (first 20 entries)
- Output joint_weights array (first 20 entries)

**What to look for**:

- `bone_to_joint_map` should have entries for all bone IDs in model
- Output arrays should have `len(vertices) * element_size` entries
- `joint_indices` should contain valid joint indices (0 to num_joints-1)
- `joint_weights` should contain weights (mostly 1.0 for primary influence)

**Key insight**: This is where Grove's internal bone IDs become USD's joint indices.

---

### Breakpoint 8: Bone Usage Statistics

**File**: `src/growpy/core/skeleton.py` (line ~263)  
**Function**: `calculate_vertex_weights()` (end of function)  
**Purpose**: Summary of conversion results

```python
print(f"[DEBUG] Conversion complete: {len(joint_indices_array)} total entries")
print(f"[DEBUG] Bones used: {len(bone_usage)} unique bone IDs")
print(f"[DEBUG] Sample bone usage: {dict(list(bone_usage.items())[:5])}")
```

**What to inspect**:

- Total entries in output arrays
- Number of unique bone IDs actually used
- Which bones are most used (bone usage counts)
- Sample output showing bone_id → joint_idx → usage_count

**Key insight**: Shows distribution of vertices across bones.

---

## How to Use These Breakpoints

### 1. Run the Pipeline

```bash
conda activate the-grove
python src/growpy/cli/generate_forest.py data/input/test_single.csv
```

### 2. Check Console Output

Look for the `[DEBUG]` prefix in console output showing the progression:

- Phase 1A: Skeleton building
- Phase 1B: Model building with bone attributes
- Phase 2B: Bone hierarchy extraction
- Phase 3: Export receiving model
- Phase 4: Bone ID to joint index conversion

### 3. Add Python Debugger Breakpoints

If you need to inspect data structures in detail, add `breakpoint()` calls:

```python
# In generate_forest.py after building models:
models = grove.build_models({...})
print(f"[DEBUG] Models built: {len(models)}")
breakpoint()  # <-- Pauses here, type 'models[0].point_attribute_bone_id' in debugger
```

Then run with Python debugger:

```bash
python -m pdb src/growpy/cli/generate_forest.py data/input/test_single.csv
# Type 'c' to continue to breakpoint
# Type 'models[0].point_attribute_bone_id' to inspect
# Type 'pp bone_ids[:20]' to pretty-print first 20 values
```

### 4. Key Questions to Answer

**Q1: Are bone attributes present after build_models()?**  
→ Check Breakpoint 4 output for `✓ Model has bone_id mapping`

**Q2: How many bones control the mesh?**  
→ Check Breakpoint 4: `Unique bone IDs: [0, 1, 2, ...]`

**Q3: Are vertices correctly assigned to bones?**  
→ Check Breakpoint 4: `Sample bone_ids (first 10 vertices): [3, 3, 3, 4, 4, ...]`  
→ Should see logical groupings (nearby vertices share bones)

**Q4: Does bone-to-joint mapping work?**  
→ Check Breakpoint 7: `bone_to_joint_map: {0: 0, 1: 1, 2: 2, ...}`  
→ Should be 1:1 mapping with no missing entries

**Q5: Are all bones used?**  
→ Check Breakpoint 8: `Bones used: X unique bone IDs`  
→ Compare to number of joints in skeleton

---

## Expected Output Example

When running `generate_forest.py` with debug breakpoints, you should see:

```
[DEBUG] PHASE 1A: About to call grove.tag_bone_id() internally via build_skeletons
[DEBUG] Grove has 1 trees

[DEBUG] PHASE 2B: get_bone_data_from_grove called
[DEBUG] Parameters: length=0.0, reduce=0.0, bias=0.5, connected=True
[DEBUG] ✓ tag_bone_id returned 45 bones
[DEBUG]   Bone 0: idx=0, parent=-1, radius=0.0500
[DEBUG]   Bone 1: idx=1, parent=0, radius=0.0450
[DEBUG]   Bone 2: idx=2, parent=1, radius=0.0400
[DEBUG]   ... and 42 more bones

[DEBUG] PHASE 1A COMPLETE: Skeleton tagging done, 1 skeletons created

[DEBUG] PHASE 1B: Building models with bone attributes...
[DEBUG] PHASE 1B COMPLETE: 1 models created

[DEBUG] === MODEL 0 BONE ATTRIBUTES ===
[DEBUG] ✓ Model has bone_id mapping: 3845 vertices
[DEBUG]   Unique bone IDs: [0, 1, 2, 3, ..., 44]
[DEBUG]   Sample bone_ids (first 10 vertices): [0, 0, 0, 1, 1, 1, 1, 2, 2, 2]
[DEBUG] ✓ Model has bone weights: 3845 vertices
[DEBUG]   Sample weights (first 10 vertices): ['1.000', '1.000', '1.000', '1.000', ...]
[DEBUG] ✓ Skeleton has 45 joints
[DEBUG] ✓ Skeleton has 10 bone chains
[DEBUG] =====================================

[DEBUG] PHASE 3: export_tree called for quercus_robur
[DEBUG] Output path: data/output/forest/quercus_robur/tree_0000_nanite_assembly.usda
[DEBUG] ✓ Model received with bone_id mapping: 3845 vertices
[DEBUG]   Unique bone IDs: 45 bones
[DEBUG] ✓ Model received with bone weights

[DEBUG] PHASE 4: calculate_vertex_weights called
[DEBUG] Converting 3845 vertices from bone_id to joint indices
[DEBUG] Bone-to-joint mapping has 45 entries
[DEBUG] Sample bone_to_joint_map: {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
[DEBUG] Conversion complete: 7690 total entries (3845 vertices × 2)
[DEBUG] Bones used: 45 unique bone IDs
[DEBUG] Sample bone usage: {0: {'count': 120, 'joint_idx': 0}, 1: {'count': 95, 'joint_idx': 1}, ...}
[DEBUG] Sample output joint_indices (first 20): [0, 0, 0, 0, 0, 0, 1, 0, 1, 0, ...]
[DEBUG] Sample output joint_weights (first 20): ['1.000', '0.000', '1.000', '0.000', ...]
```

---

## Troubleshooting

### Problem: "Model missing point_attribute_bone_id"

**Diagnosis**: Bone tagging didn't happen before `build_models()`  
**Fix**: Ensure `build_skeletons()` is called BEFORE `build_models()`

### Problem: "tag_bone_id returned 0 bones"

**Diagnosis**: Grove simulation didn't produce geometry  
**Fix**: Check grove has trees, simulation ran, and trees have branches

### Problem: "Bone-to-joint mapping has 0 entries"

**Diagnosis**: Skeleton extraction failed  
**Fix**: Check `get_bone_data_from_grove()` returned valid bones

### Problem: All vertices assigned to bone 0

**Diagnosis**: Bone tagging parameters too aggressive (skeleton_reduce too high)  
**Fix**: Use `skeleton_reduce=0.0` to preserve all bones

---

## Removing Debug Output

To disable debug output without removing breakpoints:

1. **Quick disable**: Comment out print statements in each breakpoint
2. **Environment variable**: Add check at start of each function:

   ```python
   import os
   DEBUG_MAPPING = os.getenv("GROWPY_DEBUG_MAPPING", "false").lower() == "true"
   if DEBUG_MAPPING:
       print("[DEBUG] ...")
   ```

3. **Logging module**: Replace print() with logging.debug() and control with log level

---

## Related Documentation

- `DEPENDENCY_DIAGRAM.md` - Section 7: High-level flow showing Phase 1A/1B/2B/3/4
- `DEPENDENCY_DIAGRAM.md` - Section 8: Mapping vs Skinning terminology
- `docs/growpy/tutorials/skeletal-mesh-export.md` - Complete export guide
