"""Tree export functionality for USD format with skeletal animation support.

This module handles USD tree export by merging functionality from blender_export
and usd_builder. It provides direct Grove model to USD conversion with proper
skeleton integration, material binding, and Nanite Assembly support.

Key Features:
- Direct Grove model to USD export without coordinate transformations
- Skeletal animation support with UsdSkel hierarchy
- Twig placement data preservation via primvars
- Material and texture binding
- Nanite Assembly creation for Unreal Engine 5.7+

Exported Grove Model Attributes (as USD primvars):
- All face_attribute_* exported as uniform primvars (per-face):
  * branch_id, branch_id_parent, tree_id
  * twig_long, twig_short, twig_upward, twig_dead
  * dead, end, direction
- All point_attribute_* exported as vertex primvars (per-vertex):
  * age, mass, thickness, orientation, pitch
  * vigor, shade, photosynthesis
  * bone_id, skeleton_joint_id
- Alternative twig placement methods (not currently exported):
  * model.get_twig_locations()
  * model.get_twig_orientations()
  * model.get_twig_directions()

Exported Skeleton Attributes:
- Skeleton points, poly_lines, location
- Skeleton attributes: branch_id, point_age, point_mass, point_radius
- Advanced bones from grove.tag_bone_id()

Grove-Level Attributes (not exported to USD):
- grove.total_mass - Total mass of all trees
- grove.number_of_branches - Total branch count
- grove.height - Maximum tree height
- grove.age - Grove age in flushes
- grove.roots - Root system geometry (if grown with grow_roots/build_roots)

Main Functions:
- export_tree(): Export complete tree with skeleton (formerly export_grove_tree_as_usda_native)
- build_tree_mesh(): Build USD mesh from Grove model (formerly build_tree_usd)
- add_skeleton_to_usd(): Add skeleton to existing USD file
- add_twig_skeleton_to_usd(): Add simple skeleton for twig meshes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import the_grove_22_core as gc
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

from ..config import get_config
from ..core.skeleton import calculate_vertex_weights


def export_tree(
    model: Any,
    skeleton: Any,
    output_path: Path,
    species_name: str,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Export Grove tree model as USD for Unreal Engine 5 Nanite.

    This is the main export function that creates a complete USD file with
    tree mesh, skeleton, materials, and all Grove attributes preserved.
    The skeleton is always included for wind animation support.

    Note: To export from a grove with multiple trees, call this function
    once per tree with corresponding model/skeleton pairs:
        models = grove.build_models({...})
        skeletons = grove.build_skeletons()
        for model, skeleton in zip(models, skeletons):
            export_tree(model, skeleton, output_path, species_name)

    Args:
        model: Grove tree model from grove.build_models()
        skeleton: Grove skeleton from grove.build_skeletons()
        output_path: Path for the USD file (.usd or .usda)
        species_name: Tree species name for material naming
        skeleton_length: Bone length multiplier (default: 1.0, higher=longer bones)
        skeleton_reduce: Bone reduction factor (default: 0.25, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Whether bones are connected (default: True)

    Returns:
        bool: Success status

    Example:
        >>> grove = gc.Grove()
        >>> grove.add_new_tree(...)
        >>> grove.simulate(5)
        >>> models = grove.build_models({...})
        >>> skeletons = grove.build_skeletons()
        >>> export_tree(models[0], skeletons[0], Path("tree.usda"), "oak")
    """
    config = get_config()

    try:
        # Configure model for optimal export compatibility
        try:
            # Set up-axis to Z for Blender/Unreal compatibility
            model.set_up_axis("Z")
            # Set counter-clockwise winding for standard compatibility
            model.set_winding_order("COUNTER_CLOCKWISE")
        except Exception as e:
            pass

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build USD directly from Grove model with skeleton (no Blender export needed)
        success = build_tree_mesh(
            model=model,
            skeleton=skeleton,
            output_path=output_path,
            up_axis="Z",
            triangulated=True,
            include_materials=False,
            clean_export=False,
            skeleton_length=skeleton_length,
            skeleton_reduce=skeleton_reduce,
            skeleton_bias=skeleton_bias,
            skeleton_connected=skeleton_connected,
        )

        if not success:
            return False

        # Add Nanite attributes to USD file
        add_nanite_attributes_to_usd(output_path, is_foliage=False)

        return True

    except Exception as e:
        import traceback

        traceback.print_exc()
        return False


