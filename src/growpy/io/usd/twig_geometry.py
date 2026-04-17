"""Mesh geometry operations for twig processing.

Densification, alpha-based trimming, boundary smoothing, spike cleanup,
tube/plane topology classification, and interior decimation — all running
inside Blender's Python environment (bpy / bmesh).
"""

import logging
import math
from pathlib import Path
from typing import Optional, Set

import bmesh
import bpy
import mathutils
import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None

logger = logging.getLogger(__name__)


def densify_mesh(obj, subdivision_levels=3, material_indices=None):
    """Densify mesh using subdivision to create more triangles.

    Args:
        obj: Blender mesh object
        subdivision_levels: Number of subdivision iterations (default: 3)
        material_indices: Optional set of material indices to restrict densification
    """
    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Use bmesh for subdivision
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        edges = bm.edges
        if material_indices:
            face_edges = set()
            for f in bm.faces:
                if f.material_index in material_indices:
                    for e in f.edges:
                        face_edges.add(e)
            edges = list(face_edges)

        if edges:
            bmesh.ops.subdivide_edges(
                bm, edges=edges, cuts=subdivision_levels, use_grid_fill=True
            )

        # Write back to mesh
        bm.to_mesh(obj.data)
        bm.free()

        obj.data.update()
    except Exception as e:
        pass


def _measure_average_edge_length(mesh, material_indices=None):
    """Measure average edge length for faces matching material indices.

    Args:
        mesh: Blender mesh data
        material_indices: Optional set of material indices to filter by

    Returns:
        Average edge length in Blender units, or 0.0 if no edges found.
    """
    edge_set = set()
    for poly in mesh.polygons:
        if material_indices and poly.material_index not in material_indices:
            continue
        for edge_key in poly.edge_keys:
            edge_set.add(edge_key)

    if not edge_set:
        return 0.0

    total_length = 0.0
    for v0_idx, v1_idx in edge_set:
        v0 = mesh.vertices[v0_idx].co
        v1 = mesh.vertices[v1_idx].co
        total_length += (v0 - v1).length

    return total_length / len(edge_set)


def densify_mesh_to_target_edge(
    obj, target_edge_mm, material_indices=None, max_iterations=8
):
    """Densify mesh by iteratively subdividing until target edge length is reached.

    This ensures consistent mesh density across different twig sizes by targeting
    an absolute edge length rather than a fixed subdivision count.

    Args:
        obj: Blender mesh object
        target_edge_mm: Target edge length in millimeters (e.g., 0.5 for 0.5mm edges)
        material_indices: Optional set of material indices to restrict densification
        max_iterations: Maximum subdivision iterations to prevent runaway (default: 8)

    Returns:
        Final average edge length in mm
    """
    if target_edge_mm is None or target_edge_mm <= 0:
        return 0.0

    # Convert mm to Blender units (1 Blender unit = 1m = 1000mm for typical twig scale)
    target_edge_bu = target_edge_mm / 1000.0

    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Measure initial edge length
        initial_edge = _measure_average_edge_length(obj.data, material_indices)
        initial_edge_mm = initial_edge * 1000.0

        for iteration in range(max_iterations):
            # Measure current edge length
            current_edge = _measure_average_edge_length(obj.data, material_indices)
            if current_edge <= 0:
                break

            # Check if we've reached target (within 20% tolerance)
            if current_edge <= target_edge_bu * 1.2:
                break

            # Calculate how many cuts needed to approximately halve edge length
            # Each cut=1 roughly halves edge length
            ratio = current_edge / target_edge_bu
            if ratio <= 1.5:
                cuts = 1
            elif ratio <= 3:
                cuts = 2
            else:
                cuts = 3  # Don't go too aggressive per iteration

            # Subdivide
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            edges = list(bm.edges)
            if material_indices:
                face_edges = set()
                for f in bm.faces:
                    if f.material_index in material_indices:
                        for e in f.edges:
                            face_edges.add(e)
                edges = list(face_edges)

            if edges:
                bmesh.ops.subdivide_edges(
                    bm, edges=edges, cuts=cuts, use_grid_fill=True
                )

            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()

        # Return final edge length in mm
        final_edge = _measure_average_edge_length(obj.data, material_indices)
        final_edge_mm = final_edge * 1000.0

        logger.debug(
            "Adaptive densify: %.2fmm -> %.2fmm (target: %.2fmm, %d iterations)",
            initial_edge_mm,
            final_edge_mm,
            target_edge_mm,
            iteration + 1,
        )

        return final_edge_mm

    except Exception:
        return 0.0


def apply_normal_displacement(
    obj, normal_texture_path, strength=0.005, material_indices=None
):
    """Displace mesh vertices based on normal map texture.

    Args:
        obj: Blender mesh object
        normal_texture_path: Path to normal map texture
        strength: Displacement strength multiplier (default: 0.01)
    """
    try:
        if Image is None:
            return
        if not normal_texture_path or not Path(normal_texture_path).exists():
            return

        # Load normal map image
        img = Image.open(normal_texture_path)
        img_width, img_height = img.size
        pixels = img.load()

        # Get UV layer
        if not obj.data.uv_layers.active:
            return

        uv_layer = obj.data.uv_layers.active.data
        mesh = obj.data

        # Build vertex UV mapping
        vertex_uvs = {}
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                loop = mesh.loops[loop_idx]
                vert_idx = loop.vertex_index
                uv = uv_layer[loop_idx].uv
                if vert_idx not in vertex_uvs:
                    vertex_uvs[vert_idx] = uv

        # If restricting to leaf faces, collect eligible vertices
        eligible = None
        if material_indices:
            eligible = set()
            for poly in mesh.polygons:
                if poly.material_index in material_indices:
                    for loop_idx in poly.loop_indices:
                        eligible.add(mesh.loops[loop_idx].vertex_index)

        # Displace vertices based on normal map
        for vert_idx, uv in vertex_uvs.items():
            if eligible is not None and vert_idx not in eligible:
                continue
            vert = mesh.vertices[vert_idx]

            # Sample normal map at UV coordinate
            x = int(uv.x * (img_width - 1))
            y = int((1.0 - uv.y) * (img_height - 1))  # Flip Y
            x = max(0, min(img_width - 1, x))
            y = max(0, min(img_height - 1, y))

            # Get pixel color (normal map RGB)
            pixel = pixels[x, y]
            if len(pixel) >= 3:
                # Convert from [0-255] to [-1, 1] range
                nx = (pixel[0] / 255.0) * 2.0 - 1.0
                ny = (pixel[1] / 255.0) * 2.0 - 1.0
                nz = (pixel[2] / 255.0) * 2.0 - 1.0

                # Normalize
                length = (nx * nx + ny * ny + nz * nz) ** 0.5
                if length > 0:
                    nx /= length
                    ny /= length
                    nz /= length

                # Displace along vertex normal weighted by normal map Z component
                displacement = mathutils.Vector(vert.normal) * nz * strength
                vert.co += displacement

        mesh.update()
    except Exception as e:
        pass


