"""OBJ/MTL export for Helios++ LiDAR simulation.

Converts USDA tree assemblies to Wavefront OBJ with baked twig instances
and Helios-compatible MTL materials. Post-processing step that runs after
USDA export without modifying the existing pipeline.

Each tree produces one OBJ file with trunk/branch geometry plus all twig
instances baked (transformed and merged) into the mesh. Twig prototypes
are auto-decimated to reduce polygon count.

Material groups:
    bark   - Trunk and branch geometry (helios_spectra wood)
    Per-twig materials split into leaf and wood sub-materials using
    original Blender material assignments from sidecar JSON files.
"""

import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
import numpy as np

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

from pxr import Gf, Sdf, Usd, UsdGeom

# Cache decimated twig meshes per (twig_file, ratio, simplification) to avoid re-processing
_decimated_twig_cache: Dict = {}


# Skip numpy trunk conversion for meshes larger than this (Blender DECIMATE
# cannot handle meshes this large and fails silently).
TRUNK_DIRECT_THRESHOLD = 5_000_000  # 5M faces


def _log_memory(label: str) -> None:
    """Log current and peak process RSS memory usage."""
    try:
        current_gb = None
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    current_gb = int(line.split()[1]) / (1024 * 1024)
                    break
        import resource

        peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        if current_gb is not None:
            print(f"  [Memory] {label}: {current_gb:.1f} GB current, {peak_gb:.1f} GB peak RSS")
        else:
            print(f"  [Memory] {label}: {peak_gb:.1f} GB peak RSS")
    except Exception:
        pass


def clear_twig_decimate_cache() -> None:
    """Clear the decimated twig mesh cache. Call at start of new export session."""
    global _decimated_twig_cache
    _decimated_twig_cache.clear()


