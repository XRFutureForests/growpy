"""OBJ/MTL export for Helios++ LiDAR simulation.

Converts USDA tree assemblies to Wavefront OBJ with baked twig instances
and Helios-compatible MTL materials. Post-processing step that runs after
USDA export without modifying the existing pipeline.

Each tree produces one OBJ file with trunk/branch geometry plus all twig
instances baked (transformed and merged) into the mesh. Twig prototypes
are auto-decimated to reduce polygon count.

Twig geometry is classified into wood and leaf using material bindings
from static USDA files (sourced from .blend originals).

Material groups:
    bark      - Trunk and branch geometry (helios_spectra wood)
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

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

WOOD_MATERIAL_KEYWORDS = ("bark", "branch", "wood", "dead", "stem", "twig")

# Cache classified twig meshes per (twig_file, ratio)
# Values: (verts, wood_faces, leaf_faces)
_classified_twig_cache: Dict[
    Tuple[str, float], Tuple[np.ndarray, np.ndarray, np.ndarray]
] = {}


def clear_twig_decimate_cache() -> None:
    """Clear the classified twig mesh cache. Call at start of new export session."""
    global _classified_twig_cache
    _classified_twig_cache.clear()


def _resolve_to_static(filename: str) -> str:
    """Convert a skeletal USDA filename to its static counterpart."""
    return filename.replace("_skeletal.usda", "_static.usda")


def _read_twig_mesh_classified(
    twig_path: Path,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Read twig mesh from static USDA and classify faces by material bindings.

    Uses material names to separate wood (bark/branch/wood/dead) from leaf faces.
    Static USDA files retain material bindings from the original .blend files.

    Returns:
        (vertices, wood_faces, leaf_faces) or (None, None, None)
    """
    stage = Usd.Stage.Open(str(twig_path))
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
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()

    if not points or not face_indices:
        return None, None, None

    vertices = np.array([[p[0], p[1], p[2]] for p in points], dtype=np.float64)

    # Build face list (handle triangles and quads)
    faces = []
    idx = 0
    for count in face_counts:
        if count == 3:
            faces.append(face_indices[idx : idx + 3])
        elif count == 4:
            a, b, c, d = face_indices[idx : idx + 4]
            faces.append([a, b, c])
            faces.append([a, c, d])
        idx += count

    if not faces:
        return None, None, None

    all_faces = np.array(faces, dtype=np.int64)
    num_faces = len(all_faces)

    # Check for GeomSubset-based material assignment (per-subset face groups)
    wood_face_indices: set = set()
    leaf_face_indices: set = set()
    has_subsets = False

    for child in mesh_prim.GetChildren():
        if not child.IsA(UsdGeom.Subset):
            continue
        subset = UsdGeom.Subset(child)
        subset_indices = subset.GetIndicesAttr().Get()
        if not subset_indices:
            continue

        # Get material binding on subset
        binding_api = UsdShade.MaterialBindingAPI(child)
        bound_mat, _ = binding_api.ComputeBoundMaterial()
        if not bound_mat:
            continue

        has_subsets = True
        mat_name = bound_mat.GetPrim().GetName().lower()
        is_wood = any(kw in mat_name for kw in WOOD_MATERIAL_KEYWORDS)

        target_set = wood_face_indices if is_wood else leaf_face_indices
        for fi in subset_indices:
            target_set.add(int(fi))

    if has_subsets:
        wood_mask = np.array(
            [i in wood_face_indices for i in range(num_faces)], dtype=bool
        )
        leaf_mask = np.array(
            [i in leaf_face_indices for i in range(num_faces)], dtype=bool
        )
        # Faces not in any subset default to leaf
        unassigned = ~(wood_mask | leaf_mask)
        leaf_mask |= unassigned
        return vertices, all_faces[wood_mask], all_faces[leaf_mask]

    # No subsets: single mesh-level material binding
    binding_api = UsdShade.MaterialBindingAPI(mesh_prim)
    bound_mat, _ = binding_api.ComputeBoundMaterial()
    if bound_mat:
        mat_name = bound_mat.GetPrim().GetName().lower()
        is_wood = any(kw in mat_name for kw in WOOD_MATERIAL_KEYWORDS)
        if is_wood:
            return vertices, all_faces, np.empty((0, 3), dtype=np.int64)
        return vertices, np.empty((0, 3), dtype=np.int64), all_faces

    # No material info at all - treat everything as leaf
    return vertices, np.empty((0, 3), dtype=np.int64), all_faces


