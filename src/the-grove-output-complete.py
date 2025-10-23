# %% IMPORTS
from pathlib import Path

import the_grove_22_core as gc

# %% INPUT PARAMETERS - Configure these to generate different trees

# Random seed for reproducible tree generation
random_seed = 42

# Path to tree species preset
preset_path = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/assets/presets/Fagaceae - Beech.seed.json"
)

# Tree planting parameters
position = (1, 2, 0)  # (x, y, z) coordinates
direction = (0, 0, 1)  # Initial growth direction vector
delay = 0  # Number of years to wait before growing

# Simulation parameters
flushes = 5  # Number of growth cycles to simulate

# Build parameters for 3D mesh generation
resolution = 16  # Number of points at tree base (more = smoother)
resolution_reduce = 0.8  # Reduction factor (0.0-1.0, higher = faster thinning)
texture_repeat = 3  # Times to repeat bark texture around trunk
build_cutoff_age = 0  # Stop building branches older than this (0 = no cutoff)
build_cutoff_thickness = (
    0.0  # Stop building branches thinner than this (0.0 = no cutoff)
)
build_blend = True  # Add smooth transitions between branches
build_end_cap = True  # Close off branch ends with geometry

# Model export settings
up_axis = "Z"  # "Y" for Houdini, "Z" for Blender/Unreal
winding_order = (
    "COUNTER_CLOCKWISE"  # "CLOCKWISE" for Blender, "COUNTER_CLOCKWISE" for most others
)
triangulate_mesh = True  # Convert all quads to triangles
bark_texture_aspect_ratio = 3.0  # Aspect ratio of bark texture (height/width)

# %% GROVE CREATION AND SIMULATION

# Create and configure grove
grove = gc.Grove()
grove.clear_trees()
grove.set_random_seed(random_seed)

# Load species preset and add tree
with open(preset_path, "r") as f:
    json_string = f.read()
properties = gc.io.properties_from_json_string(json_string)
grove.set_properties(properties)
position_vec = gc.Vector(*position)
direction_vec = gc.Vector(*direction)
grove.add_new_tree(position_vec, direction_vec, delay)

# Simulate tree growth
grove.simulate(flushes)

# %% MODEL BUILDING

# Build 3D models with configured parameters
build_params = {
    "resolution": resolution,
    "resolution_reduce": resolution_reduce,
    "texture_repeat": texture_repeat,
    "build_cutoff_age": build_cutoff_age,
    "build_cutoff_thickness": build_cutoff_thickness,
    "build_blend": build_blend,
    "build_end_cap": build_end_cap,
}

models = grove.build_models(build_params)
tree_model = models[0]

# Configure coordinate system and winding order
tree_model.set_up_axis(up_axis)
tree_model.set_winding_order(winding_order)

# Apply texture aspect ratio if needed
if bark_texture_aspect_ratio != 1.0:
    tree_model.apply_uv_aspect_ratio(bark_texture_aspect_ratio)

# Optionally triangulate mesh
if triangulate_mesh:
    tree_model.triangulate()

# %% EXTRACT MODEL GEOMETRY DATA

# Basic geometry components
points = tree_model.points  # List of Vector objects with (x,y,z) coordinates
faces = tree_model.faces  # List of face definitions (point indices)
uvs = tree_model.uvs  # UV coordinates for texturing

# Flat/optimized geometry data for better Python performance
points_flat = tree_model.get_points_flat()  # [x1,y1,z1,x2,y2,z2,...]
uvs_flat = tree_model.get_uvs_flat()  # [u1,v1,u2,v2,...]
uvws_flat = tree_model.get_uvws_flat()  # [u1,v1,w1,u2,v2,w2,...] for Houdini
directions_flat = tree_model.get_directions_flat()  # Flat list of direction vectors
uv_islands_flat = tree_model.get_uv_islands_flat()  # UV island data

# %% EXTRACT FACE ATTRIBUTES

# Tree and branch identification
# Note: face_attribute_tree_index only exists when using Grove.build_as_one_model()
# for multi-tree groves, not for individual trees from build_models()
face_tree_index = (
    tree_model.face_attribute_tree_index
    if hasattr(tree_model, "face_attribute_tree_index")
    else None
)
face_branch_index = (
    tree_model.face_attribute_branch_index
    if hasattr(tree_model, "face_attribute_branch_index")
    else None
)
face_branch_index_parent = (
    tree_model.face_attribute_branch_index_parent
    if hasattr(tree_model, "face_attribute_branch_index_parent")
    else None
)

# Twig placement attributes (for twig duplication)
face_twig_long = tree_model.face_attribute_twig_long  # Long twig placement triangles
face_twig_short = tree_model.face_attribute_twig_short  # Short twig placement
face_twig_upward = tree_model.face_attribute_twig_upward  # Upward facing twigs
face_twig_dead = tree_model.face_attribute_twig_dead  # Dead twigs

# Branch state attributes
face_dead = tree_model.face_attribute_dead  # Dead branch faces
face_end = tree_model.face_attribute_end  # Branch end cap faces
face_direction = tree_model.face_attribute_direction  # Original growth direction

# %% EXTRACT POINT ATTRIBUTES

# Age and structure
point_age = tree_model.point_attribute_age  # Node age in flushes/years
point_mass = tree_model.point_attribute_mass  # Mass of continuation + sub-branches

# Physical properties
point_thickness = tree_model.point_attribute_thickness  # Diameter (0.0-1.0 normalized)
point_orientation = tree_model.point_attribute_orientation  # Quaternion orientation
point_pitch = (
    tree_model.point_attribute_pitch
)  # Vertical angle (0.0=down, 0.5=horizontal, 1.0=up)

# Growth and lighting attributes
point_vigor = tree_model.point_attribute_vigor  # Growth power
point_shade = (
    tree_model.point_attribute_shade
)  # Ambient occlusion (0.0=exposed, 1.0=shaded)
point_photosynthesis = (
    tree_model.point_attribute_photosynthesis
)  # Light exposure * leaf area

# %% SKELETON BUILDING (for physics simulation)

skeletons = grove.build_skeletons()
skeleton = skeletons[0]

# Skeleton geometry
skeleton_points = skeleton.points  # [(x,y,z), ...] bone joint coordinates
skeleton_poly_lines = skeleton.poly_lines  # [[idx1,idx2,...], ...] connects joints
skeleton_location = skeleton.location  # (x,y,z) skeleton origin

# Skeleton attributes
skeleton_face_branch_id = (
    skeleton.face_attribute_branch_id
)  # Branch ID for matching to model
skeleton_point_age = skeleton.point_attribute_age  # Node age
skeleton_point_mass = skeleton.point_attribute_mass  # Node mass
skeleton_point_radius = skeleton.point_attribute_radius  # Branch radius

# %% EXPORT OPTIONS

# Generate USD string representation
usda_string = gc.io.model_to_usda_string(tree_model)

# %%