def build_tree_mesh(
    model: Any,
    skeleton: Optional[Any],
    output_path: Path,
    bones_info: Optional[List] = None,
    up_axis: str = "Z",
    triangulated: bool = True,
    include_materials: bool = False,
    clean_export: bool = False,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Build USD file directly from Grove model using API geometry data.

    This function extracts geometry data directly from the Grove model using
    the Python API and constructs a USD file without coordinate transformations.
    If skeleton is provided, adds skeleton structure inline.

    CRITICAL: The model must be triangulated BEFORE calling this function:
        model.triangulate()

    This ensures that face counts match between geometry and face attributes,
    preventing mismatches in twig placement and material assignment.

    CRITICAL: For skeletal export with proper vertex-to-bone mapping, bones_info must be provided.
    This enables direct vertex-to-bone mapping via model.point_attribute_bone_id.

    Args:
        model: Grove tree model from grove.build_models() - MUST be triangulated first
        skeleton: Optional Grove skeleton from grove.build_skeletons()
        output_path: Path where USD file will be saved
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this tree
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated (should always be True)
        include_materials: If False, creates simple geometry without materials/UVs
        clean_export: If True, creates minimal USD without default attributes (demo mode)
        skeleton_length: Bone length multiplier for skeleton creation (deprecated if bones_info provided)
        skeleton_reduce: Bone reduction factor for skeleton creation (deprecated if bones_info provided)
        skeleton_bias: Weight bias for skinning
        skeleton_connected: Use connected bone hierarchy (deprecated if bones_info provided)

    Returns:
        bool: True if USD file was created successfully
    """

    try:
        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata
        UsdGeom.SetStageUpAxis(
            stage, UsdGeom.Tokens.z if up_axis == "Z" else UsdGeom.Tokens.y
        )
        stage.SetMetadata("metersPerUnit", 1.0)

        # Store clean_export mode for skeleton addition
        if clean_export:
            stage.SetMetadata("customLayerData", {"clean_export": True})

        # Define root xform
        root_path = Sdf.Path("/tree")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Store tree location as metadata for forest positioning reference
        if hasattr(model, "location") and model.location:
            loc = model.location
            root_xform.GetPrim().SetCustomDataByKey(
                "treeLocation", Gf.Vec3f(loc.x, loc.y, loc.z)
            )

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
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = []
        for face in faces:
            face_vertex_indices.extend(face)

        # Set mesh topology
        mesh.CreatePointsAttr(usd_points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Materials and textures disabled for Nanite assembly compatibility
        # UV coordinates and materials cause issues with Nanite assembly import

        # Add all model attributes from Grove (face and point attributes)
        _add_model_attributes(mesh, model)

        # Store UV islands as metadata for texture atlas reference
        if hasattr(model, "uv_islands") and model.uv_islands:
            # Store count and structure info as metadata
            mesh.GetPrim().SetCustomDataByKey("uvIslandCount", len(model.uv_islands))
            # Note: Full island data available but not stored to keep file size reasonable
            # Can be accessed via model.uv_islands or model.get_uv_islands_flat() if needed

        # Add normals for proper Unreal rendering
        _add_mesh_normals(mesh, model)

        # Add skeleton if provided
        if skeleton is not None:
            skeleton_added = _add_skeleton_to_stage_inline(
                stage=stage,
                skeleton=skeleton,
                root_xform_prim=root_xform.GetPrim(),
                mesh_prim=mesh.GetPrim(),
                model=model,
                bones_info=bones_info,
                skeleton_length=skeleton_length,
                skeleton_reduce=skeleton_reduce,
                skeleton_bias=skeleton_bias,
                skeleton_connected=skeleton_connected,
            )
            if skeleton_added:
                pass
            else:
                pass

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        import traceback

        traceback.print_exc()
        return False


# Helper functions for internal use


def _add_skeleton_to_stage_inline(
    stage: Usd.Stage,
    skeleton: Any,
    root_xform_prim: Usd.Prim,
    mesh_prim: Usd.Prim,
    model: Optional[Any] = None,
    bones_info: Optional[List] = None,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add skeleton to open USD stage using Grove's skeleton data.

    CRITICAL: If bones_info is provided, it will be used for direct vertex-to-bone mapping
    via model.point_attribute_bone_id. This is the preferred method as it uses Grove's
    internal mapping rather than distance calculations.

    Args:
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this tree
                   If provided, enables direct vertex-to-bone mapping
    """
    try:
        if not skeleton:
            return False

        # Create UsdSkel skeleton structure directly in the stage
        # Pass bones_info for direct vertex-to-bone mapping
        _build_usdskel_from_bones(stage, skeleton, model, bones_info)

        return True

    except Exception as e:
        import traceback

        traceback.print_exc()
        return False


def add_nanite_attributes_to_usd(usd_path: Path, is_foliage: bool = False) -> bool:
    """Add Nanite-specific USD attributes to exported USD file.

    Args:
        usd_path: Path to USD file
        is_foliage: Whether this is foliage (twigs/leaves) requiring Preserve Area

    Returns:
        bool: Success status
    """
    try:
        # Open USD stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Add Nanite attributes to all meshes
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                # Enable Nanite
                prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set(
                    "enable"
                )

                # For foliage, enable Preserve Area
                if is_foliage:
                    prim.CreateAttribute(
                        "unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool
                    ).Set(True)

        # Save changes
        stage.GetRootLayer().Save()
        return True

    except Exception as e:
        return False


def _add_skeleton_to_object(
    obj: Any,
    skeleton: Any,
    species_name: str,
    grove: Any,
    model: Optional[Any] = None,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> Any:
    """Add skeleton/armature to the tree object with proper vertex weights.

    Uses Grove's tag_bone_id() to identify which bones are actually needed.

    Args:
        obj: Blender mesh object
        skeleton: Grove skeleton data
        species_name: Name of the tree species
        grove: Grove instance for weight calculation
        model: Grove model with face/vertex data (required for weights)
        skeleton_length: Bone length multiplier
        skeleton_reduce: Bone reduction factor
        skeleton_bias: Weight bias
        skeleton_connected: Whether bones are connected

    Returns:
        The armature object created
    """
    import time

    try:
        # Calculate vertex weights using Grove's tagging system
        vertices = [(v.co.x, v.co.y, v.co.z) for v in obj.data.vertices]
        faces = [[v for v in poly.vertices] for poly in obj.data.polygons]

        t_weight_start = time.time()
        vertex_to_joints, vertex_to_weights = calculate_vertex_weights(
            model,
            skeleton,
            vertices,
            faces,
            grove,
            skeleton_length,
            skeleton_reduce,
            skeleton_bias,
            skeleton_connected,
        )
        t_weight_calc = time.time()

        # Find unique bones that are actually used
        used_bone_indices = set()
        for joint_indices in vertex_to_joints:
            used_bone_indices.update(joint_indices)

        num_bones_needed = len(used_bone_indices)

        # Create armature
        armature = bpy.data.armatures.new(f"{species_name}_armature")
        armature_obj = bpy.data.objects.new(f"{species_name}_skeleton", armature)
        bpy.context.collection.objects.link(armature_obj)

        # Enter edit mode to add bones
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Get skeleton data
        points = skeleton.points
        poly_lines = skeleton.poly_lines

        # Create ONLY the bones that are actually used
        bone_names = []
        bones_map = {}
        point_to_bone = {}

        # Create root bone at index 0
        root_bone = armature.edit_bones.new("Root")
        root_bone.head = (0, 0, 0)
        root_bone.tail = (0, 0, 0.1)
        bone_names.append("Root")
        bones_map[0] = root_bone

        # Build bones from polylines
        bone_index = 1
        for poly_line in poly_lines:
            if len(poly_line) < 2:
                continue

            previous_bone = None
            for j in range(len(poly_line) - 1):
                start_idx = poly_line[j]
                end_idx = poly_line[j + 1]

                if bone_index in used_bone_indices:
                    bone_name = f"bone_{bone_index}"
                    bone = armature.edit_bones.new(bone_name)
                    bone_names.append(bone_name)
                    bones_map[bone_index] = bone

                    if start_idx < len(points) and end_idx < len(points):
                        bone.head = points[start_idx]
                        bone.tail = points[end_idx]

                    # Set parent bone
                    if j == 0:
                        if start_idx in point_to_bone:
                            bone.parent = point_to_bone[start_idx]
                        else:
                            bone.parent = root_bone
                    else:
                        if previous_bone is not None:
                            bone.parent = previous_bone
                        else:
                            bone.parent = root_bone

                    point_to_bone[end_idx] = bone
                    previous_bone = bone

                bone_index += 1

        bpy.ops.object.mode_set(mode="OBJECT")
        t_bones = time.time()

        # Parent mesh to armature
        obj.parent = armature_obj
        obj.parent_type = "OBJECT"

        # Add armature modifier
        modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = armature_obj
        modifier.use_vertex_groups = True

        # Create vertex groups and assign weights
        for bone_name in bone_names:
            obj.vertex_groups.new(name=bone_name)

        t_assign_start = time.time()
        for vert_idx, (joint_indices, weights) in enumerate(
            zip(vertex_to_joints, vertex_to_weights)
        ):
            for joint_idx, weight in zip(joint_indices, weights):
                if joint_idx < len(bone_names) and weight > 0.0:
                    bone_name = bone_names[joint_idx]
                    vgroup = obj.vertex_groups[bone_name]
                    vgroup.add([vert_idx], weight, "REPLACE")
        t_assign_end = time.time()

        return armature_obj

    except Exception as e:
        import traceback

        traceback.print_exc()
        return None


def _add_grove_attributes_to_mesh(mesh: Any, model: Any) -> None:
    """Add Grove model attributes to Blender mesh as custom properties."""
    try:
        # Face (polygon) attributes - critical for twig placements
        if hasattr(model, "face_attribute_twig_long"):
            face_layer = mesh.attributes.new(
                name="twig_long", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_twig_long):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_twig_short"):
            face_layer = mesh.attributes.new(
                name="twig_short", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_twig_short):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_twig_upward"):
            face_layer = mesh.attributes.new(
                name="twig_upward", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_twig_upward):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_twig_dead"):
            face_layer = mesh.attributes.new(
                name="twig_dead", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_twig_dead):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_dead"):
            face_layer = mesh.attributes.new(
                name="branch_dead", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_dead):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_branch_id"):
            face_layer = mesh.attributes.new(
                name="branch_id", type="INT", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_branch_id):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_branch_id_parent"):
            face_layer = mesh.attributes.new(
                name="branch_id_parent", type="INT", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_branch_id_parent):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_end"):
            face_layer = mesh.attributes.new(
                name="branch_end", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_end):
                face_layer.data[i].value = val

        # Point (vertex) attributes
        if hasattr(model, "point_attribute_age"):
            point_layer = mesh.attributes.new(name="age", type="INT", domain="POINT")
            for i, val in enumerate(model.point_attribute_age):
                point_layer.data[i].value = val

        if hasattr(model, "point_attribute_thickness"):
            point_layer = mesh.attributes.new(
                name="thickness", type="FLOAT", domain="POINT"
            )
            for i, val in enumerate(model.point_attribute_thickness):
                point_layer.data[i].value = val

    except Exception as e:
        pass


def _add_blender_attributes_as_usd_primvars(usd_path: Path, mesh_obj: Any) -> None:
    """Write Blender mesh attributes as USD primvars after export."""
    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return

        # Find the mesh prim
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue

            mesh_usd = UsdGeom.Mesh(prim)
            primvars_api = UsdGeom.PrimvarsAPI(mesh_usd)
            mesh_data = mesh_obj.data

            # Twig attributes (FACE domain)
            twig_attrs = [
                ("twig_long", Sdf.ValueTypeNames.Bool),
                ("twig_short", Sdf.ValueTypeNames.Bool),
                ("twig_upward", Sdf.ValueTypeNames.Bool),
                ("twig_dead", Sdf.ValueTypeNames.Bool),
            ]

            for attr_name, value_type in twig_attrs:
                if attr_name in mesh_data.attributes:
                    attr = mesh_data.attributes[attr_name]
                    values = [attr.data[i].value for i in range(len(attr.data))]

                    primvar = primvars_api.CreatePrimvar(
                        attr_name, value_type, UsdGeom.Tokens.uniform
                    )
                    primvar.Set(values)

        stage.Save()

    except Exception as e:
        pass


def _add_material_with_textures(obj: Any, species_name: str, config: Any) -> None:
    """Add material with textures to Blender object."""
    try:
        from ..config import get_config

        config = get_config()
        textures = _find_bark_texture(species_name, config)

        if not textures:
            return

        # Create material
        mat = bpy.data.materials.new(name=f"{species_name}_bark")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear default nodes
        nodes.clear()

        # Create nodes
        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")

        # Position nodes
        output_node.location = (300, 0)
        bsdf_node.location = (0, 0)

        # Link BSDF to output
        links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

        # Add diffuse texture if available
        if "diffuse" in textures:
            tex_node = nodes.new(type="ShaderNodeTexImage")
            tex_node.image = bpy.data.images.load(str(textures["diffuse"]))
            tex_node.location = (-300, 0)
            links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])

        # Assign material to object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    except Exception as e:
        pass


