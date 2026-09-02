"""Bake a Grove subtree plus its leaves into one welded USD prototype (XRFF-357).

MegaPlants does not instance single twigs. Its foliage parts are branch
complexes -- `CH_Branch_Up_A`, `Leaf_Twig_03` -- carrying several generations of
woody structure *and* their leaves, and every shipped preset caps
`compoundMaxBranchGeneration` at 2-3 with roughly 1000 instances per tree.
growpy places Grove twigs 1:1, which is 74,886 instances on a 25-cycle beech.

Two Nanite Assembly constraints shape what a compound part may be:

* *"You cannot create assemblies of other assemblies. The system currently
  supports a single layer of instancing."* -- so a part is ONE welded mesh.
  Bake, never nest.
* *"the vertices of skeletal assembly parts are not skinned, so they only
  animate rigidly in their bind pose."* -- so a part is rigid under wind, and
  that, not triangle count, is what limits how large one may be.

Local frame
-----------
`assembly_export` authors no xformOp anywhere: prototype Xforms are pure
identity containers, so a part's pivot and orientation are whatever its own
USD root prim already is. The PointInstancer orientation is the Grove twig
quaternion, and `core.twig._quat_forward` shows that quaternion rotates **+X**
onto the growth direction. A baked part therefore has to be authored the same
way a twig asset is:

* base (the cut point) at the origin,
* the cut branch's own axis along **+X**.

Measured on `european_beech_foliage_a_static.usda`, which is exactly that:
89.4% of its points sit at x >= 0 with the origin inside the bounding box.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# `utils.leaf_geometry.load_full_twig_mesh` refuses a twig USD that is not
# fully triangulated, and Nanite is happiest with triangles, so everything
# written here is fan-triangulated on the way in.
TRIANGLE = 3


@dataclass
class PartMesh:
    """One welded mesh destined for a single Nanite Assembly Part.

    UVs are face-varying -- one per face-corner, the same convention
    `tree_export.build_tree_mesh` writes for the stems mesh -- so `uvs` has
    exactly ``3 * len(faces)`` entries once triangulated.
    """

    points: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)
    uvs: list[tuple[float, float]] = field(default_factory=list)
    face_materials: list[int] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Raise if the invariants a USD consumer relies on are broken."""
        if len(self.uvs) != len(self.faces) * TRIANGLE:
            raise ValueError(
                f"face-varying UV count {len(self.uvs)} does not match "
                f"{len(self.faces)} triangles ({len(self.faces) * TRIANGLE} corners)"
            )
        if len(self.face_materials) != len(self.faces):
            raise ValueError(
                f"{len(self.face_materials)} material ids for {len(self.faces)} faces"
            )
        num_points = len(self.points)
        for face in self.faces:
            for index in face:
                if not 0 <= index < num_points:
                    raise ValueError(
                        f"face index {index} out of range for {num_points} points"
                    )
        for material in self.face_materials:
            if not 0 <= material < len(self.materials):
                raise ValueError(
                    f"material id {material} out of range for {len(self.materials)}"
                )

    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Axis-aligned bounds, or two zero vectors when the mesh is empty."""
        if not self.points:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        lo = tuple(min(p[axis] for p in self.points) for axis in range(3))
        hi = tuple(max(p[axis] for p in self.points) for axis in range(3))
        return lo, hi  # type: ignore[return-value]


def _ensure_pxr() -> None:
    """Expose bpy's bundled USD before importing pxr.

    The twig conversion pipeline runs inside the standalone ``bpy`` module, and
    once bpy is imported its bundled USD wins the DLL load race -- a bare
    ``from pxr import ...`` then fails with a native entry-point error. Every
    other USD module here (`assembly_export`, `tree_export`) calls this first.
    """
    from ...utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()


def _fan_triangulate(
    face: Sequence[int], corner_uvs: Sequence[tuple[float, float]]
) -> tuple[list[tuple[int, int, int]], list[tuple[float, float]]]:
    """Split one polygon into a triangle fan, carrying its face-varying UVs.

    Grove emits a mix of quads and triangles -- 334,200 quads against 90,552
    triangles on an 18-cycle beech -- so this cannot assume either.
    """
    triangles: list[tuple[int, int, int]] = []
    uvs: list[tuple[float, float]] = []
    for corner in range(1, len(face) - 1):
        triangles.append((face[0], face[corner], face[corner + 1]))
        uvs.append(corner_uvs[0])
        uvs.append(corner_uvs[corner])
        uvs.append(corner_uvs[corner + 1])
    return triangles, uvs


def subtree_branch_ids(children: Sequence[Sequence[int]], root: int) -> set[int]:
    """Grove `face_attribute_branch_id` values for every branch under `root`.

    `model.face_attribute_branch_id == walker_index + 1`, where walker_index is
    the position in the list `flatten_branches()` returns. Verified two ways on
    an 18-cycle beech: geometrically on 400 sampled branches (400/400) and
    topologically against `face_attribute_branch_id_parent` (11,685 matched, 0
    mismatched). So selecting a subtree's faces is a single set membership test
    and needs neither vertex voting nor spatial matching.

    Do NOT substitute `TwigPlacement.branch_id` here: that carries a
    `branch_id_offset` from `bones_info[0][7]` converting forest-global ids to
    per-tree local ones (`core/twig.py:406-411`).
    """
    ids: set[int] = set()
    stack = [root]
    while stack:
        branch = stack.pop()
        ids.add(branch + 1)
        stack.extend(children[branch])
    return ids


def extract_subtree_mesh(
    faces: Sequence[Sequence[int]],
    points: Sequence[Any],
    uvs: Sequence[Sequence[float]],
    face_branch_ids: Sequence[int],
    branch_ids: Iterable[int],
    twig_face_mask: Sequence[bool] | None = None,
    material: str = "bark",
) -> PartMesh:
    """Cut the woody geometry of one subtree out of a built Grove model.

    Every sequence here must already be hoisted out of the Grove model:
    `.faces`, `.points` and `.uvs` are properties that rebuild the whole list on
    each access, which is what took dataset production from 44 min per 17
    assemblies to 10 min per 99.

    Args:
        faces: `model.faces` -- point index lists, mixed triangles and quads.
        points: `model.points` -- Grove Vectors, read via .x/.y/.z.
        uvs: `model.uvs` -- one (u, v) per FACE-CORNER, not per face and not
            indexed, so it has to be sliced by a cumulative corner offset.
            Slicing it by face index instead silently scrambles texturing.
        face_branch_ids: `model.face_attribute_branch_id`.
        branch_ids: The subtree's branch ids, from `subtree_branch_ids()`.
        twig_face_mask: Per-face "this is one of Grove's twig marker faces".
            Those faces are dropped: the part bakes real twig assets at exactly
            those placements, so keeping the markers buries a flat quad inside
            every leaf cluster. Pass None to keep them.
        material: Material name assigned to the woody faces.

    Returns:
        A triangulated `PartMesh` still in tree-local coordinates.
    """
    wanted = set(branch_ids)
    part = PartMesh(materials=[material])
    remap: dict[int, int] = {}

    corner_offset = 0
    for face_index, face in enumerate(faces):
        arity = len(face)
        offset = corner_offset
        corner_offset += arity

        if face_branch_ids[face_index] not in wanted:
            continue
        if twig_face_mask is not None and twig_face_mask[face_index]:
            continue
        if arity < TRIANGLE:
            continue

        local_face = []
        for index in face:
            local = remap.get(index)
            if local is None:
                local = len(part.points)
                remap[index] = local
                point = points[index]
                part.points.append((point.x, point.y, point.z))
            local_face.append(local)

        corner_uvs = [
            (float(uvs[offset + c][0]), float(uvs[offset + c][1])) for c in range(arity)
        ]
        triangles, triangle_uvs = _fan_triangulate(local_face, corner_uvs)
        part.faces.extend(triangles)
        part.uvs.extend(triangle_uvs)
        part.face_materials.extend([0] * len(triangles))

    return part


def _normalise(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in vector))
    if length == 0.0:
        return (1.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def align_to_forward_quat(
    direction: Sequence[float],
) -> tuple[float, float, float, float]:
    """Shortest-arc quaternion (w, x, y, z) rotating `direction` onto +X.

    +X because that is the axis `core.twig._quat_forward` rotates: the
    PointInstancer orientation carries a twig's growth direction on its local
    +X, so a baked part has to present its own axis there too.
    """
    dx, dy, dz = _normalise(direction)
    dot = dx  # dot((dx, dy, dz), (1, 0, 0))

    if dot > 1.0 - 1e-9:
        return (1.0, 0.0, 0.0, 0.0)
    if dot < -1.0 + 1e-9:
        # Antiparallel: any axis perpendicular to X gives a half turn.
        return (0.0, 0.0, 0.0, 1.0)

    # cross(direction, +X) = (dy*0 - dz*0, dz*1 - dx*0, dx*0 - dy*1)
    cross = (0.0, dz, -dy)
    w = 1.0 + dot
    length = math.sqrt(w * w + sum(c * c for c in cross))
    return (w / length, cross[0] / length, cross[1] / length, cross[2] / length)


def _rotate(
    quat: Sequence[float], point: Sequence[float]
) -> tuple[float, float, float]:
    """Rotate a point by a (w, x, y, z) quaternion."""
    w, x, y, z = quat
    px, py, pz = point
    # t = 2 * cross(q_vec, p)
    tx = 2.0 * (y * pz - z * py)
    ty = 2.0 * (z * px - x * pz)
    tz = 2.0 * (x * py - y * px)
    return (
        px + w * tx + (y * tz - z * ty),
        py + w * ty + (z * tx - x * tz),
        pz + w * tz + (x * ty - y * tx),
    )


def quat_multiply(
    a: Sequence[float], b: Sequence[float]
) -> tuple[float, float, float, float]:
    """Hamilton product of two (w, x, y, z) quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def normalise_part_frame(
    part: PartMesh,
    base_pos: Sequence[float],
    base_dir: Sequence[float],
) -> tuple[float, float, float, float]:
    """Move a part into its own frame: base at origin, own axis on +X.

    Mutates `part.points` in place and returns the quaternion applied, which
    is what a placement has to undo to put the part back where it was cut.
    """
    quat = align_to_forward_quat(base_dir)
    ox, oy, oz = base_pos[0], base_pos[1], base_pos[2]
    part.points = [
        _rotate(quat, (p[0] - ox, p[1] - oy, p[2] - oz)) for p in part.points
    ]
    return quat