def convert_tree_to_obj_direct(
    model: Any,
    twig_placements: Dict[str, List],
    twig_usd_map: Dict[str, Path],
    output_dir: Path,
    species_name: str,
    tree_id: str,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    helios_spectra_leaves: str = "deciduous",
    simplification_ratios: Optional[Dict[str, float]] = None,
    mat_prefix: str = "",
    classification_codes: Optional[Dict[str, int]] = None,
) -> Optional[Path]:
    """Convert a Grove model directly to OBJ without USD/skeleton intermediate.

    Memory-optimized: simplifies twig prototypes BEFORE baking instances and
    streams twig geometry directly to OBJ file to avoid holding all instances
    in RAM simultaneously.

    Args:
        model: Grove model from grove.build_models() (must be triangulated)
        twig_placements: Dict of twig type -> list of TwigPlacement objects
        twig_usd_map: Dict of twig type -> Path to twig USD files (for prototype meshes)
        output_dir: Directory to write OBJ/MTL files
        species_name: Species name for material lookup
        tree_id: Tree identifier for file naming
        decimate_ratio: Twig decimation ratio (0.0-1.0)
        stem_decimate_ratio: Stem decimation ratio (0.0-1.0)
        helios_spectra_leaves: Helios spectra type ("conifer" or "deciduous")
        simplification_ratios: Per-material simplification ratios
            {'bark': 0.3, 'wood': 0.3, 'leaf': 1.0}. None disables.
        mat_prefix: Prefix for material names (e.g. "t01_" for classification)
        classification_codes: Per-material classification codes
            {'bark': 3101, 'wood': 2101, 'leaf': 1101, 'fruit': 4101}. None uses default.

    Returns:
        Path to generated OBJ file, or None on failure
    """
    import gc as gc_module

    from ..core.twig import normal_to_rotation_matrix, rotation_matrix_to_quaternion

    species_clean = species_name.replace(" ", "_").replace("-", "_").lower()
    helios_name = f"{species_clean}_tree_{tree_id}_helios"
    obj_path = output_dir / f"{helios_name}.obj"
    mtl_name = f"{helios_name}.mtl"
    mtl_path = output_dir / mtl_name

    _log_memory(f"Start export {species_clean} tree_{tree_id}")

    # Probe trunk size to decide processing strategy.
    # For huge meshes (>5M faces) we can stream directly from model data,
    # avoiding multi-GB numpy allocations. However, when bark decimation
    # is requested, we must convert to numpy for Blender decimation.
    faces_raw = model.faces
    num_trunk_faces = len(faces_raw)

    # Determine if bark decimation is requested
    bark_ratio = 1.0
    if simplification_ratios:
        bark_ratio = simplification_ratios.get("bark", 1.0)
    need_bark_decimate = 0.0 < bark_ratio < 1.0
    need_stem_decimate = not simplification_ratios and 0.0 < stem_decimate_ratio < 1.0
    need_decimation = need_bark_decimate or need_stem_decimate

    large_trunk = num_trunk_faces > TRUNK_DIRECT_THRESHOLD

    if large_trunk and not need_decimation:
        # Direct streaming: skip numpy conversion entirely (no decimation needed)
        points_flat = model.get_points_flat()
        num_trunk_verts = len(points_flat) // 3
        print(f"  Trunk: {num_trunk_verts:,} verts, {num_trunk_faces:,} faces (direct streaming)")
        trunk_data_raw = (points_flat, faces_raw, num_trunk_verts, num_trunk_faces)
        trunk_verts = None
        trunk_faces = None
        trunk_uvs = None
    else:
        points_flat = model.get_points_flat()
        trunk_verts = np.array(points_flat, dtype=np.float64).reshape(-1, 3)
        del points_flat

        # Memory-efficient face conversion (avoid [list(f) for f in faces_raw])
        faces_flat: List[int] = []
        for f in faces_raw:
            faces_flat.extend(f)
        del faces_raw
        trunk_faces = np.array(faces_flat, dtype=np.int64).reshape(-1, 3)
        del faces_flat

        if trunk_faces.shape[1] != 3:
            print(f"  OBJ direct: Non-triangulated faces found, skipping")
            return None

        # Extract UVs
        trunk_uvs = None
        if hasattr(model, "uvs") and model.uvs:
            uvs_raw = model.uvs
            trunk_uvs = np.array([[uv[0], uv[1]] for uv in uvs_raw], dtype=np.float64)

        # Simplify trunk (bark)
        if need_bark_decimate:
            orig = len(trunk_faces)
            if large_trunk:
                print(f"  Large trunk ({orig:,} faces): applying bark decimation (ratio {bark_ratio})")
            trunk_verts, trunk_faces = _decimate_mesh(trunk_verts, trunk_faces, bark_ratio)
            trunk_uvs = None
            print(f"  Trunk decimated: {orig:,} -> {len(trunk_faces):,} faces (ratio {bark_ratio})")
        elif need_stem_decimate:
            trunk_verts, trunk_faces = _decimate_mesh(trunk_verts, trunk_faces, stem_decimate_ratio)
            trunk_uvs = None

        print(f"  Trunk: {len(trunk_verts):,} verts, {len(trunk_faces):,} faces")
        large_trunk = False
        trunk_data_raw = None

    # Map twig types to prototype indices
    twig_type_to_proto_idx = {}
    variant_groups = {}
    sorted_twig_types = sorted(twig_usd_map.keys())
    for idx, twig_type in enumerate(sorted_twig_types):
        twig_type_to_proto_idx[twig_type] = idx
        base = twig_type.split("_var")[0]
        if base not in variant_groups:
            variant_groups[base] = []
        variant_groups[base].append(idx)

    # Read twig prototypes, apply decimation AND material-aware simplification upfront.
    # This is the key optimization: simplify the prototype ONCE instead of
    # simplifying N baked copies. For 100k instances this saves ~100x the RAM.
    proto_meshes = {}
    proto_materials = {}
    for idx, twig_type in enumerate(sorted_twig_types):
        twig_path = twig_usd_map[twig_type]
        if not twig_path.exists():
            continue

        # Build a cache key that includes simplification ratios
        simpl_key = tuple(sorted(simplification_ratios.items())) if simplification_ratios else ()
        cache_key = (str(twig_path), decimate_ratio, simpl_key)
        if cache_key in _decimated_twig_cache:
            proto_meshes[idx] = _decimated_twig_cache[cache_key]
        else:
            twig_result = _read_twig_mesh(twig_path)
            if twig_result[0] is None or twig_result[1] is None:
                continue
            raw_verts, raw_faces, raw_uvs, raw_face_mats = twig_result

            # Step 1: Geometric decimation (decimate_ratio)
            if 0.0 < decimate_ratio < 1.0:
                raw_verts, raw_faces = _decimate_mesh(raw_verts, raw_faces, decimate_ratio)
                raw_uvs = None
                raw_face_mats = None

            # Step 2: Material-aware simplification on the prototype itself
            if simplification_ratios:
                sidecar_mat_names = _read_face_material_names(twig_path)
                from .mesh_simplify import simplify_prototype

                raw_verts, raw_faces, raw_uvs, raw_face_mats = simplify_prototype(
                    raw_verts, raw_faces, raw_uvs, raw_face_mats,
                    sidecar_mat_names, simplification_ratios,
                )

            proto_meshes[idx] = (raw_verts, raw_faces, raw_uvs, raw_face_mats)
            _decimated_twig_cache[cache_key] = (raw_verts, raw_faces, raw_uvs, raw_face_mats)

        # Extract material info
        diffuse_rel = _read_twig_material(twig_path)
        mat_name = twig_path.stem.replace("_skeletal", "").replace("_static", "")
        diffuse_path = None
        if diffuse_rel:
            candidate = twig_path.parent / diffuse_rel
            if candidate.exists():
                diffuse_path = candidate
            else:
                tex_name = Path(diffuse_rel).name
                candidate = output_dir / "textures" / tex_name
                if candidate.exists():
                    diffuse_path = candidate

        sidecar_mat_names = _read_face_material_names(twig_path)
        proto_materials[idx] = (mat_name, diffuse_path, sidecar_mat_names)

    for idx, (v, f, _, _) in proto_meshes.items():
        print(f"  Twig proto {idx}: {len(v)} verts, {len(f)} faces (after simplification)")

    # Build instance lists per twig type
    fallback_map = {"twig_upward": "twig_long"}
    instance_data: List[Tuple[int, List[float], List[float]]] = []

    total_twigs = 0
    for twig_type, placement_list in twig_placements.items():
        if not placement_list:
            continue

        if twig_type in variant_groups:
            mapped_type = twig_type
        elif twig_type in fallback_map and fallback_map[twig_type] in variant_groups:
            mapped_type = fallback_map[twig_type]
        else:
            continue

        proto_indices_for_type = variant_groups[mapped_type]
        for inst_i, p in enumerate(placement_list):
            proto_idx = proto_indices_for_type[inst_i % len(proto_indices_for_type)]
            if proto_idx not in proto_meshes:
                continue
            instance_data.append((proto_idx, p.position, p.normal))
            total_twigs += 1

    _log_memory(f"Before streaming write ({total_twigs} twig instances)")

    # Copy twig textures to output
    textures_dir = output_dir / "textures"
    for twig_type in sorted_twig_types:
        twig_path = twig_usd_map[twig_type]
        source_textures_dir = twig_path.parent / "textures"
        if source_textures_dir.exists():
            textures_dir.mkdir(exist_ok=True)
            for tex_file in source_textures_dir.glob("*_foliage_*"):
                dest = textures_dir / tex_file.name
                if not dest.exists():
                    shutil.copy2(tex_file, dest)

    # Streaming OBJ write
    bark_texture = _find_bark_texture(output_dir)

    if large_trunk:
        # LARGE TRUNK PATH: write directly from model data, no numpy
        points_flat, faces_raw, num_trunk_verts, num_trunk_faces = trunk_data_raw
        trunk_face_count = num_trunk_faces
        twig_face_count = _write_obj_streaming_direct(
            obj_path, points_flat, faces_raw, num_trunk_verts,
            instance_data, proto_meshes, proto_materials,
            mtl_name, mat_prefix=mat_prefix,
        )
        del points_flat, faces_raw, trunk_data_raw
    else:
        # NORMAL PATH: numpy arrays, already decimated
        trunk_face_count = len(trunk_faces)
        twig_face_count = _write_obj_streaming(
            obj_path, trunk_verts, trunk_faces, trunk_uvs,
            instance_data, proto_meshes, proto_materials,
            mtl_name, mat_prefix=mat_prefix,
        )
        del trunk_verts, trunk_faces, trunk_uvs

    # Write MTL
    per_proto_face_mats_for_mtl = {}
    for idx, (_, faces, _, face_mats) in proto_meshes.items():
        if face_mats is not None:
            per_proto_face_mats_for_mtl[idx] = face_mats

    _write_helios_mtl(
        mtl_path, bark_texture, helios_spectra_leaves, proto_materials,
        per_proto_face_mats_for_mtl, output_dir,
        mat_prefix=mat_prefix,
        classification_codes=classification_codes,
    )

    print(
        f"  OBJ direct: {obj_path.name} "
        f"({trunk_face_count:,} trunk + {twig_face_count:,} twig faces, {total_twigs:,} instances)"
    )
    _log_memory(f"Export complete {species_clean} tree_{tree_id}")

    del instance_data
    gc_module.collect()

    return obj_path


