# Grove API Attributes - Complete Reference

This document catalogs all available attributes from The Grove 2.2 API and documents which ones are exported by growpy.

## Tree Model Attributes (from `grove.build_models()`)

### Methods

- `__new__` - Constructor
- `apply_uv_aspect_ratio` - Adjust UV aspect ratio for bark textures
- `get_uvs_flat` - Flat array of UV coordinates
- `get_uvws_flat` - Flat array of UVW coordinates (for Houdini)
- `get_uv_islands_flat` - UV island data for texture mapping
- `get_directions_flat` - Flat array of direction vectors
- `get_points_flat` - Flat array of vertex coordinates [x1,y1,z1,x2,y2,z2,...]
- `get_points_as_tuples` - Vertex coordinates as tuples
- `get_shape_as_tuples` - Normal vectors as tuples
- `set_up_axis` - Configure coordinate system (Y or Z up)
- `set_winding_order` - Face winding order (CLOCKWISE/COUNTER_CLOCKWISE)
- `triangulate` - Convert quads to triangles
- **`get_twig_locations`** - Twig placement locations (ALTERNATIVE to face attributes)
- **`get_twig_orientations`** - Twig orientation quaternions (ALTERNATIVE to face attributes)
- **`get_twig_directions`** - Twig direction vectors (ALTERNATIVE to face attributes)

### Basic Geometry

- `points` - Vertex coordinates [(x,y,z), ...]
- `faces` - Face definitions (point indices)
- `uvs` - UV texture coordinates
- `uv_islands` - UV island groupings
- `shape` - Normal vectors for each vertex
- `location` - Model origin position

### Point Attributes (Per-Vertex)

✅ = Exported as USD primvar

- ✅ `point_attribute_age` - Node age in flushes/years (int)
- ✅ `point_attribute_mass` - Mass of continuation + sub-branches (float)
- ✅ `point_attribute_thickness` - Diameter normalized 0.0-1.0 (float)
- ✅ `point_attribute_orientation` - Quaternion orientation (4-float tuple)
- ✅ `point_attribute_pitch` - Vertical angle: 0.0=down, 0.5=horizontal, 1.0=up (float)
- ✅ `point_attribute_vigor` - Growth power (float)
- ✅ `point_attribute_shade` - Ambient occlusion: 0.0=exposed, 1.0=shaded (float)
- ✅ `point_attribute_photosynthesis` - Light exposure * leaf area (float)
- ✅ `point_attribute_bone_id` - Bone ID for rigging/animation (int)
- ✅ `point_attribute_skeleton_joint_id` - Skeleton joint ID (alternative to bone_id) (int)

### Face Attributes (Per-Face)

✅ = Exported as USD primvar

- ✅ `face_attribute_branch_id` - Branch ID for each face (int)
- ✅ `face_attribute_branch_id_parent` - Parent branch ID (int)
- ✅ `face_attribute_tree_id` - Tree ID (only in build_as_one_model) (int)
- ✅ `face_attribute_twig_long` - Long twig placement triangles (bool)
- ✅ `face_attribute_twig_short` - Short twig placement triangles (bool)
- ✅ `face_attribute_twig_upward` - Upward facing twig placements (bool)
- ✅ `face_attribute_twig_dead` - Dead twig placements (bool)
- ✅ `face_attribute_dead` - Dead branch faces (bool)
- ✅ `face_attribute_end` - Branch end cap faces (bool)
- ✅ `face_attribute_direction` - Original growth direction vector (3-float tuple)

### Export Status

**All point and face attributes are automatically exported to USD as primvars** with PascalCase naming (e.g., `point_attribute_thickness` → `Thickness` primvar).

The twig placement methods (`get_twig_locations`, `get_twig_orientations`, `get_twig_directions`) provide an alternative to the face attribute approach. Currently, growpy uses face attributes for twig placement extraction, which is more reliable.

---

## Grove Object Attributes (from `gc.Grove()`)

### Simulation Methods

- `simulate` - Run growth simulation
- `set_random_seed` - Set randomization seed
- `add_new_tree` - Add tree to grove
- `add_new_tree_simple` - Simplified tree addition
- `clear_trees` - Remove all trees

### Building Methods

- `build_models` - Generate 3D meshes
- `build_skeletons` - Generate skeleton data
- `build_as_one_model` - Build all trees as single mesh
- **`build_roots`** - Generate root geometry
- **`build_roots_as_one`** - Build all roots as single mesh
- **`grow_roots`** - Simulate root growth
- `build_surround` - Build surrounding environment preview
- `build_surround_preview` - 2D preview
- `build_surround_preview_2d` - Flat 2D preview
- `build_sketch` - Sketch mode preview
- `build_sketch_2d` - 2D sketch preview
- `build_shade_preview` - Shade visualization
- `build_spring_shape` - Spring physics shape
- `build_wind_shape` - Wind animation shape

### Skeleton/Rigging Methods

- `tag_id` - Tag basic bone IDs
- `tag_bone_id` - Advanced bone tagging with parameters
- `weigh_and_bend` - Physics weight calculation

### Manual Editing Methods

