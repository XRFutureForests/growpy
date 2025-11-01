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
                               ├─ PHASE 1A: SKELETON PRE-TAGGING (CRITICAL!)
                               │   │
                               │   │  Purpose: Tag skeleton BEFORE building models
                               │   │           This bakes bone_id into model vertices
                               │   │
                               │   └─ grove.tag_bone_id(skeleton_length, skeleton_reduce, 
                               │                         skeleton_bias, skeleton_connected)
                               │       │
                               │       ├─ Input: Skeleton quality parameters
                               │       │   • skeleton_length: 0.0 (no length limits → keep all bones)
                               │       │   • skeleton_reduce: 0.0 (no reduction → keep all bones)
                               │       │   • skeleton_bias: 0.5 (weight distribution)
                               │       │   • skeleton_connected: True (parent-child hierarchy)
                               │       │
                               │       └─ Effect: TAGS the grove's internal tree structure
                               │           ◄─── THIS IS WHERE MESH-TO-SKELETON MAPPING IS DEFINED!
                               │           Grove internally marks which mesh vertices belong to which bones
                               │           Subsequent build_models() will include this mapping
                               │
                               ├─ PHASE 1B: MODEL BUILDING (Generate geometry WITH bone mapping)
                               │   │
                               │   │  Purpose: Build 3D tree mesh from Grove simulation data
                               │   │           NOW includes bone_id because tag_bone_id() was called first
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
                               │           • point_attribute_bone_id[] ◄─── CRITICAL: vertex→bone mapping!
                               │           • point_attribute_bone_weight[] ◄─── vertex influence weights!
                               │           
                               │           These bone attributes exist ONLY if tag_bone_id() was called first!
                               │           This is the MESH-TO-SKELETON MAPPING (also called SKINNING data)
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
                               │           IMPORTANT: Preserves bone_id and bone_weight during triangulation
                               │
                               ├─ PHASE 2B: SKELETON STRUCTURE EXTRACTION
                               │   │
                               │   │  Purpose: Extract bone hierarchy separately (for skeleton joints)
                               │   │           This is DIFFERENT from the vertex mapping done in Phase 1A
                               │   │
                               │   └─ skeletons = grove.build_skeletons()
                               │       │
                               │       └─ Returns: Skeleton objects with bone hierarchy
                               │           • skeleton.points → joint positions
                               │           • skeleton.poly_lines → bone connections (parent-child)
                               │           
                               │           NOTE: This creates the SKELETON JOINTS structure
                               │           The MESH-TO-SKELETON MAPPING already exists from Phase 1A/1B
                               │           in model.point_attribute_bone_id[]
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
       │                    │      │  ├─ SKELETAL SKINNING DATA (Vertex-Varying): ◄─── MESH-TO-SKELETON MAPPING!
       │                    │      │  │  │
       │                    │      │  │  │  This is the MAPPING that connects mesh vertices to skeleton bones
       │                    │      │  │  │  Data comes from Phase 1A (tag_bone_id) and Phase 1B (build_models)
       │                    │      │  │  │
       │                    │      │  │  ├─ bone_id: model.point_attribute_bone_id
       │                    │      │  │  │  └─ Per-vertex bone index (which bone influences this vertex)
       │                    │      │  │  │     Example: [0, 0, 0, 1, 1, 2, 2, 2, ...] (vertex 0-2 → bone 0, etc.)
       │                    │      │  │  │
       │                    │      │  │  └─ bone_weight: model.point_attribute_bone_weight
       │                    │      │  │     └─ Per-vertex influence weight (0.0-1.0, how much bone affects vertex)
       │                    │      │  │        Example: [1.0, 0.8, 0.6, 1.0, 0.9, ...]
       │                    │      │  │
       │                    │      │  │  TERMINOLOGY:
       │                    │      │  │  • MAPPING: The relationship (which vertex connects to which bone)
       │                    │      │  │  • SKINNING: The weighted influence (how much each bone affects vertex)
       │                    │      │  │  Both are stored in point_attribute_bone_id and point_attribute_bone_weight
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
       │                    │      │  │  Note: These bone attributes are exported as USD primvars in Phase 3
       │                    │      │  │        They will be converted to UsdSkel format in Phase 4
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
       │                    ├─ PHASE 4: USD SKELETON CREATION (Build UsdSkel structure)
       │                    │   │
       │                    │   │  Purpose: Create USD skeleton structure from Grove skeleton data
       │                    │   │           USES the bone_id mapping already computed in Phase 1A/1B
       │                    │   │           Converts bone_id to UsdSkel jointIndices format
       │                    │   │
       │                    │   └─ add_skeleton_to_usd(stage, grove, skeleton)  ◄─── IN io/tree_export.py
       │                    │      │
       │                    │      ├─ stage = Usd.Stage.Open(skeletal_tree_path)
       │                    │      │
       │                    │      ├─ Extract bone hierarchy from skeleton object
       │                    │      │  │
       │                    │      │  │  Purpose: Get bone joint structure (NOT vertex mapping)
       │                    │      │  │           Vertex mapping already exists in model.point_attribute_bone_id
       │                    │      │  │
       │                    │      │  ├─ skeleton.points → joint positions
       │                    │      │  ├─ skeleton.poly_lines → bone connections
       │                    │      │  │
       │                    │      │  └─ This creates the SKELETON JOINTS (parent-child hierarchy)
       │                    │      │     NOT the mesh-to-skeleton mapping (that's from Phase 1A/1B)
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
       │                    │      ├─ Convert bone_id to UsdSkel format ◄─── USES PRE-COMPUTED MAPPING!
       │                    │      │  │
       │                    │      │  │  Purpose: Convert Grove's bone_id to USD's jointIndices format
       │                    │      │  │           The mapping was already computed in Phase 1A/1B!
       │                    │      │  │           We're just reformatting it for USD
       │                    │      │  │
       │                    │      │  └─ For each vertex:
       │                    │      │     │
       │                    │      │     ├─ bone_id = model.point_attribute_bone_id[vertex_idx] ◄─── FROM PHASE 1B!
       │                    │      │     │  └─ This was set by grove.build_models() after tag_bone_id()
       │                    │      │     │
       │                    │      │     ├─ joint_idx = bone_to_joint[bone_id]
       │                    │      │     │  └─ Convert Grove bone index to USD joint index
       │                    │      │     │
       │                    │      │     └─ Append to joint_indices_array: [joint_idx, 0]
       │                    │      │        └─ elementSize=2 (primary influence + padding for secondary)
       │                    │      │
       │                    │      ├─ binding.CreateJointIndicesPrimvar(False, 2) ◄─── SET MESH BINDING!
       │                    │      │  │
       │                    │      │  │  Purpose: Store which joints influence each vertex
       │                    │      │  │           This is the SKINNING data (mesh-to-skeleton connection)
       │                    │      │  │
       │                    │      │  └─ Per-vertex data: which joint(s) deform this vertex
       │                    │      │     Example: [0,0, 0,0, 1,0, 1,0, 2,0, ...] 
       │                    │      │     Vertex 0-1 → joint 0, vertex 2-3 → joint 1, etc.
       │                    │      │
       │                    │      ├─ binding.CreateJointWeightsPrimvar(False, 2)
       │                    │      │  │
       │                    │      │  └─ Per-vertex weights: how much each joint influences vertex
       │                    │      │     Example: [1.0,0.0, 0.8,0.2, 1.0,0.0, ...]
       │                    │      │     From model.point_attribute_bone_weight (Phase 1B)
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

## 8. Mesh-to-Skeleton Binding: Mapping vs Skinning Explained

### What is the difference between "mapping" and "skinning"?

Both terms refer to connecting mesh vertices to skeleton bones, but with different emphasis:

**MAPPING** (also called "rigging" or "binding"):

- **What**: The relationship between mesh vertices and skeleton bones
- **Data**: Which bone(s) influence which vertex
- **Stored in**: `model.point_attribute_bone_id[]` (bone index per vertex)
- **Example**: "Vertex 42 is controlled by bone 5"
- **When**: Defined during `grove.tag_bone_id()` + `grove.build_models()`

**SKINNING** (also called "vertex weighting" or "weight painting"):

- **What**: The strength of influence each bone has on a vertex
- **Data**: How much each bone affects vertex deformation (0.0 to 1.0)
- **Stored in**: `model.point_attribute_bone_weight[]` (weight per vertex)
- **Example**: "Vertex 42 is influenced 80% by bone 5, 20% by bone 6"
- **When**: Computed during `grove.tag_bone_id()` + `grove.build_models()`

**In practice**, both are needed together for skeletal animation:

- **Mapping** tells which bones connect to which vertices
- **Skinning** tells how much each bone influences the vertex
- Together they enable smooth bone deformation during animation

### Where does this happen in GrowPy?

```
PHASE 1A: grove.tag_bone_id()
  └─ Tags skeleton structure in Grove's internal tree data
     Effect: Marks which mesh regions belong to which bones
     
PHASE 1B: grove.build_models()
  └─ Builds mesh WITH bone attributes (because tagging happened first)
     Output: model.point_attribute_bone_id[] ← MAPPING (which bone)
             model.point_attribute_bone_weight[] ← SKINNING (how much)
             
PHASE 4: Convert to USD format
  └─ Reads model.point_attribute_bone_id and bone_weight
     Output: USD primvars: skel:jointIndices and skel:jointWeights
```

**CRITICAL**: The mapping/skinning is computed in Phase 1, NOT Phase 4!
Phase 4 only converts the Grove format to USD format.

**Why use skeleton_length=0.0 and skeleton_reduce=0.0?**

- `skeleton_length=0.0`: No length limits → include all bones
- `skeleton_reduce=0.0`: No reduction → keep all bones
- This ensures Grove creates a bone for EVERY branch segment
- Result: Fine-grained mapping with bones matching mesh vertices
- Each mesh region has its own bone for precise animation control

---

## 9. Key Data Flow: From Grove Bones to USD jointIndices

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

## 10. Module Responsibilities (Refactored Structure)

### Core Modules (src/growpy/core/)

**Design Philosophy**: Pure computation without I/O dependencies. Core modules contain simulation logic, data structures, and calculations that can be tested independently.

#### `skeleton.py`

- **Pure skeleton computation** without USD dependencies
- **WHERE JOINTINDICES ARE CALCULATED** ◄─── Core bone logic
- **Responsibilities**:
  - **Builds joint hierarchy** from Grove bone data
  - **Creates jointIndices array** encoding parent relationships
  - **Calculates vertex skinning weights** from bone_id attributes
  - Defines data structures: `Vector3`, `JointTransform`, `SkeletonHierarchy`
  - No USD I/O - returns pure Python data structures

**Key Functions:**

- `get_bone_data_from_grove(grove, ...)` - Extract bones via `grove.tag_bone_id()`
- `build_skeleton_hierarchy(bones_info)` - Build joint hierarchy with parent indices
- `calculate_vertex_weights(model, bones_info)` - Skinning weight calculation

**Key Data Structures:**

- `Vector3` - Simple 3D vector with math operations
- `JointTransform` - Translation + rotation matrix
- `SkeletonHierarchy` - Complete skeleton structure (joints, parents, transforms)

#### `twig.py`

- **Pure twig placement computation** without USD dependencies
- **Responsibilities**:
  - Extracts twig placement data from Grove model face attributes
  - Calculates twig transforms (position, rotation, scale) from face geometry
  - Converts face normals to rotation matrices
  - `TwigPlacement` dataclass for structured data
  - No USD/Blender I/O - pure geometric calculations

**Key Functions:**

- `extract_twig_placements_from_model(model)` - Extract from Grove face attributes
- `calculate_twig_transform(position, normal, scale)` - Compute full transform
- `get_face_center_and_normal(vertices, face)` - Face geometry calculations
- `normal_to_rotation_matrix(normal)` - Convert normal to rotation

**Key Data Structures:**

- `TwigPlacement` - Twig instance data (type, position, normal, scale)

#### `grove.py`

- **Grove creation and tree addition** wrapper for Grove 2.2 API
- **Responsibilities**:
  - Creates Grove instances with species presets
  - Wraps Grove 2.2 API calls (`gc.Grove()`, `grove.add_new_tree()`)
  - Manages grove configuration and random seeds
  - Provides clean interface to Grove API

**Key Functions:**

- `create_grove(species_name, config=None, random_seed=None)` - Create and configure grove
- `add_tree_to_grove(grove, position, delay=0)` - Add tree to existing grove

#### `forest.py`

- **Multi-species forest simulation** with light competition
- **Responsibilities**:
  - Creates multi-species forest from DataFrame
  - Implements inter-species light competition during simulation
  - Orchestrates grove-level growth simulation
  - Returns fully simulated groves for export (no re-simulation needed)

**Key Functions:**

- `create_forest(forest_data: pd.DataFrame)` - Create groves per species
- `simulate_forest_growth(forest, cycles)` - Simulate with light competition

#### `tree.py`

- **Tree height/age utilities**
- **Responsibilities**:
  - Growth model loading and height-to-age conversion
  - Uses sklearn models trained in `create_growth_models.py`

**Key Functions:**

- `calculate_growth_cycles_from_height(forest_data)` - Convert heights to ages

### IO Modules (src/growpy/io/)

**Design Philosophy**: Handle external formats (USD, FBX, .blend). Use core/ modules for computation, focus on serialization/deserialization.

#### `tree_export.py`

- **Main tree export orchestration** to USD with skeleton
- **Responsibilities**:
  - **Main entry point** for tree export from pre-simulated groves
  - Calls `grove.tag_bone_id()` to get bone data
  - Calls `grove.build_models()` to generate tree geometry
  - Creates USD stage with mesh from Grove model
  - Extracts vertex/face/UV data via Grove API
  - Adds Grove attributes as USD primvars
  - **Integrates skeleton from core.skeleton** into USD
  - Handles material/texture lookup and bundling
  - Saves complete skeletal USD (tree mesh + skeleton + materials)

**Key Functions:**

- `export_tree(grove, output_path, ...)` - Main entry point
- `build_tree_mesh(model, output_path, ...)` - Create USD mesh from Grove model
- `add_skeleton_to_usd(stage, grove, ...)` - Add UsdSkel structure (uses core.skeleton)
- `add_twig_skeleton_to_usd(stage, ...)` - Add twig skeleton for standalone twigs
- `bundle_twigs_for_species(...)` - Copy twig assets to output
- `get_twig_usd_map_for_species(...)` - Twig asset lookup

#### `twig_export.py`

- **Twig .blend to skeletal USD conversion**
- **Responsibilities**:
  - Loads Blender .blend files via bpy
  - Adds single-bone root skeleton to twig meshes
  - Exports to USD with UsdSkel structure
  - Batch processing for twig directories

**Key Functions:**

- `export_twigs_from_blend(blend_path, output_dir)` - Main export
- `create_single_bone_skeleton(mesh)` - Add root joint (via bpy)
- `process_twig_directory(directory)` - Batch convert all .blend files

#### `assembly_export.py`

- **Nanite Assembly USD creation** for Unreal Engine
- **Responsibilities**:
  - **Composes final assembly** from skeletal tree + twig references
  - References external skeletal tree USD files
  - References external skeletal twig USD files
  - Creates PointInstancer for twig instances
  - Binds twig instances to tree skeleton joints
  - Uses `core.twig` for twig placement calculations
  - Applies UE-specific metadata and structure
  - Sets up USD composition for engine import

**Key Functions:**

- `create_assembly(tree_path, twig_dir, output_path, ...)` - Main assembly
- `validate_assembly(assembly_path)` - Structure validation
- `add_twig_instances(stage, placements, ...)` - PointInstancer setup

### Config Modules (src/growpy/config/)

**Design Philosophy**: Centralized configuration and asset management. No simulation logic.

#### `core.py`

- **Main GrowPyConfig class** for project configuration
- **Responsibilities**:
  - Asset path resolution (presets, textures, twigs, models)
  - Species data loading from CSV
  - Project directory management
  - Singleton pattern via `get_config()`

**Key Functions:**

- `get_config()` - Get/create singleton config instance
- `GrowPyConfig.get_preset_path(species)` - Resolve species preset
- `GrowPyConfig.get_species_data()` - Load species lookup table

#### `paths.py`

- **Path utilities** for asset management
- **Responsibilities**:
  - Standard directory getters (data/, assets/, growth_models/)
  - Asset path resolution
  - Twig file lookup by type

**Key Functions:**

- `get_data_directory()`, `get_assets_directory()`, etc.
- `get_preset_path(species)` - Preset resolution
- `get_twig_files_by_type(species, twig_type)` - Twig variant lookup

#### `quality.py`

- **Quality presets and LOD configuration**
- **Responsibilities**:
  - Quality presets (ultra/high/medium/low/performance)
  - Build parameters (resolution, cutoff, blend, skeleton)
  - LOD configuration for Unreal Engine

**Key Functions:**

- `get_quality_preset(preset_name)` - Get build parameters dict
- `get_lod_configs()` - LOD distance/quality configuration

#### `species.py`

- **Species-specific data utilities**
- **Responsibilities**:
  - Species color mapping for visualization
  - Species data from lookup table
  - Species validation

**Key Functions:**

- `get_species_data()` - Load species from CSV
- `get_species_colors()` - Species color palette

### CLI Scripts (src/growpy/cli/)

**Design Philosophy**: Thin wrappers around core/io functions. Parse CLI arguments, call functions, display progress.

#### `prepare_assets.py`

Copy assets from Grove 2.2 installation to project

#### `convert_twigs.py`

Convert .blend twig files to skeletal USD

#### `create_growth_models.py`

Generate sklearn height prediction models per species

#### `generate_forest.py`

Full forest generation pipeline (main export script)

---

## 11. Where jointIndices Are Set (THE ANSWER)

### Location: `src/growpy/core/skeleton.py` (computation) + `src/growpy/io/tree_export.py` (USD I/O)

**Refactored Architecture**: jointIndices computation is split between core (pure Python) and io (USD integration).

**Core Functions (computation only)**:

- `core.skeleton.get_bone_data_from_grove(grove, ...)` - Extract bone hierarchy from Grove
- `core.skeleton.build_skeleton_hierarchy(bones_info)` - Build joint data structure
  - Returns `SkeletonHierarchy` with `joint_parents` array (the jointIndices!)

**IO Functions (USD integration)**:

- `io.tree_export.add_skeleton_to_usd(stage, grove, ...)` - Add UsdSkel to stage
  - Calls `core.skeleton.build_skeleton_hierarchy()` for computation
  - Sets USD skeleton attributes from returned data

**Code flow**:

```python
# In io/tree_export.py::add_skeleton_to_usd()

# 1. Get bone data from Grove (calls grove.tag_bone_id())
from growpy.core.skeleton import get_bone_data_from_grove, build_skeleton_hierarchy

bones_info = get_bone_data_from_grove(grove, skeleton_length, skeleton_reduce, 
                                      skeleton_bias, skeleton_connected)

# 2. Build skeleton hierarchy (pure computation)
skeleton_hierarchy = build_skeleton_hierarchy(bones_info)

# 3. Set USD attributes
skel_prim.CreateJointsAttr().Set(Vt.TokenArray(skeleton_hierarchy.joint_names))
skel_prim.CreateBindTransformsAttr().Set(Vt.Matrix4dArray(skeleton_hierarchy.bind_transforms))
skel_prim.CreateRestTransformsAttr().Set(Vt.Matrix4dArray(skeleton_hierarchy.rest_transforms))

# CRITICAL: jointIndices set here
skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(skeleton_hierarchy.joint_parents))
```

**What happens**:

1. Grove bone data extracted via `grove.tag_bone_id()` → bone tuples with parent relationships
2. `build_skeleton_hierarchy()` computes joint hierarchy and `joint_parents` array
3. `joint_parents` contains parent index for each joint (root = -1)
4. Array is set as USD `jointIndices` attribute on Skeleton prim
5. This encodes the entire hierarchy in a single flat array

---

## 12. When Skeleton Is Created (Timeline)

```
Tree Export Timeline:
─────────────────────────────────

Time: 0ms
├─ Single-tree Grove created
└─ Tree growth simulated
Time: 25ms (SKELETON CREATION PHASE)
├─ Copy temp_tree_path → skeletal_tree_path
└─ add_skeleton_to_usd(stage, grove, ...) ◄─── SKELETON ADDED HERE
   │
   ├─ core.skeleton.get_bone_data_from_grove(grove, ...)
   │  └─ Calls grove.tag_bone_id() internally
   │  └─ Returns bones_info with parent relationships
   │
   ├─ core.skeleton.build_skeleton_hierarchy(bones_info)
   │  └─ Pure computation - builds joint hierarchy
   │  └─ Returns SkeletonHierarchy with joint_parents array
   │
   ├─ Create USD Skeleton structure
   │  └─ UsdSkel.Skeleton prim
   │
   ├─ SET jointIndices attribute ◄─── jointIndices SET HERE
   │  └─ skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(skeleton_hierarchy.joint_parents))
   │  └─ Uses computed data from core.skeleton
   │
   ├─ Add skinning weights to mesh
   │  └─ mesh.CreateJointIndicesPrimvar() ← MESH joint influence data
   │  └─ Uses core.skeleton.calculate_vertex_weights()
   │
   └─ stage.Save()

Time: 30ms
└─ Export complete, USD file with skeleton ready
```├─ Create USD Skeleton structure
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

## 13. Data Structure: jointIndices Explained

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

## 14. Skeleton Creation Prerequisites

```
For skeleton creation to work correctly:

1. ✓ Grove instance with simulated tree
   └─ grove.simulate(flushes=N) must be called
   └─ Required by: core.skeleton.get_bone_data_from_grove()

2. ✓ The Grove 2.2 API available
   └─ grove.tag_bone_id() method accessible
   └─ Parameters: length, reduce, bias, connected
   └─ Required by: core.skeleton.get_bone_data_from_grove()

3. ✓ Model with bone attributes (for skinning only)
   └─ model.point_attribute_bone_id[]
   └─ model.point_attribute_bone_weight[]
   └─ Required by: core.skeleton.calculate_vertex_weights()

4. ✓ USD stage with mesh already present (for USD export)
   └─ io.tree_export.build_tree_mesh() must be called first
   └─ Skeleton is added to existing USD stage
   └─ Required by: io.tree_export.add_skeleton_to_usd()

5. ✓ USD Python (pxr) available (for USD export only)
   └─ Via Blender's bundled USD (recommended)
   └─ Required by: io.tree_export.add_skeleton_to_usd()

Refactored Architecture Checkpoints:

- core.skeleton.get_bone_data_from_grove() - Extract bones from Grove (requires 1, 2)
- core.skeleton.build_skeleton_hierarchy() - Compute hierarchy (pure Python, no dependencies)
- core.skeleton.calculate_vertex_weights() - Compute weights (requires 3)
- io.tree_export.add_skeleton_to_usd() - USD integration (requires 4, 5)
- io.tree_export.export_tree() - Full orchestration (all prerequisites)
```

---

## 15. Quality Parameters' Role in Skeleton Creation

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

## 16. Complete Export Architecture Diagram

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
        ┌──────────────────────────────────────────────┐
        │ SKELETON CREATION PHASE (Refactored)         │
        │                                              │
        │ io/tree_export.py::add_skeleton_to_usd()    │
        └──────────┬───────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   ┌──────────────┐   ┌───────────────────────┐
   │ core/        │   │ io/tree_export.py     │
   │ skeleton.py  │   │                       │
   │              │   │ USD Integration Layer │
   │ COMPUTATION  │   │                       │
   │ ONLY         │   │ • Create UsdSkel prims│
   └──────────────┘   │ • Set USD attributes  │
         │            │ • Bind mesh to skel   │
         ├─ get_bone_data_from_grove()        │
         │  └─ grove.tag_bone_id()            │
         │                                    │
         ├─ build_skeleton_hierarchy()        │
         │  └─ Creates joint_parents array    │
         │  └─ jointIndices computed here! ◄──┼─── THE ANSWER!
         │                                    │
         ├─ calculate_vertex_weights()        │
         │  └─ Skinning weights from bone_id  │
         │                                    │
         └────────────────────────────────────┘
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
        │ Save as    │      │ io/assembly_        │
        │ Final Tree │      │ export.py           │
        │ USD        │      │                     │
        └────────────┘      │ create_assembly()   │
                            │                     │
                            │ Uses core/twig.py   │
                            │ for calculations    │
                            │                     │
                            │ • Add twig refs     │
                            │ • UE5 metadata      │
                            │ • Point instancing  │
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

## 17. Summary: jointIndices Creation Path

**Architecture**: GrowPy ALWAYS creates skeletal meshes. There is no static mesh export option - all trees and twigs are exported with complete skeleton structures for Unreal Engine's Nanite skeletal mesh system.

**Refactored Architecture**: Skeleton computation is split between `core/` (pure Python) and `io/` (USD integration).

**Question**: At what point is the skeleton created and where are jointIndices set?

**Answer** (Refactored Flow):

1. **Bone Extraction Phase**: `core.skeleton.get_bone_data_from_grove(grove, ...)`
   - Calls `grove.tag_bone_id()` internally
   - Returns bone tuples with parent relationships
   - Pure Python function, no USD dependencies

2. **Hierarchy Computation Phase**: `core.skeleton.build_skeleton_hierarchy(bones_info)`
   - Builds joint hierarchy from bone data
   - **Creates `joint_parents` array** (the jointIndices!)
   - Returns `SkeletonHierarchy` dataclass
   - Pure Python computation, testable in isolation

3. **USD Integration Phase**: `io.tree_export.add_skeleton_to_usd(stage, grove, ...)`
   - Calls steps 1 and 2 to get skeleton data
   - Creates USD Skeleton prim
   - **Sets jointIndices attribute**:

     ```python
     skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(skeleton_hierarchy.joint_parents))
     ```

   - Called from `io.tree_export.export_tree()`

4. **Data Source**: `joint_parents` array computed in step 2 from Grove bone relationships

5. **Format**: Each position `i` stores the parent joint index of joint `i`, with `-1` for root

6. **Related Mesh Binding**: Mesh also gets `jointIndicesPrimvar` (derived from `model.point_attribute_bone_id`) which tells which joints influence each vertex

**Key Benefits of Refactored Architecture**:

- **Separation of Concerns**: Computation (core) separate from serialization (io)
- **Testability**: Core skeleton logic testable without USD or Grove installation
- **Reusability**: Skeleton computation can be used for other export formats
- **Maintainability**: Clear boundaries between modules

**Dual jointIndices System**:

- **Skeleton jointIndices**: Encodes bone hierarchy (parent relationships)
- **Mesh jointIndicesPrimvar**: Encodes vertex-to-bone influences (skinning weights)
- Together they enable skeletal mesh deformation in Unreal Engine

---

## 18. Optimization: Single-Pass Export (No Re-Simulation)

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
