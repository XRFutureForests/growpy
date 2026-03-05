"""OBJ/MTL export for Helios++ LiDAR simulation.

Converts USDA tree assemblies to Wavefront OBJ with baked twig instances
and Helios-compatible MTL materials. Post-processing step that runs after
USDA export without modifying the existing pipeline.

Each tree produces one OBJ file with trunk/branch geometry plus all twig
instances baked (transformed and merged) into the mesh. Twig prototypes
are auto-decimated to reduce polygon count.

Material groups:
    bark      - Trunk and branch geometry (helios_spectra wood)
    leaves    - All baked twig geometry (helios_spectra conifer or deciduous)

When classify_twig_materials is enabled, twig geometry is split into:
    twig_wood - Twig branch/stem cylinders (helios_spectra wood)
    twig_leaf - Twig leaf/needle planes (helios_spectra conifer or deciduous)
"""

import math
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import bpy
import numpy as np

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

from pxr import Gf, Sdf, Usd, UsdGeom

# Cache decimated twig meshes per (twig_file, ratio) to avoid re-decimation
_decimated_twig_cache: Dict[Tuple[str, float], Tuple[np.ndarray, np.ndarray]] = {}

# Cache classified twig meshes per (twig_file, ratio)
# Values: (verts, wood_faces, leaf_faces)
_classified_twig_cache: Dict[
    Tuple[str, float], Tuple[np.ndarray, np.ndarray, np.ndarray]
] = {}


def clear_twig_decimate_cache() -> None:
    """Clear the decimated twig mesh cache. Call at start of new export session."""
    global _decimated_twig_cache, _classified_twig_cache
    _decimated_twig_cache.clear()
    _classified_twig_cache.clear()


