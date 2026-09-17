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


def harvested_branch_ids(
    children: Sequence[Sequence[int]], roots: Iterable[int]
) -> set[int]:
    """Union of `subtree_branch_ids()` over every cut point in a cut set."""
    ids: set[int] = set()
    for root in roots:
        ids |= subtree_branch_ids(children, root)
    return ids


class ComplementModel:
    """A read-only view of a Grove model with the harvested parts removed.

    XRFF-362. The base mesh under a compound assembly must be the exact
    complement of the parts placed on it, and `build_cutoff_thickness` does not
    produce that: at cut diameter 0.030 Grove's cutoff leaves 19 branches out of
    11,685 while the cut set is computed on the full-resolution tree, so the two
    meshes describe different trees and every part hangs in mid-air (median
    placement-to-mesh distance 0.739 m).

    Selecting by the inverse face mask instead makes the halves complementary by
    construction, whatever Grove's cutoff happens to mean.

    The view presents the same attribute surface `build_tree_mesh` reads, at the
    same cardinalities -- per-face `face_attribute_*`, per-point
    `point_attribute_*` (with `point_attribute_normals` at three floats per
    point), per-face-corner `uvs` and `uv_islands` -- so it can be passed to
    `build_tree_mesh` in place of the model it wraps.

    Points are compacted, not merely left unreferenced: the full-resolution
    18-cycle beech carries 546,923 points against 424,752 faces, and shipping
    the crown's vertices in a mesh that no longer has crown faces would dominate
    the file.
    """

    def __init__(
        self,
        model: Any,
        part_branch_ids: Iterable[int],
        drop_twig_faces: bool = True,
    ) -> None:
        excluded = set(part_branch_ids)

        # Grove properties rebuild their whole list per access -- hoisting two
        # in-loop reads is what took dataset production from 44 min per 17
        # assemblies to 10 min per 99. Read each exactly once.
        src_faces = model.faces
        src_points = model.points
        src_uvs = model.uvs
        face_branch_ids = model.face_attribute_branch_id

        twig_mask: list[bool] | None = None
        if drop_twig_faces:
            # A compound assembly places real baked parts at these markers, so
            # a surviving marker quad renders as a stray flat quad in the base
            # mesh. Same four arrays `bake_prototypes` masks with.
            long_ = model.face_attribute_twig_long
            short = model.face_attribute_twig_short
            upward = model.face_attribute_twig_upward
            dead = model.face_attribute_twig_dead
            twig_mask = [
                bool(long_[i] or short[i] or upward[i] or dead[i])
                for i in range(len(src_faces))
            ]

        # Destination faces produced per SOURCE face: 0 for a dropped face, 1
        # while the view is untriangulated, and the fan count afterwards. A
        # plain keep/drop mask cannot survive `triangulate()`, because a kept
        # quad then owns two destination faces while still consuming one slot
        # in every source-length `face_attribute_*` array.
        face_repeat: list[int] = []
        faces: list[list[int]] = []
        uvs: list[tuple[float, float]] = []
        point_map: dict[int, int] = {}
        kept_points: list[int] = []

        corner_offset = 0
        for face_index, face in enumerate(src_faces):
            offset = corner_offset
            corner_offset += len(face)

            if face_branch_ids[face_index] in excluded or (
                twig_mask is not None and twig_mask[face_index]
            ):
                face_repeat.append(0)
                continue

            face_repeat.append(1)
            local_face = []
            for index in face:
                local = point_map.get(index)
                if local is None:
                    local = len(kept_points)
                    point_map[index] = local
                    kept_points.append(index)
                local_face.append(local)
            faces.append(local_face)
            for corner in range(len(face)):
                uv = src_uvs[offset + corner]
                uvs.append((float(uv[0]), float(uv[1])))

        self._model = model
        self._face_repeat = face_repeat
        self._kept_points = kept_points
        self._src_face_count = len(src_faces)
        self._src_point_count = len(src_points)
        self._cache: dict[str, Any] = {}

        self.points = [src_points[i] for i in kept_points]
        self.faces = faces
        self.uvs = uvs

    def triangulate(self) -> None:
        """Fan-triangulate this view's own faces, leaving the source untouched.

        `assembly_export` calls `model.triangulate()` before `build_tree_mesh`.
        Forwarding that to the wrapped model would triangulate the very arrays
        this view was sliced from -- and `bake_prototypes` cannot tolerate it
        either, because it indexes Grove's living-twig arrays by position in
        face order and splitting each marker quad into two triangles would
        double-count every twig.
        """
        if all(len(face) == TRIANGLE for face in self.faces):
            return

        faces: list[list[int]] = []
        uvs: list[tuple[float, float]] = []
        repeat: list[int] = []
        destination = 0
        corner_offset = 0
        for count in self._face_repeat:
            if not count:
                repeat.append(0)
                continue
            fanned = 0
            for _ in range(count):
                face = self.faces[destination]
                arity = len(face)
                corner_uvs = self.uvs[corner_offset : corner_offset + arity]
                corner_offset += arity
                destination += 1
                triangles, triangle_uvs = _fan_triangulate(face, corner_uvs)
                faces.extend(list(t) for t in triangles)
                uvs.extend(triangle_uvs)
                fanned += len(triangles)
            repeat.append(fanned)

        self.faces = faces
        self.uvs = uvs
        self._face_repeat = repeat
        self._cache = {}

    @property
    def dropped_faces(self) -> int:
        """Source faces removed, against the source model's face total."""
        return sum(1 for count in self._face_repeat if not count)

    def _filter_face(self, values: Sequence[Any]) -> list[Any]:
        out: list[Any] = []
        for value, count in zip(values, self._face_repeat, strict=False):
            if count == 1:
                out.append(value)
            elif count:
                out.extend([value] * count)
        return out

    def _filter_point(self, values: Sequence[Any]) -> list[Any] | None:
        count = len(values)
        if count == self._src_point_count:
            return [values[i] for i in self._kept_points]
        if count == self._src_point_count * 3:
            # `point_attribute_normals` is a flat xyz stream, not one entry
            # per point (1,640,769 floats for 546,923 points).
            out: list[Any] = []
            for i in self._kept_points:
                out.extend(values[i * 3 : i * 3 + 3])
            return out
        return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._cache:
            return self._cache[name]

        value = getattr(self._model, name)
        filtered: Any = value
        if name.startswith("face_attribute_"):
            filtered = self._filter_face(value)
        elif name.startswith("point_attribute_"):
            filtered = self._filter_point(value) or value
        elif name == "uv_islands" and value:
            filtered = self.uvs

        self._cache[name] = filtered
        return filtered


