"""Derive a foliage size ladder from a twig .blend that ships only one object.

growpy's twig converter builds one USD variant per mesh object in a `.blend`,
so a twig asset's size ladder is however many objects the artist modelled.
Most assets have several -- `PaperBirchTwig` 18, `EuropeanBeechTwig` 5 -- but
`PacificSilverFirTwig` has exactly one, a single 0.109 m2 spray shared by silver
fir, Norway spruce, Douglas fir and Sitka spruce. That one asset is why those
species need crown densities of 0.0078-0.0169 where the broadleaves sit at
0.114-0.80, and why a compound prototype welded from it is so heavy (XRFF-412).

Rather than commission new art or scale the spray down (leaf area goes as
size^2, so reaching 0.0078 by scale alone means a 3.4 cm twig), this splits the
existing mesh along its own structure. A conifer spray is a handful of
elongated shoot pieces plus a few thousand individual needles, all separate
loose parts. Assigning each needle to its nearest shoot recovers the
sub-sprays the artist modelled, exactly and with no geometry left over.

The emitted objects are added to the source file alongside the original, whose
mesh is never touched -- so the asset the dataset already ships keeps
converting to the same bytes, and the new variants appear beside it.

Usage:
    cd data/assets/twigs/pacific_silver_fir_twig
    growpy-derive-twig-ladder PacificSilverFirTwig.blend
    growpy-derive-twig-ladder <blend> --out other.blend --fine 6 --dry-run

Then convert as usual. See [twigs.boundary_edge_mm_per_twig] in
config/twigs.toml for why a multi-size asset generally needs a per-twig
densification target.
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger("growpy.derive_twig_ladder")

# A loose part at least this long (bounding-box diagonal, metres) is structural
# -- a shoot -- rather than a single leaf or needle. The two populations are
# well separated on the assets measured: PacificSilverFirTwig's needles have a
# median diagonal of 0.033 m and its 99th percentile is 0.042 m, while its
# shoots run 0.073-0.209 m.
DEFAULT_SHOOT_MIN_M = 0.06


def _loose_parts(mesh):
    """Connected components of `mesh`, with extent, centre, faces, area, coords."""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    parent = list(range(len(bm.verts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for edge in bm.edges:
        a, b = find(edge.verts[0].index), find(edge.verts[1].index)
        if a != b:
            parent[a] = b

    coords = defaultdict(list)
    for vert in bm.verts:
        coords[find(vert.index)].append(vert.co.copy())
    faces = defaultdict(list)
    areas = defaultdict(float)
    for face in bm.faces:
        root = find(face.verts[0].index)
        faces[root].append(face.index)
        areas[root] += face.calc_area()
    bm.free()

    parts = []
    for root, co in coords.items():
        xs = [c.x for c in co]
        ys = [c.y for c in co]
        zs = [c.z for c in co]
        ext = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        parts.append(
            {
                "faces": faces[root],
                "area": areas[root],
                "diag": sum(e * e for e in ext) ** 0.5,
                "centre": (
                    sum(xs) / len(xs),
                    sum(ys) / len(ys),
                    sum(zs) / len(zs),
                ),
                # Needed to measure a needle's distance to a shoot's GEOMETRY
                # rather than to its centroid -- see `_sub_sprays`.
                "coords": [(c.x, c.y, c.z) for c in co],
            }
        )
    return parts


def _sub_sprays(parts, shoot_min_m):
    """Group needles onto their nearest shoot. Returns (sub_sprays, n_needles).

    Every face of every part lands in exactly one sub-spray, so the groups
    partition the source mesh.

    "Nearest" is measured to the shoot's own GEOMETRY, not to its centroid. A
    shoot's centroid sits at its middle, so a needle out at the distal tip can
    be closer to a neighbouring shoot's centre than to its own shoot's -- and
    the tip is exactly where a conifer spray's shoots run alongside each other.
    Measured on `PacificSilverFirTwig` before this: the 191 mm shoot behind
    variant `c` kept needles only to 60 mm and rendered 77 mm of bare stick,
    while 213 needles lying within 30 mm of that shoot's own axis had been
    handed to four neighbouring sub-sprays. The art was complete; the rule was
    wrong.
    """
    import numpy as np

    shoots = [p for p in parts if p["diag"] >= shoot_min_m]
    needles = [p for p in parts if p["diag"] < shoot_min_m]
    if not shoots:
        raise ValueError(
            f"no loose part reaches the {shoot_min_m} m shoot threshold; "
            "lower --shoot-min"
        )

    shoots.sort(key=lambda p: -p["diag"])
    groups = [
        {
            "faces": list(s["faces"]),
            # Kept separately: the shoot alone defines the variant's attachment
            # point and growth axis, which the needles around it do not.
            "shoot_faces": list(s["faces"]),
            "area": s["area"],
            "diag": s["diag"],
            "centre": s["centre"],
        }
        for s in shoots
    ]
    # Nearest vertex stands in for nearest point on the surface: a shoot is a
    # dense tube beside needles a few millimetres across, so the two agree well
    # within the spacing that decides the assignment.
    shoot_points = [np.asarray(s["coords"], dtype=float) for s in shoots]
    for needle in needles:
        centre = np.asarray(needle["centre"], dtype=float)
        nearest = min(
            range(len(groups)),
            key=lambda i: float(((shoot_points[i] - centre) ** 2).sum(axis=1).min()),
        )
        groups[nearest]["faces"].extend(needle["faces"])
        groups[nearest]["area"] += needle["area"]
    return groups, len(needles)


def _attachment_frame(verts, shoot_verts):
    """Origin and rotation putting a sub-spray into the source asset's frame.

    A twig asset is authored with its attachment point at the origin and its
    shoot running along +X, the spray spread in Y and flattened in Z --
    `PacificSilverFirTwig` measures (-0.007..0.386, -0.168..0.181,
    -0.019..0.127), nearest vertex 2.3 mm from the origin. A sub-spray cut out
    of that mesh keeps the parent's coordinates, so without this it renders up
    to 20 cm from wherever it is placed and at whatever angle its shoot happened
    to leave the parent axis. Both the welded prototypes and the residual 1:1
    twigs then read as floating foliage.

    Roll is pinned with a full orthonormal basis, not a shortest-arc rotation:
    aligning the shoot axis alone leaves the spray free to spin about it (F16).
    The second axis is the spray's own flattening plane, which is what makes a
    conifer spray look laid-out rather than bristled.
    """
    import numpy as np

    verts = np.asarray(verts, dtype=float)
    shoot = np.asarray(shoot_verts, dtype=float)

    # Proximal end = the shoot vertex closest to the parent asset's own origin,
    # i.e. the end nearest where this shoot met the trunk it grew from.
    proximal = shoot[np.argmin(np.linalg.norm(shoot, axis=1))]
    distal = shoot[np.argmax(np.linalg.norm(shoot - proximal, axis=1))]

    axis = distal - proximal
    length = np.linalg.norm(axis)
    if length < 1e-9:
        return proximal, np.eye(3)
    axis = axis / length

    # Flattening plane: the direction of least variance across the whole
    # sub-spray, needles included.
    centred = verts - verts.mean(axis=0)
    normal = np.linalg.svd(centred, full_matrices=False)[2][2]
    normal = normal - np.dot(normal, axis) * axis
    if np.linalg.norm(normal) < 1e-9:
        # Degenerate (a perfectly straight, needle-less shoot): any
        # perpendicular will do, since there is no spray to orient.
        seed = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(seed, axis)) > 0.9:
            seed = np.array([0.0, 1.0, 0.0])
        normal = seed - np.dot(seed, axis) * axis
    normal = normal / np.linalg.norm(normal)
    if normal[2] < 0:
        normal = -normal  # match the source's +Z-up spray plane

    binormal = np.cross(normal, axis)
    return proximal, np.array([axis, binormal, normal])


def _build_object(source, face_indices, name, shoot_face_indices):
    """New object holding only `face_indices` of `source`, materials preserved.

    The extracted geometry is moved into the source asset's authoring frame --
    see `_attachment_frame`.
    """
    import bmesh
    import bpy

    bm = bmesh.new()
    bm.from_mesh(source.data)
    bm.faces.ensure_lookup_table()
    keep = set(face_indices)
    shoot_verts = [tuple(v.co) for i in shoot_face_indices for v in bm.faces[i].verts]
    bmesh.ops.delete(
        bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES"
    )
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    origin, rotation = _attachment_frame(
        [tuple(v.co) for v in mesh.vertices], shoot_verts
    )
    for vert in mesh.vertices:
        local = (vert.co[0] - origin[0], vert.co[1] - origin[1], vert.co[2] - origin[2])
        vert.co = (
            float(sum(rotation[0][k] * local[k] for k in range(3))),
            float(sum(rotation[1][k] * local[k] for k in range(3))),
            float(sum(rotation[2][k] * local[k] for k in range(3))),
        )

    for material in source.data.materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def plan_ladder(parts, fine, cluster_size, shoot_min_m):
    """Pick the variants to emit. Returns (plan, sub_sprays, n_needles).

    `plan` is a list of (suffix, face_indices, area). The fine tier is spread
    evenly across the area-sorted sub-sprays rather than taken from the top,
    because a conifer spray carries several shoots of near-identical size and
    emitting all of them would be near-duplicate prototypes. One middle-tier
    variant groups the largest sub-spray with its nearest neighbours, which is
    what the next size up actually looks like on the tree.
    """
    subs, n_needles = _sub_sprays(parts, shoot_min_m)
    ordered = sorted(subs, key=lambda s: -s["area"])

    count = min(fine, len(ordered))
    if count > 1:
        picks = [
            ordered[round(i * (len(ordered) - 1) / (count - 1))] for i in range(count)
        ]
    else:
        picks = ordered[:1]

    anchor = ordered[0]
    nearest_first = sorted(
        subs,
        key=lambda s: sum(
            (a - b) ** 2 for a, b in zip(s["centre"], anchor["centre"], strict=True)
        ),
    )[: max(2, cluster_size)]

    letters = "abcdefghijklmnopqrstuvwxyz"
    plan = [
        (letters[i], p["faces"], p["area"], p["shoot_faces"])
        for i, p in enumerate(picks)
    ]
    if len(picks) < len(letters):
        plan.append(
            (
                letters[len(picks)],
                [f for s in nearest_first for f in s["faces"]],
                sum(s["area"] for s in nearest_first),
                # The cluster is oriented on the shoot it was grown around, not
                # on the union: the union's own principal axis is meaningless.
                anchor["shoot_faces"],
            )
        )
    return plan, ordered, n_needles


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Split a single-object twig .blend into a foliage size ladder, "
            "using the mesh's own shoot/needle structure (XRFF-412)."
        )
    )
    parser.add_argument("blend", type=Path, help="twig .blend to read")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write (default: overwrite the source, original object kept)",
    )
    parser.add_argument(
        "--object",
        default=None,
        help="mesh object to split (default: the only one, or the largest)",
    )
    parser.add_argument(
        "--shoot-min",
        type=float,
        default=DEFAULT_SHOOT_MIN_M,
        help=(
            "loose-part diagonal in metres at or above which a part counts as a "
            f"shoot rather than a leaf (default: {DEFAULT_SHOOT_MIN_M})"
        ),
    )
    parser.add_argument(
        "--fine", type=int, default=6, help="fine-tier variants to emit (default: 6)"
    )
    parser.add_argument(
        "--cluster-size",
        type=int,
        default=4,
        help="sub-sprays grouped into the middle-tier variant (default: 4)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report the ladder without writing"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    if not args.blend.exists():
        logger.error("Not found: %s", args.blend)
        return 1

    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(args.blend))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        logger.error("No mesh objects in %s", args.blend)
        return 1
    if args.object:
        source = next((o for o in meshes if o.name == args.object), None)
        if source is None:
            logger.error(
                "No object %r in %s (have: %s)",
                args.object,
                args.blend,
                ", ".join(sorted(o.name for o in meshes)),
            )
            return 1
    else:
        source = max(meshes, key=lambda o: len(o.data.polygons))
        if len(meshes) > 1:
            logger.warning(
                "%s already holds %d mesh objects; splitting the largest (%s). "
                "A ladder is usually only missing when there is exactly one.",
                args.blend.name,
                len(meshes),
                source.name,
            )

    parts = _loose_parts(source.data)
    total_faces = sum(len(p["faces"]) for p in parts)
    total_area = sum(p["area"] for p in parts)
    logger.info(
        "%s: %d loose parts, %d faces, %.5f m2 mesh area",
        source.name,
        len(parts),
        total_faces,
        total_area,
    )

    try:
        plan, subs, n_needles = plan_ladder(
            parts, args.fine, args.cluster_size, args.shoot_min
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    covered = sum(len(s["faces"]) for s in subs)
    logger.info(
        "%d shoots + %d needles -> %d sub-sprays covering %d/%d faces",
        len(subs),
        n_needles,
        len(subs),
        covered,
        total_faces,
    )
    if covered != total_faces:
        # Cannot happen while every part is either a shoot or assigned to one,
        # but a silent partial cover would ship variants with holes in them.
        logger.error(
            "sub-sprays cover %d of %d faces -- refusing to write a partial ladder",
            covered,
            total_faces,
        )
        return 1

    smallest = min(area for _, _, area, _ in plan)
    logger.info("ladder (the source object is kept unchanged alongside these):")
    for suffix, faces, area, _ in plan:
        logger.info(
            "   %s%s  faces=%-7d area=%.5f m2  1/%.1f of the full spray",
            source.name,
            suffix.upper(),
            len(faces),
            area,
            total_area / area,
        )
    logger.info(
        "   %s   faces=%-7d area=%.5f m2  (unchanged)",
        source.name,
        total_faces,
        total_area,
    )
    logger.info("   span: %.1fx in leaf area", total_area / smallest)

    if args.dry_run:
        return 0

    for suffix, faces, _, shoot_faces in plan:
        _build_object(source, faces, f"{source.name}{suffix.upper()}", shoot_faces)

    destination = args.out or args.blend
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))
    logger.info(
        "wrote %s (%d mesh objects)",
        destination,
        len([o for o in bpy.data.objects if o.type == "MESH"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