- `manual_prune` - Manual branch pruning
- `manual_bend` - Manual branch bending
- `manual_draw` - Manual branch drawing
- `replant_tree` - Move tree to new location
- `get_snapping_points` - Get snap points for editing
- `smooth` - Smooth branch angles
- `smooth_minimal` - Minimal smoothing

### Property Management

- `get_properties` - Get all grove properties
- `set_properties` - Set grove properties from JSON
- `seed` - Species seed data
- `remember_orig_pos` - Store original positions

### Reactive Environment

- `set_react_block_triangles_from_coords` - Block growth zones
- `set_react_shade_triangles_from_coords` - Shade sources
- `set_react_attract_triangles_from_coords` - Growth attractors
- `set_react_deflect_triangles_from_coords` - Growth deflectors
- `calculate_shade_together` - Multi-tree shade calculation
- `create_shade_geometry` - Generate shade mesh
- `create_shade_geometry_coords` - Shade mesh from coordinates

### Grove-Level Attributes

❌ = Not currently exported to USD (runtime-only)

- ❌ **`total_mass`** - Total mass of all trees (float)
- ❌ **`number_of_branches`** - Total branch count (int)
- ❌ **`height`** - Maximum tree height (float)
- ❌ **`age`** - Grove age in flushes (int)
- ❌ **`roots`** - Root system geometry (model object, if grown)
- `trees` - List of tree objects in grove
- `get_tree_positions_and_directions` - Tree location data

### Export Status

**Grove-level attributes are NOT exported to USD files** as they are runtime-only metadata. These attributes are useful for:

- Forest simulation analysis
- Growth statistics
- Physics calculations
- Multi-tree coordination

To access root geometry, use `grove.grow_roots()` followed by `grove.build_roots()` or `grove.build_roots_as_one()`. The returned root model has the same structure as tree models (points, faces, attributes).

---

## Skeleton Object Attributes (from `grove.build_skeletons()`)

### Methods

- `set_y_up` - Set Y-up coordinate system
- `set_z_up` - Set Z-up coordinate system (default for Blender/Unreal)

### Geometry

✅ = Exported to USD as skeleton

- ✅ `points` - Bone joint coordinates [(x,y,z), ...]
- ✅ `poly_lines` - Bone connectivity [[idx1,idx2,...], ...]
- ✅ `location` - Skeleton origin (x,y,z)

### Attributes

✅ = Exported to USD as skeleton metadata

- ✅ `point_attribute_age` - Node age
- ✅ `point_attribute_mass` - Node mass
- ✅ `point_attribute_radius` - Branch radius at joint
- ✅ `face_attribute_branch_id` - Branch ID for matching to model

### Export Status

**All skeleton attributes are exported to USD** as part of the UsdSkel structure. The skeleton is embedded in the tree USD file for skeletal mesh assemblies.

---

## Export Summary

### Fully Exported to USD

1. **Tree Model Geometry**: points, faces, UVs, normals
2. **All Point Attributes**: Automatically as vertex primvars
3. **All Face Attributes**: Automatically as uniform primvars
4. **Skeleton Data**: Complete UsdSkel structure with all attributes
5. **Advanced Bones**: From `grove.tag_bone_id()` with custom parameters

### Available but Not Exported

1. **Grove Statistics**: total_mass, number_of_branches, height, age
   - These are runtime-only and should be logged separately
2. **Root Geometry**: Available via `grove.grow_roots()` + `grove.build_roots()`
   - Could be exported as separate USD if needed
3. **Twig Placement Methods**: get_twig_locations/orientations/directions
   - Face attributes are used instead (more reliable)

### Implementation Notes

The export system uses **dynamic attribute discovery**:

```python
# All attributes starting with 'face_attribute_' are exported
face_attrs = [attr for attr in dir(model) if attr.startswith("face_attribute_")]

# All attributes starting with 'point_attribute_' are exported  
point_attrs = [attr for attr in dir(model) if attr.startswith("point_attribute_")]
```

This means **any new attributes added by Grove 2.2 updates will be automatically exported** without code changes.

---

## Usage Examples

### Export with All Attributes

```python
import the_grove_22_core as gc
from growpy.io.tree_export import export_tree

grove = gc.Grove()
grove.add_new_tree(gc.Vector(0,0,0), gc.Vector(0,0,1), 0)
grove.simulate(5)

models = grove.build_models({...})
skeletons = grove.build_skeletons()

# All attributes automatically included
export_tree(models[0], skeletons[0], Path("tree.usda"), "oak")
```

### Access Grove Statistics

```python
# Get runtime statistics
print(f"Total Mass: {grove.total_mass}")
print(f"Branches: {grove.number_of_branches}")
print(f"Height: {grove.height}")
print(f"Age: {grove.age}")
```

### Export Root System

```python
# Generate and build roots
grove.grow_roots()
root_models = grove.build_roots()

# Roots have same structure as tree models
for root_model in root_models:
    print(f"Root points: {len(root_model.points)}")
    print(f"Root faces: {len(root_model.faces)}")
    # Can export roots using same export_tree function if needed
```

---

## See Also

- `docs/guides/grove-api-usage.md` - Grove API usage patterns
- `src/the-grove-output-complete.py` - Complete attribute extraction example
- `src/growpy/io/tree_export.py` - USD export implementation
