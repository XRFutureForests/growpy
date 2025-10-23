# %% IMPORTS
from pathlib import Path

# Expose Blender's bundled USD library to avoid DLL issues
try:
    import bpy.utils  # type: ignore
    bpy.utils.expose_bundled_modules()
except ImportError:
    pass  # Not running in Blender, use system pxr

import the_grove_22_core as gc
from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

# Generates tree USD skeletal mesh files for Unreal Engine 5.7+
# Creates a single .usda file containing:
# - SkelRoot container for skeleton hierarchy
# - Skeleton with bone definitions and transforms
# - Mesh geometry with SkelBindingAPI for deformation
# - Grove attributes preserved as primvars
#
# Import the .usda file directly into Unreal Engine as a skeletal mesh.


# %% INPUT PARAMETERS - Configure these to match your tree generation
random_seed = 42
preset_path = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/assets/presets/Fagaceae - Beech.seed.json"
)

# Tree planting parameters
position = (1, 2, 0)
direction = (0, 0, 1)
delay = 0

# Simulation parameters
flushes = 5

# Build parameters
resolution = 16
resolution_reduce = 0.8
texture_repeat = 3
build_cutoff_age = 0
build_cutoff_thickness = 0.0
build_blend = True
build_end_cap = True

# Skeleton parameters
skeleton_length = 2.0
skeleton_reduce = 0.4
skeleton_bias = 0.5
skeleton_connected = True

# Smoothing parameters
smoothing_iterations = 5
enable_smooth = True

# Output configuration
output_dir = Path("data/output")
output_dir.mkdir(parents=True, exist_ok=True)
species_name = "Beech"


# %% HELPER FUNCTIONS

def create_usd_skeleton_from_bones(stage, skel_path, bones):
    """Create UsdSkel skeleton from Grove bones with proper hierarchy.

    Bones are tuples: (is_root, bone_idx, head, tail, radius, mass, connected, parent_idx)
    """
    skeleton = UsdSkel.Skeleton.Define(stage, skel_path)

    bone_names = []
    rest_transforms = []
    bind_transforms = []
    topology = []
    bone_idx_to_list_idx = {}

    # Sort bones by index for consistent ordering
    sorted_bones = sorted(bones, key=lambda b: b[1])

    # First pass: create name mapping
    for list_idx, bone_data in enumerate(sorted_bones):
        bone_idx = bone_data[1]  # Extract bone_idx from tuple
        bone_names.append(f"bone_{bone_idx:03d}")
        bone_idx_to_list_idx[bone_idx] = list_idx

    # Second pass: build transforms and topology
    for list_idx, bone_data in enumerate(sorted_bones):
        bone_idx = bone_data[1]  # bone_idx
        head = bone_data[2]      # head position
        tail = bone_data[3]      # tail position
        parent_idx = bone_data[7]  # parent_idx

        # Map parent index to list position
        if parent_idx >= 0 and parent_idx in bone_idx_to_list_idx:
            topology.append(bone_idx_to_list_idx[parent_idx])
        else:
            topology.append(-1)

        # Extract positions (Vector objects have .x, .y, .z)
        head_pos = Gf.Vec3d(head.x, head.y, head.z)
        tail_pos = Gf.Vec3d(tail.x, tail.y, tail.z)

        # Bone direction
        bone_dir = tail_pos - head_pos
        bone_length = bone_dir.GetLength()

        # Create rotation to align bone with +Y axis
        if bone_length > 0.001:
            bone_dir.Normalize()
            default_dir = Gf.Vec3d(0, 1, 0)
            rotation = Gf.Rotation(default_dir, bone_dir)
        else:
            rotation = Gf.Rotation()

        # Build transform matrix
        transform = Gf.Matrix4d(1.0)
        transform.SetTranslate(head_pos)
        transform.SetRotateOnly(rotation.GetQuat())

        rest_transforms.append(transform)
        bind_transforms.append(transform)

    # Set skeleton attributes
    skeleton.GetJointsAttr().Set(Vt.TokenArray(bone_names))
    skeleton.GetRestTransformsAttr().Set(Vt.Matrix4dArray(rest_transforms))
    skeleton.GetBindTransformsAttr().Set(Vt.Matrix4dArray(bind_transforms))

    # Set topology as a custom attribute on the skeleton prim
    # This defines the parent-child relationships: topology[i] = parent index of joint i
    skel_prim = skeleton.GetPrim()
    topology_attr = skel_prim.CreateAttribute(
        "skel:topology", Sdf.ValueTypeNames.IntArray, custom=False
    )
    topology_attr.Set(Vt.IntArray(topology))

    print(f"  Created skeleton with {len(bone_names)} joints")
    return skeleton, bone_names


