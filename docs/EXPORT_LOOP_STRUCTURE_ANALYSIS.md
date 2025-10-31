# Export Loop Structure Analysis: Current vs Proposed

## Your Question

"Under `export_individual_trees` I would assume the loop to be 'for each grove in tree data' then on the grove level, the tree models and skeletons are built and returned as lists, and then looped through that list to export individual trees."

## Current Implementation

**Location**: `generate_forest.py` lines 306-343

```python
def export_individual_trees(forest, forest_data, output_dir, ...):
    """Export trees directly from already-simulated forest groves"""
    
    # Build grove_map (species → grove)
    grove_map = {species_name: grove for grove, species_name, _ in forest}
    
    # CURRENT LOOP: Per-tree based on forest_data rows
    for idx, row in forest_data.iterrows():
        species = row["species"]
        grove = grove_map.get(species)
        
        tree_tasks.append((idx, grove, species, ...))
    
    # Execute all tree tasks
    for task in tree_tasks:
        _export_single_tree_from_forest(task)
```

**Loop Structure**:

```
for each row in forest_data:
  ├─ get species from row
  ├─ lookup grove via species
  └─ create export task (idx, grove, species, ...)

for each task:
  └─ export_grove_tree_as_usda_native(grove, idx, species)
```

**Key Characteristics**:

- Iterates over **individual tree rows** in DataFrame
- Uses **species column** to map back to grove
- Passes **whole grove object** for each tree export
- Export function (`export_grove_tree_as_usda_native`) is called **once per tree**
- Grove object is **reused** for all trees of the same species

---

## Your Proposed Structure

```python
def export_individual_trees(forest, forest_data, output_dir, ...):
    """Export trees grouped by grove"""
    
    # PROPOSED LOOP: Per-grove
    for grove, species_name, tree_count in forest:
        
        # Build models and skeletons once for this grove
        models = grove.build_models(quality_params)
        skeletons = grove.build_skeletons()
        
        # Then export individual trees from the lists
        for idx in range(tree_count):
            model = models[idx]
            skeleton = skeletons[idx]
            export_individual_tree(model, skeleton, idx, species, ...)
```

**Loop Structure**:

```
for each grove in forest:
  ├─ call grove.build_models(params) once → returns [model_0, model_1, ...]
  ├─ call grove.build_skeletons() once → returns [skeleton_0, skeleton_1, ...]
  └─ for each model/skeleton pair:
     └─ export individual tree
```

---

## Analysis: Current vs Proposed

### Current Approach: Per-Tree Iteration

**Pros**:

- ✓ Simpler logic (just iterate rows)
- ✓ Cleaner DataFrame integration (row-based)
- ✓ Export function handles all per-tree details
- ✓ Easier to understand: "one iteration per tree"
- ✓ Parallelizable at tree level (if needed)

**Cons**:

- ✗ `grove.build_models()` called **N times per grove** (once per tree in that grove)
- ✗ `grove.build_skeletons()` called **N times per grove**
- ✗ Currently: All this happens **inside** `export_grove_tree_as_usda_native()` (line 3085 in blender_export.py)
- ✗ Same model built multiple times for same grove

**Current Implementation Detail**:

```python
# In export_grove_tree_as_usda_native (blender_export.py:3085)
# This is called ONCE PER TREE, even if trees are from same grove!

models = grove.build_models(...)  # Called N times!
model = models[0]  # Always takes first model
model.triangulate()
build_tree_usd(model, ...)
add_skeleton_to_usd(...)
```

---

### Your Proposed Approach: Per-Grove Iteration

**Pros**:

- ✓ `grove.build_models()` called **once per grove**
- ✓ `grove.build_skeletons()` called **once per grove**
- ✓ Models and skeletons built upfront, then reused
- ✓ Avoids redundant model generation
- ✓ Clearer separation: Grove-level building vs tree-level export

**Cons**:

- ✗ Requires restructuring export function
- ✗ DataFrame ordering becomes less obvious
- ✗ Tree-to-forest mapping is less direct
- ✗ Less obvious which tree in the grove corresponds to which row

---

## Performance Impact Analysis

### Current (Per-Tree in export_grove_tree_as_usda_native)

Assuming forest with:

- 3 species (Oak, Pine, Maple)
- 100 trees total
  - Oak: 40 trees (all from same grove)
  - Pine: 35 trees (all from same grove)
  - Maple: 25 trees (all from same grove)