def placement_quat_for_direction(
    direction: Sequence[float],
) -> tuple[float, float, float, float]:
    """PointInstancer orientation that puts a normalised part back on `direction`.

    `normalise_part_frame` rotates the cut branch's axis onto +X to author the
    prototype; placing it is the inverse, which for a unit quaternion is its
    conjugate. The result goes straight into the instancer's orientations array
    -- `assembly_export` authors those as `Gf.Quath(q[0], q[1], q[2], q[3])`,
    w-first, and applies no xformOp of its own.
    """
    w, x, y, z = align_to_forward_quat(direction)
    return (w, -x, -y, -z)


def merge_mesh(
    target: PartMesh,
    source: PartMesh,
    translation: Sequence[float] = (0.0, 0.0, 0.0),
    rotation: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
    scale: float = 1.0,
) -> None:
    """Weld `source` into `target` under a rigid transform.

    This is the "single layer of instancing" constraint made concrete: leaves
    cannot be a nested assembly, so the twig asset's triangles are baked into
    the part at each placement transform.
    """
    offset = len(target.points)
    material_remap = {}
    for local_id, name in enumerate(source.materials):
        if name not in target.materials:
            target.materials.append(name)
        material_remap[local_id] = target.materials.index(name)

    for point in source.points:
        scaled = (point[0] * scale, point[1] * scale, point[2] * scale)
        rotated = _rotate(rotation, scaled)
        target.points.append(
            (
                rotated[0] + translation[0],
                rotated[1] + translation[1],
                rotated[2] + translation[2],
            )
        )

    target.faces.extend(
        (a + offset, b + offset, c + offset) for a, b, c in source.faces
    )
    target.uvs.extend(source.uvs)
    target.face_materials.extend(material_remap[m] for m in source.face_materials)


