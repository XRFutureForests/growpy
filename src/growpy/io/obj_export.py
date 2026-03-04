"""OBJ/MTL export for Helios++ LiDAR simulation.

Converts USDA tree assemblies to Wavefront OBJ with baked twig instances
and Helios-compatible MTL materials. Post-processing step that runs after
USDA export without modifying the existing pipeline.

Each tree produces one OBJ file with trunk/branch geometry plus all twig
instances baked (transformed and merged) into the mesh. Twig prototypes
are auto-decimated to reduce polygon count.

Material groups:
    bark   - Trunk and branch geometry (helios_spectra wood)
    leaves - All baked twig geometry (helios_spectra conifer or deciduous)
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


def clear_twig_decimate_cache() -> None:
    """Clear the decimated twig mesh cache. Call at start of new export session."""
    global _decimated_twig_cache
    _decimated_twig_cache.clear()


def convert_tree_to_obj(
    assembly_usda_path: Path,
    species_name: str,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    helios_spectra_leaves: str = "deciduous",
) -> Optional[Path]:
    """Convert a tree's USDA assembly to OBJ with baked twigs.

    Reads the assembly USDA and its referenced skeletal tree mesh,
    extracts twig instance data from PointInstancer, decimates twig
    prototypes, bakes all instances into the mesh, and writes OBJ+MTL.

    Args:
        assembly_usda_path: Path to the Nanite Assembly USDA file
        species_name: Species name for texture/material lookup
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons)
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0, lower = fewer polygons)
        helios_spectra_leaves: Helios spectra type for leaves ("conifer" or "deciduous")

    Returns:
        Path to generated OBJ file, or None on failure
    """
    tree_dir = assembly_usda_path.parent
    helios_name = assembly_usda_path.stem.replace("_assembly", "_helios")
    obj_path = tree_dir / f"{helios_name}.obj"
    mtl_name = f"{helios_name}.mtl"
    mtl_path = tree_dir / mtl_name

    # Find skeletal USDA in same directory
    skeletal_files = list(tree_dir.glob("*_skeletal.usda"))
    if not skeletal_files:
        print(f"  OBJ export: No skeletal USDA found in {tree_dir}")
        return None
    skeletal_path = skeletal_files[0]

    # Read trunk/branch mesh from skeletal USDA
    trunk_verts, trunk_faces, trunk_uvs = _read_tree_mesh(skeletal_path)
    if trunk_verts is None:
        print(f"  OBJ export: Failed to read tree mesh from {skeletal_path}")
        return None

    # Decimate stem/branch geometry (Helios cares about twig positions, not stem detail)
    if 0.0 < stem_decimate_ratio < 1.0:
        orig_faces = len(trunk_faces)
        trunk_verts, trunk_faces = _decimate_mesh(
            trunk_verts, trunk_faces, stem_decimate_ratio
        )
        trunk_uvs = (
            None  # UVs invalidated by decimation; Helios uses spectra, not textures
        )

    # Read twig instance data from assembly USDA
    instancer_data = _read_twig_instancer(assembly_usda_path)

    twig_verts = np.empty((0, 3), dtype=np.float64)
    twig_faces = np.empty((0, 3), dtype=np.int64)

    if instancer_data is not None:
        positions, orientations, scales, proto_indices, proto_files = instancer_data

        # Read and decimate each unique twig prototype
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

        # Bake all twig instances into combined mesh
        if proto_meshes:
            twig_verts, twig_faces = _bake_twig_instances(
                proto_meshes, positions, orientations, scales, proto_indices
            )

    if trunk_verts is None or trunk_faces is None:
        print(f"  OBJ export: No valid tree mesh data")
        return None

    # Write OBJ + MTL
    bark_texture = _find_bark_texture(tree_dir)
    _write_obj(
        obj_path, trunk_verts, trunk_faces, trunk_uvs, twig_verts, twig_faces, mtl_name
    )
    _write_helios_mtl(mtl_path, bark_texture, helios_spectra_leaves)

    trunk_face_count = len(trunk_faces)
    twig_face_count = len(twig_faces)
    print(
        f"  OBJ export: {obj_path.name} ({trunk_face_count} trunk + {twig_face_count} twig faces)"
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


def _find_bark_texture(tree_dir: Path) -> Optional[Path]:
    """Find bark texture in tree output directory."""
    textures_dir = tree_dir / "textures"
    if not textures_dir.exists():
        return None

    for ext in [".jpg", ".jpeg", ".png"]:
        for f in textures_dir.glob(f"*bark*{ext}"):
            return f

    return None


def _write_obj(
    obj_path: Path,
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    twig_verts: np.ndarray,
    twig_faces: np.ndarray,
    mtl_name: str,
) -> None:
    """Write Wavefront OBJ file with bark and leaves material groups."""
    has_uvs = trunk_uvs is not None and len(trunk_uvs) > 0
    trunk_vert_count = len(trunk_verts)

    with open(obj_path, "w") as f:
        f.write(f"# Helios++ tree mesh\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # Write trunk vertices
        for v in trunk_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write twig vertices
        for v in twig_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        f.write("\n")

        # Write UVs
        if has_uvs:
            for uv in trunk_uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Dummy UVs for twig vertices (one per face-vertex)
        twig_face_vert_count = len(twig_faces) * 3
        if twig_face_vert_count > 0:
            f.write(f"vt 0.0 0.0\n")
            twig_uv_start = len(trunk_uvs) + 1 if has_uvs else 1
        else:
            twig_uv_start = 0

        f.write("\n")

        # Trunk faces (bark material)
        f.write("usemtl bark\n")
        if has_uvs:
            # UVs are face-varying: UV index i maps to face-vertex i
            for fi, face in enumerate(trunk_faces):
                uv_base = fi * 3
                f.write(
                    f"f {face[0]+1}/{uv_base+1} {face[1]+1}/{uv_base+2} {face[2]+1}/{uv_base+3}\n"
                )
        else:
            for face in trunk_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        # Twig faces (leaves material)
        if len(twig_faces) > 0:
            f.write("\nusemtl leaves\n")
            for face in twig_faces:
                # Offset vertex indices by trunk vertex count
                v0 = face[0] + trunk_vert_count + 1
                v1 = face[1] + trunk_vert_count + 1
                v2 = face[2] + trunk_vert_count + 1
                if has_uvs:
                    # All twig faces share single dummy UV
                    f.write(
                        f"f {v0}/{twig_uv_start} {v1}/{twig_uv_start} {v2}/{twig_uv_start}\n"
                    )
                else:
                    f.write(f"f {v0} {v1} {v2}\n")


def write_combined_obj(
    tree_entries: List[Tuple[Path, float, float, float, str]],
    output_path: Path,
    helios_spectra_leaves: str = "deciduous",
) -> Path:
    """Merge all individual tree OBJs into a single combined OBJ at CSV positions.

    Reads each per-tree OBJ, translates vertices by (x, y, z) from the CSV,
    and writes one combined OBJ + MTL with bark/leaves material groups.

    Args:
        tree_entries: List of (obj_path, x, y, z, species_name) tuples
        output_path: Path to write the combined OBJ file
        helios_spectra_leaves: Helios spectra type for leaves material

    Returns:
        Path to generated combined OBJ file
    """
    mtl_name = output_path.stem + ".mtl"
    mtl_path = output_path.with_suffix(".mtl")

    vert_offset = 0
    uv_offset = 0
    bark_faces_all: List[str] = []
    leaves_faces_all: List[str] = []
    verts_all: List[str] = []
    uvs_all: List[str] = []

    for obj_path, x, y, z, _species in tree_entries:
        if not obj_path.exists():
            continue

        local_verts = 0
        local_uvs = 0
        current_mtl = "bark"

        with open(obj_path, "r") as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.split()
                    vx = float(parts[1]) + x
                    vy = float(parts[2]) + y
                    vz = float(parts[3]) + z
                    verts_all.append(f"v {vx:.6f} {vy:.6f} {vz:.6f}\n")
                    local_verts += 1
                elif line.startswith("vt "):
                    uvs_all.append(line)
                    local_uvs += 1
                elif line.startswith("usemtl "):
                    current_mtl = line.strip().split()[1]
                elif line.startswith("f "):
                    new_face = _offset_face_line(line, vert_offset, uv_offset)
                    if current_mtl == "leaves":
                        leaves_faces_all.append(new_face)
                    else:
                        bark_faces_all.append(new_face)

        vert_offset += local_verts
        uv_offset += local_uvs

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write("# Helios++ combined forest mesh\n")
        f.write(f"mtllib {mtl_name}\n\n")

        for v in verts_all:
            f.write(v)
        f.write("\n")
        for uv in uvs_all:
            f.write(uv)
        f.write("\n")

        f.write("usemtl bark\n")
        for face in bark_faces_all:
            f.write(face)

        if leaves_faces_all:
            f.write("\nusemtl leaves\n")
            for face in leaves_faces_all:
                f.write(face)

    _write_helios_mtl(
        mtl_path, bark_texture=None, helios_spectra_leaves=helios_spectra_leaves
    )

    total_verts = len(verts_all)
    total_faces = len(bark_faces_all) + len(leaves_faces_all)
    print(
        f"  Combined OBJ: {output_path.name} ({total_verts} verts, {total_faces} faces, {len(tree_entries)} trees)"
    )
    return output_path


def _offset_face_line(line: str, vert_offset: int, uv_offset: int) -> str:
    """Offset vertex/UV indices in an OBJ face line by global offsets."""
    parts = line.strip().split()
    new_parts = ["f"]
    for token in parts[1:]:
        components = token.split("/")
        vi = int(components[0]) + vert_offset
        if len(components) >= 2 and components[1]:
            ti = int(components[1]) + uv_offset
            new_parts.append(f"{vi}/{ti}")
        else:
            new_parts.append(str(vi))
    return " ".join(new_parts) + "\n"


def _write_helios_mtl(
    mtl_path: Path,
    bark_texture: Optional[Path],
    helios_spectra_leaves: str = "deciduous",
) -> None:
    """Write Helios-compatible MTL file.

    Helios++ uses custom MTL properties:
        helios_spectra  - ECOSTRESS spectral library identifier
        helios_classification - ASPRS point classification (4 = high vegetation)
    """
    with open(mtl_path, "w") as f:
        f.write("# Helios++ compatible material\n\n")

        # Bark material
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

        # Leaves material
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
    generate_combined_obj: bool = False,
) -> List[Tuple[Path, float, float, float, str]]:
    """Export all USDA tree assemblies in a forest directory to OBJ/MTL.

    Post-processes USDA output from generate_forest into Wavefront OBJ
    for Helios++ LiDAR simulation. Optionally generates a Helios++ scene
    XML and/or a single combined OBJ with all trees positioned.

    Args:
        output_dir: Forest output directory containing species/tree_* subdirs.
        csv_path: Input CSV with tree positions (x, y, z, fid columns).
        decimate_ratio: Twig decimation ratio (0.0-1.0, lower = fewer polygons).
        stem_decimate_ratio: Stem/branch decimation ratio (0.0-1.0).
        generate_scene_xml: Generate Helios++ scene XML with tree positions.
        generate_combined_obj: Export a single combined OBJ with all trees.

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

    obj_files: List[Tuple[Path, float, float, float, str]] = []
    for assembly_path in sorted(assembly_files):
        tree_dir_name = assembly_path.parent.name
        tree_id_str = tree_dir_name.replace("tree_", "")

        species_dir = assembly_path.parent.parent.name
        species_name = species_dir.replace("_", " ").title()

        is_conifer = any(kw in species_dir.lower() for kw in CONIFER_KEYWORDS)
        spectra = "conifer" if is_conifer else "deciduous"

        obj_path = convert_tree_to_obj(
            assembly_usda_path=assembly_path,
            species_name=species_name,
            decimate_ratio=decimate_ratio,
            stem_decimate_ratio=stem_decimate_ratio,
            helios_spectra_leaves=spectra,
        )

        if obj_path:
            try:
                fid = int(tree_id_str)
                row = forest_data[forest_data["fid"] == fid].iloc[0]
                obj_files.append(
                    (
                        obj_path,
                        float(row["x"]),
                        float(row["y"]),
                        float(row["z"]),
                        species_name,
                    )
                )
            except (ValueError, IndexError):
                obj_files.append((obj_path, 0.0, 0.0, 0.0, species_name))

    if generate_scene_xml and obj_files:
        from growpy.io.helios_scene import generate_helios_scene

        scene_path = output_dir / "helios_scene.xml"
        generate_helios_scene(tree_entries=obj_files, output_path=scene_path)

    if generate_combined_obj and obj_files:
        is_conifer_forest = any(
            any(kw in sp.lower() for kw in CONIFER_KEYWORDS)
            for _, _, _, _, sp in obj_files
        )
        spectra = "conifer" if is_conifer_forest else "deciduous"
        combined_path = output_dir / "forest_combined.obj"
        write_combined_obj(
            tree_entries=obj_files,
            output_path=combined_path,
            helios_spectra_leaves=spectra,
        )

    print(f"\nOBJ export complete: {len(obj_files)} trees converted")
    return obj_files