def _extract_tree_mesh(
    assembly_usda_path: Path,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
) -> Optional[tuple]:
    """Extract tree mesh data from USDA assembly without writing files.

    Reads static USDA files (preferred over skeletal) for trunk geometry and
    twig prototypes. Static files have material bindings from the original
    .blend files, enabling material-based wood/leaf classification.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons)
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0)

    Returns:
        (trunk_verts, trunk_faces, twig_wood_verts, twig_wood_faces,
         twig_leaf_verts, twig_leaf_faces) or None on failure
    """
    tree_dir = assembly_usda_path.parent

    # Prefer static USDA for OBJ export (no skeleton needed, has material bindings)
    stem_files = list(tree_dir.glob("*_stems_static.usda"))
    if not stem_files:
        stem_files = list(tree_dir.glob("*_static.usda"))
    if not stem_files:
        # Fallback to skeletal if no static available
        stem_files = list(tree_dir.glob("*_stems_skeletal.usda"))
    if not stem_files:
        stem_files = list(tree_dir.glob("*_skeletal.usda"))
    if not stem_files:
        print(f"  OBJ export: No stem USDA found in {tree_dir}")
        return None
    # Filter out twig/foliage files from matches
    stem_files = [
        f for f in stem_files if "foliage" not in f.stem and "twig" not in f.stem
    ]
    if not stem_files:
        print(f"  OBJ export: No stem USDA found in {tree_dir}")
        return None
    stem_path = stem_files[0]

    # Read trunk/branch mesh from USDA
    trunk_verts, trunk_faces, _trunk_uvs = _read_tree_mesh(stem_path)
    if trunk_verts is None:
        print(f"  OBJ export: Failed to read tree mesh from {stem_path}")
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

    twig_wood_verts, twig_wood_faces = _empty_v.copy(), _empty_f.copy()
    twig_leaf_verts, twig_leaf_faces = _empty_v.copy(), _empty_f.copy()

    if instancer_data is not None:
        positions, orientations, scales, proto_indices, proto_files = instancer_data

        classified_protos: Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for idx, twig_file in proto_files.items():
            # Resolve to static variant for material bindings
            static_file = _resolve_to_static(twig_file)
            twig_path = tree_dir / static_file
            if not twig_path.exists():
                # Fallback to original file
                twig_path = tree_dir / twig_file
            if not twig_path.exists():
                continue

            cache_key = (str(twig_path), decimate_ratio)
            if cache_key in _classified_twig_cache:
                classified_protos[idx] = _classified_twig_cache[cache_key]
                continue

            # Read with material classification from static USDA
            raw_verts, raw_wood_faces, raw_leaf_faces = _read_twig_mesh_classified(
                twig_path
            )
            if raw_verts is None:
                continue

            if 0.0 < decimate_ratio < 1.0 and (
                len(raw_wood_faces) > 0 or len(raw_leaf_faces) > 0
            ):
                # Decimate wood and leaf parts separately to preserve classification
                if len(raw_wood_faces) > 0:
                    dec_wood_v, dec_wood_f = _decimate_mesh(
                        raw_verts, raw_wood_faces, decimate_ratio
                    )
                else:
                    dec_wood_v = raw_verts
                    dec_wood_f = raw_wood_faces
                if len(raw_leaf_faces) > 0:
                    dec_leaf_v, dec_leaf_f = _decimate_mesh(
                        raw_verts, raw_leaf_faces, decimate_ratio
                    )
                else:
                    dec_leaf_v = raw_verts
                    dec_leaf_f = raw_leaf_faces
                classified_protos[idx] = (
                    raw_verts,
                    dec_wood_f,
                    dec_leaf_f,
                )
            else:
                classified_protos[idx] = (raw_verts, raw_wood_faces, raw_leaf_faces)
            _classified_twig_cache[cache_key] = classified_protos[idx]

        if classified_protos:
            twig_wood_verts, twig_wood_faces, twig_leaf_verts, twig_leaf_faces = (
                _bake_classified_twig_instances(
                    classified_protos,
                    positions,
                    orientations,
                    scales,
                    proto_indices,
                )
            )

    return (
        trunk_verts,
        trunk_faces,
        twig_wood_verts,
        twig_wood_faces,
        twig_leaf_verts,
        twig_leaf_faces,
    )


