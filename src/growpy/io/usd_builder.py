"""USD file builder using direct Grove API geometry data.

This module creates USD files directly from Grove API data without using
Grove's model_to_usda_string export. This approach avoids coordinate
transformation issues since the Grove API provides geometry data in the
correct coordinate system.

Key benefits:
- No coordinate transformation needed
- Direct access to all Grove attributes
- Cleaner integration with skeleton and twig systems
- More control over USD structure
"""

from pathlib import Path
from typing import Any, List, Optional, Tuple

try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False


def build_tree_usd(
    model: Any,
    output_path: Path,
    up_axis: str = "Z",
    triangulated: bool = True,
) -> bool:
    """Build USD file directly from Grove model using API geometry data.

    This function extracts geometry data directly from the Grove model using
    the Python API and constructs a USD file without coordinate transformations.

    Args:
        model: Grove tree model from grove.build_models()
        output_path: Path where USD file will be saved
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated

    Returns:
        bool: True if USD file was created successfully

    Example:
        >>> grove = gc.Grove()
        >>> grove.add_new_tree(...)
        >>> grove.simulate(5)
        >>> models = grove.build_models({...})
        >>> model = models[0]
        >>> model.triangulate()
        >>> build_tree_usd(model, Path("tree.usda"), up_axis="Z")
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata
        UsdGeom.SetStageUpAxis(
            stage, UsdGeom.Tokens.z if up_axis == "Z" else UsdGeom.Tokens.y
        )
        stage.SetMetadata("metersPerUnit", 1.0)

        # Define root xform
        root_path = Sdf.Path("/Tree")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Define mesh
        mesh_path = root_path.AppendChild("TreeMesh")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Extract geometry data from Grove model
        points = model.points  # List of Vector objects with (x, y, z)
        faces = model.faces  # List of face definitions (point indices)
        uvs = model.uvs  # UV coordinates for texturing

        # Convert points to USD format
        usd_points = [Gf.Vec3f(p.x, p.y, p.z) for p in points]

        # Convert faces to USD format
        # Faces can be triangles or quads depending on triangulation
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = []
        for face in faces:
            face_vertex_indices.extend(face)

        # Set mesh topology
        mesh.CreatePointsAttr(usd_points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Add UV coordinates (primvar)
        if uvs:
            primvars_api = UsdGeom.PrimvarsAPI(mesh)
            uv_primvar = primvars_api.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
            )
            usd_uvs = [Gf.Vec2f(uv[0], uv[1]) for uv in uvs]
            uv_primvar.Set(usd_uvs)

        # Add face attributes from Grove
        _add_grove_face_attributes(mesh, model)

        # Add point attributes from Grove
        _add_grove_point_attributes(mesh, model)

        # Set display color (default gray for bark)
        mesh.CreateDisplayColorAttr([Gf.Vec3f(0.4, 0.3, 0.2)])

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error building USD file: {e}")
        import traceback

        traceback.print_exc()
        return False


def _add_grove_face_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove face attributes as USD primvars.

    These attributes are critical for twig placement and material assignment.
    Uses PascalCase naming convention to match Grove's native export.

    Args:
        mesh: USD mesh to add attributes to
        model: Grove model with face attributes
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Twig placement attributes
    if hasattr(model, "face_attribute_twig_long"):
        primvar = primvars_api.CreatePrimvar(
            "TwigLong", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_long)

    if hasattr(model, "face_attribute_twig_short"):
        primvar = primvars_api.CreatePrimvar(
            "TwigShort", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_short)

    if hasattr(model, "face_attribute_twig_upward"):
        primvar = primvars_api.CreatePrimvar(
            "TwigUpward", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_upward)

    if hasattr(model, "face_attribute_twig_dead"):
        primvar = primvars_api.CreatePrimvar(
            "TwigDead", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_twig_dead)

    # Branch state attributes
    if hasattr(model, "face_attribute_dead"):
        primvar = primvars_api.CreatePrimvar(
            "Dead", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_dead)

    if hasattr(model, "face_attribute_end"):
        primvar = primvars_api.CreatePrimvar(
            "End", Sdf.ValueTypeNames.BoolArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_end)

    # Branch identification
    if hasattr(model, "face_attribute_branch_index"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndex", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_index)

    if hasattr(model, "face_attribute_branch_index_parent"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndexParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_index_parent)

    if hasattr(model, "face_attribute_branch_index_parent"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndexParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_index_parent)


def _add_grove_point_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove point attributes as USD primvars.

    These attributes provide useful metadata about tree structure and growth.

    Args:
        mesh: USD mesh to add attributes to
        model: Grove model with point attributes
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Age and structure
    if hasattr(model, "point_attribute_age"):
        primvar = primvars_api.CreatePrimvar(
            "Age", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_age)

    if hasattr(model, "point_attribute_mass"):
        primvar = primvars_api.CreatePrimvar(
            "Mass", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_mass)

    # Physical properties
    if hasattr(model, "point_attribute_thickness"):
        primvar = primvars_api.CreatePrimvar(
            "Thickness", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_thickness)

    if hasattr(model, "point_attribute_pitch"):
        primvar = primvars_api.CreatePrimvar(
            "Pitch", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_pitch)

    # Growth and lighting
    if hasattr(model, "point_attribute_vigor"):
        primvar = primvars_api.CreatePrimvar(
            "Vigor", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_vigor)

    if hasattr(model, "point_attribute_shade"):
        primvar = primvars_api.CreatePrimvar(
            "Shade", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_shade)

    if hasattr(model, "point_attribute_photosynthesis"):
        primvar = primvars_api.CreatePrimvar(
            "Photosynthesis", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_photosynthesis)


def add_skeleton_to_usd(
    usd_path: Path,
    grove: Any,
    skeleton_length: float = 2.0,
    skeleton_reduce: float = 0.4,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add skeleton to existing USD file using Grove's tag_bone_id API.

    This function uses Grove's advanced skeleton bone tagging system to create
    a UsdSkel skeleton. The bones are generated using the same parameters as
    Grove's native Blender export.

    Args:
        usd_path: Path to existing USD file with tree mesh
        grove: Grove instance with simulated tree
        skeleton_length: Length threshold for bone creation
        skeleton_reduce: Reduction factor for thin branches
        skeleton_bias: Bias towards parent or child bones
        skeleton_connected: Whether bones are connected in hierarchy

    Returns:
        bool: True if skeleton was added successfully

    Example:
        >>> build_tree_usd(model, Path("tree.usda"))
        >>> add_skeleton_to_usd(
        ...     Path("tree.usda"),
        ...     grove,
        ...     skeleton_length=2.0,
        ...     skeleton_reduce=0.4
        ... )
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Usd, UsdGeom, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Error: Could not open USD stage at {usd_path}")
            return False

        # Build skeleton from grove
        skeletons = grove.build_skeletons()
        if not skeletons:
            print("Error: No skeletons generated from grove")
            return False

        skeleton = skeletons[0]

        # Tag bones with custom parameters (matches Blender operator)
        bones = grove.tag_bone_id(
            skeleton_length,
            skeleton_reduce**2,  # Square the reduce value
            skeleton_bias,
            skeleton_connected,
        )

        if not bones:
            print("Error: No bones generated from skeleton")
            return False

        # Create UsdSkel skeleton structure
        _build_usdskel_from_bones(stage, skeleton, bones)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding skeleton to USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def _build_usdskel_from_bones(
    stage: Usd.Stage,
    skeleton: Any,
    bones: List[Tuple],
) -> None:
    """Build UsdSkel skeleton from Grove bones.

    Args:
        stage: USD stage to add skeleton to
        skeleton: Grove skeleton object
        bones: List of bone tuples from grove.tag_bone_id()
    """
    from pxr import Gf, Sdf, UsdGeom, UsdSkel, Vt

    # Find mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if not mesh_prim:
        print("Warning: No mesh found in USD stage")
        return

    # Create skeleton prim at root level
    skel_root_path = Sdf.Path("/Tree/Skeleton")
    skel_root = UsdSkel.Root.Define(stage, skel_root_path)

    # Apply Unreal skeletal mesh schema to SkelRoot
    skel_root_prim = stage.GetPrimAtPath(skel_root_path)
    skel_root_prim.SetMetadata(
        "apiSchemas",
        Sdf.TokenListOp.Create(prependedItems=["UnrealNaniteAssemblyRootAPI"]),
    )
    skel_root_prim.CreateAttribute(
        "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token
    ).Set("skeletalMesh")

    skel_path = skel_root_path.AppendChild("TreeSkel")
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Set skeleton relationship for Unreal
    skel_root_prim.CreateRelationship("unreal:naniteAssembly:skeleton").SetTargets(
        [skel_path]
    )

    # Build joint hierarchy with proper parent-child relationships
    joint_tokens = []
    bind_transforms = []
    rest_transforms = []

    # Create joint hierarchy map and calculate local transforms
    bone_to_joint_path = {}  # bone_idx -> full joint path
    bone_positions = {}  # bone_idx -> world position (for calculating local offsets)

    # Get root bone offset to align skeleton with mesh at origin
    root_offset = Gf.Vec3d(0, 0, 0)
    if len(bones) > 0:
        root_bone = bones[0]
        root_start = root_bone[2]  # start_point
        root_offset = Gf.Vec3d(root_start.x, root_start.y, root_start.z)

    #  # Bone format: (is_root, bone_id, start_point, end_point, radius1, radius2, connected, parent_branch_id)
    # Note: bone_id is actually the branch ID, parent_bone_idx is actually parent branch ID

    # First pass: map branch_id -> list of bone indices in that branch
    branch_to_bones = {}
    for bone_idx, bone in enumerate(bones):
        branch_id = bone[1]  # Field 1 is branch_id
        if branch_id not in branch_to_bones:
            branch_to_bones[branch_id] = []
        branch_to_bones[branch_id].append(bone_idx)

    # Second pass: build joint paths
    for bone_idx, bone in enumerate(bones):
        (
            is_root,
            branch_id,  # This is the branch ID this bone belongs to
            start_point,
            end_point,
            radius1,
            radius2,
            connected,
            parent_branch_id,  # This is the parent BRANCH ID, not parent bone index
        ) = bone

        # Build hierarchical joint path
        joint_name = f"joint_{bone_idx}"

        if is_root:
            # Root bone - no parent
            joint_path = joint_name
            parent_for_hierarchy = None
        elif connected and bone_idx > 0:
            # Connected bone - parent is previous bone in sequence
            parent_for_hierarchy = bone_idx - 1
            parent_path = bone_to_joint_path.get(parent_for_hierarchy, "")
            if parent_path:
                joint_path = f"{parent_path}/{joint_name}"
            else:
                joint_path = joint_name
        else:
            # New branch starting - attach to last bone of parent branch
            if parent_branch_id in branch_to_bones:
                # Find last bone in parent branch
                parent_branch_bones = branch_to_bones[parent_branch_id]
                parent_for_hierarchy = parent_branch_bones[-1]
                parent_path = bone_to_joint_path.get(parent_for_hierarchy, "")
                if parent_path:
                    joint_path = f"{parent_path}/{joint_name}"
                else:
                    joint_path = joint_name
            else:
                # Fallback - attach to root
                parent_for_hierarchy = 0
                parent_path = bone_to_joint_path.get(0, "")
                if parent_path:
                    joint_path = f"{parent_path}/{joint_name}"
                else:
                    joint_path = joint_name

        bone_to_joint_path[bone_idx] = joint_path
        joint_tokens.append(joint_path)

        # Store world position for this bone (offset by root to align with mesh at origin)
        world_pos = Gf.Vec3d(start_point.x, start_point.y, start_point.z) - root_offset
        bone_positions[bone_idx] = world_pos

        # Calculate LOCAL transform (relative to parent)
        if parent_for_hierarchy is None:
            # Root bone is now at origin since we subtracted root_offset
            local_pos = world_pos
        else:
            # Child bone: position relative to parent
            parent_pos = bone_positions.get(parent_for_hierarchy, Gf.Vec3d(0, 0, 0))
            local_pos = world_pos - parent_pos

        transform = Gf.Matrix4d(1.0)
        transform.SetTranslateOnly(local_pos)

        bind_transforms.append(transform)
        rest_transforms.append(transform)

    # Set skeleton attributes
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # Re-parent mesh under SkelRoot
    new_mesh_path = skel_root_path.AppendChild("TreeMesh")

    # Copy mesh to new location
    old_mesh_path = mesh_prim.GetPath()
    Sdf.CopySpec(
        stage.GetRootLayer(), old_mesh_path, stage.GetRootLayer(), new_mesh_path
    )

    # Remove old mesh
    stage.RemovePrim(old_mesh_path)

    # Get the new mesh prim
    mesh_prim = stage.GetPrimAtPath(new_mesh_path)
    mesh = UsdGeom.Mesh(mesh_prim)

    # Bind mesh to skeleton
    binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
    binding_api.CreateSkeletonRel().SetTargets([skel_path])

    # Add skinning data (joint influences and weights)
    # Use BranchIndex from face attributes to map vertices to bones
    points = mesh.GetPointsAttr().Get()
    num_points = len(points)

    # Get BranchIndex primvar to know which branch each face belongs to
    primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
    branch_index_primvar = primvars_api.GetPrimvar("BranchIndex")

    # Create vertex-to-joint mapping
    joint_indices = []
    joint_weights = []

    if branch_index_primvar and branch_index_primvar.HasValue():
        # Get per-face branch indices
        branch_indices = branch_index_primvar.Get()
        face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

        # Map each vertex to its bone based on which face(s) it belongs to
        vertex_to_joint = {}  # vertex_idx -> (joint_idx, weight)

        face_idx = 0
        vert_offset = 0
        for face_vert_count in face_vertex_counts:
            branch_idx = branch_indices[face_idx]
            # Map branch index to bone index (branch_id maps to bone)
            bone_idx = min(branch_idx, len(bones) - 1)  # Clamp to valid bone

            # Assign this bone to all vertices of this face
            for i in range(face_vert_count):
                vertex_idx = face_vertex_indices[vert_offset + i]
                # Simple assignment: vertex fully weighted to its branch's bone
                vertex_to_joint[vertex_idx] = (bone_idx, 1.0)

            vert_offset += face_vert_count
            face_idx += 1

        # Build final arrays (one entry per vertex)
        for v_idx in range(num_points):
            if v_idx in vertex_to_joint:
                joint_idx, weight = vertex_to_joint[v_idx]
                joint_indices.append(joint_idx)
                joint_weights.append(weight)
            else:
                # Unassigned vertices bound to root
                joint_indices.append(0)
                joint_weights.append(1.0)
    else:
        # Fallback: all vertices bound to root
        joint_indices = [0] * num_points
        joint_weights = [1.0] * num_points

    # Set skinning attributes with proper element size
    binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
    binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

    return skel


def add_materials_to_usd(
    usd_path: Path,
    species_name: str,
    textures: Optional[dict] = None,
) -> bool:
    """Add material and texture bindings to USD file.

    Args:
        usd_path: Path to USD file
        species_name: Species name for material naming
        textures: Dictionary with texture paths (diffuse, normal, roughness)

    Returns:
        bool: True if materials were added successfully
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
        from pxr import Sdf, Usd, UsdGeom, UsdShade

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Error: Could not open USD stage at {usd_path}")
            return False

        # Find mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            print("Warning: No mesh found in USD stage")
            return False

        # Create material
        material_path = mesh_prim.GetPath().GetParentPath().AppendChild("BarkMaterial")
        material = UsdShade.Material.Define(stage, material_path)

        # Create shader
        shader_path = material_path.AppendChild("Shader")
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")

        # Set material properties
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.4, 0.3, 0.2)
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)

        # Add texture inputs if provided
        if textures:
            # TODO: Add texture file references
            pass

        # Connect shader to material output
        material.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )

        # Bind material to mesh
        UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding materials to USD: {e}")
        import traceback

        traceback.print_exc()
        return False