def _classify_twig_faces(
    verts: np.ndarray, faces: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Classify twig faces into wood (tube) and leaf (plane) components.

    Uses boundary-edge topology: tube components (branches) have no boundary
    edges or low boundary-vertex ratio. Plane components (leaves/needles)
    have boundary edges around their perimeter.

    Mirrors the heuristic in twig_export.py _is_likely_tube_component() but
    operates on numpy arrays without Blender dependency.

    Args:
        verts: (N, 3) vertex positions
        faces: (M, 3) triangle indices

    Returns:
        Tuple of (wood_mask, leaf_mask) boolean arrays over faces
    """
    num_faces = len(faces)
    if num_faces == 0:
        empty = np.zeros(0, dtype=bool)
        return empty, empty

    # Build edge-to-face adjacency
    # Each face contributes 3 edges (sorted vertex pairs)
    edge_faces: Dict[Tuple[int, int], List[int]] = {}
    for fi in range(num_faces):
        for ei in range(3):
            v0, v1 = int(faces[fi, ei]), int(faces[fi, (ei + 1) % 3])
            edge_key = (min(v0, v1), max(v0, v1))
            if edge_key not in edge_faces:
                edge_faces[edge_key] = []
            edge_faces[edge_key].append(fi)

    # Boundary edges: adjacent to exactly 1 face
    boundary_edges = {e for e, fl in edge_faces.items() if len(fl) == 1}

    # Build face adjacency for flood fill
    face_neighbors: Dict[int, List[int]] = {i: [] for i in range(num_faces)}
    for fl in edge_faces.values():
        if len(fl) == 2:
            face_neighbors[fl[0]].append(fl[1])
            face_neighbors[fl[1]].append(fl[0])

    # Find connected face components
    visited = np.zeros(num_faces, dtype=bool)
    wood_mask = np.zeros(num_faces, dtype=bool)

    for start in range(num_faces):
        if visited[start]:
            continue

        # Flood fill component
        component = []
        stack = [start]
        while stack:
            fi = stack.pop()
            if visited[fi]:
                continue
            visited[fi] = True
            component.append(fi)
            for nb in face_neighbors[fi]:
                if not visited[nb]:
                    stack.append(nb)

        # Collect boundary edges and vertices for this component
        comp_boundary_edges = set()
        comp_verts = set()
        for fi in component:
            for ei in range(3):
                v0, v1 = int(faces[fi, ei]), int(faces[fi, (ei + 1) % 3])
                edge_key = (min(v0, v1), max(v0, v1))
                if edge_key in boundary_edges:
                    comp_boundary_edges.add(edge_key)
            for vi in range(3):
                comp_verts.add(int(faces[fi, vi]))

        # No boundary edges -> closed surface -> tube
        if not comp_boundary_edges:
            for fi in component:
                wood_mask[fi] = True
            continue

        # Too small to classify reliably
        if len(comp_verts) < 8:
            continue

        # Count boundary loops (connected components of boundary edges)
        boundary_visited: set = set()
        loop_count = 0
        for start_edge in comp_boundary_edges:
            if start_edge in boundary_visited:
                continue
            loop_count += 1
            edge_stack = [start_edge]
            while edge_stack:
                edge = edge_stack.pop()
                if edge in boundary_visited:
                    continue
                boundary_visited.add(edge)
                # Find adjacent boundary edges (share a vertex)
                for v in edge:
                    for other_edge in comp_boundary_edges:
                        if other_edge not in boundary_visited and v in other_edge:
                            edge_stack.append(other_edge)

        # Boundary vertex ratio
        comp_boundary_verts = set()
        for e in comp_boundary_edges:
            comp_boundary_verts.add(e[0])
            comp_boundary_verts.add(e[1])
        boundary_vert_ratio = len(comp_boundary_verts) / len(comp_verts)

        # 2+ boundary loops with moderate boundary ratio -> tube (both ends open)
        if loop_count >= 2 and boundary_vert_ratio < 0.5:
            for fi in component:
                wood_mask[fi] = True
            continue

        # Single open end with very low boundary ratio -> tube (one end capped)
        if loop_count == 1 and boundary_vert_ratio < 0.15:
            for fi in component:
                wood_mask[fi] = True

    leaf_mask = ~wood_mask
    return wood_mask, leaf_mask


def _extract_tree_mesh(
    assembly_usda_path: Path,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    classify_twigs: bool = False,
) -> Optional[tuple]:
    """Extract tree mesh data from USDA assembly without writing files.

    Reads the assembly USDA and its referenced skeletal tree mesh,
    extracts twig instance data from PointInstancer, decimates geometry,
    and bakes all twig instances.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons)
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0)
        classify_twigs: Split twig faces into wood/leaf by topology

    Returns:
        Without classification: (trunk_verts, trunk_faces, twig_verts, twig_faces)
        With classification: (trunk_verts, trunk_faces, twig_wood_verts, twig_wood_faces,
                              twig_leaf_verts, twig_leaf_faces)
        None on failure
    """
    tree_dir = assembly_usda_path.parent

    # Find the stems skeletal USDA (not twig/foliage skeletal files)
    skeletal_files = list(tree_dir.glob("*_stems_skeletal.usda"))
    if not skeletal_files:
        skeletal_files = list(tree_dir.glob("*_skeletal.usda"))
    if not skeletal_files:
        print(f"  OBJ export: No skeletal USDA found in {tree_dir}")
        return None
    skeletal_path = skeletal_files[0]

    # Read trunk/branch mesh from skeletal USDA
    trunk_verts, trunk_faces, _trunk_uvs = _read_tree_mesh(skeletal_path)
    if trunk_verts is None:
        print(f"  OBJ export: Failed to read tree mesh from {skeletal_path}")
        return None

    # Decimate stem/branch geometry
    if 0.0 < stem_decimate_ratio < 1.0:
        trunk_verts, trunk_faces = _decimate_mesh(
            trunk_verts, trunk_faces, stem_decimate_ratio
        )

    # Read twig instance data from assembly USDA
    instancer_data = _read_twig_instancer(assembly_usda_path)

    _empty_v = np.empty((0, 3), dtype=np.float64)
    _empty_f = np.empty((0, 3), dtype=np.int64)

    if classify_twigs:
        twig_wood_verts, twig_wood_faces = _empty_v.copy(), _empty_f.copy()
        twig_leaf_verts, twig_leaf_faces = _empty_v.copy(), _empty_f.copy()
    else:
        twig_verts, twig_faces = _empty_v.copy(), _empty_f.copy()

    if instancer_data is not None:
        positions, orientations, scales, proto_indices, proto_files = instancer_data

        if classify_twigs:
            # Classified path: separate wood/leaf per prototype
            classified_protos: Dict[
                int, Tuple[np.ndarray, np.ndarray, np.ndarray]
            ] = {}
            for idx, twig_file in proto_files.items():
                twig_path = tree_dir / twig_file
                if not twig_path.exists():
                    continue

                cache_key = (str(twig_path), decimate_ratio)
                if cache_key in _classified_twig_cache:
                    classified_protos[idx] = _classified_twig_cache[cache_key]
                    continue

                twig_result = _read_twig_mesh(twig_path)
                if twig_result[0] is None or twig_result[1] is None:
                    continue
                raw_verts, raw_faces = twig_result[0], twig_result[1]

                if 0.0 < decimate_ratio < 1.0:
                    dec_verts, dec_faces = _decimate_mesh(
                        raw_verts, raw_faces, decimate_ratio
                    )
                else:
                    dec_verts, dec_faces = raw_verts, raw_faces

                wood_mask, leaf_mask = _classify_twig_faces(dec_verts, dec_faces)
                classified_protos[idx] = (dec_verts, dec_faces[wood_mask], dec_faces[leaf_mask])
                _classified_twig_cache[cache_key] = classified_protos[idx]

            if classified_protos:
                twig_wood_verts, twig_wood_faces, twig_leaf_verts, twig_leaf_faces = (
                    _bake_classified_twig_instances(
                        classified_protos, positions, orientations, scales, proto_indices
                    )
                )
        else:
            # Unclassified path: all twig faces together
            proto_meshes = {}
            for idx, twig_file in proto_files.items():
                twig_path = tree_dir / twig_file
                if not twig_path.exists():
                    continue

                cache_key = (str(twig_path), decimate_ratio)
                if cache_key in _decimated_twig_cache:
                    proto_meshes[idx] = _decimated_twig_cache[cache_key]
                    continue

                twig_result = _read_twig_mesh(twig_path)
                if twig_result[0] is None or twig_result[1] is None:
                    continue
                raw_verts, raw_faces = twig_result[0], twig_result[1]

                if 0.0 < decimate_ratio < 1.0:
                    dec_verts, dec_faces = _decimate_mesh(
                        raw_verts, raw_faces, decimate_ratio
                    )
                else:
                    dec_verts, dec_faces = raw_verts, raw_faces

                proto_meshes[idx] = (dec_verts, dec_faces)
                _decimated_twig_cache[cache_key] = (dec_verts, dec_faces)

            if proto_meshes:
                twig_verts, twig_faces = _bake_twig_instances(
                    proto_meshes, positions, orientations, scales, proto_indices
                )

    if classify_twigs:
        return trunk_verts, trunk_faces, twig_wood_verts, twig_wood_faces, twig_leaf_verts, twig_leaf_faces

    return trunk_verts, trunk_faces, twig_verts, twig_faces


def convert_tree_to_obj(
    assembly_usda_path: Path,
    species_name: str,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    helios_spectra_leaves: str = "deciduous",
    classify_twigs: bool = False,
) -> Optional[Path]:
    """Convert a tree's USDA assembly to an individual OBJ file with baked twigs.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        species_name: Species name for texture/material lookup
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons)
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0)
        helios_spectra_leaves: Helios spectra type for leaves ("conifer" or "deciduous")
        classify_twigs: Split twig faces into wood/leaf materials

    Returns:
        Path to generated OBJ file, or None on failure
    """
    mesh_data = _extract_tree_mesh(
        assembly_usda_path, decimate_ratio, stem_decimate_ratio,
        classify_twigs=classify_twigs,
    )
    if mesh_data is None:
        return None

    tree_dir = assembly_usda_path.parent
    helios_name = assembly_usda_path.stem.replace("_assembly", "_helios")
    obj_path = tree_dir / f"{helios_name}.obj"
    mtl_name = f"{helios_name}.mtl"
    mtl_path = tree_dir / mtl_name
    bark_texture = _find_bark_texture(tree_dir)

    if classify_twigs:
        trunk_verts, trunk_faces, tw_verts, tw_faces, tl_verts, tl_faces = mesh_data
        _write_obj(
            obj_path, trunk_verts, trunk_faces, None,
            np.empty((0, 3)), np.empty((0, 3), dtype=np.int64), mtl_name,
            twig_wood_verts=tw_verts, twig_wood_faces=tw_faces,
            twig_leaf_verts=tl_verts, twig_leaf_faces=tl_faces,
        )
        _write_helios_mtl(mtl_path, bark_texture, helios_spectra_leaves, classify_twigs=True)
        print(
            f"  OBJ export: {obj_path.name} ({len(trunk_faces)} trunk + "
            f"{len(tw_faces)} twig_wood + {len(tl_faces)} twig_leaf faces)"
        )
    else:
        trunk_verts, trunk_faces, twig_verts, twig_faces = mesh_data
        _write_obj(
            obj_path, trunk_verts, trunk_faces, None, twig_verts, twig_faces, mtl_name
        )
        _write_helios_mtl(mtl_path, bark_texture, helios_spectra_leaves)
        print(
            f"  OBJ export: {obj_path.name} ({len(trunk_faces)} trunk + {len(twig_faces)} twig faces)"
        )

    return obj_path


def _read_tree_mesh(
    skeletal_path: Path,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Read tree mesh geometry from skeletal USDA.

    Returns:
        Tuple of (vertices[N,3], faces[M,3], uvs[M*3,2]) or (None, None, None)
    """
    stage = Usd.Stage.Open(str(skeletal_path))
    if not stage:
        return None, None, None

    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if mesh_prim is None:
        return None, None, None

    mesh = UsdGeom.Mesh(mesh_prim)

    points = mesh.GetPointsAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()

    if not points or not face_counts or not face_indices:
        return None, None, None

    vertices = np.array([[p[0], p[1], p[2]] for p in points], dtype=np.float64)

    # Build face array (assumes triangulated - all counts = 3)
    faces = np.array(face_indices, dtype=np.int64).reshape(-1, 3)

    # Read UVs (faceVarying - one UV per face-vertex)
    uvs = None
    primvars_api = UsdGeom.PrimvarsAPI(mesh)
    st_primvar = primvars_api.GetPrimvar("st")
    if st_primvar and st_primvar.IsDefined():
        uv_data = st_primvar.Get()
        if uv_data:
            uvs = np.array([[uv[0], uv[1]] for uv in uv_data], dtype=np.float64)

    return vertices, faces, uvs