def _find_bark_texture(species_name: str, config: Any) -> Optional[Dict[str, Path]]:
    """Find bark textures for species."""
    try:
        texture_dir = config.assets_root / "textures"
        if not texture_dir.exists():
            return None

        textures = {}

        # Look for diffuse texture
        for pattern in [f"{species_name}_bark.png", f"{species_name}_diffuse.png"]:
            texture_path = texture_dir / pattern
            if texture_path.exists():
                textures["diffuse"] = texture_path
                break

        # Look for normal texture
        for pattern in [f"{species_name}_normal.png", f"{species_name}_norm.png"]:
            texture_path = texture_dir / pattern
            if texture_path.exists():
                textures["normal"] = texture_path
                break

        return textures if textures else None

    except Exception as e:
        return None


def _add_model_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add all Grove model attributes as USD primvars.

    Dynamically discovers and adds all face_attribute_* and point_attribute_*
    from the model, handling different attribute types automatically.

    Face attributes are added with 'uniform' interpolation (per-face).
    Point attributes are added with 'vertex' interpolation (per-vertex).

    Skeleton-related attributes (bone_id, skeleton_joint_id) are skipped
    as they're handled separately during skeleton binding.
    """
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Mapping of attribute value types to USD types
    def get_usd_type(attr_value):
        """Determine USD value type from Python attribute."""
        if not attr_value or len(attr_value) == 0:
            return None

        sample = attr_value[0]
        if isinstance(sample, bool):
            return Sdf.ValueTypeNames.BoolArray
        elif isinstance(sample, int):
            return Sdf.ValueTypeNames.IntArray
        elif isinstance(sample, float):
            return Sdf.ValueTypeNames.FloatArray
        elif isinstance(sample, (tuple, list)) and len(sample) == 3:
            # Vector3 type
            return Sdf.ValueTypeNames.Float3Array
        else:
            # Default to float for unknown types
            return Sdf.ValueTypeNames.FloatArray

    # Get all attribute names from model
    model_attrs = dir(model)

    # Process face attributes (per-face, uniform interpolation)
    face_attrs = [attr for attr in model_attrs if attr.startswith("face_attribute_")]
    for attr_name in sorted(face_attrs):
        try:
            attr_value = getattr(model, attr_name, None)
            if attr_value is None or len(attr_value) == 0:
                continue

            # Convert branch IDs from global to local indices
            # This requires branch_id_offset from skeleton building
            if attr_name in (
                "face_attribute_branch_id",
                "face_attribute_branch_id_parent",
            ):
                # These will be handled separately with proper offset conversion
                # For now, skip them - they'll be added after skeleton building
                continue

            usd_type = get_usd_type(attr_value)
            if usd_type is None:
                continue

            # Convert attribute name to PascalCase for USD
            # e.g., face_attribute_thickness -> Thickness
            primvar_name = "".join(
                word.capitalize()
                for word in attr_name.replace("face_attribute_", "").split("_")
            )

            primvar = primvars_api.CreatePrimvar(
                primvar_name, usd_type, UsdGeom.Tokens.uniform
            )
            primvar.Set(attr_value)

        except Exception as e:
            # Skip attributes that fail to convert
            pass

    # Process point attributes (per-vertex, vertex interpolation)
    point_attrs = [attr for attr in model_attrs if attr.startswith("point_attribute_")]

    for attr_name in sorted(point_attrs):
        try:
            # Skip bone_id as it's handled separately in skeleton binding
            # The jointIndices primvar will have the local bone indices
            if attr_name == "point_attribute_bone_id":
                continue

            attr_value = getattr(model, attr_name, None)
            if attr_value is None or len(attr_value) == 0:
                continue

            usd_type = get_usd_type(attr_value)
            if usd_type is None:
                continue

            # Convert attribute name to PascalCase for USD
            # e.g., point_attribute_thickness -> Thickness
            primvar_name = "".join(
                word.capitalize()
                for word in attr_name.replace("point_attribute_", "").split("_")
            )

            primvar = primvars_api.CreatePrimvar(
                primvar_name, usd_type, UsdGeom.Tokens.vertex
            )
            primvar.Set(attr_value)

        except Exception as e:
            # Skip attributes that fail to convert
            pass


def _add_usd_materials(
    stage: Usd.Stage, mesh_prim: UsdGeom.Mesh, model: Any, mesh_path: str
) -> None:
    """Create proper USD materials for Unreal Engine compatibility.

    NOTE: Only bark material is applied to tree skeletal mesh.
    Twig materials are handled separately in twig USD files.
    """
    # Define bark material color
    BARK_BROWN = Gf.Vec3f(0.45, 0.30, 0.20)

    # Create materials path
    materials_path = mesh_path + "/Materials"
    UsdGeom.Scope.Define(stage, materials_path)

    def create_material(name: str, color: Gf.Vec3f) -> UsdShade.Material:
        mat = UsdShade.Material.Define(stage, f"{materials_path}/{name}")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/{name}/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        return mat

    # Create only bark material for tree mesh
    bark_mat = create_material("BarkMaterial", BARK_BROWN)

    # Apply MaterialBindingAPI schema first, then bind material
    binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim.GetPrim())
    binding_api.Bind(bark_mat)


def _add_mesh_normals(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add normals to mesh for proper Unreal rendering.

    Prefers using actual normals from model.shape if available,
    falls back to simple up-facing normals if not.
    """
    try:
        # Try to use real normals from model.shape
        if hasattr(model, "shape") and model.shape:
            # model.shape contains normal vectors for each vertex
            # Convert to USD format
            normals = []
            for normal in model.shape:
                if hasattr(normal, "x"):
                    # Vector object
                    normals.append(Gf.Vec3f(normal.x, normal.y, normal.z))
                elif isinstance(normal, (tuple, list)) and len(normal) == 3:
                    # Tuple/list format
                    normals.append(Gf.Vec3f(normal[0], normal[1], normal[2]))
                else:
                    # Unknown format, skip
                    continue

            if normals:
                normals_attr = mesh.CreateNormalsAttr()
                normals_attr.Set(normals)
                # Use vertex interpolation for per-vertex normals
                mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                return

        # Fallback: create simple per-face normals
        faces = model.faces if hasattr(model, "faces") else []
        if faces:
            # Create up-facing normals for each face
            normals = [Gf.Vec3f(0, 0, 1) for _ in faces]
            normals_attr = mesh.CreateNormalsAttr()
            normals_attr.Set(normals)
            mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

    except Exception:
        pass



