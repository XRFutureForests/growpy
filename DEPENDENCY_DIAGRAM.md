# GrowPy Generate Forest Script: Dependency & Call Diagram

## Overview

This document maps the dependencies and call flow of `generate_forest.py`, with particular focus on **skeletal mesh creation** and **jointIndices assignment**.

**Architecture Note**: GrowPy exports ONLY skeletal meshes. All trees and twigs are exported with complete skeleton structures for use with Unreal Engine's Nanite skeletal mesh system. Static mesh export has been removed for simplicity and to focus on the skeletal workflow.

---

## Table of Contents

### Pipeline Steps (Sections 1-5)

1. [Complete Pipeline Overview](#1-complete-pipeline-overview)
2. [STEP 1: Asset Preparation](#2-step-1-asset-preparation-prepare_assetspy)
3. [STEP 2: Twig Export](#3-step-2-twig-export-export_twigspy)
4. [STEP 3: Growth Model Creation](#4-step-3-growth-model-creation-create_growth_modelspy)
5. [STEP 4: Forest Generation](#5-step-4-forest-generation-generate_forestpy)

### Architecture & Dependencies (Sections 6-9)

6. [Dependency Diagram (Module Relationships)](#6-dependency-diagram-module-relationships)
7. [Export Call Sequence (Skeletal Mesh Creation)](#7-export-call-sequence-skeletal-mesh-creation)
8. [Key Data Flow: From Grove Bones to USD jointIndices](#8-key-data-flow-from-grove-bones-to-usd-jointindices)
9. [Module Responsibilities](#9-module-responsibilities)

### Skeleton Creation Details (Sections 10-15)

10. [Where jointIndices Are Set](#10-where-jointindices-are-set-the-answer)
11. [When Skeleton Is Created (Timeline)](#11-when-skeleton-is-created-timeline)
12. [Data Structure: jointIndices Explained](#12-data-structure-jointindices-explained)
13. [Skeleton Creation Prerequisites](#13-skeleton-creation-prerequisites)
14. [Quality Parameters' Role](#14-quality-parameters-role-in-skeleton-creation)
15. [Complete Export Architecture Diagram](#15-complete-export-architecture-diagram)

### Summary & Optimization (Sections 16-17)

16. [Summary: jointIndices Creation Path](#16-summary-jointindices-creation-path)
17. [Optimization: Single-Pass Export](#17-optimization-single-pass-export-no-re-simulation)

---

## 1. Complete Pipeline Overview

The GrowPy pipeline consists of five main CLI steps that must be run in sequence:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GROWPY COMPLETE PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────┘

  STEP 1: prepare_assets.py
    ↓     Copy assets from Grove 2.2 installation
    │     • Species presets (.seed.json files)
    │     • Textures (bark, leaf materials)
    │     • Twig models (.blend files)
    │
  STEP 2: export_twigs.py
    ↓     Convert Blender twig models to skeletal USD
    │     • Load .blend files
    │     • Add root joint skeleton
    │     • Export as .usda with UsdSkel
    │
  STEP 3: create_growth_models.py
    ↓     Generate height prediction models
    │     • Simulate multiple trees per species
    │     • Measure height vs growth_cycles
    │     • Train sklearn regression models
    │
  STEP 4: generate_forest.py
    ↓     Create forest from CSV data
    │     • Load tree positions/species from CSV
    │     • Simulate multi-species growth with light competition
    │     • Export individual skeletal trees
    │     • Create skeletal Nanite Assemblies
    │
  STEP 5: (Optional) Manual import to Unreal Engine
          Import skeletal Nanite Assemblies
          • UE5.7+ skeletal Nanite system
          • LOD generation
          • Material setup
```

---

## 2. STEP 1: Asset Preparation (prepare_assets.py)

### Purpose

Copy assets from The Grove 2.2 installation to project directory for pipeline use.

### CLI Usage

```bash
python src/growpy/cli/prepare_assets.py
```

### Call Sequence

```
prepare_assets.py::main()
  │
  ├─ get_config()
  │   └─ Returns GrowPyConfig with paths
  │
  ├─ Find Grove 2.2 installation
  │   └─ Check standard locations:
  │       • C:/Program Files/The Grove/
  │       • ~/Applications/The Grove/
  │       • Environment variable GROVE_INSTALL_PATH
  │
  ├─ Copy Species Presets
  │   │
  │   └─ Source: <grove_install>/presets/
  │       Destination: data/assets/presets/
  │       Files: *.seed.json (growth parameters, branch angles, etc.)
  │
  ├─ Copy Textures
  │   │
  │   └─ Source: <grove_install>/textures/
  │       Destination: data/assets/textures/
  │       Files: bark_*.png, leaf_*.png, normal_*.png
  │
  └─ Copy Twig Models
      │
      └─ Source: <grove_install>/twigs/
          Destination: data/assets/twigs/
          Files: *_twig.blend (Blender twig mesh models)
```

### Output

```
data/assets/
  ├─ presets/
  │   ├─ oak.seed.json
  │   ├─ pine.seed.json
  │   └─ maple.seed.json
  │
  ├─ textures/
  │   ├─ bark_oak.png
  │   ├─ leaf_oak.png
  │   └─ ...
  │
  └─ twigs/
      ├─ oak_twig_long.blend
      ├─ oak_twig_short.blend
      └─ ...
```

### Dependencies

- **GrowPyConfig**: Asset path management
- **The Grove 2.2**: Source installation with assets

---

## 3. STEP 2: Twig Export (export_twigs.py)

### Purpose

Convert Blender twig .blend files to skeletal USD format with root joint for Nanite Assembly binding.

### CLI Usage

```bash
python src/growpy/cli/export_twigs.py data/assets/twigs
```

### Call Sequence

```
export_twigs.py::main()
  │
  ├─ Parse arguments
  │   └─ twigs_dir: Directory containing .blend files
  │
  ├─ Find all .blend files
  │   └─ Pattern: *_twig*.blend
  │
  └─ For each .blend file:
      │
      └─ export_twigs_from_blend()  ◄─── IN twig_export.py
          │
          ├─ Import bpy (Blender Python)
          │   └─ bpy.ops.wm.open_mainfile(filepath=blend_path)
          │
          ├─ Find twig mesh in scene
          │   └─ Search for objects with "twig" in name
          │
          ├─ Add root joint skeleton
          │   │
          │   └─ create_single_bone_skeleton()
          │       │
          │       ├─ Create Armature object
          │       ├─ Add single root bone at mesh origin
          │       ├─ Parent mesh to armature
          │       └─ Set vertex weights (all verts → root bone = 1.0)
          │
          ├─ Export as USD with bpy.ops.wm.usd_export()
          │   │
          │   └─ Parameters:
          │       • export_animation=True (required for skeletal)
          │       • export_armatures=True (include skeleton)
          │       • export_materials=True
          │       • evaluation_mode='RENDER'
          │
          └─ Save as: <species>_twig_<type>_skeletal.usda
              │
              └─ Output: data/assets/twigs/*.usda
```

### Output

```
data/assets/twigs/
  ├─ oak_twig_long_skeletal.usda      (skeletal mesh with root joint)
  ├─ oak_twig_short_skeletal.usda
  ├─ pine_twig_long_skeletal.usda
  └─ ...
```

### Key Features

- **Root Joint Skeleton**: Single-bone skeleton at mesh origin
- **Full Skinning**: All vertices weighted to root bone (weight=1.0)
- **UsdSkel Structure**: Proper SkelRoot/Skeleton/Animation hierarchy
- **Nanite Compatible**: Can be bound to tree skeleton joints in assembly

### Dependencies

- **bpy (Blender Python)**: For .blend file loading and USD export
- **core/skeleton.py**: Skeleton computation utilities
- **USD (pxr)**: For UsdSkel structure validation

---

## 4. STEP 3: Growth Model Creation (create_growth_models.py)

### Purpose

Generate machine learning models that predict tree height from growth cycles for each species.

### CLI Usage

```bash
python src/growpy/cli/create_growth_models.py
```

### Call Sequence

```
create_growth_models.py::main()
  │
  ├─ get_config()
  │   └─ Load species list from tree_asset_lookup.csv
  │
  ├─ For each species:
  │   │
  │   ├─ PHASE 1: Data Collection
  │   │   │
  │   │   └─ For growth_cycles in [1, 2, 5, 10, 15, 20]:
  │   │       │
  │   │       ├─ Create Grove with species preset
  │   │       │   └─ grove = gc.Grove()
  │   │       │   └─ grove.load_seed(preset_path)
  │   │       │
  │   │       ├─ Add single tree
  │   │       │   └─ grove.add_new_tree(
  │   │       │         position=gc.Vector(0,0,0),
  │   │       │         direction=gc.Vector(0,0,1),
  │   │       │         lateral_offset=0
  │   │       │       )
  │   │       │
  │   │       ├─ Simulate growth
  │   │       │   └─ grove.simulate(flushes=growth_cycles)
  │   │       │
  │   │       ├─ Measure final height
  │   │       │   └─ trees = grove.get_trees()
  │   │       │   └─ height = trees[0].calculate_height()
  │   │       │
  │   │       └─ Record data point: (growth_cycles, height)
  │   │
  │   ├─ PHASE 2: Model Training
  │   │   │
  │   │   └─ Train sklearn model
  │   │       │
  │   │       ├─ from sklearn.linear_model import Ridge
  │   │       ├─ model = Ridge(alpha=1.0)
  │   │       ├─ X = growth_cycles (reshaped)
  │   │       ├─ y = heights
  │   │       └─ model.fit(X, y)
  │   │
  │   ├─ PHASE 3: Model Validation
  │   │   │
  │   │   └─ Calculate metrics
  │   │       ├─ R² score (goodness of fit)
  │   │       ├─ Mean Absolute Error
  │   │       └─ Root Mean Squared Error
  │   │
  │   └─ PHASE 4: Model Persistence
  │       │
  │       └─ Save model with joblib
  │           └─ joblib.dump(model, output_path)
  │               └─ Output: data/assets/growth_models/<species>_growth_model.pkl
  │
  └─ Summary Report
      └─ Print all species models with R² scores
```

### Output

```
data/assets/growth_models/
  ├─ oak_growth_model.pkl         (sklearn Ridge model)
  ├─ pine_growth_model.pkl
  ├─ maple_growth_model.pkl
  └─ ...

Model Format (pickled dict):
{
  'model': Ridge(alpha=1.0),
  'species': 'oak',
  'r2_score': 0.987,
  'training_data': [(cycles, height), ...],
  'metadata': {...}
}
```

### Model Usage

Later in pipeline, calculate growth cycles from desired height:

```python
import joblib
model = joblib.load('data/assets/growth_models/oak_growth_model.pkl')
desired_height = 15.0  # meters
growth_cycles = model.predict([[desired_height]])[0]
```

### Dependencies

- **The Grove 2.2 API**: Tree growth simulation
- **sklearn**: Ridge regression model
- **joblib**: Model serialization
- **GrowPyConfig**: Species and preset management

---

## 5. STEP 4: Forest Generation (generate_forest.py)

This is the main export step covered in detail in sections 6-12 below.

### Quick Overview

```
generate_forest.py::main()
  │
  ├─ Load CSV with tree data (x, y, species, height)
  ├─ Calculate growth_cycles from height using growth models
  ├─ Create multi-species forest (inter-species light competition)
  ├─ Simulate forest growth (single pass)
  └─ Export individual skeletal trees with Nanite Assemblies
```

See **Section 6: Export Call Sequence** for complete details.

---

## 6. Dependency Diagram (Module Relationships)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    generate_forest.py (CLI Entry)                   │
│                     └─ Main forest generation                         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐   ┌──────────────┐   ┌─────────────┐
    │ config/ │   │ core/        │   │ io/         │
    │         │   │              │   │             │
    │ GrowPy  │   │ forest.py    │   │tree_export.py ◄──── TREE EXPORT
    │Config   │   │ grove.py     │   │              │
    │ quality │   │ tree.py      │   │twig_export.py ◄──── TWIG EXPORT
    │         │   │ skeleton.py  │   │              │
    │ (Asset  │   │ twig.py      │   │assembly.py   ◄──── ASSEMBLY
    │ lookup  │   │              │   │              │
    │ Quality)│   │(simulation & │   │(USD I/O)     │
    └─────────┘   │ computation) │   └─────────────┘
                  └──────────────┘
                            │
                            ▼
                  ┌──────────────────────┐
                  │ The Grove 2.2 Python │
                  │ API (the_grove_22_   │
                  │ core.grove_core)     │
                  │                      │
                  │ • Grove() instance   │
                  │ • tag_bone_id()  ◄── CRITICAL: Bone tagging
                  │ • build_models()     │
                  │ • build_skeletons()  │
                  │ • triangulate()      │
                  └──────────────────────┘
                            │
                            ▼
                  ┌──────────────────────┐
                  │  Blender Python API  │
                  │  (bpy) + USD (pxr)   │
                  │                      │
                  │  • UsdSkel.*         │
                  │  • UsdGeom.*         │
                  │  • Gf.* (math ops)   │
                  └──────────────────────┘
```

---

## 7. Complete Export Call Sequence

This section details the **entire export process** from forest CSV data through final Nanite Assembly creation. All exports create skeletal meshes with complete skeleton structures.

### High-Level Flow

```
generate_forest.py::main()
  │
  ├─ parse_arguments()
  │   └─ Parse CLI flags:
  │       • csv_path: Forest data file (x, y, species, height)
  │       • output_dir: Export destination
  │       • quality: Preset (ultra/high/medium/low/performance)
  │       • formats: Export formats (usd/usda)
  │       • create_nanite_assembly: Build Nanite Assembly USD
  │       • skeleton_*: Skeleton quality parameters
  │       • growth_cycle_limit: Max simulation cycles
  │
  └─ generate_forest_exports()
       │
       ├─ PREPARATION PHASE
       │   │
       │   ├─ Load CSV with pandas
       │   │   └─ forest_data = pd.read_csv(csv_path)
       │   │       Required columns: x, y, species, height
       │   │       Optional columns: z (defaults to 0)
       │   │
       │   ├─ Calculate growth_cycles from height
       │   │   └─ calculate_growth_cycles_from_height(forest_data)
       │   │       Uses growth models: data/assets/growth_models/<species>_growth_model.pkl
       │   │       For each tree: growth_cycles = model.predict(height)
       │   │
       │   ├─ Apply growth_cycle_limit scaling
       │   │   └─ If max(growth_cycles) > limit:
       │   │       scale_factor = limit / max
       │   │       forest_data['growth_cycles'] *= scale_factor
       │   │
       │   └─ Get quality settings
       │       └─ quality_params = get_quality_preset(quality)
       │           {resolution, resolution_reduce, texture_repeat,
       │            build_cutoff_age, build_cutoff_thickness,
       │            build_blend, build_end_cap, skeleton_*}
       │
       ├─ FOREST SIMULATION PHASE (Single-Pass)
       │   │
       │   ├─ create_forest(forest_data)  ◄─── Creates multi-species forest
       │   │   │
       │   │   └─ For each unique species:
       │   │       │
       │   │       ├─ Load species preset
       │   │       │   └─ preset_path = config.get_preset_path(species)
       │   │       │       File: data/assets/presets/<species>.seed.json
       │   │       │
       │   │       ├─ Create Grove for species
       │   │       │   └─ grove = gc.Grove()
       │   │       │   └─ grove.load_seed(preset_path)
       │   │       │
       │   │       ├─ Add all trees of this species to grove
       │   │       │   └─ For each row where species matches:
       │   │       │       grove.add_new_tree(
       │   │       │         position=gc.Vector(x, y, z),
       │   │       │         direction=gc.Vector(0, 0, 1),
       │   │       │         lateral_offset=0,
       │   │       │         delay=row['delay']
       │   │       │       )
       │   │       │
       │   │       └─ Append to forest list
       │   │           forest.append((grove, species_name, tree_count))
       │   │
       │   └─ simulate_forest_growth(forest, max_cycles)  ◄─── Simulates ONCE
       │       │
       │       └─ For cycle in range(max_cycles):
       │           │
       │           ├─ For each grove in forest:
       │           │   └─ grove.simulate(flushes=1)
       │           │       Simulates one growth cycle
       │           │
       │           └─ Apply inter-species light competition
       │               For each tree: adjust vigor based on neighbors
       │               (Trees from different species compete for light)
       │
       ├─ TWIG BUNDLING PHASE
       │   │
       │   └─ bundle_twigs_for_species()  ◄─── Copy twigs to output dirs
       │       │
       │       └─ For each unique species in forest_data:
       │           │
       │           ├─ species_dir = output_dir / species_name
       │           │   Create species-specific output directory
       │           │
       │           └─ Copy skeletal twig USD files
       │               Source: data/assets/twigs/<species>_twig_*_skeletal.usda
       │               Destination: species_dir/<species>_twig_*.usda
       │               (Twigs are pre-exported in STEP 2 of pipeline)
       │
       └─ INDIVIDUAL TREE EXPORT PHASE
           │
           └─ export_individual_trees(forest, forest_data, ...)  ◄─── Main export loop
               │
               ├─ Build grove_map for efficient lookup
               │   └─ grove_map = {species_name: grove for grove, species_name, _ in forest}
               │       Maps species → pre-simulated grove instance
               │
               ├─ Build tree_tasks list
               │   └─ For each row in forest_data:
               │       tree_tasks.append((idx, grove, species, output_dir, quality_params, ...))
               │       grove retrieved from grove_map[species]  ◄─── Already simulated!
               │
               └─ Export trees sequentially (bpy/USD not multiprocess-safe)
                   │
                   └─ For each task in tree_tasks:
                       │
                       └─ _export_single_tree_from_forest(task)  ◄─── Worker function
                           │
                           ├─ Unpack task parameters
                           │   (idx, grove, species, output_dir, quality_params, ...)
                           │
                           ├─ Create species output directory
                           │   species_dir = output_dir / species_clean
                           │   File naming: <species>_tree_<idx:04d>.usda
                           │
                           ├─ Get twig USD paths for this species
                           │   └─ get_twig_usd_map_for_species(species, config, prefer_skeletal=True)
                           │       Returns: {'twig_long': Path, 'twig_short': Path, ...}
                           │       Points to skeletal twig USDs copied in bundling phase
                           │
                           └─ tree_export.export_tree()  ◄─── MAIN EXPORT FUNCTION
                               │
                               │  Location: src/growpy/io/tree_export.py
                               │  Purpose: Export single tree as skeletal USD with optional Assembly
                               │  Note: ALL exports are skeletal - skeleton is ALWAYS created
                               │
                               ├─ PHASE 1: MODEL BUILDING (Generate geometry)
                               │   │
                               │   │  Purpose: Build 3D tree mesh from Grove simulation data
                               │   │           Skeleton will be added later in Phase 4
                               │   │
                               │   └─ grove.build_models({quality_params})
                               │       │
                               │       ├─ Input: Build parameters dict
                               │       │   {
                               │       │     'resolution': 4-32 (vertices around branch circumference),
                               │       │     'resolution_reduce': 0.0-1.0 (taper resolution on thin branches),
                               │       │     'texture_repeat': int (UV tiling),
                               │       │     'build_cutoff_age': int (skip young branches),
                               │       │     'build_cutoff_thickness': float (skip thin branches),
                               │       │     'build_blend': bool (smooth branch joints),
                               │       │     'build_end_cap': bool (close branch ends)
                               │       │   }
                               │       │
                               │       └─ Returns: [Model] with attributes:
                               │           • point_coordinates() → vertex positions
                               │           • face_indices() → triangle connectivity
                               │           • face_attribute_twig_* → twig placement data
                               │           • material_indices → material per face
                               │           Note: Bone attributes (bone_id, bone_weight) are added later in Phase 4
                               │
                               ├─ PHASE 2: MODEL PREPARATION (Ensure consistent topology)
                               │   │
                               │   │  Purpose: Convert all faces to triangles for consistent export
                               │   │           USD and Unreal prefer triangle-only meshes
                               │   │
                               │   └─ model.triangulate()
                               │       │
                               │       └─ Converts any quad/n-gon faces to triangles
                               │           Ensures face_attribute_twig_* alignment with geometry
                               │
                               ├─ PHASE 3: SKELETAL USD EXPORT (Mesh + Materials + Skeleton)
       │                    │   │
       │                    │   │  Purpose: Export Grove geometry to USD with materials, twig placement, AND skeleton
       │                    │   │           Skeleton is added INLINE during USD building (no save/reopen needed)
       │                    │   │           This is the skeletal-only workflow optimization
       │                    │   │
       │                    │   │  Input Parameters:
       │                    │   │  • model: Grove Model object (from Phase 1 build_models)
       │                    │   │  • grove: Grove instance (for skeleton creation)
       │                    │   │  • output_path: USD file path for skeletal tree mesh
       │                    │   │  • skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
       │                    │   │
       │                    │   └─ build_tree_mesh(model, output_path, grove=grove, skeleton_*=...)
       │                    │      │
       │                    │      │  Purpose: Convert Grove Model to USD Mesh with full attribute preservation
       │                    │      │
       │                    │      ├─ Usd.Stage.CreateNew(output_path)
       │                    │      │  └─ Creates empty USD stage at specified path
       │                    │      │
       │                    │      ├─ Extract Grove Geometry via Grove API:
       │                    │      │  │
       │                    │      │  ├─ point_data = model.point_coordinates()
       │                    │      │  │  └─ Returns: List of Vector3 positions [(x,y,z), ...]
       │                    │      │  │  └─ Length: Total vertex count (e.g., 15,000 for 32 resolution)
       │                    │      │  │
       │                    │      │  ├─ face_data = model.face_indices()
       │                    │      │  │  └─ Returns: List of triangles [vertex_idx0, vertex_idx1, vertex_idx2]
       │                    │      │  │  └─ Length: Total triangle count × 3 indices
       │                    │      │  │
       │                    │      │  ├─ uv_data = model.uv_coordinates()
       │                    │      │  │  └─ Returns: UV coordinates per vertex
       │                    │      │  │
       │                    │      │  └─ texture_paths from Grove texture system
       │                    │      │     └─ Bark texture, leaf texture (if applicable)
       │                    │      │
       │                    │      ├─ Create UsdGeom.Mesh Prim
       │                    │      │  │
       │                    │      │  ├─ mesh = UsdGeom.Mesh.Define(stage, "/TreeGeometry")
       │                    │      │  │
       │                    │      │  ├─ mesh.CreatePointsAttr().Set(point_data)
       │                    │      │  │  └─ Sets vertex positions from Grove model
       │                    │      │  │
       │                    │      │  ├─ mesh.CreateFaceVertexIndicesAttr().Set(face_data)
       │                    │      │  │  └─ Sets triangle topology from Grove model
       │                    │      │  │
       │                    │      │  └─ mesh.CreateFaceVertexCountsAttr().Set([3] * num_triangles)
       │                    │      │     └─ All triangles (each face has 3 vertices)
       │                    │      │
       │                    │      ├─ Add Primvars (Grove Attributes as USD Custom Data)
       │                    │      │  │
       │                    │      │  │  Purpose: Preserve Grove's twig placement and skeletal binding data
       │                    │      │  │
       │                    │      │  ├─ TWIG PLACEMENT DATA (Face-Varying):
       │                    │      │  │  │
       │                    │      │  │  ├─ TwigLong: model.face_attribute_twig_long
       │                    │      │  │  │  └─ Per-face twig type ID for long twigs
       │                    │      │  │  │
       │                    │      │  │  ├─ TwigShort: model.face_attribute_twig_short
       │                    │      │  │  │  └─ Per-face twig type ID for short twigs
       │                    │      │  │  │
       │                    │      │  │  ├─ TwigUpward: model.face_attribute_twig_upward
       │                    │      │  │  │  └─ Per-face twig type ID for upward-facing twigs
       │                    │      │  │  │
       │                    │      │  │  └─ TwigDead: model.face_attribute_twig_dead
       │                    │      │  │     └─ Per-face twig type ID for dead twigs
       │                    │      │  │
       │                    │      │  │  Note: Skeletal binding data (bone_id, bone_weight) is NOT added here
       │                    │      │  │        Skeleton doesn't exist yet - binding happens in Phase 4
       │                    │      │  │
       │                    │      ├─ Add Materials to USD
       │                    │      │  │
       │                    │      │  ├─ Create UsdShade.Material prim
       │                    │      │  │
       │                    │      │  ├─ Add texture references (bark_texture.png, etc.)
       │                    │      │  │
       │                    │      │  └─ Bind material to mesh geometry
       │                    │      │
       │                    │      └─ stage.Save() → Intermediate tree USD file
       │                    │         │
       │                    │         └─ Output: {output_dir}/{species_name}_tree_intermediate.usda
       │                    │            Contains: Mesh geometry + materials + twig placement data
       │                    │            Missing: Skeleton structure (added in Phase 4)
       │                    │
       │                    ├─ PHASE 4: SKELETON ADDITION (CRITICAL PATH!)
       │                    │   │
       │                    │   │  Purpose: Create skeleton structure and add bone binding to mesh
       │                    │   │           THIS is where bone tagging happens (not before model building)
       │                    │   │
       │                    │   └─ add_skeleton_to_stage()  ◄─── IN skeleton.py
       │                    │      │
       │                    │      ├─ stage = Usd.Stage.Open(skeletal_tree_path)
       │                    │      │
       │                    │      ├─ grove.tag_bone_id() ◄─── BONE TAGGING HAPPENS HERE!
       │                    │      │  │
       │                    │      │  │  Purpose: Extract bone hierarchy from Grove's simulated tree
       │                    │      │  │           This is the ONLY place bone tagging is needed
       │                    │      │  │
       │                    │      │  ├─ Input: Skeleton quality parameters
       │                    │      │  │   • skeleton_length: Bone length multiplier (default: 1.0)
       │                    │      │  │   • skeleton_reduce: Reduction factor 0-1 (default: 0.1)
       │                    │      │  │   • skeleton_bias: Weight bias 0-1 (default: 0.5)
       │                    │      │  │   • skeleton_connected: Use connected hierarchy (default: True)
       │                    │      │  │
       │                    │      │  └─ Returns: bones_info = [(bone_id, parent_id, head, tail, radius), ...]
       │                    │      │
       │                    │      ├─ Build USD Skeleton Structure
       │                    │      │  │
       │                    │      │  ├─ Create SkelRoot (UsdSkel.Root)
       │                    │      │  │
       │                    │      │  └─ Create Skeleton (UsdSkel.Skeleton)
       │                    │      │
       │                    │      ├─ Build Joint Hierarchy from bone_info
       │                    │      │  │
       │                    │      │  ├─ Loop through bones_info:
       │                    │      │  │  │
       │                    │      │  │  ├─ bones_info[i] = (bone_id, parent_bone_id, head_pos, tail_pos, radius)
       │                    │      │  │  │
       │                    │      │  │  ├─ Create joint_name = f"joint_{joint_idx}"
       │                    │      │  │  │
       │                    │      │  │  ├─ Map bone_idx → joint_idx
       │                    │      │  │  │
       │                    │      │  │  ├─ Calculate LOCAL transform relative to parent
       │                    │      │  │  │  • parent_pos = world_head_positions[parent_joint_idx]
       │                    │      │  │  │  • relative_pos = world_head - parent_pos
       │                    │      │  │  │  • bone_direction = world_tail - world_head
       │                    │      │  │  │  • rotation = align_default_to_direction(bone_direction)
       │                    │      │  │  │
       │                    │      │  │  └─ Append to bind_transforms & rest_transforms
       │                    │      │  │
       │                    │      │  ├─ Build joint_parents array:
       │                    │      │  │  │
       │                    │      │  │  ├─ For each bone, determine parent_joint_idx
       │                    │      │  │  │
       │                    │      │  │  └─ joint_parents[i] = parent_joint_idx
       │                    │      │  │     └─ This encodes the HIERARCHY in flat joint array
       │                    │      │  │
       │                    │      │  └─ Fill other arrays:
       │                    │      │     • joints = ["joint_0", "joint_1", "joint_2", ...]
       │                    │      │     • joint_parents = [(-1 for root), 0, 0, 1, ...]
       │                    │      │     • bind_transforms = [matrices]
       │                    │      │     • rest_transforms = [matrices]
       │                    │      │
       │                    │      ├─ SET SKELETON ATTRIBUTES ◄─── CRITICAL!
       │                    │      │  │
       │                    │      │  ├─ skel_prim.CreateJointsAttr()
       │                    │      │  │  .Set(Vt.TokenArray(joints))
       │                    │      │  │  └─ ["joint_0", "joint_1", "joint_2", ...]
       │                    │      │  │
       │                    │      │  ├─ skel_prim.CreateBindTransformsAttr()
       │                    │      │  │  .Set(Vt.Matrix4dArray(bind_transforms))
       │                    │      │  │  └─ Local transforms of each joint
       │                    │      │  │
       │                    │      │  ├─ skel_prim.CreateRestTransformsAttr()
       │                    │      │  │  .Set(Vt.Matrix4dArray(rest_transforms))
       │                    │      │  │  └─ Same as bind (T-pose)
       │                    │      │  │
       │                    │      │  └─ skel_prim.CreateJointIndicesAttr() ◄─── JOINTINDICES SET HERE!
       │                    │      │     .Set(Vt.IntArray(joint_parents))
       │                    │      │     │
       │                    │      │     ├─ Format: [parent_idx_0, parent_idx_1, parent_idx_2, ...]
       │                    │      │     │
       │                    │      │     ├─ Example (for a tree with 3-level hierarchy):
       │                    │      │     │  joint_0 (root):      parent_idx = -1  (no parent)
       │                    │      │     │  joint_1 (branch):    parent_idx = 0   (parent is root)
       │                    │      │     │  joint_2 (sub-branch): parent_idx = 1  (parent is branch)
       │                    │      │     │
       │                    │      │     └─ ARRAY: [-1, 0, 1]
       │                    │      │        This IS the jointIndices!
       │                    │      │
       │                    │      ├─ Add Skinning Weights (if model provided)
       │                    │      │  │
       │                    │      │  └─ For each vertex:
       │                    │      │     │
       │                    │      │     ├─ bone_id = model.point_attribute_bone_id[vertex_idx]
       │                    │      │     │
       │                    │      │     ├─ joint_idx = bone_to_joint[bone_id]
       │                    │      │     │
       │                    │      │     └─ Append to joint_indices_array: [joint_idx, 0]
       │                    │      │        └─ elementSize=2 (primary + padding)
       │                    │      │
       │                    │      ├─ binding.CreateJointIndicesPrimvar(False, 2)
       │                    │      │  │
       │                    │      │  └─ SET MESH SKINNING WEIGHTS ◄─── MESH BINDING!
       │                    │      │     For each vertex: which joint(s) influence it?
       │                    │      │     └─ This tells Unreal which bones deform which vertices
       │                    │      │
       │                    │      ├─ Create SkelAnimation for bind pose
       │                    │      │
       │                    │      ├─ Move mesh under SkelRoot
       │                    │      │
       │                    │      └─ stage.Save() → Final skeletal USD
       │                    │         │
       │                    │         └─ Output: {output_dir}/{species_name}_tree.usda
       │                    │            Complete skeletal tree with UsdSkel structure
       │                    │
       │                    ├─ PHASE 5: NANITE ASSEMBLY CREATION (Skeletal Tree + Twig Instances)
       │                    │   │
       │                    │   │  Purpose: Combine skeletal tree mesh with skeletal twig references
       │                    │   │           Create final USD for Unreal Engine import with joint binding
       │                    │   │
       │                    │   │  Input Parameters:
       │                    │   │  • skeletal_tree_path: Path to skeletal tree USD from Phase 4
       │                    │   │  • twig_bundle_dir: Directory with skeletal twig USD files
       │                    │   │  • assembly_output_path: Path for final Nanite Assembly USD
       │                    │   │
       │                    │   └─ build_skeletal_nanite_assembly()  ◄─── IN nanite_assembly.py
       │                    │      │
       │                    │      │  Purpose: Build complete skeletal assembly with twig placement
       │                    │      │
       │                    │      ├─ Load Skeletal Tree USD
       │                    │      │  │
       │                    │      │  ├─ tree_stage = Usd.Stage.Open(skeletal_tree_path)
       │                    │      │  │
       │                    │      │  └─ Extract tree skeleton structure:
       │                    │      │     • joints array (["joint_0", "joint_1", ...])
       │                    │      │     • joint_parents (hierarchy)
       │                    │      │     • bind_transforms (joint matrices)
       │                    │      │
       │                    │      ├─ Extract Twig Placement Data from Tree Mesh
       │                    │      │  │
       │                    │      │  │  Purpose: Identify which twigs to instance and where
       │                    │      │  │
       │                    │      │  ├─ mesh = tree_stage.GetPrimAtPath("/TreeGeometry")
       │                    │      │  │
       │                    │      │  ├─ Read twig primvars:
       │                    │      │  │  • twig_long = mesh.GetPrimvar("TwigLong").Get()
       │                    │      │  │  • twig_short = mesh.GetPrimvar("TwigShort").Get()
       │                    │      │  │  • twig_upward = mesh.GetPrimvar("TwigUpward").Get()
       │                    │      │  │  • twig_dead = mesh.GetPrimvar("TwigDead").Get()
       │                    │      │  │
       │                    │      │  └─ For each face with twig_id > 0:
       │                    │      │     │
       │                    │      │     ├─ Determine twig type and variant
       │                    │      │     │
       │                    │      │     ├─ Calculate twig placement:
       │                    │      │     │  • face_center_position (from vertex positions)
       │                    │      │     │  • face_normal_direction (for orientation)
       │                    │      │     │  • rotation (align twig to branch)
       │                    │      │     │
       │                    │      │     └─ Store placement data:
       │                    │      │        {
       │                    │      │          "twig_type": "long_01",
       │                    │      │          "position": (x, y, z),
       │                    │      │          "rotation": (rx, ry, rz),
       │                    │      │          "scale": (sx, sy, sz),
       │                    │      │          "parent_joint": joint_idx  ← FROM bone_id primvar
       │                    │      │        }
       │                    │      │
       │                    │      ├─ Create Nanite Assembly USD Stage
       │                    │      │  │
       │                    │      │  ├─ assembly_stage = Usd.Stage.CreateNew(assembly_output_path)
       │                    │      │  │
       │                    │      │  ├─ Create SkelRoot for entire assembly
       │                    │      │  │  assembly_root = UsdSkel.Root.Define(stage, "/Assembly")
       │                    │      │  │
       │                    │      │  └─ Copy tree skeleton to assembly
       │                    │      │     skel = UsdSkel.Skeleton.Define(stage, "/Assembly/Skeleton")
       │                    │      │     └─ Copy joints, bind_transforms, rest_transforms from tree
       │                    │      │
       │                    │      ├─ Add Tree Mesh Reference
       │                    │      │  │
       │                    │      │  ├─ tree_mesh_ref = assembly_stage.DefinePrim("/Assembly/TreeMesh")
       │                    │      │  │
       │                    │      │  ├─ tree_mesh_ref.GetReferences().AddReference(skeletal_tree_path)
       │                    │      │  │  └─ Reference skeletal tree USD
       │                    │      │  │
       │                    │      │  └─ Bind tree mesh to assembly skeleton
       │                    │      │     binding_api = UsdSkel.BindingAPI.Apply(tree_mesh_ref)
       │                    │      │     binding_api.CreateSkeletonRel().SetTargets(["/Assembly/Skeleton"])
       │                    │      │
       │                    │      ├─ Add Twig Instances with Joint Binding
       │                    │      │  │
       │                    │      │  │  Purpose: Instance skeletal twigs and bind to tree joints
       │                    │      │  │
       │                    │      │  └─ For each twig placement:
       │                    │      │     │
       │                    │      │     ├─ Create twig instance prim:
       │                    │      │     │  twig_prim = assembly_stage.DefinePrim(f"/Assembly/Twig_{idx}")
       │                    │      │     │
       │                    │      │     ├─ Add reference to skeletal twig USD:
       │                    │      │     │  twig_path = f"{twig_bundle_dir}/{twig_type}.usda"
       │                    │      │     │  twig_prim.GetReferences().AddReference(twig_path)
       │                    │      │     │
       │                    │      │     ├─ Set twig transform (position, rotation, scale)
       │                    │      │     │
       │                    │      │     ├─ Bind twig to parent joint:
       │                    │      │     │  │
       │                    │      │     │  │  CRITICAL: Each twig binds to a specific tree joint
       │                    │      │     │  │           This creates the branch→twig skeletal connection
       │                    │      │     │  │
       │                    │      │     │  ├─ binding_api = UsdSkel.BindingAPI.Apply(twig_prim)
       │                    │      │     │  │
       │                    │      │     │  ├─ binding_api.CreateSkeletonRel().SetTargets(["/Assembly/Skeleton"])
       │                    │      │     │  │  └─ Bind to assembly skeleton (not twig's own skeleton)
       │                    │      │     │  │
       │                    │      │     │  └─ Set joint binding via parent joint index
       │                    │      │     │     └─ Twig's root joint inherits transform from tree's branch joint
       │                    │      │     │        This is how twigs move with tree branches in Unreal
       │                    │      │     │
       │                    │      │     └─ Result: Skeletal twig instance bound to tree joint
       │                    │      │
       │                    │      ├─ Set Assembly Metadata
       │                    │      │  │
       │                    │      │  ├─ Set default prim: assembly_stage.SetDefaultPrim(assembly_root)
       │                    │      │  │
       │                    │      │  ├─ Add metadata:
       │                    │      │  │  • species_name
       │                    │      │  │  • total_joints_count
       │                    │      │  │  • twig_instance_count
       │                    │      │  │  • creation_timestamp
       │                    │      │  │
       │                    │      │  └─ Set up axis and units for Unreal Engine
       │                    │      │     UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
       │                    │      │     UsdGeom.SetStageMetersPerUnit(stage, 0.01)  # cm units
       │                    │      │
       │                    │      └─ assembly_stage.Save() → Final Nanite Assembly USD
       │                    │         │
       │                    │         └─ Output: {output_dir}/{species_name}_nanite_assembly.usda
       │                    │            │
       │                    │            └─ Contents:
       │                    │               • Skeletal tree mesh with full UsdSkel structure
       │                    │               • Skeletal twig instances positioned on branches
       │                    │               • Joint hierarchy shared by tree and all twigs
       │                    │               • Complete binding for Unreal Engine skeletal import
       │                    │               • Ready for Nanite virtualized geometry in UE5
       │                    │
       │                    └─ RETURN: Skeletal Nanite Assembly USD file

### Export Output File Structure

After running `generate_forest.py`, the output directory contains:

```

output/forest/
├── forest_data.csv                 # Species, position, height, growth_cycles per tree
├── Oak/                            # Per-species directories
│   ├── twigs/                      # Skeletal twig bundle (copied from data/assets/twigs)
│   │   ├── twig_long_01.usda      # Skeletal twig with root joint
│   │   ├── twig_short_01.usda     # Skeletal twig with root joint
│   │   └── ...                     # All twig variants for this species
│   ├── Oak_tree_0001.usda         # Skeletal tree USD (intermediate - tree only)
│   ├── Oak_tree_0002.usda         # Multiple trees per species
│   ├── ...
│   └── Oak_nanite_assembly_0001.usda    # FINAL: Skeletal assembly (tree + twigs)
│       └── Contains:
│           • /Assembly/Skeleton         # Shared UsdSkel skeleton
│           • /Assembly/TreeMesh         # Reference to skeletal tree
│           • /Assembly/Twig_0001        # Twig instance bound to joint_42
│           • /Assembly/Twig_0002        # Twig instance bound to joint_58
│           • ... (all twig placements)
│
├── Maple/                          # Another species
│   ├── twigs/
│   │   └── ...
│   ├── Maple_tree_0001.usda
│   └── Maple_nanite_assembly_0001.usda
│
└── ... (more species)

```

**Key File Types:**

1. **Skeletal Tree USD** (`{species}_tree_{idx:04d}.usda`)
   - Contains: Tree mesh geometry only
   - Structure: SkelRoot → Skeleton → Mesh (with binding)
   - Primvars: TwigLong, TwigShort, bone_id, bone_weight
   - Purpose: Intermediate file for assembly creation

2. **Skeletal Twig USD** (`twig_{type}_{variant:02d}.usda`)
   - Contains: Single twig mesh with root joint
   - Structure: SkelRoot → Skeleton (1-2 joints) → Mesh
   - Created in: Twig export phase (export_twigs.py)
   - Purpose: Reusable skeletal twig assets

3. **Skeletal Nanite Assembly USD** (`{species}_nanite_assembly_{idx:04d}.usda`)
   - Contains: Complete skeletal tree with all twig instances
   - Structure: Assembly SkelRoot → Shared Skeleton → TreeMesh + Twig instances
   - Joint Binding: Each twig bound to specific tree joint
   - Purpose: Final USD for Unreal Engine import
   - Import to: UE5 as Skeletal Mesh with Nanite enabled
```

---

## 8. Key Data Flow: From Grove Bones to USD jointIndices

### Step-by-Step Data Transformation

```
┌──────────────────────────────────────────────────────────────────────┐
│ GROVE BONE DATA (from tag_bone_id)                                  │
│                                                                       │
│ bones_info[i] = (                                                    │
│   bone_idx,        # Grove's bone ID (index in tree)                 │
│   parent_idx,      # Parent bone ID (-1 for root)                    │
│   head_pos,        # Grove Vector - bone start position             │
│   tail_pos,        # Grove Vector - bone end position               │
│   radius           # Bone thickness                                  │
│ )                                                                    │
│                                                                       │
│ Also returned: model.point_attribute_bone_id[]                      │
│   ↓                                                                   │
│   Maps each VERTEX to a bone_id                                     │
│   └─ Used for skinning weights                                      │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ BUILD JOINT HIERARCHY (in add_skeleton_to_usd)                      │
│                                                                       │
│ Loop through bones_info:                                            │
│                                                                       │
│ bone[0] = 0, bone[1] = -1  →  joint_0, parent = -1 (ROOT)           │
│ bone[0] = 1, bone[1] = 0   →  joint_1, parent = 0  (child of root) │
│ bone[0] = 2, bone[1] = 0   →  joint_2, parent = 0  (child of root) │
│ bone[0] = 3, bone[1] = 1   →  joint_3, parent = 1  (child of j1)   │
│ bone[0] = 4, bone[1] = 2   →  joint_4, parent = 2  (child of j2)   │
│                                                                       │
│ bone_to_joint mapping:                                              │
│   -1 → 0 (root bone maps to root joint)                             │
│   0 → 1  (bone 0 maps to joint 1)                                   │
│   1 → 2  (bone 1 maps to joint 2)                                   │
│   2 → 3  (bone 2 maps to joint 3)                                   │
│   ...                                                                │
│                                                                       │
│ joint_parents array built:                                          │
│   position 0: -1 (root has no parent)                               │
│   position 1: 0  (joint_1's parent is joint_0)                      │
│   position 2: 0  (joint_2's parent is joint_0)                      │
│   position 3: 1  (joint_3's parent is joint_1)                      │
│   position 4: 2  (joint_4's parent is joint_2)                      │
│                                                                       │
│ Result: joint_parents = [-1, 0, 0, 1, 2]                           │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ USD SKELETON ATTRIBUTES (Final Result)                              │
│                                                                       │
│ Skeleton Prim {                                                     │
│   joints: ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4"]  │
│                                                                       │
│   jointIndices: [-1, 0, 0, 1, 2]  ◄─── THE ANSWER!                │
│     └─ Position i stores parent index of joint i                    │
│     └─ -1 means "no parent" (root joint)                            │
│                                                                       │
│   bindTransforms: [Matrix4d, Matrix4d, ...]                         │
│     └─ Local transforms relative to parent                          │
│                                                                       │
│   restTransforms: [Matrix4d, Matrix4d, ...]                         │
│     └─ T-pose transforms                                            │
│ }                                                                    │
│                                                                       │
│ Mesh Binding {                                                      │
│   jointIndicesPrimvar: [                                            │
│     0, 0,  ← vertex 0 influenced by joint_0 (primary) + padding    │
│     0, 0,  ← vertex 1 influenced by joint_0                        │
│     1, 0,  ← vertex 2 influenced by joint_1                        │
│     2, 0,  ← vertex 3 influenced by joint_2                        │
│     3, 0,  ← vertex 4 influenced by joint_3                        │
│     ...                                                              │
│   ]                                                                  │
│   └─ elementSize=2 means pairs (primary_joint, secondary_joint)    │
│   └─ Derived from model.point_attribute_bone_id[vertex_idx]       │
│                                                                       │
│   jointWeightsPrimvar: [                                            │
│     1.0, 0.0,  ← vertex 0 fully influenced by joint_0             │
│     1.0, 0.0,  ← vertex 1 fully influenced by joint_0             │
│     1.0, 0.0,  ← vertex 2 fully influenced by joint_1             │
│     ...                                                              │
│   ]                                                                  │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
                    EXPORTED TO USD FILE
                              ↓
         Used by Unreal Engine for skeletal mesh deformation
```

---

## 9. Module Responsibilities (Refactored Structure)

## 9. Module Responsibilities (Refactored Structure)

### Core Modules (src/growpy/core/)

#### `skeleton.py` (NEW - moved from io/)

- **Pure computation** for skeleton structures
- **WHERE JOINTINDICES ARE CALCULATED** ◄─── Core bone logic
- **Responsibilities**:
  - **Builds joint hierarchy** from bone tuples with parent indices
  - **Creates jointIndices array** from bone parent relationships
  - **Calculates vertex skinning weights** from `model.point_attribute_bone_id`
  - No USD I/O - pure Python data structures

**Key Functions:**

- `build_skeleton_structure(bones_info)` - Build joint hierarchy
- `calculate_joint_indices(bones_info)` - Create jointIndices array
- `calculate_vertex_weights(model, bones_info)` - Skinning weight calculation

#### `twig.py` (NEW - moved from io/)

- **Pure computation** for twig placement
- **Responsibilities**:
  - Extracts twig placement data from Grove model
  - Calculates twig transforms (position, rotation, scale)
  - TwigPlacement dataclass for structured data
  - No USD I/O - pure geometric calculations

**Key Functions:**

- `extract_twig_data(model)` - Extract from Grove model
- `calculate_twig_transforms(positions, normals)` - Compute orientations
- `TwigPlacement` - Data structure for placement info

#### `grove.py` (existing)

- **Functions**: `create_grove()`, `add_tree_to_grove()`
- **Responsibilities**:
  - Creates Grove instances with species presets
  - Wraps Grove 2.2 API calls for tree addition
  - Manages random seeds and grove configuration

#### `forest.py` (existing)

- **Functions**: `create_forest()`, `simulate_forest_growth()`
- **Responsibilities**:
  - Creates multi-species forest with multiple groves
  - Implements inter-species light competition simulation
  - Orchestrates grove-level growth simulation
  - Returns fully simulated groves for export

### IO Modules (src/growpy/io/)

#### `tree_export.py` (NEW - combines blender_export + usd_builder)

- **Entry point**: `export_tree()`
- **Responsibilities**:
  - **Main orchestration** for tree export from pre-simulated groves
  - Calls `grove.tag_bone_id()` BEFORE model building (CRITICAL!)
  - Calls `grove.build_models()` to get model with bone IDs baked in
  - Creates USD stage with mesh geometry from Grove model
  - Extracts vertex/face/UV data directly from Grove API
  - Adds Grove face/point attributes as primvars
  - **Adds skeleton to USD** using `core.skeleton` for computation
  - Handles material/texture lookup and bundling
  - Saves complete skeletal USD file (tree mesh + skeleton)

**Key Functions:**

- `export_tree()` - Main entry point (replaces `export_grove_tree_as_usda_native()`)
- `build_tree_mesh()` - Creates mesh geometry (replaces `build_tree_usd()`)
- `add_skeleton_to_stage()` - Add UsdSkel structure (uses core.skeleton)
- `add_tree_materials()` - Material setup
- `get_twig_usd_map_for_species()` - Twig asset lookup

#### `twig_export.py` (RENAMED from blender_twig_processor.py)

- **Entry point**: `export_twigs_from_blend()`
- **Responsibilities**:
  - Exports twig meshes from .blend files to USD
  - Creates single-bone skeleton for twigs
  - Batch processes twig directories

**Key Functions:**

- `export_twigs_from_blend()` - Main export from .blend
- `create_single_bone_skeleton()` - Add root skeleton
- `process_twig_directory()` - Batch processing

#### `assembly.py` (RENAMED from unreal_nanite_assembly.py)

- **Entry point**: `create_assembly()`
- **Responsibilities**:
  - **Composes final assembly** from tree + twig meshes
  - References external skeletal tree USD files
  - References external skeletal twig USD files
  - Creates PointInstancer for twig instances with bindJoints
  - Uses `core.twig` for twig placement calculations
  - Applies engine-specific schemas (NaniteAssemblyRootAPI, etc.)
  - Sets up proper USD composition for engine import

**Key Functions:**

- `create_assembly()` - Main assembly creation (replaces `create_nanite_assembly_usd()`)
- `validate_assembly()` - Assembly structure validation
- `add_twig_instances()` - PointInstancer setup (uses core.twig)

### Config Module (src/growpy/config/)

#### `quality.py` (ENHANCED)

- **Functions**: `get_quality_preset()`, `get_lod_configs()`
- **Responsibilities**:
  - Quality presets for tree model building
  - LOD configuration management
  - Consolidated from io/export.py
- **Functions**: `create_grove()`, `add_tree_to_grove()`
- **Responsibilities**:
  - Creates Grove instances with species presets
  - Wraps Grove 2.2 API calls for tree addition
  - Manages random seeds and grove configuration

### `core/forest.py`

- **Functions**: `create_forest()`, `simulate_forest_growth()`
- **Responsibilities**:
  - Creates multi-species forest with multiple groves
  - Implements inter-species light competition simulation
  - Orchestrates grove-level growth simulation
  - Returns fully simulated groves for export

---

## 10. Where jointIndices Are Set (THE ANSWER)

### Location: `src/growpy/core/skeleton.py` (computation) + `src/growpy/io/tree_export.py` (USD I/O)

**Functions**:

- `core.skeleton.calculate_joint_indices()` - Pure computation
- `io.tree_export.add_skeleton_to_stage()` - USD integration

**Code snippet** (lines ~245-255):

```python
# CRITICAL: jointIndices array set here
try:
    # Try using official API first (newer USD versions)
    skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(joint_parents))
except AttributeError:
    # Fallback for older USD versions
    from pxr import Sdf
    
    joint_indices_attr = skel_prim.GetPrim().CreateAttribute(
        "jointIndices",
        Sdf.ValueTypeNames.IntArray,
        custom=False,
        variability=Sdf.VariabilityUniform,
    )
    joint_indices_attr.Set(Vt.IntArray(joint_parents))
```

**What happens**:

1. `joint_parents` array is built as we loop through `bones_info` from Grove
2. Each element stores the parent joint index for that position's joint
3. The array is set as the `jointIndices` attribute on the Skeleton prim
4. This encodes the entire hierarchy in a single flat array

---

## 11. When Skeleton Is Created (Timeline)

```
Tree Export Timeline:
─────────────────────────────────

Time: 0ms
├─ Single-tree Grove created
└─ Tree growth simulated

Time: 10ms
├─ grove.tag_bone_id() called ◄─── BONES TAGGED
│  └─ Returns bone structure with parent relationships
├─ grove.build_models() called
│  └─ Models include point_attribute_bone_id from tagging
└─ model.triangulate()

Time: 20ms
├─ build_tree_mesh() creates base USD with mesh
│  └─ Mesh + primvars + materials
└─ Save temp_tree_path (static mesh, no skeleton)

Time: 25ms (SKELETON CREATION PHASE)
├─ Copy temp_tree_path → skeletal_tree_path
└─ add_skeleton_to_stage(skeletal_tree_path) ◄─── SKELETON ADDED HERE
   │
   ├─ grove.tag_bone_id() called AGAIN
   │  └─ Gets bone structure with parent relationships
   │
   ├─ Build joint hierarchy from bones
   │  └─ Create joint_parents array
   │
   ├─ Create USD Skeleton structure
   │  └─ UsdSkel.Skeleton prim
   │
   ├─ SET jointIndices attribute ◄─── jointIndices SET HERE
   │  └─ skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(joint_parents))
   │
   ├─ Add skinning weights to mesh
   │  └─ mesh.CreateJointIndicesPrimvar() ← MESH joint influence data
   │
   └─ stage.Save()

Time: 30ms
└─ Export complete, USD file with skeleton ready
```

---

## 12. Data Structure: jointIndices Explained

### Definition

`jointIndices` is an **IntArray attribute** on the `Skeleton` prim that encodes parent-child relationships.

### Format

```
jointIndices[i] = parent_joint_index_of_joint_i

Example for a 4-level tree:
─────────────────────────────
Joint 0 (root):       jointIndices[0] = -1  (no parent)
Joint 1 (branch):     jointIndices[1] = 0   (parent is joint 0)
Joint 2 (twig):       jointIndices[2] = 1   (parent is joint 1)
Joint 3 (tip):        jointIndices[3] = 2   (parent is joint 2)

Result: jointIndices = [-1, 0, 1, 2]
```

### Why It's Needed

- **Skeletal hierarchy** must be preserved in USD for Unreal Engine animation
- **Bone deformation** relies on parent-child relationships
- **Forward kinematics** uses jointIndices to propagate transforms

### Related: Mesh Joint Influences

A separate `jointIndicesPrimvar` exists on the Mesh prim:

```
Mesh jointIndicesPrimvar[vertex_i * elementSize + j] = joint_index

This tells which joints influence each vertex:
- elementSize=2 means each vertex has 2 influences (primary + secondary)
- Paired with jointWeightsPrimvar for weighted blending
```

---

## 13. Skeleton Creation Prerequisites

```
For skeleton creation to work correctly:

1. ✓ Grove instance with simulated tree
   └─ grove.simulate(flushes=N) must be called

2. ✓ tag_bone_id() callable on grove
   └─ Requires The Grove 2.2 API
   └─ Parameters: length, reduce, bias, connected

3. ✓ Model with bone attributes
   └─ model.point_attribute_bone_id[]
   └─ model.point_attribute_bone_weight[]

4. ✓ USD stage with mesh already present
   └─ usd_builder.build_tree_usd() must have been called first
   └─ Skeleton is added to existing USD, not created from scratch

5. ✓ USD Python (pxr) available
   └─ Via Blender's bundled USD (recommended)
All prerequisites checked in:
- tree_export.export_tree() - orchestration
- core.skeleton - skeleton computation
- io.tree_export.add_skeleton_to_stage() - USD skeleton creation
- tree_export.export_tree() - orchestration
- skeleton.add_skeleton_to_stage() - skeleton creation
```

---

## 14. Quality Parameters' Role in Skeleton Creation

```
Skeleton Parameters (passed through generate_forest.py):

--skeleton-length FLOAT (default: 1.0)
  └─ Multiplier for bone lengths
  └─ Passed to: grove.tag_bone_id(skeleton_length, ...)
  └─ Effect: Longer values create longer, merged bones

--skeleton-reduce FLOAT (default: 0.25, range: 0-1)
  └─ Reduction factor for number of bones
  └─ Passed to: grove.tag_bone_id(..., skeleton_reduce, ...)
  └─ Effect: Higher values = fewer bones in skeleton

--skeleton-bias FLOAT (default: 0.5, range: 0-1)
  └─ Weight bias for skinning
  └─ Passed to: grove.tag_bone_id(..., skeleton_bias, ...)
  └─ Effect: How much primary vs. secondary joints influence vertices

--skeleton-connected BOOL (default: True)
  └─ Connected bone hierarchy vs. disconnected
  └─ Passed to: grove.tag_bone_id(..., connected=skeleton_connected)
  └─ Effect: Connected maintains parent-child relationships (jointIndices matter)
  └─          Disconnected creates floating bones (jointIndices less critical)

All flow through:
  generate_forest_exports()
    └─ quality_params dict
    └─ export_grove_tree_as_usda_native()
    └─ grove.tag_bone_id(skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected)
    └─ add_skeleton_to_usd()
    └─ jointIndices built from bone parent relationships
```

---

## 15. Complete Export Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                   GENERATE_FOREST.PY                            │
│                 (CLI Entry Point)                               │
└────────────────┬───────────────────────────────────────────────┘
                 │
         ┌───────┴────────┬──────────────┐
         ▼                ▼              ▼
    ┌─────────┐   ┌──────────┐  ┌─────────────┐
    │ Config  │   │ Forest   │  │ Quality     │
    │ (Assets)│   │Simulation│  │Parameters   │
    └─────────┘   └──────────┘  └─────────────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
         ┌────────────────────────────┐
         │ export_individual_trees()  │
         │ (Loop over forest trees)   │
         └────────────────────────────┘
                        │
                        │ (for each tree)
                        ▼
         ┌──────────────────────────────────┐
         │ _export_single_tree_from_forest()│
         │ (Worker function)                │
         └────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
   ┌─────────────┐          ┌──────────────────┐
   │Grove Sim    │          │Mesh Generation   │
   │             │          │ & Tagging        │
   │ • Create    │          │                  │
   │ • Simulate  │          │ 1. tag_bone_id() │ ◄── BONES TAGGED
   │ • Tag Bones │          │ 2. build_models()│
   └─────────────┘          │ 3. triangulate() │
                            └──────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
            ┌──────────────────┐      ┌──────────────────────┐
            │ tree_export.py   │      │ tree_export.py       │
            │                  │      │                      │
            │ build_tree_mesh()│      │ Orchestration Layer  │
            │                  │      │                      │
            │ • Geometry       │      │ • Parameter passing  │
            │ • Primvars       │      │ • Asset bundling     │
            │ • Materials      │      │ • Validation         │
            │ • Save stage     │      └──────────────────────┘
            └─────┬────────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ Static Tree USD  │ (mesh + materials, NO skeleton)
         └─────────┬────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ skeleton.py          │ ◄── SKELETON CREATION PHASE
        │                      │
        │ add_skeleton_to_     │
        │ stage()              │
        │                      │
        │ • tag_bone_id()      │ ◄── BONES RETRIEVED AGAIN
        │ • Build hierarchy    │
        │ • jointIndices SET   │ ◄──── THE ANSWER IS HERE!
        │ • Skinning weights   │
        │ • SkelRoot/Skeleton  │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────┐
        │ Skeletal Tree    │ (mesh + materials + skeleton + jointIndices)
        │ USD              │
        └──────┬───────────┘
               │
               ├──────────────────────┐
               │                      │
               ▼                      ▼
        ┌────────────┐      ┌─────────────────────┐
        │ Save as    │      │ assembly.py         │
        │ Final Tree │      │                     │
        │ USD        │      │ create_assembly()   │
        └────────────┘      │                     │
                            │ • Add twig refs     │
                            │ • UE5 metadata      │
                            │ • Point instancing  │
                            │                     │
                            └─────┬───────────────┘
                                  │
                                  ▼
                        ┌──────────────────┐
                        │ Nanite Assembly  │
                        │ USD (UE5 format) │
                        └──────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
            ┌──────────────┐         ┌──────────────────┐
            │ Validation   │         │ Output in        │
            │ (jointIndices│         │ data/output/     │
            │  structure)  │         │ forest/          │
            └──────────────┘         │ species_name/    │
                                     └──────────────────┘
```

---

## 16. Summary: jointIndices Creation Path

**Architecture**: GrowPy ALWAYS creates skeletal meshes. There is no static mesh export option - all trees and twigs are exported with complete skeleton structures for Unreal Engine's Nanite skeletal mesh system.

**Question**: At what point is the skeleton created and where are jointIndices set?

1. **Skeleton Creation Phase**: `add_skeleton_to_stage()` in `io/tree_export.py` (uses `core/skeleton.py` for computation, called from `export_tree()`)
**Answer**:

1. **Skeleton Creation Phase**: `add_skeleton_to_stage()` in `skeleton.py` (called from `tree_export.export_tree()`)

2. **jointIndices Location**: Set in `add_skeleton_to_stage()` around line 245:

   ```python
   skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(joint_parents))
   ```

3. **Data Source**: `joint_parents` array, built by looping through `grove.tag_bone_id()` results

4. **Format**: Each position `i` in the array stores the parent joint index of joint `i`, with `-1` for root

5. **Related Mesh Binding**: Mesh also gets `jointIndicesPrimvar` (derived from `model.point_attribute_bone_id`) which tells which joints influence each vertex

This dual jointIndices system:

- **Skeleton jointIndices**: Encodes bone hierarchy
- **Mesh jointIndicesPrimvar**: Encodes vertex-to-bone influences
- Together they enable skeletal mesh deformation in Unreal Engine

---

## 17. Optimization: Single-Pass Export (No Re-Simulation)

### The Problem (Original Implementation)

The original export pipeline was inefficient:

1. Forest simulation creates all groves with all trees and simulates them (ONCE)
2. Then during export, for EACH tree, a NEW single-tree grove is created
3. That new grove is simulated AGAIN from scratch to get the tree
4. Finally the tree is exported

**Result**: Each tree simulates `growth_cycles * total_trees` times instead of just once!

### The Solution (Current Implementation)

The optimized pipeline:

1. Forest simulation creates all groves with all trees and simulates them (ONCE)
2. During export, each tree is exported DIRECTLY from the already-simulated grove
3. No re-simulation occurs
4. Significantly faster (especially with many trees or high cycle counts)

### How It Works

```python
# Forest simulation phase (happens once)
forest = create_forest(forest_data)
simulate_forest_growth(forest, max_cycles)
# Result: forest is list of (grove, species_name, tree_count) tuples
#         Each grove contains fully simulated trees with light competition effects

# Export phase (uses pre-simulated groves)
export_individual_trees(forest, forest_data, ...)
  │
  └─ for each tree in forest_data:
     └─ grove = grove_map[species]  # ◄─── Already simulated!
     └─ tree_export.export_tree(grove, ...)
```

### Performance Impact

**Before optimization**:

- 10 trees × 10 growth cycles = 100 simulations
- Plus one initial forest simulation = 101 total simulations

**After optimization**:

- 1 forest simulation
- 0 re-simulations during export
- ~100x faster export phase!

### Trade-offs

- **Advantage**: Preserves inter-species light competition effects (trees that were in the original forest)
- **Advantage**: Single simulation pass is much faster
- **Limitation**: All trees of same species share the same grove (in current implementation)
  - For independent trees with different growth parameters, override with `--no-forest-simulation` flag if added

### Code Changes

**Modified functions**:

- `export_individual_trees()`: Now accepts `forest` parameter with pre-simulated groves
- `_export_single_tree_from_forest()`: Now exports directly from grove, no re-simulation
- `generate_forest_exports()`: Passes forest to export function

**Key optimization**:

```python
# OLD: Re-simulate each tree
grove = create_grove(species)
grove.add_new_tree(...)
grove.simulate(flushes=growth_cycles)  # ◄─── REMOVED

# NEW: Use already-simulated grove
grove = grove_map[species]  # ◄─── Retrieved from forest
# No simulation needed!
```