def trim_by_alpha_mask(
    obj,
    alpha_texture_path,
    threshold=0.5,
    require_alpha_channel=False,
    material_indices=None,
    allow_luminance_for_masks: bool = False,
    method="all",
    preserve_interior=True,
):
    """Trim mesh geometry based on alpha/opacity mask texture.

    Removes faces based on alpha values using specified method.

    Args:
        obj: Blender mesh object
        alpha_texture_path: Path to alpha/mask texture
        threshold: Alpha threshold for keeping geometry (0.0-1.0, default: 0.5)
        method: 'all' (default) = delete only if ALL vertices < threshold (conservative),
                'average' = delete if avg alpha < threshold (more aggressive)
        preserve_interior: If True (default), preserve faces whose center samples
                           an opaque alpha value, protecting thin geometry centers.
    """
    try:
        if Image is None:
            return
        if not alpha_texture_path or not Path(alpha_texture_path).exists():
            return

        # Load alpha/translucency image
        img = Image.open(alpha_texture_path)
        bands = img.getbands()
        has_alpha = "A" in bands

        # Determine if we can use luminance as alpha for explicit mask textures
        name_lower = Path(alpha_texture_path).stem.lower()
        looks_like_mask = any(
            k in name_lower
            for k in ["alpha", "opacity", "mask", "transparent", "cutout"]
        )

        if require_alpha_channel and not has_alpha:
            return

        # Choose channel for trimming
        alpha_img = None
        if has_alpha:
            alpha_img = img.getchannel("A")
        elif allow_luminance_for_masks and looks_like_mask:
            # Use luminance for explicit mask textures
            alpha_img = img.convert("L")
        else:
            # No usable alpha information
            return

        img_width, img_height = alpha_img.size
        pixels = alpha_img.load()

        # Heuristic inversion for certain mask naming
        invert_mask = any(k in name_lower for k in ["mask", "cutout"])

        # Get UV layer
        if not obj.data.uv_layers.active:
            return

        mesh = obj.data
        uv_layer = mesh.uv_layers.active.data

        # Use bmesh for efficient face deletion
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Build UV layer reference in bmesh
        uv_layer_bm = bm.loops.layers.uv.active
        if not uv_layer_bm:
            bm.free()
            return

        # Mark faces for deletion based on alpha values
        faces_to_delete = []
        center_preserved = 0
        for face in bm.faces:
            if material_indices and face.material_index not in material_indices:
                continue

            # Sample alpha at each vertex of the face
            alpha_values = []
            uv_coords = []
            for loop in face.loops:
                uv = loop[uv_layer_bm].uv
                uv_coords.append((uv.x, uv.y))

                # Sample alpha texture
                x = int(uv.x * (img_width - 1))
                y = int((1.0 - uv.y) * (img_height - 1))  # Flip Y
                x = max(0, min(img_width - 1, x))
                y = max(0, min(img_height - 1, y))

                # Get alpha value (0-255)
                alpha = pixels[x, y] / 255.0
                if invert_mask:
                    alpha = 1.0 - alpha
                alpha_values.append(alpha)

            # PRESERVE_INTERIOR: Also sample alpha at face centroid
            # This protects thin geometry (needles) whose corners may sample
            # transparent areas but whose CENTER samples opaque texture
            if preserve_interior and uv_coords:
                center_u = sum(uv[0] for uv in uv_coords) / len(uv_coords)
                center_v = sum(uv[1] for uv in uv_coords) / len(uv_coords)
                cx = int(center_u * (img_width - 1))
                cy = int((1.0 - center_v) * (img_height - 1))
                cx = max(0, min(img_width - 1, cx))
                cy = max(0, min(img_height - 1, cy))
                center_alpha = pixels[cx, cy] / 255.0
                if invert_mask:
                    center_alpha = 1.0 - center_alpha
                # If center is opaque, preserve this face (needle center protection)
                if center_alpha >= threshold:
                    center_preserved += 1
                    continue

            # Delete face based on method
            if method == "all":
                # Delete only if ALL vertices below threshold (aggressive)
                if all(a < threshold for a in alpha_values):
                    faces_to_delete.append(face)
            else:  # method == "average" (default)
                # Delete if average alpha below threshold (better for thin geometry)
                avg_alpha = (
                    sum(alpha_values) / len(alpha_values) if alpha_values else 0.0
                )
                if avg_alpha < threshold:
                    faces_to_delete.append(face)

        # Delete marked faces
        total_faces_before = len(bm.faces)
        bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
        faces_remaining = len(bm.faces)

        center_msg = (
            f", {center_preserved} center-preserved"
            if preserve_interior and center_preserved > 0
            else ""
        )
        logger.debug(
            "Alpha trimming: deleted %d/%d faces (%.1f%%), %d remaining%s, threshold=%s",
            len(faces_to_delete),
            total_faces_before,
            100 * len(faces_to_delete) / total_faces_before,
            faces_remaining,
            center_msg,
            threshold,
        )

        # Write back to mesh
        bm.to_mesh(mesh)
        bm.free()

        mesh.update()
    except Exception as e:
        logger.warning("Alpha trimming failed: %s", e, exc_info=True)