def convert_tree_to_obj(
    assembly_usda_path: Path,
    species_name: str,
    decimate_ratio: float = 0.3,
    stem_decimate_ratio: float = 0.1,
    helios_spectra_leaves: str = "deciduous",
    simplification_ratios: Optional[Dict[str, float]] = None,
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

    # Find the stems skeletal USDA (not twig/foliage skeletal files)
    skeletal_files = list(tree_dir.glob("*_stems_skeletal.usda"))
    if not skeletal_files:
        # Fallback to any skeletal USDA
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
    per_proto_faces: Dict[int, np.ndarray] = {}
    per_proto_uvs: Dict[int, np.ndarray] = {}
    per_proto_face_mats: Dict[int, np.ndarray] = {}
    # Map prototype index -> material info (name, diffuse texture path, sidecar material names)
    proto_materials: Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]] = {}

    if instancer_data is not None:
        positions, orientations, scales, proto_indices, proto_files = instancer_data

        # Read and decimate each unique twig prototype
        proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]] = {}
        for idx, twig_file in proto_files.items():
            twig_path = tree_dir / twig_file
            if not twig_path.exists():
                continue

            cache_key = (str(twig_path), decimate_ratio)
            if cache_key in _decimated_twig_cache:
                proto_meshes[idx] = _decimated_twig_cache[cache_key]
            else:
                twig_result = _read_twig_mesh(twig_path)
                if twig_result[0] is None or twig_result[1] is None:
                    continue
                raw_verts, raw_faces, raw_uvs, raw_face_mats = twig_result

                if 0.0 < decimate_ratio < 1.0:
                    dec_verts, dec_faces = _decimate_mesh(
                        raw_verts, raw_faces, decimate_ratio
                    )
                    # UVs and per-face materials invalidated by decimation
                    dec_uvs = None
                    dec_face_mats = None
                else:
                    dec_verts, dec_faces, dec_uvs = raw_verts, raw_faces, raw_uvs
                    dec_face_mats = raw_face_mats

                proto_meshes[idx] = (dec_verts, dec_faces, dec_uvs, dec_face_mats)
                _decimated_twig_cache[cache_key] = (dec_verts, dec_faces, dec_uvs, dec_face_mats)

            # Extract material info from twig USD and sidecar
            diffuse_rel = _read_twig_material(twig_path)
            mat_name = Path(twig_file).stem.replace("_skeletal", "").replace("_static", "")
            diffuse_path = None
            if diffuse_rel:
                # Resolve relative texture path against twig location
                candidate = twig_path.parent / diffuse_rel
                if candidate.exists():
                    diffuse_path = candidate
                else:
                    # Try textures dir in tree output
                    tex_name = Path(diffuse_rel).name
                    candidate = tree_dir / "textures" / tex_name
                    if candidate.exists():
                        diffuse_path = candidate

            # Read sidecar material names for leaf/wood classification
            sidecar_mat_names = _read_face_material_names(twig_path)
            proto_materials[idx] = (mat_name, diffuse_path, sidecar_mat_names)

        # Bake all twig instances grouped by prototype
        if proto_meshes:
            twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats = _bake_twig_instances(
                proto_meshes, positions, orientations, scales, proto_indices
            )

    if trunk_verts is None or trunk_faces is None:
        print(f"  OBJ export: No valid tree mesh data")
        return None

    # Material-aware simplification (before writing OBJ)
    if simplification_ratios:
        from .mesh_simplify import simplify_tree_mesh

        (
            trunk_verts, trunk_faces, trunk_uvs,
            twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
        ) = simplify_tree_mesh(
            trunk_verts, trunk_faces, trunk_uvs,
            twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
            proto_materials, simplification_ratios,
        )

    # Write OBJ + MTL
    bark_texture = _find_bark_texture(tree_dir)
    _write_obj(
        obj_path, trunk_verts, trunk_faces, trunk_uvs,
        twig_verts, per_proto_faces, per_proto_uvs, per_proto_face_mats,
        proto_materials, mtl_name,
    )
    _write_helios_mtl(
        mtl_path, bark_texture, helios_spectra_leaves, proto_materials,
        per_proto_face_mats, tree_dir,
    )

    trunk_face_count = len(trunk_faces)
    twig_face_count = sum(len(f) for f in per_proto_faces.values())
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


def _read_twig_material(twig_path: Path) -> Optional[str]:
    """Extract diffuse texture filename from twig USD material.

    Returns:
        Relative texture path (e.g. './textures/species_foliage_diffuse.png') or None
    """
    try:
        from pxr import UsdShade

        stage = Usd.Stage.Open(str(twig_path))
        if not stage:
            return None

        for prim in stage.Traverse():
            if not prim.IsA(UsdShade.Shader):
                continue
            shader = UsdShade.Shader(prim)
            if shader.GetIdAttr().Get() != "UsdUVTexture":
                continue
            # Check if this texture connects to diffuseColor
            if "DiffuseTexture" not in str(prim.GetPath()):
                continue
            file_input = shader.GetInput("file")
            if file_input:
                val = file_input.Get()
                if val:
                    return str(val.resolvedPath or val.path)
    except Exception:
        pass
    return None