def _read_twig_instancer(
    assembly_path: Path,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]]:
    """Read PointInstancer data and prototype file references from assembly USDA.

    Returns:
        Tuple of (positions[N,3], orientations[N,4], scales[N,3], proto_indices[N], proto_files{idx: filename})
        or None if no instancer found
    """
    # Read raw layer for prototype references (avoids instance proxy issues)
    layer = Sdf.Layer.FindOrOpen(str(assembly_path))
    if not layer:
        return None

    # Also open a composed stage for instancer attribute values
    stage = Usd.Stage.Open(str(assembly_path))
    if not stage:
        return None

    # Find PointInstancer
    instancer_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.PointInstancer):
            instancer_prim = prim
            break

    if instancer_prim is None:
        return None

    instancer = UsdGeom.PointInstancer(instancer_prim)

    raw_positions = instancer.GetPositionsAttr().Get()
    raw_orientations = instancer.GetOrientationsAttr().Get()
    raw_scales = instancer.GetScalesAttr().Get()
    raw_proto_indices = instancer.GetProtoIndicesAttr().Get()

    if not raw_positions or not raw_proto_indices:
        return None

    positions = np.array([[p[0], p[1], p[2]] for p in raw_positions], dtype=np.float64)
    orientations = np.array(
        [
            [o.GetReal(), o.GetImaginary()[0], o.GetImaginary()[1], o.GetImaginary()[2]]
            for o in raw_orientations
        ],
        dtype=np.float64,
    )
    scales = np.array([[s[0], s[1], s[2]] for s in raw_scales], dtype=np.float64)
    proto_indices = np.array(raw_proto_indices, dtype=np.int64)

    # Extract twig USDA filenames from prototype references via Sdf layer
    proto_targets = instancer.GetPrototypesRel().GetTargets()
    proto_files = {}

    for idx, proto_sdf_path in enumerate(proto_targets):
        proto_spec = layer.GetPrimAtPath(proto_sdf_path)
        if not proto_spec:
            continue

        # Each prototype Xform has a child SkelRoot that references the twig USDA
        for child_spec in proto_spec.nameChildren:
            refs = child_spec.referenceList.prependedItems
            for ref in refs:
                asset_path = ref.assetPath
                filename = asset_path.lstrip("./")
                proto_files[idx] = filename
                break
            break

    return positions, orientations, scales, proto_indices, proto_files