def load_prototype_mesh(usd_path: Path) -> PartMesh:
    """Read a twig prototype USD back as a `PartMesh`, materials included.

    Reads the STATIC twin: it is the one carrying per-material GeomSubsets and
    a Materials scope, where the skeletal twin has a single material and none.
    """
    _ensure_pxr()

    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        raise FileNotFoundError(f"cannot open twig prototype: {usd_path}")

    mesh_prim = next(
        (p for p in stage.Traverse() if p.GetTypeName() == "Mesh"),
        None,
    )
    if mesh_prim is None:
        raise ValueError(f"no Mesh prim in {usd_path}")

    mesh = UsdGeom.Mesh(mesh_prim)
    raw_points = mesh.GetPointsAttr().Get() or []
    counts = list(mesh.GetFaceVertexCountsAttr().Get() or [])
    indices = list(mesh.GetFaceVertexIndicesAttr().Get() or [])

    part = PartMesh(points=[(p[0], p[1], p[2]) for p in raw_points])

    primvar = UsdGeom.PrimvarsAPI(mesh_prim).GetPrimvar("st")
    flat_uvs = list(primvar.Get() or []) if primvar else []
    if primvar and primvar.IsIndexed():
        uv_indices = list(primvar.GetIndices() or [])
        flat_uvs = [flat_uvs[i] for i in uv_indices]

    # Face id -> material, from the GeomSubsets the static twin carries.
    face_material = [0] * len(counts)
    subsets = [c for c in mesh_prim.GetChildren() if c.GetTypeName() == "GeomSubset"]
    if subsets:
        for subset_prim in subsets:
            name = subset_prim.GetName()
            part.materials.append(name)
            material_id = len(part.materials) - 1
            subset_indices = UsdGeom.Subset(subset_prim).GetIndicesAttr().Get() or []
            for face_index in subset_indices:
                if 0 <= face_index < len(face_material):
                    face_material[face_index] = material_id
    if not part.materials:
        part.materials.append(usd_path.stem.replace("_static", ""))

    cursor = 0
    for face_index, arity in enumerate(counts):
        face = indices[cursor : cursor + arity]
        corner_uvs = [
            (float(flat_uvs[cursor + c][0]), float(flat_uvs[cursor + c][1]))
            if cursor + c < len(flat_uvs)
            else (0.0, 0.0)
            for c in range(arity)
        ]
        cursor += arity
        if arity < TRIANGLE:
            continue
        triangles, triangle_uvs = _fan_triangulate(face, corner_uvs)
        part.faces.extend(triangles)
        part.uvs.extend(triangle_uvs)
        part.face_materials.extend([face_material[face_index]] * len(triangles))

    return part