def _read_face_material_names(twig_path: Path) -> Optional[List[str]]:
    """Read sidecar face material names for a twig USD file.

    Looks for a `*_face_materials.json` sidecar alongside the twig USD file.
    Returns the list of Blender material names, or None if no sidecar found.
    """
    stem = twig_path.stem.replace("_skeletal", "").replace("_static", "")
    sidecar_path = twig_path.parent / f"{stem}_face_materials.json"
    if not sidecar_path.exists():
        return None
    try:
        with open(sidecar_path, "r") as f:
            data = json.load(f)
        return data.get("materials")
    except Exception:
        return None


def _read_twig_mesh(
    twig_path: Path,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Read twig mesh geometry, UVs, and per-face material indices from USDA file.

    Returns:
        Tuple of (vertices[N,3], faces[M,3], uvs[K,2], face_mat_indices[M])
        or (None, None, None, None). face_mat_indices maps each face to
        its Blender material index (from sidecar JSON), or None if unavailable.
    """
    stage = Usd.Stage.Open(str(twig_path))
    if not stage:
        return None, None, None, None

    # Find first mesh prim
    mesh_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prim = prim
            break

    if mesh_prim is None:
        return None, None, None, None

    mesh = UsdGeom.Mesh(mesh_prim)
    points = mesh.GetPointsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()

    if not points or not face_indices:
        return None, None, None, None

    vertices = np.array([[p[0], p[1], p[2]] for p in points], dtype=np.float64)

    # Read UVs (face-varying)
    uvs = None
    primvars_api = UsdGeom.PrimvarsAPI(mesh)
    st_primvar = primvars_api.GetPrimvar("st")
    if st_primvar and st_primvar.IsDefined():
        uv_data = st_primvar.Get()
        if uv_data:
            uvs = np.array([[uv[0], uv[1]] for uv in uv_data], dtype=np.float64)

    # Handle mixed face sizes (triangles and quads)
    faces = []
    # Track which original face-vertex indices map to output triangles
    tri_uv_indices = []
    idx = 0
    for count in face_counts:
        if count == 3:
            faces.append(face_indices[idx : idx + 3])
            tri_uv_indices.extend([idx, idx + 1, idx + 2])
        elif count == 4:
            # Triangulate quad
            a, b, c, d = face_indices[idx : idx + 4]
            faces.append([a, b, c])
            tri_uv_indices.extend([idx, idx + 1, idx + 2])
            faces.append([a, c, d])
            tri_uv_indices.extend([idx, idx + 2, idx + 3])
        idx += count

    if not faces:
        return None, None, None, None

    # Remap UVs to match triangulated face order
    if uvs is not None and len(tri_uv_indices) > 0:
        if max(tri_uv_indices) < len(uvs):
            uvs = uvs[tri_uv_indices]
        else:
            uvs = None

    # Load per-face material indices from sidecar JSON
    face_mat_indices = None
    stem = twig_path.stem.replace("_skeletal", "").replace("_static", "")
    sidecar_path = twig_path.parent / f"{stem}_face_materials.json"
    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r") as f_json:
                sidecar = json.load(f_json)
            raw_indices = sidecar.get("face_material_indices", [])
            if len(raw_indices) == len(face_counts):
                # Sidecar matches original (pre-triangulation) face count.
                # Expand to match triangulated faces: quads produce 2 triangles.
                expanded = []
                for fi, count in enumerate(face_counts):
                    mat_idx = raw_indices[fi] if fi < len(raw_indices) else 0
                    if count == 3:
                        expanded.append(mat_idx)
                    elif count == 4:
                        expanded.extend([mat_idx, mat_idx])
                face_mat_indices = np.array(expanded, dtype=np.int32)
            elif len(raw_indices) == len(faces):
                # Already triangulated (sidecar saved post-triangulation)
                face_mat_indices = np.array(raw_indices, dtype=np.int32)
        except Exception:
            pass

    return vertices, np.array(faces, dtype=np.int64), uvs, face_mat_indices


def _decimate_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    ratio: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Decimate mesh using Blender's DECIMATE modifier.

    For large meshes (>10M faces), delegates to chunked spatial decimation
    from mesh_simplify to limit peak RAM usage.

    Args:
        vertices: (N, 3) vertex positions
        faces: (M, 3) triangle indices
        ratio: Decimation ratio (0.0-1.0, lower = more reduction)

    Returns:
        Tuple of (decimated_vertices, decimated_faces)
    """
    from .mesh_simplify import CHUNK_FACE_LIMIT, _decimate_chunked

    if len(faces) > CHUNK_FACE_LIMIT:
        return _decimate_chunked(vertices, faces, ratio, CHUNK_FACE_LIMIT)

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
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]],
    positions: np.ndarray,
    orientations: np.ndarray,
    scales: np.ndarray,
    proto_indices: np.ndarray,
) -> Tuple[np.ndarray, Dict[int, np.ndarray], Dict[int, np.ndarray], Dict[int, np.ndarray]]:
    """Transform and merge all twig instances grouped by prototype index.

    Returns:
        Tuple of (combined_vertices[N,3],
                  per_proto_faces: {proto_idx: faces[M,3]},
                  per_proto_uvs: {proto_idx: uvs[M*3,2]},
                  per_proto_face_mats: {proto_idx: face_mat_indices[M]})
    """
    all_verts = []
    per_proto_faces: Dict[int, List[np.ndarray]] = {}
    per_proto_uvs: Dict[int, List[np.ndarray]] = {}
    per_proto_face_mats: Dict[int, List[np.ndarray]] = {}
    vert_offset = 0

    for i in range(len(positions)):
        proto_idx = proto_indices[i]
        if proto_idx not in proto_meshes:
            continue

        proto_verts, proto_faces, proto_uvs, proto_face_mats = proto_meshes[proto_idx]
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

        if proto_idx not in per_proto_faces:
            per_proto_faces[proto_idx] = []
            per_proto_uvs[proto_idx] = []
            per_proto_face_mats[proto_idx] = []

        per_proto_faces[proto_idx].append(proto_faces + vert_offset)
        if proto_uvs is not None:
            per_proto_uvs[proto_idx].append(proto_uvs)
        if proto_face_mats is not None:
            per_proto_face_mats[proto_idx].append(proto_face_mats)

        vert_offset += len(proto_verts)

    if not all_verts:
        return np.empty((0, 3), dtype=np.float64), {}, {}, {}

    # Stack face, UV, and material arrays per prototype
    stacked_faces = {}
    stacked_uvs = {}
    stacked_face_mats = {}
    for idx in per_proto_faces:
        stacked_faces[idx] = np.vstack(per_proto_faces[idx])
        if per_proto_uvs.get(idx):
            stacked_uvs[idx] = np.vstack(per_proto_uvs[idx])
        if per_proto_face_mats.get(idx):
            stacked_face_mats[idx] = np.concatenate(per_proto_face_mats[idx])

    return np.vstack(all_verts), stacked_faces, stacked_uvs, stacked_face_mats


