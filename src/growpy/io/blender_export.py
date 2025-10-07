"""Export for Grove tree models optimized for Unreal Engine 5 Nanite."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import bpy BEFORE any other Grove-related modules to avoid DLL conflicts
try:
    import bpy

    BPY_AVAILABLE = True
except (ImportError, OSError) as e:
    # bpy not available or DLL load failed - this is expected when not using Blender Python
    bpy = None
    BPY_AVAILABLE = False

# Import after bpy check to avoid potential conflicts
from ..config import get_config

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


def add_nanite_attributes_to_usd(usd_path: Path, is_foliage: bool = False) -> bool:
    """Add Nanite-specific USD attributes to exported USD file.

    Args:
        usd_path: Path to USD file
        is_foliage: Whether this is foliage (twigs/leaves) requiring Preserve Area

    Returns:
        bool: Success status
    """
    try:
        from pxr import Sdf, Usd, UsdGeom

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

                # For foliage, enable Preserve Area to prevent thinning at distance
                if is_foliage:
                    prim.CreateAttribute(
                        "unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool
                    ).Set(True)

        # Save changes
        stage.GetRootLayer().Save()
        return True

    except ImportError:
        print("USD Python (pxr) not available. Nanite attributes not added.")
        print("Install with: pip install usd-core")
        return False
    except Exception as e:
        print(f"Failed to add Nanite attributes to USD: {e}")
        return False


def validate_mesh_for_nanite(mesh: Any) -> Dict[str, Any]:
    """Validate mesh for Unreal Engine Nanite compatibility.

    Checks mesh topology, UV continuity, and other Nanite requirements.

    Args:
        mesh: Blender mesh object

    Returns:
        Dict with validation results:
            - compatible: bool (overall compatibility)
            - warnings: List[str] (potential issues)
            - stats: Dict (mesh statistics)
    """
    validation = {"compatible": True, "warnings": [], "stats": {}}

    try:
        # Triangle count check (<1M recommended for optimal performance)
        triangle_count = len(mesh.polygons)
        validation["stats"]["triangle_count"] = triangle_count

        if triangle_count > 1000000:
            validation["warnings"].append(
                f"High triangle count ({triangle_count:,}). "
                "Consider <1M triangles for optimal Nanite performance."
            )

        # Check for quads vs triangles
        quad_count = sum(1 for poly in mesh.polygons if len(poly.vertices) == 4)
        tri_count = triangle_count - quad_count
        validation["stats"]["quad_count"] = quad_count
        validation["stats"]["tri_count"] = tri_count

        # UV continuity check - count UV seams
        if mesh.uv_layers:
            uv_seam_count = sum(1 for edge in mesh.edges if edge.use_seam)
            validation["stats"]["uv_seams"] = uv_seam_count
            validation["stats"]["uv_layers"] = len(mesh.uv_layers)

            if uv_seam_count > triangle_count * 0.3:
                validation["warnings"].append(
                    f"High UV seam count ({uv_seam_count}). "
                    "UV discontinuities increase vertex count in Nanite."
                )
        else:
            validation["warnings"].append(
                "No UV maps found. UVs recommended for texturing."
            )

        # Topology check - look for degenerate triangles (very thin/long)
        import mathutils

        thin_triangle_count = 0
        for poly in mesh.polygons:
            if len(poly.vertices) >= 3:
                verts = [mesh.vertices[v].co for v in poly.vertices[:3]]
                # Calculate aspect ratio using edge lengths
                edges = [
                    (verts[1] - verts[0]).length,
                    (verts[2] - verts[1]).length,
                    (verts[0] - verts[2]).length,
                ]
                if min(edges) > 0:
                    aspect_ratio = max(edges) / min(edges)
                    if aspect_ratio > 10:  # Very thin triangle
                        thin_triangle_count += 1

        validation["stats"]["thin_triangles"] = thin_triangle_count
        if thin_triangle_count > triangle_count * 0.1:
            validation["warnings"].append(
                f"Many thin triangles detected ({thin_triangle_count}). "
                "May impact Nanite clustering efficiency."
            )

        # Check vertex count
        validation["stats"]["vertex_count"] = len(mesh.vertices)

        # Materials check
        validation["stats"]["material_count"] = len(mesh.materials)
        if len(mesh.materials) == 0:
            validation["warnings"].append("No materials assigned.")

    except Exception as e:
        validation["compatible"] = False
        validation["warnings"].append(f"Validation error: {e}")

    return validation


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
            "build_cutoff_thickness": 0.0,
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


def export_tree_as_usd(
    grove,
    output_path: Path,
    species_name: str,
    include_skeleton: bool = True,
    export_skeleton_separately: bool = False,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
) -> bool:
    """Export Grove tree model as USD for Unreal Engine 5 Nanite.

    Args:
        grove: Grove instance with simulated trees
        output_path: Path for the USD file (.usd or .usda)
        species_name: Tree species name for material naming
        include_skeleton: Whether to include skeleton in export
        export_skeleton_separately: Export skeleton as separate USD file
        resolution: Number of vertices around branch circumference (4-32, default: 32)
                   Higher = smoother branches. 16=moderate, 24=high, 32=very high quality
        resolution_reduce: How quickly to reduce resolution on thinner branches (0.0-1.0, default: 0.8)
                          Lower = maintains detail longer, Higher = reduces faster
        texture_repeat: Texture repetitions around trunk circumference (default: 3)
        build_cutoff_age: Skip building branches younger than this age (default: 0)
        build_cutoff_thickness: Skip branches thinner than this diameter (default: 0.0)
        build_blend: Add smooth geometry at branch joints (default: True)
        build_end_cap: Close off branch ends with geometry (default: True)

    Returns:
        bool: Success status
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export USD")
        return False

    ensure_grove_available()
    config = get_config()

    try:
        # Clear existing scene
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        # Build tree model with configurable quality settings
        models = grove.build_models(
            {
                "resolution": resolution,
                "resolution_reduce": resolution_reduce,
                "texture_repeat": texture_repeat,
                "build_cutoff_age": build_cutoff_age,
                "build_cutoff_thickness": build_cutoff_thickness,
                "build_blend": build_blend,
                "build_end_cap": build_end_cap,
            }
        )

        if not models:
            print("No models generated from grove")
            return False

        model = models[0]

        # Create mesh
        mesh_name = f"{species_name}_tree_mesh"
        mesh = bpy.data.meshes.new(mesh_name)

        points = model.get_points_flat()
        faces = [[int(i) for i in face] for face in model.faces]
        uvs = model.get_uvs_flat() if hasattr(model, "get_uvs_flat") else []

        vertices = [
            (points[i], points[i + 1], points[i + 2]) for i in range(0, len(points), 3)
        ]

        mesh.from_pydata(vertices, [], faces)
        mesh.update()

        if uvs and len(uvs) >= len(faces) * 6:
            mesh.uv_layers.new(name="UVMap")
            uv_layer = mesh.uv_layers.active.data
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv_index = loop_index * 2
                    if uv_index + 1 < len(uvs):
                        uv_layer[loop_index].uv = (uvs[uv_index], uvs[uv_index + 1])

        _add_grove_attributes_to_mesh(mesh, model)

        obj = bpy.data.objects.new(mesh_name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Apply triangulation for Nanite (requires consistent topology)
        triangulate_modifier = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")
        triangulate_modifier.quad_method = "BEAUTY"
        triangulate_modifier.ngon_method = "BEAUTY"

        # Build skeleton
        armature_obj = None
        if include_skeleton or export_skeleton_separately:
            skeletons = grove.build_skeletons()
            if skeletons:
                armature_obj = _add_skeleton_to_object(obj, skeletons[0], species_name)

        # Add material with textures
        _add_material_with_textures(obj, species_name, config)

        # Validate mesh for Nanite (after materials are assigned)
        validation = validate_mesh_for_nanite(mesh)
        if validation["warnings"]:
            print(f"Nanite validation warnings for {species_name}:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
        print(
            f"Mesh stats: {validation['stats']['triangle_count']:,} tris, "
            f"{validation['stats']['vertex_count']:,} verts"
        )

        # Export skeleton separately if requested
        if export_skeleton_separately and armature_obj:
            skeleton_path = (
                output_path.parent / f"{output_path.stem}_skeleton{output_path.suffix}"
            )
            bpy.ops.object.select_all(action="DESELECT")
            armature_obj.select_set(True)
            bpy.context.view_layer.objects.active = armature_obj

            skeleton_params = {
                "filepath": str(skeleton_path),
                "selected_objects_only": True,
                "export_animation": False,
                "export_armatures": True,
                "export_shapekeys": False,
                "use_instancing": False,
                "evaluation_mode": "RENDER",
            }

            try:
                bpy.ops.wm.usd_export(**skeleton_params, export_custom_properties=True)
            except TypeError:
                bpy.ops.wm.usd_export(**skeleton_params)

        # Export mesh (with or without skeleton)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        if include_skeleton and armature_obj and not export_skeleton_separately:
            armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # USD export optimized for Nanite with all Grove attributes
        # Try to export with attributes if supported (Blender 3.6+)
        export_params = {
            "filepath": str(output_path),
            "selected_objects_only": True,
            "export_animation": False,
            "export_armatures": (include_skeleton and not export_skeleton_separately),
            "export_shapekeys": False,
            "use_instancing": False,
            "evaluation_mode": "RENDER",
            "generate_preview_surface": True,
            "export_materials": True,
            "export_uvmaps": True,
            "export_normals": True,
        }

        # Add export_attributes if supported (Blender 3.6+)
        try:
            bpy.ops.wm.usd_export(**export_params, export_custom_properties=True)
        except TypeError:
            # Fallback for older Blender versions without attribute export
            bpy.ops.wm.usd_export(**export_params)

        # Write Blender mesh attributes as USD primvars (critical for twig placement)
        _add_blender_attributes_as_usd_primvars(output_path, obj)

        # Add Nanite attributes to USD file
        add_nanite_attributes_to_usd(output_path, is_foliage=False)

        print(f"✓ Exported USD with Nanite compatibility for {species_name}")
        return True

    except Exception as e:
        print(f"Failed to export tree USD: {e}")
        return False


def create_nanite_assembly_usd(
    tree_mesh_path: Path,
    twig_mesh_paths: List[Path],
    output_assembly_path: Path,
    species_name: str,
) -> bool:
    """Create a USD Assembly file for Unreal Engine 5.7 Nanite Assemblies.

    This generates a .usda file with proper Unreal API schemas that defines
    the hierarchical assembly composition with instancing for twigs.

    Args:
        tree_mesh_path: Path to main tree mesh USD file (trunk/branches)
        twig_mesh_paths: List of paths to twig/leaf USD mesh files
        output_assembly_path: Output path for assembly USDA file
        species_name: Tree species name

    Returns:
        bool: Success status
    """
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom

        # Create new stage
        stage = Usd.Stage.CreateNew(str(output_assembly_path))

        # Define root prim with NaniteAssemblyRootAPI
        root_prim = stage.DefinePrim(f"/{species_name}_Assembly", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Add Unreal Nanite Assembly metadata
        root_prim.SetMetadata("apiSchemas", ["NaniteAssemblyRootAPI"])
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token
        ).Set("staticMesh")

        # Reference main tree mesh (trunk/branches)
        trunk_prim = stage.DefinePrim(f"/{species_name}_Assembly/Trunk", "Xform")
        trunk_prim.GetReferences().AddReference(str(tree_mesh_path.resolve()))
        trunk_prim.SetMetadata("apiSchemas", ["NaniteAssemblyExternalRefAPI"])

        # Add twig instances if provided
        if twig_mesh_paths:
            twigs_group = stage.DefinePrim(f"/{species_name}_Assembly/Twigs", "Xform")

            for idx, twig_path in enumerate(twig_mesh_paths):
                twig_prim = stage.DefinePrim(
                    f"/{species_name}_Assembly/Twigs/Twig_{idx}", "Xform"
                )
                twig_prim.GetReferences().AddReference(str(twig_path.resolve()))
                twig_prim.SetMetadata("apiSchemas", ["NaniteAssemblyExternalRefAPI"])

        # Save stage
        stage.GetRootLayer().Save()
        return True

    except ImportError:
        print("USD Python (pxr) not available. Install with: pip install usd-core")
        return False
    except Exception as e:
        print(f"Failed to create Nanite Assembly USD: {e}")
        return False


def _add_skeleton_to_object(obj: Any, skeleton: Any, species_name: str) -> Any:
    """Add skeleton/armature to the tree object.

    Returns:
        The armature object created
    """
    try:
        # Create armature
        armature = bpy.data.armatures.new(f"{species_name}_armature")
        armature_obj = bpy.data.objects.new(f"{species_name}_skeleton", armature)
        bpy.context.collection.objects.link(armature_obj)

        # Enter edit mode to add bones
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Add bones from skeleton data
        points = skeleton.points
        poly_lines = skeleton.poly_lines

        # Map point indices to bones for branch connections
        point_to_bone = {}

        for i, poly_line in enumerate(poly_lines):
            if len(poly_line) < 2:
                continue

            previous_bone = None
            for j in range(len(poly_line) - 1):
                bone_name = f"bone_{i}_{j}"
                bone = armature.edit_bones.new(bone_name)

                start_idx = poly_line[j]
                end_idx = poly_line[j + 1]

                if start_idx < len(points) and end_idx < len(points):
                    bone.head = points[start_idx]
                    bone.tail = points[end_idx]

                # Set parent: either previous bone in chain or parent branch bone
                if j == 0 and start_idx in point_to_bone:
                    # First bone of branch - connect to parent branch at shared point
                    bone.parent = point_to_bone[start_idx]
                elif previous_bone is not None:
                    # Continue chain within same branch
                    bone.parent = previous_bone

                # Track this bone's endpoint for potential child branches
                point_to_bone[end_idx] = bone
                previous_bone = bone

        bpy.ops.object.mode_set(mode="OBJECT")

        # Add armature modifier for proper deformation (don't use parent relationship for FBX export)
        modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = armature_obj
        modifier.use_vertex_groups = True

        # Create vertex groups for automatic weights (optional - can be improved)
        # For now, we just ensure the armature relationship is via modifier only

        return armature_obj

    except Exception as e:
        print(f"Failed to add skeleton: {e}")
        return None


def _add_grove_attributes_to_mesh(mesh: Any, model: Any) -> None:
    """Add Grove model attributes to Blender mesh as custom properties.

    This preserves all the information from the Grove, including twig placements,
    branch indices, and various tree attributes that can be used in Unreal Engine.
    """
    try:
        # Face (polygon) attributes - these are critical for twig placements
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

        if hasattr(model, "face_attribute_branch_index"):
            face_layer = mesh.attributes.new(
                name="branch_index", type="INT", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_branch_index):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_branch_index_parent"):
            face_layer = mesh.attributes.new(
                name="branch_index_parent", type="INT", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_branch_index_parent):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_end"):
            face_layer = mesh.attributes.new(
                name="branch_end", type="BOOLEAN", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_end):
                face_layer.data[i].value = val

        if hasattr(model, "face_attribute_tree_index"):
            face_layer = mesh.attributes.new(
                name="tree_index", type="INT", domain="FACE"
            )
            for i, val in enumerate(model.face_attribute_tree_index):
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

        if hasattr(model, "point_attribute_mass"):
            point_layer = mesh.attributes.new(name="mass", type="FLOAT", domain="POINT")
            for i, val in enumerate(model.point_attribute_mass):
                point_layer.data[i].value = val

        if hasattr(model, "point_attribute_shade"):
            point_layer = mesh.attributes.new(
                name="shade", type="FLOAT", domain="POINT"
            )
            for i, val in enumerate(model.point_attribute_shade):
                point_layer.data[i].value = val

        if hasattr(model, "point_attribute_vigor"):
            point_layer = mesh.attributes.new(
                name="vigor", type="FLOAT", domain="POINT"
            )
            for i, val in enumerate(model.point_attribute_vigor):
                point_layer.data[i].value = val

        if hasattr(model, "point_attribute_photosynthesis"):
            point_layer = mesh.attributes.new(
                name="photosynthesis", type="FLOAT", domain="POINT"
            )
            for i, val in enumerate(model.point_attribute_photosynthesis):
                point_layer.data[i].value = val

        if hasattr(model, "point_attribute_pitch"):
            point_layer = mesh.attributes.new(
                name="pitch", type="FLOAT", domain="POINT"
            )
            for i, val in enumerate(model.point_attribute_pitch):
                point_layer.data[i].value = val

    except Exception as e:
        print(f"Warning: Failed to add some Grove attributes to mesh: {e}")


def _add_grove_face_attributes_to_usd(usd_path: Path, model: Any) -> None:
    """Add Grove face attributes (twig placements) to USD file as primvars.

    Grove's native USD export doesn't include twig face attributes which are
    critical for twig placement. This function adds them manually.

    Args:
        usd_path: Path to USD file to modify
        model: Grove model with face attributes
    """
    try:
        from pxr import Sdf, Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Warning: Could not open USD stage at {usd_path}")
            return

        # Find mesh prim
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue

            mesh_usd = UsdGeom.Mesh(prim)
            primvars_api = UsdGeom.PrimvarsAPI(mesh_usd)

            # Add twig face attributes with uniform interpolation (per-face)
            twig_attrs = [
                ("twig_long", "face_attribute_twig_long"),
                ("twig_short", "face_attribute_twig_short"),
                ("twig_upward", "face_attribute_twig_upward"),
                ("twig_dead", "face_attribute_twig_dead"),
            ]

            twig_counts = {}
            for attr_name, model_attr in twig_attrs:
                if hasattr(model, model_attr):
                    values = getattr(model, model_attr)
                    if values:
                        # Convert Grove's Rust Vec<bool> to Python list
                        # Use list() to force conversion from Rust collection
                        try:
                            bool_values = list(values)
                        except Exception:
                            # Fallback if list() doesn't work
                            bool_values = [bool(values[i]) for i in range(len(values))]

                        primvar = primvars_api.CreatePrimvar(
                            attr_name,
                            Sdf.ValueTypeNames.BoolArray,
                            UsdGeom.Tokens.uniform,
                        )
                        primvar.Set(bool_values)
                        true_count = sum(1 for v in bool_values if v)
                        twig_counts[attr_name] = true_count

            if twig_counts:
                print(f"  ✓ Added twig face attributes to USD:")
                for attr, count in twig_counts.items():
                    print(f"    - {attr}: {count} faces")
            else:
                print(f"  Warning: No twig attributes found in Grove model")

        stage.Save()

    except Exception as e:
        print(f"Warning: Failed to add Grove face attributes to USD: {e}")
        import traceback

        traceback.print_exc()


def _add_blender_attributes_as_usd_primvars(usd_path: Path, mesh_obj: Any) -> None:
    """Write Blender mesh attributes as USD primvars after export.

    Blender's USD exporter doesn't export custom mesh attributes as primvars,
    so we manually write them using the USD Python API.

    Args:
        usd_path: Path to USD file to modify
        mesh_obj: Blender mesh object with custom attributes
    """
    try:
        from pxr import Sdf, Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Warning: Could not open USD stage at {usd_path}")
            return

        # Find the mesh prim (typically at /Tree/Tree or similar)
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue

            mesh_usd = UsdGeom.Mesh(prim)
            primvars_api = UsdGeom.PrimvarsAPI(mesh_usd)
            mesh_data = mesh_obj.data

            # Twig attributes (FACE domain - most critical for twig placement)
            twig_attrs = [
                ("twig_long", Sdf.ValueTypeNames.Bool),
                ("twig_short", Sdf.ValueTypeNames.Bool),
                ("twig_upward", Sdf.ValueTypeNames.Bool),
                ("twig_dead", Sdf.ValueTypeNames.Bool),
            ]

            for attr_name, value_type in twig_attrs:
                if attr_name in mesh_data.attributes:
                    attr = mesh_data.attributes[attr_name]
                    # Get values from Blender attribute
                    values = [attr.data[i].value for i in range(len(attr.data))]

                    # Create USD primvar with uniform interpolation (per-face)
                    primvar = primvars_api.CreatePrimvar(
                        attr_name, value_type, UsdGeom.Tokens.uniform
                    )
                    primvar.Set(values)
                    print(
                        f"  Added primvar {attr_name}: {sum(values)} true out of {len(values)} faces"
                    )

            # Other face attributes
            face_attrs = [
                ("branch_dead", Sdf.ValueTypeNames.Bool),
                ("branch_index", Sdf.ValueTypeNames.Int),
                ("branch_index_parent", Sdf.ValueTypeNames.Int),
                ("branch_end", Sdf.ValueTypeNames.Bool),
                ("tree_index", Sdf.ValueTypeNames.Int),
            ]

            for attr_name, value_type in face_attrs:
                if attr_name in mesh_data.attributes:
                    attr = mesh_data.attributes[attr_name]
                    values = [attr.data[i].value for i in range(len(attr.data))]
                    primvar = primvars_api.CreatePrimvar(
                        attr_name, value_type, UsdGeom.Tokens.uniform
                    )
                    primvar.Set(values)

            # Point (vertex) attributes
            point_attrs = [
                ("age", Sdf.ValueTypeNames.Int),
                ("thickness", Sdf.ValueTypeNames.Float),
                ("mass", Sdf.ValueTypeNames.Float),
                ("shade", Sdf.ValueTypeNames.Float),
                ("vigor", Sdf.ValueTypeNames.Float),
                ("photosynthesis", Sdf.ValueTypeNames.Float),
                ("pitch", Sdf.ValueTypeNames.Float),
            ]

            for attr_name, value_type in point_attrs:
                if attr_name in mesh_data.attributes:
                    attr = mesh_data.attributes[attr_name]
                    values = [attr.data[i].value for i in range(len(attr.data))]
                    primvar = primvars_api.CreatePrimvar(
                        attr_name, value_type, UsdGeom.Tokens.vertex
                    )
                    primvar.Set(values)

        stage.Save()
        print(f"✓ Added Blender attributes as USD primvars to {usd_path.name}")

    except Exception as e:
        print(f"Warning: Failed to add primvars to USD file: {e}")
        import traceback

        traceback.print_exc()


def _find_bark_texture(
    species_name: str, config: Optional[Any] = None
) -> Optional[Dict[str, Path]]:
    """Find bark texture files for a species from assets folder.

    Args:
        species_name: Common name of species (e.g., "European beech")
        config: GrowPy configuration

    Returns:
        Dict with 'diffuse' and 'normal' texture paths, or None if not found
    """
    if config is None:
        config = get_config()

    # Get project root
    project_root = Path(__file__).parent.parent.parent.parent
    texture_dir = project_root / "data" / "assets" / "textures"

    if not texture_dir.exists():
        return None

    textures = {}

    # Try to get texture from lookup table first
    try:
        from ..config import GrowPyConfig

        species_data = GrowPyConfig.get_species_data(species_name)
        if species_data and "Bark Texture" in species_data:
            bark_texture_name = species_data.get("Bark Texture")
            if bark_texture_name and str(bark_texture_name) not in ["", "nan"]:
                diffuse_path = texture_dir / bark_texture_name
                if diffuse_path.exists():
                    textures["diffuse"] = diffuse_path

                    # Look for corresponding normal map
                    normal_name = diffuse_path.stem + "Normal" + diffuse_path.suffix
                    normal_path = diffuse_path.parent / normal_name
                    if normal_path.exists():
                        textures["normal"] = normal_path
                    else:
                        # Try alternative normal naming (e.g., Birch70_normal.jpg)
                        normal_name_alt = (
                            diffuse_path.stem + "_normal" + diffuse_path.suffix
                        )
                        normal_path_alt = diffuse_path.parent / normal_name_alt
                        if normal_path_alt.exists():
                            textures["normal"] = normal_path_alt

                    return textures
    except Exception:
        pass

    # Fallback: use original pattern matching
    # Clean species name for matching
    species_clean = species_name.lower().replace(" ", "").replace("-", "")

    # Common texture name patterns to try
    texture_patterns = [
        species_name.replace(" ", ""),  # "EuropeanBeech"
        species_name.split()[-1],  # "Beech"
        species_name.split()[0],  # "European"
    ]

    for pattern in texture_patterns:
        pattern_clean = pattern.replace(" ", "").lower()

        # Look for diffuse texture
        for tex_file in texture_dir.glob(f"*{pattern}*.jpg"):
            if "normal" not in tex_file.name.lower():
                textures["diffuse"] = tex_file

                # Look for corresponding normal map
                normal_name = tex_file.stem + "Normal" + tex_file.suffix
                normal_path = tex_file.parent / normal_name
                if normal_path.exists():
                    textures["normal"] = normal_path
                break

        if textures:
            break

    return textures if textures else None


def _add_material_with_textures(
    obj: Any, species_name: str, config: Optional[Any] = None
) -> None:
    """Add material with bark textures to tree object.

    Args:
        obj: Blender object
        species_name: Name of species for texture lookup
        config: GrowPy configuration
    """
    try:
        material = bpy.data.materials.new(name=f"{species_name}_bark")
        material.use_nodes = True
        nodes = material.node_tree.nodes

        # Clear default nodes
        nodes.clear()

        # Add basic nodes
        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        output_node.location = (400, 0)

        bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf_node.location = (0, 0)

        # Find textures
        textures = _find_bark_texture(species_name, config)

        if textures:
            # Add diffuse texture
            if "diffuse" in textures:
                tex_image = bpy.data.images.load(str(textures["diffuse"]))
                tex_node = nodes.new(type="ShaderNodeTexImage")
                tex_node.image = tex_image
                tex_node.location = (-400, 200)
                tex_node.label = "Bark Diffuse"

                # Connect to base color
                links = material.node_tree.links
                links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])

            # Add normal map
            if "normal" in textures:
                normal_image = bpy.data.images.load(str(textures["normal"]))
                normal_tex_node = nodes.new(type="ShaderNodeTexImage")
                normal_tex_node.image = normal_image
                normal_tex_node.location = (-400, -200)
                normal_tex_node.label = "Bark Normal"
                normal_tex_node.image.colorspace_settings.name = "Non-Color"

                # Add normal map node
                normal_map_node = nodes.new(type="ShaderNodeNormalMap")
                normal_map_node.location = (-100, -200)

                links = material.node_tree.links
                links.new(
                    normal_tex_node.outputs["Color"], normal_map_node.inputs["Color"]
                )
                links.new(normal_map_node.outputs["Normal"], bsdf_node.inputs["Normal"])
        else:
            # Fallback to simple brown color
            bsdf_node.inputs["Base Color"].default_value = (0.4, 0.3, 0.2, 1.0)

        # Set material properties for bark
        bsdf_node.inputs["Roughness"].default_value = 0.8
        bsdf_node.inputs["Metallic"].default_value = 0.0

        # Link to output
        links = material.node_tree.links
        links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

        # Assign to object
        obj.data.materials.append(material)

    except Exception as e:
        print(f"Failed to add material with textures: {e}")
        # Fallback to simple material
        _add_simple_material(obj, species_name)