def _get_alpha_texture_for_geometry(tex_map: dict):
    """Get the best alpha source for geometry processing from texture map.

    Priority order:
        1. Dedicated 'alpha' texture file (use as luminance)
        2. Dedicated 'translucent' texture file (use as luminance)
        3. Embedded alpha channel in 'diffuse' texture (fallback)

    Args:
        tex_map: Dict from _gather_texture_candidates with texture paths

    Returns:
        (texture_path, use_luminance) tuple, or (None, False) if no alpha available
    """
    # Priority 1: Dedicated alpha texture
    if tex_map.get("alpha"):
        return tex_map["alpha"], True  # Use luminance for dedicated alpha files

    # Priority 2: Translucent texture as alpha source
    if tex_map.get("translucent"):
        return tex_map["translucent"], True  # Use luminance for translucent files

    # Priority 3: Embedded alpha in diffuse texture
    if tex_map.get("diffuse"):
        return tex_map["diffuse"], False  # Use embedded alpha channel

    return None, False


def _build_vertex_alpha_map(mesh, alpha_img):
    """Build per-vertex alpha map by sampling the alpha image at UVs.

    Returns: dict vert_index -> alpha [0..1]
    """
    if alpha_img is None or not mesh.uv_layers.active:
        return {}
    pixels = alpha_img.load()
    w, h = alpha_img.size
    uv_layer = mesh.uv_layers.active.data
    vert_alpha = {}
    # Use averaged alpha over all loops touching the vertex
    accum = {}
    counts = {}
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            loop = mesh.loops[loop_idx]
            vi = loop.vertex_index
            uv = uv_layer[loop_idx].uv
            x = int(max(0, min(w - 1, uv.x * (w - 1))))
            y = int(max(0, min(h - 1, (1.0 - uv.y) * (h - 1))))
            a = pixels[x, y] / 255.0
            accum[vi] = accum.get(vi, 0.0) + a
            counts[vi] = counts.get(vi, 0) + 1
    for vi, total in accum.items():
        vert_alpha[vi] = total / max(1, counts.get(vi, 1))
    return vert_alpha