def _find_bark_texture(tree_dir: Path) -> Optional[Path]:
    """Find bark texture in tree output directory."""
    textures_dir = tree_dir / "textures"
    if not textures_dir.exists():
        return None

    for ext in [".jpg", ".jpeg", ".png"]:
        for f in textures_dir.glob(f"*bark*{ext}"):
            return f

    return None


def _stream_twig_vertices(
    f,
    initial_vert_offset: int,
    instance_data: List[Tuple[int, List[float], List[float]]],
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]],
) -> Tuple[Dict[int, List[int]], int]:
    """Stream twig instance vertices to an open OBJ file handle.

    Returns (proto_instance_offsets, final_vert_offset) for use by
    _write_twig_faces.
    """
    from ..core.twig import normal_to_rotation_matrix, rotation_matrix_to_quaternion
    from collections import defaultdict

    instances_by_proto: Dict[int, List[Tuple[List[float], List[float]]]] = defaultdict(list)
    for proto_idx, position, normal in instance_data:
        instances_by_proto[proto_idx].append((position, normal))

    vert_offset = initial_vert_offset
    proto_instance_offsets: Dict[int, List[int]] = defaultdict(list)

    for proto_idx in sorted(instances_by_proto.keys()):
        if proto_idx not in proto_meshes:
            continue
        proto_verts = proto_meshes[proto_idx][0]
        num_proto_verts = len(proto_verts)
        if num_proto_verts == 0:
            continue

        for position, normal in instances_by_proto[proto_idx]:
            rot_matrix = normal_to_rotation_matrix(normal)
            quat = rotation_matrix_to_quaternion(rot_matrix)
            w, x, y, z = quat
            rot = _quat_to_rotation_matrix(w, x, y, z)

            transformed = (rot @ proto_verts.T).T + np.array(position)
            for v in transformed:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

            proto_instance_offsets[proto_idx].append(vert_offset)
            vert_offset += num_proto_verts

    return proto_instance_offsets, vert_offset


def _write_twig_faces(
    f,
    proto_instance_offsets: Dict[int, List[int]],
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]],
    proto_materials: Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]],
    mat_prefix: str = "",
) -> int:
    """Write twig faces grouped by prototype and sub-material. Returns face count."""
    twig_face_count = 0
    for proto_idx in sorted(proto_instance_offsets.keys()):
        if proto_idx not in proto_meshes:
            continue
        _, proto_faces, _, proto_face_mats = proto_meshes[proto_idx]
        if len(proto_faces) == 0:
            continue

        mat_name, _, sidecar_mat_names = proto_materials.get(
            proto_idx, (f"leaves_{proto_idx}", None, None)
        )
        offsets = proto_instance_offsets[proto_idx]

        if proto_face_mats is not None and sidecar_mat_names:
            unique_mat_ids = sorted(set(proto_face_mats.tolist()))
            for mat_id in unique_mat_ids:
                blend_mat_name = (
                    sidecar_mat_names[mat_id]
                    if mat_id < len(sidecar_mat_names)
                    else f"material_{mat_id}"
                )
                sub_mat_name = f"{mat_prefix}{mat_name}:{blend_mat_name}"
                mask = proto_face_mats == mat_id
                sub_faces = proto_faces[mask]
                if len(sub_faces) == 0:
                    continue

                f.write(f"\nusemtl {sub_mat_name}\n")
                for base_offset in offsets:
                    for face in sub_faces:
                        f.write(f"f {face[0]+base_offset+1} {face[1]+base_offset+1} {face[2]+base_offset+1}\n")
                        twig_face_count += 1
        else:
            f.write(f"\nusemtl {mat_prefix}{mat_name}\n")
            for base_offset in offsets:
                for face in proto_faces:
                    f.write(f"f {face[0]+base_offset+1} {face[1]+base_offset+1} {face[2]+base_offset+1}\n")
                    twig_face_count += 1

    return twig_face_count


def _write_obj_streaming_direct(
    obj_path: Path,
    points_flat: List[float],
    faces_raw: list,
    num_trunk_verts: int,
    instance_data: List[Tuple[int, List[float], List[float]]],
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]],
    proto_materials: Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]],
    mtl_name: str,
    mat_prefix: str = "",
) -> int:
    """Write OBJ file for large trunk meshes without any numpy conversion.

    Trunk vertices are read directly from the flat float list returned by
    model.get_points_flat() and trunk faces from model.faces.  This avoids
    allocating multi-GB numpy arrays for 30M+ vertex meshes.
    """
    with open(obj_path, "w") as f:
        f.write(f"# Helios++ tree mesh (direct streaming export)\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # -- All vertices first (trunk + twigs) --
        for i in range(0, len(points_flat), 3):
            f.write(f"v {points_flat[i]:.6f} {points_flat[i+1]:.6f} {points_flat[i+2]:.6f}\n")

        proto_offsets, _ = _stream_twig_vertices(
            f, num_trunk_verts, instance_data, proto_meshes,
        )
        f.write("\n")

        # -- All faces (trunk then twigs) --
        f.write(f"usemtl {mat_prefix}bark\n")
        for face in faces_raw:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        twig_face_count = _write_twig_faces(
            f, proto_offsets, proto_meshes, proto_materials,
            mat_prefix=mat_prefix,
        )

    return twig_face_count


def _write_obj_streaming(
    obj_path: Path,
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    instance_data: List[Tuple[int, List[float], List[float]]],
    proto_meshes: Dict[int, Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]],
    proto_materials: Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]],
    mtl_name: str,
    mat_prefix: str = "",
) -> int:
    """Write OBJ file by streaming twig instances directly to disk.

    For normal-sized trunk meshes that fit in numpy arrays (and may have
    been decimated). Peak RAM = trunk numpy arrays + 1 twig prototype.
    """
    has_trunk_uvs = trunk_uvs is not None and len(trunk_uvs) > 0
    trunk_vert_count = len(trunk_verts)

    with open(obj_path, "w") as f:
        f.write(f"# Helios++ tree mesh (streaming export)\n")
        f.write(f"mtllib {mtl_name}\n\n")

        # -- All vertices (trunk + twigs) --
        for v in trunk_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        proto_offsets, _ = _stream_twig_vertices(
            f, trunk_vert_count, instance_data, proto_meshes,
        )

        # -- UVs (trunk only) --
        if has_trunk_uvs:
            f.write("\n")
            for uv in trunk_uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        f.write("\n")

        # -- All faces (trunk then twigs) --
        f.write(f"usemtl {mat_prefix}bark\n")
        if has_trunk_uvs:
            for fi, face in enumerate(trunk_faces):
                uv_base = fi * 3
                f.write(
                    f"f {face[0]+1}/{uv_base+1} {face[1]+1}/{uv_base+2} {face[2]+1}/{uv_base+3}\n"
                )
        else:
            for face in trunk_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        twig_face_count = _write_twig_faces(
            f, proto_offsets, proto_meshes, proto_materials,
            mat_prefix=mat_prefix,
        )

    return twig_face_count