def write_compound_part_usd(
    part: PartMesh,
    output_path: Path,
    part_name: str | None = None,
    material_source: Path | None = None,
) -> Path:
    """Write one welded part as a standalone prototype USD.

    The shape is dictated by `assembly_export`, which derives its reference
    target from the FILENAME -- `stem.replace("_skeletal", "").replace("_static",
    "")` -- and then references `/{that name}` inside the file. Renaming the file
    without renaming the root prim yields an unresolved reference that opens
    without error and renders nothing.

    Args:
        part: The welded mesh, already in its own frame.
        output_path: Destination `.usda`. A `_static` suffix is conventional.
        part_name: Root prim name. Defaults to the stem minus `_static`/`_skeletal`.
        material_source: Twig prototype USD whose `Materials` scope is copied in,
            so the part's subsets bind to the species' real leaf and bark
            materials rather than to nothing.
    """
    _ensure_pxr()

    from pxr import Sdf, Usd, UsdGeom, Vt

    part.validate()

    if part_name is None:
        part_name = output_path.stem.replace("_static", "").replace("_skeletal", "")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(output_path))
    # Matches the stems and twig stages: Grove works in Z-up metres.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root = UsdGeom.Xform.Define(stage, f"/{part_name}")
    stage.SetDefaultPrim(root.GetPrim())

    mesh = UsdGeom.Mesh.Define(stage, f"/{part_name}/{part_name}_mesh")
    mesh.CreatePointsAttr(Vt.Vec3fArray([tuple(p) for p in part.points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([TRIANGLE] * len(part.faces)))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray([index for face in part.faces for index in face])
    )
    lo, hi = part.bounds()
    mesh.CreateExtentAttr(Vt.Vec3fArray([tuple(lo), tuple(hi)]))

    # Both of these are declared explicitly by all 48 shipped static twig
    # prototypes, and a compound part occupies the same prototype slot. USD's
    # fallbacks are the opposite of what foliage needs: catmullClark would treat
    # a baked crown as a subdivision surface, and single-sided makes every leaf
    # invisible from behind.
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr(True)

    primvars = UsdGeom.PrimvarsAPI(mesh)
    uv_primvar = primvars.CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying
    )
    uv_primvar.Set(Vt.Vec2fArray([tuple(uv) for uv in part.uvs]))

    # One GeomSubset per material, mirroring the static twig prototypes.
    if len(part.materials) > 1:
        for material_id, name in enumerate(part.materials):
            face_indices = [
                i for i, m in enumerate(part.face_materials) if m == material_id
            ]
            if not face_indices:
                continue
            subset = UsdGeom.Subset.Define(
                stage, f"/{part_name}/{part_name}_mesh/{name}"
            )
            subset.CreateElementTypeAttr(UsdGeom.Tokens.face)
            subset.CreateFamilyNameAttr("materialBind")
            subset.CreateIndicesAttr(Vt.IntArray(face_indices))

    if material_source is not None:
        _copy_materials(stage, part_name, part, material_source)
        _stage_textures(material_source, output_path.parent)

    stage.GetRootLayer().Save()
    logger.info(
        "compound part %s: %d points, %d triangles, %d materials -> %s",
        part_name,
        len(part.points),
        len(part.faces),
        len(part.materials),
        output_path.name,
    )
    return output_path


