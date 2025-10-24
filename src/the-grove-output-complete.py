# %% IMPORTS
from pathlib import Path

import the_grove_22_core as gc

# %% INPUT PARAMETERS - Configure these to generate different trees
# This script demonstrates comprehensive Grove API usage including:
# - Tree growth simulation with custom parameters
# - 3D mesh generation with build parameters
# - Skeleton/bone system for rigging and physics
# - Complete geometry and attribute data extraction
# - Export to multiple formats (text dump, USDA)

# Random seed for reproducible tree generation (default: 0)
random_seed = 42

# Path to tree species preset (default: None)
preset_path = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/assets/presets/Fagaceae - Beech.seed.json"
)

# Tree planting parameters
position = (1, 2, 0)  # (x, y, z) coordinates (default: (0, 0, 0))
direction = (0, 0, 1)  # Initial growth direction vector (default: (0, 0, 1))
delay = 0  # Number of years to wait before growing (default: 0)

# Simulation parameters
flushes = 2  # Number of growth cycles to simulate (default: 1)

# Build parameters for 3D mesh generation
resolution = 16  # Number of points at tree base (default: 16, range: 3-32)
resolution_reduce = (
    0.8  # Reduction factor (default: 0.8, range: 0.0-1.0, higher = faster thinning)
)
texture_repeat = (
    3  # Times to repeat bark texture around trunk (default: 1, range: 1-10)
)
build_cutoff_age = (
    0  # Stop building branches older than this (default: 0 = no cutoff, range: 0-100)
)
build_cutoff_thickness = 0.0  # Stop building branches thinner than this (default: 0.0 = no cutoff, range: 0.0-1.0)
build_blend = True  # Add smooth transitions between branches (default: True)
build_end_cap = True  # Close off branch ends with geometry (default: True)

# Skeleton parameters for physics simulation and rigging
skeleton_length = 2.0  # Length threshold for bone creation (default: 2.0, range: 0.0-5.0, lower = more bones)
skeleton_reduce = (
    0.4  # Reduce bones below thickness threshold (default: 0.4, range: 0.0-1.0)
)
skeleton_bias = 0.5  # Bias towards parent or child bones (default: 0.5, range: 0.0-1.0)
skeleton_connected = True  # Whether bones are connected in hierarchy (default: False)

# Smoothing parameters
enable_smooth = True  # Apply smoothing to reduce sharp branch angles (default: False)
smooth_iterations = (
    5  # Number of smoothing iterations to apply (default: 1, range: 1-10)
)

# Model export settings
up_axis = "Z"  # Coordinate system up axis (default: "Z", options: "Y" for Houdini, "Z" for Blender/Unreal)
winding_order = "COUNTER_CLOCKWISE"  # Face winding order (default: "COUNTER_CLOCKWISE", options: "CLOCKWISE" for Blender, "COUNTER_CLOCKWISE" for most others)
triangulate_mesh = True  # Convert all quads to triangles (default: False)
bark_texture_aspect_ratio = (
    3.0  # Aspect ratio of bark texture height/width (default: 1.0, range: 0.1-10.0)
)

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

# Apply smoothing if enabled
if enable_smooth:
    print(f"\nApplying smoothing with {smooth_iterations} iteration(s)")
    for i in range(smooth_iterations):
        grove.smooth()
        print(f"  Smoothing iteration {i+1} complete")
else:
    print("\nSmoothing disabled")

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

# %% SKELETON BUILDING (BEFORE WIND ANIMATION)

# Build skeleton
skeletons = grove.build_skeletons()
skeleton = skeletons[0]

# Tag bones with custom parameters matching Blender operator settings
bones = grove.tag_bone_id(
    skeleton_length,
    skeleton_reduce**2,  # Square the reduce value as per Blender operator
    skeleton_bias,
    skeleton_connected,
)

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


print(f"Generated {len(bones)} bones from skeleton with custom parameters")
print(f"  Length threshold: {skeleton_length}")
print(f"  Reduce threshold: {skeleton_reduce}")
print(f"  Bias: {skeleton_bias}")
print(f"  Connected: {skeleton_connected}")

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


# %% EXPORT GEOMETRY AND ATTRIBUTES
# All geometry and attribute data is exported directly from Grove API
# Direct data access is more reliable than intermediate format parsing
# %%
# Export all geometry and attribute data to text files for systematic comparison
output_dir = Path("data/output/grove_geometry_dump")
output_dir.mkdir(parents=True, exist_ok=True)

# Save basic geometry
with open(output_dir / "points.txt", "w") as f:
    f.write("# Point coordinates (x, y, z)\n")
    for i, p in enumerate(points):
        f.write(f"{i}: {p.x}, {p.y}, {p.z}\n")

with open(output_dir / "faces.txt", "w") as f:
    f.write("# Face definitions (point indices)\n")
    for i, face in enumerate(faces):
        f.write(f"{i}: {face}\n")