def _build_usdskel_from_bones(
    stage: Usd.Stage,
    skeleton: Any,
    model: Optional[Any] = None,
    bones_info: Optional[List[Tuple]] = None,
    twig_placements: Optional[Dict[str, List[Dict]]] = None,
    verbose: bool = False,
) -> None:
    """Build UsdSkel skeleton from Grove skeleton polylines.

    CRITICAL for Unreal Engine recognition:
    1. SkelRoot MUST have SkelBindingAPI applied
    2. SkelRoot MUST have skel:skeleton relationship pointing to Skeleton prim
    3. Mesh should NOT have any skel:* relationships (those go on SkelRoot only)

    CRITICAL for proper vertex-to-bone mapping:
    - If bones_info is provided AND model has point_attribute_bone_id, uses direct mapping
    - This is the preferred method as it uses Grove's internal vertex-to-bone assignments
    - Falls back to distance-based mapping only if point_attribute_bone_id is unavailable

    Args:
        stage: USD stage to add skeleton to
        skeleton: Grove skeleton object with points and poly_lines
        model: Optional Grove model with point_attribute_bone_id for direct mapping
        bones_info: Optional list of bone tuples from grove.tag_bone_id()
        twig_placements: Optional twig placement data (deprecated)
        verbose: Whether to print debug information
    """
    # Find mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if not mesh_prim:
        return

    # Convert /tree to SkelRoot with proper API schemas
    tree_prim = stage.GetPrimAtPath("/tree")
    if tree_prim:
        # Redefine as SkelRoot if not already
        if not tree_prim.IsA(UsdSkel.Root):
            skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/tree"))
            tree_prim = skel_root.GetPrim()
    else:
        skel_root = UsdSkel.Root.Define(stage, Sdf.Path("/tree"))
        tree_prim = skel_root.GetPrim()

    # CRITICAL: Apply SkelBindingAPI to SkelRoot using proper metadata
    # This is required for Unreal Engine to recognize the skeletal structure
    api_schemas = tree_prim.GetMetadata("apiSchemas")
    if api_schemas:
        # Append to existing schemas
        if "SkelBindingAPI" not in api_schemas.prependedItems:
            api_schemas.prependedItems.append("SkelBindingAPI")
            tree_prim.SetMetadata("apiSchemas", api_schemas)
    else:
        # Create new TokenListOp
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["SkelBindingAPI"]
        tree_prim.SetMetadata("apiSchemas", api_schemas)

    # Create skeleton as sibling to mesh (both under SkelRoot)
    skel_path = Sdf.Path("/tree/TreeSkel")
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Build joint hierarchy
    joint_tokens = []
    bind_transforms = []
    rest_transforms = []

    # Get tree offset for local space conversion
    tree_offset = (
        Gf.Vec3d(model.location.x, model.location.y, model.location.z)
        if model and hasattr(model, "location") and model.location
        else Gf.Vec3d(0, 0, 0)
    )

    # Build joint hierarchy from bones_info if available

    # bones_info format: (is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
    # CRITICAL: parent_bone_id values in bones_info are already global bone indices across all trees
    # However, bone indices in the array restart at 0 for each tree

    # Calculate bone ID offset from first bone
    # If first bone is tree root and parent_bone_id > 0, that's the offset
    # If first bone is tree root and parent_bone_id == 0, this is the first tree (offset = 0)
    first_bone = bones_info[0]
    is_tree_root, parent_bone_id = first_bone[0], first_bone[1]
    first_branch_id = first_bone[7]  # branch_id from tuple

    if is_tree_root and parent_bone_id == 0:
        bone_id_offset = 0  # First tree in grove
    elif is_tree_root:
        bone_id_offset = (
            parent_bone_id  # Subsequent tree, offset by previous tree's bone count
        )
    else:
        # Not a tree root (shouldn't happen for first bone)
        bone_id_offset = 0

    # Calculate branch ID offset
    # Branch IDs in bones_info are global, we need to convert to local (0-based per tree)
    # The first bone's branch_id tells us the offset
    branch_id_offset = first_branch_id

    if verbose:
        print(f"Building skeleton from bones_info ({len(bones_info)} bones)")
        print(f"  Bone ID offset: {bone_id_offset}")
        print(f"  Branch ID offset: {branch_id_offset}")
        print(f"  Tree offset: {tree_offset}")

    # Build joints using bones_info
    bone_id_to_joint_path = {}
    bone_positions = {}

    for bone_idx, bone_info in enumerate(bones_info):
        (
            is_tree_root,
            parent_bone_id,
            start_point,
            end_point,
            radius,
            mass,
            is_branch_root,
            branch_id,
        ) = bone_info

        # Global bone ID = local index + offset
        global_bone_id = bone_id_offset + bone_idx

        # Convert start point to local space (relative to tree origin)
        world_pos = Gf.Vec3d(start_point.x, start_point.y, start_point.z)
        local_pos = world_pos - tree_offset
        bone_positions[global_bone_id] = local_pos

        # Name joints using LOCAL bone index (bone_idx), not global_bone_id
        # This ensures joint names match the jointIndices in vertex binding
        # Tree 0: root, joint_1, joint_2, ...
        # Tree 1: root, joint_1, joint_2, ... (restart numbering)
        if bone_idx == 0:
            joint_name = "root"
        else:
            joint_name = f"joint_{bone_idx}"

        # Build joint path using parent_bone_id
        # Convert parent_bone_id from global to local index for this tree
        if bone_idx == 0:
            # True root bone (first bone in this tree)
            joint_path = joint_name
        else:
            # Parent bone ID is global, convert to local by subtracting offset
            local_parent_id = parent_bone_id - bone_id_offset
            parent_path = bone_id_to_joint_path.get(parent_bone_id)
            if parent_path:
                joint_path = f"{parent_path}/{joint_name}"
            else:
                # Fallback: attach to root if parent not found
                if verbose:
                    print(
                        f"WARNING: Parent bone {parent_bone_id} (local: {local_parent_id}) not found for bone {global_bone_id} (local: {bone_idx}), attaching to root"
                    )
                joint_path = f"root/{joint_name}"

        bone_id_to_joint_path[global_bone_id] = joint_path
        joint_tokens.append(joint_path)

        # Create bind transform (absolute position in local space)
        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(local_pos)
        bind_transforms.append(bind_transform)

        # Create rest transform (position relative to parent)
        if bone_idx == 0:
            # Root bone (first bone in this tree) uses absolute position
            relative_pos = local_pos
        else:
            parent_pos = bone_positions.get(parent_bone_id, Gf.Vec3d(0, 0, 0))
            relative_pos = local_pos - parent_pos

        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(relative_pos)
        rest_transforms.append(rest_transform)

    # Set skeleton attributes
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # CRITICAL: Create SkelAnimation for bind pose (required for Unreal skeletal mesh recognition)
    # Even without animation, Unreal needs this to recognize as skeletal mesh
    anim_path = Sdf.Path("/tree/Animation")
    anim = UsdSkel.Animation.Define(stage, anim_path)

    # Set animation joints (same as skeleton)
    anim.CreateJointsAttr(joint_tokens)

    # Set bind pose transforms (identity for each joint)
    # USD requires these arrays to match the number of joints
    num_joints = len(joint_tokens)
    identity_translations = Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)] * num_joints)
    identity_rotations = Vt.QuatfArray(
        [Gf.Quatf(1, 0, 0, 0)] * num_joints
    )  # w, x, y, z
    identity_scales = Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)] * num_joints)

    anim.CreateTranslationsAttr(identity_translations)
    anim.CreateRotationsAttr(identity_rotations)
    anim.CreateScalesAttr(identity_scales)

    # Bind animation to skeleton via SkelRoot's animationSource relationship
    skel_binding_api = UsdSkel.BindingAPI.Apply(tree_prim)
    skel_binding_api.CreateAnimationSourceRel().SetTargets([anim_path])

    # CRITICAL: Apply SkelBindingAPI to mesh and add skinning data
    # Unreal Engine requires BOTH SkelRoot and Mesh to have skeleton bindings
    mesh_api_schemas = mesh_prim.GetMetadata("apiSchemas")
    if mesh_api_schemas:
        if "SkelBindingAPI" not in mesh_api_schemas.prependedItems:
            mesh_api_schemas.prependedItems.append("SkelBindingAPI")
            mesh_prim.SetMetadata("apiSchemas", mesh_api_schemas)
    else:
        mesh_api_schemas = Sdf.TokenListOp()
        mesh_api_schemas.prependedItems = ["SkelBindingAPI"]
        mesh_prim.SetMetadata("apiSchemas", mesh_api_schemas)

    # Create skeleton relationship on mesh
    mesh_skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
    mesh_skel_rel.SetTargets([skel_path])

    # Add skinning data (joint indices and weights) to mesh
    mesh_geom = UsdGeom.Mesh(mesh_prim)
    points_attr = mesh_geom.GetPointsAttr()
    if points_attr:
        points = points_attr.Get()
        num_vertices = len(points)

        joint_indices = []
        joint_weights = []

        # CRITICAL: Use direct vertex-to-bone mapping if available
        # Grove provides point_attribute_bone_id after calling tag_bone_id() before build_models()
        if model and hasattr(model, "point_attribute_bone_id"):
            bone_ids = model.point_attribute_bone_id

            if verbose:
                print(
                    f"Using direct vertex-to-bone mapping via point_attribute_bone_id"
                )
                print(f"  Vertices: {len(bone_ids)}, Joints: {len(joint_tokens)}")
                # Debug: show unique bone IDs and their distribution
                unique_ids = set(bone_ids)
                print(f"  Unique bone IDs found: {sorted(unique_ids)}")
                print(f"  Bone ID range: {min(bone_ids)} to {max(bone_ids)}")

            # Convert global bone IDs to local joint indices
            # bone_ids from Grove contain global IDs that span across all trees
            # We need local indices (0, 1, 2...) that match our joint names (root, joint_1, joint_2...)
            joint_indices = [bone_id - bone_id_offset for bone_id in bone_ids]
            joint_weights = [1.0] * len(bone_ids)

            if verbose:
                print(f"  Converted to local indices with offset {bone_id_offset}")
                local_unique_ids = set(joint_indices)
                print(f"  Local joint indices: {sorted(local_unique_ids)}")
                print(
                    f"  Local index range: {min(joint_indices)} to {max(joint_indices)}"
                )

        else:
            # Fallback: simple rigid binding to root joint
            # This should only happen if tag_bone_id() wasn't called before build_models()
            if verbose:
                print(
                    f"WARNING: point_attribute_bone_id not available, using fallback rigid binding"
                )
                print(
                    f"  Make sure to call grove.build_skeletons() and grove.tag_bone_id() BEFORE grove.build_models()"
                )

            for _ in range(num_vertices):
                # Bind each vertex to joint 0 with full weight
                # Using 1 influence per vertex (rigid binding)
                joint_indices.append(0)
                joint_weights.append(1.0)

        # Create primvars for skinning
        primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

        # Joint indices primvar (1 influence per vertex for rigid binding)
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(1)

        # Joint weights primvar (1 influence per vertex for rigid binding)
        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(1)

        # Add branch ID attributes with local indices
        # Convert from global branch IDs to local (0-based per tree)
        if model and hasattr(model, "face_attribute_branch_id"):
            global_branch_ids = model.face_attribute_branch_id
            local_branch_ids = [
                branch_id - branch_id_offset for branch_id in global_branch_ids
            ]

            branch_id_primvar = primvars_api.CreatePrimvar(
                "branchID", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
            )
            branch_id_primvar.Set(local_branch_ids)

            if verbose:
                print(
                    f"  Converted BranchId: {len(local_branch_ids)} faces, offset={branch_id_offset}"
                )
                print(
                    f"    Global range: {min(global_branch_ids)}-{max(global_branch_ids)}"
                )
                print(
                    f"    Local range: {min(local_branch_ids)}-{max(local_branch_ids)}"
                )

        if model and hasattr(model, "face_attribute_branch_id_parent"):
            global_parent_ids = model.face_attribute_branch_id_parent
            local_parent_ids = [
                parent_id - branch_id_offset if parent_id >= 0 else parent_id
                for parent_id in global_parent_ids
            ]

            branch_parent_primvar = primvars_api.CreatePrimvar(
                "branchIDParent", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
            )
            branch_parent_primvar.Set(local_parent_ids)

            if verbose:
                print(f"  Converted BranchIdParent: {len(local_parent_ids)} faces")


