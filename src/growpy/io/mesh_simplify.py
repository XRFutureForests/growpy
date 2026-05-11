"""Material-aware mesh simplification for Helios++ OBJ export.

Applies per-material simplification ratios to in-memory mesh arrays
between _bake_twig_instances() and _write_obj(). Wood materials (bark,
twigs) get reduced while leaf materials preserve shape for LAI accuracy.

Material classification uses the same WOOD_KEYWORDS as the MTL writer:
material names containing "twig", "bark", "branch", "wood", or "stem"
are classified as wood. Names containing "fruit" are classified as fruit.
Everything else is treated as leaf geometry.
"""

import gc as gc_module
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

WOOD_KEYWORDS = ("twig", "bark", "branch", "wood", "stem")
FRUIT_KEYWORDS = ("fruit",)

# Meshes above this face count use chunked decimation to limit peak RAM.
# Each chunk stays below this size during Blender decimation.
CHUNK_FACE_LIMIT = 10_000_000


def classify_material(material_name: str) -> str:
    """Classify a material name as 'bark', 'wood', 'fruit', or 'leaf'.

    'bark' is the literal trunk/branch material.
    'wood' covers twig wood sub-materials.
    'fruit' covers fruit sub-materials (e.g. EuropeanOakFruits).
    'leaf' is everything else (leaves, etc.).
    """
    if material_name == "bark":
        return "bark"
    lower = material_name.lower()
    if any(kw in lower for kw in WOOD_KEYWORDS):
        return "wood"
    if any(kw in lower for kw in FRUIT_KEYWORDS):
        return "fruit"
    return "leaf"


