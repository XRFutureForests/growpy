"""Export for Grove tree models optimized for Unreal Engine 5 Nanite."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import bpy BEFORE any other Grove-related modules to avoid DLL conflicts
try:
    import bpy

    # Expose Blender's bundled VFX libraries (USD/pxr, MaterialX, etc.)
    # This allows importing pxr without DLL conflicts (Blender 4.4+)
    bpy.utils.expose_bundled_modules()

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

    Based on official UE Nanite documentation:
    https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine

    Key Requirements:
    - Triangles only (no quads/ngons) - handled by Grove's model.triangulate()
    - Vertex-to-triangle ratio should be <2:1 (shared vertices, not faceted)
    - Supports multiple UVs and vertex colors
    - Materials must be Opaque or Masked blend modes
    - No degenerate geometry (zero-area faces)
    - Tangents are derived implicitly (not stored)

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
        # Triangle count check
        # Nanite handles millions of triangles, but check for reasonable counts
        triangle_count = len(mesh.polygons)
        validation["stats"]["triangle_count"] = triangle_count
        vertex_count = len(mesh.vertices)
        validation["stats"]["vertex_count"] = vertex_count

        # Vertex-to-triangle ratio check (should be <2:1 for optimal performance)
        # Ratio >2:1 indicates faceted normals or poor vertex sharing
        if vertex_count > 0 and triangle_count > 0:
            vertex_ratio = vertex_count / triangle_count
            validation["stats"]["vertex_to_triangle_ratio"] = vertex_ratio

            if vertex_ratio > 2.0:
                validation["warnings"].append(
                    f"High vertex-to-triangle ratio ({vertex_ratio:.2f}:1). "
                    "Ratio >2:1 suggests faceted normals or poor vertex sharing. "
                    "Ideal ratio is <1:1 for shared vertices."
                )
            elif vertex_ratio > 2.5:
                validation["warnings"].append(
                    f"Very high vertex-to-triangle ratio ({vertex_ratio:.2f}:1). "
                    "Ratio approaching 3:1 means mesh is completely faceted. "
                    "This significantly increases data size and rendering cost."
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

        # Configure model for optimal export compatibility
        try:
            # Set up-axis to Z for Blender/Unreal compatibility
            model.set_up_axis("Z")
            print("  Set model up-axis to Z (Blender/Unreal compatible)")

            # Set counter-clockwise winding for standard compatibility
            model.set_winding_order("COUNTER_CLOCKWISE")
            print("  Set counter-clockwise winding order")
        except Exception as e:
            print(f"  Warning: Could not configure model orientation: {e}")

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
            # Apply UVs as provided by Grove without modification
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv_index = loop_index * 2
                    if uv_index + 1 < len(uvs):
                        u = uvs[uv_index]
                        v = uvs[uv_index + 1]
                        uv_layer[loop_index].uv = (u, v)

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
                # Note: Don't store grove reference on skeleton - it's a Rust object
                armature_obj = _add_skeleton_to_object(
                    obj, skeletons[0], species_name, grove, model
                )

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
        # CRITICAL: export_animation=True required for skeletal meshes even with bind pose
        # Without it, Blender won't create SkelAnimation prim that Unreal needs
        export_params = {
            "filepath": str(output_path),
            "selected_objects_only": True,
            "export_animation": (include_skeleton and not export_skeleton_separately),
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

        print(f"[OK] Exported USD with Nanite compatibility for {species_name}")
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

        # Reference Unreal schema for Nanite Assembly API schemas
        # This ensures proper schema definitions for Unreal Engine import
        schema_path = (
            Path(__file__).parent.parent.parent.parent
            / "data"
            / "unreal_schema"
            / "generatedSchema.usda"
        )
        if schema_path.exists():
            stage.GetRootLayer().subLayerPaths.append(str(schema_path.resolve()))
        else:
            print(f"  Warning: Unreal schema not found at {schema_path}")
            print(f"  Nanite Assembly may not import correctly in Unreal Engine")

        # Set stage metadata (Z-up, meters)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

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


def _calculate_vertex_weights(
    model: Any,
    skeleton: Any,
    vertices: List[Tuple[float, float, float]],
    faces: List[List[int]],
    grove: Any = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.25,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> Tuple[List[List[int]], List[List[float]]]:
    """Calculate proper vertex weights for skeletal animation using Grove's bone IDs.

    Uses Grove's tag_bone_id() system for direct bone assignment - the fastest
    and most accurate method. All fallback methods have been removed.

    Args:
        model: Grove model with bone_id attribute
        skeleton: Grove skeleton with poly_lines and points
        vertices: List of vertex positions [(x,y,z), ...]
        faces: List of face vertex indices [[v1,v2,v3], ...]
        grove: Grove instance for bone tagging (required)
        skeleton_length: Bone length multiplier (default: 1.0, higher=longer bones)
        skeleton_reduce: Bone reduction factor (default: 0.25, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Whether bones are connected (default: True)

    Returns:
        (joint_indices, joint_weights) where:
        - joint_indices[vertex_idx] = [bone_idx1, bone_idx2, ...]
        - joint_weights[vertex_idx] = [weight1, weight2, ...]
    """
    num_vertices = len(vertices)

    # Initialize: all vertices start with root bone
    vertex_to_joints = [[0] for _ in range(num_vertices)]
    vertex_to_weights = [[1.0] for _ in range(num_vertices)]

    # Use Grove's optimized bone tagging system
    if grove is None or not hasattr(grove, "tag_bone_id"):
        print("  Warning: Grove bone tagging not available, using root-only weights")
        return vertex_to_joints, vertex_to_weights

    try:
        import time

        print("  Using Grove's bone tagging system...")
        print(
            f"    Skeleton params: length={skeleton_length}, reduce={skeleton_reduce}, bias={skeleton_bias}, connected={skeleton_connected}"
        )

        # Use Grove's bone tagging with configurable parameters
        # length: Bone length multiplier (higher = longer/merged bones)
        # reduce: Bone reduction factor (higher = fewer bones)
        # bias: Weight bias (0-1 range)
        # connected: Whether bones are connected
        t0 = time.time()
        bones = grove.tag_bone_id(
            skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
        )
        t1 = time.time()
        print(f"      [TIME]  grove.tag_bone_id(): {t1-t0:.2f}s")

        if not bones or not hasattr(model, "point_attribute_bone_id"):
            print("  Warning: Grove bone tagging failed, using root-only weights")
            return vertex_to_joints, vertex_to_weights

        bone_ids = model.point_attribute_bone_id

        if len(bone_ids) != num_vertices:
            print(
                f"  Warning: Bone ID count mismatch ({len(bone_ids)} vs {num_vertices}), using root-only weights"
            )
            return vertex_to_joints, vertex_to_weights

        # Direct vertex-to-bone mapping from Grove
        for vert_idx, bone_id in enumerate(bone_ids):
            if bone_id >= 0 and bone_id < len(bones):
                vertex_to_joints[vert_idx] = [bone_id]
                vertex_to_weights[vert_idx] = [1.0]

        print(
            f"  [OK] Grove bone assignment complete: {num_vertices} vertices, {len(bones)} bones"
        )
        return vertex_to_joints, vertex_to_weights

    except Exception as e:
        print(f"  Error in Grove bone tagging: {e}")
        print("  Using root-only weights as fallback")
        return vertex_to_joints, vertex_to_weights


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

    Uses Grove's tag_bone_id() to identify which bones are actually needed,
    then creates only those bones to avoid creating 30K+ unnecessary bones.

    Args:
        obj: Blender mesh object
        skeleton: Grove skeleton data
        species_name: Name of the tree species
        grove: Grove instance for weight calculation
        model: Grove model with face/vertex data (required for weights)
        skeleton_length: Bone length multiplier (default: 1.0, higher=longer bones)
        skeleton_reduce: Bone reduction factor (default: 0.25, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Whether bones are connected (default: True)

    Returns:
        The armature object created
    """
    import time

    try:
        # First, determine which bones are actually used by Grove's tagging system
        # This avoids creating 30K+ bones when only ~32 are needed
        vertices = [(v.co.x, v.co.y, v.co.z) for v in obj.data.vertices]
        faces = [[v for v in poly.vertices] for poly in obj.data.polygons]

        t_weight_start = time.time()
        vertex_to_joints, vertex_to_weights = _calculate_vertex_weights(
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
        bones_map = {}  # bone_index -> bone object
        point_to_bone = {}  # point_index -> bone (for hierarchy)

        # Create root bone at index 0
        root_bone = armature.edit_bones.new("Root")
        root_bone.head = (0, 0, 0)
        root_bone.tail = (0, 0, 0.1)  # Small offset for valid bone
        bone_names.append("Root")
        bones_map[0] = root_bone

        # Build mapping from bone index to poly_line segments
        # Grove's tag_bone_id returns indices that map to bones in skeleton
        bone_index = 1  # Start at 1 (Root is 0)
        for poly_line in poly_lines:
            if len(poly_line) < 2:
                continue

            previous_bone = None
            for j in range(len(poly_line) - 1):
                start_idx = poly_line[j]
                end_idx = poly_line[j + 1]

                if bone_index in used_bone_indices:
                    # This bone is actually used - create it
                    bone_name = f"bone_{bone_index}"
                    bone = armature.edit_bones.new(bone_name)
                    bone_names.append(bone_name)
                    bones_map[bone_index] = bone

                    if start_idx < len(points) and end_idx < len(points):
                        bone.head = points[start_idx]
                        bone.tail = points[end_idx]

                    # Set parent bone to maintain hierarchy
                    if j == 0:
                        # First bone in branch - check if it connects to another branch
                        if start_idx in point_to_bone:
                            bone.parent = point_to_bone[start_idx]
                        else:
                            bone.parent = root_bone
                    else:
                        # Subsequent bones parent to previous bone in chain
                        if previous_bone is not None:
                            bone.parent = previous_bone
                        else:
                            bone.parent = root_bone

                    # Track this bone's endpoint for child branches
                    point_to_bone[end_idx] = bone
                    previous_bone = bone
                else:
                    # Bone not used, but still need to track if it would connect branches
                    if j == 0 and start_idx in point_to_bone:
                        previous_bone = point_to_bone[start_idx]
                    else:
                        previous_bone = None

                bone_index += 1

        bpy.ops.object.mode_set(mode="OBJECT")
        t_bones = time.time()
        print(
            f"      [TIME]  Bone creation: {t_bones-t_weight_calc:.2f}s ({len(bone_names)} bones)"
        )

        # Parent mesh to armature for proper FBX skeletal mesh export
        obj.parent = armature_obj
        obj.parent_type = "OBJECT"

        # Add armature modifier for proper deformation
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

        print(f"    [OK] Applied weights for {len(vertices)} vertices to FBX skeleton")

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
    """DEPRECATED: This function is no longer needed.

    Grove's native USD export (gc.io.model_to_usda_string) already includes:
    1. Twig face attributes as PascalCase primvars (TwigDead, TwigUpward, TwigSide, TwigEnd)
    2. Z-up coordinate system (no Y-up conversion needed)

    This function was created when Grove exported Y-up USD without twig attributes,
    but recent versions now export complete Z-up USD natively.

    Kept for backward compatibility but should not be called in new code.

    Args:
        usd_path: Path to USD file to modify
        model: Grove model with face attributes
    """
    import warnings

    warnings.warn(
        "_add_grove_face_attributes_to_usd is deprecated - Grove now exports "
        "complete Z-up USD with twig primvars natively",
        DeprecationWarning,
        stacklevel=2,
    )
    return  # Early return - function is no-op now

    # Original implementation kept below for reference but never executed
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"Warning: Could not open USD stage at {usd_path}")
            return

        # Convert stage from Y-up to Z-up
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

        # Find mesh prim
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue

            mesh_usd = UsdGeom.Mesh(prim)
            primvars_api = UsdGeom.PrimvarsAPI(mesh_usd)

            # Transform mesh geometry from Y-up to Z-up
            # Get points and transform them
            points_attr = mesh_usd.GetPointsAttr()
            if points_attr:
                points = points_attr.Get()
                if points:
                    # Convert each point: (x, y, z) -> (x, -z, y)
                    transformed_points = [Gf.Vec3f(p[0], -p[2], p[1]) for p in points]
                    points_attr.Set(transformed_points)

            # Transform normals if they exist
            normals_attr = mesh_usd.GetNormalsAttr()
            if normals_attr and normals_attr.HasValue():
                normals = normals_attr.Get()
                if normals:
                    # Convert normals: (x, y, z) -> (x, -z, y)
                    transformed_normals = [Gf.Vec3f(n[0], -n[2], n[1]) for n in normals]
                    normals_attr.Set(transformed_normals)

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
                print(f"  [OK] Added twig face attributes to USD:")
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
        print(f"[OK] Added Blender attributes as USD primvars to {usd_path.name}")

    except Exception as e:
        print(f"Warning: Failed to add primvars to USD file: {e}")
        import traceback

        traceback.print_exc()


def _convert_mesh_yup_to_zup(usd_path: Path) -> bool:
    """DEPRECATED: Convert mesh vertices from Y-up (Grove) to Z-up (Unreal).

    This function is no longer needed when using usd_builder.build_tree_usd(),
    which accesses Grove API geometry directly in the correct coordinate system.

    Historical note: This was needed when using gc.io.model_to_usda_string()
    which exported in Y-up coordinates requiring transformation:
    (x, y, z)_grove → (x, -z, y)_usd

    Args:
        usd_path: Path to USD file with Y-up mesh

    Returns:
        bool: True if conversion succeeded

    Deprecated:
        Use usd_builder.build_tree_usd() instead of gc.io.model_to_usda_string()
    """
    try:
        from pxr import Gf, Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Set stage to Z-up
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

        # Find and convert mesh vertices
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                points_attr = mesh.GetPointsAttr()
                points = points_attr.Get()

                if points:
                    # Convert Y-up to Z-up: (x, y, z) → (x, -z, y)
                    converted_points = [Gf.Vec3f(p[0], -p[2], p[1]) for p in points]
                    points_attr.Set(converted_points)

        stage.Save()
        return True

    except Exception as e:
        print(f"  Warning: Could not convert mesh to Z-up: {e}")
        return False


def _add_materials_to_usd(
    usd_path: Path,
    grove: Any,
    species_name: str,
    config: Optional[Any] = None,
) -> Optional[dict]:
    """Add bark texture materials to USD file (without skeleton).

    This adds only materials/textures to a static mesh USD file.
    Use this for the base tree_only.usda (static mesh).
    Use _add_skeleton_and_materials_to_usd for skeletal mesh versions.

    Args:
        usd_path: Path to USD file to enhance
        grove: Grove instance (unused but kept for consistency)
        species_name: Species name for texture lookup
        config: GrowPy configuration

    Returns:
        Optional[dict]: Texture paths dict if found, None otherwise
    """
    try:
        from pxr import Sdf, Usd, UsdGeom, UsdShade

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"  Warning: Could not open USD stage at {usd_path}")
            return None

        # Find the tree mesh prim
        tree_mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                tree_mesh_prim = prim
                break

        if not tree_mesh_prim:
            print(f"  Warning: No mesh found in USD file")
            return None

        # Add bark texture material
        print(f"  Adding bark texture material...")
        textures = _find_bark_texture(species_name, config)

        if textures:
            # Create material at mesh parent level
            material_path = (
                tree_mesh_prim.GetPath().GetParentPath().AppendChild("BarkMaterial")
            )
            material = UsdShade.Material.Define(stage, material_path)

            # Create shader
            shader = UsdShade.Shader.Define(stage, material_path.AppendChild("Shader"))
            shader.CreateIdAttr("UsdPreviewSurface")

            # Create UV reader for texture coordinates
            uv_reader_path = material_path.AppendChild("UVReader")
            uv_reader = UsdShade.Shader.Define(stage, uv_reader_path)
            uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
            uv_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
            uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

            # Diffuse texture
            if "diffuse" in textures:
                diffuse_tex_path = material_path.AppendChild("DiffuseTexture")
                diffuse_tex = UsdShade.Shader.Define(stage, diffuse_tex_path)
                diffuse_tex.CreateIdAttr("UsdUVTexture")
                # Use relative path from USD file location to textures subdirectory
                relative_path = f"./textures/{textures['diffuse'].name}"
                diffuse_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    relative_path
                )
                # Connect UV coordinates
                diffuse_tex.CreateInput(
                    "st", Sdf.ValueTypeNames.Float2
                ).ConnectToSource(
                    uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
                )
                diffuse_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect to shader
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(
                    diffuse_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                )
                print(f"    [OK] Added diffuse texture: {textures['diffuse'].name}")

            # Normal map
            if "normal" in textures:
                normal_tex_path = material_path.AppendChild("NormalTexture")
                normal_tex = UsdShade.Shader.Define(stage, normal_tex_path)
                normal_tex.CreateIdAttr("UsdUVTexture")
                # Use relative path from USD file location to textures subdirectory
                relative_path = f"./textures/{textures['normal'].name}"
                normal_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    relative_path
                )
                # Connect UV coordinates
                normal_tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                    uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
                )
                normal_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect to shader
                shader.CreateInput(
                    "normal", Sdf.ValueTypeNames.Normal3f
                ).ConnectToSource(
                    normal_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                )
                print(f"    [OK] Added normal map: {textures['normal'].name}")

            # Set material properties for bark
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

            # Create surface output
            shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            material.CreateSurfaceOutput().ConnectToSource(
                shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            )

            # Bind material to mesh
            binding_api = UsdShade.MaterialBindingAPI.Apply(tree_mesh_prim)
            binding_api.Bind(material)

            print(f"    [OK] Bound material to mesh")
        else:
            print(f"    [INFO]  No bark textures found for {species_name}")

        # Save changes
        stage.Save()
        return textures

    except ImportError:
        print("  ERROR: USD Python (pxr) not available")
        return None
    except Exception as e:
        print(f"  Failed to add materials to USD: {e}")
        import traceback

        traceback.print_exc()
        return None