def _read_twig_mesh(
    twig_path: Path,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Read twig mesh geometry from USDA file.

    Returns:
        Tuple of (vertices[N,3], faces[M,3]) or (None, None)
    """
    stage = Usd.Stage.Open(str(twig_path))
    if not stage:
        return None, None

    # Find first mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if mesh_prim is None:
        return None, None

    mesh = UsdGeom.Mesh(mesh_prim)
    points = mesh.GetPointsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()

    if not points or not face_indices:
        return None, None

    vertices = np.array([[p[0], p[1], p[2]] for p in points], dtype=np.float64)

    # Handle mixed face sizes (triangles and quads)
    faces = []
    idx = 0
    for count in face_counts:
        if count == 3:
            faces.append(face_indices[idx : idx + 3])
        elif count == 4:
            # Triangulate quad
            a, b, c, d = face_indices[idx : idx + 4]
            faces.append([a, b, c])
            faces.append([a, c, d])
        idx += count

    if not faces:
        return None, None

    return vertices, np.array(faces, dtype=np.int64)


def _decimate_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    ratio: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Decimate mesh using Blender's DECIMATE modifier.

    Args:
        vertices: (N, 3) vertex positions
        faces: (M, 3) triangle indices
        ratio: Decimation ratio (0.0-1.0, lower = more reduction)

    Returns:
        Tuple of (decimated_vertices, decimated_faces)
    """
    import bpy

    # Create temporary mesh in Blender
    mesh_data = bpy.data.meshes.new("_helios_decimate_temp")
    mesh_data.from_pydata(
        vertices.tolist(),
        [],
        faces.tolist(),
    )
    mesh_data.update()

    obj = bpy.data.objects.new("_helios_decimate_temp", mesh_data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add and apply DECIMATE modifier
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio

    # Apply modifier using depsgraph evaluation (avoids bpy.ops context issues)
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

    # Clean up Blender objects
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_data, do_unlink=True)

    if len(result_verts) == 0 or len(result_faces) == 0:
        return vertices, faces

    return result_verts, result_faces


def _quat_to_rotation_matrix(w: float, x: float, y: float, z: float) -> np.ndarray:
    """Convert quaternion (w, x, y, z) to 3x3 rotation matrix."""
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _bake_twig_instances(
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray]],
    positions: np.ndarray,
    orientations: np.ndarray,
    scales: np.ndarray,
    proto_indices: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Transform and merge all twig instances into a single combined mesh.

    Returns:
        Tuple of (combined_vertices[N,3], combined_faces[M,3])
    """
    all_verts = []
    all_faces = []
    vert_offset = 0

    for i in range(len(positions)):
        proto_idx = proto_indices[i]
        if proto_idx not in proto_meshes:
            continue

        proto_verts, proto_faces = proto_meshes[proto_idx]
        if len(proto_verts) == 0:
            continue

        # Build transform: v_out = rotation @ (scale * v_in) + position
        w, x, y, z = orientations[i]
        rot = _quat_to_rotation_matrix(w, x, y, z)
        scale = scales[i]
        pos = positions[i]

        scaled = proto_verts * scale
        transformed = (rot @ scaled.T).T + pos

        all_verts.append(transformed)
        all_faces.append(proto_faces + vert_offset)
        vert_offset += len(proto_verts)

    if not all_verts:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int64)

    return np.vstack(all_verts), np.vstack(all_faces)


def _bake_classified_twig_instances(
    classified_protos: Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]],
    positions: np.ndarray,
    orientations: np.ndarray,
    scales: np.ndarray,
    proto_indices: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Transform and merge classified twig instances into wood and leaf meshes.

    Args:
        classified_protos: {proto_idx: (verts, wood_faces, leaf_faces)}

    Returns:
        (wood_verts, wood_faces, leaf_verts, leaf_faces)
    """
    wood_verts_list: List[np.ndarray] = []
    wood_faces_list: List[np.ndarray] = []
    leaf_verts_list: List[np.ndarray] = []
    leaf_faces_list: List[np.ndarray] = []
    wood_vert_offset = 0
    leaf_vert_offset = 0

    for i in range(len(positions)):
        proto_idx = proto_indices[i]
        if proto_idx not in classified_protos:
            continue

        proto_verts, proto_wood_faces, proto_leaf_faces = classified_protos[proto_idx]
        if len(proto_verts) == 0:
            continue

        w, x, y, z = orientations[i]
        rot = _quat_to_rotation_matrix(w, x, y, z)
        scale = scales[i]
        pos = positions[i]

        scaled = proto_verts * scale
        transformed = (rot @ scaled.T).T + pos

        if len(proto_wood_faces) > 0:
            wood_verts_list.append(transformed)
            wood_faces_list.append(proto_wood_faces + wood_vert_offset)
            wood_vert_offset += len(proto_verts)

        if len(proto_leaf_faces) > 0:
            leaf_verts_list.append(transformed)
            leaf_faces_list.append(proto_leaf_faces + leaf_vert_offset)
            leaf_vert_offset += len(proto_verts)

    _empty_v = np.empty((0, 3), dtype=np.float64)
    _empty_f = np.empty((0, 3), dtype=np.int64)

    wood_verts = np.vstack(wood_verts_list) if wood_verts_list else _empty_v
    wood_faces = np.vstack(wood_faces_list) if wood_faces_list else _empty_f
    leaf_verts = np.vstack(leaf_verts_list) if leaf_verts_list else _empty_v
    leaf_faces = np.vstack(leaf_faces_list) if leaf_faces_list else _empty_f

    return wood_verts, wood_faces, leaf_verts, leaf_faces