def simplify_trunk_mesh(
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    ratio: float,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """Simplify trunk/bark mesh using Blender's quadric decimation.

    For large meshes (>CHUNK_FACE_LIMIT faces), splits spatially into
    height bands and decimates each chunk independently.  This keeps peak
    RAM proportional to chunk size instead of total mesh size.

    Args:
        trunk_verts: (N, 3) vertex positions
        trunk_faces: (M, 3) triangle indices
        trunk_uvs: Optional (M*3, 2) per-face-vertex UVs
        ratio: Target ratio of triangles to keep (0.0-1.0)

    Returns:
        Tuple of (simplified_verts, simplified_faces, simplified_uvs).
        UVs are set to None after decimation (Helios uses spectra, not textures).
    """
    if ratio >= 1.0 or len(trunk_faces) == 0:
        return trunk_verts, trunk_faces, trunk_uvs

    num_faces = len(trunk_faces)

    if num_faces > CHUNK_FACE_LIMIT:
        dec_verts, dec_faces = _decimate_chunked(
            trunk_verts, trunk_faces, ratio, CHUNK_FACE_LIMIT,
        )
        return dec_verts, dec_faces, None

    dec_verts, dec_faces = _decimate_with_bpy(trunk_verts, trunk_faces, ratio)
    return dec_verts, dec_faces, None


def simplify_twig_meshes(
    twig_verts: np.ndarray,
    per_proto_faces: Dict[int, np.ndarray],
    per_proto_uvs: Dict[int, np.ndarray],
    per_proto_face_mats: Dict[int, np.ndarray],
    proto_materials: Dict[int, Tuple[str, object, Optional[List[str]]]],
    simplification_ratios: Dict[str, float],
) -> Tuple[np.ndarray, Dict[int, np.ndarray], Dict[int, np.ndarray], Dict[int, np.ndarray]]:
    """Simplify twig meshes per material sub-group.

    For each prototype, splits faces by sub-material (leaf vs wood),
    applies the configured ratio to each group, and reassembles.

    Args:
        twig_verts: (N, 3) combined twig vertices
        per_proto_faces: {proto_idx: faces[M, 3]}
        per_proto_uvs: {proto_idx: uvs[K, 2]}
        per_proto_face_mats: {proto_idx: face_mat_indices[M]}
        proto_materials: {proto_idx: (mat_name, diffuse_path, sidecar_mat_names)}
        simplification_ratios: {'bark': r, 'wood': r, 'leaf': r, 'fruit': r}

    Returns:
        Tuple of (new_twig_verts, new_per_proto_faces, new_per_proto_uvs, new_per_proto_face_mats)
    """
    if not per_proto_faces or len(twig_verts) == 0:
        return twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats

    bark_ratio = simplification_ratios.get("bark", 1.0)
    wood_ratio = simplification_ratios.get("wood", 1.0)
    leaf_ratio = simplification_ratios.get("leaf", 1.0)
    fruit_ratio = simplification_ratios.get("fruit", 1.0)

    # If nothing to simplify, return as-is
    if bark_ratio >= 1.0 and wood_ratio >= 1.0 and leaf_ratio >= 1.0 and fruit_ratio >= 1.0:
        return twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats

    new_verts_list = []
    new_per_proto_faces = {}
    new_per_proto_uvs = {}
    new_per_proto_face_mats = {}
    vert_offset = 0

    for proto_idx in sorted(per_proto_faces.keys()):
        faces = per_proto_faces[proto_idx]
        if len(faces) == 0:
            new_per_proto_faces[proto_idx] = faces
            continue

        face_mats = per_proto_face_mats.get(proto_idx)
        _, _, sidecar_mat_names = proto_materials.get(proto_idx, ("", None, None))

        if face_mats is not None and sidecar_mat_names:
            # Split faces by material classification (bark vs wood vs leaf vs fruit)
            result_verts, result_faces, result_face_mats = _simplify_proto_by_material(
                twig_verts, faces, face_mats, sidecar_mat_names,
                bark_ratio, wood_ratio, leaf_ratio, fruit_ratio, vert_offset,
            )
        else:
            # No sub-material info: apply leaf ratio (preserve by default)
            result_verts, result_faces_raw = _extract_and_simplify(
                twig_verts, faces, leaf_ratio,
            )
            result_faces = result_faces_raw + vert_offset
            result_face_mats = face_mats

        new_verts_list.append(result_verts)
        new_per_proto_faces[proto_idx] = result_faces
        new_per_proto_face_mats[proto_idx] = result_face_mats
        new_per_proto_uvs[proto_idx] = np.empty((0, 2), dtype=np.float64)
        vert_offset += len(result_verts)

    if new_verts_list:
        new_twig_verts = np.vstack(new_verts_list)
    else:
        new_twig_verts = np.empty((0, 3), dtype=np.float64)

    return new_twig_verts, new_per_proto_faces, new_per_proto_uvs, new_per_proto_face_mats


def simplify_prototype(
    verts: np.ndarray,
    faces: np.ndarray,
    uvs: Optional[np.ndarray],
    face_mats: Optional[np.ndarray],
    sidecar_mat_names: Optional[List[str]],
    simplification_ratios: Dict[str, float],
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """Simplify a single twig prototype mesh by material classification.

    Applied BEFORE baking instances so memory savings scale with instance count.
    For 100k instances, simplifying the 1 prototype is far cheaper than
    simplifying 100k baked copies.

    Args:
        verts: (N, 3) prototype vertices
        faces: (M, 3) prototype faces
        uvs: Optional (K, 2) per-face-vertex UVs
        face_mats: Optional (M,) per-face material indices
        sidecar_mat_names: Optional list of material names from sidecar JSON
        simplification_ratios: {'bark': r, 'wood': r, 'leaf': r, 'fruit': r}

    Returns:
        (simplified_verts, simplified_faces, simplified_uvs, simplified_face_mats)
    """
    bark_ratio = simplification_ratios.get("bark", 1.0)
    wood_ratio = simplification_ratios.get("wood", 1.0)
    leaf_ratio = simplification_ratios.get("leaf", 1.0)
    fruit_ratio = simplification_ratios.get("fruit", 1.0)

    if bark_ratio >= 1.0 and wood_ratio >= 1.0 and leaf_ratio >= 1.0 and fruit_ratio >= 1.0:
        return verts, faces, uvs, face_mats

    if len(faces) == 0:
        return verts, faces, uvs, face_mats

    if face_mats is not None and sidecar_mat_names:
        result_verts, result_faces, result_face_mats = _simplify_proto_by_material(
            verts, faces, face_mats, sidecar_mat_names,
            bark_ratio, wood_ratio, leaf_ratio, fruit_ratio, 0,
        )
        return result_verts, result_faces, None, result_face_mats

    # No sub-material info: apply leaf ratio
    result_verts, result_faces = _extract_and_simplify(verts, faces, leaf_ratio)
    return result_verts, result_faces, None, face_mats


def _simplify_proto_by_material(
    all_verts: np.ndarray,
    faces: np.ndarray,
    face_mats: np.ndarray,
    sidecar_mat_names: List[str],
    bark_ratio: float,
    wood_ratio: float,
    leaf_ratio: float,
    fruit_ratio: float,
    global_offset: int,
) -> Tuple[np.ndarray, Optional[np.ndarray], np.ndarray]:
    """Simplify a single prototype's faces split by bark/wood/leaf/fruit material.

    Returns:
        (combined_verts, combined_faces_with_offset, combined_face_mats)
    """
    unique_mat_ids = sorted(set(face_mats.tolist()))
    result_verts_list = []
    result_faces_list = []
    result_mats_list = []
    local_offset = 0

    for mat_id in unique_mat_ids:
        blend_name = sidecar_mat_names[mat_id] if mat_id < len(sidecar_mat_names) else ""
        mat_class = classify_material(blend_name)
        if mat_class == "bark":
            ratio = bark_ratio
        elif mat_class == "wood":
            ratio = wood_ratio
        elif mat_class == "fruit":
            ratio = fruit_ratio
        else:
            ratio = leaf_ratio

        mask = face_mats == mat_id
        sub_faces = faces[mask]

        if len(sub_faces) == 0:
            continue

        sub_verts, sub_faces_reindexed = _extract_and_simplify(
            all_verts, sub_faces, ratio,
        )

        result_verts_list.append(sub_verts)
        result_faces_list.append(sub_faces_reindexed + global_offset + local_offset)
        result_mats_list.append(np.full(len(sub_faces_reindexed), mat_id, dtype=np.int32))
        local_offset += len(sub_verts)

    if not result_verts_list:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int64), np.empty(0, dtype=np.int32)

    return (
        np.vstack(result_verts_list),
        np.vstack(result_faces_list),
        np.concatenate(result_mats_list),
    )


def _extract_and_simplify(
    all_verts: np.ndarray,
    faces: np.ndarray,
    ratio: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract vertices used by faces, simplify, and return with reindexed faces.

    Args:
        all_verts: Full vertex array
        faces: (M, 3) face indices into all_verts
        ratio: Decimation ratio (0.0-1.0)

    Returns:
        (extracted_verts, reindexed_faces) where face indices are 0-based
    """
    used = np.unique(faces.ravel())
    old_to_new = np.full(len(all_verts), -1, dtype=np.int64)
    old_to_new[used] = np.arange(len(used))

    sub_verts = all_verts[used]
    sub_faces = old_to_new[faces.ravel()].reshape(-1, 3)

    if ratio < 1.0 and len(sub_faces) > 0:
        sub_verts, sub_faces = _decimate_with_bpy(sub_verts, sub_faces, ratio)

    return sub_verts, sub_faces


def _decimate_chunked(
    vertices: np.ndarray,
    faces: np.ndarray,
    ratio: float,
    chunk_limit: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Decimate a large mesh by splitting into spatial chunks along the Z axis.

    Each chunk is decimated independently via Blender, then results are
    concatenated.  Peak RAM stays proportional to ``chunk_limit`` instead
    of total face count.  Boundary seams between chunks are negligible for
    Helios spectra-based simulation.

    Args:
        vertices: (N, 3) vertex positions
        faces: (M, 3) triangle indices
        ratio: Target ratio of faces to keep (0.0-1.0)
        chunk_limit: Max faces per chunk sent to Blender

    Returns:
        (concatenated_verts, concatenated_faces)
    """
    num_faces = len(faces)
    n_chunks = max(1, int(np.ceil(num_faces / chunk_limit)))
    print(
        f"  Chunked decimation: {num_faces:,} faces -> {n_chunks} chunks "
        f"(~{chunk_limit:,} faces each, ratio {ratio})"
    )

    # Compute face centroids along Z axis for spatial splitting
    face_z = vertices[faces, 2].mean(axis=1)

    # Quantile-based split for roughly equal chunk sizes
    percentiles = np.linspace(0, 100, n_chunks + 1)
    boundaries = np.percentile(face_z, percentiles)

    all_verts: List[np.ndarray] = []
    all_faces: List[np.ndarray] = []
    vert_offset = 0

    for i in range(n_chunks):
        lo, hi = boundaries[i], boundaries[i + 1]
        if i < n_chunks - 1:
            mask = (face_z >= lo) & (face_z < hi)
        else:
            mask = face_z >= lo

        chunk_faces_global = faces[mask]
        if len(chunk_faces_global) == 0:
            continue

        # Extract only the vertices referenced by this chunk
        used_ids = np.unique(chunk_faces_global.ravel())
        old_to_new = np.empty(len(vertices), dtype=np.int64)
        old_to_new[used_ids] = np.arange(len(used_ids))
        chunk_verts = vertices[used_ids]
        chunk_faces_local = old_to_new[chunk_faces_global.ravel()].reshape(-1, 3)

        print(
            f"    Chunk {i + 1}/{n_chunks}: {len(chunk_faces_local):,} faces, "
            f"{len(chunk_verts):,} verts (z={lo:.1f}..{hi:.1f})"
        )

        dec_v, dec_f = _decimate_with_bpy(chunk_verts, chunk_faces_local, ratio)

        # Free chunk inputs before accumulating results
        del chunk_verts, chunk_faces_local, chunk_faces_global, used_ids, old_to_new
        gc_module.collect()

        all_verts.append(dec_v)
        all_faces.append(dec_f + vert_offset)
        vert_offset += len(dec_v)

        del dec_v, dec_f
        gc_module.collect()

    if not all_verts:
        return vertices, faces

    result_verts = np.vstack(all_verts)
    result_faces = np.vstack(all_faces)
    del all_verts, all_faces
    gc_module.collect()

    total_in = num_faces
    total_out = len(result_faces)
    print(f"  Chunked decimation done: {total_in:,} -> {total_out:,} faces")
    return result_verts, result_faces


def _decimate_with_bpy(
    vertices: np.ndarray,
    faces: np.ndarray,
    ratio: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Decimate mesh using Blender's DECIMATE modifier (quadric collapse).

    Same approach as the existing _decimate_mesh in obj_export.py but
    isolated here for the simplification module.
    """
    import bpy

    mesh_data = bpy.data.meshes.new("_simplify_temp")
    mesh_data.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh_data.update()

    obj = bpy.data.objects.new("_simplify_temp", mesh_data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data

    result_verts = np.array(
        [[v.co.x, v.co.y, v.co.z] for v in eval_mesh.vertices], dtype=np.float64
    )
    result_faces = np.array(
        [
            [p.vertices[0], p.vertices[1], p.vertices[2]]
            for p in eval_mesh.polygons
            if len(p.vertices) == 3
        ],
        dtype=np.int64,
    )

    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_data, do_unlink=True)

    if len(result_verts) == 0 or len(result_faces) == 0:
        return vertices, faces

    return result_verts, result_faces


def simplify_tree_mesh(
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    twig_verts: np.ndarray,
    per_proto_faces: Dict[int, np.ndarray],
    per_proto_uvs: Dict[int, np.ndarray],
    per_proto_face_mats: Dict[int, np.ndarray],
    proto_materials: Dict[int, Tuple[str, object, Optional[List[str]]]],
    simplification_ratios: Dict[str, float],
) -> Tuple[
    np.ndarray, np.ndarray, Optional[np.ndarray],
    np.ndarray, Dict[int, np.ndarray], Dict[int, np.ndarray], Dict[int, np.ndarray],
]:
    """Apply material-aware simplification to a complete tree mesh.

    Top-level function called from convert_tree_to_obj_direct and
    convert_tree_to_obj, between bake_twig_instances and _write_obj.

    Args:
        trunk_verts, trunk_faces, trunk_uvs: Trunk/bark geometry
        twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats: Twig geometry
        proto_materials: Material metadata per prototype
        simplification_ratios: {'bark': 0.3, 'wood': 0.3, 'leaf': 1.0, 'fruit': 0.3}

    Returns:
        Simplified versions of all input arrays.
    """
    bark_ratio = simplification_ratios.get("bark", 1.0)
    has_work = (
        bark_ratio < 1.0
        or simplification_ratios.get("wood", 1.0) < 1.0
        or simplification_ratios.get("leaf", 1.0) < 1.0
        or simplification_ratios.get("fruit", 1.0) < 1.0
    )
    if not has_work:
        return (
            trunk_verts, trunk_faces, trunk_uvs,
            twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
        )

    start = time.time()
    orig_trunk_faces = len(trunk_faces)
    orig_twig_faces = sum(len(f) for f in per_proto_faces.values())

    # Simplify trunk
    trunk_verts, trunk_faces, trunk_uvs = simplify_trunk_mesh(
        trunk_verts, trunk_faces, trunk_uvs, bark_ratio,
    )

    # Simplify twigs by material
    twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats = simplify_twig_meshes(
        twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
        proto_materials, simplification_ratios,
    )

    new_trunk_faces = len(trunk_faces)
    new_twig_faces = sum(len(f) for f in per_proto_faces.values())
    elapsed = time.time() - start
    print(
        f"  Simplification: trunk {orig_trunk_faces} -> {new_trunk_faces} faces, "
        f"twigs {orig_twig_faces} -> {new_twig_faces} faces ({elapsed:.1f}s)"
    )

    return (
        trunk_verts, trunk_faces, trunk_uvs,
        twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
    )