def convert_tree_to_obj(
    assembly_usda_path: Path,
    species_name: str,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    helios_spectra_leaves: str = "deciduous",
) -> Optional[Path]:
    """Convert a tree's USDA assembly to an individual OBJ file with baked twigs.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        species_name: Species name for texture/material lookup
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons)
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0)
        helios_spectra_leaves: Helios spectra type for leaves ("conifer" or "deciduous")

    Returns:
        Path to generated OBJ file, or None on failure
    """
    mesh_data = _extract_tree_mesh(
        assembly_usda_path,
        decimate_ratio,
        stem_decimate_ratio,
    )
    if mesh_data is None:
        return None

    tree_dir = assembly_usda_path.parent
    helios_name = assembly_usda_path.stem.replace("_assembly", "_helios")
    obj_path = tree_dir / f"{helios_name}.obj"
    mtl_name = f"{helios_name}.mtl"
    mtl_path = tree_dir / mtl_name
    bark_texture = _find_bark_texture(tree_dir)

    trunk_verts, trunk_faces, tw_verts, tw_faces, tl_verts, tl_faces = mesh_data
    _write_obj(
        obj_path,
        trunk_verts,
        trunk_faces,
        None,
        mtl_name,
        twig_wood_verts=tw_verts,
        twig_wood_faces=tw_faces,
        twig_leaf_verts=tl_verts,
        twig_leaf_faces=tl_faces,
    )
    _write_helios_mtl(mtl_path, bark_texture, helios_spectra_leaves)
    print(
        f"  OBJ export: {obj_path.name} ({len(trunk_faces)} trunk + "
        f"{len(tw_faces)} twig_wood + {len(tl_faces)} twig_leaf faces)"
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
    mtl_name: str,
    up_axis: str = "y",
    twig_wood_verts: Optional[np.ndarray] = None,
    twig_wood_faces: Optional[np.ndarray] = None,
    twig_leaf_verts: Optional[np.ndarray] = None,
    twig_leaf_faces: Optional[np.ndarray] = None,
) -> None:
    """Write Wavefront OBJ file with bark, twig_wood, twig_leaf material groups."""
    has_uvs = trunk_uvs is not None and len(trunk_uvs) > 0
    trunk_vert_count = len(trunk_verts)

    if twig_wood_verts is None:
        twig_wood_verts = np.empty((0, 3))
    if twig_wood_faces is None:
        twig_wood_faces = np.empty((0, 3), dtype=np.int64)
    if twig_leaf_verts is None:
        twig_leaf_verts = np.empty((0, 3))
    if twig_leaf_faces is None:
        twig_leaf_faces = np.empty((0, 3), dtype=np.int64)

    with open(obj_path, "w") as f:
        f.write(f"# Helios++ tree mesh\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # Write all vertices
        for v in trunk_verts:
            f.write(_fmt_vert(v, up_axis))
        for v in twig_wood_verts:
            f.write(_fmt_vert(v, up_axis))
        for v in twig_leaf_verts:
            f.write(_fmt_vert(v, up_axis))

        f.write("\n")

        # Write UVs
        if has_uvs:
            for uv in trunk_uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Dummy UVs for twig vertices
        total_twig_faces = len(twig_wood_faces) + len(twig_leaf_faces)
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


def write_combined_obj(
    tree_meshes: List[tuple],
    output_path: Path,
    helios_spectra_leaves: str = "deciduous",
    up_axis: str = "y",
) -> Path:
    """Merge all tree meshes into a single combined OBJ at CSV positions.

    Works directly from numpy arrays -- no individual OBJ files needed.

    Args:
        tree_meshes: List of tuples:
            (trunk_verts, trunk_faces, tw_verts, tw_faces, tl_verts, tl_faces, x, y, z)
        output_path: Path to write the combined OBJ file
        helios_spectra_leaves: Helios spectra type for leaves material

    Returns:
        Path to generated combined OBJ file
    """
    mtl_name = output_path.stem + ".mtl"
    mtl_path = output_path.with_suffix(".mtl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_bark_verts: List[np.ndarray] = []
    all_bark_faces: List[np.ndarray] = []
    bark_vert_offset = 0

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
    bark_faces = (
        np.vstack(all_bark_faces)
        if all_bark_faces
        else np.empty((0, 3), dtype=np.int64)
    )
    tw_verts = np.vstack(all_tw_verts) if all_tw_verts else np.empty((0, 3))
    tw_faces = (
        np.vstack(all_tw_faces)
        if all_tw_faces
        else np.empty((0, 3), dtype=np.int64)
    )
    tl_verts = np.vstack(all_tl_verts) if all_tl_verts else np.empty((0, 3))
    tl_faces = (
        np.vstack(all_tl_faces)
        if all_tl_faces
        else np.empty((0, 3), dtype=np.int64)
    )

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

    _write_helios_mtl(
        mtl_path,
        bark_texture=None,
        helios_spectra_leaves=helios_spectra_leaves,
    )
    return output_path


def _write_helios_mtl(
    mtl_path: Path,
    bark_texture: Optional[Path],
    helios_spectra_leaves: str = "deciduous",
) -> None:
    """Write Helios-compatible MTL file with bark, twig_wood, twig_leaf materials.

    Helios++ uses custom MTL properties:
        helios_spectra  - ECOSTRESS spectral library identifier
        helios_classification - ASPRS point classification (4 = high vegetation)
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
) -> List[Tuple[Path, float, float, float, str]]:
    """Export all USDA tree assemblies to a combined OBJ for Helios++.

    Extracts mesh data from USDA assemblies and writes a single combined
    OBJ with all trees positioned at their CSV coordinates. Optionally
    also writes individual per-tree OBJ files.

    Twig geometry is classified into wood/leaf using material bindings
    from static USDA files (sourced from .blend originals).

    Args:
        output_dir: Forest output directory containing species/tree_* subdirs.
        csv_path: Input CSV with tree positions (x, y, z, fid columns).
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons).
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0).
        generate_scene_xml: Generate Helios++ scene XML with tree positions.
        individual_obj: Also write individual per-tree OBJ files (default: False).
        up_axis: Coordinate up axis for OBJ output ("y" or "z").

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

        trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f = mesh_data
        print(
            f"  Extracted: {assembly_path.parent.name} "
            f"({len(trunk_faces)} trunk + {len(tw_f)} twig_wood + {len(tl_f)} twig_leaf faces)"
        )
        tree_meshes.append(
            (trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f, x, y, z)
        )

        if individual_obj:
            tree_dir = assembly_path.parent
            helios_name = assembly_path.stem.replace("_assembly", "_helios")
            obj_path = tree_dir / f"{helios_name}.obj"
            mtl_name = f"{helios_name}.mtl"
            mtl_path = tree_dir / mtl_name

            _write_obj(
                obj_path,
                trunk_verts,
                trunk_faces,
                None,
                mtl_name,
                up_axis=up_axis,
                twig_wood_verts=tw_v,
                twig_wood_faces=tw_f,
                twig_leaf_verts=tl_v,
                twig_leaf_faces=tl_f,
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