def get_quality_preset(preset_name: str) -> Dict[str, Any]:
    """Get predefined quality preset for tree model building.

    Args:
        preset_name: One of 'ultra', 'high', 'medium', 'low', 'performance'

    Returns:
        Dictionary with build quality parameters
    """
    presets = {
        "ultra": {
            "resolution": 32,
            "resolution_reduce": 0.75,
            "texture_repeat": 4,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "build_end_cap": True,
        },
        "high": {
            "resolution": 24,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.001,
            "build_blend": True,
            "build_end_cap": True,
        },
        "medium": {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.005,
            "build_blend": True,
            "build_end_cap": True,
        },
        "low": {
            "resolution": 12,
            "resolution_reduce": 0.85,
            "texture_repeat": 2,
            "build_cutoff_age": 1,
            "build_cutoff_thickness": 0.01,
            "build_blend": True,
            "build_end_cap": False,
        },
        "performance": {
            "resolution": 8,
            "resolution_reduce": 0.9,
            "texture_repeat": 2,
            "build_cutoff_age": 2,
            "build_cutoff_thickness": 0.02,
            "build_blend": False,
            "build_end_cap": False,
        },
    }

    if preset_name not in presets:
        raise ValueError(
            f"Unknown quality preset: {preset_name}. Choose from: {list(presets.keys())}"
        )

    return presets[preset_name]


