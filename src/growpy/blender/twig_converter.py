"""Twig conversion for GrowPy Blender addon.

Converts twig .blend sources to USD files used by Nanite assembly export.
Produces both static and skeletal variants and caches results per session.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bpy

_PXR_READY = False
_TWIG_CACHE: Dict[str, Tuple[Path, Path]] = {}


def _ensure_pxr() -> None:
    global _PXR_READY
    if _PXR_READY:
        return

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()

    env_path = os.environ.get("PXR_PLUGINPATH_NAME")
    if env_path:
        try:
            from pxr import Plug

            abs_path = os.path.abspath(env_path)
            if os.path.exists(abs_path):
                reg = Plug.Registry()
                if not reg.GetPluginWithName("unreal"):
                    reg.RegisterPlugins(abs_path)
        except Exception:
            pass

    _PXR_READY = True


def _sanitize_identifier(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch.lower())
        elif ch in (" ", "-"):
            out.append("_")
    clean = "".join(out).strip("_")
    return clean or "twig"


def _classify_twig_type(stem: str) -> str:
    s = stem.lower()
    if "dead" in s:
        return "twig_dead"
    if "upward" in s:
        return "twig_upward"
    if "lateral" in s or "short" in s:
        return "twig_short"
    if "apical" in s or "long" in s:
        return "twig_long"
    return "twig_long"


def _apply_api_schema(prim: Any, schema_name: str) -> None:
    from pxr import Sdf

    api_schemas = prim.GetMetadata("apiSchemas")
    if api_schemas:
        items = list(api_schemas.prependedItems)
        if schema_name not in items:
            items.append(schema_name)
            api_schemas.prependedItems = items
            prim.SetMetadata("apiSchemas", api_schemas)
        return

    op = Sdf.TokenListOp()
    op.prependedItems = [schema_name]
    prim.SetMetadata("apiSchemas", op)


def _collect_mesh_objects_from_blend(blend_path: Path) -> List[bpy.types.Object]:
    mesh_objects: List[bpy.types.Object] = []
    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)

    for obj in data_to.objects:
        if obj and obj.type == "MESH":
            mesh_objects.append(obj)
    return mesh_objects


def _link_temp_objects(mesh_objects: List[bpy.types.Object]) -> bpy.types.Collection:
    temp = bpy.data.collections.new("__growpy_twigs_tmp")
    bpy.context.scene.collection.children.link(temp)
    for obj in mesh_objects:
        if obj.name not in temp.objects:
            temp.objects.link(obj)
    return temp


def _cleanup_temp(
    temp_collection: bpy.types.Collection, mesh_objects: List[bpy.types.Object]
) -> None:
    for obj in mesh_objects:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
    try:
        bpy.data.collections.remove(temp_collection)
    except Exception:
        pass


def _export_objects_to_usd(
    mesh_objects: List[bpy.types.Object],
    output_path: Path,
    include_skeleton: bool,
) -> None:
    _ensure_pxr()
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

    root_name = _sanitize_identifier(
        output_path.stem.replace("_skeletal", "").replace("_static", "")
    )
    if output_path.exists():
        output_path.unlink()
    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)

    root_path = Sdf.Path(f"/{root_name}")
    if include_skeleton:
        root_prim = UsdSkel.Root.Define(stage, root_path).GetPrim()
        _apply_api_schema(root_prim, "SkelBindingAPI")
        skel_path = root_path.AppendChild(f"{root_name}_skel")
        skel = UsdSkel.Skeleton.Define(stage, skel_path)
        skel.CreateJointsAttr(["root"])

        bind = Gf.Matrix4d(1.0)
        rest = Gf.Matrix4d(1.0)
        skel.CreateBindTransformsAttr([bind])
        skel.CreateRestTransformsAttr([rest])

        root_rel = root_prim.CreateRelationship("skel:skeleton", custom=False)
        root_rel.SetTargets([skel_path])
    else:
        root_prim = UsdGeom.Xform.Define(stage, root_path).GetPrim()
        skel_path = None

    depsgraph = bpy.context.evaluated_depsgraph_get()

    for obj in mesh_objects:
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        if mesh is None:
            continue

        mesh.calc_loop_triangles()
        mesh_name = _sanitize_identifier(obj.name)
        mesh_prim = UsdGeom.Mesh.Define(
            stage, root_path.AppendChild(mesh_name)
        ).GetPrim()
        usd_mesh = UsdGeom.Mesh(mesh_prim)

        pts = []
        for v in mesh.vertices:
            wc = eval_obj.matrix_world @ v.co
            pts.append(Gf.Vec3f(float(wc.x), float(wc.y), float(wc.z)))

        counts = []
        indices = []
        for tri in mesh.loop_triangles:
            counts.append(3)
            indices.extend(tri.vertices)

        usd_mesh.CreatePointsAttr(pts)
        usd_mesh.CreateFaceVertexCountsAttr(counts)
        usd_mesh.CreateFaceVertexIndicesAttr(indices)

        if include_skeleton and skel_path is not None:
            _apply_api_schema(mesh_prim, "SkelBindingAPI")
            mesh_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
            mesh_rel.SetTargets([skel_path])

            primvars = UsdGeom.PrimvarsAPI(usd_mesh)
            joint_indices = primvars.CreatePrimvar(
                "skel:jointIndices",
                Sdf.ValueTypeNames.IntArray,
                UsdGeom.Tokens.vertex,
            )
            joint_indices.Set([0] * len(pts))
            joint_indices.SetElementSize(1)

            joint_weights = primvars.CreatePrimvar(
                "skel:jointWeights",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.vertex,
            )
            joint_weights.Set([1.0] * len(pts))
            joint_weights.SetElementSize(1)

        eval_obj.to_mesh_clear()

    stage.SetDefaultPrim(root_prim)
    stage.GetRootLayer().Save()


def convert_blend_to_usd(
    blend_path: str | Path, output_dir: str | Path
) -> Tuple[Path, Path]:
    """Convert one twig .blend file to (skeletal_usd, static_usd)."""
    src = Path(blend_path)
    dst = Path(output_dir)
    dst.mkdir(parents=True, exist_ok=True)

    cache_key = str(src.resolve())
    if cache_key in _TWIG_CACHE:
        return _TWIG_CACHE[cache_key]

    stem = _sanitize_identifier(src.stem)
    skeletal_path = dst / f"{stem}_skeletal.usda"
    static_path = dst / f"{stem}_static.usda"

    mesh_objects = _collect_mesh_objects_from_blend(src)
    if not mesh_objects:
        raise RuntimeError(f"No mesh objects found in twig blend file: {src}")

    temp = _link_temp_objects(mesh_objects)
    try:
        _export_objects_to_usd(mesh_objects, static_path, include_skeleton=False)
        _export_objects_to_usd(mesh_objects, skeletal_path, include_skeleton=True)
    finally:
        _cleanup_temp(temp, mesh_objects)

    _TWIG_CACHE[cache_key] = (skeletal_path, static_path)
    return skeletal_path, static_path


def convert_twig_sources(
    twig_blend_paths: List[str],
    output_dir: str | Path,
    use_skeletal_mesh: bool,
) -> Dict[str, List[Path]]:
    """Convert all twig sources and return mapping twig_type -> USD paths."""
    result: Dict[str, List[Path]] = {
        "twig_long": [],
        "twig_short": [],
        "twig_upward": [],
        "twig_dead": [],
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for twig_path in twig_blend_paths:
        src = Path(twig_path)
        if not src.exists():
            continue

        skeletal_path, static_path = convert_blend_to_usd(src, out)
        selected = skeletal_path if use_skeletal_mesh else static_path
        twig_type = _classify_twig_type(src.stem)
        result.setdefault(twig_type, []).append(selected)

    return result


def clear_cache() -> None:
    _TWIG_CACHE.clear()