def _detect_alpha_inversion(alpha_img):
    """Detect if alpha mask uses inverted convention (black=opaque).

    Uses corner-based detection: samples corners of the texture to determine
    the "background" value (should be transparent in standard convention).

    The actual leaf/bark geometry doesn't extend to texture edges, so corners
    reliably represent the transparent background. If corners are bright,
    the convention is inverted (white=opaque).

    Returns:
        True if texture uses inverted convention (bright corners = white background)
    """
    if alpha_img is None:
        return False

    pixels_array = np.array(alpha_img, dtype=np.float32)
    h, w = pixels_array.shape

    # Sample corners: 10x10 patches at each corner
    patch_size = min(10, h // 4, w // 4)
    if patch_size < 2:
        # Image too small to detect reliably, assume standard
        return False

    corners = [
        pixels_array[0:patch_size, 0:patch_size],  # top-left
        pixels_array[0:patch_size, -patch_size:],  # top-right
        pixels_array[-patch_size:, 0:patch_size],  # bottom-left
        pixels_array[-patch_size:, -patch_size:],  # bottom-right
    ]

    # Calculate mean corner value (represents the background)
    corner_values = [corner.mean() for corner in corners]
    corner_mean = np.mean(corner_values)

    # If corners are bright (> ~155/255), background is white = inverted convention
    # If corners are dark (< ~100/255), background is black = standard convention
    return corner_mean > 155


def _sample_alpha_at_uv(uv_x, uv_y, alpha_img, invert=False):
    """Sample alpha value at UV coordinate from alpha image.

    Args:
        uv_x, uv_y: UV coordinates (0-1 range)
        alpha_img: PIL Image in grayscale mode
        invert: If True, invert alpha (1.0 - value)

    Returns:
        Alpha value 0.0-1.0
    """
    if alpha_img is None:
        return 1.0
    pixels = alpha_img.load()
    w, h = alpha_img.size
    x = int(max(0, min(w - 1, uv_x * (w - 1))))
    y = int(max(0, min(h - 1, (1.0 - uv_y) * (h - 1))))
    alpha = pixels[x, y] / 255.0
    return (1.0 - alpha) if invert else alpha


def cut_along_alpha_contour(
    obj,
    material_indices,
    alpha_img,
    threshold,
    binary_search_iterations=8,
):
    """Cut leaf meshes along the exact alpha=threshold contour in one pass.

    For each leaf triangle with mixed opaque/transparent vertices, binary-searches
    in UV space to find the alpha crossing on each opaque <-> transparent edge,
    inserts a new vertex at that crossing (3D position via linear interpolation,
    UV via per-face linear interpolation), and retriangulates the opaque side.
    Fully transparent triangles are discarded.

    The resulting mesh carries the silhouette as geometry, so the exported
    material can be fully opaque (no masked alpha, no Nanite proxy path).
    Because UVs are interpolated linearly on unchanged opaque verts and on the
    new cut verts, the original texture mapping is preserved without distortion.
    No boundary smoothing or spike cleanup is required afterwards.

    Args:
        obj: Blender mesh object
        material_indices: Set of material indices identifying leaf geometry
        alpha_img: Alpha texture PIL Image (grayscale, L mode)
        threshold: Alpha threshold (0..1); verts below are transparent
        binary_search_iterations: Bisection steps per edge (8 -> 1/256 bracket)
    """
    if not material_indices or alpha_img is None:
        return
    mesh = obj.data
    if not mesh:
        return

    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        invert_alpha = _detect_alpha_inversion(alpha_img)
        initial_face_count = len(mesh.polygons)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        leaf_ngons = [
            f
            for f in bm.faces
            if f.material_index in material_indices and len(f.verts) > 3
        ]
        if leaf_ngons:
            bmesh.ops.triangulate(bm, faces=leaf_ngons)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

        uv_layer = bm.loops.layers.uv.active
        if uv_layer is None:
            bm.free()
            return

        vert_alpha_sum = {}
        vert_uv_sum = {}
        vert_count = {}
        for face in bm.faces:
            if face.material_index not in material_indices:
                continue
            for loop in face.loops:
                vi = loop.vert.index
                uv = loop[uv_layer].uv
                a = _sample_alpha_at_uv(
                    uv.x, uv.y, alpha_img, invert=invert_alpha
                )
                vert_alpha_sum[vi] = vert_alpha_sum.get(vi, 0.0) + a
                prev = vert_uv_sum.get(vi, (0.0, 0.0))
                vert_uv_sum[vi] = (prev[0] + uv.x, prev[1] + uv.y)
                vert_count[vi] = vert_count.get(vi, 0) + 1

        vert_alpha = {}
        vert_uv_avg = {}
        for vi, n in vert_count.items():
            vert_alpha[vi] = vert_alpha_sum[vi] / n
            vert_uv_avg[vi] = (vert_uv_sum[vi][0] / n, vert_uv_sum[vi][1] / n)

        edge_cuts = {}  # (vi_low, vi_high) -> (BMVert, t_from_vi_low)

        def get_edge_cut(v_op, v_tr):
            vi_op, vi_tr = v_op.index, v_tr.index
            key = (min(vi_op, vi_tr), max(vi_op, vi_tr))
            cached = edge_cuts.get(key)
            if cached is not None:
                new_vert, t_low = cached
                t_from_op = t_low if vi_op == key[0] else 1.0 - t_low
                return new_vert, t_from_op

            uv_op = vert_uv_avg[vi_op]
            uv_tr = vert_uv_avg[vi_tr]
            t_lo, t_hi = 0.0, 1.0
            for _ in range(binary_search_iterations):
                t_mid = 0.5 * (t_lo + t_hi)
                u = uv_op[0] + t_mid * (uv_tr[0] - uv_op[0])
                v = uv_op[1] + t_mid * (uv_tr[1] - uv_op[1])
                a = _sample_alpha_at_uv(
                    u, v, alpha_img, invert=invert_alpha
                )
                if a >= threshold:
                    t_lo = t_mid
                else:
                    t_hi = t_mid
            t = 0.5 * (t_lo + t_hi)
            t = max(0.01, min(0.99, t))

            pos = v_op.co.lerp(v_tr.co, t)
            new_vert = bm.verts.new(pos)
            t_low = t if vi_op == key[0] else 1.0 - t
            edge_cuts[key] = (new_vert, t_low)
            return new_vert, t

        faces_to_delete = []
        new_faces_spec = []  # list of (loops_spec, material_index)

        for face in list(bm.faces):
            if face.material_index not in material_indices:
                continue
            if len(face.verts) != 3:
                continue

            loops = list(face.loops)
            verts = [lp.vert for lp in loops]
            uvs = [tuple(lp[uv_layer].uv) for lp in loops]
            alphas = [vert_alpha.get(v.index, 1.0) for v in verts]
            op_mask = [a >= threshold for a in alphas]
            n_op = sum(op_mask)

            if n_op == 3:
                continue
            if n_op == 0:
                faces_to_delete.append(face)
                continue

            faces_to_delete.append(face)
            mat_idx = face.material_index

            if n_op == 1:
                i_op = op_mask.index(True)
                v_op = verts[i_op]
                uv_op = uvs[i_op]
                v_t1 = verts[(i_op + 1) % 3]
                uv_t1 = uvs[(i_op + 1) % 3]
                v_t2 = verts[(i_op + 2) % 3]
                uv_t2 = uvs[(i_op + 2) % 3]

                new1, t1 = get_edge_cut(v_op, v_t1)
                new2, t2 = get_edge_cut(v_op, v_t2)
                uv_n1 = (
                    uv_op[0] + t1 * (uv_t1[0] - uv_op[0]),
                    uv_op[1] + t1 * (uv_t1[1] - uv_op[1]),
                )
                uv_n2 = (
                    uv_op[0] + t2 * (uv_t2[0] - uv_op[0]),
                    uv_op[1] + t2 * (uv_t2[1] - uv_op[1]),
                )
                new_faces_spec.append(
                    ([(v_op, uv_op), (new1, uv_n1), (new2, uv_n2)], mat_idx)
                )

            else:  # n_op == 2
                i_tr = op_mask.index(False)
                v_tr = verts[i_tr]
                uv_tr = uvs[i_tr]
                v_o1 = verts[(i_tr + 1) % 3]
                uv_o1 = uvs[(i_tr + 1) % 3]
                v_o2 = verts[(i_tr + 2) % 3]
                uv_o2 = uvs[(i_tr + 2) % 3]

                new1, t1 = get_edge_cut(v_o1, v_tr)
                new2, t2 = get_edge_cut(v_o2, v_tr)
                uv_n1 = (
                    uv_o1[0] + t1 * (uv_tr[0] - uv_o1[0]),
                    uv_o1[1] + t1 * (uv_tr[1] - uv_o1[1]),
                )
                uv_n2 = (
                    uv_o2[0] + t2 * (uv_tr[0] - uv_o2[0]),
                    uv_o2[1] + t2 * (uv_tr[1] - uv_o2[1]),
                )
                # Quad v_o1, v_o2, new2, new1 -> two triangles keeping winding
                new_faces_spec.append(
                    (
                        [(v_o1, uv_o1), (v_o2, uv_o2), (new2, uv_n2)],
                        mat_idx,
                    )
                )
                new_faces_spec.append(
                    (
                        [(v_o1, uv_o1), (new2, uv_n2), (new1, uv_n1)],
                        mat_idx,
                    )
                )

        if faces_to_delete:
            # FACES_ONLY keeps verts alive; FACES would purge our newly-created
            # cut verts (they have no linked faces yet at this point)
            bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES_ONLY")
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

        created = 0
        for loops_spec, mat_idx in new_faces_spec:
            verts_only = [lv[0] for lv in loops_spec]
            if len(set(verts_only)) != len(verts_only):
                continue
            try:
                new_face = bm.faces.new(verts_only)
            except ValueError:
                continue
            new_face.material_index = mat_idx
            for loop, (_, uv_target) in zip(new_face.loops, loops_spec):
                loop[uv_layer].uv = uv_target
            created += 1

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Drop orphan verts left behind by deleted transparent faces
        orphans = [v for v in bm.verts if not v.link_faces]
        if orphans:
            bmesh.ops.delete(bm, geom=orphans, context="VERTS")

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        logger.info(
            "Alpha contour cut: %d->%d faces (%d edge cuts)",
            initial_face_count,
            len(mesh.polygons),
            len(edge_cuts),
        )

    except Exception as e:
        logger.warning("Alpha contour cut error: %s", e, exc_info=True)


def densify_and_trim_interleaved(
    obj,
    material_indices,
    alpha_img,
    threshold,
    target_edge_factor=None,
    boundary_edge_mm=0.5,
    max_iterations=10,
    method="all",
):
    """Densify leaf edges with interleaved trimming - transition-face-aware algorithm.

    Algorithm:
        1. Pre-triangulate all leaf faces (ensure triangle assumption)
        2. Build vertex alpha map from texture sampling (auto-inverts if needed)
        3. Identify working faces:
           - Transition faces: have both opaque (>=threshold) and transparent (<threshold) vertices
           - Transparent faces: ALL vertices transparent AND at least one edge > target
           - Boundary faces: have at least one mesh boundary edge
        4. Delete small fully-transparent faces (all edges <= target)
        5. Subdivide long edges in working faces (edge_split affects all adjacent faces)
        6. Repeat steps 2-5 until no changes

    Key advantages:
        - Transition faces get densified first (the actual leaf silhouette boundary)
        - Transparent faces are subdivided only to make them small enough to delete
        - edge_split naturally propagates subdivision to neighboring faces
        - Auto-detects inverted alpha masks (black=opaque convention)
        - Only new midpoint vertices are added; original vertices are never moved

    Args:
        obj: Blender mesh object
        material_indices: Set of material indices for leaf geometry
        alpha_img: Alpha texture PIL Image (grayscale)
        threshold: Alpha threshold (0.0-1.0) - vertices below are "transparent"
        target_edge_factor: DEPRECATED - ignored when boundary_edge_mm is set.
        boundary_edge_mm: Target boundary edge length in millimeters (default: 0.5).
            Edges longer than this are subdivided at their midpoint.
            1 Blender unit = 1 meter = 1000 mm.
        max_iterations: Maximum subdivision iterations (default: 10)
        method: Trim method - "all" (delete only if ALL verts < threshold) or
                "average" (delete if avg < threshold). Default "all" is conservative.
    """
    try:
        mesh = obj.data
        if not mesh or not material_indices or alpha_img is None:
            return

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Detect if alpha mask needs inversion by sampling average alpha
        # If mean alpha < 0.5, the mask likely uses black=opaque convention
        invert_alpha = _detect_alpha_inversion(alpha_img)

        # Convert mm to Blender units (1 BU = 1 m = 1000 mm)
        target_edge_bu = max(0.0001, boundary_edge_mm / 1000.0)

        initial_face_count = len(mesh.polygons)

        # Limit face growth to prevent runaway subdivision
        # Allow up to 20x original face count for thorough boundary densification
        # This allows fine subdivision (0.05 factor) without hitting the limit
        max_face_count = initial_face_count * 20

        total_faces_deleted = 0

        # PRE-PROCESSING: Ensure mesh is fully triangulated before edge detection
        # This satisfies the algorithm requirement to check and triangulate if needed
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        leaf_faces_to_triangulate = [
            f
            for f in bm.faces
            if f.material_index in material_indices and len(f.verts) > 3
        ]
        if leaf_faces_to_triangulate:
            bmesh.ops.triangulate(bm, faces=leaf_faces_to_triangulate)

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        for iteration in range(max_iterations):
            # Check face count limit
            current_face_count = len(mesh.polygons)
            if current_face_count > max_face_count:
                break

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            # Get UV layer
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                bm.free()
                return

            # Build vertex alpha map by sampling texture at UV coordinates
            vert_alpha = {}
            vert_uv = {}
            for face in bm.faces:
                if face.material_index not in material_indices:
                    continue
                for loop in face.loops:
                    vi = loop.vert.index
                    uv = loop[uv_layer].uv
                    alpha = _sample_alpha_at_uv(
                        uv.x, uv.y, alpha_img, invert=invert_alpha
                    )
                    # Average if vertex seen multiple times
                    if vi in vert_alpha:
                        vert_alpha[vi] = (vert_alpha[vi] + alpha) / 2
                        old_uv = vert_uv[vi]
                        vert_uv[vi] = ((old_uv[0] + uv.x) / 2, (old_uv[1] + uv.y) / 2)
                    else:
                        vert_alpha[vi] = alpha
                        vert_uv[vi] = (uv.x, uv.y)

            leaf_faces_set = {
                f for f in bm.faces if f.material_index in material_indices
            }

            # STEP 1: Identify working faces - THREE categories:
            # A) Transition faces: have BOTH opaque and transparent vertices (alpha threshold crossing)
            # B) Transparent faces: ALL vertices transparent with long edges (need subdivision)
            # C) Boundary faces: have at least one mesh boundary edge
            working_faces = set()
            transition_faces = set()
            transparent_faces = set()

            for face in leaf_faces_set:
                if len(face.verts) != 3:
                    continue

                alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                has_opaque = any(a >= threshold for a in alphas)
                has_transparent = any(a < threshold for a in alphas)
                all_transparent = all(a < threshold for a in alphas)

                # Category A: Transition face (crosses threshold)
                if has_opaque and has_transparent:
                    transition_faces.add(face)
                    working_faces.add(face)

                # Category B: Fully transparent face with long edges
                elif all_transparent:
                    max_edge = max(e.calc_length() for e in face.edges)
                    if max_edge > target_edge_bu:
                        transparent_faces.add(face)
                        working_faces.add(face)

                # Category C: Boundary face (mesh edge)
                for edge in face.edges:
                    adj_count = sum(1 for f in edge.link_faces if f in leaf_faces_set)
                    if adj_count == 1:  # Boundary edge
                        working_faces.add(face)
                        break

            # STEP 2: Delete small fully-transparent faces
            faces_to_delete = []
            for face in leaf_faces_set:
                if len(face.verts) != 3:
                    continue

                alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                if not all(a < threshold for a in alphas):
                    continue

                # All edges must be short enough to delete
                max_edge = max(e.calc_length() for e in face.edges)
                if max_edge <= target_edge_bu:
                    faces_to_delete.append(face)

            if faces_to_delete:
                bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
                total_faces_deleted += len(faces_to_delete)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                # Rebuild working faces after deletion
                leaf_faces_set = {
                    f for f in bm.faces if f.material_index in material_indices
                }
                working_faces = set()

                for face in leaf_faces_set:
                    if len(face.verts) != 3:
                        continue

                    alphas = [vert_alpha.get(v.index, 1.0) for v in face.verts]
                    has_opaque = any(a >= threshold for a in alphas)
                    has_transparent = any(a < threshold for a in alphas)
                    all_transparent = all(a < threshold for a in alphas)

                    if has_opaque and has_transparent:
                        working_faces.add(face)
                    elif all_transparent:
                        max_edge = max(e.calc_length() for e in face.edges)
                        if max_edge > target_edge_bu:
                            working_faces.add(face)
                    else:
                        for edge in face.edges:
                            adj_count = sum(
                                1 for f in edge.link_faces if f in leaf_faces_set
                            )
                            if adj_count == 1:
                                working_faces.add(face)
                                break

            # STEP 3: Find edges to subdivide in working faces
            edges_to_split = set()
            for face in working_faces:
                for edge in face.edges:
                    if edge.calc_length() > target_edge_bu:
                        edges_to_split.add(edge)

            # Check stopping condition
            if not faces_to_delete and not edges_to_split:
                bm.to_mesh(mesh)
                bm.free()
                mesh.update()
                break

            # STEP 4: Split edges at midpoint
            for edge in edges_to_split:
                if edge.is_valid:
                    try:
                        bmesh.utils.edge_split(edge, edge.verts[0], 0.5)
                    except Exception:
                        pass

            # STEP 5: Triangulate any n-gons created by subdivision
            # Important: triangulate ALL n-gons in leaf geometry, not just working faces
            new_ngons = [
                f
                for f in bm.faces
                if len(f.verts) > 3 and f.material_index in material_indices
            ]
            if new_ngons:
                bmesh.ops.triangulate(bm, faces=new_ngons)

            # Update mesh and prepare for next iteration
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

        # After all iterations, ensure ALL faces are triangles for Nanite compatibility
        bm = bmesh.new()
        bm.from_mesh(mesh)
        ngons = [f for f in bm.faces if len(f.verts) > 3]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)

        # FINAL PASS: Delete triangles that are fully transparent
        # Now that we have small triangles, we can identify fully-transparent ones
        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            final_faces_to_delete = []
            for face in bm.faces:
                if face.material_index not in material_indices:
                    continue
                # Sample all vertices
                all_transparent = True
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    alpha = _sample_alpha_at_uv(
                        uv.x, uv.y, alpha_img, invert=invert_alpha
                    )
                    if alpha >= threshold:
                        all_transparent = False
                        break
                if all_transparent:
                    # Also check centroid
                    loop_uvs = [
                        (loop[uv_layer].uv.x, loop[uv_layer].uv.y)
                        for loop in face.loops
                    ]
                    center_u = sum(uv[0] for uv in loop_uvs) / len(loop_uvs)
                    center_v = sum(uv[1] for uv in loop_uvs) / len(loop_uvs)
                    center_alpha = _sample_alpha_at_uv(
                        center_u, center_v, alpha_img, invert=invert_alpha
                    )
                    if center_alpha < threshold:
                        final_faces_to_delete.append(face)

            if final_faces_to_delete:
                bmesh.ops.delete(bm, geom=final_faces_to_delete, context="FACES")
                total_faces_deleted += len(final_faces_to_delete)

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        mesh.update()
        final_vert_count = len(mesh.vertices)
        final_face_count = len(mesh.polygons)

        logger.info(
            "Alpha trim: %d->%d faces (%d deleted)",
            initial_face_count,
            final_face_count,
            total_faces_deleted,
        )

    except Exception as e:
        logger.warning("Alpha trim error: %s", e, exc_info=True)