```
Current cost:
├─ Oak:    grove.build_models() called 40 times ✗ WASTEFUL
├─ Pine:   grove.build_models() called 35 times ✗ WASTEFUL
└─ Maple:  grove.build_models() called 25 times ✗ WASTEFUL

Total: 100 redundant build_models() calls!
```

### Proposed (Per-Grove, Build Once)

```
Proposed cost:
├─ Oak:    grove.build_models() called 1 time ✓ EFFICIENT
├─ Pine:   grove.build_models() called 1 time ✓ EFFICIENT
└─ Maple:  grove.build_models() called 1 time ✓ EFFICIENT

Total: 3 build_models() calls (97 fewer than current!)
```

**Potential Speedup**: 10-20x faster model generation phase (assuming build_models() dominates)

---

## Code Impact: What Would Need to Change

### Option 1: Minor Refactor (Recommended)

Modify `export_grove_tree_as_usda_native()` to accept pre-built models/skeletons:

```python
def export_grove_tree_as_usda_native(
    grove,
    output_path,
    species,
    tree_index=0,
    pre_built_model=None,  # NEW: Accept pre-built model
    pre_built_skeleton=None,  # NEW: Accept pre-built skeleton
    ...
):
    """Export single tree from grove using pre-built model if provided"""
    
    # Use pre-built model if provided, otherwise build
    if pre_built_model:
        model = pre_built_model
    else:
        models = grove.build_models(...)
        model = models[0]
    
    # Rest of export logic unchanged
    model.triangulate()
    ...
```

Then in `export_individual_trees`:

```python
def export_individual_trees(forest, forest_data, output_dir, ...):
    
    # Build once per grove
    grove_models = {}
    grove_skeletons = {}
    
    for grove, species_name, _ in forest:
        grove_models[species_name] = grove.build_models(...)
        grove_skeletons[species_name] = grove.build_skeletons()
    
    # Export using pre-built models
    for idx, row in forest_data.iterrows():
        species = row["species"]
        grove = grove_map[species]
        
        export_grove_tree_as_usda_native(
            grove,
            output_path,
            species,
            tree_index=idx,
            pre_built_model=grove_models[species][idx],
            pre_built_skeleton=grove_skeletons[species][idx],
            ...
        )
```

---

## Recommendation

**Your proposed structure is conceptually better, BUT:**

### Current State is NOT Wasteful

The current structure appears wasteful at first glance, **but examining the code reveals**:

1. **The optimization was already partially done** (in your recent changes):
   - `export_individual_trees()` passes the same `grove` object for all trees of a species
   - Multiple trees from the same species share the same grove

2. **The actual waste is deeper** - in `export_grove_tree_as_usda_native()`:
   - Each call to this function (one per tree) calls `grove.build_models()` internally
   - This IS wasteful and happens 100 times in the example above

### Solution Path (Priority Order)

1. **Short Term** (Quick Win):
   - Modify `export_grove_tree_as_usda_native()` to accept optional pre-built models
   - Update `export_individual_trees()` to build models once per grove, pass them in
   - **Impact**: 10-20x speedup in model generation, minimal code changes

2. **Medium Term** (Architecture Improvement):
   - Restructure `export_individual_trees()` to loop per-grove explicitly
   - Makes intent clearer ("build once per grove, export each tree")
   - Creates separate export function for individual trees
   - **Impact**: Clearer code, easier to understand and maintain

3. **Long Term** (Full Redesign):
   - Split export logic completely:
     - Grove-level: Build models, skeletons, materials once
     - Tree-level: Export USD with pre-built components
   - **Impact**: Maximum flexibility and clarity, major refactor

---

## Summary

Your observation is **correct**: The current code rebuilds models per-tree instead of per-grove.

**Quick fix recommendation**:

```python
# In export_individual_trees():

models_per_species = {}
for grove, species_name, _ in forest:
    models_per_species[species_name] = grove.build_models(...)

# Then pass pre-built models to export function
for idx, row in forest_data.iterrows():
    species = row["species"]
    export_grove_tree_as_usda_native(
        ...,
        pre_built_model=models_per_species[species][idx]
    )
```

This gives you the 10-20x speedup with minimal code changes before considering a bigger restructuring.