def _find_bark_texture(tree_dir: Path) -> Optional[Path]:
    """Find bark texture in tree output directory."""
    textures_dir = tree_dir / "textures"
    if not textures_dir.exists():
        return None

    for ext in [".jpg", ".jpeg", ".png"]:
        for f in textures_dir.glob(f"*bark*{ext}"):
            return f

    return None


def _fmt_vert(v: np.ndarray, up_axis: str) -> str:
    """Format a vertex for OBJ output, applying coordinate transform if needed."""
    if up_axis == "z":
        return f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n"
    # Z-up to Y-up: x, y, z -> x, z, -y
    return f"v {v[0]:.6f} {v[2]:.6f} {-v[1]:.6f}\n"


def _write_obj(
    obj_path: Path,
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    twig_verts: np.ndarray,
    twig_faces: np.ndarray,
    mtl_name: str,
    up_axis: str = "y",
    twig_wood_verts: Optional[np.ndarray] = None,
    twig_wood_faces: Optional[np.ndarray] = None,
    twig_leaf_verts: Optional[np.ndarray] = None,
    twig_leaf_faces: Optional[np.ndarray] = None,
) -> None:
    """Write Wavefront OBJ file with material groups.

    When twig_wood_verts/twig_leaf_verts are provided (classified mode),
    writes 3 material groups: bark, twig_wood, twig_leaf.
    Otherwise writes 2 groups: bark, leaves.
    """
    classified = twig_wood_verts is not None and twig_leaf_verts is not None
    has_uvs = trunk_uvs is not None and len(trunk_uvs) > 0
    trunk_vert_count = len(trunk_verts)

    with open(obj_path, "w") as f:
        f.write(f"# Helios++ tree mesh\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # Write all vertices
        for v in trunk_verts:
            f.write(_fmt_vert(v, up_axis))

        if classified:
            for v in twig_wood_verts:
                f.write(_fmt_vert(v, up_axis))
            for v in twig_leaf_verts:
                f.write(_fmt_vert(v, up_axis))
        else:
            for v in twig_verts:
                f.write(_fmt_vert(v, up_axis))

        f.write("\n")

        # Write UVs
        if has_uvs:
            for uv in trunk_uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Dummy UVs for twig vertices
        total_twig_faces = (
            (len(twig_wood_faces) + len(twig_leaf_faces))
            if classified
            else len(twig_faces)
        )
        if total_twig_faces > 0:
            f.write(f"vt 0.0 0.0\n")
            twig_uv_start = len(trunk_uvs) + 1 if has_uvs else 1
        else:
            twig_uv_start = 0

        f.write("\n")

        # Trunk faces (bark material)
        f.write("usemtl bark\n")
        if has_uvs:
            for fi, face in enumerate(trunk_faces):
                uv_base = fi * 3
                f.write(
                    f"f {face[0]+1}/{uv_base+1} {face[1]+1}/{uv_base+2} {face[2]+1}/{uv_base+3}\n"
                )
        else:
            for face in trunk_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        if classified:
            # Twig wood faces
            wood_offset = trunk_vert_count
            if len(twig_wood_faces) > 0:
                f.write("\nusemtl twig_wood\n")
                for face in twig_wood_faces:
                    v0 = face[0] + wood_offset + 1
                    v1 = face[1] + wood_offset + 1
                    v2 = face[2] + wood_offset + 1
                    if has_uvs:
                        f.write(
                            f"f {v0}/{twig_uv_start} {v1}/{twig_uv_start} {v2}/{twig_uv_start}\n"
                        )
                    else:
                        f.write(f"f {v0} {v1} {v2}\n")

            # Twig leaf faces
            leaf_offset = trunk_vert_count + len(twig_wood_verts)
            if len(twig_leaf_faces) > 0:
                f.write("\nusemtl twig_leaf\n")
                for face in twig_leaf_faces:
                    v0 = face[0] + leaf_offset + 1
                    v1 = face[1] + leaf_offset + 1
                    v2 = face[2] + leaf_offset + 1
                    if has_uvs:
                        f.write(
                            f"f {v0}/{twig_uv_start} {v1}/{twig_uv_start} {v2}/{twig_uv_start}\n"
                        )
                    else:
                        f.write(f"f {v0} {v1} {v2}\n")
        else:
            # Unclassified: all twig faces as leaves
            if len(twig_faces) > 0:
                f.write("\nusemtl leaves\n")
                for face in twig_faces:
                    v0 = face[0] + trunk_vert_count + 1
                    v1 = face[1] + trunk_vert_count + 1
                    v2 = face[2] + trunk_vert_count + 1
                    if has_uvs:
                        f.write(
                            f"f {v0}/{twig_uv_start} {v1}/{twig_uv_start} {v2}/{twig_uv_start}\n"
                        )
                    else:
                        f.write(f"f {v0} {v1} {v2}\n")


def write_combined_obj(
    tree_meshes: List[tuple],
    output_path: Path,
    helios_spectra_leaves: str = "deciduous",
    up_axis: str = "y",
    classify_twigs: bool = False,
) -> Path:
    """Merge all tree meshes into a single combined OBJ at CSV positions.

    Works directly from numpy arrays -- no individual OBJ files needed.

    Args:
        tree_meshes: List of tuples. Without classification:
            (trunk_verts, trunk_faces, twig_verts, twig_faces, x, y, z)
            With classification:
            (trunk_verts, trunk_faces, tw_verts, tw_faces, tl_verts, tl_faces, x, y, z)
        output_path: Path to write the combined OBJ file
        helios_spectra_leaves: Helios spectra type for leaves material
        classify_twigs: Whether tree_meshes contain classified twig data

    Returns:
        Path to generated combined OBJ file
    """
    mtl_name = output_path.stem + ".mtl"
    mtl_path = output_path.with_suffix(".mtl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_bark_verts: List[np.ndarray] = []
    all_bark_faces: List[np.ndarray] = []
    bark_vert_offset = 0

    if classify_twigs:
        all_tw_verts: List[np.ndarray] = []
        all_tw_faces: List[np.ndarray] = []
        all_tl_verts: List[np.ndarray] = []
        all_tl_faces: List[np.ndarray] = []
        tw_vert_offset = 0
        tl_vert_offset = 0

        for entry in tree_meshes:
            trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f, x, y, z = entry
            offset = np.array([x, y, z], dtype=np.float64)

            all_bark_verts.append(trunk_verts + offset)
            all_bark_faces.append(trunk_faces + bark_vert_offset)
            bark_vert_offset += len(trunk_verts)

            if len(tw_v) > 0:
                all_tw_verts.append(tw_v + offset)
                all_tw_faces.append(tw_f + tw_vert_offset)
                tw_vert_offset += len(tw_v)

            if len(tl_v) > 0:
                all_tl_verts.append(tl_v + offset)
                all_tl_faces.append(tl_f + tl_vert_offset)
                tl_vert_offset += len(tl_v)

        bark_verts = np.vstack(all_bark_verts) if all_bark_verts else np.empty((0, 3))
        bark_faces = np.vstack(all_bark_faces) if all_bark_faces else np.empty((0, 3), dtype=np.int64)
        tw_verts = np.vstack(all_tw_verts) if all_tw_verts else np.empty((0, 3))
        tw_faces = np.vstack(all_tw_faces) if all_tw_faces else np.empty((0, 3), dtype=np.int64)
        tl_verts = np.vstack(all_tl_verts) if all_tl_verts else np.empty((0, 3))
        tl_faces = np.vstack(all_tl_faces) if all_tl_faces else np.empty((0, 3), dtype=np.int64)

        total_bark_verts = len(bark_verts)
        total_tw_verts = len(tw_verts)

        with open(output_path, "w") as f:
            f.write("# Helios++ combined forest mesh\n")
            f.write(f"mtllib {mtl_name}\n\n")

            for v in bark_verts:
                f.write(_fmt_vert(v, up_axis))
            for v in tw_verts:
                f.write(_fmt_vert(v, up_axis))
            for v in tl_verts:
                f.write(_fmt_vert(v, up_axis))

            f.write("\n")

            f.write("usemtl bark\n")
            for face in bark_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

            if len(tw_faces) > 0:
                f.write("\nusemtl twig_wood\n")
                for face in tw_faces:
                    v0 = face[0] + total_bark_verts + 1
                    v1 = face[1] + total_bark_verts + 1
                    v2 = face[2] + total_bark_verts + 1
                    f.write(f"f {v0} {v1} {v2}\n")

            if len(tl_faces) > 0:
                f.write("\nusemtl twig_leaf\n")
                for face in tl_faces:
                    v0 = face[0] + total_bark_verts + total_tw_verts + 1
                    v1 = face[1] + total_bark_verts + total_tw_verts + 1
                    v2 = face[2] + total_bark_verts + total_tw_verts + 1
                    f.write(f"f {v0} {v1} {v2}\n")

        total_verts = len(bark_verts) + len(tw_verts) + len(tl_verts)
        total_faces = len(bark_faces) + len(tw_faces) + len(tl_faces)
        print(
            f"  Combined OBJ: {output_path.name} ({total_verts} verts, {total_faces} faces, "
            f"{len(tw_faces)} twig_wood + {len(tl_faces)} twig_leaf, {len(tree_meshes)} trees)"
        )

    else:
        all_leaf_verts: List[np.ndarray] = []
        all_leaf_faces: List[np.ndarray] = []
        leaf_vert_offset = 0

        for entry in tree_meshes:
            trunk_verts, trunk_faces, twig_verts, twig_faces, x, y, z = entry
            offset = np.array([x, y, z], dtype=np.float64)

            all_bark_verts.append(trunk_verts + offset)
            all_bark_faces.append(trunk_faces + bark_vert_offset)
            bark_vert_offset += len(trunk_verts)

            if len(twig_verts) > 0:
                all_leaf_verts.append(twig_verts + offset)
                all_leaf_faces.append(twig_faces + leaf_vert_offset)
                leaf_vert_offset += len(twig_verts)

        bark_verts = np.vstack(all_bark_verts) if all_bark_verts else np.empty((0, 3))
        bark_faces = np.vstack(all_bark_faces) if all_bark_faces else np.empty((0, 3), dtype=np.int64)
        leaf_verts = np.vstack(all_leaf_verts) if all_leaf_verts else np.empty((0, 3))
        leaf_faces = np.vstack(all_leaf_faces) if all_leaf_faces else np.empty((0, 3), dtype=np.int64)

        total_bark_verts = len(bark_verts)

        with open(output_path, "w") as f:
            f.write("# Helios++ combined forest mesh\n")
            f.write(f"mtllib {mtl_name}\n\n")

            for v in bark_verts:
                f.write(_fmt_vert(v, up_axis))
            for v in leaf_verts:
                f.write(_fmt_vert(v, up_axis))

            f.write("\n")

            f.write("usemtl bark\n")
            for face in bark_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

            if len(leaf_faces) > 0:
                f.write("\nusemtl leaves\n")
                for face in leaf_faces:
                    v0 = face[0] + total_bark_verts + 1
                    v1 = face[1] + total_bark_verts + 1
                    v2 = face[2] + total_bark_verts + 1
                    f.write(f"f {v0} {v1} {v2}\n")

        total_verts = len(bark_verts) + len(leaf_verts)
        total_faces = len(bark_faces) + len(leaf_faces)
        print(
            f"  Combined OBJ: {output_path.name} ({total_verts} verts, {total_faces} faces, {len(tree_meshes)} trees)"
        )

    _write_helios_mtl(
        mtl_path, bark_texture=None, helios_spectra_leaves=helios_spectra_leaves,
        classify_twigs=classify_twigs,
    )
    return output_path


def _write_helios_mtl(
    mtl_path: Path,
    bark_texture: Optional[Path],
    helios_spectra_leaves: str = "deciduous",
    classify_twigs: bool = False,
) -> None:
    """Write Helios-compatible MTL file.

    Helios++ uses custom MTL properties:
        helios_spectra  - ECOSTRESS spectral library identifier
        helios_classification - ASPRS point classification (4 = high vegetation)

    When classify_twigs is True, writes twig_wood and twig_leaf materials
    instead of a single leaves material.
    """
    with open(mtl_path, "w") as f:
        f.write("# Helios++ compatible material\n\n")

        # Bark material (trunk/branches)
        f.write("newmtl bark\n")
        f.write("Ka 0.1 0.1 0.1\n")
        f.write("Kd 0.4 0.3 0.2\n")
        f.write("Ks 0.05 0.05 0.05\n")
        if bark_texture:
            rel_texture = f"textures/{bark_texture.name}"
            f.write(f"map_Kd {rel_texture}\n")
        f.write("helios_spectra wood\n")
        f.write("helios_classification 4\n")
        f.write("\n")

        if classify_twigs:
            # Twig wood material (twig branch cylinders)
            f.write("newmtl twig_wood\n")
            f.write("Ka 0.1 0.1 0.1\n")
            f.write("Kd 0.35 0.25 0.15\n")
            f.write("Ks 0.05 0.05 0.05\n")
            f.write("helios_spectra wood\n")
            f.write("helios_classification 4\n")
            f.write("\n")

            # Twig leaf material (leaf/needle planes)
            f.write("newmtl twig_leaf\n")
            f.write("Ka 0.1 0.15 0.05\n")
            f.write("Kd 0.3 0.5 0.15\n")
            f.write("Ks 0.2 0.2 0.2\n")
            f.write(f"helios_spectra {helios_spectra_leaves}\n")
            f.write("helios_classification 4\n")
        else:
            # Combined leaves material
            f.write("newmtl leaves\n")
            f.write("Ka 0.1 0.15 0.05\n")
            f.write("Kd 0.3 0.5 0.15\n")
            f.write("Ks 0.2 0.2 0.2\n")
            f.write(f"helios_spectra {helios_spectra_leaves}\n")
            f.write("helios_classification 4\n")


CONIFER_KEYWORDS = [
    "spruce",
    "pine",
    "fir",
    "cedar",
    "cypress",
    "juniper",
    "larch",
    "hemlock",
    "yew",
    "redwood",
    "sequoia",
    "thuja",
]


def export_forest_obj(
    output_dir: Path,
    csv_path: Path,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    generate_scene_xml: bool = False,
    individual_obj: bool = False,
    up_axis: str = "y",
    classify_twigs: bool = False,
) -> List[Tuple[Path, float, float, float, str]]:
    """Export all USDA tree assemblies to a combined OBJ for Helios++.

    Extracts mesh data from USDA assemblies and writes a single combined
    OBJ with all trees positioned at their CSV coordinates. Optionally
    also writes individual per-tree OBJ files.

    Args:
        output_dir: Forest output directory containing species/tree_* subdirs.
        csv_path: Input CSV with tree positions (x, y, z, fid columns).
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons).
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0).
        generate_scene_xml: Generate Helios++ scene XML with tree positions.
        individual_obj: Also write individual per-tree OBJ files (default: False).
        up_axis: Coordinate up axis for OBJ output ("y" or "z").
        classify_twigs: Split twig faces into wood/leaf materials by topology.

    Returns:
        List of (obj_path, x, y, z, species_name) tuples for exported trees.
    """
    import pandas as pd

    clear_twig_decimate_cache()

    # Find all assembly USDA files (exclude skeletal/static/twig files)
    assembly_files = []
    for usda in output_dir.glob("*/tree_*/*.usda"):
        if usda.stem.endswith("_skeletal") or usda.stem.endswith("_static"):
            continue
        if "twig" in usda.stem.lower():
            continue
        assembly_files.append(usda)

    if not assembly_files:
        print("OBJ export: No assembly USDA files found")
        return []

    print(f"\n{'='*60}")
    print(f"HELIOS OBJ EXPORT ({len(assembly_files)} trees)")
    if classify_twigs:
        print("  Twig material classification: enabled")
    print(f"{'='*60}")

    forest_data = pd.read_csv(csv_path)
    if "fid" not in forest_data.columns:
        forest_data["fid"] = range(1, len(forest_data) + 1)
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    tree_meshes: List[tuple] = []
    obj_files: List[Tuple[Path, float, float, float, str]] = []

    for assembly_path in sorted(assembly_files):
        tree_dir_name = assembly_path.parent.name
        tree_id_str = tree_dir_name.replace("tree_", "")

        species_dir = assembly_path.parent.parent.name
        species_name = species_dir.replace("_", " ").title()

        is_conifer = any(kw in species_dir.lower() for kw in CONIFER_KEYWORDS)
        spectra = "conifer" if is_conifer else "deciduous"

        mesh_data = _extract_tree_mesh(
            assembly_usda_path=assembly_path,
            decimate_ratio=decimate_ratio,
            stem_decimate_ratio=stem_decimate_ratio,
            classify_twigs=classify_twigs,
        )
        if mesh_data is None:
            continue

        # Look up CSV position
        try:
            fid = int(tree_id_str)
            row = forest_data[forest_data["fid"] == fid].iloc[0]
            x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
        except (ValueError, IndexError):
            x, y, z = 0.0, 0.0, 0.0

        if classify_twigs:
            trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f = mesh_data
            print(
                f"  Extracted: {assembly_path.parent.name} "
                f"({len(trunk_faces)} trunk + {len(tw_f)} twig_wood + {len(tl_f)} twig_leaf faces)"
            )
            tree_meshes.append((trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f, x, y, z))

            if individual_obj:
                tree_dir = assembly_path.parent
                helios_name = assembly_path.stem.replace("_assembly", "_helios")
                obj_path = tree_dir / f"{helios_name}.obj"
                mtl_name = f"{helios_name}.mtl"
                mtl_path = tree_dir / mtl_name

                _write_obj(
                    obj_path, trunk_verts, trunk_faces, None,
                    np.empty((0, 3)), np.empty((0, 3), dtype=np.int64), mtl_name,
                    up_axis=up_axis,
                    twig_wood_verts=tw_v, twig_wood_faces=tw_f,
                    twig_leaf_verts=tl_v, twig_leaf_faces=tl_f,
                )
                bark_texture = _find_bark_texture(tree_dir)
                _write_helios_mtl(mtl_path, bark_texture, spectra, classify_twigs=True)
                print(f"  OBJ export: {obj_path.name}")
                obj_files.append((obj_path, x, y, z, species_name))
            else:
                obj_files.append((Path(""), x, y, z, species_name))
        else:
            trunk_verts, trunk_faces, twig_verts, twig_faces = mesh_data
            print(
                f"  Extracted: {assembly_path.parent.name} "
                f"({len(trunk_faces)} trunk + {len(twig_faces)} twig faces)"
            )
            tree_meshes.append((trunk_verts, trunk_faces, twig_verts, twig_faces, x, y, z))

            if individual_obj:
                tree_dir = assembly_path.parent
                helios_name = assembly_path.stem.replace("_assembly", "_helios")
                obj_path = tree_dir / f"{helios_name}.obj"
                mtl_name = f"{helios_name}.mtl"
                mtl_path = tree_dir / mtl_name

                _write_obj(
                    obj_path, trunk_verts, trunk_faces, None,
                    twig_verts, twig_faces, mtl_name, up_axis=up_axis,
                )
                bark_texture = _find_bark_texture(tree_dir)
                _write_helios_mtl(mtl_path, bark_texture, spectra)
                print(f"  OBJ export: {obj_path.name}")
                obj_files.append((obj_path, x, y, z, species_name))
            else:
                obj_files.append((Path(""), x, y, z, species_name))

    # Always write combined OBJ
    if tree_meshes:
        is_conifer_forest = any(
            any(kw in sp.lower() for kw in CONIFER_KEYWORDS)
            for _, _, _, _, sp in obj_files
        )
        spectra = "conifer" if is_conifer_forest else "deciduous"
        combined_path = output_dir / "forest_combined.obj"
        write_combined_obj(
            tree_meshes=tree_meshes,
            output_path=combined_path,
            helios_spectra_leaves=spectra,
            up_axis=up_axis,
            classify_twigs=classify_twigs,
        )

    if generate_scene_xml and tree_meshes:
        from growpy.io.helios_scene import generate_helios_scene

        combined_path = output_dir / "forest_combined.obj"
        scene_path = output_dir / "helios_scene.xml"
        generate_helios_scene(
            tree_entries=[(combined_path, 0.0, 0.0, 0.0, "forest")],
            output_path=scene_path,
        )

    print(f"\nOBJ export complete: {len(tree_meshes)} trees")
    return obj_files