def get_twig_usd_map_for_species(
    species_name: str,
    config: Optional[Any] = None,
    prefer_nanite_assembly: bool = False,
    prefer_skeletal: bool = False,
) -> Dict[str, Path]:
    """Get mapping of twig types to USD file paths for a species.

    NOTE: Twig references should NEVER use Nanite Assembly USD files.
    Nanite Assembly is only for the top-level tree assembly, not individual twigs.
    Using Nanite Assembly twigs causes Unreal Engine import crashes.

    Args:
        species_name: Name of tree species
        config: GrowPy configuration
        prefer_nanite_assembly: DEPRECATED - always False, kept for compatibility
        prefer_skeletal: If True, prefer skeletal twig variants (_skeletal.usda)

    Returns:
        Dict mapping twig types to USD file paths:
        {'twig_long': Path, 'twig_short': Path, ...}
    """
    if config is None:
        from growpy import get_config

        config = get_config()

    from growpy.config import get_twig_files_by_type

    twig_files_by_type = get_twig_files_by_type(species_name)

    if not twig_files_by_type:
        pass

    twig_usd_map = {}

    # Map Grove attribute names to twig file types
    type_mapping = {
        "twig_long": ["apical", "long", "end", "terminal", "var_a", "var_c"],
        "twig_short": ["lateral", "short", "side", "var_b", "var_d"],
        "twig_upward": ["upward", "up", "var_e"],
        "twig_dead": ["dead", "fall", "winter"],
    }

    for grove_type, keywords in type_mapping.items():
        for twig_type, twig_paths in twig_files_by_type.items():
            if any(kw in twig_type.lower() for kw in keywords):
                if twig_paths:
                    twig_file = twig_paths[0]

                    # CRITICAL: ALWAYS use regular USD files for twigs
                    for ext in [".usda", ".usd"]:
                        usd_file = twig_file.with_suffix(ext)

                        if "_nanite_assembly" in usd_file.name:
                            continue

                        is_skeletal = "_skel" in usd_file.stem
                        if prefer_skeletal and not is_skeletal:
                            skeletal_file = (
                                usd_file.parent
                                / f"{usd_file.stem}_skel{usd_file.suffix}"
                            )
                            if skeletal_file.exists():
                                twig_usd_map[grove_type] = skeletal_file
                                break
                            continue
                        elif not prefer_skeletal and is_skeletal:
                            continue

                        if usd_file.exists():
                            twig_usd_map[grove_type] = usd_file
                            break

                    if grove_type in twig_usd_map:
                        break

    return twig_usd_map