def _write_obj(
    obj_path: Path,
    trunk_verts: np.ndarray,
    trunk_faces: np.ndarray,
    trunk_uvs: Optional[np.ndarray],
    twig_verts: np.ndarray,
    per_proto_faces: Dict[int, np.ndarray],
    per_proto_uvs: Dict[int, np.ndarray],
    per_proto_face_mats: Dict[int, np.ndarray],
    proto_materials: Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]],
    mtl_name: str,
) -> None:
    """Write Wavefront OBJ file with bark and per-twig leaf/wood material groups."""
    has_trunk_uvs = trunk_uvs is not None and len(trunk_uvs) > 0
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

        # Write trunk UVs
        uv_offset = 0
        if has_trunk_uvs:
            for uv in trunk_uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
            uv_offset = len(trunk_uvs)

        # Write per-prototype twig UVs and record their start offsets
        proto_uv_starts: Dict[int, int] = {}
        for proto_idx in sorted(per_proto_faces.keys()):
            proto_uvs = per_proto_uvs.get(proto_idx)
            if proto_uvs is not None and len(proto_uvs) > 0:
                proto_uv_starts[proto_idx] = uv_offset
                for uv in proto_uvs:
                    f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
                uv_offset += len(proto_uvs)

        f.write("\n")

        # Trunk faces (bark material)
        f.write("usemtl bark\n")
        if has_trunk_uvs:
            for fi, face in enumerate(trunk_faces):
                uv_base = fi * 3
                f.write(
                    f"f {face[0]+1}/{uv_base+1} {face[1]+1}/{uv_base+2} {face[2]+1}/{uv_base+3}\n"
                )
        else:
            for face in trunk_faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        # Twig faces grouped by prototype, split by leaf/wood sub-materials
        for proto_idx in sorted(per_proto_faces.keys()):
            faces = per_proto_faces[proto_idx]
            if len(faces) == 0:
                continue

            mat_name, _, sidecar_mat_names = proto_materials.get(
                proto_idx, (f"leaves_{proto_idx}", None, None)
            )
            face_mats = per_proto_face_mats.get(proto_idx)
            has_twig_uvs = proto_idx in proto_uv_starts

            if face_mats is not None and sidecar_mat_names and len(face_mats) == len(faces):
                # Split faces by sub-material (leaf vs wood)
                unique_mat_ids = sorted(set(face_mats.tolist()))
                for mat_id in unique_mat_ids:
                    blend_mat_name = (
                        sidecar_mat_names[mat_id]
                        if mat_id < len(sidecar_mat_names)
                        else f"material_{mat_id}"
                    )
                    sub_mat_name = f"{mat_name}:{blend_mat_name}"
                    mask = face_mats == mat_id
                    sub_faces = faces[mask]
                    if len(sub_faces) == 0:
                        continue

                    f.write(f"\nusemtl {sub_mat_name}\n")

                    if has_twig_uvs:
                        uv_base_start = proto_uv_starts[proto_idx]
                        # Get original face indices for this sub-material
                        face_indices_in_proto = np.where(mask)[0]
                        for local_fi, face in zip(face_indices_in_proto, sub_faces):
                            v0 = face[0] + trunk_vert_count + 1
                            v1 = face[1] + trunk_vert_count + 1
                            v2 = face[2] + trunk_vert_count + 1
                            uv0 = uv_base_start + local_fi * 3 + 1
                            uv1 = uv_base_start + local_fi * 3 + 2
                            uv2 = uv_base_start + local_fi * 3 + 3
                            f.write(f"f {v0}/{uv0} {v1}/{uv1} {v2}/{uv2}\n")
                    else:
                        for face in sub_faces:
                            v0 = face[0] + trunk_vert_count + 1
                            v1 = face[1] + trunk_vert_count + 1
                            v2 = face[2] + trunk_vert_count + 1
                            f.write(f"f {v0} {v1} {v2}\n")
            else:
                # No sub-material info: single material for all faces
                f.write(f"\nusemtl {mat_name}\n")

                if has_twig_uvs:
                    uv_base = proto_uv_starts[proto_idx]
                    for fi, face in enumerate(faces):
                        v0 = face[0] + trunk_vert_count + 1
                        v1 = face[1] + trunk_vert_count + 1
                        v2 = face[2] + trunk_vert_count + 1
                        uv0 = uv_base + fi * 3 + 1
                        uv1 = uv_base + fi * 3 + 2
                        uv2 = uv_base + fi * 3 + 3
                        f.write(f"f {v0}/{uv0} {v1}/{uv1} {v2}/{uv2}\n")
                else:
                    for face in faces:
                        v0 = face[0] + trunk_vert_count + 1
                        v1 = face[1] + trunk_vert_count + 1
                        v2 = face[2] + trunk_vert_count + 1
                        f.write(f"f {v0} {v1} {v2}\n")