def add_mesh_to_stage(
    stage,
    mesh_path,
    points,
    faces,
    uvs,
    point_thickness=None,
    point_orientation=None,
    point_age=None,
    point_vigor=None,
    point_shade=None,
    face_branch_index=None,
    face_twig_long=None,
    face_twig_short=None,
    skeleton=None,
    bone_names=None,
):
    """Add mesh geometry and attributes to USD stage."""

    # Define mesh prim
    mesh = UsdGeom.Mesh.Define(stage, mesh_path)
    mesh_prim = mesh.GetPrim()

    # Set mesh topology
    face_vertex_counts = [len(face) for face in faces]
    face_vertex_indices = []
    for face in faces:
        face_vertex_indices.extend(face)

    mesh.CreatePointsAttr().Set(
        Vt.Vec3fArray([Gf.Vec3f(p.x, p.y, p.z) for p in points])
    )
    mesh.CreateFaceVertexCountsAttr().Set(Vt.IntArray(face_vertex_counts))
    mesh.CreateFaceVertexIndicesAttr().Set(Vt.IntArray(face_vertex_indices))

    # Set UVs as primvar
    if uvs:
        # UVs can be tuples (u, v) or Vector objects
        uv_data = Vt.Vec2fArray([
            Gf.Vec2f(u[0], u[1]) if isinstance(u, (tuple, list)) else Gf.Vec2f(u.x, u.y)
            for u in uvs
        ])
        mesh_prim.CreateAttribute("primvars:st", Sdf.ValueTypeNames.Float2Array).Set(uv_data)

    # Add point attributes
    if point_thickness:
        mesh_prim.CreateAttribute(
            "primvars:grove:thickness", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_thickness))

    if point_age:
        mesh_prim.CreateAttribute(
            "primvars:grove:age", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_age))

    if point_vigor:
        mesh_prim.CreateAttribute(
            "primvars:grove:vigor", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_vigor))

    if point_shade:
        mesh_prim.CreateAttribute(
            "primvars:grove:shade", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_shade))

    if point_orientation:
        # Convert Vector quaternions to Gf.Quatf (w, x, y, z order)
        orientation_array = Vt.QuatfArray(
            [Gf.Quatf(q[3], q[0], q[1], q[2]) for q in point_orientation]
        )
        mesh_prim.CreateAttribute(
            "primvars:grove:orientation", Sdf.ValueTypeNames.QuatfArray
        ).Set(orientation_array)

    # Add face attributes
    if face_branch_index:
        mesh_prim.CreateAttribute(
            "primvars:grove:branch_index", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_branch_index))

    if face_twig_long:
        mesh_prim.CreateAttribute(
            "primvars:grove:twig_long", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_twig_long))

    if face_twig_short:
        mesh_prim.CreateAttribute(
            "primvars:grove:twig_short", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_twig_short))

    # Apply skeleton binding if skeleton provided
    if skeleton and bone_names:
        skel_binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
        skel_binding_api.CreateSkeletonRel().AddTarget(skeleton.GetPrim().GetPath())

        # Set bind joints as primvar
        mesh_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
        ).Set(Vt.TokenArray(bone_names))
        print(f"  Bound mesh to skeleton with {len(bone_names)} joints")

    print(f"  Added mesh: {len(points)} points, {len(faces)} faces")
    return mesh


