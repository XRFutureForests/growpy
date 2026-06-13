#!/usr/bin/env python3
"""Blender mesh export utilities for USD format.

Functions for exporting Blender mesh objects to USD files using
the pxr module directly. Used as a fallback when bpy.ops.wm.usd_export
is not available.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from pxr import Gf, Sdf, Usd, UsdGeom
except ImportError:
    # Standalone mode - do manual initialization
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    from pxr import Gf, Sdf, Usd, UsdGeom


def export_blender_mesh_to_usd(
    obj, output_path, include_normals=True, include_uvs=True
):
    """Export Blender mesh object to USD file using pxr directly.

    This is a fallback when bpy.ops.wm.usd_export is not available
    (e.g., in standalone bpy).
    Creates a basic USD file with geometry only (no materials/textures).

    Args:
        obj: Blender mesh object or empty with child mesh to export
        output_path: Path to write USD file
        include_normals: Include vertex normals in export
        include_uvs: Include UV coordinates in export (best effort)

    Returns:
        True if export succeeded, False otherwise
    """
    try:
        # Find actual mesh object (might be passed an empty with children)
        mesh_obj = obj
        if not hasattr(obj.data, "vertices"):
            # obj is an empty, find first mesh child
            found = False
            for child in obj.children:
                if hasattr(child.data, "vertices"):
                    mesh_obj = child
                    found = True
                    break
            if not found:
                logger.error("No mesh data found in object or its children")
                return False

        # Create USD stage and mesh prim
        stage = Usd.Stage.CreateNew(str(output_path))
        mesh = mesh_obj.data
        mesh_prim = UsdGeom.Mesh.Define(stage, Sdf.Path("/Mesh"))

        # Collect and set vertex positions
        points = []
        for vert in mesh.vertices:
            co = vert.co
            points.append(Gf.Vec3f(co.x, co.y, co.z))

        mesh_prim.CreatePointsAttr().Set(points)

        # Collect and set face vertex counts and indices
        face_vertex_counts = []
        face_vertex_indices = []

        for poly in mesh.polygons:
            face_vertex_counts.append(len(poly.vertices))
            face_vertex_indices.extend(poly.vertices)

        mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)
        mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices)

        # Add normals if requested
        if include_normals:
            normals = []
            for vert in mesh.vertices:
                n = vert.normal
                normals.append(Gf.Vec3f(n.x, n.y, n.z))
            mesh_prim.CreateNormalsAttr().Set(normals)

        # Save the stage
        stage.GetRootLayer().Save()
        return True

    except Exception as e:
        logger.error("Direct USD export failed: %s", e, exc_info=True)
        return False
