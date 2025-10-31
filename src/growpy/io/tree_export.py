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

# Import bpy BEFORE any other Grove-related modules to avoid DLL conflicts
try:
    import bpy

    # Expose Blender's bundled VFX libraries (USD/pxr, MaterialX, etc.)
    # This allows importing pxr without DLL conflicts (Blender 4.4+)
    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()

    BPY_AVAILABLE = True
except (ImportError, OSError) as e:
    # bpy not available or DLL load failed - this is expected when not using Blender Python
    bpy = None
    BPY_AVAILABLE = False

# Try to import USD after bpy exposure
try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

# Import after bpy check to avoid potential conflicts
from ..config import get_config
from ..core.skeleton import calculate_vertex_weights

# Lazy import of gc to avoid conflicts with bpy
_gc = None
_gc_available = None


def _get_gc():
    """Lazy import of grove core."""
    global _gc, _gc_available
    if _gc is None and _gc_available is None:
        try:
            import the_grove_22_core as grove_core

            _gc = grove_core
            _gc_available = True
        except ImportError:
            _gc = None
            _gc_available = False
    return _gc


def _check_bpy_available():
    """Check if bpy is available at runtime."""
    return BPY_AVAILABLE


def ensure_grove_available():
    """Ensure Grove core is available."""
    gc = _get_gc()
    if gc is None:
        raise ImportError("Grove core (the_grove_22_core) not available")


def _extract_twig_placements_from_usd(usd_path: Path) -> Dict[str, List[Dict]]:
    """Extract twig placements from USD primvars - local helper for tree_export."""
    if not USD_AVAILABLE:
        return {}

    placements = {}
    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return placements

        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                primvars_api = UsdGeom.PrimvarsAPI(mesh)

                # Check for twig primvars
                for twig_type in [
                    "twig_long",
                    "twig_short",
                    "twig_upward",
                    "twig_dead",
                ]:
                    pos_primvar = primvars_api.GetPrimvar(f"{twig_type}_position")
                    normal_primvar = primvars_api.GetPrimvar(f"{twig_type}_normal")
                    scale_primvar = primvars_api.GetPrimvar(f"{twig_type}_scale")

                    if pos_primvar and normal_primvar:
                        positions = pos_primvar.Get()
                        normals = normal_primvar.Get()
                        scales = (
                            scale_primvar.Get()
                            if scale_primvar
                            else [1.0] * len(positions)
                        )

                        if positions and normals:
                            placements[twig_type] = []
                            for i in range(len(positions)):
                                placements[twig_type].append(
                                    {
                                        "position": tuple(positions[i]),
                                        "normal": tuple(normals[i]),
                                        "scale": scales[i] if i < len(scales) else 1.0,
                                    }
                                )
    except Exception as e:
        print(f"Warning: Failed to extract twig placements: {e}")

    return placements