def _stage_textures(material_source: Path, output_dir: Path) -> int:
    """Copy the twig prototype's `textures/` next to the baked part.

    `Sdf.CopySpec` carries shader `inputs:file` asset paths verbatim, and those
    are relative (`@./textures/...@`), so they resolve against whichever layer
    holds them. Written into a different directory they resolve to nothing and
    the part renders untextured. `assembly_export` stages twig textures the same
    way when it copies a prototype into the instances directory.
    """
    source_dir = material_source.parent / "textures"
    if not source_dir.is_dir() or source_dir.resolve() == (
        output_dir / "textures"
    ).resolve():
        return 0

    import shutil

    target_dir = output_dir / "textures"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for texture in source_dir.iterdir():
        if not texture.is_file():
            continue
        target = target_dir / texture.name
        if target.exists() and target.stat().st_size == texture.stat().st_size:
            continue
        shutil.copy2(texture, target)
        copied += 1
    if copied:
        logger.info("staged %d textures into %s", copied, target_dir)
    return copied



def _copy_materials(
    stage: Any, part_name: str, part: PartMesh, material_source: Path
) -> None:
    """Copy a twig prototype's Materials scope in and bind the subsets to it."""
    _ensure_pxr()

    from pxr import Sdf, Usd, UsdShade

    source_stage = Usd.Stage.Open(str(material_source))
    if source_stage is None:
        logger.warning("cannot open material source %s", material_source)
        return

    source_scope = next(
        (
            p
            for p in source_stage.Traverse()
            if p.GetName() == "Materials" and p.GetTypeName() == "Scope"
        ),
        None,
    )
    if source_scope is None:
        logger.warning("no Materials scope in %s", material_source)
        return

    target_scope = Sdf.Path(f"/{part_name}/Materials")
    Sdf.CreatePrimInLayer(stage.GetRootLayer(), target_scope)
    copied = Sdf.CopySpec(
        source_stage.GetRootLayer(),
        source_scope.GetPath(),
        stage.GetRootLayer(),
        target_scope,
    )
    if not copied:
        logger.warning("failed to copy Materials from %s", material_source)
        return

    available = {
        p.GetName(): p
        for p in stage.GetPrimAtPath(target_scope).GetChildren()
        if p.GetTypeName() == "Material"
    }
    if not available:
        return

    def _bind(prim_path: str, name: str) -> None:
        """Bind one prim to the material of that name, or say why it could not.

        Deliberately no silent fallback to "whatever material came first": 17 of
        the 48 shipped static twig prototypes carry no GeomSubsets at all, so the
        copied scope holds a single combined material and a lookup for
        `<species>_bark` misses. Binding the woody faces to the leaf material
        would look plausible and be wrong.
        """
        prim = stage.GetPrimAtPath(prim_path)
        if not (prim and prim.IsValid()):
            return
        target = available.get(name)
        if target is None and len(available) == 1:
            # A twig with no subsets ships one combined leaf+bark material; the
            # woody faces legitimately share it.
            target = next(iter(available.values()))
            logger.info(
                "compound part %s: no material named %r in %s, binding the "
                "prototype's single combined material instead",
                part_name,
                name,
                material_source.name,
            )
        if target is None:
            logger.warning(
                "compound part %s: no material named %r in %s (available: %s); "
                "leaving it unbound rather than binding the wrong one",
                part_name,
                name,
                material_source.name,
                sorted(available),
            )
            return
        UsdShade.MaterialBindingAPI.Apply(prim)
        UsdShade.MaterialBindingAPI(prim).Bind(UsdShade.Material(target))

    if len(part.materials) < 2:
        # No GeomSubsets are written for a single-material part -- a bare woody
        # part with no leaves welded in -- so the binding goes on the mesh.
        _bind(
            f"/{part_name}/{part_name}_mesh",
            part.materials[0] if part.materials else "",
        )
        return

    for name in part.materials:
        _bind(f"/{part_name}/{part_name}_mesh/{name}", name)
