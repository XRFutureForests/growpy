"""USD export utilities for GrowPy Blender addon.

Self-contained helpers to export Grove tree models to USD with optional UsdSkel
data and to build Unreal Engine 5.7+ Nanite Assembly wrappers.
"""

from __future__ import annotations

import math
import os
import random
import shutil
from pathlib import Path
from typing import Any

import bpy

from .skeleton_builder import (
    build_joint_hierarchy,
    calculate_vertex_weights,
    filter_bones_for_mesh,
)

_PXR_READY = False


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
    return clean or "asset"


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


def _build_matrix(tx: float, ty: float, tz: float) -> Any:
    from pxr import Gf

    m = Gf.Matrix4d(1.0)
    m.SetTranslateOnly(Gf.Vec3d(tx, ty, tz))
    return m


def _get_tree_offset(
    model: Any, bones_info: list[tuple] | None
) -> tuple[float, float, float]:
    """Get tree world-space offset for skeleton alignment.

    Tries model.location first, falls back to the tree root bone start_point.
    """
    if hasattr(model, "location") and model.location is not None:
        loc = model.location
        if hasattr(loc, "x"):
            return (loc.x, loc.y, loc.z)

    if bones_info:
        for bone in bones_info:
            is_tree_root = bone[0]
            if is_tree_root:
                sp = bone[2]
                return (sp.x, sp.y, sp.z)

    return (0.0, 0.0, 0.0)


def _add_bark_material(
    stage: Any,
    mesh_prim: Any,
    root_path: Any,
    species_name: str,
    bark_texture_path: str | None = None,
) -> None:
    """Add bark material with optional texture to the tree mesh.

    Creates a UsdPreviewSurface material with bark texture if a valid texture
    file is provided. Falls back to solid brown color otherwise. Copies texture
    files to a textures/ subdirectory next to the USD file.
    """
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    BARK_BROWN = Gf.Vec3f(0.4, 0.3, 0.2)

    materials_path = str(root_path) + "/Materials"
    UsdGeom.Scope.Define(stage, materials_path)

    bark_mat_name = (
        f"{_sanitize_identifier(species_name)}_bark" if species_name else "bark"
    )
    mat_path = f"{materials_path}/{bark_mat_name}"
    bark_mat = UsdShade.Material.Define(stage, mat_path)

    shader = UsdShade.Shader.Define(stage, f"{mat_path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")

    texture_found = False
    if bark_texture_path and os.path.isfile(bark_texture_path):
        texture_found = True
        texture_file = Path(bark_texture_path)

        uv_reader = UsdShade.Shader.Define(stage, f"{mat_path}/uvmap")
        uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
        uv_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        tex_reader = UsdShade.Shader.Define(stage, f"{mat_path}/DiffuseTexture")
        tex_reader.CreateIdAttr("UsdUVTexture")
        tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
            f"./textures/{texture_file.name}"
        )
        tex_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(
            "sRGB"
        )
        tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            uv_reader.ConnectableAPI(), "result"
        )

        shader.CreateInput(
            "diffuseColor", Sdf.ValueTypeNames.Color3f
        ).ConnectToSource(tex_reader.ConnectableAPI(), "rgb")

        # Check for a matching normal map (same stem with _normal suffix)
        normal_candidates = [
            texture_file.parent / f"{texture_file.stem}_normal{texture_file.suffix}",
            texture_file.parent / f"{texture_file.stem}Normal{texture_file.suffix}",
        ]
        normal_file = None
        for candidate in normal_candidates:
            if candidate.is_file():
                normal_file = candidate
                break

        if normal_file:
            normal_reader = UsdShade.Shader.Define(
                stage, f"{mat_path}/NormalTexture"
            )
            normal_reader.CreateIdAttr("UsdUVTexture")
            normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                f"./textures/{normal_file.name}"
            )
            normal_reader.CreateInput(
                "sourceColorSpace", Sdf.ValueTypeNames.Token
            ).Set("raw")
            normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            normal_reader.CreateInput(
                "st", Sdf.ValueTypeNames.Float2
            ).ConnectToSource(uv_reader.ConnectableAPI(), "result")
            shader.CreateInput(
                "normal", Sdf.ValueTypeNames.Normal3f
            ).ConnectToSource(normal_reader.ConnectableAPI(), "rgb")

        # Copy texture files to output textures/ subdirectory
        output_dir = Path(stage.GetRootLayer().realPath).parent
        textures_dir = output_dir / "textures"
        textures_dir.mkdir(exist_ok=True)

        dest = textures_dir / texture_file.name
        if not dest.exists():
            shutil.copy2(str(texture_file), str(dest))

        if normal_file:
            dest_normal = textures_dir / normal_file.name
            if not dest_normal.exists():
                shutil.copy2(str(normal_file), str(dest_normal))

    if not texture_found:
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(BARK_BROWN)

    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)
    bark_mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
    binding_api.Bind(bark_mat)