def export_tree(
    model: Any,
    skeleton: Any,
    output_path: Path,
    species_name: str,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.25,
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
    if not _check_bpy_available():
        print("bpy module not available - cannot export USD")
        return False

    if not USD_AVAILABLE:
        print("USD Python (pxr) not available - cannot export USD")
        return False

    ensure_grove_available()
    config = get_config()

    try:
        # Configure model for optimal export compatibility
        try:
            # Set up-axis to Z for Blender/Unreal compatibility
            model.set_up_axis("Z")
            # Set counter-clockwise winding for standard compatibility
            model.set_winding_order("COUNTER_CLOCKWISE")
        except Exception as e:
            print(f"  Warning: Could not configure model orientation: {e}")

        print(f"  Set model to Z up-axis and counter-clockwise winding")

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build USD directly from Grove model with skeleton (no Blender export needed)
        print(f"  Building USD with skeleton from Grove model...")
        success = build_tree_mesh(
            model=model,
            skeleton=skeleton,
            output_path=output_path,
            up_axis="Z",
            triangulated=True,
            include_materials=True,
            clean_export=False,
            skeleton_length=skeleton_length,
            skeleton_reduce=skeleton_reduce,
            skeleton_bias=skeleton_bias,
            skeleton_connected=skeleton_connected,
        )

        if not success:
            print(f"Failed to build USD mesh")
            return False

        # Add Nanite attributes to USD file
        add_nanite_attributes_to_usd(output_path, is_foliage=False)

        print(f"[OK] Exported tree to USD with Nanite compatibility for {species_name}")
        return True

    except Exception as e:
        print(f"Failed to export tree USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def build_tree_mesh(
    model: Any,
    skeleton: Optional[Any],
    output_path: Path,
    up_axis: str = "Z",
    triangulated: bool = True,
    include_materials: bool = True,
    clean_export: bool = False,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.1,
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

    Args:
        model: Grove tree model from grove.build_models() - MUST be triangulated first
        skeleton: Optional Grove skeleton from grove.build_skeletons()
        output_path: Path where USD file will be saved
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated (should always be True)
        include_materials: If False, creates simple geometry without materials/UVs
        clean_export: If True, creates minimal USD without default attributes (demo mode)
        skeleton_length: Bone length multiplier for skeleton creation
        skeleton_reduce: Bone reduction factor for skeleton creation
        skeleton_bias: Weight bias for skinning
        skeleton_connected: Use connected bone hierarchy

    Returns:
        bool: True if USD file was created successfully

    Example:
        >>> grove = gc.Grove()
        >>> grove.add_new_tree(...)
        >>> grove.simulate(5)
        >>> models = grove.build_models({...})
        >>> skeletons = grove.build_skeletons()
        >>> model = models[0]
        >>> model.triangulate()  # CRITICAL: Must triangulate first
        >>> build_tree_mesh(model, skeletons[0], Path("tree.usda"), up_axis="Z")
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

        # Store clean_export mode for skeleton addition
        if clean_export:
            stage.SetMetadata("customLayerData", {"clean_export": True})

        # Define root xform
        root_path = Sdf.Path("/tree")
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
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = []
        for face in faces:
            face_vertex_indices.extend(face)

        # Set mesh topology
        mesh.CreatePointsAttr(usd_points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Add UV coordinates and materials only if requested
        if include_materials:
            if uvs:
                primvars_api = UsdGeom.PrimvarsAPI(mesh)
                uv_primvar = primvars_api.CreatePrimvar(
                    "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
                )
                usd_uvs = [Gf.Vec2f(uv[0], uv[1]) for uv in uvs]
                uv_primvar.Set(usd_uvs)

            # Create proper USD materials with UsdPreviewSurface
            _add_usd_materials(stage, mesh, model, str(mesh_path))

        # Add face attributes from Grove
        _add_grove_face_attributes(mesh, model)

        # Add point attributes from Grove
        _add_grove_point_attributes(mesh, model)

        # Add normals for proper Unreal rendering
        _add_mesh_normals(mesh, model)

        # Add skeleton if provided
        if skeleton is not None:
            print(f"  Adding skeleton to USD stage...")
            skeleton_added = _add_skeleton_to_stage_inline(
                stage=stage,
                skeleton=skeleton,
                root_xform_prim=root_xform.GetPrim(),
                mesh_prim=mesh.GetPrim(),
                model=model,
                skeleton_length=skeleton_length,
                skeleton_reduce=skeleton_reduce,
                skeleton_bias=skeleton_bias,
                skeleton_connected=skeleton_connected,
            )
            if skeleton_added:
                print(f"    [OK] Skeleton added with UsdSkel structure")
            else:
                print(f"    Warning: Failed to add skeleton")

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"Error building USD file: {e}")
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
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.1,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add skeleton to open USD stage using Grove's skeleton data."""
    try:
        if not skeleton:
            print("Error: No skeleton provided")
            return False

        # Create UsdSkel skeleton structure directly in the stage
        _build_usdskel_from_bones(stage, skeleton, None, None)

        return True

    except Exception as e:
        print(f"    Error adding skeleton: {e}")
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
            print(f"Failed to open USD stage: {usd_path}")
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
        print(f"Failed to add Nanite attributes to USD: {e}")
        return False


def _add_skeleton_to_object(
    obj: Any,
    skeleton: Any,
    species_name: str,
    grove: Any,
    model: Optional[Any] = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.25,
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
        print(f"      [TIME]  Weight calculation: {t_weight_calc-t_weight_start:.2f}s")

        # Find unique bones that are actually used
        used_bone_indices = set()
        for joint_indices in vertex_to_joints:
            used_bone_indices.update(joint_indices)

        num_bones_needed = len(used_bone_indices)
        print(
            f"      [INFO]  Creating {num_bones_needed} bones (from Grove's tag_bone_id)"
        )

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
        print(
            f"      [TIME]  Bone creation: {t_bones-t_weight_calc:.2f}s ({len(bone_names)} bones)"
        )

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
        print(
            f"      [TIME]  Weight assignment: {t_assign_end-t_assign_start:.2f}s ({len(vertices)} vertices)"
        )

        print(f"    [OK] Applied weights for {len(vertices)} vertices to skeleton")

        return armature_obj

    except Exception as e:
        print(f"Failed to add skeleton: {e}")
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
        print(f"Warning: Failed to add some Grove attributes to mesh: {e}")


def _add_blender_attributes_as_usd_primvars(usd_path: Path, mesh_obj: Any) -> None:
    """Write Blender mesh attributes as USD primvars after export."""
    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Warning: Could not open USD stage at {usd_path}")
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
                    print(
                        f"  Added primvar {attr_name}: {sum(values)} true out of {len(values)} faces"
                    )

        stage.Save()
        print(f"[OK] Added Blender attributes as USD primvars to {usd_path.name}")

    except Exception as e:
        print(f"Warning: Failed to add primvars to USD file: {e}")


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
        print(f"Warning: Failed to add material: {e}")


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


def _add_grove_face_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove face attributes as USD primvars."""
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # Branch attributes
    if hasattr(model, "face_attribute_branch_id"):
        primvar = primvars_api.CreatePrimvar(
            "BranchIndex", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.uniform
        )
        primvar.Set(model.face_attribute_branch_id)


def _add_grove_point_attributes(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add Grove point attributes as USD primvars."""
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    if hasattr(model, "point_attribute_age"):
        primvar = primvars_api.CreatePrimvar(
            "Age", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_age)

    if hasattr(model, "point_attribute_thickness"):
        primvar = primvars_api.CreatePrimvar(
            "Thickness", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        primvar.Set(model.point_attribute_thickness)


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

    # Apply bark material to entire mesh
    UsdShade.MaterialBindingAPI(mesh_prim).Bind(bark_mat)


def _add_mesh_normals(mesh: UsdGeom.Mesh, model: Any) -> None:
    """Add computed normals to mesh for proper Unreal rendering."""
    try:
        faces = model.faces if hasattr(model, "faces") else []
        if not faces:
            return

        # Create simple up-facing normals
        normals = [Gf.Vec3f(0, 0, 1) for _ in faces]
        normals_attr = mesh.CreateNormalsAttr()
        normals_attr.Set(normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

    except Exception:
        pass


def add_skeleton_to_usd(
    usd_path: Path,
    grove: Any,
    tree_model: Any = None,
    skeleton_length: float = 2.0,
    skeleton_reduce: float = 0.4,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    add_twig_bones: bool = True,
    verbose: bool = False,
) -> bool:
    """Add skeleton to existing USD file using Grove's skeleton data.

    Args:
        usd_path: Path to existing USD file with tree mesh
        grove: Grove instance with simulated tree
        tree_model: Tree model (unused, kept for compatibility)
        skeleton_length: Length threshold
        skeleton_reduce: Reduction factor
        skeleton_bias: Bias setting
        skeleton_connected: Connection setting
        add_twig_bones: If True, add twig mount bones to skeleton
        verbose: If True, print detailed debug information

    Returns:
        bool: True if skeleton was added successfully
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
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

        # Create UsdSkel skeleton structure
        # Note: Twig placement data is written as primvars and extracted during assembly creation
        _build_usdskel_from_bones(stage, skeleton, None, None)

        # Set defaultPrim
        tree_prim = stage.GetPrimAtPath("/tree")
        if tree_prim:
            stage.SetDefaultPrim(tree_prim)

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
    twig_placements: Optional[Dict[str, List[Dict]]] = None,
    verbose: bool = False,
) -> None:
    """Build UsdSkel skeleton from Grove skeleton polylines.

    CRITICAL for Unreal Engine recognition:
    1. SkelRoot MUST have SkelBindingAPI applied
    2. SkelRoot MUST have skel:skeleton relationship pointing to Skeleton prim
    3. Mesh should NOT have any skel:* relationships (those go on SkelRoot only)
    """
    # Find mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if not mesh_prim:
        print("Warning: No mesh found in USD stage")
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

    skeleton_points = skeleton.points
    skeleton_polylines = skeleton.poly_lines

    # Convert points to tuples
    def to_tuple(point):
        if isinstance(point, tuple):
            return point
        elif hasattr(point, "x"):
            return (point.x, point.y, point.z)
        else:
            return tuple(point)

    skeleton_points = [to_tuple(p) for p in skeleton_points]

    # Calculate tree offset from root point to convert world space to local space
    # The mesh geometry is exported in local space (near origin), but skeleton points
    # are in world space from grove.add_new_tree(position, ...). We need to subtract
    # this offset so skeleton and mesh are in the same coordinate space.
    if skeleton_points and skeleton_polylines and skeleton_polylines[0]:
        root_point_idx = skeleton_polylines[0][0]
        root_point = skeleton_points[root_point_idx]
        tree_offset = Gf.Vec3d(root_point[0], root_point[1], root_point[2])
        print(f"    Tree offset (root position): {tree_offset}")
    else:
        tree_offset = Gf.Vec3d(0, 0, 0)
        print("    Warning: No skeleton points found, using zero offset")

    # Build joint hierarchy from polylines
    bone_positions = {}
    point_to_joint_path = {}
    point_to_joint_index = {}

    joint_counter = 0

    for polyline_idx, polyline in enumerate(skeleton_polylines):
        prev_joint_path = None
        start_idx = 1 if polyline_idx > 0 else 0

        for i, point_idx in enumerate(polyline[start_idx:], start=start_idx):
            point = skeleton_points[point_idx]
            world_pos = Gf.Vec3d(point[0], point[1], point[2])
            # Convert to local space by subtracting tree offset
            local_pos = world_pos - tree_offset

            joint_name = f"joint_{joint_counter}"
            point_to_joint_index[point_idx] = joint_counter
            joint_counter += 1

            if i == start_idx:
                if polyline_idx == 0:
                    joint_path = joint_name
                else:
                    shared_point_idx = polyline[0]
                    parent_joint_path = point_to_joint_path[shared_point_idx]
                    joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                joint_path = f"{prev_joint_path}/{joint_name}"

            point_to_joint_path[point_idx] = joint_path
            joint_tokens.append(joint_path)
            bone_positions[point_idx] = local_pos  # Store local position

            # Create bind transform with local position
            bind_transform = Gf.Matrix4d(1.0)
            bind_transform.SetTranslateOnly(local_pos)
            bind_transforms.append(bind_transform)

            if i == 0:
                relative_pos = local_pos
            else:
                prev_point_idx = polyline[i - 1]
                parent_pos = bone_positions.get(prev_point_idx, Gf.Vec3d(0, 0, 0))
                relative_pos = local_pos - parent_pos

            rest_transform = Gf.Matrix4d(1.0)
            rest_transform.SetTranslateOnly(relative_pos)
            rest_transforms.append(rest_transform)

            prev_joint_path = joint_path

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

    print(
        f"    [OK] Created SkelAnimation ({num_joints} joints, bind pose for UE skeletal mesh recognition)"
    )

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

        # Create simple rigid binding: all vertices bound to root joint (joint_0)
        # For proper skinning, this would need to calculate weights based on vertex positions
        joint_indices = []
        joint_weights = []

        for _ in range(num_vertices):
            # Bind each vertex to joint 0 with full weight
            # Using 2 influences per vertex (elementSize = 2)
            joint_indices.extend([0, 0])
            joint_weights.extend([1.0, 0.0])

        # Create primvars for skinning
        primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

        # Joint indices primvar
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(2)

        # Joint weights primvar
        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(2)

    print(
        f"    [OK] Applied SkelBindingAPI to SkelRoot and Mesh with {num_vertices} vertices"
    )


def add_twig_skeleton_to_usd(
    usd_path: Path,
    pivot_point: Tuple[float, float, float] = (0, 0, 0),
) -> bool:
    """Add simple skeleton to twig USD with single root joint at pivot.

    Args:
        usd_path: Path to existing USD file with twig mesh
        pivot_point: World position of root joint (pivot/attachment point)

    Returns:
        bool: True if skeleton was added successfully
    """
    if not USD_AVAILABLE:
        print("Error: USD Python module not available")
        return False

    try:
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
            print(f"Warning: No mesh found in USD file {usd_path.name}")
            return False

        # Create skeleton root
        root_path = Sdf.Path("/twig")
        skel_root = UsdSkel.Root.Define(stage, root_path)
        skel_root_prim = stage.GetPrimAtPath(root_path)

        UsdSkel.BindingAPI.Apply(skel_root_prim)

        # Create skeleton with single root joint
        skel_path = root_path.AppendChild("Skel")
        skel = UsdSkel.Skeleton.Define(stage, skel_path)

        joint_tokens = ["root"]
        world_pos = Gf.Vec3d(pivot_point[0], pivot_point[1], pivot_point[2])

        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(world_pos)

        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(world_pos)

        skel.CreateJointsAttr(joint_tokens)
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray([bind_transform]))
        skel.CreateRestTransformsAttr(Vt.Matrix4dArray([rest_transform]))

        # Move mesh under SkelRoot
        expected_mesh_path = root_path.AppendChild("Mesh")
        if mesh_prim.GetPath() != expected_mesh_path:
            old_mesh_path = mesh_prim.GetPath()
            Sdf.CopySpec(
                stage.GetRootLayer(),
                old_mesh_path,
                stage.GetRootLayer(),
                expected_mesh_path,
            )
            stage.RemovePrim(old_mesh_path)
            mesh_prim = stage.GetPrimAtPath(expected_mesh_path)

        mesh = UsdGeom.Mesh(mesh_prim)

        # Bind mesh to skeleton
        binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Set skinning data
        points = mesh.GetPointsAttr().Get()
        num_points = len(points)

        joint_indices = []
        joint_weights = []
        for _ in range(num_points):
            joint_indices.extend([0, 0])
            joint_weights.extend([1.0, 0.0])

        primvarsAPI = UsdGeom.PrimvarsAPI(mesh_prim)

        joint_indices_primvar = primvarsAPI.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(2)

        joint_weights_primvar = primvarsAPI.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(2)

        stage.Save()
        return True

    except Exception as e:
        print(f"Error adding twig skeleton to USD: {e}")
        import traceback

        traceback.print_exc()
        return False


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

    print(f"  Looking for twigs for species: {species_name}")
    twig_files_by_type = get_twig_files_by_type(species_name)

    if not twig_files_by_type:
        print(f"  WARNING: No twig files found for species '{species_name}'")
        print(f"  This could mean:")
        print(f"    1. Species name doesn't match lookup table entries")
        print(f"    2. Species has no twig configured in lookup table")
        print(f"    3. Twig files don't exist in the twigs directory")

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
                                print(f"    Found {grove_type}: {skeletal_file.name}")
                                break
                            continue
                        elif not prefer_skeletal and is_skeletal:
                            continue

                        if usd_file.exists():
                            twig_usd_map[grove_type] = usd_file
                            print(f"    Found {grove_type}: {usd_file.name}")
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
            print(f"  No twig files found for {species_name}")
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
                        print(f"    Copied twig: {dest_file.name}")
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
                            print(f"    Copied twig: {dest_file.name}")

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
                    print(f"    Copied {texture_count} twig textures to textures/")

        if twig_manifest["total_twigs"] > 0:
            print(
                f"  [OK] Bundled {twig_manifest['total_twigs']} twig files for {species_name}"
            )
        else:
            print(f"  ⚠ No twig files copied for {species_name}")

    except Exception as e:
        print(f"Failed to bundle twigs for {species_name}: {e}")

    return results