def write_combined_obj(
    tree_entries: List[Tuple[Path, float, float, float, str]],
    output_path: Path,
    helios_spectra_leaves: str = "deciduous",
) -> Path:
    """Merge all individual tree OBJs into a single combined OBJ at CSV positions.

    Uses a two-pass streaming approach to avoid holding all geometry in RAM:
    - Pass 1: Stream vertices and UVs directly to disk, collecting only face offsets
    - Pass 2: Stream faces to disk, re-reading each source OBJ file

    Args:
        tree_entries: List of (obj_path, x, y, z, species_name) tuples
        output_path: Path to write the combined OBJ file
        helios_spectra_leaves: Helios spectra type for leaves material

    Returns:
        Path to generated combined OBJ file
    """
    import tempfile

    _log_memory("Before combined OBJ")

    mtl_name = output_path.stem + ".mtl"
    mtl_path = output_path.with_suffix(".mtl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect MTL files for material merging
    mtl_files: List[Path] = []

    # Per-tree offsets: [(obj_path, x, y, z, vert_offset, uv_offset)]
    tree_offsets: List[Tuple[Path, float, float, float, int, int]] = []
    total_verts = 0
    total_uvs = 0
    total_faces = 0

    # PASS 1: Stream vertices and UVs to a temp file, record offsets per tree
    temp_geom = tempfile.NamedTemporaryFile(
        mode="w", suffix=".obj", dir=output_path.parent, delete=False
    )
    temp_geom_path = Path(temp_geom.name)

    try:
        for obj_path, x, y, z, _species in tree_entries:
            if not obj_path.exists():
                continue

            obj_mtl = obj_path.with_suffix(".mtl")
            if obj_mtl.exists():
                mtl_files.append(obj_mtl)

            local_verts = 0
            local_uvs = 0
            vert_offset = total_verts
            uv_offset = total_uvs

            with open(obj_path, "r") as f:
                for line in f:
                    if line.startswith("v "):
                        parts = line.split()
                        vx = float(parts[1]) + x
                        vy = float(parts[2]) + y
                        vz = float(parts[3]) + z
                        temp_geom.write(f"v {vx:.6f} {vy:.6f} {vz:.6f}\n")
                        local_verts += 1
                    elif line.startswith("vt "):
                        temp_geom.write(line)
                        local_uvs += 1

            tree_offsets.append((obj_path, x, y, z, vert_offset, uv_offset))
            total_verts += local_verts
            total_uvs += local_uvs

        temp_geom.close()

        _log_memory("After pass 1 (vertices/UVs)")

        # PASS 2: Write final OBJ by concatenating geometry + streaming faces
        with open(output_path, "w") as out:
            out.write("# Helios++ combined forest mesh\n")
            out.write(f"mtllib {mtl_name}\n\n")

            # Copy geometry from temp file
            with open(temp_geom_path, "r") as geom:
                for line in geom:
                    out.write(line)
            out.write("\n")

            # Stream faces from each source OBJ, applying offsets
            # Write per-tree with usemtl directives inline (valid OBJ format)
            for obj_path, _, _, _, v_off, uv_off in tree_offsets:
                current_mtl = None
                with open(obj_path, "r") as f:
                    for line in f:
                        if line.startswith("usemtl "):
                            mat = line.strip().split(maxsplit=1)[1]
                            if mat != current_mtl:
                                out.write(f"usemtl {mat}\n")
                                current_mtl = mat
                        elif line.startswith("f "):
                            out.write(_offset_face_line(line, v_off, uv_off))
                            total_faces += 1

    finally:
        # Clean up temp file
        temp_geom_path.unlink(missing_ok=True)

    # Merge material definitions from all individual MTL files
    _write_combined_mtl(mtl_path, mtl_files, helios_spectra_leaves)

    _log_memory("After combined OBJ complete")

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
    proto_materials: Optional[Dict[int, Tuple[str, Optional[Path], Optional[List[str]]]]] = None,
    per_proto_face_mats: Optional[Dict[int, np.ndarray]] = None,
    tree_dir: Optional[Path] = None,
    mat_prefix: str = "",
    classification_codes: Optional[Dict[str, int]] = None,
) -> None:
    """Write Helios-compatible MTL file with per-twig leaf/wood materials.

    When sidecar material data is available, creates separate sub-materials
    for leaf and wood face groups (e.g. `twig_name:BeechLeaves` and
    `twig_name:BeechTwigs`). Wood sub-materials use helios_spectra "wood",
    leaf sub-materials use the configured leaf spectra type.

    Helios++ uses custom MTL properties:
        helios_spectra  - ECOSTRESS spectral library identifier
        helios_classification - ASPRS point classification (4 = high vegetation)
            or 3-digit code when helios_classification is enabled
    """
    from .mesh_simplify import classify_material

    def _get_classification(material_class: str) -> int:
        if classification_codes:
            return classification_codes.get(material_class, 4)
        return 4

    with open(mtl_path, "w") as f:
        f.write("# Helios++ compatible material\n\n")

        # Bark material
        f.write(f"newmtl {mat_prefix}bark\n")
        f.write("Ka 0.1 0.1 0.1\n")
        f.write("Kd 0.4 0.3 0.2\n")
        f.write("Ks 0.05 0.05 0.05\n")
        if bark_texture:
            rel_texture = f"textures/{bark_texture.name}"
            f.write(f"map_Kd {rel_texture}\n")
        f.write("helios_spectra wood\n")
        f.write(f"helios_classification {_get_classification('bark')}\n")

        # Per-twig materials
        if proto_materials:
            for proto_idx in sorted(proto_materials.keys()):
                mat_name, diffuse_path, sidecar_mat_names = proto_materials[proto_idx]
                face_mats = (per_proto_face_mats or {}).get(proto_idx)

                # Copy diffuse texture to output if needed
                if diffuse_path and diffuse_path.exists() and tree_dir:
                    tex_out_dir = tree_dir / "textures"
                    tex_out_dir.mkdir(exist_ok=True)
                    dest = tex_out_dir / diffuse_path.name
                    if not dest.exists():
                        shutil.copy2(diffuse_path, dest)

                if face_mats is not None and sidecar_mat_names:
                    # Write sub-materials for each Blender material
                    unique_mat_ids = sorted(set(face_mats.tolist()))
                    for mat_id in unique_mat_ids:
                        blend_mat_name = (
                            sidecar_mat_names[mat_id]
                            if mat_id < len(sidecar_mat_names)
                            else f"material_{mat_id}"
                        )
                        sub_mat_name = f"{mat_prefix}{mat_name}:{blend_mat_name}"
                        mat_class = classify_material(blend_mat_name)

                        f.write(f"\nnewmtl {sub_mat_name}\n")
                        if mat_class in ("wood", "bark"):
                            f.write("Ka 0.1 0.1 0.1\n")
                            f.write("Kd 0.4 0.3 0.2\n")
                            f.write("Ks 0.05 0.05 0.05\n")
                            f.write("helios_spectra wood\n")
                        else:
                            f.write("Ka 0.1 0.15 0.05\n")
                            f.write("Kd 0.8 0.8 0.8\n")
                            f.write("Ks 0.2 0.2 0.2\n")
                            if diffuse_path and diffuse_path.exists():
                                f.write(f"map_Kd textures/{diffuse_path.name}\n")
                            f.write(f"helios_spectra {helios_spectra_leaves}\n")
                        f.write(f"helios_classification {_get_classification(mat_class)}\n")
                else:
                    # No sub-material info: single material
                    f.write(f"\nnewmtl {mat_prefix}{mat_name}\n")
                    f.write("Ka 0.1 0.15 0.05\n")
                    f.write("Kd 0.8 0.8 0.8\n")
                    f.write("Ks 0.2 0.2 0.2\n")
                    if diffuse_path and diffuse_path.exists():
                        f.write(f"map_Kd textures/{diffuse_path.name}\n")
                    f.write(f"helios_spectra {helios_spectra_leaves}\n")
                    f.write(f"helios_classification {_get_classification('leaf')}\n")
        else:
            # Fallback: single generic leaves material
            f.write(f"\nnewmtl {mat_prefix}leaves\n")
            f.write("Ka 0.1 0.15 0.05\n")
            f.write("Kd 0.3 0.5 0.15\n")
            f.write("Ks 0.2 0.2 0.2\n")
            f.write(f"helios_spectra {helios_spectra_leaves}\n")
            f.write(f"helios_classification {_get_classification('leaf')}\n")


