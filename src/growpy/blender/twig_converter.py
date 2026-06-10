"""Twig conversion for GrowPy Blender addon.

Converts twig .blend sources to USD files used by Nanite assembly export.
Produces both static and skeletal variants and caches results per session.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import bpy

_PXR_READY = False
_TWIG_CACHE: dict[str, tuple[Path, Path]] = {}


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


def _collect_mesh_objects_from_blend(blend_path: Path) -> list[bpy.types.Object]:
    mesh_objects: list[bpy.types.Object] = []
    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)

    for obj in data_to.objects:
        if obj and obj.type == "MESH":
            mesh_objects.append(obj)
    return mesh_objects


def _link_temp_objects(mesh_objects: list[bpy.types.Object]) -> bpy.types.Collection:
    temp = bpy.data.collections.new("__growpy_twigs_tmp")
    bpy.context.scene.collection.children.link(temp)
    for obj in mesh_objects:
        if obj.name not in temp.objects:
            temp.objects.link(obj)
    return temp


def _cleanup_temp(
    temp_collection: bpy.types.Collection, mesh_objects: list[bpy.types.Object]
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


def _extract_textures_from_object(
    obj: bpy.types.Object,
) -> list[dict[str, Any]]:
    """Extract image texture file paths from Blender material nodes."""
    textures: list[dict[str, Any]] = []
    if not obj.data.materials:
        return textures

    for mat in obj.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "TEX_IMAGE" or node.image is None:
                continue
            filepath = bpy.path.abspath(node.image.filepath)
            if filepath and os.path.isfile(filepath):
                name_lower = Path(filepath).stem.lower()
                if any(k in name_lower for k in ["normal", "norm", "nrm"]):
                    tex_type = "normal"
                elif any(k in name_lower for k in ["alpha", "opacity", "mask"]):
                    continue  # Skip alpha for Nanite
                else:
                    tex_type = "diffuse"
                textures.append({"type": tex_type, "path": filepath})
    return textures


def _add_twig_material(
    stage: Any,
    mesh_prim: Any,
    root_path: Any,
    twig_name: str,
    textures: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    """Add leaf material with textures to a twig mesh prim."""
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    LEAF_GREEN = Gf.Vec3f(0.3, 0.6, 0.2)

    materials_path = str(root_path) + "/Materials"
    UsdGeom.Scope.Define(stage, materials_path)

    mat_name = f"{_sanitize_identifier(twig_name)}_leaf"
    mat_full = f"{materials_path}/{mat_name}"
    mat = UsdShade.Material.Define(stage, mat_full)

    shader = UsdShade.Shader.Define(stage, f"{mat_full}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")

    diffuse_tex = None
    normal_tex = None
    for t in textures:
        if t["type"] == "diffuse" and diffuse_tex is None:
            diffuse_tex = Path(t["path"])
        elif t["type"] == "normal" and normal_tex is None:
            normal_tex = Path(t["path"])

    textures_dir = output_dir / "textures"
    texture_found = False

    if diffuse_tex and diffuse_tex.is_file():
        texture_found = True
        textures_dir.mkdir(exist_ok=True)

        uv_reader = UsdShade.Shader.Define(stage, f"{mat_full}/uvmap")
        uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
        uv_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        tex_reader = UsdShade.Shader.Define(stage, f"{mat_full}/DiffuseTexture")
        tex_reader.CreateIdAttr("UsdUVTexture")
        tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
            f"./textures/{diffuse_tex.name}"
        )
        tex_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
        tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            uv_reader.ConnectableAPI(), "result"
        )
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            tex_reader.ConnectableAPI(), "rgb"
        )

        dest = textures_dir / diffuse_tex.name
        if not dest.exists():
            shutil.copy2(str(diffuse_tex), str(dest))

        if normal_tex and normal_tex.is_file():
            normal_reader = UsdShade.Shader.Define(stage, f"{mat_full}/NormalTexture")
            normal_reader.CreateIdAttr("UsdUVTexture")
            normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                f"./textures/{normal_tex.name}"
            )
            normal_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(
                "raw"
            )
            normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            normal_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                uv_reader.ConnectableAPI(), "result"
            )
            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(
                normal_reader.ConnectableAPI(), "rgb"
            )

            dest_normal = textures_dir / normal_tex.name
            if not dest_normal.exists():
                shutil.copy2(str(normal_tex), str(dest_normal))

    if not texture_found:
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(LEAF_GREEN)

    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
    binding_api.Bind(mat)


def _export_objects_to_usd(
    mesh_objects: list[bpy.types.Object],
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
        try:
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

            # Export UVs from Blender mesh
            if mesh.uv_layers.active:
                uv_layer = mesh.uv_layers.active.data
                uvs = []
                for tri in mesh.loop_triangles:
                    for loop_idx in tri.loops:
                        uv = uv_layer[loop_idx].uv
                        uvs.append(Gf.Vec2f(float(uv[0]), float(uv[1])))
                if uvs:
                    primvars_api = UsdGeom.PrimvarsAPI(usd_mesh)
                    st = primvars_api.CreatePrimvar(
                        "st",
                        Sdf.ValueTypeNames.TexCoord2fArray,
                        UsdGeom.Tokens.faceVarying,
                    )
                    st.Set(uvs)

            # Extract textures and add material
            obj_textures = _extract_textures_from_object(obj)
            _add_twig_material(
                stage, mesh_prim, root_path, root_name, obj_textures, output_path.parent
            )

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

        except Exception:
            pass
        finally:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass

    stage.SetDefaultPrim(root_prim)
    stage.GetRootLayer().Save()


def convert_blend_to_usd(
    blend_path: str | Path, output_dir: str | Path
) -> tuple[Path, Path]:
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
    twig_blend_paths: list[str],
    output_dir: str | Path,
    use_skeletal_mesh: bool,
) -> dict[str, list[Path]]:
    """Convert all twig sources and return mapping twig_type -> USD paths."""
    result: dict[str, list[Path]] = {
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