def build_tree_mesh_usd(
    model: Any,
    output_path: Path,
    species_name: str,
    tree_id: str | None = None,
    bones_info: list[tuple] | None = None,
    include_skeleton: bool = True,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
    bark_texture_path: str | None = None,
) -> bool:
    """Export a single Grove tree model to USD.

    The output contains a root Xform/SkelRoot and one mesh. If bone data is
    provided, a UsdSkel skeleton and vertex skinning primvars are included.
    """
    _ensure_pxr()
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

    output_path.parent.mkdir(parents=True, exist_ok=True)

    species_key = _sanitize_identifier(species_name)
    tree_key = f"_{tree_id}" if tree_id else ""
    root_name = f"{species_key}{tree_key}_stems"
    mesh_name = f"{root_name}_mesh"
    skel_name = f"{root_name}_skel"

    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)

    root_path = Sdf.Path(f"/{root_name}")
    if include_skeleton:
        root_prim = UsdSkel.Root.Define(stage, root_path).GetPrim()
    else:
        root_prim = UsdGeom.Xform.Define(stage, root_path).GetPrim()

    mesh_prim = UsdGeom.Mesh.Define(stage, root_path.AppendChild(mesh_name)).GetPrim()
    mesh = UsdGeom.Mesh(mesh_prim)

    points = [Gf.Vec3f(p.x, p.y, p.z) for p in model.points]
    face_counts = [len(face) for face in model.faces]
    face_indices: list[int] = []
    for face in model.faces:
        face_indices.extend(face)

    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr(face_counts)
    mesh.CreateFaceVertexIndicesAttr(face_indices)

    if hasattr(model, "uvs") and model.uvs:
        primvars = UsdGeom.PrimvarsAPI(mesh)
        uvs = [Gf.Vec2f(float(u[0]), float(u[1])) for u in model.uvs]
        st = primvars.CreatePrimvar(
            "st",
            Sdf.ValueTypeNames.TexCoord2fArray,
            UsdGeom.Tokens.faceVarying,
        )
        st.Set(uvs)

    if include_skeleton and bones_info:
        _apply_api_schema(root_prim, "SkelBindingAPI")
        _apply_api_schema(mesh_prim, "SkelBindingAPI")

        # Tree offset: bone positions from Grove are in world space, while
        # mesh points from build_models() are tree-local. Subtract the tree
        # location so the skeleton aligns with the mesh.
        tree_offset = _get_tree_offset(model, bones_info)

        bone_offset = 0
        if hasattr(model, "point_attribute_bone_id") and model.point_attribute_bone_id:
            bone_offset = min(model.point_attribute_bone_id)

        filtered_bones, bone_to_joint_map = filter_bones_for_mesh(
            model,
            bones_info,
            bone_id_offset=bone_offset,
        )

        (
            joint_tokens,
            bind_positions,
            rest_positions,
            _bone_id_to_joint,
        ) = build_joint_hierarchy(
            filtered_bones, bone_id_offset=0, tree_offset=tree_offset
        )

        skel_path = root_path.AppendChild(skel_name)
        skel = UsdSkel.Skeleton.Define(stage, skel_path)
        skel.CreateJointsAttr(joint_tokens)
        skel.CreateBindTransformsAttr([_build_matrix(*p) for p in bind_positions])
        skel.CreateRestTransformsAttr([_build_matrix(*p) for p in rest_positions])

        root_rel = root_prim.CreateRelationship("skel:skeleton", custom=False)
        root_rel.SetTargets([skel_path])
        mesh_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
        mesh_rel.SetTargets([skel_path])

        indices, weights = calculate_vertex_weights(
            model=model,
            bone_to_joint_map=bone_to_joint_map,
            bones_info=filtered_bones,
            element_size=2,
            junction_blend_distance=junction_blend_distance,
            blend_mode=blend_mode,
        )

        if not indices or not weights:
            vert_count = len(points)
            indices = [0, 0] * vert_count
            weights = [1.0, 0.0] * vert_count

        primvars = UsdGeom.PrimvarsAPI(mesh)
        joint_idx = primvars.CreatePrimvar(
            "skel:jointIndices",
            Sdf.ValueTypeNames.IntArray,
            UsdGeom.Tokens.vertex,
        )
        joint_idx.Set(indices)
        joint_idx.SetElementSize(2)

        joint_w = primvars.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_w.Set(weights)
        joint_w.SetElementSize(2)

    _add_bark_material(stage, mesh_prim, root_path, species_name, bark_texture_path)

    stage.SetDefaultPrim(root_prim)
    stage.GetRootLayer().Save()
    return True


