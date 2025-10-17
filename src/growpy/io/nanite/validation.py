"""Nanite mesh validation."""

from typing import Any, Dict


def validate_mesh_for_nanite(mesh: Any) -> Dict[str, Any]:
    """Validate mesh for Unreal Engine Nanite compatibility.

    Args:
        mesh: Blender mesh object

    Returns:
        Dict with validation results
    """
    validation = {"compatible": True, "warnings": [], "stats": {}}

    triangle_count = len(mesh.polygons)
    vertex_count = len(mesh.vertices)
    validation["stats"]["triangle_count"] = triangle_count
    validation["stats"]["vertex_count"] = vertex_count

    if vertex_count > 0 and triangle_count > 0:
        vertex_ratio = vertex_count / triangle_count
        validation["stats"]["vertex_to_triangle_ratio"] = vertex_ratio

        if vertex_ratio > 2.0:
            validation["warnings"].append(
                f"High vertex-to-triangle ratio ({vertex_ratio:.2f}:1)"
            )

    quad_count = sum(1 for poly in mesh.polygons if len(poly.vertices) == 4)
    validation["stats"]["quad_count"] = quad_count
    validation["stats"]["tri_count"] = triangle_count - quad_count

    if mesh.uv_layers:
        uv_seam_count = sum(1 for edge in mesh.edges if edge.use_seam)
        validation["stats"]["uv_seams"] = uv_seam_count
        validation["stats"]["uv_layers"] = len(mesh.uv_layers)

        if uv_seam_count > triangle_count * 0.3:
            validation["warnings"].append(f"High UV seam count ({uv_seam_count})")
    else:
        validation["warnings"].append("No UV maps found")

    import mathutils
    thin_triangle_count = 0
    for poly in mesh.polygons:
        if len(poly.vertices) >= 3:
            verts = [mesh.vertices[v].co for v in poly.vertices[:3]]
            edges = [
                (verts[1] - verts[0]).length,
                (verts[2] - verts[1]).length,
                (verts[0] - verts[2]).length,
            ]
            if min(edges) > 0 and max(edges) / min(edges) > 10:
                thin_triangle_count += 1

    validation["stats"]["thin_triangles"] = thin_triangle_count
    if thin_triangle_count > triangle_count * 0.1:
        validation["warnings"].append(f"Many thin triangles detected ({thin_triangle_count})")

    validation["stats"]["material_count"] = len(mesh.materials)
    if len(mesh.materials) == 0:
        validation["warnings"].append("No materials assigned")

    return validation