def _write_combined_mtl(
    mtl_path: Path,
    source_mtl_files: List[Path],
    helios_spectra_leaves: str = "deciduous",
) -> None:
    """Merge material definitions from individual tree MTL files into one combined MTL.

    Deduplicates materials by name, keeping the first definition encountered.
    """
    seen_materials: Dict[str, List[str]] = {}

    for src_mtl in source_mtl_files:
        if not src_mtl.exists():
            continue
        current_name = None
        current_lines: List[str] = []
        with open(src_mtl, "r") as f:
            for line in f:
                if line.startswith("newmtl "):
                    if current_name and current_name not in seen_materials:
                        seen_materials[current_name] = current_lines
                    current_name = line.strip().split(maxsplit=1)[1]
                    current_lines = [line]
                elif current_name is not None:
                    current_lines.append(line)
        if current_name and current_name not in seen_materials:
            seen_materials[current_name] = current_lines

    with open(mtl_path, "w") as f:
        f.write("# Helios++ combined forest material\n\n")
        # Write bark first
        if "bark" in seen_materials:
            for line in seen_materials["bark"]:
                f.write(line)
            f.write("\n")
        for mat_name in sorted(seen_materials.keys()):
            if mat_name == "bark":
                continue
            for line in seen_materials[mat_name]:
                f.write(line)
            f.write("\n")

    if not seen_materials:
        # Fallback if no MTL files found
        _write_helios_mtl(mtl_path, None, helios_spectra_leaves)


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
    simplification_ratios: Optional[Dict[str, float]] = None,
    per_species_ratios: Optional[Dict[str, Dict[str, float]]] = None,
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

    if decimate_ratio >= 1.0 and stem_decimate_ratio >= 1.0:
        print(
            "  Decimate ratios = 1.0: no OBJ decimation applied.\n"
            "  NOTE: Twig mesh geometry reflects [twigs] conversion settings\n"
            "  (alpha_trim, smooth_boundary, interior_decimate_ratio)."
        )

    forest_data = pd.read_csv(csv_path)
    if "fid" not in forest_data.columns:
        forest_data["fid"] = range(1, len(forest_data) + 1)
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    import time

    t_trees_start = time.perf_counter()

    obj_files: List[Tuple[Path, float, float, float, str]] = []
    for assembly_path in sorted(assembly_files):
        tree_dir_name = assembly_path.parent.name
        tree_id_str = tree_dir_name.replace("tree_", "")

        species_dir = assembly_path.parent.parent.name
        species_name = species_dir.replace("_", " ").title()

        is_conifer = any(kw in species_dir.lower() for kw in CONIFER_KEYWORDS)
        spectra = "conifer" if is_conifer else "deciduous"

        # Resolve per-species simplification overrides if configured
        tree_ratios = simplification_ratios
        if tree_ratios and per_species_ratios and species_dir in per_species_ratios:
            tree_ratios = {**tree_ratios, **per_species_ratios[species_dir]}

        obj_path = convert_tree_to_obj(
            assembly_usda_path=assembly_path,
            species_name=species_name,
            decimate_ratio=decimate_ratio,
            stem_decimate_ratio=stem_decimate_ratio,
            helios_spectra_leaves=spectra,
            simplification_ratios=tree_ratios,
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

    t_trees_end = time.perf_counter()
    print(
        f"\n  Individual OBJ export: {len(obj_files)} trees in "
        f"{t_trees_end - t_trees_start:.1f}s"
    )

    if generate_scene_xml and obj_files:
        from growpy.io.helios_scene import generate_helios_scene

        scene_path = output_dir / "helios_scene.xml"
        generate_helios_scene(tree_entries=obj_files, output_path=scene_path)

    if generate_combined_obj and obj_files:
        t_combined_start = time.perf_counter()

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

        t_combined_end = time.perf_counter()
        print(
            f"  Combined OBJ assembly: {t_combined_end - t_combined_start:.1f}s"
        )

    print(f"\nOBJ export complete: {len(obj_files)} trees converted")
    return obj_files