def bundle_twigs_for_species(
    species_name: str,
    output_dir: Path,
    formats: List[str] = ["usda"],
    config: Optional[Any] = None,
) -> Dict[str, List[Path]]:
    """Bundle twig files for a species to output directory.

    Copies relevant twig meshes (USD) to species output folder
    for easier asset management in Unreal Engine.

    Args:
        species_name: Name of tree species
        output_dir: Output directory for this species
        formats: Export formats to copy ('usd', 'usda')
        config: GrowPy configuration

    Returns:
        Dict with 'twig_files' and 'manifest' paths
    """
    if config is None:
        from growpy import get_config

        config = get_config()

    import shutil

    results = {"twig_files": [], "manifest": None}

    try:
        twig_dir = output_dir
        twig_dir.mkdir(parents=True, exist_ok=True)

        from growpy.config import get_twig_files_by_type

        twig_files_by_type = get_twig_files_by_type(species_name)

        if not twig_files_by_type:
            return results

        twig_manifest = {"species": species_name, "twig_files": [], "total_twigs": 0}
        copied_textures = set()

        all_twig_files = set()
        for twig_paths in twig_files_by_type.values():
            all_twig_files.update(twig_paths)

        for source_file in sorted(all_twig_files):
            if not source_file.exists():
                continue

            source_base = source_file.parent / source_file.stem

            for fmt in formats:
                if fmt == "usd":
                    extensions = [".usd", ".usda"]
                elif fmt == "usda":
                    extensions = [".usda", ".usd"]
                else:
                    continue

                for ext in extensions:
                    fmt_source_file = source_base.with_suffix(ext)
                    if fmt_source_file.exists():
                        dest_file = twig_dir / fmt_source_file.name
                        shutil.copy2(fmt_source_file, dest_file)
                        results["twig_files"].append(dest_file)
                        twig_manifest["twig_files"].append(dest_file.name)
                        twig_manifest["total_twigs"] += 1
                        break

                    skeletal_file = (
                        source_base.parent / f"{source_base.stem}_skeletal{ext}"
                    )
                    if skeletal_file.exists():
                        dest_file = twig_dir / skeletal_file.name
                        if not dest_file.exists():
                            shutil.copy2(skeletal_file, dest_file)
                            results["twig_files"].append(dest_file)
                            twig_manifest["twig_files"].append(dest_file.name)
                            twig_manifest["total_twigs"] += 1

        source_texture_dir = None
        if all_twig_files:
            first_twig = next(iter(all_twig_files))
            source_texture_dir = first_twig.parent / "textures"

            if source_texture_dir.exists():
                dest_texture_dir = twig_dir / "textures"
                dest_texture_dir.mkdir(exist_ok=True)

                texture_count = 0
                for texture_file in source_texture_dir.glob("*"):
                    if texture_file.is_file():
                        dest_tex = dest_texture_dir / texture_file.name
                        if not dest_tex.exists():
                            shutil.copy2(texture_file, dest_tex)
                            texture_count += 1
                            copied_textures.add(texture_file.name)

                if texture_count > 0:
                    pass

        if twig_manifest["total_twigs"] > 0:
            pass
        else:
            pass

    except Exception as e:
        pass

    return results
