"""OBJ/MTL export for Helios++ LiDAR simulation.

Converts USDA tree assemblies to Wavefront OBJ with baked twig instances
and Helios-compatible MTL materials. Post-processing step that runs after
USDA export without modifying the existing pipeline.

Each tree produces one OBJ file with trunk/branch geometry plus all twig
instances baked (transformed and merged) into the mesh.

Twig geometry is classified into wood and leaf using material bindings
from static USDA files (sourced from .blend originals).

Material groups:
    bark      - Trunk and branch geometry (helios_spectra wood)
    twig_wood - Twig branch/stem cylinders (helios_spectra wood)
    twig_leaf - Twig leaf/needle planes (helios_spectra conifer or deciduous)
"""

import logging
import math
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import bpy
import numpy as np

logger = logging.getLogger(__name__)

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

WOOD_MATERIAL_KEYWORDS = ("bark", "branch", "wood", "dead", "stem", "twig")

# Cache classified twig meshes per twig file path
# Values: (verts, wood_faces, leaf_faces)
_classified_twig_cache: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def clear_twig_cache() -> None:
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
) -> Optional[tuple]:
    """Extract tree mesh data from USDA assembly without writing files.

    Reads static USDA files (preferred over skeletal) for trunk geometry and
    twig prototypes. Static files have material bindings from the original
    .blend files, enabling material-based wood/leaf classification.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file

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
        logger.warning("OBJ export: No stem USDA found in %s", tree_dir)
        return None
    # Filter out twig/foliage files from matches
    stem_files = [
        f for f in stem_files if "foliage" not in f.stem and "twig" not in f.stem
    ]
    if not stem_files:
        logger.warning("OBJ export: No stem USDA found in %s", tree_dir)
        return None
    stem_path = stem_files[0]

    # Read trunk/branch mesh from USDA
    trunk_verts, trunk_faces, _trunk_uvs = _read_tree_mesh(stem_path)
    if trunk_verts is None:
        logger.warning("OBJ export: Failed to read tree mesh from %s", stem_path)
        return None

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

            cache_key = str(twig_path)
            if cache_key in _classified_twig_cache:
                classified_protos[idx] = _classified_twig_cache[cache_key]
                continue

            # Read with material classification from static USDA
            raw_verts, raw_wood_faces, raw_leaf_faces = _read_twig_mesh_classified(
                twig_path
            )
            if raw_verts is None:
                continue

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
    helios_spectra_leaves: str = "deciduous",
) -> Optional[Path]:
    """Convert a tree's USDA assembly to an individual OBJ file with baked twigs.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        species_name: Species name for texture/material lookup
        helios_spectra_leaves: Helios spectra type for leaves ("conifer" or "deciduous")

    Returns:
        Path to generated OBJ file, or None on failure
    """
    mesh_data = _extract_tree_mesh(assembly_usda_path)
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
    logger.info(
        "OBJ export: %s (%d trunk + %d twig_wood + %d twig_leaf faces)",
        obj_path.name,
        len(trunk_faces),
        len(tw_faces),
        len(tl_faces),
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

    Streams data per-tree in chunks to avoid OOM from np.vstack on large forests.

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

    # Pre-scan vertex counts for face offset calculation
    bark_counts = [len(e[0]) for e in tree_meshes]
    tw_counts = [len(e[2]) for e in tree_meshes]
    tl_counts = [len(e[4]) for e in tree_meshes]
    total_bark = sum(bark_counts)
    total_tw = sum(tw_counts)
    total_tl = sum(tl_counts)
    chunk = 500_000

    with open(output_path, "w") as f:
        f.write("# Helios++ combined forest mesh\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # Vertices streamed per-tree in chunks: bark, twig_wood, twig_leaf
        for trunk_verts, _, _, _, _, _, x, y, z in tree_meshes:
            offset = np.array([x, y, z], dtype=np.float64)
            for s in range(0, len(trunk_verts), chunk):
                for v in trunk_verts[s : s + chunk] + offset:
                    f.write(_fmt_vert(v, up_axis))

        for _, _, tw_v, _, _, _, x, y, z in tree_meshes:
            if len(tw_v) == 0:
                continue
            offset = np.array([x, y, z], dtype=np.float64)
            for s in range(0, len(tw_v), chunk):
                for v in tw_v[s : s + chunk] + offset:
                    f.write(_fmt_vert(v, up_axis))

        for _, _, _, _, tl_v, _, x, y, z in tree_meshes:
            if len(tl_v) == 0:
                continue
            offset = np.array([x, y, z], dtype=np.float64)
            for s in range(0, len(tl_v), chunk):
                for v in tl_v[s : s + chunk] + offset:
                    f.write(_fmt_vert(v, up_axis))

        f.write("\n")

        # Faces: bark
        f.write("usemtl bark\n")
        cum = 0
        for i, (_, trunk_faces, _, _, _, _, _, _, _) in enumerate(tree_meshes):
            base = cum + 1
            for face in trunk_faces:
                idx = face + base
                f.write(f"f {idx[0]} {idx[1]} {idx[2]}\n")
            cum += bark_counts[i]

        # Faces: twig_wood
        if total_tw > 0:
            f.write("\nusemtl twig_wood\n")
            cum = 0
            for i, (_, _, _, tw_f, _, _, _, _, _) in enumerate(tree_meshes):
                if len(tw_f) == 0:
                    continue
                base = total_bark + cum + 1
                for face in tw_f:
                    idx = face + base
                    f.write(f"f {idx[0]} {idx[1]} {idx[2]}\n")
                cum += tw_counts[i]

        # Faces: twig_leaf
        if total_tl > 0:
            f.write("\nusemtl twig_leaf\n")
            cum = 0
            for i, (_, _, _, _, _, tl_f, _, _, _) in enumerate(tree_meshes):
                if len(tl_f) == 0:
                    continue
                base = total_bark + total_tw + cum + 1
                for face in tl_f:
                    idx = face + base
                    f.write(f"f {idx[0]} {idx[1]} {idx[2]}\n")
                cum += tl_counts[i]

    total_verts = total_bark + total_tw + total_tl
    total_faces = (
        sum(len(e[1]) for e in tree_meshes)
        + sum(len(e[3]) for e in tree_meshes)
        + sum(len(e[5]) for e in tree_meshes)
    )
    logger.info(
        "Combined OBJ: %s (%d verts, %d faces, %d twig_wood + %d twig_leaf, %d trees)",
        output_path.name,
        total_verts,
        total_faces,
        sum(len(e[3]) for e in tree_meshes),
        sum(len(e[5]) for e in tree_meshes),
        len(tree_meshes),
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
    generate_scene_xml: bool = False,
    individual_obj: bool = False,
    up_axis: str = "y",
    timer=None,
) -> List[Tuple[Path, float, float, float, str]]:
    """Export USDA tree assemblies to OBJ for Helios++ LiDAR simulation.

    Two mutually exclusive output modes:
    - Combined OBJ (default): Single file with all trees, positions baked in.
    - Scene XML (helios_scene=True): Individual per-tree OBJs referenced by
      a Helios scene XML with translate offsets per tree position.

    Twig geometry is classified into wood/leaf using material bindings
    from static USDA files (sourced from .blend originals).

    Args:
        output_dir: Forest output directory containing species/tree_* subdirs.
        csv_path: Input CSV with tree positions (x, y, z, fid columns).
        generate_scene_xml: Generate Helios++ scene XML with tree positions.
        individual_obj: Also write individual per-tree OBJ files (default: False).
        up_axis: Coordinate up axis for OBJ output ("y" or "z").

    Returns:
        List of (obj_path, x, y, z, species_name) tuples for exported trees.
    """
    from contextlib import nullcontext

    import pandas as pd

    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    def _track(name):
        return timer.track(name) if timer.enabled else nullcontext()

    clear_twig_cache()

    # Find static assembly USDA files (OBJ export uses static mesh data)
    assembly_files = sorted(output_dir.glob("*/tree_*/*_assembly_static.usda"))

    if not assembly_files:
        logger.warning("OBJ export: No assembly USDA files found")
        return []

    logger.info("HELIOS OBJ EXPORT (%d trees)", len(assembly_files))

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

        with _track("extract_tree_mesh"):
            mesh_data = _extract_tree_mesh(assembly_usda_path=assembly_path)
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
        logger.info(
            "Extracted: %s (%d trunk + %d twig_wood + %d twig_leaf faces)",
            assembly_path.parent.name,
            len(trunk_faces),
            len(tw_f),
            len(tl_f),
        )
        tree_meshes.append((trunk_verts, trunk_faces, tw_v, tw_f, tl_v, tl_f, x, y, z))

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
            logger.info("OBJ export: %s", obj_path.name)
            obj_files.append((obj_path, x, y, z, species_name))
        else:
            obj_files.append((Path(""), x, y, z, species_name))

    if generate_scene_xml and tree_meshes:
        # Scene XML references individual OBJs positioned via translate filters
        if not individual_obj:
            logger.warning(
                "helios_scene requires individual_obj=true; skipping scene XML"
            )
        else:
            with _track("generate_helios_scene"):
                from growpy.io.helios_scene import generate_helios_scene

                scene_path = output_dir / "helios_scene.xml"
                generate_helios_scene(
                    tree_entries=obj_files,
                    output_path=scene_path,
                )
    elif tree_meshes:
        # Combined OBJ as standalone alternative (positions baked into vertices)
        is_conifer_forest = any(
            any(kw in sp.lower() for kw in CONIFER_KEYWORDS)
            for _, _, _, _, sp in obj_files
        )
        spectra = "conifer" if is_conifer_forest else "deciduous"
        combined_path = output_dir / "forest_combined.obj"
        with _track("write_combined_obj"):
            write_combined_obj(
                tree_meshes=tree_meshes,
                output_path=combined_path,
                helios_spectra_leaves=spectra,
                up_axis=up_axis,
            )

    logger.info("OBJ export complete: %d trees", len(tree_meshes))
    return obj_files