def _smooth_boundary_edges(
    obj,
    leaf_material_indices: Set[int],
    alpha_img,
    threshold: float,
    smooth_iterations: int = 3,
    smooth_factor: float = 0.5,
    boundary_rings: int = 1,
):
    """Apply Laplacian smoothing to mesh boundary vertices after alpha trimming.

    This smooths the actual mesh edges (after face removal) to follow texture contours
    more naturally, reducing jagged appearance from regular subdivision grid.

    CRITICAL: Must be called AFTER alpha trimming, as it smooths the actual trimmed
    mesh boundary, not the pre-trim alpha threshold crossings.

    Args:
        obj: Blender mesh object (after alpha trimming)
        leaf_material_indices: Set of material indices for leaf geometry
        alpha_img: Not used - kept for API compatibility
        threshold: Not used - kept for API compatibility
        smooth_iterations: Number of smoothing passes (default: 3)
        smooth_factor: Smoothing strength per iteration (0.0-1.0, default: 0.5)
        boundary_rings: Width of boundary region to smooth (default: 1)
    """
    if smooth_iterations <= 0 or smooth_factor <= 0.0:
        return

    mesh = obj.data
    if not mesh:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Collect leaf faces
    leaf_faces = set()
    for face in bm.faces:
        if face.material_index in leaf_material_indices:
            leaf_faces.add(face)

    if not leaf_faces:
        bm.free()
        return

    # Find boundary vertices - vertices on edges with only one adjacent leaf face
    boundary_verts = set()
    for edge in bm.edges:
        # Count adjacent leaf faces
        adjacent_leaf_faces = sum(1 for f in edge.link_faces if f in leaf_faces)

        # Boundary edge has exactly 1 adjacent leaf face (outer perimeter)
        if adjacent_leaf_faces == 1:
            for vert in edge.verts:
                boundary_verts.add(vert)

    if not boundary_verts:
        bm.free()
        return

    # Expand boundary by boundary_rings
    all_leaf_verts = set()
    for face in leaf_faces:
        for vert in face.verts:
            all_leaf_verts.add(vert)

    current = set(boundary_verts)
    for _ in range(max(0, int(boundary_rings))):
        grow = set()
        for v in current:
            for edge in v.link_edges:
                for nb in edge.verts:
                    if nb in all_leaf_verts and nb not in boundary_verts:
                        grow.add(nb)
        if not grow:
            break
        boundary_verts.update(grow)
        current = grow

    # Apply Laplacian smoothing to boundary vertices
    for iteration in range(smooth_iterations):
        # Calculate new positions
        new_positions = {}
        for vert in boundary_verts:
            # Get connected vertices through edges
            neighbors = []
            for edge in vert.link_edges:
                for nb in edge.verts:
                    if nb != vert and nb in all_leaf_verts:
                        neighbors.append(nb)

            if not neighbors:
                continue

            # Average neighbor positions
            avg_pos = mathutils.Vector((0, 0, 0))
            for nb in neighbors:
                avg_pos += nb.co
            avg_pos /= len(neighbors)

            # Blend between original and averaged position
            new_pos = vert.co.lerp(avg_pos, smooth_factor)
            new_positions[vert] = new_pos

        # Apply new positions
        for vert, new_pos in new_positions.items():
            vert.co = new_pos

    # Write back to mesh
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _cleanup_boundary_spikes(
    obj,
    leaf_material_indices: Set[int],
    iterations: int = 2,
    area_factor: float = 0.2,
    short_len_factor: float = 0.25,
    angle_deg: float = 55.0,
):
    """Remove tiny boundary spike faces and collapse very short boundary edges.

    Targets sliver triangles created by alpha-based trimming that point inwards or
    stick out as small spikes. Heuristics:
      - Delete faces with >=2 boundary edges and very small area
      - Prefer deletion when the angle between the two boundary edges at the tip
        is sharp (below angle_deg)
      - Collapse boundary edges that are much shorter than the typical boundary
        edge length

    Args:
        obj: Blender mesh object (after alpha trimming)
        leaf_material_indices: Set of material indices for leaf geometry
        iterations: How many cleanup passes to run
        area_factor: Threshold as a fraction of median leaf-face area
        short_len_factor: Boundary edge collapse threshold as fraction of median
        angle_deg: Max angle at spike tip to qualify for deletion
    """
    mesh = obj.data
    if not mesh:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    leaf_faces = [f for f in bm.faces if f.material_index in leaf_material_indices]
    leaf_faces = [f for f in bm.faces if f.material_index in leaf_material_indices]
    if not leaf_faces:
        bm.free()
        return

    face_areas = [f.calc_area() for f in leaf_faces]
    if not face_areas:
        bm.free()
        return

    # Robust median area for thresholds
    sorted_areas = sorted(face_areas)
    median_area = sorted_areas[len(sorted_areas) // 2] or 1e-12

    # Boundary edge length stats
    boundary_edges = []
    leaf_face_set = set(leaf_faces)
    for e in bm.edges:
        if sum(1 for f in e.link_faces if f in leaf_face_set) == 1:
            boundary_edges.append(e)
    if boundary_edges:
        lengths = [e.calc_length() for e in boundary_edges]
        lengths.sort()
        median_len = lengths[len(lengths) // 2] or 1e-9
    else:
        median_len = 1e-9

    short_len_thresh = median_len * max(0.0, float(short_len_factor))
    spike_angle = math.radians(max(1.0, float(angle_deg)))

    for _ in range(max(1, int(iterations))):
        to_delete = set()

        for f in list(leaf_faces):
            # Count boundary edges for this face
            b_edges = [
                e
                for e in f.edges
                if sum(1 for lf in e.link_faces if lf in leaf_face_set) == 1
            ]
            if len(b_edges) < 2:
                continue

            area = f.calc_area()
            # Angle at the common vertex of two boundary edges (if exists)
            sharp = False
            if len(b_edges) >= 2:
                v_common = None
                s0 = set(b_edges[0].verts)
                s1 = set(b_edges[1].verts)
                inter = s0 & s1
                if inter:
                    v_common = list(inter)[0]
                if v_common is not None:
                    # Build vectors along the two edges from the common vertex
                    vecs = []
                    for e in b_edges[:2]:
                        other = e.other_vert(v_common)
                        v = other.co - v_common.co
                        if v.length_squared > 0:
                            vecs.append(v.normalized())
                    if len(vecs) == 2:
                        try:
                            ang = vecs[0].angle(vecs[1])
                            sharp = ang < spike_angle
                        except Exception:
                            sharp = False

            if area < median_area * area_factor or sharp:
                to_delete.add(f)

        if to_delete:
            bmesh.ops.delete(bm, geom=list(to_delete), context="FACES")
            # Refresh cached collections
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            # Rebuild leaf face list after deletions
            leaf_faces = [
                f for f in bm.faces if f.material_index in leaf_material_indices
            ]
            leaf_face_set = set(leaf_faces)

        # Collapse very short boundary edges
        to_collapse = [
            e
            for e in bm.edges
            if sum(1 for lf in e.link_faces if lf in leaf_face_set) == 1
            and e.calc_length() < short_len_thresh
        ]
        if to_collapse:
            try:
                bmesh.ops.collapse(bm, edges=to_collapse)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
            except Exception:
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _is_likely_tube_component(component, boundary_edge_set):
    """Check if a component with boundary edges is a 3D volume (cylinder,
    acorn, berry) rather than a flat leaf plane.

    Uses three signals:
    - Flatness (PCA): leaves have one near-zero principal dimension; 3D shapes
      (acorns, cylinders) have meaningful extent in all three axes
    - Boundary loop count: tubes have 2 loops (both ends open) or 1 (one capped)
    - Boundary vertex ratio: tubes have few boundary verts relative to total
    """
    comp_boundary = set()
    comp_verts = set()
    for f in component:
        for e in f.edges:
            if e in boundary_edge_set:
                comp_boundary.add(e)
        for v in f.verts:
            comp_verts.add(v)

    if len(comp_verts) < 8:
        return False

    # Flatness check via PCA -- catches 3D shapes (acorns, berries) that a
    # topological test alone misclassifies when they have a stem hole.
    coords = np.array([v.co[:] for v in comp_verts], dtype=np.float32)
    centered = coords - coords.mean(axis=0)
    try:
        sv = np.linalg.svd(centered, compute_uv=False)
        if sv[0] > 0 and (sv[2] / sv[0]) >= 0.08:
            return True
    except np.linalg.LinAlgError:
        pass

    if not comp_boundary:
        return False

    # Count boundary loops (connected components of boundary edges)
    boundary_visited = set()
    loop_count = 0
    for start_edge in comp_boundary:
        if start_edge in boundary_visited:
            continue
        loop_count += 1
        stack = [start_edge]
        while stack:
            edge = stack.pop()
            if edge in boundary_visited:
                continue
            boundary_visited.add(edge)
            for v in edge.verts:
                for linked_edge in v.link_edges:
                    if (
                        linked_edge in comp_boundary
                        and linked_edge not in boundary_visited
                    ):
                        stack.append(linked_edge)

    comp_boundary_verts = set()
    for e in comp_boundary:
        for v in e.verts:
            comp_boundary_verts.add(v)

    boundary_vert_ratio = len(comp_boundary_verts) / len(comp_verts)

    # 2+ boundary loops (both ends open) with moderate boundary ratio -> tube
    if loop_count >= 2 and boundary_vert_ratio < 0.5:
        return True

    # Single open end (one end capped): very low boundary ratio -> tube
    if loop_count == 1 and boundary_vert_ratio < 0.15:
        return True

    return False


def _apply_interior_decimate(
    obj,
    ratio: float = 0.5,
    boundary_rings: int = 1,
    interior_edge_mm: float = 0.0,
):
    """Apply topology-based interior decimation on leaf/needle geometry.

    Classifies mesh faces by connected component topology:
    - Tube components (no boundary edges) = branch cylinders -> protected
    - Open-ended tube components (boundary at uncapped ends) -> protected
    - Plane components (has boundary edges) = leaves/needles -> interior decimated

    Boundary vertices (leaf silhouette edges) are also protected, so only the
    interior of leaf planes gets simplified.

    When interior_edge_mm > 0, the decimation ratio is computed automatically
    from the current average interior edge length so the result converges to
    the requested edge size regardless of input resolution.  The explicit ratio
    parameter is ignored in that case.

    The ratio is passed directly to Blender's Decimate modifier.  Protected
    vertices (boundary rings + tube verts) are shielded via an inverted vertex
    group, so collapse operates only on the interior.

    Args:
        obj: Blender mesh object (should be called AFTER alpha trimming)
        ratio: Decimation ratio (0.0-1.0, lower = more reduction).
            Ignored when interior_edge_mm > 0.
        boundary_rings: Number of vertex rings to protect around boundary
        interior_edge_mm: Target average interior edge length in millimeters.
            0 = disabled (use ratio instead).
    """
    if interior_edge_mm <= 0 and (ratio <= 0.0 or ratio >= 1.0):
        return

    mesh = obj.data
    if not mesh:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # Find boundary edges (edges with exactly 1 adjacent face)
    boundary_edge_set = set()
    for edge in bm.edges:
        if len(edge.link_faces) == 1:
            boundary_edge_set.add(edge)

    # Find connected face components and classify each
    visited = set()
    tube_verts = set()
    plane_faces = set()
    plane_verts = set()

    for start_face in bm.faces:
        if start_face in visited:
            continue
        component = set()
        stack = [start_face]
        while stack:
            face = stack.pop()
            if face in visited:
                continue
            visited.add(face)
            component.add(face)
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor not in visited:
                        stack.append(neighbor)

        has_boundary = any(e in boundary_edge_set for f in component for e in f.edges)
        if not has_boundary or _is_likely_tube_component(component, boundary_edge_set):
            for f in component:
                for v in f.verts:
                    tube_verts.add(v)
        else:
            plane_faces.update(component)
            for f in component:
                for v in f.verts:
                    plane_verts.add(v)

    if not plane_faces:
        bm.free()
        return

    # Find boundary vertices on plane components (leaf silhouette edges)
    boundary_verts = set()
    for edge in boundary_edge_set:
        for vert in edge.verts:
            boundary_verts.add(vert)

    if not boundary_verts:
        bm.free()
        return

    # Expand boundary protection by boundary_rings
    current = set(boundary_verts)
    for _ in range(max(0, int(boundary_rings))):
        grow = set()
        for v in current:
            for edge in v.link_edges:
                for nb in edge.verts:
                    if nb in plane_verts and nb not in boundary_verts:
                        grow.add(nb)
        if not grow:
            break
        boundary_verts.update(grow)
        current = grow

    # Protect: boundary verts (silhouette) + tube verts (branches) + non-mesh verts
    preserve_indices = {v.index for v in boundary_verts}
    preserve_indices.update(v.index for v in tube_verts)

    total_verts = len(bm.verts)
    decimatable = total_verts - len(preserve_indices)
    total_faces = len(bm.faces)

    # Compute ratio from interior_edge_mm when specified
    if interior_edge_mm > 0:
        target_bu = interior_edge_mm / 1000.0
        interior_edges = [
            e
            for e in bm.edges
            if all(v not in boundary_verts and v not in tube_verts for v in e.verts)
        ]
        if interior_edges:
            avg_interior = sum(e.calc_length() for e in interior_edges) / len(
                interior_edges
            )
            # Face count scales as 1/edge_length^2, so keeping
            # (current / target)^2 of faces yields the target edge length.
            if avg_interior > 0 and avg_interior < target_bu:
                ratio = min(0.95, (avg_interior / target_bu) ** 2)
                ratio = max(0.05, ratio)
            elif avg_interior >= target_bu:
                bm.free()
                return
        else:
            bm.free()
            return

    bm.free()

    if decimatable <= 0:
        logger.debug(
            "Interior decimate: skipped (no interior verts to decimate, "
            "%d tube + %d boundary = all verts protected)",
            len(tube_verts),
            len(boundary_verts),
        )
        return

    logger.info(
        "Interior decimate: %d tube verts protected, "
        "%d boundary verts protected, %d/%d verts decimatable (ratio %.3f)",
        len(tube_verts),
        len(boundary_verts),
        decimatable,
        total_verts,
        ratio,
    )

    # Use the edit-mode decimate operator on only interior faces.
    # This makes `ratio` scale against the selected interior, not the global
    # face count -- so ratio=0.3 actually keeps 30% of interior faces.
    # The DECIMATE modifier with a vertex group uses a global ratio and
    # saturates when protected verts dominate, requiring absurdly small values.
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    # Mark interior faces (and their verts/edges) as selected.
    for v in mesh.vertices:
        v.select = v.index not in preserve_indices
    for e in mesh.edges:
        e.select = all(vi not in preserve_indices for vi in e.vertices)
    for p in mesh.polygons:
        p.select = all(vi not in preserve_indices for vi in p.vertices)

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.decimate(ratio=float(ratio))
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