def _add_simple_material(obj: Any, species_name: str) -> None:
    """Add simple material to tree object (fallback)."""
    try:
        material = bpy.data.materials.new(name=f"{species_name}_bark")
        material.use_nodes = True
        nodes = material.node_tree.nodes

        # Clear default nodes
        nodes.clear()

        # Add basic nodes
        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")

        # Set brown bark color
        bsdf_node.inputs["Base Color"].default_value = (0.4, 0.3, 0.2, 1.0)
        bsdf_node.inputs["Roughness"].default_value = 0.8

        # Link nodes
        links = material.node_tree.links
        links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

        # Assign to object
        obj.data.materials.append(material)

    except Exception as e:
        print(f"Failed to add material: {e}")


def export_twigs_from_blend(blend_file_path: Path, output_dir: Path) -> List[Path]:
    """Export all twig objects from a Blend file as individual USD files.

    Args:
        blend_file_path: Path to the .blend file containing twigs
        output_dir: Directory to save individual twig USD files

    Returns:
        List[Path]: Paths to exported USD files
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export twigs")
        return []

    if not blend_file_path.exists():
        print(f"Blend file not found: {blend_file_path}")
        return []

    exported_files = []

    try:
        # Clear existing data to prevent memory issues
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Load the blend file
        bpy.ops.wm.open_mainfile(filepath=str(blend_file_path))

        # Find all mesh objects
        mesh_objects = [
            obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.data
        ]

        if not mesh_objects:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)

        for obj in mesh_objects:
            try:
                # Clear selection and select only this object
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Clean object name for filename
                clean_name = "".join(
                    c for c in obj.name if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                clean_name = clean_name.replace(" ", "_")
                if not clean_name:
                    clean_name = f"twig_{len(exported_files)}"

                usd_path = output_dir / f"{clean_name}.usda"

                # Export as USD with all attributes
                twig_params = {
                    "filepath": str(usd_path),
                    "selected_objects_only": True,
                    "export_animation": False,
                    "export_armatures": False,
                    "export_shapekeys": False,
                    "use_instancing": False,
                    "evaluation_mode": "RENDER",
                    "generate_preview_surface": True,
                    "export_materials": True,
                    "export_uvmaps": True,
                    "export_normals": True,
                }

                try:
                    bpy.ops.wm.usd_export(**twig_params, export_custom_properties=True)
                except TypeError:
                    bpy.ops.wm.usd_export(**twig_params)

                exported_files.append(usd_path)

            except Exception as e:
                continue

    except Exception as e:
        print(f"Failed to process blend file {blend_file_path}: {e}")

    return exported_files


def _export_fbx_internal(
    grove: Any,
    output_path: Path,
    species_name: str,
    include_skeleton: bool = True,
    include_twig_attributes: bool = True,
    config: Optional[Any] = None,
) -> bool:
    """Export tree as FBX with textures, skeleton, and twig attributes.

    Args:
        grove: Grove object containing tree
        output_path: Output FBX file path
        species_name: Name of species for materials
        include_skeleton: Include armature/skeleton
        include_twig_attributes: Preserve twig placement attributes
        config: GrowPy configuration

    Returns:
        bool: Success status
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export FBX")
        return False

    try:
        # Clear scene
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Build Grove model first
        from ..core.tree import build_grove_with_all_attributes

        build_params = {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "build_end_cap": True,
        }
        models = build_grove_with_all_attributes(grove, build_params)

        if not models:
            print(f"No models generated for {species_name}")
            return False

        model = models[0]

        # Extract mesh data from Grove model
        points = model.get_points_flat()
        faces = [[int(i) for i in face] for face in model.faces]
        uvs = model.get_uvs_flat() if hasattr(model, "get_uvs_flat") else []
        vertices = [
            (points[i], points[i + 1], points[i + 2]) for i in range(0, len(points), 3)
        ]

        # Create Blender mesh
        mesh = bpy.data.meshes.new(f"{species_name}_mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()

        # Add UVs if available
        if uvs and len(uvs) >= len(faces) * 6:
            mesh.uv_layers.new(name="UVMap")
            uv_layer = mesh.uv_layers.active.data
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv_index = loop_index * 2
                    if uv_index + 1 < len(uvs):
                        uv_layer[loop_index].uv = (uvs[uv_index], uvs[uv_index + 1])

        # Add Grove attributes to mesh (including twig attributes)
        if include_twig_attributes:
            _add_grove_attributes_to_mesh(mesh, model)

        # Create object
        obj = bpy.data.objects.new(f"{species_name}_tree", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Build skeleton
        armature_obj = None
        if include_skeleton:
            skeletons = grove.build_skeletons()
            if skeletons:
                armature_obj = _add_skeleton_to_object(obj, skeletons[0], species_name)

        # Add material with textures
        _add_material_with_textures(obj, species_name, config)

        # Add Nanite metadata as custom properties
        obj["nanite_compatible"] = True
        obj["nanite_preserve_area"] = False  # False for trees (branches/trunk)
        obj["unreal_nanite"] = "enable"

        # Apply triangulation for consistent topology (Nanite requirement)
        triangulate_mod = obj.modifiers.new(
            name="Triangulate_Nanite", type="TRIANGULATE"
        )
        triangulate_mod.quad_method = "BEAUTY"
        triangulate_mod.ngon_method = "BEAUTY"

        # Validate mesh for Nanite
        mesh_data = obj.data
        validation = validate_mesh_for_nanite(mesh_data)
        if validation["warnings"]:
            print(f"Nanite validation warnings for {species_name}:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

        # Prepare for export
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        if include_skeleton and armature_obj:
            armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # FBX Export with optimal settings for Unreal Nanite
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=True,
            object_types={"MESH", "ARMATURE"} if include_skeleton else {"MESH"},
            mesh_smooth_type="FACE",  # Single smoothing group (Nanite requirement)
            use_mesh_modifiers=True,  # Apply triangulation modifier
            use_mesh_edges=False,  # No edge data (cleaner for Nanite)
            use_tspace=True,  # Tangent space for normal maps
            use_custom_props=True,  # Export Nanite metadata + twig attributes
            add_leaf_bones=False,
            primary_bone_axis="Y",
            secondary_bone_axis="X",
            armature_nodetype="NULL",
            bake_anim=False,
            path_mode="COPY",  # Copy textures
            embed_textures=True,  # Embed in FBX
            batch_mode="OFF",
            use_batch_own_dir=False,
            axis_forward="-Z",
            axis_up="Y",
        )

        print(
            f"✓ Exported FBX with textures and {'skeleton + ' if include_skeleton else ''}{'twig attributes' if include_twig_attributes else ''}"
        )
        return True

    except Exception as e:
        print(f"Failed to export tree FBX: {e}")
        import traceback

        traceback.print_exc()
        return False


def batch_export_tree_usd(
    forest_data: Any,
    output_dir: Path,
    config: Optional[Any] = None,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
) -> List[Path]:
    """Export multiple trees from forest data as individual USD files.

    Args:
        forest_data: Forest simulation data with species and positions
        output_dir: Directory to save USD files
        config: GrowPy configuration
        resolution: Number of vertices around branch circumference (4-32, default: 32)
        resolution_reduce: How quickly to reduce resolution on thinner branches (0.0-1.0)
        texture_repeat: Texture repetitions around trunk circumference
        build_cutoff_age: Skip building branches younger than this age
        build_cutoff_thickness: Skip branches thinner than this diameter
        build_blend: Add smooth geometry at branch joints
        build_end_cap: Close off branch ends with geometry

    Returns:
        List[Path]: Paths to exported USD files
    """
    if config is None:
        config = get_config()

    exported_files = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get unique species
    species_list = (
        forest_data["species"].unique()
        if hasattr(forest_data, "unique")
        else set(forest_data.get("species", []))
    )

    for species in species_list:
        try:
            from ..core.grove import create_grove
            from ..core.tree import build_grove_with_all_attributes

            # Create grove for this species
            grove = create_grove(species)

            # Add a single tree for this species
            gc = _get_gc()
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            # Simulate growth
            grove.simulate(flushes=10)

            # Export as USD
            species_clean = (
                "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
                .strip()
                .replace(" ", "_")
            )
            usd_path = output_dir / f"{species_clean}_tree.usda"

            if export_tree_as_usd(
                grove,
                usd_path,
                species,
                include_skeleton=True,
                export_skeleton_separately=False,
                resolution=resolution,
                resolution_reduce=resolution_reduce,
                texture_repeat=texture_repeat,
                build_cutoff_age=build_cutoff_age,
                build_cutoff_thickness=build_cutoff_thickness,
                build_blend=build_blend,
                build_end_cap=build_end_cap,
            ):
                exported_files.append(usd_path)

        except Exception as e:
            print(f"Failed to export {species} as USD: {e}")
            continue

    return exported_files


def batch_export_trees_for_unreal(
    forest_data: Any,
    output_dir: Path,
    config: Optional[Any] = None,
    num_variations: int = 3,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
    bundle_twigs: bool = True,
    export_formats: List[str] = ["fbx", "usda"],
    use_native_usd_export: bool = True,
    include_twigs_in_usd: bool = True,
    create_nanite_assembly: bool = True,
) -> Dict[str, List[Path]]:
    """Export trees as FBX/USD for Unreal Engine Nanite with PCG metadata.

    Creates multiple variations of each species for procedural variation in Unreal's
    PCG (Procedural Content Generation) and Foliage systems. Includes twig bundling
    and comprehensive metadata for optimal Unreal workflow.

    Args:
        forest_data: Forest simulation data with species and positions
        output_dir: Base directory for exports
        config: GrowPy configuration
        num_variations: Number of variations per species for procedural diversity
        resolution: Number of vertices around branch circumference (4-32, default: 32)
        resolution_reduce: How quickly to reduce resolution on thinner branches (0.0-1.0)
        texture_repeat: Texture repetitions around trunk circumference
        build_cutoff_age: Skip building branches younger than this age
        build_cutoff_thickness: Skip branches thinner than this diameter
        build_blend: Add smooth geometry at branch joints
        build_end_cap: Close off branch ends with geometry
        bundle_twigs: Copy relevant twig files to output folder
        export_formats: Export formats ('fbx', 'usd', 'usda')
        use_native_usd_export: Use Grove's native USD export (recommended, includes all attributes)
        include_twigs_in_usd: Include twigs as point instances in USD files
        create_nanite_assembly: Create Nanite Assembly USD for Unreal Engine (default: True)

    Returns:
        Dict with 'usd', 'fbx', 'metadata', and 'twigs' file paths
    """
    if config is None:
        config = get_config()

    import json

    from .unreal_metadata import create_metadata_from_growth_data

    results = {"usd": [], "fbx": [], "metadata": [], "twigs": []}

    # Create output directories
    usd_dir = (
        output_dir / "USD"
        if "usd" in export_formats or "usda" in export_formats
        else None
    )
    fbx_dir = output_dir / "FBX" if "fbx" in export_formats else None
    metadata_dir = output_dir / "Metadata"

    if usd_dir:
        usd_dir.mkdir(parents=True, exist_ok=True)
    if fbx_dir:
        fbx_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Get unique species and their growth cycles from forest data
    species_list = (
        forest_data["species"].unique()
        if hasattr(forest_data, "unique")
        else set(forest_data.get("species", []))
    )

    for species in species_list:
        try:
            from ..core.grove import create_grove

            species_clean = (
                "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
                .strip()
                .replace(" ", "_")
            )
            species_metadata = {
                "species": species,
                "variations": [],
                "recommended_settings": {
                    "min_spacing": 3.0,
                    "max_spacing": 8.0,
                    "scale_min": 0.8,
                    "scale_max": 1.2,
                    "rotation_random": True,
                    "align_to_normal": True,
                },
            }

            # Get average growth cycles for this species from forest data
            # Use the mean growth cycles for trees of this species
            species_trees = forest_data[forest_data["species"] == species]
            if "growth_cycles" in species_trees.columns:
                avg_cycles = int(species_trees["growth_cycles"].mean())
            else:
                # Fallback to default if growth_cycles not calculated
                avg_cycles = 10
                print(
                    f"Warning: No growth_cycles found for {species}, using default {avg_cycles}"
                )

            # Create variations with different random seeds and parameters
            for variation_idx in range(num_variations):
                grove = create_grove(species)

                # Apply variation parameters to grove settings
                if hasattr(grove, "tree"):
                    tree = grove.tree

                    if variation_idx == 1:
                        if hasattr(tree, "lean"):
                            tree.lean = 0.15
                        if hasattr(tree, "branch_density"):
                            tree.branch_density *= 1.2
                        if hasattr(tree, "thickness_variation"):
                            tree.thickness_variation = 0.9
                    elif variation_idx == 2:
                        if hasattr(tree, "lean"):
                            tree.lean = 0.05
                        if hasattr(tree, "thickness_variation"):
                            tree.thickness_variation = 1.1

                # Add tree with unique random seed
                import random

                random.seed(42 + variation_idx * 100)

                gc = _get_gc()
                grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

                # Simulate using growth cycles calculated from tree height
                # Add slight variation (±1 flush) to create diversity within species
                flush_count = avg_cycles + (variation_idx % 3) - 1
                flush_count = max(1, flush_count)  # Ensure at least 1 flush
                grove.simulate(flushes=flush_count)

                variation_name = f"{species_clean}_var{variation_idx + 1}"

                # Document variation characteristics
                variation_type = "standard"
                if variation_idx == 1:
                    variation_type = "leaning_dense"
                elif variation_idx == 2:
                    variation_type = "upright_thick"

                variation_info = {
                    "name": variation_name,
                    "variation_index": variation_idx,
                    "variation_type": variation_type,
                    "growth_flushes": flush_count,
                    "files": {},
                }

                # Export USD if requested
                if usd_dir:
                    usd_path = usd_dir / f"{variation_name}.usda"

                    # Get twig USD paths if including twigs
                    twig_usd_map = None
                    if include_twigs_in_usd:
                        twig_usd_map = get_twig_usd_map_for_species(species, config)
                        if not twig_usd_map:
                            print(f"  Warning: No twig USD files found for {species}")

                    export_success = False
                    if use_native_usd_export:
                        # Use Grove's native USD export with twigs
                        export_success = export_grove_tree_as_usda_native(
                            grove,
                            usd_path,
                            species,
                            twig_usd_paths=twig_usd_map,
                            include_twigs=include_twigs_in_usd,
                            use_point_instancer=True,
                            convert_to_ue=True,
                            create_nanite_assembly=create_nanite_assembly,
                            resolution=resolution,
                            resolution_reduce=resolution_reduce,
                            texture_repeat=texture_repeat,
                            build_cutoff_age=build_cutoff_age,
                            build_cutoff_thickness=build_cutoff_thickness,
                            build_blend=build_blend,
                            build_end_cap=build_end_cap,
                        )
                    else:
                        # Use Blender-based USD export (legacy)
                        export_success = export_tree_as_usd(
                            grove,
                            usd_path,
                            species,
                            include_skeleton=True,
                            export_skeleton_separately=False,
                            resolution=resolution,
                            resolution_reduce=resolution_reduce,
                            texture_repeat=texture_repeat,
                            build_cutoff_age=build_cutoff_age,
                            build_cutoff_thickness=build_cutoff_thickness,
                            build_blend=build_blend,
                            build_end_cap=build_end_cap,
                        )

                    if export_success:
                        results["usd"].append(usd_path)
                        variation_info["files"]["usd"] = str(
                            usd_path.relative_to(output_dir)
                        )

                # Export FBX if requested
                if fbx_dir:
                    fbx_path = fbx_dir / f"{variation_name}.fbx"
                    try:
                        from ..core.tree import (
                            build_grove_with_all_attributes,
                            build_skeletons,
                        )

                        # Build mesh and skeleton
                        build_params = {
                            "resolution": resolution,
                            "resolution_reduce": resolution_reduce,
                            "build_cutoff_age": build_cutoff_age,
                            "build_cutoff_thickness": build_cutoff_thickness,
                            "build_blend": build_blend,
                            "build_end_cap": build_end_cap,
                        }
                        build_grove_with_all_attributes(grove, build_params)
                        build_skeletons(grove)

                        if _check_bpy_available():
                            if _export_fbx_internal(
                                grove,
                                fbx_path,
                                species,
                                include_skeleton=True,
                                include_twig_attributes=True,
                                config=config,
                            ):
                                results["fbx"].append(fbx_path)
                                variation_info["files"]["fbx"] = str(
                                    fbx_path.relative_to(output_dir)
                                )
                    except Exception as e:
                        print(f"FBX export failed for {variation_name}: {e}")

                species_metadata["variations"].append(variation_info)

            # Create PCG metadata from growth data
            # Estimate tree dimensions (this is a placeholder - ideally get from grove stats)
            height_range = (15.0, 25.0)  # meters, typical for mature tree
            crown_radius_range = (4.0, 7.0)  # meters

            # Create comprehensive PCG metadata
            pcg_metadata = create_metadata_from_growth_data(
                species_name=species,
                height_range=height_range,
                crown_radius_range=crown_radius_range,
                growth_rate="medium",
                twig_files=[],  # Will be populated if twigs bundled
                variation_count=num_variations,
            )

            # Bundle twigs if requested
            if bundle_twigs:
                print(f"  Bundling twigs for {species}...")
                twig_results = bundle_twigs_for_species(
                    species,
                    output_dir / species_clean,
                    formats=export_formats,
                    config=config,
                )
                results["twigs"].extend(twig_results["twig_files"])

                # Update PCG metadata with twig files
                if twig_results["manifest"]:
                    import json as json_lib

                    with open(twig_results["manifest"], "r") as f:
                        twig_manifest = json_lib.load(f)
                    pcg_metadata.twig_files = [
                        f
                        for files in twig_manifest["twig_types"].values()
                        for f in files
                    ]

            # Combine basic metadata with PCG metadata
            combined_metadata = {
                **species_metadata,
                "pcg": pcg_metadata.to_dict(),
                "unreal_settings": {
                    "nanite": {
                        "enabled": True,
                        "preserve_area": True,
                        "fallback_percent_triangles": 100,
                    },
                    "foliage_type": pcg_metadata.foliage_type,
                    "materials": {
                        "wpo_disable_distance": pcg_metadata.wpo_disable_distance,
                        "two_sided": False,
                        "blend_mode": "Opaque",
                    },
                },
            }

            # Save species metadata
            metadata_path = metadata_dir / f"{species_clean}_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(combined_metadata, f, indent=2)
            results["metadata"].append(metadata_path)

            print(f"Exported {species}: {num_variations} variations")
            if bundle_twigs and pcg_metadata.twig_files:
                print(f"  Bundled {len(pcg_metadata.twig_files)} twig files")

        except Exception as e:
            print(f"Failed to export {species}: {e}")
            continue

    # Create master metadata file for Unreal import
    master_metadata = {
        "format_version": "1.0",
        "export_type": "vegetation_assets",
        "species_count": len(species_list),
        "variations_per_species": num_variations,
        "species": [
            {
                "name": sp,
                "metadata_file": f"Metadata/{sp.replace(' ', '_')}_metadata.json",
            }
            for sp in species_list
        ],
        "unreal_import_notes": {
            "usd_import": "Import USD files for Nanite-enabled assets (UE 5.7+)",
            "foliage_setup": "Create Foliage Type assets for each variation",
            "pcg_setup": "Use metadata for PCG scatter point attributes",
        },
    }

    master_path = output_dir / "import_metadata.json"
    with open(master_path, "w") as f:
        json.dump(master_metadata, f, indent=2)
    results["metadata"].append(master_path)

    return results


def export_grove_tree_as_usda_native(
    grove: Any,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    include_twigs: bool = True,
    use_point_instancer: bool = True,
    convert_to_ue: bool = True,
    create_nanite_assembly: bool = True,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
) -> bool:
    """Export Grove tree using native USD export with optional twig point instances.

    This function uses The Grove's native model_to_usda_string() for the base tree
    export, then adds twigs as point instances following the Grove's twig placement
    attributes. Optionally creates a Nanite Assembly USD for Unreal Engine.

    Creates two USD files:
    - Standard USD with twigs (compatible with all DCC apps)
    - Nanite Assembly USD (optimized for Unreal Engine 5.7+)

    Args:
        grove: Grove instance with simulated trees
        output_path: Path for output USDA file
        species_name: Tree species name
        twig_usd_paths: Dict mapping twig types to USD file paths
                       {'twig_long': Path, 'twig_short': Path, etc.}
        include_twigs: Whether to add twigs as point instances
        use_point_instancer: Use USD PointInstancer (recommended for Unreal/Nanite)
        convert_to_ue: Convert coordinates from Blender to Unreal Engine
        create_nanite_assembly: Also create Nanite Assembly USD for Unreal (default: True)
        resolution: Number of vertices around branch circumference (4-32, default: 32)
        resolution_reduce: How quickly to reduce resolution on thinner branches (0.0-1.0)
        texture_repeat: Texture repetitions around trunk circumference
        build_cutoff_age: Skip building branches younger than this age
        build_cutoff_thickness: Skip branches thinner than this diameter
        build_blend: Add smooth geometry at branch joints
        build_end_cap: Close off branch ends with geometry

    Returns:
        bool: Success status
    """
    ensure_grove_available()
    gc = _get_gc()

    try:
        print(f"Exporting {species_name} as USDA...")

        # Build tree model with Grove
        models = grove.build_models(
            {
                "resolution": resolution,
                "resolution_reduce": resolution_reduce,
                "texture_repeat": texture_repeat,
                "build_cutoff_age": build_cutoff_age,
                "build_cutoff_thickness": build_cutoff_thickness,
                "build_blend": build_blend,
                "build_end_cap": build_end_cap,
            }
        )

        if not models:
            print("No models generated from grove")
            return False

        model = models[0]

        # Export using Grove's native USD export
        usda_string = gc.io.model_to_usda_string(model)

        # Save to temporary file first (we'll enhance it with twigs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_tree_path = (
            output_path.parent / f"{output_path.stem}_tree_only{output_path.suffix}"
        )

        with open(temp_tree_path, "w") as f:
            f.write(usda_string)

        print(f"  ✓ Exported base tree USD: {temp_tree_path.name}")

        # CRITICAL: Add twig face attributes from Grove model to USD
        # Grove's native USD export doesn't include custom face attributes
        _add_grove_face_attributes_to_usd(temp_tree_path, model)

        # Add twigs if requested
        if include_twigs and twig_usd_paths:
            from .twig_placement import export_twig_placements_to_usd

            print(f"  Adding twigs as point instances...")

            success = export_twig_placements_to_usd(
                tree_usd_path=temp_tree_path,
                twig_usd_paths=twig_usd_paths,
                output_path=output_path,
                tree_mesh=None,
                extract_from_usd=True,  # Extract placements from USD
                use_point_instancer=use_point_instancer,
                convert_to_ue=convert_to_ue,
            )

            if success:
                print(f"  ✓ Created complete USDA with twigs: {output_path.name}")
                # Keep the tree-only file for reference
                print(f"  ✓ Tree-only USD saved as: {temp_tree_path.name}")
            else:
                print(f"  Warning: Failed to add twigs, using tree-only export")
                # Copy tree-only to final output
                import shutil

                shutil.copy2(temp_tree_path, output_path)
        else:
            # No twigs requested, just use the tree-only export
            import shutil

            shutil.copy2(temp_tree_path, output_path)
            print(f"  ✓ Exported tree USD: {output_path.name}")

        # Create Nanite Assembly USD for Unreal if requested
        if create_nanite_assembly:
            from .unreal_nanite_assembly import create_nanite_assembly_usd

            nanite_path = (
                output_path.parent
                / f"{output_path.stem}_NaniteAssembly{output_path.suffix}"
            )

            print(f"\n  Creating Unreal Nanite Assembly...")
            nanite_success = create_nanite_assembly_usd(
                tree_usd_path=temp_tree_path if not include_twigs else output_path,
                output_path=nanite_path,
                species_name=species_name,
                twig_usd_paths=twig_usd_paths if include_twigs else None,
                use_skeletal_mesh=False,
            )

            if nanite_success:
                print(f"  ✓ Nanite Assembly USD: {nanite_path.name}")
                print(f"    Import this file in Unreal Engine 5.7+")

        return True

    except Exception as e:
        print(f"Failed to export Grove tree as USDA: {e}")
        import traceback

        traceback.print_exc()
        return False


def get_twig_usd_map_for_species(
    species_name: str,
    config: Optional[Any] = None,
) -> Dict[str, Path]:
    """Get mapping of twig types to USD file paths for a species.

    Args:
        species_name: Name of tree species
        config: GrowPy configuration

    Returns:
        Dict mapping twig types to USD file paths:
        {'twig_long': Path, 'twig_short': Path, ...}
    """
    if config is None:
        config = get_config()

    from ..config import GrowPyConfig

    twig_files_by_type = GrowPyConfig.get_twig_files_by_type(species_name)
    twig_usd_map = {}

    # Map Grove attribute names to twig file types
    # Grove uses: twig_long, twig_short, twig_upward, twig_dead
    type_mapping = {
        "twig_long": ["apical", "long", "end", "terminal"],
        "twig_short": ["lateral", "short", "side"],
        "twig_upward": ["upward", "up"],
        "twig_dead": ["dead", "fall", "winter"],
    }

    for grove_type, keywords in type_mapping.items():
        # Find first matching twig file
        for twig_type, twig_paths in twig_files_by_type.items():
            if any(kw in twig_type.lower() for kw in keywords):
                if twig_paths:
                    # Get first twig file and look for USD version (prefer USD over FBX)
                    twig_file = twig_paths[0]
                    # Prioritize USDA/USD over FBX for better compatibility
                    for ext in [".usda", ".usd"]:
                        usd_file = twig_file.with_suffix(ext)
                        if usd_file.exists():
                            twig_usd_map[grove_type] = usd_file
                            print(f"    Found {grove_type}: {usd_file.name}")
                            break
                    if grove_type not in twig_usd_map:
                        # Fallback to FBX if no USD found
                        fbx_file = twig_file.with_suffix(".fbx")
                        if fbx_file.exists():
                            twig_usd_map[grove_type] = fbx_file
                            print(
                                f"    Found {grove_type}: {fbx_file.name} (FBX fallback)"
                            )
                    break

    # Add fallback mappings for missing twig types
    # If twig_upward not found, use twig_short (upward twigs are similar to lateral)
    if "twig_upward" not in twig_usd_map and "twig_short" in twig_usd_map:
        twig_usd_map["twig_upward"] = twig_usd_map["twig_short"]
        print(f"    Using twig_short for twig_upward (no upward-specific twig)")

    # If twig_dead not found, use twig_short (dead twigs similar to lateral)
    if "twig_dead" not in twig_usd_map and "twig_short" in twig_usd_map:
        twig_usd_map["twig_dead"] = twig_usd_map["twig_short"]
        print(f"    Using twig_short for twig_dead (no dead-specific twig)")

    return twig_usd_map


def bundle_twigs_for_species(
    species_name: str,
    output_dir: Path,
    formats: List[str] = ["fbx", "usda"],
    config: Optional[Any] = None,
) -> Dict[str, List[Path]]:
    """Bundle twig files for a species to output directory.

    Copies relevant twig meshes (FBX/USD) to species output folder
    for easier asset management in Unreal Engine.

    Args:
        species_name: Name of tree species
        output_dir: Output directory for this species
        formats: Export formats to copy ('fbx', 'usd', 'usda')
        config: GrowPy configuration

    Returns:
        Dict with 'twig_files' and 'manifest' paths
    """
    if config is None:
        config = get_config()

    import shutil

    results = {"twig_files": [], "manifest": None}

    try:
        # Get twig files for this species
        twig_dir = output_dir / "twigs"
        twig_dir.mkdir(parents=True, exist_ok=True)

        # Get available twig USD map (already resolved to actual files)
        twig_usd_map = get_twig_usd_map_for_species(species_name, config)

        if not twig_usd_map:
            print(f"  No twig files found for {species_name}")
            return results

        twig_manifest = {"species": species_name, "twig_types": {}, "total_twigs": 0}

        # Copy each twig file in the map
        for twig_type, source_file in twig_usd_map.items():
            if not source_file.exists():
                continue

            twig_manifest["twig_types"][twig_type] = []

            # Copy the file
            dest_file = twig_dir / source_file.name
            shutil.copy2(source_file, dest_file)
            results["twig_files"].append(dest_file)
            twig_manifest["twig_types"][twig_type].append(dest_file.name)
            twig_manifest["total_twigs"] += 1

            # Also copy textures if they exist
            texture_dir = source_file.parent / "textures"
            if texture_dir.exists():
                dest_texture_dir = twig_dir / "textures"
                dest_texture_dir.mkdir(exist_ok=True)
                for texture_file in texture_dir.glob("*"):
                    if texture_file.is_file():
                        shutil.copy2(texture_file, dest_texture_dir / texture_file.name)

        # Save twig manifest
        if twig_manifest["total_twigs"] > 0:
            manifest_path = twig_dir / "twig_manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(twig_manifest, f, indent=2)
            results["manifest"] = manifest_path

    except Exception as e:
        print(f"Failed to bundle twigs for {species_name}: {e}")

    return results
