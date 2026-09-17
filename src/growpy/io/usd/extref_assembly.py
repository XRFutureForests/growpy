"""Share a compound part library between trees by UE package path (XRFF-389).

A compound assembly written by `create_assembly` embeds its prototypes: every
tree carries its own copy of every part USD, and UE re-imports all of them per
tree. On an 18-cycle `silver_fir` that is 838 MB of ASCII and 915 s of import
for ONE tree. Naming the parts by package path instead takes the same tree to a
0.827 MB USD and 52.2 s, against a 795.5 s library import paid once per species.

Two measured constraints shape the code here, and neither is guessable:

* **F23 -- `meshAssetPath` does not work on a PointInstancer prototype.**
  `USDNaniteAssemblyTranslator.cpp` has exactly one call site for
  `GetExternalAssetRef`, inside `RecursivelyBuildAssembly`, and it sits AFTER
  the `if (Prim.IsA("PointInstancer")) return`. `CollectPointInstancerAssets`
  resolves prototypes only by finding a `UsdSkelSkeleton` in the prim-link
  cache; there is no asset-path fallback. The supported shape is one `Xform`
  per placement carrying `NaniteAssemblyExternalRefAPI` +
  `NaniteAssemblySkelBindingAPI`, its own transform and its own slice of the
  bindings. The PointInstancer goes away entirely.
* **F24 -- the part library must be ONE USD stage.** Imported as separate
  tasks each part gets its own material instance, and UE's
  `merge_identical_material_slots` compares `UMaterialInterface` pointers, so
  four separately-imported parts produced FIVE material slots where the
  single-stage form produced two.

The conversion is a rewrite of an already-written assembly rather than a second
authoring path on purpose: the bindJoints construction in `assembly_export` is
where the subtle failures live (a single unresolvable joint token discards the
WHOLE instancer, F11), and it should have one implementation, not two.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# UE's USD stage import lands a skeletal mesh at
# ``<destination>/<stage stem>/SkeletalMeshes/SK_<prim name>``, and it does so
# even with ``prim_path_folder_structure = False``. Measured importing
# ``silver_fir_library.usda`` (a Scope holding seven ``SkelRoot`` prims) into
# ``/Game/CompoundLib2/silver_fir``: the parts landed as
# ``silver_fir_library/SkeletalMeshes/SK_silver_fir_compound_p00`` and so on.
# Getting this wrong is not a soft failure -- an unresolvable ``meshAssetPath``
# produces an assembly with no parts, and the import still reports success.
PART_ASSET_PREFIX = "SK_"
PART_ASSET_FOLDER = "SkeletalMeshes"


def _ensure_pxr() -> None:
    from ...utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()


def library_package_path(
    destination_path: str, library_stem: str, part_name: str
) -> str:
    """UE package path a library part imports to.

    Args:
        destination_path: The ``/Game/...`` folder the library stage is
            imported into.
        library_stem: Filename stem of the library stage, without extension.
        part_name: Root prim name of the part inside the library.
    """
    if not destination_path.startswith("/Game/"):
        # A UE content path, not a filesystem one. Worth refusing rather than
        # writing: an unresolvable meshAssetPath builds an assembly with no
        # parts and the import still reports success, so the mistake shows up
        # as an invisible tree, not as an error. Git Bash rewrites a leading
        # `/Game/...` argument into `C:/Program Files/Git/Game/...` unless
        # MSYS_NO_PATHCONV=1 is set, which is exactly how this happens.
        raise ValueError(
            f"library destination must be a UE content path under /Game/, "
            f"got {destination_path!r}"
        )
    asset = f"{PART_ASSET_PREFIX}{part_name}"
    folder = f"{destination_path.rstrip('/')}/{library_stem}/{PART_ASSET_FOLDER}"
    return f"{folder}/{asset}.{asset}"


def write_part_library_usd(
    parts: Sequence[tuple[str, Path]],
    output_path: Path,
) -> Path:
    """Bake a species' compound parts into ONE referencing stage (F24).

    Args:
        parts: ``(part name, skeletal part USD)`` pairs. The part file must sit
            beside `output_path`; the reference is written relative so the
            library stays movable with the parts it names.
        output_path: Destination ``.usda``. Its stem becomes the root Scope's
            name, and therefore the folder UE imports the parts under -- see
            `library_package_path`.

    Returns:
        `output_path`.
    """
    _ensure_pxr()

    from pxr import Usd, UsdGeom

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    library_name = output_path.stem
    root = stage.DefinePrim(f"/{library_name}", "Scope")

    for name, part_file in parts:
        if not part_file.is_file():
            raise FileNotFoundError(f"library part missing: {part_file}")
        prim = stage.DefinePrim(f"/{library_name}/{name}", "SkelRoot")
        prim.GetReferences().AddReference(f"./{part_file.name}", f"/{name}")

    stage.SetDefaultPrim(root)
    stage.GetRootLayer().Save()
    logger.info(
        "part library: %d parts -> %s (%d bytes)",
        len(parts),
        output_path.name,
        output_path.stat().st_size,
    )
    return output_path


def _apply_api_schemas(prim: Any, names: Sequence[str]) -> None:
    from pxr import Sdf

    op = Sdf.TokenListOp()
    op.prependedItems = list(names)
    prim.SetMetadata("apiSchemas", op)


def convert_assembly_to_external_refs(
    source_path: Path,
    output_path: Path,
    asset_paths: dict[str, str],
) -> dict[str, Any]:
    """Rewrite a PointInstancer assembly into external-ref form (F23).

    The root, its `meshType` and `skeleton` relationship, and the stems
    reference are carried over verbatim; ``/TwigInstances`` becomes
    ``/Parts/inst_NNNNN``, one `Xform` per placement, each naming its prototype
    by UE package path and carrying its own slice of the instancer's
    ``bindJoints``/``bindJointWeights``.

    Args:
        source_path: Assembly written by `create_assembly` (PointInstancer form).
        output_path: Destination. Written beside `source_path` by convention so
            the relative stems reference still resolves -- this is checked.
        asset_paths: Prototype USD FILENAME -> UE package path. Keyed by
            filename rather than by prototype index because the index depends
            on the order `create_assembly` happened to walk `twig_usd_paths`,
            and a hybrid assembly mixes compound parts with 1:1 twigs. Every
            prototype the instancer uses must be present; a missing one would
            silently drop that prototype's whole share of the crown.

    Returns:
        Counts for logging: ``instances``, ``prototypes``, ``element_size``,
        ``file_bytes``.
    """
    _ensure_pxr()

    from pxr import Gf, Sdf, Usd, UsdGeom, Vt

    if output_path.parent.resolve() != source_path.parent.resolve():
        # The stems reference is authored `./<name>.usda` relative to the
        # assembly's own directory, so moving the assembly breaks it -- a
        # dangling reference opens fine in pxr and then crashes the editor
        # inside the Nanite hierarchy encoder (XRFF-367).
        raise ValueError(
            f"external-ref assembly must be written beside its source "
            f"({source_path.parent}), not {output_path.parent}"
        )

    stage = Usd.Stage.Open(str(source_path))
    if stage is None:
        raise ValueError(f"cannot open assembly: {source_path}")
    root = stage.GetDefaultPrim()

    instancer_prim = next(
        (p for p in stage.Traverse() if p.GetTypeName() == "PointInstancer"), None
    )
    if instancer_prim is None:
        raise ValueError(f"no PointInstancer in {source_path}")
    instancer = UsdGeom.PointInstancer(instancer_prim)

    proto_indices = list(instancer.GetProtoIndicesAttr().Get() or [])
    positions = list(instancer.GetPositionsAttr().Get() or [])
    orientations = list(instancer.GetOrientationsAttr().Get() or [])
    scales_attr = instancer.GetScalesAttr().Get()
    scales = list(scales_attr) if scales_attr else None

    primvars = UsdGeom.PrimvarsAPI(instancer_prim)
    bind_joints_pv = primvars.GetPrimvar("unreal:naniteAssembly:bindJoints")
    bind_weights_pv = primvars.GetPrimvar("unreal:naniteAssembly:bindJointWeights")
    element_size = bind_joints_pv.GetElementSize() if bind_joints_pv else 0
    joints = list(bind_joints_pv.Get() or []) if bind_joints_pv else []
    weights = list(bind_weights_pv.Get() or []) if bind_weights_pv else []

    count = len(proto_indices)
    if joints and len(joints) != count * element_size:
        raise ValueError(
            f"{source_path.name}: {len(joints)} bindJoints for {count} instances "
            f"at elementSize {element_size}"
        )

    # Prototype index -> the file its prim references, so the caller can key
    # package paths by something stable.
    proto_files: list[str] = []
    for target in instancer.GetPrototypesRel().GetTargets():
        referenced = ""
        for prim in Usd.PrimRange(stage.GetPrimAtPath(target)):
            refs = prim.GetMetadata("references")
            items = list(getattr(refs, "prependedItems", [])) if refs else []
            if items:
                referenced = Path(str(items[0].assetPath)).name
                break
        proto_files.append(referenced)

    used = {proto_files[i] for i in set(proto_indices)}
    missing = sorted(name for name in used if name not in asset_paths)
    if missing:
        raise ValueError(
            f"{source_path.name}: no package path for prototype file(s) "
            f"{missing}; every prototype the assembly instances must be in "
            "the library"
        )

    if output_path.exists():
        output_path.unlink()
    out = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(out, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(out, 1.0)

    name = root.GetName()
    out_root = UsdGeom.Xform.Define(out, f"/{name}").GetPrim()
    out_root.SetMetadata("kind", "group")
    _apply_api_schemas(out_root, ["NaniteAssemblyRootAPI"])
    # `meshType` is declared `uniform token` by the unreal schema. The third
    # positional argument of CreateAttribute is `custom`, not `variability`, so
    # both have to be spelled out or the attribute comes out `custom token` and
    # drifts from the shape assembly_export writes.
    out_root.CreateAttribute(
        "unreal:naniteAssembly:meshType",
        Sdf.ValueTypeNames.Token,
        custom=False,
        variability=Sdf.VariabilityUniform,
    ).Set(
        stage.GetAttributeAtPath(
            root.GetPath().AppendProperty("unreal:naniteAssembly:meshType")
        ).Get()
        or "skeletalMesh"
    )

    stems = next((c for c in root.GetChildren() if c.GetTypeName() == "SkelRoot"), None)
    if stems is None:
        raise ValueError(f"{source_path.name}: no SkelRoot stems child to carry over")
    out_stems = out.DefinePrim(f"/{name}/{stems.GetName()}", "SkelRoot")
    for ref in stems.GetMetadata("references").prependedItems:
        out_stems.GetReferences().AddReference(ref.assetPath, ref.primPath)

    skeleton_rel = root.GetRelationship("unreal:naniteAssembly:skeleton")
    if skeleton_rel:
        out_root.CreateRelationship(
            "unreal:naniteAssembly:skeleton", custom=True
        ).SetTargets(skeleton_rel.GetTargets())

    out.DefinePrim(f"/{name}/Parts", "Scope")
    for i in range(count):
        part = UsdGeom.Xform.Define(out, f"/{name}/Parts/inst_{i:05d}")
        prim = part.GetPrim()
        _apply_api_schemas(
            prim, ["NaniteAssemblyExternalRefAPI", "NaniteAssemblySkelBindingAPI"]
        )
        prim.CreateAttribute(
            "unreal:naniteAssembly:meshAssetPath",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set(asset_paths[proto_files[proto_indices[i]]])

        quat = orientations[i]
        rotation = Gf.Rotation(
            Gf.Quatd(
                float(quat.real), Gf.Vec3d(*[float(c) for c in quat.imaginary])
            )
        )
        matrix = Gf.Matrix4d().SetRotate(rotation)
        if scales:
            matrix = (
                Gf.Matrix4d().SetScale(Gf.Vec3d(*[float(c) for c in scales[i]]))
                * matrix
            )
        matrix.SetTranslateOnly(Gf.Vec3d(*[float(c) for c in positions[i]]))
        part.AddTransformOp().Set(matrix)

        if not joints:
            continue
        out_primvars = UsdGeom.PrimvarsAPI(prim)
        slice_ = slice(i * element_size, (i + 1) * element_size)
        joints_pv = out_primvars.CreatePrimvar(
            "unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            UsdGeom.Tokens.constant,
        )
        joints_pv.Set(Vt.TokenArray(joints[slice_]))
        joints_pv.SetElementSize(element_size)
        if weights:
            weights_pv = out_primvars.CreatePrimvar(
                "unreal:naniteAssembly:bindJointWeights",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.constant,
            )
            weights_pv.Set(Vt.FloatArray(weights[slice_]))
            weights_pv.SetElementSize(element_size)

    out.SetDefaultPrim(out_root)
    out.GetRootLayer().Save()

    report = {
        "file": str(output_path),
        "file_bytes": output_path.stat().st_size,
        "instances": count,
        "prototypes": len(set(proto_indices)),
        "element_size": element_size,
    }
    logger.info(
        "external-ref assembly: %d instances over %d shared prototypes, "
        "%.3f MB -> %s",
        report["instances"],
        report["prototypes"],
        report["file_bytes"] / 1e6,
        output_path.name,
    )
    return report