def _add_skeleton_only_to_usd(
    usd_path: Path,
    grove: Any,
    species_name: str,
    model: Optional[Any] = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.1,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add ONLY skeleton to USD file (materials should already be present).

    This is used when creating skeletal tree from static tree that already has materials.
    Avoids duplicate material addition and file corruption.

    Args:
        usd_path: Path to USD file (should already have materials)
        grove: Grove instance for skeleton
        species_name: Species name
        model: Optional model for weight calculation
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.1, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Connected bone hierarchy (default: True)

    Returns:
        bool: True if skeleton added successfully
    """
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Find tree mesh and parent
        tree_mesh_prim = None
        tree_xform_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                tree_mesh_prim = prim
                tree_xform_prim = stage.GetPrimAtPath(prim.GetPath().GetParentPath())
                break

        if not tree_mesh_prim or not tree_xform_prim:
            return False

        mesh = UsdGeom.Mesh(tree_mesh_prim)
        original_mesh_path = tree_mesh_prim.GetPath()
        original_xform_path = tree_xform_prim.GetPath()

        # Build skeleton
        print(f"  Adding skeleton to USD (UE5.7 SkelRoot structure)...")

        # CRITICAL: Use grove.tag_bone_id() to get actual bone segments with head/tail positions
        # This is THE CORRECT WAY per Blender addon reference implementation
        # tag_bone_id() returns: [(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]
        # Unlike skeleton.points/poly_lines which only give connectivity, this gives actual bone geometry
        bones_info = grove.tag_bone_id(
            skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
        )

        if not bones_info or len(bones_info) == 0:
            print(f"    Warning: No bone data from tag_bone_id()")
            return False

        print(
            f"    [OK] Grove returned {len(bones_info)} bones with head/tail positions"
        )

        # Still need skeletons for metadata, but we'll use bones_info for geometry
        skeletons = grove.build_skeletons()
        if not skeletons or len(skeletons) == 0:
            print(f"    Warning: No skeleton data available")
            return False

        skeleton_data = skeletons[0]

        # Use Grove's bone tagging to determine which bones are needed (reduces 87K+ points to ~100-500 bones)
        # NOTE: tag_bone_id() should have been called BEFORE building the model
        # If model has bone_id attribute, use it for bone reduction
        # Otherwise, create all joints (no reduction)

        used_bone_indices = None
        if model is not None and hasattr(model, "point_attribute_bone_id"):
            bone_ids = model.point_attribute_bone_id
            used_bone_indices = set(bone_ids)
            print(
                f"    [OK] Using bone IDs from model: {len(used_bone_indices)} unique bones"
            )
        else:
            # Fallback: Try to tag bones now (but this won't work if model was already built)
            if model is not None and hasattr(grove, "tag_bone_id"):
                print(
                    f"    Warning: Model missing bone_id attribute - attempting to tag bones now"
                )
                print(
                    f"    (This may not work correctly - bones should be tagged BEFORE building model)"
                )
                try:
                    bones = grove.tag_bone_id(
                        skeleton_length,
                        skeleton_reduce,
                        skeleton_bias,
                        skeleton_connected,
                    )
                    if bones and hasattr(model, "point_attribute_bone_id"):
                        bone_ids = model.point_attribute_bone_id
                        used_bone_indices = set(bone_ids)
                        print(
                            f"    [OK] Bone reduction: {len(bones)} bones needed (from {len(skeleton_data.points)} skeleton points)"
                        )
                    else:
                        print(
                            "    Warning: Grove bone tagging returned no bones or bone_id attribute missing"
                        )
                except Exception as e:
                    print(
                        f"    Warning: Bone tagging failed ({e}), creating all joints"
                    )

        if used_bone_indices is None:
            print(
                f"    Creating all {len(skeleton_data.points)} joints (no bone reduction)"
            )

        # Create SkelRoot
        skel_root_path = original_xform_path.AppendChild("SkelRoot")
        skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)
        skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())

        # Create skeleton
        skel_path = skel_root_path.AppendChild("Skeleton")
        skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

        # Apply Unreal Engine schemas for Control Rig support
        # ControlRigAPI enables Control Rig integration in Unreal Engine
        skel_api_schemas = Sdf.TokenListOp()
        skel_api_schemas.prependedItems = ["ControlRigAPI"]
        skel_prim.GetPrim().SetMetadata("apiSchemas", skel_api_schemas)

        # Build joint hierarchy using Grove's bone tagging for reduction
        points = skeleton_data.points
        poly_lines = skeleton_data.poly_lines

        joints = []
        joint_parents = []
        bind_transforms = []
        rest_transforms = []

        joints.append("Root")
        joint_parents.append(-1)
        root_transform = Gf.Matrix4d().SetIdentity()
        bind_transforms.append(root_transform)
        rest_transforms.append(root_transform)

        joint_positions = {}
        joint_positions[0] = Gf.Vec3d(0, 0, 0)
        point_to_joint = {}
        bones_map = {0: 0}  # bone_index -> joint_index mapping
        joint_path_names = {}  # Maps joint index to hierarchical path name
        joint_path_names[0] = "Root"

        # Create joints only for used bones (or all if no reduction)
        bone_index = 1
        for line in poly_lines:
            if len(line) < 2:
                continue

            parent_joint_idx = 0
            previous_bone = None
            parent_path = "Root"

            for j in range(len(line) - 1):
                start_idx = line[j]
                end_idx = line[j + 1]

                # Check if this bone should be created
                should_create = (used_bone_indices is None) or (
                    bone_index in used_bone_indices
                )

                if should_create:
                    # Use hierarchical joint names that encode parent-child relationships
                    if j == 0:
                        # First bone in branch
                        if start_idx in point_to_joint:
                            # Child of parent branch bone
                            parent_joint_idx = point_to_joint[start_idx]
                            parent_path = joint_path_names[parent_joint_idx]
                        else:
                            # Root-level branch
                            parent_joint_idx = 0
                            parent_path = "Root"
                        joint_name = f"{parent_path}/bone_{bone_index}"
                    else:
                        # Subsequent bone in same branch - child of previous bone
                        joint_name = f"{parent_path}/bone_{bone_index}"

                    joint_idx = len(joints)
                    joints.append(joint_name)
                    bones_map[bone_index] = joint_idx
                    joint_path_names[joint_idx] = joint_name
                    parent_path = (
                        joint_name  # This becomes parent for next bone in chain
                    )

                    if start_idx < len(points) and end_idx < len(points):
                        start_pos = Gf.Vec3d(*points[start_idx])
                        end_pos = Gf.Vec3d(*points[end_idx])

                        # Parent already determined above when building hierarchical name
                        joint_parents.append(parent_joint_idx)

                        # Calculate transform relative to parent
                        # For the first bone in a branch (j == 0), parent is either Root or another bone
                        # For subsequent bones (j > 0), parent is the previous bone in the chain
                        parent_pos = joint_positions.get(
                            parent_joint_idx, Gf.Vec3d(0, 0, 0)
                        )
                        relative_pos = start_pos - parent_pos

                        local_transform = Gf.Matrix4d().SetIdentity()
                        local_transform.SetTranslateOnly(relative_pos)
                        bind_transforms.append(local_transform)
                        rest_transforms.append(local_transform)

                        # CRITICAL: Track END position so next bone in chain starts where this one ends
                        # This creates connected bone chains instead of all bones starting from parent
                        joint_positions[joint_idx] = end_pos
                        point_to_joint[end_idx] = joint_idx
                        previous_bone = bone_index
                        parent_joint_idx = (
                            joint_idx  # Next bone in chain will be child of this one
                        )
                else:
                    # Bone not used - don't update previous_bone tracking
                    # Keep previous_bone pointing to the last CREATED bone
                    # Only update if this is first bone in branch and connects to existing joint
                    if j == 0 and start_idx in point_to_joint:
                        # Find the bone_index that created this joint
                        connecting_joint_idx = point_to_joint[start_idx]
                        parent_path = joint_path_names[connecting_joint_idx]
                        parent_joint_idx = connecting_joint_idx
                        # Search bones_map to find which bone_index created this joint
                        for bidx, jidx in bones_map.items():
                            if jidx == connecting_joint_idx:
                                previous_bone = bidx
                                break

                bone_index += 1

        # Set skeleton attributes
        skel_prim.CreateJointsAttr().Set(Vt.TokenArray(joints))
        skel_prim.CreateBindTransformsAttr().Set(Vt.Matrix4dArray(bind_transforms))
        skel_prim.CreateRestTransformsAttr().Set(Vt.Matrix4dArray(rest_transforms))

        # Create SkelAnimation
        anim_path = skel_root_path.AppendChild("Animation")
        anim = UsdSkel.Animation.Define(stage, anim_path)
        anim.CreateJointsAttr().Set(Vt.TokenArray(joints))
        anim.CreateTranslationsAttr().Set(
            Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)] * len(joints))
        )
        anim.CreateRotationsAttr().Set(
            Vt.QuatfArray([Gf.Quatf(1, 0, 0, 0)] * len(joints))
        )
        anim.CreateScalesAttr().Set(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)] * len(joints)))

        skel_prim.GetPrim().GetRelationship("skel:animationSource").SetTargets(
            [anim_path]
        )

        print(f"    [OK] Created SkelRoot with skeleton ({len(joints)} joints)")
        print(
            f"    [OK] Created SkelAnimation ({len(joints)} joints, bind pose for UE skeletal mesh recognition)"
        )

        # Move mesh under SkelRoot
        new_mesh_path = skel_root_path.AppendChild("Mesh")
        mesh_prim_copy = stage.OverridePrim(new_mesh_path)
        Sdf.CopySpec(
            stage.GetRootLayer(),
            original_mesh_path,
            stage.GetRootLayer(),
            new_mesh_path,
        )

        tree_mesh_prim = stage.GetPrimAtPath(new_mesh_path)
        mesh = UsdGeom.Mesh(tree_mesh_prim)

        # Bind mesh to skeleton
        mesh_binding_api = UsdSkel.BindingAPI.Apply(tree_mesh_prim)
        mesh_binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Calculate vertex weights
        print(f"  Calculating vertex weights for {species_name}...")

        points_attr = mesh.GetPointsAttr().Get()
        num_vertices = len(points_attr)
        vertices = [(p[0], p[1], p[2]) for p in points_attr]

        face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

        faces = []
        idx = 0
        for count in face_vertex_counts:
            face = [face_vertex_indices[idx + i] for i in range(count)]
            faces.append(face)
            idx += count

        if model is not None:
            joint_indices, joint_weights = _calculate_vertex_weights(
                model,
                skeleton_data,
                vertices,
                faces,
                grove,
                skeleton_length,
                skeleton_reduce,
                skeleton_bias,
                skeleton_connected,
            )
            print(f"    [OK] Calculated weights for {num_vertices} vertices")
        else:
            joint_indices = [[0] for _ in range(num_vertices)]
            joint_weights = [[1.0] for _ in range(num_vertices)]

        max_influences = max(len(indices) for indices in joint_indices)

        joint_indices_flat = []
        joint_weights_flat = []
        for vert_indices, vert_weights in zip(joint_indices, joint_weights):
            padded_indices = list(vert_indices) + [0] * (
                max_influences - len(vert_indices)
            )
            padded_weights = list(vert_weights) + [0.0] * (
                max_influences - len(vert_weights)
            )
            joint_indices_flat.extend(padded_indices[:max_influences])
            joint_weights_flat.extend(padded_weights[:max_influences])

        mesh_binding_api.CreateJointIndicesPrimvar(False, max_influences).Set(
            Vt.IntArray(joint_indices_flat)
        )
        mesh_binding_api.CreateJointWeightsPrimvar(False, max_influences).Set(
            Vt.FloatArray(joint_weights_flat)
        )

        # Remove original mesh
        stage.RemovePrim(original_mesh_path)

        # Keep root as default prim
        root_prim = stage.GetPrimAtPath(
            "/" + original_xform_path.pathString.split("/")[1]
        )
        if root_prim:
            stage.SetDefaultPrim(root_prim)
            print(
                f"    [OK] Set default prim to {root_prim.GetPath()} (preserves material access)"
            )

        print(f"    [OK] Bound mesh to skeleton with joint influences")
        print(f"    [OK] Hierarchy: SkelRoot > [Skeleton + Mesh]")

        stage.Save()
        return True

    except Exception as e:
        print(f"    Error adding skeleton: {e}")
        import traceback

        traceback.print_exc()
        return False


def _add_skeleton_and_materials_to_usd(
    usd_path: Path,
    grove: Any,
    species_name: str,
    config: Optional[Any] = None,
    model: Optional[Any] = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.25,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> Optional[dict]:
    """Add skeleton and materials to Grove's native USD export.

    Enhances Grove's basic USD export with:
    1. UsdSkel skeleton hierarchy for animation (wrapped in SkelRoot for UE5.7)
    2. Bark texture materials (diffuse + normal)
    3. Proper skeletal mesh binding

    Creates proper UsdSkel structure for Unreal Engine 5.7:
    - SkelRoot (container with SkelBindingAPI)
      - Skeleton (joint hierarchy)
      - Mesh (skinned geometry with joint influences)

    Args:
        usd_path: Path to USD file to enhance
        grove: Grove instance (for building skeleton)
        species_name: Species name for texture lookup
        config: GrowPy configuration
        model: Grove model (for bone tagging info)
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.25, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Whether bones are connected (default: True)

    Returns:
        Optional[dict]: Texture paths dict if found, None otherwise
    """
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"  Warning: Could not open USD stage at {usd_path}")
            return None

        # Find the tree mesh prim and its parent Xform
        tree_mesh_prim = None
        tree_xform_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                tree_mesh_prim = prim
                tree_xform_prim = stage.GetPrimAtPath(prim.GetPath().GetParentPath())
                break

        if not tree_mesh_prim or not tree_xform_prim:
            print(f"  Warning: No mesh or parent xform found in USD file")
            return None

        mesh = UsdGeom.Mesh(tree_mesh_prim)

        # Get original mesh path and parent path
        original_mesh_path = tree_mesh_prim.GetPath()
        original_xform_path = tree_xform_prim.GetPath()

        # 1. Add skeleton if available - wrapped in SkelRoot for UE5.7
        print(f"  Adding skeleton to USD (UE5.7 SkelRoot structure)...")
        print(
            f"    Skeleton params: length={skeleton_length}, reduce={skeleton_reduce}, bias={skeleton_bias}, connected={skeleton_connected}"
        )

        # CRITICAL: Call tag_bone_id() BEFORE build_skeletons() to configure bone generation
        # This step tags the tree structure with bone IDs using the specified parameters
        # NOTE: If model was already built with bone tagging, this won't affect the existing model
        # but will ensure the skeleton matches the bone structure
        if hasattr(grove, "tag_bone_id"):
            print(f"    Configuring skeleton with tag_bone_id()...")
            bones_info = grove.tag_bone_id(
                skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
            )
            print(f"    [OK] Tagged {len(bones_info) if bones_info else 0} bones")

        skeletons = grove.build_skeletons()
        if skeletons and len(skeletons) > 0:
            skeleton_data = skeletons[0]
            # Note: Don't store grove reference on skeleton - it's a Rust object

            # Create SkelRoot as parent container (required for UE5.7)
            # SkelRoot wraps both the Skeleton and the skinned Mesh
            skel_root_path = original_xform_path.AppendChild("SkelRoot")
            skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)

            # Apply SkelBindingAPI to the SkelRoot (UE5.7 requirement)
            # This is CRITICAL for Unreal to recognize this as a skeletal mesh
            skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())

            # Create skeleton prim inside SkelRoot
            skel_path = skel_root_path.AppendChild("Skeleton")
            skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

            # Apply Unreal Engine schemas for Control Rig support
            # ControlRigAPI enables Control Rig integration in Unreal Engine
            skel_api_schemas = Sdf.TokenListOp()
            skel_api_schemas.prependedItems = ["ControlRigAPI"]
            skel_prim.GetPrim().SetMetadata("apiSchemas", skel_api_schemas)

            # Convert Grove skeleton to USD skeleton
            # Grove skeleton has: points, poly_lines, location
            points = skeleton_data.points
            poly_lines = skeleton_data.poly_lines

            # Build joint hierarchy and topology
            joints = []
            joint_parents = []
            bind_transforms = []
            rest_transforms = []

            # Root joint at skeleton location
            joints.append("Root")
            joint_parents.append(-1)
            root_transform = Gf.Matrix4d().SetIdentity()
            bind_transforms.append(root_transform)
            rest_transforms.append(root_transform)

            # Track joint positions for calculating relative transforms
            joint_positions = {}
            joint_positions[0] = Gf.Vec3d(0, 0, 0)  # Root at origin

            # Track bone connections across branches
            point_to_joint = {}
            joint_path_names = {}  # Maps joint index to hierarchical path name

            # Create bones from poly_lines with hierarchical naming
            for i, poly_line in enumerate(poly_lines):
                if len(poly_line) < 2:
                    continue

                prev_joint_idx = None  # Will be determined based on connection
                parent_path = None  # Parent joint's hierarchical path

                for j in range(len(poly_line) - 1):
                    current_joint_idx = len(joints)

                    # Determine parent joint and build hierarchical path
                    if j == 0:
                        # First bone in branch
                        start_idx = poly_line[j]
                        if start_idx in point_to_joint:
                            # Connect to parent branch at shared point
                            prev_joint_idx = point_to_joint[start_idx]
                            parent_path = joint_path_names[prev_joint_idx]
                            # Child of parent branch bone
                            joint_name = f"{parent_path}/Branch_{i}_Bone_{j}"
                        else:
                            # No parent branch connection, parent to root
                            prev_joint_idx = 0
                            parent_path = "Root"
                            # Direct child of root
                            joint_name = f"Root/Branch_{i}_Bone_{j}"
                    else:
                        # Subsequent bone in same branch - child of previous bone
                        joint_name = f"{parent_path}/Branch_{i}_Bone_{j}"

                    joints.append(joint_name)
                    joint_path_names[current_joint_idx] = joint_name
                    parent_path = (
                        joint_name  # This becomes parent for next bone in chain
                    )

                    # Parent is previous joint in the chain
                    joint_parents.append(prev_joint_idx)

                    # Calculate bone transform RELATIVE to parent
                    start_idx = poly_line[j]
                    end_idx = poly_line[j + 1]

                    # Track this joint at its end point for branch connections
                    point_to_joint[end_idx] = current_joint_idx

                    if start_idx < len(points) and end_idx < len(points):
                        start_pos = Gf.Vec3d(*points[start_idx])
                        end_pos = Gf.Vec3d(*points[end_idx])

                        # Get parent position
                        parent_pos = joint_positions[prev_joint_idx]

                        # Calculate relative offset from parent to this bone's start
                        relative_offset = start_pos - parent_pos

                        # Create transform matrix with relative translation
                        transform = Gf.Matrix4d().SetIdentity()
                        transform.SetTranslateOnly(relative_offset)

                        bind_transforms.append(transform)
                        rest_transforms.append(transform)

                        # Store this joint's position for child bones
                        joint_positions[current_joint_idx] = start_pos

                    prev_joint_idx = current_joint_idx

            # Set skeleton attributes
            # Joint hierarchy is encoded in the joint names themselves (paths)
            skel_prim.CreateJointsAttr(
                Vt.TokenArray([Sdf.Path(j).pathString for j in joints])
            )
            skel_prim.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
            skel_prim.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

            print(f"    [OK] Created SkelRoot with skeleton ({len(joints)} joints)")

            # Create SkelAnimation for bind pose (CRITICAL for Unreal skeletal mesh recognition)
            # Even without animation, Unreal needs this to recognize as skeletal mesh
            anim_path = skel_root_path.AppendChild("Animation")
            anim_prim = UsdSkel.Animation.Define(stage, anim_path)

            # Set animation joints (same as skeleton)
            anim_prim.CreateJointsAttr(
                Vt.TokenArray([Sdf.Path(j).pathString for j in joints])
            )

            # Set bind pose transforms (identity for each joint)
            # USD requires these arrays to match the number of joints
            # Identity transforms = no animation, use bind pose from skeleton
            num_joints = len(joints)
            identity_translations = Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)] * num_joints)
            identity_rotations = Vt.QuatfArray(
                [Gf.Quatf(1, 0, 0, 0)] * num_joints
            )  # w, x, y, z
            identity_scales = Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)] * num_joints)

            anim_prim.CreateTranslationsAttr(identity_translations)
            anim_prim.CreateRotationsAttr(identity_rotations)
            anim_prim.CreateScalesAttr(identity_scales)

            # Bind animation to skeleton
            skel_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())
            skel_binding_api.CreateAnimationSourceRel().SetTargets([anim_path])

            print(
                f"    [OK] Created SkelAnimation ({num_joints} joints, bind pose for UE skeletal mesh recognition)"
            )

            # Move mesh inside SkelRoot and bind to skeleton
            # This creates the proper hierarchy: SkelRoot/Skeleton + SkelRoot/Mesh
            mesh_in_skel_path = skel_root_path.AppendChild("Mesh")

            # Copy mesh to new location inside SkelRoot
            Sdf.CopySpec(
                stage.GetRootLayer(),
                original_mesh_path,
                stage.GetRootLayer(),
                mesh_in_skel_path,
            )

            # Get the moved mesh prim
            tree_mesh_prim = stage.GetPrimAtPath(mesh_in_skel_path)
            mesh = UsdGeom.Mesh(tree_mesh_prim)

            # Bind moved mesh to skeleton
            mesh_binding_api = UsdSkel.BindingAPI.Apply(tree_mesh_prim)
            mesh_binding_api.CreateSkeletonRel().SetTargets([skel_path])

            # Calculate proper vertex weights based on branch assignment and proximity
            print(f"    Calculating vertex weights for {species_name}...")

            # Get mesh data
            points_attr = mesh.GetPointsAttr().Get()
            num_vertices = len(points_attr)
            vertices = [(p[0], p[1], p[2]) for p in points_attr]

            # Get face data from USD
            face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
            face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

            # Reconstruct faces
            faces = []
            idx = 0
            for count in face_vertex_counts:
                face = [face_vertex_indices[idx + i] for i in range(count)]
                faces.append(face)
                idx += count

            # Calculate weights if model is available
            if model is not None:
                joint_indices, joint_weights = _calculate_vertex_weights(
                    model, skeleton_data, vertices, faces
                )
                print(f"    [OK] Calculated weights for {num_vertices} vertices")
            else:
                # Fallback to root-only weights
                joint_indices = [[0] for _ in range(num_vertices)]
                joint_weights = [[1.0] for _ in range(num_vertices)]
                print(f"    Warning: No model provided, using root-only weights")

            # Use proper UsdSkel API for joint influences (critical for UE5 recognition)
            # CreateJointIndicesPrimvar and CreateJointWeightsPrimvar handle the
            # primvar setup correctly for skeletal mesh import
            max_influences = max(len(indices) for indices in joint_indices)

            # Flatten to single array with padding
            joint_indices_flat = []
            joint_weights_flat = []

            for vert_indices, vert_weights in zip(joint_indices, joint_weights):
                # Pad to max_influences with zeros
                padded_indices = list(vert_indices) + [0] * (
                    max_influences - len(vert_indices)
                )
                padded_weights = list(vert_weights) + [0.0] * (
                    max_influences - len(vert_weights)
                )
                joint_indices_flat.extend(padded_indices[:max_influences])
                joint_weights_flat.extend(padded_weights[:max_influences])

            # Use UsdSkel.BindingAPI methods (proper way to set skeletal weights)
            mesh_binding_api.CreateJointIndicesPrimvar(False, max_influences).Set(
                Vt.IntArray(joint_indices_flat)
            )
            mesh_binding_api.CreateJointWeightsPrimvar(False, max_influences).Set(
                Vt.FloatArray(joint_weights_flat)
            )

            # Remove original mesh outside SkelRoot (now duplicated inside)
            stage.RemovePrim(original_mesh_path)

            # CRITICAL: Keep /root (or tree parent) as default prim, NOT SkelRoot
            # This ensures materials in /root/_materials remain accessible in Unreal
            # Setting SkelRoot as default causes materials to be hidden
            root_prim = stage.GetPrimAtPath(
                "/" + original_xform_path.pathString.split("/")[1]
            )
            if root_prim:
                stage.SetDefaultPrim(root_prim)
                print(
                    f"    [OK] Set default prim to {root_prim.GetPath()} (preserves material access)"
                )

            print(f"    [OK] Bound mesh to skeleton with joint influences")
            print(f"    [OK] Hierarchy: SkelRoot > [Skeleton + Mesh]")

        # 2. Add bark texture material
        print(f"  Adding bark texture material...")
        textures = _find_bark_texture(species_name, config)

        if textures:
            # Create material
            material_path = (
                tree_mesh_prim.GetPath().GetParentPath().AppendChild("BarkMaterial")
            )
            material = UsdShade.Material.Define(stage, material_path)

            # Create shader
            shader = UsdShade.Shader.Define(stage, material_path.AppendChild("Shader"))
            shader.CreateIdAttr("UsdPreviewSurface")

            # Create UV reader for texture coordinates
            uv_reader_path = material_path.AppendChild("UVReader")
            uv_reader = UsdShade.Shader.Define(stage, uv_reader_path)
            uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
            uv_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
            uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

            # Diffuse texture
            if "diffuse" in textures:
                diffuse_tex_path = material_path.AppendChild("DiffuseTexture")
                diffuse_tex = UsdShade.Shader.Define(stage, diffuse_tex_path)
                diffuse_tex.CreateIdAttr("UsdUVTexture")
                # Use relative path from USD file location to textures subdirectory
                relative_path = f"./textures/{textures['diffuse'].name}"
                diffuse_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    relative_path
                )
                # Connect UV coordinates
                diffuse_tex.CreateInput(
                    "st", Sdf.ValueTypeNames.Float2
                ).ConnectToSource(
                    uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
                )
                diffuse_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect to shader
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(
                    diffuse_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                )
                print(f"    [OK] Added diffuse texture: {textures['diffuse'].name}")

            # Normal map
            if "normal" in textures:
                normal_tex_path = material_path.AppendChild("NormalTexture")
                normal_tex = UsdShade.Shader.Define(stage, normal_tex_path)
                normal_tex.CreateIdAttr("UsdUVTexture")
                # Use relative path from USD file location to textures subdirectory
                relative_path = f"./textures/{textures['normal'].name}"
                normal_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                    relative_path
                )
                # Connect UV coordinates
                normal_tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                    uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
                )
                normal_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                # Connect to shader
                shader.CreateInput(
                    "normal", Sdf.ValueTypeNames.Normal3f
                ).ConnectToSource(
                    normal_tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                )
                print(f"    [OK] Added normal map: {textures['normal'].name}")

            # Set material properties for bark
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

            # Create surface output
            shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            material.CreateSurfaceOutput().ConnectToSource(
                shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            )

            # Bind material to mesh
            binding_api = UsdShade.MaterialBindingAPI.Apply(tree_mesh_prim)
            binding_api.Bind(material)

            print(f"    [OK] Bound material to mesh")
        else:
            print(f"    [INFO]  No bark textures found for {species_name}")

        # Save changes
        stage.Save()
        return textures

    except ImportError:
        print("  ERROR: USD Python (pxr) not available")
        return None
    except Exception as e:
        print(f"  Failed to add skeleton/materials to USD: {e}")
        import traceback

        traceback.print_exc()
        return None


def _add_skeleton_to_twig_usd(usd_path: Path) -> bool:
    """Add a simple single-bone skeleton to a twig USD file.

    This makes the twig compatible with skeletal mesh Nanite Assemblies in Unreal.
    Creates a single bone at origin with the mesh bound to it.

    Args:
        usd_path: Path to twig USD file to modify

    Returns:
        bool: Success status
    """
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Find the mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            return False

        # Get mesh and parent
        mesh = UsdGeom.Mesh(mesh_prim)
        original_mesh_path = mesh_prim.GetPath()
        parent_path = original_mesh_path.GetParentPath()

        # Create SkelRoot at parent level
        skel_root_path = parent_path.AppendChild("SkelRoot")
        skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)

        # Create simple skeleton with single bone at origin
        skel_path = skel_root_path.AppendChild("Skeleton")
        skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

        # Define single joint at origin
        joints = ["Root"]
        skel_prim.CreateJointsAttr(joints)

        # Bind transforms (identity matrix at origin)
        bind_transforms = [Gf.Matrix4d().SetIdentity()]
        skel_prim.CreateBindTransformsAttr(bind_transforms)

        # Rest transforms (same as bind)
        skel_prim.CreateRestTransformsAttr(bind_transforms)

        # Create SkelAnimation for bind pose (CRITICAL for Unreal skeletal mesh recognition)
        # Even single-bone skeletons need this for UE to recognize as skeletal mesh
        anim_path = skel_root_path.AppendChild("Animation")
        anim_prim = UsdSkel.Animation.Define(stage, anim_path)

        # Set animation joints (single joint)
        anim_prim.CreateJointsAttr(joints)

        # Set identity transforms for single bone (matching number of joints)
        # USD requires these arrays to have proper dimensions
        anim_prim.CreateTranslationsAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)]))
        anim_prim.CreateRotationsAttr(
            Vt.QuatfArray([Gf.Quatf(1, 0, 0, 0)])
        )  # w, x, y, z (identity quaternion)
        anim_prim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)]))

        # Bind animation to skeleton
        skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())
        skel_root_binding_api.CreateAnimationSourceRel().SetTargets([anim_path])

        print(f"    -> Added SkelAnimation (identity bind pose) to twig")

        # Create new mesh prim inside SkelRoot
        new_mesh_path = skel_root_path.AppendChild(original_mesh_path.name)
        new_mesh_prim = stage.DefinePrim(new_mesh_path, "Mesh")

        # Copy all mesh attributes
        for attr in mesh_prim.GetAttributes():
            value = attr.Get()
            if value is not None:
                new_mesh_prim.CreateAttribute(attr.GetName(), attr.GetTypeName()).Set(
                    value
                )

        # Apply skeletal binding
        skel_binding_api = UsdSkel.BindingAPI.Apply(new_mesh_prim)
        skel_binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Get vertex count
        mesh_points = mesh.GetPointsAttr().Get()
        num_verts = len(mesh_points) if mesh_points else 0

        if num_verts > 0:
            # Bind all vertices to the single root joint with full weight
            joint_indices = Vt.IntArray([0] * num_verts)
            joint_weights = Vt.FloatArray([1.0] * num_verts)

            skel_binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
            skel_binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

        # Copy material binding if it exists
        from pxr import UsdShade

        old_mat_api = UsdShade.MaterialBindingAPI(mesh_prim)
        mat_binding = old_mat_api.GetDirectBinding()
        if mat_binding:
            new_mat_api = UsdShade.MaterialBindingAPI.Apply(new_mesh_prim)
            new_mat_api.Bind(mat_binding.GetMaterial())

        # Remove original mesh
        stage.RemovePrim(original_mesh_path)

        # Set root as default prim (NOT SkelRoot!) so materials are accessible
        # This ensures materials in /root/_materials are visible when Unreal imports
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim:
            print(
                f"    -> Setting default prim to 'root' (was: {stage.GetDefaultPrim().GetPath() if stage.GetDefaultPrim() else 'none'})"
            )
            stage.SetDefaultPrim(root_prim)
            print(f"    -> New default prim: {stage.GetDefaultPrim().GetPath()}")
        else:
            print(f"    -> WARNING: Could not find /root prim!")

        # Save
        stage.Save()
        return True

    except Exception as e:
        print(f"  Warning: Could not add skeleton to twig {usd_path.name}: {e}")
        return False


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
        from ..config import get_species_data

        species_data = get_species_data(species_name)
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

                # OPTIMIZATION: Skeletal twigs are NOT needed for Nanite Assemblies
                # Reason: Static twig geometry + PointInstancer NaniteAssemblySkelBindingAPI
                #         is the correct approach for skeletal assemblies
                #
                # Keeping skeletal twig conversion disabled to:
                # - Reduce export time (no skeleton conversion step)
                # - Save disk space (fewer USD files)
                # - Avoid confusion (static twigs work for all assemblies)
                #
                # If skeletal twigs are needed for other workflows, uncomment below:

                # skeletal_path = output_dir / f"{clean_name}_skeletal.usda"
                # import shutil
                # shutil.copy2(usd_path, skeletal_path)
                # if _add_skeleton_to_twig_usd(skeletal_path):
                #     exported_files.append(skeletal_path)

            except Exception as e:
                continue

    except Exception as e:
        print(f"Failed to process blend file {blend_file_path}: {e}")

    return exported_files


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
    export_formats: List[str] = ["usda"],
    use_native_usd_export: bool = True,
    include_twigs_in_usd: bool = True,
    create_nanite_assembly: bool = True,
) -> Dict[str, List[Path]]:
    """Export trees as USD for Unreal Engine Nanite with PCG metadata.

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
        export_formats: Export formats ('usd', 'usda')
        use_native_usd_export: Use Grove's native USD export (recommended, includes all attributes)
        include_twigs_in_usd: Include twigs as point instances in USD files
        create_nanite_assembly: Create Nanite Assembly USD for Unreal Engine (default: True)

    Returns:
        Dict with 'usd', 'metadata', and 'twigs' file paths
    """
    if config is None:
        config = get_config()

    import json

    from .unreal_metadata import create_metadata_from_growth_data

    results = {"usd": [], "metadata": [], "twigs": []}

    # Create clearer output directory structure:
    # output_dir/
    #   ├── Species1/
    #   │   ├── USD/
    #   │   └── twigs/
    #   └── Species2/
    #       ├── USD/
    #       └── twigs/

    metadata_dir = output_dir / "Metadata"
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

            # Create species-specific directories
            species_dir = output_dir / species_clean
            species_dir.mkdir(parents=True, exist_ok=True)

            usd_dir = (
                species_dir / "USD"
                if "usd" in export_formats or "usda" in export_formats
                else None
            )

            if usd_dir:
                usd_dir.mkdir(parents=True, exist_ok=True)

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
                        # Get static USD twig files (never Nanite Assembly for twig references)
                        # CRITICAL: Use prefer_skeletal=False to ensure static twigs for static assemblies
                        twig_usd_map = get_twig_usd_map_for_species(
                            species, config, prefer_skeletal=False
                        )
                        if not twig_usd_map:
                            print(f"  Warning: No twig USD files found for {species}")

                    export_success = False
                    if use_native_usd_export:
                        # Use Grove's native USD export with twigs, skeleton, and materials
                        export_success = export_grove_tree_as_usda_native(
                            grove,
                            usd_path,
                            species,
                            twig_usd_paths=twig_usd_map,
                            include_twigs=include_twigs_in_usd,
                            use_point_instancer=True,
                            convert_to_ue=True,
                            create_nanite_assembly=create_nanite_assembly,
                            include_skeleton=True,
                            resolution=resolution,
                            resolution_reduce=resolution_reduce,
                            texture_repeat=texture_repeat,
                            build_cutoff_age=build_cutoff_age,
                            build_cutoff_thickness=build_cutoff_thickness,
                            build_blend=build_blend,
                            build_end_cap=build_end_cap,
                            config=config,
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
                print(f"\n  Bundling twigs for {species}...")
                twig_results = bundle_twigs_for_species(
                    species,
                    species_dir,  # Use species-specific directory
                    formats=export_formats,
                    config=config,
                )
                results["twigs"].extend(twig_results["twig_files"])

                # Update PCG metadata with twig files
                if twig_results["manifest"]:
                    import json as json_lib

                    with open(twig_results["manifest"], "r") as f:
                        twig_manifest = json_lib.load(f)
                    # twig_manifest now has "twig_files" list instead of "twig_types" dict
                    pcg_metadata.twig_files = twig_manifest.get("twig_files", [])

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
    include_skeleton: bool = True,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.1,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    config: Optional[Any] = None,
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
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.1, higher=fewer bones)
        skeleton_bias: Weight bias (default: 0.5, range 0-1)
        skeleton_connected: Connected bone hierarchy (default: True)

    Returns:
        bool: Success status

    Coordinate System Handling:
        Grove → USD transformation pipeline:

        1. Grove exports model via model_to_usda_string()
           - Documented to export in Y-up coordinate system
           - Vertex coordinates: (x, y, z) where Y is vertical

        2. We wrap Grove's USD in Z-up stage
           - Stage metadata: UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
           - Stage scale: UsdGeom.SetStageMetersPerUnit(stage, 1.0)
           - Face attributes converted: Y-up → Z-up via _add_grove_face_attributes_to_usd()

        3. Twigs added with convert_to_ue flag
           - If True: Blender Z-up → Unreal Z-up (handedness conversion)
           - Transformation: (x, y, z) → (y, -x, z)

        4. Unreal import
           - Reads Z-up USD correctly
           - Scale: Meters (USD) handled automatically
           - Handedness: Left-handed (if convert_to_ue=True)

        Note: The Grove model vertices may already be in Z-up despite Y-up metadata.
        This needs validation - see docs/growpy/COORDINATE_SYSTEMS.md
    """
    ensure_grove_available()
    gc = _get_gc()

    try:
        print(f"Exporting {species_name} as USDA...")

        # Tag bones BEFORE building models so bone IDs are included in model
        # This is critical for skeleton export to work correctly
        if include_skeleton and hasattr(grove, "tag_bone_id"):
            print(
                f"  Tagging bones (length={skeleton_length}, reduce={skeleton_reduce}, bias={skeleton_bias}, connected={skeleton_connected})..."
            )
            try:
                bones = grove.tag_bone_id(
                    skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
                )
                if bones:
                    print(f"    [OK] Tagged {len(bones)} bones for skeleton")
                else:
                    print("    Warning: Bone tagging returned no bones")
            except Exception as e:
                print(f"    Warning: Bone tagging failed: {e}")

        # Build tree model with Grove
        # If bone tagging was done above, the model will include bone_id attributes
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

        # Triangulate using Grove's native function for consistent topology
        # This ensures compatibility with Nanite and other triangle-only pipelines
        model.triangulate()

        # Export using direct Grove API geometry (no coordinate transformation needed)
        from .usd_builder import build_tree_usd

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_tree_path = (
            output_path.parent / f"{output_path.stem}_tree_only{output_path.suffix}"
        )

        # Build USD directly from Grove API data
        if not build_tree_usd(model, temp_tree_path, up_axis="Z", triangulated=True):
            print(f"  Error: Failed to build tree USD")
            return False

        print(f"  [OK] Exported base tree USD: {temp_tree_path.name}")

        # No coordinate transformation needed - Grove API provides correct coordinates

        # NOTE: Grove's native USD export already includes twig face attributes
        # as PascalCase primvars (TwigDead, TwigUpward, TwigSide, TwigEnd)
        # No need to add duplicate snake_case versions
        # NOTE: Grove API face attributes are already added as primvars by usd_builder
        # using PascalCase naming (TwigDead, TwigUpward, TwigLong, TwigShort)

        # Add materials to base tree (static mesh version)
        # Find bark textures
        base_textures = _find_bark_texture(species_name, config)
        if base_textures:
            from .usd_builder import add_materials_to_usd

            add_materials_to_usd(temp_tree_path, species_name, base_textures)
            copy_bark_textures_for_species(
                species_name,
                temp_tree_path.parent.parent,  # Go up to species dir
                base_textures,
            )

        # Create skeletal version with skeleton ONLY (materials already added)
        skeletal_tree_path = temp_tree_path
        if include_skeleton:
            import shutil

            skeletal_tree_path = (
                output_path.parent
                / f"{output_path.stem}_tree_only_skeletal{output_path.suffix}"
            )

            print(f"  Creating skeletal tree USD with native Grove exporter...")

            # CRITICAL: Copy temp_tree_path to skeletal path FIRST
            # This preserves temp_tree_path as static (no skeleton)
            # Materials are already in temp_tree_path, so they get copied too
            shutil.copy2(temp_tree_path, skeletal_tree_path)

            # Add ONLY skeleton to the SKELETAL copy (materials already present from copy)
            # Use usd_builder which correctly uses Grove's tag_bone_id() API
            from .usd_builder import add_skeleton_to_usd

            skeleton_added = add_skeleton_to_usd(
                usd_path=skeletal_tree_path,
                grove=grove,
                skeleton_length=skeleton_length,
                skeleton_reduce=skeleton_reduce,
                skeleton_bias=skeleton_bias,
                skeleton_connected=skeleton_connected,
            )

            if skeleton_added:
                print(f"  [OK] Skeletal tree USD: {skeletal_tree_path.name}")
                print(f"    (Skeletal mesh with embedded UsdSkel)")
            else:
                print(f"  ⚠ Failed to add skeleton to tree USD")
                skeletal_tree_path = temp_tree_path

            # temp_tree_path remains static mesh only (no skeleton)
            # This is used for static Nanite Assembly
        else:
            # If no skeleton requested, use temp_tree_path for everything
            skeletal_tree_path = temp_tree_path

        # Skip creating standard assembly files - only create Nanite Assembly
        # Standard assembly files (with point instanced twigs) are not needed for Nanite workflow
        print(f"  [OK] Tree-only USD saved as: {temp_tree_path.name}")

        # Create Nanite Assembly USD for Unreal if requested
        if create_nanite_assembly:
            from .unreal_nanite_assembly import create_nanite_assembly_usd

            # Create USD-based static mesh assembly
            nanite_path = (
                output_path.parent
                / f"{output_path.stem}_NaniteAssembly{output_path.suffix}"
            )

            print(f"\n  Creating Unreal Nanite Assembly (USD/Static)...")
            # CRITICAL: Static assembly must use static (non-skeletal) tree USD
            # temp_tree_path is the static tree mesh (no skeleton)
            # twig_usd_paths with prefer_skeletal=False ensures static twigs
            # Get static twig paths explicitly
            static_twig_paths = (
                get_twig_usd_map_for_species(
                    species_name, config, prefer_skeletal=False
                )
                if include_twigs
                else None
            )

            nanite_success = create_nanite_assembly_usd(
                tree_usd_path=temp_tree_path,  # Static tree mesh (no skeleton)
                output_path=nanite_path,
                species_name=species_name,
                twig_usd_paths=static_twig_paths,  # Static twigs only
                use_skeletal_mesh=False,
            )

            if nanite_success:
                print(f"  [OK] Nanite Assembly USD: {nanite_path.name}")
                print(f"    Import this file in Unreal Engine 5.7+ (static mesh)")

            # Create skeletal Nanite Assembly if skeleton is enabled
            if include_skeleton and include_twigs and twig_usd_paths:
                print(f"\n  Creating Skeletal Nanite Assembly...")

                # Skeletal Nanite Assembly references:
                # - skeletal_tree_path (*_tree_only_skeletal.usda) - geometry + skeleton
                # - static_twig_paths - STATIC twigs (geometry only)
                # The skeleton from skeletal_tree_path is referenced and static twigs are bound to it
                skeletal_nanite_path = (
                    output_path.parent
                    / f"{output_path.stem}_NaniteAssembly_skeletal{output_path.suffix}"
                )

                skeletal_nanite_success = create_nanite_assembly_usd(
                    tree_usd_path=skeletal_tree_path,  # SKELETAL tree (geometry + skeleton)
                    output_path=skeletal_nanite_path,
                    species_name=species_name,
                    twig_usd_paths=static_twig_paths,  # STATIC twigs (geometry only)
                    use_skeletal_mesh=True,
                    skeleton_source_usd=skeletal_tree_path,  # Extract skeleton from here
                    twig_placement_source_usd=temp_tree_path,  # Extract placements from static tree
                )

                if skeletal_nanite_success:
                    print(
                        f"  [OK] Skeletal Nanite Assembly: {skeletal_nanite_path.name}"
                    )
                    print(
                        f"    References: {skeletal_tree_path.name} (tree + skeleton) + static twigs"
                    )
                    print(f"    Import this file in Unreal Engine 5.7+ (skeletal mesh)")
            elif include_skeleton:
                print(f"\n  [INFO]  For skeletal mesh with animation:")
                print(
                    f"     Import {skeletal_tree_path.name} directly (skeleton embedded)"
                )
                print(f"     (No twigs - skeletal assembly not applicable)")

        return True

    except Exception as e:
        print(f"Failed to export Grove tree as USDA: {e}")
        import traceback

        traceback.print_exc()
        return False


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
        config = get_config()

    from ..config import get_twig_files_by_type

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
    # Grove uses: twig_long, twig_short, twig_upward, twig_dead
    type_mapping = {
        "twig_long": ["apical", "long", "end", "terminal", "var_a", "var_c"],
        "twig_short": ["lateral", "short", "side", "var_b", "var_d"],
        "twig_upward": ["upward", "up", "var_e"],
        "twig_dead": ["dead", "fall", "winter"],
    }

    for grove_type, keywords in type_mapping.items():
        # Find first matching twig file
        for twig_type, twig_paths in twig_files_by_type.items():
            if any(kw in twig_type.lower() for kw in keywords):
                if twig_paths:
                    # Get first twig file and look for USD version (prefer USD over FBX)
                    twig_file = twig_paths[0]

                    # CRITICAL: ALWAYS use regular USD files for twigs, NEVER Nanite Assembly
                    # Nanite Assembly is only for top-level tree assembly
                    # Using Nanite Assembly twigs causes Unreal Engine import crashes
                    for ext in [".usda", ".usd"]:
                        usd_file = twig_file.with_suffix(ext)

                        # Skip Nanite Assembly files completely
                        if "_NaniteAssembly" in usd_file.name:
                            continue

                        # Filter based on skeletal preference
                        is_skeletal = "_skeletal" in usd_file.stem
                        if prefer_skeletal and not is_skeletal:
                            # Looking for skeletal, this is static - check for skeletal variant
                            skeletal_file = (
                                usd_file.parent
                                / f"{usd_file.stem}_skeletal{usd_file.suffix}"
                            )
                            if skeletal_file.exists():
                                twig_usd_map[grove_type] = skeletal_file
                                print(f"    Found {grove_type}: {skeletal_file.name}")
                                break
                            continue
                        elif not prefer_skeletal and is_skeletal:
                            # Looking for static, this is skeletal - skip it
                            continue

                        if usd_file.exists():
                            twig_usd_map[grove_type] = usd_file
                            print(f"    Found {grove_type}: {usd_file.name}")
                            break

                    # CRITICAL: If we found a match (either USD or skeletal variant),
                    # break out of twig_type loop to prevent other matches from overwriting
                    if grove_type in twig_usd_map:
                        break

                    # Fallback to FBX if no USD found
                    fbx_file = twig_file.with_suffix(".fbx")
                    if fbx_file.exists():
                        twig_usd_map[grove_type] = fbx_file
                        print(f"    Found {grove_type}: {fbx_file.name} (FBX fallback)")
                        break

    # Add fallback mappings for missing twig types
    # If no matches found and twig files exist, use first available for each type
    if not twig_usd_map and twig_files_by_type:
        print(f"    Using generic twig mapping (no keyword matches found)")
        # Get all available twig files, filtering by skeletal preference
        all_twigs = []
        for twig_paths in twig_files_by_type.values():
            for twig_path in twig_paths:
                # Check if this twig matches skeletal preference
                for ext in [".usda", ".usd"]:
                    usd_file = twig_path.with_suffix(ext)
                    if not usd_file.exists() or "_NaniteAssembly" in usd_file.name:
                        continue

                    is_skeletal = "_skeletal" in usd_file.stem

                    # Apply skeletal filtering
                    if prefer_skeletal and not is_skeletal:
                        # Looking for skeletal variant
                        skeletal_file = (
                            usd_file.parent
                            / f"{usd_file.stem}_skeletal{usd_file.suffix}"
                        )
                        if skeletal_file.exists():
                            all_twigs.append(skeletal_file)
                            break
                    elif not prefer_skeletal and is_skeletal:
                        # Skip skeletal files when looking for static
                        continue
                    else:
                        # Match found
                        all_twigs.append(usd_file)
                        break

        if all_twigs:
            # Use first few twigs for different types
            for i, grove_type in enumerate(
                ["twig_long", "twig_short", "twig_upward", "twig_dead"]
            ):
                if i < len(all_twigs):
                    twig_usd_map[grove_type] = all_twigs[i]
                    print(f"    Assigned {grove_type}: {all_twigs[i].name}")

    # If twig_upward not found, use twig_short (upward twigs are similar to lateral)
    if "twig_upward" not in twig_usd_map and "twig_short" in twig_usd_map:
        twig_usd_map["twig_upward"] = twig_usd_map["twig_short"]
        print(f"    Using twig_short for twig_upward (no upward-specific twig)")

    # If twig_dead not found, use twig_short (dead twigs similar to lateral)
    if "twig_dead" not in twig_usd_map and "twig_short" in twig_usd_map:
        twig_usd_map["twig_dead"] = twig_usd_map["twig_short"]
        print(f"    Using twig_short for twig_dead (no dead-specific twig)")

    # Summary
    if twig_usd_map:
        print(f"  SUCCESS: Found {len(twig_usd_map)} twig type(s) for '{species_name}'")
    else:
        print(f"  ERROR: No twig mapping could be created for '{species_name}'")
        print(f"  Trees will be exported WITHOUT twigs")

    return twig_usd_map


def copy_bark_textures_for_species(
    species_name: str,
    species_output_dir: Path,
    textures: Optional[Dict[str, Path]],
) -> List[Path]:
    """Copy bark texture files to species output directory.

    Similar to twig texture bundling, copies bark textures (diffuse + normal)
    to output/USD/textures/ for easier asset management in Unreal Engine.

    Args:
        species_name: Name of tree species
        species_output_dir: Output directory for this species
        textures: Dict with 'diffuse' and 'normal' texture paths

    Returns:
        List of copied texture file paths
    """
    import shutil

    copied_files = []

    if not textures:
        return copied_files

    # Create textures subdirectory in species folder
    texture_dir = species_output_dir / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)

    # Copy diffuse texture
    if "diffuse" in textures and textures["diffuse"].exists():
        dest_path = texture_dir / textures["diffuse"].name
        shutil.copy2(textures["diffuse"], dest_path)
        copied_files.append(dest_path)
        print(f"  [OK] Copied diffuse texture: {textures['diffuse'].name}")

    # Copy normal map
    if "normal" in textures and textures["normal"].exists():
        dest_path = texture_dir / textures["normal"].name
        shutil.copy2(textures["normal"], dest_path)
        copied_files.append(dest_path)
        print(f"  [OK] Copied normal map: {textures['normal'].name}")

    return copied_files


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
        config = get_config()

    import shutil

    results = {"twig_files": [], "manifest": None}

    try:
        # Get twig files for this species - place directly in species folder
        twig_dir = output_dir
        twig_dir.mkdir(parents=True, exist_ok=True)

        # Get available twig files for this species (all variations)
        from ..config import get_twig_files_by_type

        twig_files_by_type = get_twig_files_by_type(species_name)

        if not twig_files_by_type:
            print(f"  No twig files found for {species_name}")
            return results

        twig_manifest = {"species": species_name, "twig_files": [], "total_twigs": 0}
        copied_textures = set()  # Track copied textures to avoid duplicates

        # Collect all unique twig files (avoid duplicates)
        all_twig_files = set()
        for twig_paths in twig_files_by_type.values():
            all_twig_files.update(twig_paths)

        # Copy ALL twig files for this species in requested formats
        for source_file in sorted(all_twig_files):
            if not source_file.exists():
                continue

            # Get the base path without extension
            source_base = source_file.parent / source_file.stem

            # Copy all requested formats (both static and skeletal variants)
            for fmt in formats:
                # Determine file extension based on format
                if fmt == "usd":
                    extensions = [".usd", ".usda"]  # Try both
                elif fmt == "usda":
                    extensions = [".usda", ".usd"]  # Try both
                else:
                    continue

                # Try to find file with any of the extensions
                for ext in extensions:
                    fmt_source_file = source_base.with_suffix(ext)
                    if fmt_source_file.exists():
                        # Copy the file
                        dest_file = twig_dir / fmt_source_file.name
                        shutil.copy2(fmt_source_file, dest_file)
                        results["twig_files"].append(dest_file)
                        twig_manifest["twig_files"].append(dest_file.name)
                        twig_manifest["total_twigs"] += 1
                        print(f"    Copied twig: {dest_file.name}")
                        break  # Found file, no need to try other extensions

                    # Also check for skeletal variant
                    skeletal_file = (
                        source_base.parent / f"{source_base.stem}_skeletal{ext}"
                    )
                    if (
                        skeletal_file.exists()
                        and not (twig_dir / skeletal_file.name).exists()
                    ):
                        # Copy skeletal variant
                        dest_file = twig_dir / skeletal_file.name
                        shutil.copy2(skeletal_file, dest_file)
                        results["twig_files"].append(dest_file)
                        twig_manifest["twig_files"].append(dest_file.name)
                        twig_manifest["total_twigs"] += 1
                        print(f"    Copied twig: {dest_file.name}")

        # Copy textures if they exist (only once per species)
        if all_twig_files:
            # Get texture directory from first twig file
            first_twig = next(iter(all_twig_files))
            texture_dir = first_twig.parent / "textures"
            if texture_dir.exists():
                dest_texture_dir = twig_dir / "textures"
                dest_texture_dir.mkdir(exist_ok=True)
                for texture_file in texture_dir.glob("*"):
                    if texture_file.is_file():
                        shutil.copy2(texture_file, dest_texture_dir / texture_file.name)
                print(f"    Copied textures from {texture_dir.name}")

        # Save twig manifest
        if twig_manifest["total_twigs"] > 0:
            manifest_path = twig_dir / "twig_manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(twig_manifest, f, indent=2)
            results["manifest"] = manifest_path
            print(
                f"  [OK] Bundled {twig_manifest['total_twigs']} twig files for {species_name}"
            )
        else:
            print(f"  ⚠ No twig files copied for {species_name}")

    except Exception as e:
        print(f"Failed to bundle twigs for {species_name}: {e}")

    return results
    return results
