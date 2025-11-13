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
- build_tree_mesh(): Build USD mesh from Grove model (formerly build_tree_usd)
- add_skeleton_to_usd(): Add skeleton to existing USD file
- add_twig_skeleton_to_usd(): Add simple skeleton for twig meshes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
import the_grove_22_core as gc

from ..utils.pxr_init import ensure_pxr_with_unreal_schema

ensure_pxr_with_unreal_schema()

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

from ..config import get_config
from ..core.skeleton import calculate_vertex_weights


def build_static_tree_mesh(
    model: Any,
    output_path: Path,
    species_name: Optional[str] = None,
    up_axis: str = "Z",
    triangulated: bool = True,
) -> bool:
    """Build static USD mesh from Grove model (no skeleton, with materials).

    This function creates a static mesh USD file for Nanite static assemblies.
    Unlike skeletal meshes, this includes materials and textures but no skeleton.

    CRITICAL: The model must be triangulated BEFORE calling this function:
        model.triangulate()

    Args:
        model: Grove tree model from grove.build_models() - MUST be triangulated first
        output_path: Path where USD file will be saved
        species_name: Species name for texture lookup
        up_axis: Coordinate system up axis ("Y" or "Z")
        triangulated: Whether the model has been triangulated (should always be True)

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

        # Define root xform
        root_path = Sdf.Path("/tree")
        root_xform = UsdGeom.Xform.Define(stage, root_path)

        # Add tree location metadata if available
        if hasattr(model, "location") and model.location:
            loc = model.location
            root_xform.GetPrim().SetCustomDataByKey(
                "treeLocation", Gf.Vec3f(loc.x, loc.y, loc.z)
            )

        # Define mesh
        mesh_path = root_path.AppendChild("TreeMesh")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Extract geometry data from Grove model
        points = model.points
        faces = model.faces
        uvs = model.uvs

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

        # Add normals for proper rendering
        _add_mesh_normals(mesh, model, clean_export=False)

        # Add materials with textures
        _add_static_materials(
            stage, mesh.GetPrim(), str(root_path), model, species_name
        )

        # Save stage
        stage.Save()
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
    clean_export: bool = True,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
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

        # Skip treeLocation metadata for clean export
        # Tree positioning is handled at the assembly level
        if not clean_export and hasattr(model, "location") and model.location:
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

        # Skip model attributes for clean skeletal export
        # These attributes (Age, Pitch, Vigor, etc.) are not needed for Nanite assembly
        # and make debugging harder. They can be re-enabled if needed for analysis.
        if not clean_export:
            # Add all model attributes from Grove (face and point attributes)
            _add_model_attributes(mesh, model)

        # Skip UV island metadata for clean export
        # UV data is included in the mesh but metadata is not needed for Nanite assembly
        if not clean_export and hasattr(model, "uv_islands") and model.uv_islands:
            # Store count and structure info as metadata
            mesh.GetPrim().SetCustomDataByKey("uvIslandCount", len(model.uv_islands))
            # Note: Full island data available but not stored to keep file size reasonable
            # Can be accessed via model.uv_islands or model.get_uv_islands_flat() if needed

        # Add normals for proper Unreal rendering (skip for clean export)
        _add_mesh_normals(mesh, model, clean_export=clean_export)

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
                clean_export=clean_export,
                junction_blend_distance=junction_blend_distance,
                blend_mode=blend_mode,
            )
            if skeleton_added:
                pass
            else:
                pass

        # Add materials to mesh (required for Nanite assembly recognition)
        # Materials are created as siblings to TreeMesh inside /tree root
        _add_skeletal_materials(stage, mesh.GetPrim(), str(root_path))

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
    clean_export: bool = True,
    junction_blend_distance: float = 0.1,
    blend_mode: str = "linear",
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
        # Pass bones_info for direct vertex-to-bone mapping with junction blending
        _build_usdskel_from_bones(
            stage,
            skeleton,
            model,
            bones_info,
            clean_export=clean_export,
            verbose=False,  # Set to True for debugging
            junction_blend_distance=junction_blend_distance,
            blend_mode=blend_mode,
        )

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


def _add_skeletal_materials(
    stage: Usd.Stage, mesh_prim: Usd.Prim, root_path: str
) -> None:
    """Add materials to skeletal tree mesh for Nanite assembly recognition.

    Creates Materials scope as sibling to TreeMesh inside /tree root,
    matching the structure used in twig files.

    Args:
        stage: USD stage
        mesh_prim: TreeMesh prim
        root_path: Path to root xform (e.g., "/tree")
    """
    try:
        # Bark material color (brown)
        BARK_BROWN = Gf.Vec3f(0.4, 0.3, 0.2)

        # Create Materials scope as sibling to TreeMesh
        materials_path = root_path + "/Materials"
        UsdGeom.Scope.Define(stage, materials_path)

        # Create BarkMaterial
        bark_mat = UsdShade.Material.Define(stage, f"{materials_path}/BarkMaterial")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/BarkMaterial/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(BARK_BROWN)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
        bark_mat.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )

        # Apply MaterialBindingAPI to mesh and bind material
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding_api.Bind(bark_mat)

    except Exception as e:
        # Silently fail - material addition is optional
        pass


def _add_static_materials(
    stage: Usd.Stage,
    mesh_prim: Usd.Prim,
    root_path: str,
    model: Any,
    species_name: Optional[str] = None,
) -> None:
    """Add materials with textures to static tree mesh.

    Creates Materials scope with bark material and texture support for static assemblies.
    Unlike skeletal materials, this includes texture references for more detailed rendering.

    Args:
        stage: USD stage
        mesh_prim: TreeMesh prim
        root_path: Path to root xform (e.g., "/tree")
        model: Grove model (for accessing texture/material data if needed)
        species_name: Species name for texture lookup
    """
    try:
        from ..config import get_config

        config = get_config()

        # Bark material color (brown) - fallback if no texture
        BARK_BROWN = Gf.Vec3f(0.4, 0.3, 0.2)

        # Create Materials scope as sibling to TreeMesh
        materials_path = root_path + "/Materials"
        UsdGeom.Scope.Define(stage, materials_path)

        # Create BarkMaterial with texture support
        bark_mat = UsdShade.Material.Define(stage, f"{materials_path}/BarkMaterial")
        shader = UsdShade.Shader.Define(
            stage, f"{materials_path}/BarkMaterial/PreviewSurface"
        )
        shader.CreateIdAttr("UsdPreviewSurface")

        # Try to find and add bark texture if available using asset lookup table
        texture_found = False
        texture_file = None
        if species_name:
            from growpy.config.paths import get_bark_texture_path

            texture_file = get_bark_texture_path(species_name)

            if texture_file and texture_file.exists():
                texture_found = True
                # Create texture reader
                tex_reader = UsdShade.Shader.Define(
                    stage, f"{materials_path}/BarkMaterial/DiffuseTexture"
                )
                tex_reader.CreateIdAttr("UsdUVTexture")
                # Use relative path to textures/ subdirectory
                tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    f"./textures/{texture_file.name}"
                )
                tex_reader.CreateInput(
                    "sourceColorSpace", Sdf.ValueTypeNames.Token
                ).Set("sRGB")
                tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect texture to shader
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(tex_reader.ConnectableAPI(), "rgb")

        # Fallback to solid color if no texture found
        if not texture_found:
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                BARK_BROWN
            )

        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        bark_mat.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )

        # Apply MaterialBindingAPI to mesh and bind material
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding_api.Bind(bark_mat)

        # Copy texture file to output directory if found
        if texture_found and texture_file:
            import shutil
            from pathlib import Path

            # Get output directory from stage
            output_dir = Path(stage.GetRootLayer().realPath).parent

            # Create textures subdirectory (matches twig texture structure)
            textures_dir = output_dir / "textures"
            textures_dir.mkdir(exist_ok=True)

            # Copy texture file to textures/ subdirectory
            dest_texture = textures_dir / texture_file.name
            if not dest_texture.exists():
                shutil.copy2(texture_file, dest_texture)

    except Exception as e:
        # Silently fail - material addition is optional
        pass


def _add_mesh_normals(
    mesh: UsdGeom.Mesh, model: Any, clean_export: bool = True
) -> None:
    """Add normals to mesh for proper Unreal rendering.

    Prefers using actual normals from model.shape if available,
    falls back to simple up-facing normals if not.

    Args:
        clean_export: If True, skip normals entirely (Nanite assemblies don't need them)
    """
    # Skip normals for clean export (reference files don't have them)
    if clean_export:
        return
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
        # Silently fail - USD material addition is optional
        pass


def _build_usdskel_from_bones(
    stage: Usd.Stage,
    skeleton: Any,
    model: Optional[Any] = None,
    bones_info: Optional[List[Tuple]] = None,
    twig_placements: Optional[Dict[str, List[Dict]]] = None,
    verbose: bool = False,
    clean_export: bool = True,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
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
    branch_id_to_joint_path = (
        {}
    )  # Maps local branch_id to joint path ending with branch_X

    # Create lookup dict for bones_info by global bone ID
    bones_info_dict = {}
    for bone_idx, bone_info in enumerate(bones_info):
        global_bone_id = bone_id_offset + bone_idx
        bones_info_dict[global_bone_id] = bone_info

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

        # Convert start point to tree-local space (world position - tree origin)
        world_pos = Gf.Vec3d(start_point.x, start_point.y, start_point.z)
        local_pos = world_pos - tree_offset
        bone_positions[global_bone_id] = local_pos

        # NATURAL HIERARCHY - Build joint paths following parent-child relationships
        # This preserves the natural bone structure from Grove
        local_branch_id = branch_id - branch_id_offset

        if bone_idx == 0:
            # First bone is always tree_root
            joint_name = "tree_root"
            joint_path = joint_name
        elif is_branch_root:
            # Branch root: tree_root/branch_X
            joint_name = f"branch_{local_branch_id}"
            # Get parent's joint path and append this joint
            if parent_bone_id in bone_id_to_joint_path:
                parent_joint_path = bone_id_to_joint_path[parent_bone_id]
                joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                joint_path = f"tree_root/{joint_name}"
        else:
            # Regular joint: follow parent hierarchy
            joint_name = f"joint_{bone_idx}"
            # Get parent's joint path and append this joint
            if parent_bone_id in bone_id_to_joint_path:
                parent_joint_path = bone_id_to_joint_path[parent_bone_id]
                joint_path = f"{parent_joint_path}/{joint_name}"
            else:
                joint_path = f"tree_root/{joint_name}"

        # Store the bone's joint path
        bone_joint_path = joint_path
        bone_id_to_joint_path[global_bone_id] = bone_joint_path
        joint_tokens.append(bone_joint_path)

        # Create restTransform (LOCAL space - position relative to parent bone)
        # USD requirement: restTransforms are in local space
        if bone_idx == 0:
            # Root bone: identity transform (no translation from origin)
            relative_pos = Gf.Vec3d(0, 0, 0)
        else:
            # Calculate offset from parent bone position
            parent_pos = bone_positions.get(parent_bone_id, Gf.Vec3d(0, 0, 0))
            relative_pos = local_pos - parent_pos

        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(relative_pos)
        rest_transforms.append(rest_transform)

        # Create bindTransform (WORLD space - absolute position from tree origin)
        # USD requirement: bindTransforms are in world space (tree-local coordinates)
        # This is used by skinning to transform vertices from bind pose to animated pose
        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(local_pos)
        bind_transforms.append(bind_transform)

        # If this is a branch root, map branch_id to joint path for bindJoints lookup
        # The joint itself is already named "branch_X" so no separate joint needed
        if is_branch_root:
            branch_id_to_joint_path[local_branch_id] = bone_joint_path

    # Set skeleton attributes
    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # Store branch_id mapping for later use in bindJoints
    # This allows assembly export to use: branch_id_to_joint_path[placement.branch_id]
    if hasattr(tree_prim, "branch_id_to_joint_path"):
        tree_prim.branch_id_to_joint_path = branch_id_to_joint_path

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
                    f"Using hierarchical junction blending with blend_distance={junction_blend_distance}"
                )
                print(f"  Vertices: {len(bone_ids)}, Joints: {len(joint_tokens)}")
                # Debug: show unique bone IDs and their distribution
                unique_ids = set(bone_ids)
                print(f"  Unique bone IDs found: {sorted(unique_ids)}")
                print(f"  Bone ID range: {min(bone_ids)} to {max(bone_ids)}")

            # Build bone_to_joint_map for local (tree-specific) bone indices
            bone_to_joint_map = {}
            for bone_idx in range(len(bones_info)):
                global_bone_id = bone_id_offset + bone_idx
                local_bone_id = bone_idx
                bone_to_joint_map[global_bone_id] = local_bone_id

            # Use calculate_vertex_weights with reduced weights at junctions
            from ..core.skeleton import calculate_vertex_weights

            joint_indices_flat, joint_weights_flat = calculate_vertex_weights(
                model=model,
                bone_to_joint_map=bone_to_joint_map,
                bones_info=bones_info,
                element_size=2,
                junction_blend_distance=junction_blend_distance,
                blend_mode=blend_mode,
            )

            # Unpack flat arrays (2 values per vertex from calculate_vertex_weights with dual-bone weighting)
            joint_indices = joint_indices_flat
            joint_weights = joint_weights_flat

            if verbose:
                print(f"  Calculated weights with {len(joint_indices)} vertices")
                # Count vertices with reduced weights at junctions
                reduced_weight_count = sum(1 for w in joint_weights if w < 1.0)
                print(
                    f"  Vertices with reduced weights: {reduced_weight_count} ({reduced_weight_count * 100 / len(joint_weights):.1f}%)"
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
                joint_indices.append(0)
                joint_weights.append(1.0)

        # Create primvars for skinning
        primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

        # CRITICAL: Use elementSize=2 for dual-bone binding with parent/child weight blending
        # joint_indices and joint_weights are in dual-bone format from calculate_vertex_weights
        # Each vertex has two bone indices and two weight values that sum to 1.0

        # Joint indices primvar (2 influences per vertex)
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices", Sdf.ValueTypeNames.IntArray, UsdGeom.Tokens.vertex
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(2)

        # Joint weights primvar (2 influences per vertex for dual-bone weighting)
        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(2)

        # Add branch ID attributes with local indices (only if not clean export)
        # Convert from global branch IDs to local (0-based per tree)
        # These are debug/visualization attributes not required for Nanite
        if not clean_export:
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
                    "branchIDParent",
                    Sdf.ValueTypeNames.IntArray,
                    UsdGeom.Tokens.uniform,
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
    prefer_static: bool = False,
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
        prefer_static: If True, prefer static twig variants (_static.usda)

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

                        # Check for skeletal or static variants
                        is_skeletal = "_skeletal" in usd_file.stem
                        is_static = "_static" in usd_file.stem

                        if prefer_static:
                            # Look for static variant
                            if not is_static:
                                static_file = (
                                    usd_file.parent
                                    / f"{usd_file.stem}_static{usd_file.suffix}"
                                )
                                if static_file.exists():
                                    twig_usd_map[grove_type] = static_file
                                    break
                                continue
                            if is_static and usd_file.exists():
                                twig_usd_map[grove_type] = usd_file
                                break
                        elif prefer_skeletal:
                            # Look for skeletal variant
                            if not is_skeletal:
                                skeletal_file = (
                                    usd_file.parent
                                    / f"{usd_file.stem}_skeletal{usd_file.suffix}"
                                )
                                if skeletal_file.exists():
                                    twig_usd_map[grove_type] = skeletal_file
                                    break
                                continue
                            if is_skeletal and usd_file.exists():
                                twig_usd_map[grove_type] = usd_file
                                break
                        else:
                            # No preference - skip variants
                            if is_skeletal or is_static:
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

        # CRITICAL: Texture bundling disabled for Nanite compatibility
        # Nanite assemblies with skeletal meshes don't use textures from USD
        # All materials and textures should be configured in Unreal Engine
        # source_texture_dir = None
        # if all_twig_files:
        #     first_twig = next(iter(all_twig_files))
        #     source_texture_dir = first_twig.parent / "textures"
        #
        #     if source_texture_dir.exists():
        #         dest_texture_dir = twig_dir / "textures"
        #         dest_texture_dir.mkdir(exist_ok=True)
        #
        #         texture_count = 0
        #         for texture_file in source_texture_dir.glob("*"):
        #             if texture_file.is_file():
        #                 dest_tex = dest_texture_dir / texture_file.name
        #                 if not dest_tex.exists():
        #                     shutil.copy2(texture_file, dest_tex)
        #                     texture_count += 1
        #                     copied_textures.add(texture_file.name)

    except Exception:
        # Silently fail - twig bundling is optional
        pass

    return results