def _normalise(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in vector))
    if length == 0.0:
        return (1.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _basis_to_quat(
    forward: Sequence[float],
    right: Sequence[float],
    up: Sequence[float],
) -> tuple[float, float, float, float]:
    """Quaternion taking `forward`/`right`/`up` onto +X/+Y/+Z.

    The rotation matrix whose ROWS are the basis vectors maps each onto its
    axis, since row_i . basis_j is the Kronecker delta for an orthonormal set.
    Shepperd's method picks the largest diagonal term so the square root never
    loses precision near a half turn.
    """
    m = (tuple(forward), tuple(right), tuple(up))
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        quat = (
            0.25 * s,
            (m[2][1] - m[1][2]) / s,
            (m[0][2] - m[2][0]) / s,
            (m[1][0] - m[0][1]) / s,
        )
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        quat = (
            (m[2][1] - m[1][2]) / s,
            0.25 * s,
            (m[0][1] + m[1][0]) / s,
            (m[0][2] + m[2][0]) / s,
        )
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        quat = (
            (m[0][2] - m[2][0]) / s,
            (m[0][1] + m[1][0]) / s,
            0.25 * s,
            (m[1][2] + m[2][1]) / s,
        )
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        quat = (
            (m[1][0] - m[0][1]) / s,
            (m[0][2] + m[2][0]) / s,
            (m[1][2] + m[2][1]) / s,
            0.25 * s,
        )
    length = math.sqrt(sum(c * c for c in quat)) or 1.0
    return (quat[0] / length, quat[1] / length, quat[2] / length, quat[3] / length)


def align_to_forward_quat(
    direction: Sequence[float],
    reference_up: Sequence[float] = (0.0, 0.0, 1.0),
) -> tuple[float, float, float, float]:
    """Quaternion (w, x, y, z) rotating `direction` onto +X, roll pinned by up.

    +X because that is the axis `core.twig._quat_forward` rotates: the
    PointInstancer orientation carries a twig's growth direction on its local
    +X, so a baked part has to present its own axis there too.

    **Not** shortest-arc, which was the original implementation. Shortest-arc
    pins one axis and leaves rotation ABOUT that axis free, so a prototype baked
    from one medoid's roll is re-used at every placement with whatever roll the
    minimal rotation happens to produce. Measured on an 18-cycle silver_fir:
    roll against world-up scattered to a median of 28 deg, 35% of parts beyond
    45 deg and 16% beyond 90 deg -- their sprays effectively upside down. A
    conifer reads as a bottlebrush instead of flat, layered sprays; a broadleaf
    hides it, because its foliage is near-isotropic about the branch axis.

    Building a full orthonormal basis against `reference_up` makes roll a
    function of the branch direction alone, so a part is authored and placed in
    the same frame and its foliage keeps a consistent relationship to gravity.
    """
    forward = _normalise(direction)
    if all(c == 0.0 for c in direction):
        return (1.0, 0.0, 0.0, 0.0)

    right = _cross(reference_up, forward)
    if math.sqrt(sum(c * c for c in right)) < 1e-6:
        # Branch parallel to the reference up (a leader, typically): any
        # perpendicular will do, so long as it is chosen deterministically.
        right = _cross((1.0, 0.0, 0.0), forward)
        if math.sqrt(sum(c * c for c in right)) < 1e-6:
            right = _cross((0.0, 1.0, 0.0), forward)
    right = _normalise(right)
    up = _normalise(_cross(forward, right))
    return _basis_to_quat(forward, right, up)


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
    bark_species: str | None = None,
    skeletal: bool = False,
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
            so the part's subsets bind to the species' real leaf materials
            rather than to nothing.
        bark_species: Species whose *tree* bark material the woody faces should
            bind. Without it they inherit the twig prototype's same-named bark,
            which samples the foliage atlas (XRFF-363).
        skeletal: Author the part as a `SkelRoot` with a single-joint skeleton,
            the form a SKELETAL Nanite Assembly requires of its prototypes.
            Handed a static prototype, UE logs "Failed to find Skeletal Mesh
            asset for PointInstancer prototype" and silently builds no assembly
            at all (XRFF-366).
    """
    _ensure_pxr()

    from pxr import Sdf, Usd, UsdGeom, UsdSkel, Vt

    part.validate()

    if part_name is None:
        part_name = output_path.stem.replace("_static", "").replace("_skeletal", "")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(output_path))
    # Matches the stems and twig stages: Grove works in Z-up metres.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    if skeletal:
        root = UsdSkel.Root.Define(stage, f"/{part_name}")
        root.GetPrim().SetTypeName("SkelRoot")
        UsdSkel.BindingAPI.Apply(root.GetPrim())
    else:
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

    if skeletal:
        _add_part_skeleton(stage, part_name, mesh, len(part.points))

    if material_source is not None:
        _copy_materials(stage, part_name, part, material_source, bark_species)
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


def _add_part_skeleton(stage: Any, part_name: str, mesh: Any, num_points: int) -> None:
    """Give a part the single-joint skeleton a skeletal assembly demands.

    Mirrors `twig_export`'s skeletal twig exactly, because that is the shape
    `assembly_export` and the UE importer already accept: one joint named
    `twig_root`, its bind transform rotated -90 degrees about Z so the bone
    points along +X (the axis a part is authored on), and rigid dual-bone
    skinning -- every vertex on joint 0 at full weight with a zero-weight second
    influence.

    Nanite assembly parts are unskinned regardless (*"the vertices of skeletal
    assembly parts are not skinned, so they only animate rigidly in their bind
    pose"*), so this skeleton does not deform anything. It exists so the part
    reaches the assembly as a Part on the skeletal root at all.
    """
    from pxr import Gf, Sdf, UsdSkel, Vt

    skel_path = Sdf.Path(f"/{part_name}").AppendChild(f"{part_name}_skel")
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    transform = Gf.Matrix4d(1.0)
    transform.SetRotateOnly(Gf.Rotation(Gf.Vec3d(0, 0, 1), -90.0))
    transform.SetTranslateOnly(Gf.Vec3d(0.0, 0.0, 0.0))

    skel.CreateJointsAttr(["twig_root"])
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray([transform]))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray([transform]))
    # [-1] marks the root joint as parentless; without it Unreal cannot read
    # the hierarchy.
    skel.GetPrim().CreateAttribute(
        "jointIndices",
        Sdf.ValueTypeNames.IntArray,
        custom=False,
        variability=Sdf.VariabilityUniform,
    ).Set(Vt.IntArray([-1]))

    binding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
    binding.CreateSkeletonRel().SetTargets([skel_path])
    binding.CreateJointIndicesPrimvar(False, 2).Set(Vt.IntArray([0, 0] * num_points))
    binding.CreateJointWeightsPrimvar(False, 2).Set(
        Vt.FloatArray([1.0, 0.0] * num_points)
    )


def _stage_textures(material_source: Path, output_dir: Path) -> int:
    """Copy the twig prototype's `textures/` next to the baked part.

    `Sdf.CopySpec` carries shader `inputs:file` asset paths verbatim, and those
    are relative (`@./textures/...@`), so they resolve against whichever layer
    holds them. Written into a different directory they resolve to nothing and
    the part renders untextured. `assembly_export` stages twig textures the same
    way when it copies a prototype into the instances directory.
    """
    source_dir = material_source.parent / "textures"
    if (
        not source_dir.is_dir()
        or source_dir.resolve() == (output_dir / "textures").resolve()
    ):
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
    stage: Any,
    part_name: str,
    part: PartMesh,
    material_source: Path,
    bark_species: str | None = None,
) -> None:
    """Copy a twig prototype's Materials scope in and bind the subsets to it.

    When `bark_species` is given, the twig's own `<species>_bark` is replaced by
    the tree bark material `tree_export` authors for the stems mesh. The twig's
    bark samples the FOLIAGE atlas, and Grove's woody faces carry Grove's bark
    UVs, so indexing that atlas with them tiles leaves across the wood -- which
    is exactly what the imported part showed (XRFF-363).
    """
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

    # What the twig prototype actually shipped, snapshotted BEFORE the tree bark
    # is authored in. 17 of the 48 static twig prototypes carry no GeomSubsets
    # and so ship a single combined leaf+bark material; the fallback below keys
    # off that count and must not see the material we add ourselves.
    twig_materials = {
        p.GetName(): p
        for p in stage.GetPrimAtPath(target_scope).GetChildren()
        if p.GetTypeName() == "Material"
    }
    available = dict(twig_materials)

    if bark_species:
        from .tree_export import _add_skeletal_materials

        bark_name = f"{bark_species}_bark"
        stage.RemovePrim(target_scope.AppendChild(bark_name))
        _add_skeletal_materials(
            stage,
            stage.GetPrimAtPath(f"/{part_name}/{part_name}_mesh"),
            f"/{part_name}",
            bark_species,
        )
        bark = stage.GetPrimAtPath(target_scope.AppendChild(bark_name))
        if bark and bark.IsValid():
            available[bark_name] = bark
        else:
            logger.warning(
                "compound part %s: tree bark material %r was not authored",
                part_name,
                bark_name,
            )

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
        if target is None and len(twig_materials) == 1:
            # A twig with no subsets ships one combined leaf+bark material; the
            # faces it covers legitimately share it. Keyed on what the TWIG
            # shipped, so authoring the tree bark in does not disarm it.
            target = next(iter(twig_materials.values()))
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
