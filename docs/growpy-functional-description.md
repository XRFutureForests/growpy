# GrowPy Package - Comprehensive Functional Description

**Document Version:** 1.1
**Date:** 2026-01-09 (updated 2026-02-27)
**Purpose:** Complete functional description of the GrowPy package architecture and data flow

> **Status as of 2026-02-27**: Refactoring phases 1-3 are complete (logging, deprecated code removal, code structure improvements). The architecture described here remains accurate; specific code quality metrics (print statement counts, fallback counts) reflect the pre-refactoring baseline.

---

## Table of Contents

1. [Package Overview](#package-overview)
2. [Architecture and Design Principles](#architecture-and-design-principles)
3. [CLI Scripts - Pipeline Workflow](#cli-scripts---pipeline-workflow)
4. [Core Processing Modules](#core-processing-modules)
5. [Input/Output and Export System](#inputoutput-and-export-system)
6. [Configuration Management](#configuration-management)
7. [Data Flow and Dependencies](#data-flow-and-dependencies)
8. [Key Algorithms and Processing Logic](#key-algorithms-and-processing-logic)
9. [External Dependencies](#external-dependencies)
10. [Optimization Opportunities](#optimization-opportunities)

---

## Package Overview

GrowPy is a Python package that converts The Grove 2.2 procedural tree generation assets into Unreal Engine 5-compatible USD (Universal Scene Description) format with Nanite mesh support. It provides a complete 4-step pipeline for:

1. **Asset Preparation**: Copying and standardizing Grove assets
2. **Twig Conversion**: Converting Blender twig meshes to USD format
3. **Growth Model Analysis**: Creating height-to-age prediction models
4. **Forest Generation**: Simulating tree growth and exporting to USD

### Core Capabilities

- **Multi-species Forest Simulation**: Inter-species light competition
- **Skeletal Animation Support**: Wind animation via DynamicWind system
- **PVE Integration**: Procedural Vegetation Editor preset generation
- **Quality Presets**: 5 LOD levels (ultra, high, medium, low, performance)
- **Unreal Engine Integration**: Automated import script generation

### Package Structure

```
src/growpy/
├── cli/                    # Command-line interface scripts (4 scripts)
├── core/                   # Core simulation logic (5 modules)
├── io/                     # Input/Output and asset export (15+ modules)
├── config/                 # Configuration management (6 modules)
├── utils/                  # Utility functions and analysis tools (5 modules)
├── tests/                  # Test suite
└── __init__.py             # Package initialization
```

---

## Architecture and Design Principles

### 1. Pipeline-Based Architecture

The package follows a strict 4-step pipeline pattern where each CLI script produces output consumed by subsequent scripts:

```
prepare_assets.py → convert_twigs.py → create_growth_models.py → generate_forest.py
```

**Design Principle**: Each step is independently executable and produces deterministic output in `data/assets/` or `data/output/`.

### 2. Separation of Concerns

- **CLI Layer**: User interaction, argument parsing, orchestration
- **Core Layer**: Tree/forest simulation, Grove API integration
- **IO Layer**: File format conversion, USD export, texture processing
- **Config Layer**: Quality presets, parameter management, path resolution

### 3. Configuration Over Code

- **Quality Presets**: Predefined parameter sets for different use cases
- **Preset Overrides**: Dynamic parameter adjustment during simulation
- **CSV-Driven**: Species selection and forest layout via CSV files

### 4. External API Integration

- **The Grove 2.2 Core**: C++ library via Python bindings (the_grove_22_core)
- **Blender Python API**: Direct mesh manipulation and USD export
- **Pixar USD**: Universal Scene Description file format

---

## CLI Scripts - Pipeline Workflow

### Script 1: prepare_assets.py

**Purpose**: Copy and standardize Grove 2.2 assets for GrowPy processing

#### Processing Steps

1. **CSV Loading and Validation**
   - Load input CSV (forest placement or asset lookup format)
   - Auto-detect CSV format (has "species" column vs "Common Name" column)
   - Extract unique species names if forest placement CSV
   - Map to asset lookup table (src/growpy/config/tree_asset_lookup.csv)

2. **Species Name Standardization**
   - Convert Grove CamelCase names to snake_case
   - Example: "BaldCypress80" → "bald_cypress_80"
   - Apply to presets, twigs, and textures consistently

3. **Preset File Copying**
   - Source: `{grove_dir}/presets/*.seed.json`
   - Destination: `data/assets/presets/{species}.seed.json`
   - Rename using standardized species names

4. **Twig Directory Copying**
   - Source: `{grove_dir}/twigs/{CamelCaseTwig}/`
   - Destination: `data/assets/twigs/{snake_case_twig}/`
   - Contains .blend files and textures subdirectory

5. **Twig Texture Processing**
   - Standardize texture naming conventions
   - Extract alpha channel from diffuse if no dedicated alpha exists
   - Strip alpha from diffuse (RGBA → RGB)
   - Optional: Resize to power-of-2 dimensions (--resize-textures flag)
   - Validate required textures exist (diffuse, alpha, normal)

6. **Bark Texture Copying**
   - Source: `{grove_dir}/textures/{CamelCase}.jpg`
   - Destination: `data/assets/textures/{snake_case}_bark.jpg`
   - Preserve age numbers (e.g., "Beech60" → "beech_60_bark.jpg")

7. **PVE Config Generation**
   - Create null placeholder configs for each species
   - Destination: `data/assets/pve_configs/{species}_pve.json`
   - Only create if doesn't exist (preserve user customizations)

#### Key Functions

- `load_species_csv()`: Parse and validate CSV formats
- `camel_to_snake()`: CamelCase to snake_case conversion
- `standardize_species_name()`: Species name normalization
- `ensure_power_of_2_textures()`: Texture resizing for GPU compatibility
- `process_twig_textures()`: Complete texture processing pipeline

#### Output Files

```
data/assets/
├── presets/{species}.seed.json
├── twigs/{species}_twig/*.blend
├── textures/{species}_{age}_bark.jpg
└── pve_configs/{species}_pve.json
```

---

### Script 2: convert_twigs.py

**Purpose**: Convert Grove twig .blend files to USD with silhouette optimization

#### Processing Steps

1. **Twig Discovery and Filtering**
   - Find all .blend files in `data/assets/twigs/`
   - Filter by CSV species list if provided
   - Parse twig type from filename (apical, lateral, upward, dead, summer)

2. **Blender File Loading**
   - Open .blend file via Blender Python API (bpy)
   - Extract mesh objects (leaves, branches)
   - Locate armature if present

3. **Texture Sampling and Alpha Mapping**
   - Load all textures associated with materials
   - Sample alpha values at UV coordinates for each vertex
   - Build vertex-to-alpha mapping (0.0 = transparent, 1.0 = opaque)
   - Auto-detect inverted alpha masks (black = opaque)

4. **Interleaved Densification + Trimming Algorithm**

   **Iteration Loop (repeat until stable):**

   a. **Classify Faces by Alpha**
   - Transition faces: Have BOTH opaque and transparent vertices
   - Transparent faces: ALL vertices transparent
   - Opaque faces: ALL vertices opaque
   - Boundary faces: Have at least one mesh boundary edge

   b. **Delete Small Transparent Faces**
   - Find fully transparent faces
   - Check if all edges <= target edge length
   - Delete if small enough (removes interior transparent geometry)

   c. **Subdivide Transition Edges**
   - Find edges connecting opaque and transparent vertices
   - Subdivide if edge length > target (creates higher resolution silhouette)
   - Edge split operation naturally propagates to neighboring faces

   d. **Convergence Check**
   - Stop if no faces deleted and no edges subdivided
   - Prevents infinite loops

5. **Boundary Smoothing (Optional)**
   - Apply Laplacian smoothing to boundary vertices
   - Smooth mesh edges to follow alpha texture curves
   - Configurable iterations and strength

6. **Dual USD Export**

   **Skeletal Variant** (`{name}_skeletal.usda`):
   - Embed armature skeleton (root joint at origin)
   - Minimal export: geometry only (no materials)
   - Used in skeletal Nanite assemblies for animation

   **Static Variant** (`{name}_static.usda`):
   - Full PBR materials with textures
   - No skeleton (static geometry)
   - Used in static Nanite assemblies

7. **Twig Name Standardization**
   - Parse species, type, variation from filename
   - Generate consistent output names
   - Example: "BeechApicalTwig" → "beech_apical_skeletal.usda"

#### Key Algorithms

**Boundary-Only Densification**:
- Only subdivides edges at the silhouette boundary
- Interior mesh topology preserved
- Creates high-detail edges where alpha transitions occur

**Relative Edge Sizing**:
- `boundary_edge_mm` parameter is fraction of average edge length
- Default: 0.5 (subdivide to 50% of avg edge)
- Scale-independent: works for any mesh size

**Alpha Trimming Methods**:
- `all`: Delete face only if ALL vertex samples < threshold (conservative)
- `any`: Delete face if ANY vertex sample < threshold (aggressive)

#### Key Functions

- `process_twig_directory()`: Batch process all twigs in directory
- `process_twig_file()`: Single twig conversion (in io/twig_export.py)
- `standardize_twig_name()`: Filename parsing and standardization
- `classify_texture_type()`: Detect PBR texture types
- `find_textures_for_material()`: Smart texture matching

#### Output Files

```
data/assets/twigs/{species}_twig/
├── {species}_twig_{type}_skeletal.usda
└── {species}_twig_{type}_static.usda
```

---

### Script 3: create_growth_models.py

**Purpose**: Generate species-specific height curves and age prediction models

#### Processing Steps

1. **Species Discovery**
   - Load CSV to get species list
   - Find corresponding preset files in `data/assets/presets/`
   - Validate presets exist

2. **Growth Curve Simulation (Per Species)**

   For each species, simulate growth for multiple random seeds:

   a. **Initialize Grove**
   - Load species preset (.seed.json)
   - Create single tree at origin
   - Set random seed

   b. **Simulate Growth Cycles**
   - Run grove.simulate(1) for each cycle
   - Record height and DBH (diameter at breast height)
   - Track elapsed time

   c. **Plateau Detection**
   - Monitor height increase per cycle
   - Stop if increase < height_threshold (default: 0.05m)
   - Stop if no growth for max_cycles_without_growth (default: 3)

   d. **Timeout Protection**
   - Maximum simulation time per seed (default: 300s)
   - Prevents infinite loops or stuck simulations

3. **Multi-Seed Averaging**
   - Run simulation with N random seeds (default: 1, recommended: 3)
   - Average height and DBH values across seeds
   - Produces more robust growth curves

4. **Growth Model Fitting**
   - Use scikit-learn to fit height-to-age relationship
   - Create inverse function: height → cycles
   - Store coefficients for runtime prediction

5. **Visualization**
   - Generate matplotlib plot of height vs cycles
   - Save as PNG: `{species}_height_curve.png`
   - Visual verification of growth patterns

6. **Model Serialization**
   - Save growth data as JSON
   - Format: `{species}_growth_model.json`
   - Contains: cycles, heights, DBH values, metadata

#### Key Features

- **Automatic Plateau Detection**: Stops when tree reaches mature height
- **Timeout Protection**: Prevents resource exhaustion
- **Robust Averaging**: Multiple seeds reduce variation
- **Visual Feedback**: Progress bars for cycles and species

#### Key Functions

- `SpeciesGrowthAnalyzer` class:
  - `generate_height_curve_for_species()`: Simulate single species
  - `create_growth_model_for_species()`: Fit prediction model
  - `analyze_all_species()`: Batch process multiple species
  - `save_growth_models()`: JSON serialization

#### Output Files

```
data/assets/growth_models/
├── {species}_growth_model.json
└── {species}_height_curve.png
```

---

### Script 4: generate_forest.py

**Purpose**: Complete forest generation with USD export and Unreal import scripts

#### Processing Steps

1. **CSV Loading and Height-to-Cycles Conversion**
   - Load forest CSV: `x, y, species, height, z (optional)`
   - Load growth models for each species
   - Calculate growth_cycles from height using prediction models
   - Calculate delay for staggered growth (max_cycles - tree_cycles)

2. **Growth Cycle Limiting**
   - Cap cycles to growth_cycle_limit (default: 10)
   - If exceeded, scale all cycles proportionally: `new = old * (limit / max)`
   - Recalculate delays after scaling to prevent trees from never growing
   - Apply height scaling only if within limit

3. **Forest Creation**
   - Group trees by species
   - Create one Grove instance per species
   - Add trees to each grove at (x, y, z) positions
   - Track original CSV fid for each tree (for naming)

4. **Forest Growth Simulation**

   **Preset Override Application**:
   - Load species curves from seed.json files (interpolated overrides)
   - Apply CLI overrides if provided (higher priority)
   - Override priority: CLI args > species curves > defaults

   **Growth Loop** (for each cycle):
   - Apply preset overrides (dynamic parameter adjustment)
   - Calculate shade geometry for all groves
   - Share shade data between groves (inter-species light competition)
   - Run grove.simulate(1) for each species

   **Phase 1: Growth Simulation** (~60-80% of time)
   - Simulate branch growth, bud creation, leaf shedding
   - Light competition affects growth rates
   - Overhead branches shade lower trees

5. **Branch Smoothing (Optional)**

   **Phase 2: Branch Smoothing** (~10-20% of time)
   - Applied after simulation, before building
   - Reduces sharp branch angles

   **Smoothing Workflow**:
   - `grove.smooth_minimal()`: Fix ugly kinks on thick branches (once)
   - `grove.smooth()`: Reduce sharp angles (repeat N times, default: 10)
   - `grove.weigh_and_bend()`: Recalculate positions (CRITICAL - without this, smoothing has no effect!)

6. **Skeleton and Model Building**

   **Per Grove** (contains multiple trees):

   a. **Build Skeletons**
   - Extract branch hierarchy from simulation
   - Create bone structure for animation

   b. **Tag Bone IDs**
   - Apply quality preset parameters:
     - `skeleton_length`: Bone distance threshold (higher = fewer bones)
     - `skeleton_reduce`: Thickness threshold (higher = skip thinner branches)
     - `skeleton_bias`: Bone distribution (0.0 = trunk, 1.0 = tips)
     - `skeleton_connected`: Connected vs disconnected chains
   - CRITICAL: Unreal has 32,767 bone limit (16-bit signed int)

   c. **Build 3D Models**
   - Generate mesh geometry from branches
   - Apply quality parameters:
     - `resolution`: Vertex count per branch segment (8-32)
     - `resolution_reduce`: Simplification factor
     - `build_cutoff_age`: Minimum branch age to include
     - `build_cutoff_thickness`: Minimum branch thickness
     - `texture_repeat`: UV scaling

7. **Tree Export Loop**

   **For each tree in each grove**:

   a. **Get Twig USD Map**
   - Find skeletal twig USD files for this species
   - Map twig types (apical, lateral, etc.) to USD paths
   - Always use skeletal twigs (work for both assembly types)

   b. **Export Nanite Assembly**
   - Assembly file: `{species}.usda` (same name per species)
   - Tree mesh: `{species}_{tree_id}_skeletal.usda` (unique per tree)
   - References twigs via PointInstancer
   - Embeds skeleton for skeletal assemblies
   - Copy twig USD files to tree folder (caching optimization)

   c. **Generate DynamicWind JSON**
   - Separate JSON file: `{species}_{tree_id}_DynamicWind.json`
   - Maps skeleton joints to wind simulation groups
   - Import in Unreal: ImportDynamicWindSkeletalDataFromFile
   - Only for skeletal meshes (not static)

   d. **Generate PVE Preset JSON** (optional, skip with --skip-pve-json)
   - File: `{species}_{tree_id}.json`
   - Complete PVE preset for Unreal Procedural Vegetation Editor
   - Extracts branch hierarchy, polylines, attributes
   - ~3% of export time

8. **Unreal Script Generation** (optional, with --import-to-unreal)

   **Import Script** (`unreal_scripts/import_forest.py`):
   - Standalone Python script for Unreal Engine
   - Imports all tree assemblies to Content Browser
   - Configurable destination path (default: /Game/GrowPy/Trees)
   - Execute via VSCode Unreal Python extension
   - Includes tree position data from CSV

   **Cleanup Script** (`unreal_scripts/clean_assets.py`):
   - Remove all imported assets
   - Dry-run mode by default (preview only)
   - Set DRY_RUN = False for actual deletion

#### Key Processing Phases

**Timing Breakdown** (approximate):
- CSV loading: <1%
- Forest creation: 1-5%
- Growth simulation: 60-80%
- Smoothing: 10-20% (if enabled)
- Building (skeletons + models): 5-10%
- Export (per tree): 1-3% each
- PVE JSON: ~3% total (optional)
- Wind JSON: <1% (always generated for skeletal)

#### Export Variants

**Skeletal Assemblies** (default):
- Minimal export: geometry + skeleton only
- No materials/textures in tree mesh
- Wind animation support
- Smaller file size
- Use skeletal twigs

**Static Assemblies** (optional, --include-static):
- Full PBR materials with textures
- No skeleton (static geometry)
- Better visual quality for static placement
- Larger file size
- Use skeletal twigs (same as skeletal assemblies)

#### Key Functions

- `generate_forest_exports()`: Main orchestration
- `create_forest()`: Group trees by species, create groves
- `simulate_forest_growth()`: Growth simulation with preset overrides
- `export_individual_trees()`: Export all trees from groves
- `_export_single_tree_from_forest()`: Per-tree export logic
- `generate_unreal_import_script()`: Create import script
- `generate_unreal_cleanup_script()`: Create cleanup script

#### Output Structure

```
data/output/forest/
├── {species}/
│   └── tree_{id:04d}/
│       ├── {species}.usda                        # Nanite assembly (shared name)
│       ├── {species}_{tree_id}_skeletal.usda     # Tree mesh with skeleton
│       ├── {species}_{tree_id}_DynamicWind.json  # Wind animation data
│       ├── {species}_{tree_id}.json              # PVE preset (optional)
│       └── twigs/                                # Copied twig USD files
│           ├── {species}_twig_apical_skeletal.usda
│           └── {species}_twig_lateral_skeletal.usda
└── unreal_scripts/
    ├── import_forest.py
    └── clean_assets.py
```

---

## Core Processing Modules

### core/tree.py

**Purpose**: Height-to-cycles conversion using growth models

**Key Functions**:
- `calculate_growth_cycles_from_height()`: Load growth models and convert height column to growth_cycles
- Uses linear interpolation if height between data points
- Extrapolates if height exceeds model range

### core/grove.py

**Purpose**: Single-species grove management (wrapper around Grove API)

**Key Functions**:
- `create_grove()`: Initialize Grove instance for species
- `add_tree_to_grove()`: Place tree at (x, y, z) with optional delay

**Grove API Methods Used**:
- `grove.simulate(cycles)`: Run growth simulation
- `grove.smooth()`: Reduce branch angles
- `grove.smooth_minimal()`: Fix thick branch kinks
- `grove.weigh_and_bend()`: Recalculate branch positions
- `grove.build_skeletons()`: Extract bone hierarchy
- `grove.tag_bone_id()`: Filter bones by quality parameters
- `grove.build_models()`: Generate 3D mesh geometry
- `grove.create_shade_geometry_coords()`: Get shade geometry for light competition
- `grove.calculate_shade_together()`: Apply shared shade data

### core/forest.py

**Purpose**: Multi-species forest creation and simulation

**Key Functions**:
- `create_forest()`: Group trees by species, create groves, track fids
- `simulate_forest_growth()`: Growth simulation with preset overrides and smoothing

**Preset Override System**:
- Load species curves from seed.json files (interpolated_overrides)
- Apply CLI overrides (static_overrides and interpolated_overrides)
- Priority: CLI > species curves > defaults
- Applied at each growth cycle for dynamic parameter adjustment

**Inter-Species Light Competition**:
- All groves share shade geometry
- Shade from one species affects growth of other species
- Simulates realistic forest dynamics

### core/skeleton.py

**Purpose**: Skeleton hierarchy management for skeletal meshes

**Data Structures**:
- `Vector3`: 3D point (x, y, z)
- `JointTransform`: Bone position, rotation, scale
- `SkeletonHierarchy`: Full skeleton tree with parent-child relationships

**Key Functions**:
- `build_skeleton_hierarchy()`: Convert Grove skeleton to USD skeleton
- `calculate_vertex_weights()`: Skinning weights for vertex deformation
- `tag_bone_id()`: Filter bones by quality parameters
- `filter_bones_for_mesh()`: Reduce skeleton size

### core/twig.py

**Purpose**: Twig placement extraction and bone assignment

**Data Structures**:
- `TwigPlacement`: Position, rotation, scale, type, leaf count, bone_id

**Key Functions**:
- `extract_twig_placements_from_model()`: Find all twigs in tree
- `get_face_center_and_normal()`: Geometry calculations for placement
- `normal_to_rotation_matrix()`: Convert surface normal to 3D rotation
- `_find_twig_bone_id()`: Assign twigs to skeleton bones (vertex voting or branch lookup)

**Twig-to-Bone Assignment**:
1. Vertex voting: Use vertex bone_id attributes (fast, accurate)
2. Branch lookup fallback: Match twig to nearest branch (slow, less accurate)

---

## Input/Output and Export System

### io/assembly_export.py (63KB - Most Complex)

**Purpose**: Create Nanite Assembly USD files for Unreal Engine

**Key Function**: `export_tree_as_nanite_assembly()`

**Assembly Structure**:
```
Assembly USD (species.usda)
├── References tree mesh (species_tree_id_skeletal.usda)
├── PointInstancer for twigs (instances skeletal twig USD files)
├── Skeleton (embedded from tree mesh, skeletal only)
├── Material bindings (skeletal: none, static: PBR materials)
└── DynamicWind attributes (embedded in skeleton prim)
```

**Processing Steps**:

1. **Create Assembly Stage**
   - Define root prim: `/Assembly`
   - Set up USD layer and stage

2. **Reference Tree Mesh**
   - Add reference to tree USD file
   - Skeletal: includes skeleton
   - Static: no skeleton

3. **Setup PointInstancer for Twigs**
   - Group twig placements by type (apical, lateral, etc.)
   - Map types to twig USD prototypes
   - Apply fallback mapping if type missing
   - Set positions, rotations, scales, indices

4. **Embed DynamicWind Attributes** (skeletal only)
   - Read wind JSON
   - Embed in skeleton prim as USD attributes:
     - `unreal:dynamicWind:jointNames`
     - `unreal:dynamicWind:jointSimulationGroups`

5. **Copy Twig USD Files**
   - Copy skeletal twig files to tree folder
   - Cache copied files (avoid redundant copies)
   - Update twig references to use local paths

6. **Material Bindings** (static only)
   - Create material scope
   - Bind materials to tree mesh
   - Reference texture files

7. **Validation** (optional, skip with --skip-validation)
   - Verify assembly structure
   - Check all references valid
   - Validate PointInstancer indices

**Twig Type Fallback Mapping**:
```python
{
    "dead" → "apical",
    "summer" → "apical",
    "upward" → "lateral"
}
```

**Optimization**: Twig file copy cache prevents duplicate file operations

### io/tree_export.py (73KB - Complex)

**Purpose**: Convert Grove Model to USD mesh with skeleton

**Key Function**: `build_tree_mesh()`

**Processing Steps**:

1. **Create USD Mesh Prim**
   - Define mesh path in USD stage
   - Set mesh type (skeletal or static)

2. **Transfer Geometry Data**
   - Points: 3D vertex positions
   - Face Vertex Counts: Triangles (3) or quads (4)
   - Face Vertex Indices: Mesh topology
   - Normals: Per-vertex normals

3. **Apply Bone ID Attribute** (skeletal only)
   - `bone_id` primvar for vertex skinning
   - Maps vertices to skeleton bones
   - Used for animation deformation

4. **Create Materials** (static only)
   - Bark material with diffuse texture
   - PBR shader setup
   - Texture coordinate mapping

5. **Embed Skeleton** (skeletal only)
   - Convert Grove skeleton to UsdSkel format
   - Set bind transforms
   - Create animation rig

**Twig USD Map**: `get_twig_usd_map_for_species()`
- Find all twig USD files for species
- Map twig types to file paths
- Prefer skeletal or static variants

### io/twig_export.py (149KB - Most Complex)

**Purpose**: Convert Blender .blend files to USD with silhouette optimization

**Key Function**: `process_twig_file()`

**Major Processing Phases**:

1. **Blender File Loading**
   - Open .blend via bpy API
   - Find mesh objects
   - Locate armature

2. **Texture Sampling**
   - Load all material textures
   - Sample alpha at UV coordinates
   - Build vertex-to-alpha map

3. **Interleaved Densification + Trimming**
   - See detailed algorithm in convert_twigs.py section above
   - Boundary-only subdivision
   - Small transparent face deletion
   - Convergence detection

4. **Boundary Smoothing** (optional)
   - Laplacian smoothing on boundary vertices
   - Smooth edges to follow alpha curves

5. **Dual USD Export**
   - Skeletal: geometry + armature
   - Static: geometry + materials

**Key Algorithms**:
- Boundary detection via mesh.edges with is_boundary flag
- Alpha sampling via texture pixel access
- Edge subdivision via bmesh.ops.subdivide_edges
- Face deletion via bmesh.ops.delete

**Texture Processing**:
- Classify texture types (diffuse, alpha, normal, etc.)
- Find textures for each material
- Smart matching by filename patterns
- Copy standardized textures to output

### io/wind_json.py

**Purpose**: Generate DynamicWind JSON for Unreal wind animation

**Key Function**: `generate_wind_json()`

**Processing Steps**:

1. **Read Skeleton from USD**
   - Load tree USD file
   - Extract skeleton hierarchy
   - Get joint names and transforms

2. **Classify Joints by Simulation Group**
   - trunk: Root and primary branches
   - primary: Thick branches (thickness > 0.05)
   - secondary: Medium branches (thickness 0.01-0.05)
   - tertiary: Thin branches (thickness < 0.01)

3. **Calculate Wind Parameters**
   - Per-joint simulation group assignment
   - Based on hierarchy depth and thickness

4. **Serialize to JSON**
   - Format for Unreal ImportDynamicWindSkeletalDataFromFile
   - jointNames array
   - jointSimulationGroups array (0-3)

**Classification Strategies**:
- Preferred: Use skeleton thickness attributes
- Fallback: Hierarchy depth from joint name parsing

### io/pve_grove_mapper.py (54KB - Complex)

**Purpose**: Map Grove simulation data to Unreal PVE preset format

**Key Function**: `generate_pve_from_grove()`

**Processing Steps**:

1. **Extract Branch Hierarchy**
   - Build polyline structure from skeleton
   - Calculate generation levels (distance from trunk)
   - Determine parent-child relationships

2. **Calculate Global Attributes**
   - age: Growth cycles
   - vigor: Tree health (0.0-1.0)
   - mass: Total branch mass

3. **Calculate Point Attributes** (per-vertex on polylines)
   - position: 3D coordinates
   - rotation: Branch orientation
   - thickness: Branch radius
   - length_from_root: Distance along branch hierarchy

4. **Calculate Primitive Attributes** (per-branch)
   - generation: Hierarchy level (0 = trunk)
   - parent: Parent branch index
   - length: Branch length
   - gradients: Thickness change along branch
   - bud_direction: Growth direction vectors

5. **Extract Foliage Data**
   - Leaf positions and orientations
   - Link leaves to branch segments
   - Calculate density and distribution

6. **Apply Species Overrides**
   - Load PVE config from data/assets/pve_configs/
   - Override default parameters
   - Species-specific adjustments

7. **Validate and Serialize**
   - Validate against PVE schema
   - Serialize to JSON
   - Format for Unreal import

**PVE Schema Structure**:
```json
{
    "global_attributes": {
        "age": float,
        "vigor": float,
        "mass": float
    },
    "point_attributes": {
        "position": [[x,y,z], ...],
        "rotation": [[x,y,z,w], ...],
        "thickness": [float, ...]
    },
    "primitive_attributes": {
        "generation": [int, ...],
        "parent": [int, ...],
        "length": [float, ...]
    },
    "foliage": [...]
}
```

---

## Configuration Management

### config/quality.py

**Quality Presets**: 5 levels with different parameter sets

**Parameters**:
- `resolution`: Vertex count per branch segment (8-32)
- `resolution_reduce`: Simplification factor (0.75-0.9)
- `texture_repeat`: UV scaling (2-4)
- `build_cutoff_age`: Minimum branch age (0-2 cycles)
- `build_cutoff_thickness`: Minimum branch thickness (0.0-0.05)
- `skeleton_length`: Bone distance threshold (0.1-4.0)
- `skeleton_reduce`: Thickness threshold (0.1-0.8)
- `skeleton_bias`: Bone distribution (0.5 default)
- `skeleton_connected`: Connected bone chains (bool)

**Preset Comparison**:

| Preset | Vertices | Skeleton | Use Case |
|--------|----------|----------|----------|
| ultra | 32 | Most bones | Hero trees, closeup |
| high | 24 | Many bones | Featured trees |
| medium | 16 | Balanced | Background trees |
| low | 12 | Few bones | Distant trees |
| performance | 8 | Minimal | Far background |

### config/preset_overrides.py

**Preset Override System**: Dynamic parameter adjustment during simulation

**Override Types**:

1. **Static Overrides**:
   - Fixed values applied at every cycle
   - Example: `drop_decay=0.1` (reduce branch decay)
   - Specified via CLI: `--preset-override drop_decay=0.1`

2. **Interpolated Overrides**:
   - Values interpolated from curve over cycles
   - Loaded from species seed.json files
   - Format: `{param}_curve: [(cycle, value), ...]`

**Priority Order**:
1. CLI preset overrides (highest)
2. Species curves from seed.json
3. Grove defaults (lowest)

**Common Parameters**:
- `drop_decay`: Rate of dead branch decay (0.0-1.0)
- `drop_weak`: Rate of weak branch dropping
- `drop_shaded`: Rate of shaded branch dropping
- `drop_obsolete`: Rate of obsolete branch dropping
- `light_power`: Light intensity influence

**Longevity Mode**: Predefined overrides to prevent tree death at high cycles
```python
{
    "drop_decay": 0.1,
    "drop_weak": 0.1,
    "drop_shaded": 0.1,
    "drop_obsolete": 0.0
}
```

### config/paths.py

**Path Resolution**: Find Grove assets with multiple fallback strategies

**Key Functions**:
- `get_preset_path()`: Find species preset file
- `get_growth_model_path()`: Find growth model JSON
- `get_twig_directory()`: Find twig folder
- `get_bark_texture_path()`: Find bark texture

**Fallback Strategies**:
1. Try standardized snake_case name
2. Try original Grove CamelCase name
3. Try lookup table mapping
4. Try filename variations

---

## Data Flow and Dependencies

### Complete Pipeline Data Flow

```
Input CSV (x, y, species, height)
    ↓
[prepare_assets.py]
    ├─ Copy presets → data/assets/presets/
    ├─ Copy twigs → data/assets/twigs/
    ├─ Process textures
    └─ Create PVE configs → data/assets/pve_configs/
    ↓
[convert_twigs.py]
    ├─ Load .blend files from data/assets/twigs/
    ├─ Densify + trim silhouettes
    └─ Export USD → {twig}_skeletal.usda, {twig}_static.usda
    ↓
[create_growth_models.py]
    ├─ Load presets from data/assets/presets/
    ├─ Simulate growth curves
    └─ Save models → data/assets/growth_models/
    ↓
[generate_forest.py]
    ├─ Load growth models
    ├─ Calculate growth_cycles from height
    ├─ Create forest (groves per species)
    ├─ Simulate growth with inter-species competition
    ├─ Build skeletons and models
    ├─ Export per tree:
    │   ├─ Nanite assembly → {species}.usda
    │   ├─ Tree mesh → {species}_{id}_skeletal.usda
    │   ├─ Wind JSON → {species}_{id}_DynamicWind.json
    │   └─ PVE JSON → {species}_{id}.json (optional)
    └─ Generate Unreal scripts → unreal_scripts/
```

### Module Dependencies

**No Circular Dependencies** - Clean dependency graph:

```
config/ (independent, no internal dependencies)
    ↓
core/ (depends on config, the_grove_22_core)
    ↓
io/ (depends on config, core, pxr USD, bpy)
    ↓
cli/ (orchestrates all layers)
```

**External Dependencies**:
- `the_grove_22_core`: C++ Grove API (Python bindings)
- `bpy`: Blender Python API
- `pxr`: Pixar USD
- `pandas`: CSV and DataFrame
- `numpy`: Numerical operations
- `scikit-learn`: Growth model fitting
- `matplotlib`: Plotting
- `PIL/Pillow`: Image processing
- `tqdm`: Progress bars

---

## Key Algorithms and Processing Logic

### 1. Height-to-Cycles Conversion

**Purpose**: Convert tree height (meters) to growth cycles for simulation

**Algorithm**:
1. Load growth model JSON for species
2. Find cycles corresponding to target height
3. Linear interpolation if between data points
4. Extrapolation if beyond model range

**Used By**: generate_forest.py (calculate_growth_cycles_from_height)

### 2. Interleaved Densification + Trimming

**Purpose**: Create high-detail silhouettes while removing internal transparent faces

**Algorithm** (from convert_twigs.py):
```
while not converged:
    1. Classify faces by alpha (opaque, transparent, transition, boundary)
    2. Delete small fully-transparent faces (all edges <= target)
    3. Subdivide long transition edges (edges > target at alpha boundary)
    4. Check convergence (no changes in step 2 or 3)
```

**Key Properties**:
- Only subdivides silhouette boundary (transition zones)
- Interior mesh topology preserved
- Auto-detects inverted alpha (black=opaque)
- Scale-independent (relative edge sizing)

**Used By**: convert_twigs.py (process_twig_file)

### 3. Multi-Species Light Competition

**Purpose**: Simulate realistic forest dynamics where species compete for light

**Algorithm** (from core/forest.py):
```python
for cycle in range(cycles):
    # Apply preset overrides
    for grove in forest:
        apply_overrides(grove, cycle)

    # Share shade geometry between species
    if len(groves) > 1:
        all_coords = []
        for grove in groves:
            coords = grove.create_shade_geometry_coords()
            all_coords.extend(coords)

        for grove in groves:
            grove.calculate_shade_together(all_coords)

    # Simulate growth
    for grove in forest:
        grove.weigh_and_bend()
        grove.simulate(1)
```

**Key Properties**:
- Shade geometry shared between all species
- Grove API handles shade calculation
- Overhead branches reduce light for lower trees
- Affects growth rates and branch survival

**Used By**: generate_forest.py (simulate_forest_growth)

### 4. Twig-to-Bone Assignment

**Purpose**: Assign each twig placement to a skeleton bone for animation

**Algorithm** (from core/twig.py):
```python
def _find_twig_bone_id():
    # Strategy 1: Vertex voting (fast, accurate)
    if model has point_attribute_bone_id:
        for each face vertex:
            collect bone_id votes
        return most common bone_id

    # Strategy 2: Branch lookup (slow, fallback)
    else:
        for each branch:
            if twig within branch bounding box:
                return branch_id
        return 0  # root fallback
```

**Key Properties**:
- Vertex voting preferred (uses Grove's bone assignments)
- Branch lookup fallback for models without vertex bone data
- Twig placement uses center of twig face
- Fallback to root bone if no match found

**Used By**: io/assembly_export.py (during PointInstancer creation)

### 5. Skeleton Bone Filtering

**Purpose**: Reduce skeleton bone count while preserving animation quality

**Algorithm** (from generate_forest.py):
```python
# Grove API filters bones based on quality parameters
bones = grove.tag_bone_id(
    skeleton_length,      # Bone distance threshold (higher = fewer bones)
    skeleton_reduce**2,   # Thickness threshold squared (like Grove UI)
    skeleton_bias,        # Distribution (0.0 = trunk, 1.0 = tips)
    skeleton_connected    # Connected chains vs isolated bones
)
```

**Quality Preset Values**:
- ultra: length=0.1, reduce=0.1 (most bones, max detail)
- medium: length=2.0, reduce=0.4 (balanced, Grove default)
- performance: length=4.0, reduce=0.8 (minimal bones, 32K limit safe)

**Used By**: generate_forest.py (_export_single_tree_from_forest)

### 6. Preset Override Interpolation

**Purpose**: Dynamic parameter adjustment during growth simulation

**Algorithm** (from config/preset_overrides.py):
```python
def apply_to_grove(grove, current_cycle, total_cycles):
    # Apply static overrides (fixed values)
    for param, value in static_overrides:
        setattr(grove, param, value)

    # Apply interpolated overrides (curves)
    for param, curve_points in interpolated_overrides:
        # Linear interpolation between curve points
        value = interpolate(curve_points, current_cycle)
        setattr(grove, param, value)
```

**Curve Format** (in seed.json):
```json
{
    "drop_decay_curve": [
        [0, 0.5],    // cycle 0: value 0.5
        [50, 0.3],   // cycle 50: value 0.3
        [100, 0.1]   // cycle 100: value 0.1
    ]
}
```

**Used By**: generate_forest.py (simulate_forest_growth)

---

## External Dependencies

### The Grove 2.2 Core (the_grove_22_core)

**Type**: C++ library with Python bindings (CFFI or ctypes)

**Key Classes**:
- `Grove`: Main simulation class
- `Model`: 3D geometry representation
- `Skeleton`: Bone hierarchy

**Key Methods Used**:
- Growth: `simulate()`, `weigh_and_bend()`
- Smoothing: `smooth()`, `smooth_minimal()`
- Building: `build_skeletons()`, `tag_bone_id()`, `build_models()`
- Light: `create_shade_geometry_coords()`, `calculate_shade_together()`

**Integration**: Wrapper functions in core/grove.py

### Blender Python API (bpy)

**Type**: Python module embedded in Blender

**Key Modules Used**:
- `bpy.data`: Access Blender data (meshes, materials, textures)
- `bpy.ops`: Blender operators (import, export, modifiers)
- `bmesh`: Low-level mesh editing
- `bpy.utils`: Bundled module exposure

**Integration**: Direct imports in io/twig_export.py and cli/convert_twigs.py

**Special Handling**: Bundled module exposure for NumPy access
```python
if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()
```

### Pixar USD (pxr)

**Type**: Universal Scene Description Python bindings

**Key Modules Used**:
- `pxr.Usd`: Core USD API (Stage, Prim, Attribute)
- `pxr.UsdGeom`: Geometry (Mesh, PointInstancer, Xform)
- `pxr.UsdSkel`: Skeletal animation (Skeleton, Animation, BindingAPI)
- `pxr.UsdShade`: Materials and shaders

**Integration**: All io/ export modules

**Initialization**: Custom environment setup in utils/pxr_init.py

---

## Optimization Opportunities

Based on the comprehensive analysis, the following optimization opportunities have been identified:

### 1. Verbose Output Cleanup

**Current State**:
- 84 print statements in CLI scripts alone
- 23 total files with print statements
- No unified logging system
- Hardcoded print statements in library code

**Recommendations**:
- Replace print() with Python logging module
- Add log levels: DEBUG, INFO, WARNING, ERROR
- Make verbose output opt-in via --verbose flag
- Remove debugging print statements from production code

**Impact**: Cleaner output, better maintainability, easier debugging

### 2. Deprecated/Legacy Code Removal

**Current State**:
- 7 files with TODO/FIXME/NOTE comments
- Multiple deprecated functions marked but not removed
- Legacy fallback paths for old file formats
- Unused parameter warnings

**Identified Deprecated Code**:
- `io/tree_export.py`: `export_tree_mesh()` marked DEPRECATED (line 72)
- `io/tree_export.py`: Multiple deprecated skeleton parameters (lines 147-150)
- `io/assembly_export.py`: `skeleton_source_usd` parameter deprecated (line 113)
- `io/pve_grove_mapper.py`: Deprecated parent calculation method (line 1043)
- `io/pve_hierarchy_builder.py`: Legacy model parameter kept for compatibility (lines 84, 164)

**Recommendations**:
- Remove deprecated functions entirely
- Clean up legacy parameter handling
- Remove fallback code for old formats
- Update function signatures to remove unused parameters

**Impact**: Reduced code size, less confusion, easier maintenance

### 3. Fallback Code Reduction

**Current State**:
- Extensive fallback logic throughout codebase
- Multiple path resolution fallbacks in config/paths.py
- Twig-to-bone assignment fallbacks in core/twig.py
- Texture matching fallbacks in io/twig_export.py

**Fallback Categories**:
- **Path Resolution**: 8+ fallback attempts per asset lookup
- **Twig-Bone Assignment**: 2 strategies (vertex voting → branch lookup)
- **Texture Matching**: 3-tier matching (direct → word overlap → permissive)
- **PVE Attribute**: Multiple fallback defaults

**Recommendations**:
- Standardize asset organization (eliminate CamelCase → snake_case variations)
- Document required file structure clearly
- Reduce fallback depth (1-2 levels max)
- Log warnings when fallbacks used
- Consider failing fast on missing assets rather than silent fallbacks

**Impact**: Faster asset lookup, clearer error messages, less unexpected behavior

### 4. Redundant File Operations

**Current State**:
- Twig USD files copied per tree (even if already copied)
- Texture processing repeated for each twig variant
- No caching for repeated asset reads
- File existence checks in tight loops

**Identified Redundancies**:
- `io/assembly_export.py`: Copy twig files even if already present
- `cli/prepare_assets.py`: Process textures separately for each species
- `io/twig_export.py`: Reload textures for each material

**Recommendations**:
- Expand twig copy cache (currently partial)
- Cache texture processing results
- Batch file operations where possible
- Use file modification time checks to skip up-to-date files

**Impact**: Faster exports, reduced disk I/O, lower memory usage

### 5. Profiling and Performance Tracking

**Current State**:
- Profiling system implemented (utils/profiling.py)
- Optional via --profile flag
- Not enabled by default
- Timer hierarchy for detailed breakdown

**Recommendations**:
- Enable profiling by default (minimal overhead)
- Add summary output always (even without --profile)
- Track more granular operations
- Add memory profiling alongside time profiling
- Consider persistent profiling data for optimization analysis

**Impact**: Better performance visibility, easier bottleneck identification

### 6. Configuration Consolidation

**Current State**:
- Multiple configuration sources:
  - Quality presets (config/quality.py)
  - Preset overrides (config/preset_overrides.py)
  - PVE species overrides (config/pve_species_overrides.py)
  - Asset lookup CSV (config/tree_asset_lookup.csv)
- Overlapping parameters between systems
- Priority rules not always clear

**Recommendations**:
- Consolidate configuration into single system
- Clear hierarchy: CLI > species > quality > defaults
- Single source of truth for each parameter
- Document parameter precedence explicitly
- Consider YAML/TOML for human-readable config

**Impact**: Easier configuration, fewer conflicts, better documentation

### 7. Error Handling Improvements

**Current State**:
- Many functions silently fail or return default values
- Try/except blocks catch generic Exception
- Error messages not always informative
- Some errors printed but not raised

**Recommendations**:
- Raise specific exceptions with clear messages
- Add custom exception classes for domain errors
- Fail fast on critical errors (missing assets)
- Use warnings module for non-critical issues
- Log full stack traces for debugging

**Impact**: Easier debugging, clearer failure modes, better user experience

### 8. Documentation and Code Comments

**Current State**:
- Extensive docstrings in CLI scripts (good)
- Less documentation in library modules
- Some outdated comments referencing old behavior
- Algorithm explanations mostly in CLI help text

**Recommendations**:
- Move algorithm documentation to library modules
- Update outdated comments
- Add type hints consistently
- Document assumptions and limitations
- Create architecture decision records (ADRs)

**Impact**: Easier onboarding, better maintenance, clearer intent

### 9. Testing Coverage

**Current State**:
- Single test file: tests/test_pve_generation.py
- No tests for CLI scripts
- No tests for core simulation logic
- No tests for export functions

**Recommendations**:
- Add unit tests for core modules
- Add integration tests for CLI pipeline
- Add regression tests for export formats
- Mock external dependencies (Grove API, bpy, USD)
- Set up CI/CD with test automation

**Impact**: Fewer bugs, safer refactoring, better quality

### 10. Memory Management

**Current State**:
- Manual garbage collection after tree export
- Large data structures held in memory during processing
- Grove instances kept alive throughout pipeline
- No streaming processing for large forests

**Identified Issues**:
- `generate_forest.py`: Grove instances stored until all exports complete
- `generate_forest.py`: Models list kept in memory (cleared iteratively)
- Memory spikes during skeleton/model building

**Recommendations**:
- Process and export trees incrementally
- Release Grove instances immediately after export
- Stream processing for large forests
- Memory profiling to identify peaks
- Consider disk-based caching for very large forests

**Impact**: Lower memory usage, handle larger forests, fewer crashes

---

## Summary

GrowPy is a well-structured package with clear separation of concerns and a logical pipeline architecture. The code is generally clean and well-documented, with extensive help text in CLI scripts.

**Strengths**:
- Clear 4-step pipeline workflow
- Modular architecture with no circular dependencies
- Comprehensive CLI documentation
- Flexible configuration system
- Performance profiling infrastructure

**Areas for Improvement**:
- Verbose output cleanup (replace print with logging)
- Remove deprecated/legacy code
- Reduce fallback complexity
- Improve error handling and fail-fast behavior
- Add comprehensive test coverage
- Consolidate configuration systems
- Optimize file operations and memory usage

The package is production-ready but would benefit significantly from the optimization opportunities identified above. The refactoring should focus on:
1. **Code cleanup** (verbose output, deprecated code, comments)
2. **Simplification** (reduce fallbacks, consolidate config)
3. **Robustness** (error handling, testing)
4. **Performance** (file operations, memory management)