with open(output_dir / "uvs.txt", "w") as f:
    f.write("# UV coordinates (u, v)\n")
    for i, uv in enumerate(uvs):
        f.write(f"{i}: {uv}\n")

# Save flat geometry data
with open(output_dir / "points_flat.txt", "w") as f:
    f.write("# Flat point array [x1,y1,z1,x2,y2,z2,...]\n")
    f.write(str(points_flat))

with open(output_dir / "uvs_flat.txt", "w") as f:
    f.write("# Flat UV array [u1,v1,u2,v2,...]\n")
    f.write(str(uvs_flat))

with open(output_dir / "directions_flat.txt", "w") as f:
    f.write("# Flat direction vectors\n")
    f.write(str(directions_flat))

# Save face attributes
with open(output_dir / "face_attributes.txt", "w") as f:
    f.write("# Face Attributes\n\n")

    if face_tree_index:
        f.write("## Tree Index\n")
        f.write(f"{face_tree_index}\n\n")

    if face_branch_index:
        f.write("## Branch Index\n")
        f.write(f"{face_branch_index}\n\n")

    if face_branch_index_parent:
        f.write("## Branch Parent Index\n")
        f.write(f"{face_branch_index_parent}\n\n")

    f.write("## Twig Long\n")
    f.write(f"{face_twig_long}\n\n")

    f.write("## Twig Short\n")
    f.write(f"{face_twig_short}\n\n")

    f.write("## Twig Upward\n")
    f.write(f"{face_twig_upward}\n\n")

    f.write("## Twig Dead\n")
    f.write(f"{face_twig_dead}\n\n")

    f.write("## Dead Faces\n")
    f.write(f"{face_dead}\n\n")

    f.write("## End Faces\n")
    f.write(f"{face_end}\n\n")

    f.write("## Face Direction\n")
    f.write(f"{face_direction}\n")

# Save point attributes
with open(output_dir / "point_attributes.txt", "w") as f:
    f.write("# Point Attributes\n\n")

    f.write("## Age\n")
    f.write(f"{point_age}\n\n")

    f.write("## Mass\n")
    f.write(f"{point_mass}\n\n")

    f.write("## Thickness\n")
    f.write(f"{point_thickness}\n\n")

    f.write("## Orientation\n")
    f.write(f"{point_orientation}\n\n")

    f.write("## Pitch\n")
    f.write(f"{point_pitch}\n\n")

    f.write("## Vigor\n")
    f.write(f"{point_vigor}\n\n")

    f.write("## Shade\n")
    f.write(f"{point_shade}\n\n")

    f.write("## Photosynthesis\n")
    f.write(f"{point_photosynthesis}\n")

# Save skeleton data
with open(output_dir / "skeleton.txt", "w") as f:
    f.write("# Skeleton Data\n\n")

    f.write("## Points\n")
    for i, p in enumerate(skeleton_points):
        f.write(f"{i}: {p}\n")
    f.write("\n")

    f.write("## Poly Lines\n")
    for i, line in enumerate(skeleton_poly_lines):
        f.write(f"{i}: {line}\n")
    f.write("\n")

    f.write(f"## Location\n{skeleton_location}\n\n")

    f.write(f"## Branch ID\n{skeleton_face_branch_id}\n\n")
    f.write(f"## Point Age\n{skeleton_point_age}\n\n")
    f.write(f"## Point Mass\n{skeleton_point_mass}\n\n")
    f.write(f"## Point Radius\n{skeleton_point_radius}\n")

# Save advanced skeleton bones data
with open(output_dir / "skeleton_bones.txt", "w") as f:
    f.write("# Advanced Skeleton Bones (Tagged with custom parameters)\n\n")
    f.write(f"# Parameters:\n")
    f.write(f"#   Length: {skeleton_length}\n")
    f.write(f"#   Reduce: {skeleton_reduce}\n")
    f.write(f"#   Bias: {skeleton_bias}\n")
    f.write(f"#   Connected: {skeleton_connected}\n\n")
    f.write(f"# Total bones: {len(bones)}\n\n")
    f.write(
        "# Format: bone_index: (branch_id, bone_id, start_point, end_point, parent_bone_id)\n\n"
    )

    for i, bone in enumerate(bones):
        f.write(f"{i}: {bone}\n")

print(f"Exported all geometry and attributes to {output_dir}")
print(f"\nExport Summary:")
print(f"  Points: {len(points)}")
print(f"  Faces: {len(faces)}")
print(f"  UV Coordinates: {len(uvs)}")
print(f"  Skeleton Points: {len(skeleton_points)}")
print(f"  Skeleton Bones (advanced): {len(bones)}")
if enable_smooth:
    print(f"  Smoothing applied: {smooth_iterations} iteration(s)")
print("\nAll data exported successfully!")

# %%