def _normal_to_quaternion(
    normal: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    """Create quaternion rotating +X onto the target normal."""
    nx, ny, nz = normal
    n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
    if n_len <= 1e-8:
        return (1.0, 0.0, 0.0, 0.0)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len

    ax, ay, az = 1.0, 0.0, 0.0
    dot = ax * nx + ay * ny + az * nz

    if dot >= 1.0 - 1e-8:
        return (1.0, 0.0, 0.0, 0.0)
    if dot <= -1.0 + 1e-8:
        return (0.0, 0.0, 1.0, 0.0)

    cx = ay * nz - az * ny
    cy = az * nx - ax * nz
    cz = ax * ny - ay * nx
    s = math.sqrt((1.0 + dot) * 2.0)
    inv = 1.0 / s
    qw = 0.5 * s
    qx = cx * inv
    qy = cy * inv
    qz = cz * inv
    return (qw, qx, qy, qz)


def _add_twig_instances(
    stage: Any,
    assembly_name: str,
    twig_usd_paths: dict[str, list[Path]],
    twig_placements: dict[str, list[dict[str, Any]]],
    use_skeletal_mesh: bool,
) -> None:
    from pxr import Gf, Sdf, UsdGeom

    prototype_scope = stage.DefinePrim(f"/{assembly_name}/TwigPrototypes", "Scope")
    if not use_skeletal_mesh:
        UsdGeom.Imageable(prototype_scope).MakeInvisible()

    type_to_indices: dict[str, list[int]] = {}
    prototype_paths: list[Any] = []
    dedup: dict[str, int] = {}

    for twig_type, path_list in twig_usd_paths.items():
        for twig_path in path_list:
            key = twig_path.name
            if key in dedup:
                type_to_indices.setdefault(twig_type, []).append(dedup[key])
                continue

            idx = len(prototype_paths)
            dedup[key] = idx
            type_to_indices.setdefault(twig_type, []).append(idx)

            proto_name = _sanitize_identifier(twig_path.stem)
            proto_path = f"/{assembly_name}/TwigPrototypes/{proto_name}"
            proto_prim = stage.DefinePrim(proto_path, "Xform")
            proto_prim.SetInstanceable(True)

            # The twig USD root prim strips _skeletal/_static from the name
            twig_root_name = _sanitize_identifier(
                twig_path.stem.replace("_skeletal", "").replace("_static", "")
            )
            child_type = "SkelRoot" if use_skeletal_mesh else "Xform"
            child = stage.DefinePrim(f"{proto_path}/{twig_root_name}", child_type)
            child.GetReferences().AddReference(
                f"./twigs/{twig_path.name}",
                f"/{twig_root_name}",
            )

            prototype_paths.append(Sdf.Path(proto_path))

    if not prototype_paths:
        return

    instancer_prim = stage.DefinePrim(
        f"/{assembly_name}/TwigInstances", "PointInstancer"
    )
    instancer = UsdGeom.PointInstancer(instancer_prim)
    instancer.CreatePrototypesRel().SetTargets(prototype_paths)

    rng = random.Random(42)
    all_indices = list(range(len(prototype_paths)))

    positions = []
    orientations = []
    scales = []
    proto_indices = []

    for twig_type, placements in twig_placements.items():
        if not placements:
            continue

        pool = type_to_indices.get(twig_type, all_indices)
        if not pool:
            continue

        for p in placements:
            pos = p.get("position", (0.0, 0.0, 0.0))
            nrm = p.get("normal", (1.0, 0.0, 0.0))
            scl = float(p.get("scale", 1.0))

            q = _normal_to_quaternion(nrm)
            positions.append(Gf.Vec3f(float(pos[0]), float(pos[1]), float(pos[2])))
            orientations.append(
                Gf.Quath(float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            )
            scales.append(Gf.Vec3f(scl, scl, scl))
            proto_indices.append(rng.choice(pool))

    instancer.CreatePositionsAttr().Set(positions)
    instancer.CreateOrientationsAttr().Set(orientations)
    instancer.CreateScalesAttr().Set(scales)
    instancer.CreateProtoIndicesAttr().Set(proto_indices)

    if use_skeletal_mesh:
        _apply_api_schema(instancer_prim, "NaniteAssemblySkelBindingAPI")

        bind_joints = ["tree_root"] * len(positions)
        bind_weights = [1.0] * len(positions)
        joints_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        joints_attr.Set(bind_joints)
        joints_attr.SetMetadata("interpolation", "uniform")
        joints_attr.SetMetadata("elementSize", 1)

        weights_attr = instancer_prim.CreateAttribute(
            "primvars:unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        weights_attr.Set(bind_weights)
        weights_attr.SetMetadata("interpolation", "uniform")
        weights_attr.SetMetadata("elementSize", 1)


def create_nanite_assembly(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    tree_id: str | None = None,
    twig_usd_paths: dict[str, list[Path]] | None = None,
    twig_placements: dict[str, list[dict[str, Any]]] | None = None,
    use_skeletal_mesh: bool = True,
) -> bool:
    """Create Nanite Assembly USD wrapping a tree mesh and optional twig instances."""
    _ensure_pxr()
    from pxr import Sdf, Usd, UsdGeom

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    species_key = _sanitize_identifier(species_name)
    tree_key = f"_{tree_id}" if tree_id else ""
    tree_root_name = f"{species_key}{tree_key}_stems"
    assembly_name = f"{species_key}{tree_key}_nanite_assembly"

    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)

    root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
    stage.SetDefaultPrim(root_prim)

    _apply_api_schema(root_prim, "NaniteAssemblyRootAPI")
    root_prim.SetMetadata("kind", "group")
    mesh_type = "skeletalMesh" if use_skeletal_mesh else "staticMesh"
    root_prim.CreateAttribute(
        "unreal:naniteAssembly:meshType",
        Sdf.ValueTypeNames.Token,
        custom=False,
        variability=Sdf.VariabilityUniform,
    ).Set(mesh_type)

    tree_prim_type = "SkelRoot" if use_skeletal_mesh else "Xform"
    tree_prim = stage.DefinePrim(f"/{assembly_name}/{tree_root_name}", tree_prim_type)
    tree_prim.GetReferences().AddReference(
        f"./{tree_usd_path.name}", f"/{tree_root_name}"
    )

    if use_skeletal_mesh:
        skel_rel = root_prim.CreateRelationship(
            "unreal:naniteAssembly:skeleton",
            custom=True,
        )
        skel_rel.SetTargets(
            [Sdf.Path(f"/{assembly_name}/{tree_root_name}/{tree_root_name}_skel")]
        )

    if twig_usd_paths and twig_placements:
        _add_twig_instances(
            stage=stage,
            assembly_name=assembly_name,
            twig_usd_paths=twig_usd_paths,
            twig_placements=twig_placements,
            use_skeletal_mesh=use_skeletal_mesh,
        )

    stage.GetRootLayer().Save()
    return True