def export_tree_mesh_to_usd(
    output_path,
    points,
    faces,
    uvs,
    point_thickness,
    point_orientation,
    point_age,
    point_vigor,
    point_shade,
    face_branch_index,
    face_twig_long,
    face_twig_short,
    bones,
    species_name="Tree",
):
    """Export skeletal tree mesh to USD.

    Creates a properly structured skeletal mesh with:
    - SkelRoot containing the skeleton
    - Mesh bound to skeleton via SkelBindingAPI
    - All Grove attributes preserved as primvars
    """

    print(f"\nExporting skeletal tree mesh to USD: {output_path}")

    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)

    # Create root transform
    root_prim = stage.DefinePrim("/Tree", "Xform")

    # Create SkelRoot for skeleton hierarchy
    skel_root_prim = UsdSkel.Root.Define(stage, "/Tree/SkelRoot")

    # Create skeleton under SkelRoot
    skeleton, bone_names = create_usd_skeleton_from_bones(
        stage, "/Tree/SkelRoot/Skeleton", bones
    )

    # Create mesh as sibling to SkelRoot (not child)
    # This allows the mesh to be bound to skeleton without being under it
    mesh = UsdGeom.Mesh.Define(stage, "/Tree/Mesh")
    mesh_prim = mesh.GetPrim()

    # Set mesh topology
    face_vertex_counts = [len(face) for face in faces]
    face_vertex_indices = []
    for face in faces:
        face_vertex_indices.extend(face)

    mesh.CreatePointsAttr().Set(
        Vt.Vec3fArray([Gf.Vec3f(p.x, p.y, p.z) for p in points])
    )
    mesh.CreateFaceVertexCountsAttr().Set(Vt.IntArray(face_vertex_counts))
    mesh.CreateFaceVertexIndicesAttr().Set(Vt.IntArray(face_vertex_indices))

    # Set UVs as primvar
    if uvs:
        uv_data = Vt.Vec2fArray([
            Gf.Vec2f(u[0], u[1]) if isinstance(u, (tuple, list)) else Gf.Vec2f(u.x, u.y)
            for u in uvs
        ])
        mesh_prim.CreateAttribute("primvars:st", Sdf.ValueTypeNames.Float2Array).Set(uv_data)

    # Add point attributes
    if point_thickness:
        mesh_prim.CreateAttribute(
            "primvars:grove:thickness", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_thickness))

    if point_age:
        mesh_prim.CreateAttribute(
            "primvars:grove:age", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_age))

    if point_vigor:
        mesh_prim.CreateAttribute(
            "primvars:grove:vigor", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_vigor))

    if point_shade:
        mesh_prim.CreateAttribute(
            "primvars:grove:shade", Sdf.ValueTypeNames.FloatArray
        ).Set(Vt.FloatArray(point_shade))

    if point_orientation:
        orientation_array = Vt.QuatfArray(
            [Gf.Quatf(q[3], q[0], q[1], q[2]) for q in point_orientation]
        )
        mesh_prim.CreateAttribute(
            "primvars:grove:orientation", Sdf.ValueTypeNames.QuatfArray
        ).Set(orientation_array)

    # Add face attributes
    if face_branch_index:
        mesh_prim.CreateAttribute(
            "primvars:grove:branch_index", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_branch_index))

    if face_twig_long:
        mesh_prim.CreateAttribute(
            "primvars:grove:twig_long", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_twig_long))

    if face_twig_short:
        mesh_prim.CreateAttribute(
            "primvars:grove:twig_short", Sdf.ValueTypeNames.IntArray
        ).Set(Vt.IntArray(face_twig_short))

    # Apply SkelBindingAPI to establish binding
    skel_binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
    skel_binding_api.CreateSkeletonRel().AddTarget(skeleton.GetPrim().GetPath())

    # Set geometry bind transform (identity matrix)
    geom_bind_xform = Gf.Matrix4d(1.0)
    skel_binding_api.CreateGeomBindTransformAttr().Set(geom_bind_xform)

    # Create joint influences per vertex
    vertex_count = len(points)

    # Bind all vertices to bone 0 (root) with full weight
    # This is uniform binding - all mesh deforms together with root
    joint_indices = Vt.IntArray([0] * vertex_count)
    joint_weights = Vt.FloatArray([1.0] * vertex_count)

    # Store as primvars for skeleton deformation
    indices_attr = mesh_prim.CreateAttribute(
        "primvars:skel:jointIndices",
        Sdf.ValueTypeNames.IntArray,
    )
    indices_attr.Set(joint_indices)

    weights_attr = mesh_prim.CreateAttribute(
        "primvars:skel:jointWeights",
        Sdf.ValueTypeNames.FloatArray,
    )
    weights_attr.Set(joint_weights)

    stage.GetRootLayer().Save()
    print(f"  Created skeletal mesh: {len(points)} points, {len(faces)} faces")
    print(f"  Bound to skeleton at {skeleton.GetPrim().GetPath()}")
    print(f"  Saved: {output_path}")

    return stage


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

# Apply smoothing
if enable_smooth:
    print(f"\nApplying smoothing with {smoothing_iterations} iteration(s)")
    for i in range(smoothing_iterations):
        grove.smooth()
        print(f"  Smoothing iteration {i+1} complete")

# %% MODEL BUILDING

# Build 3D models
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

# Configure coordinate system
tree_model.set_up_axis("Z")
tree_model.set_winding_order("COUNTER_CLOCKWISE")

# %% SKELETON BUILDING

# Build skeleton
skeletons = grove.build_skeletons()
skeleton = skeletons[0]

# Tag bones with custom parameters
bones = grove.tag_bone_id(
    skeleton_length,
    skeleton_reduce**2,
    skeleton_bias,
    skeleton_connected,
)

print(f"Generated {len(bones)} bones from skeleton")

# %% EXTRACT GEOMETRY DATA

# Basic geometry
points = tree_model.points
faces = tree_model.faces
uvs = tree_model.uvs

# Point attributes
point_age = tree_model.point_attribute_age
point_thickness = tree_model.point_attribute_thickness
point_orientation = tree_model.point_attribute_orientation
point_vigor = tree_model.point_attribute_vigor
point_shade = tree_model.point_attribute_shade

# Face attributes (with safe access)
face_branch_index = (
    tree_model.face_attribute_branch_index
    if hasattr(tree_model, "face_attribute_branch_index")
    else None
)
face_twig_long = (
    tree_model.face_attribute_twig_long
    if hasattr(tree_model, "face_attribute_twig_long")
    else None
)
face_twig_short = (
    tree_model.face_attribute_twig_short
    if hasattr(tree_model, "face_attribute_twig_short")
    else None
)

# Skeleton data
skeleton_points = skeleton.points
skeleton_poly_lines = skeleton.poly_lines

print(f"\nExtracted geometry:")
print(f"  Points: {len(points)}")
print(f"  Faces: {len(faces)}")
print(f"  Skeleton bones: {len(bones)}")

# %% EXPORT TO USD

# Export skeletal mesh directly (can import this into Unreal)
usd_output_path = output_dir / f"{species_name}.usda"

export_tree_mesh_to_usd(
    usd_output_path,
    points,
    faces,
    uvs,
    point_thickness,
    point_orientation,
    point_age,
    point_vigor,
    point_shade,
    face_branch_index,
    face_twig_long,
    face_twig_short,
    bones,
    species_name,
)

print(f"\nSuccess! Skeletal mesh USD created:")
print(f"  {usd_output_path}")
print(f"\nImport directly into Unreal Engine as a skeletal mesh")
