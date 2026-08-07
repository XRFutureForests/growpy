"""Geometric re-derivation of leaf/wood surface area for twig prototypes.

Fixes a bug in the XRFF-274 ``<prototype>_leaf_area.json`` sidecars: those
values are **whole-mesh surface area, wood included**, not leaf area. The
material-name exclusion in
``io/usd/twig_export.py::_detect_leaf_material_indices`` (bark/branch/wood/
dead keyword match) either never fired (all 49 prototypes measured have
``leaf_faces == total_faces``; ``european_oak_foliage_apical`` even lists a
subset literally named ``european_oak_bark`` among its
``leaf_material_indices``) or cannot fire at all, because several
prototypes -- critically every measured conifer -- have **no material
separation whatsoever** (a single ``<species>_leaf`` material covering both
needles and the woody shoot, with no ``GeomSubset``\\ s at all).

Per the project owner's direction, this module does **not** attempt a
better material-name heuristic. It re-derives leaf area from mesh
**geometry and topology**: connected mesh components are classified as
LEAF (flat or curved sheet) or WOOD (3D volume: branch cylinder, acorn,
berry) from three signals --

1. **Closed-ness** -- a component with no open boundary at all is a
   watertight 3D volume (acorn, berry, capped branch), never a leaf.
   Extended by signal 3 to bodies with a small opening in them.
2. **Boundary loop count + boundary-vertex ratio** -- a tube has few
   boundary vertices relative to its total vertex count (most of a
   cylinder's surface is interior); a leaf sheet is mostly boundary.
   Guarded by signal 3, because this ratio also falls with tessellation
   density and would otherwise call a finely meshed flat sheet a tube.
3. **Normal wrap** -- the largest eigenvalue of the area-weighted face
   normal orientation tensor ``sum(a_i * n_i n_i^T) / sum(a_i)``. This
   measures how far the surface's normals spread over the Gauss sphere,
   and is scale-, resolution- and pose-free. A flat sheet gives 1.0
   (all normals identical); a sheet with genuine curvature stays high
   (0.79-0.99 on every measured broadleaf blade); a tube whose normals
   sweep a full circle about its axis converges to 0.5; a sphere to 1/3.

Why not PCA flatness (XRFF-318 recalibration)
---------------------------------------------
The first version of this module ported ``io/usd/twig_geometry.py::
_is_likely_tube_component`` verbatim, including its leading **PCA
flatness** test (``sv[2] / sv[0] >= 0.08`` => 3D volume => wood). That
test validated exactly on needle and compound-leaflet species and failed
badly on broadleaves: whole-mesh wood fractions of 0.70-1.00 against
bark-GeomSubset references of 0.003-0.16. The misclassified components
were whole leaf blades -- broadleaf blades are modelled with real
non-planar curvature (vein bulge, leaf curl), which pushes whole-component
PCA to ratios of 0.08-0.43, indistinguishable from a real volume. The
``0.08`` threshold was calibrated in ``twig_geometry.py`` to separate
branch cylinders from *perfectly flat* leaf cards for decimation
protection -- a different discrimination problem. The PCA flatness test is
therefore **not used here at all**; a curved sheet and a cylinder differ in
where their normals point, not in whether their points fill three
dimensions.

The normal-wrap test is applied **only to components with two or more
boundary loops** (see ``NORMAL_WRAP_RATIO``). Ungated it is unsafe: a
Scots pine needle fascicle is a single-loop component whose needles
radiate about the shoot, so collectively its normals also sweep a full
circle (measured 0.523-0.73) and it is indistinguishable from a tube by
normals alone. Gated on multi-loop topology, which fascicles do not have,
the signal separates with a wide margin -- see ``NORMAL_WRAP_RATIO``.

Validated against real assets: ``pacific_silver_fir_foliage`` (107,876
faces, no material separation, the single largest and most consequential
twig prototype in the project) splits into 2,219 disjoint mesh components
(needles are NOT vertex-welded to the woody rachis) -- so the
component-based approach is geometrically valid on exactly the asset it
most needs to work on, not just on the assets that happen to have
GeomSubsets already. Fir has **zero** components in the normal-wrap test's
gated pool (no component has >= 2 boundary loops *and* boundary-vertex
ratio >= 0.5), so the recalibration is provably inert on it: its wood
fraction is 0.157 for every value of ``NORMAL_WRAP_RATIO``.

Sidecar
-------
``write_leaf_geometry_sidecar`` writes ``<prototype>_leaf_area_geom.json``
next to the existing (uncorrected) ``<prototype>_leaf_area.json`` -- a new
file, not an overwrite, so old and new values remain both available for
audit/comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

# --- classifier thresholds --------------------------------------------------
# These are NOT the thresholds used by io/usd/twig_geometry.py::
# _is_likely_tube_component; that function solves a different problem
# (decimation protection) and must not be changed to match these. Every value
# below was placed inside an observed empty band -- a range containing no
# component of *either* class across all 49 measured prototypes -- rather than
# at an error minimum, so that the classifier does not sit on a cliff edge.

MIN_COMPONENT_VERTS = 8

# Components with >= 2 boundary loops and a boundary-vertex ratio below this
# are open tubes. Inherited unchanged from _is_likely_tube_component. Measured
# error is completely flat over [0.3, 0.8]; this is the value that identifies
# the 14 wood components of pacific_silver_fir_foliage.
LOOP2_BOUNDARY_VERT_RATIO = 0.5

# Components with exactly 1 boundary loop and a boundary-vertex ratio below
# this are tubes with one capped end. Raised from _is_likely_tube_component's
# 0.15: Scots pine's woody stubs sit at 0.18-0.20 and were being missed, while
# every single-loop *leaf* component measured sits at >= 0.70 except a handful
# of sub-0.3 cm^2 fragments. The band [0.25, 0.40) contains no single-loop
# component of either class, so 0.35 splits a genuine gap. Measured error is
# flat over [0.25, 0.40].
LOOP1_BOUNDARY_VERT_RATIO = 0.35

# A normal wrap ratio below 0.5 is geometrically impossible for a sheet OR a
# tube: 0.5 is the limit a developable surface reaches only when it wraps a
# full 360 degrees about one axis, and going below it requires the normals to
# spread in a second direction too -- i.e. double curvature, a dome or closed
# body (a sphere sits at 1/3). Components below this threshold are therefore
# buds, berries and acorns that happen to have a small opening, and are the
# nearly-closed generalisation of the watertight "no boundary => wood" rule.
# Every measured component in [0.45, 0.50) is wood (582 cm^2) bar one 0.18
# cm^2 fragment; the ones this rule adds sit at 0.333-0.437.
CLOSED_NORMAL_WRAP_RATIO = 0.45

# Guard on both boundary-vertex-ratio tube tests: a component is only called a
# tube if its normals also wrap. Boundary-vertex ratio is a proxy for "mostly
# interior surface", but it is really a measure of tessellation density -- a
# finely subdivided FLAT sheet has few boundary vertices too (a 20x20 grid sits
# at 0.19), so the ratio alone would call a densely meshed leaf a tube at any
# threshold, including the original 0.15. Requiring the normals to wrap as well
# removes that dependence on mesh density. Costs nothing on the measured
# assets: in the pool the ratio tests catch, every wood component sits at
# <= 0.622 and there is no component of either class in [0.65, 1.0], so error
# is identical for any guard from 0.65 upward.
TUBE_NORMAL_WRAP_GUARD = 0.80

# Largest eigenvalue of the area-weighted face-normal orientation tensor,
# below which a component's normals are judged to wrap around an axis (tube /
# volume) rather than to face one way (sheet / leaf). Applied ONLY to
# components with >= 2 boundary loops -- see the module docstring for why the
# ungated form is unsafe. Within that gated pool the measured split is:
# wood <= 0.522 (73 cm^2 of beech, oak and pine stems), leaf >= 0.622 (pine
# needle sprays); the band [0.523, 0.617] is empty for both classes. 0.57 is
# its midpoint. Measured error is flat over [0.54, 0.62].
NORMAL_WRAP_RATIO = 0.57

_SUBSET_EXCLUDE_KEYWORDS = ("bark", "branch", "wood", "dead")


# --- mesh topology -----------------------------------------------------------


def triangle_areas(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Per-triangle area (m^2) for a triangulated mesh."""
    if len(triangles) == 0:
        return np.zeros(0, dtype=np.float64)
    v0 = points[triangles[:, 0]]
    v1 = points[triangles[:, 1]]
    v2 = points[triangles[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return 0.5 * np.linalg.norm(cross, axis=1)


def build_edge_face_map(triangles: np.ndarray) -> dict[tuple[int, int], list[int]]:
    """Map each undirected mesh edge (min_vert, max_vert) to the list of
    triangle indices that use it. Length 1 => boundary edge; length 2 =>
    ordinary interior (manifold) edge; length > 2 => non-manifold edge.
    """
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, (a, b, c) in enumerate(triangles):
        a, b, c = int(a), int(b), int(c)
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_faces.setdefault(key, []).append(fi)
    return edge_faces


class _UnionFind:
    """Minimal union-find for boundary-loop counting (small per-component
    vertex sets -- a plain dict beats scipy's per-call overhead here).
    """

    def __init__(self):
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self._parent.setdefault(x, x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self._parent[ry] = rx

    def vertices(self) -> set[int]:
        return set(self._parent.keys())


def _count_boundary_loops(
    boundary_edges: list[tuple[int, int]],
) -> tuple[int, set[int]]:
    """Number of connected boundary loops and the set of boundary vertices,
    for a component's boundary edges. Two boundary edges belong to the same
    loop iff they are connected through shared vertices -- equivalent to
    the bmesh original's "walk linked boundary edges through each vertex".
    """
    uf = _UnionFind()
    for u, v in boundary_edges:
        uf.union(u, v)
    verts = uf.vertices()
    loop_count = len({uf.find(v) for v in verts})
    return loop_count, verts


def normal_wrap_ratio(points: np.ndarray, triangles: np.ndarray) -> float | None:
    """Largest eigenvalue of the area-weighted face-normal orientation
    tensor ``sum(a_i * n_i n_i^T) / sum(a_i)``, for one set of faces.

    The tensor has unit trace (the ``n_i`` are unit vectors), so its
    eigenvalues sum to 1 and the largest is confined to ``[1/3, 1]``. It
    measures how far the surface's normals spread over the Gauss sphere:

    ==========================  =====
    surface                     value
    ==========================  =====
    flat sheet                  1.0
    curved sheet (leaf blade)   0.79-0.99 (measured, all broadleaves)
    tube / cylinder             ~0.5
    sphere                      1/3
    ==========================  =====

    Because ``n_i n_i^T`` is invariant under ``n -> -n``, the result does
    not depend on face winding, and because the weights are triangle
    areas it does not depend on tessellation density. It is also
    invariant to scale and rigid motion, so unlike a size or face-count
    prior it carries no assumption about how big a leaf is.

    Returns ``None`` for a degenerate face set with no positive area.
    """
    triangles = np.asarray(triangles, dtype=np.int64)
    if len(triangles) == 0:
        return None
    v0 = points[triangles[:, 0]]
    v1 = points[triangles[:, 1]]
    v2 = points[triangles[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    norms = np.linalg.norm(cross, axis=1)
    keep = norms > 0
    if not np.any(keep):
        return None
    unit_normals = cross[keep] / norms[keep][:, None]
    weights = 0.5 * norms[keep]  # triangle areas
    tensor = (unit_normals * weights[:, None]).T @ unit_normals / weights.sum()
    try:
        eigenvalues = np.linalg.eigvalsh(tensor)
    except np.linalg.LinAlgError:
        return None
    return float(eigenvalues[-1])


def _pca_flatness_ratio(coords: np.ndarray) -> float | None:
    """``sv[2] / sv[0]`` of the component's centred vertex cloud.

    Reported as a diagnostic only -- it does NOT drive classification.
    See the module docstring for why it was removed from the decision.
    """
    centered = coords - coords.mean(axis=0)
    try:
        sv = np.linalg.svd(centered, compute_uv=False)
    except np.linalg.LinAlgError:
        return None
    if len(sv) < 3 or sv[0] <= 0:
        return None
    return float(sv[2] / sv[0])


def _classify_component(
    comp_vert_ids: np.ndarray,
    points: np.ndarray,
    comp_triangles: np.ndarray,
    boundary_edges: list[tuple[int, int]],
) -> dict:
    """Classify one connected mesh component as leaf or wood.

    See the module docstring for the signal rationale. The caller is
    expected to have already handled the "no boundary edges at all" case
    (closed volume => wood) -- see :func:`classify_twig_mesh`.
    """
    n_verts = int(len(comp_vert_ids))
    detail = {
        "is_wood": False,
        "reason": "leaf_sheet",
        "flatness_ratio": None,
        "normal_wrap_ratio": None,
        "loop_count": None,
        "boundary_vert_ratio": None,
    }

    if n_verts < MIN_COMPONENT_VERTS:
        detail["reason"] = "too_small_default_leaf"
        return detail

    # Diagnostics: recorded for audit, not used for the decision.
    detail["flatness_ratio"] = _pca_flatness_ratio(points[comp_vert_ids])
    wrap = normal_wrap_ratio(points, comp_triangles)
    detail["normal_wrap_ratio"] = wrap

    if not boundary_edges:
        return detail

    loop_count, boundary_verts = _count_boundary_loops(boundary_edges)
    boundary_vert_ratio = len(boundary_verts) / n_verts
    detail["loop_count"] = loop_count
    detail["boundary_vert_ratio"] = boundary_vert_ratio

    if wrap is not None and wrap < CLOSED_NORMAL_WRAP_RATIO:
        # Doubly curved: a bud or berry with a small opening in it.
        detail["is_wood"] = True
        detail["reason"] = "closed_normals_wrap_sphere"
        return detail

    wraps_like_tube = wrap is not None and wrap < TUBE_NORMAL_WRAP_GUARD
    ratio_limit = (
        LOOP2_BOUNDARY_VERT_RATIO if loop_count >= 2 else LOOP1_BOUNDARY_VERT_RATIO
    )

    if loop_count >= 1 and boundary_vert_ratio < ratio_limit and wraps_like_tube:
        # Mostly-interior surface whose normals wrap: an open tube.
        detail["is_wood"] = True
        detail["reason"] = (
            "tube_two_open_ends" if loop_count >= 2 else "tube_one_open_end"
        )
    elif loop_count >= 2 and wrap is not None and wrap < NORMAL_WRAP_RATIO:
        # A branched woody shell: too much of it is boundary for the tube
        # test to fire (every stub end adds a loop and its vertices), but
        # its normals still wrap fully around an axis instead of facing one
        # way like a leaf sheet.
        detail["is_wood"] = True
        detail["reason"] = "normals_wrap_axis"

    return detail


def classify_twig_mesh(points: np.ndarray, triangles: np.ndarray) -> dict:
    """Classify every face of a twig mesh as leaf (0) or wood (1), from
    geometry alone -- no material information used or required.

    Returns a dict with:
      - ``face_class``: int8 array, one entry per triangle (0=leaf, 1=wood)
      - ``n_components``: number of disjoint mesh components found
      - ``components``: list of per-component diagnostic dicts (id, face/
        vert counts, classification, and the signals that drove it)
    """
    triangles = np.asarray(triangles, dtype=np.int64)
    n_faces = len(triangles)
    if n_faces == 0:
        return {
            "face_class": np.zeros(0, dtype=np.int8),
            "n_components": 0,
            "components": [],
        }

    edge_faces = build_edge_face_map(triangles)

    boundary_edge_owner: dict[tuple[int, int], int] = {}
    pair_i: list[int] = []
    pair_j: list[int] = []
    for key, faces in edge_faces.items():
        if len(faces) == 1:
            boundary_edge_owner[key] = faces[0]
        elif len(faces) == 2:
            pair_i.append(faces[0])
            pair_j.append(faces[1])
        else:
            # Non-manifold edge (>2 faces): union every pair so connectivity
            # is still correct; should not occur in well-formed twig meshes.
            for x in range(len(faces)):
                for y in range(x + 1, len(faces)):
                    pair_i.append(faces[x])
                    pair_j.append(faces[y])

    if pair_i:
        rows = np.array(pair_i + pair_j)
        cols = np.array(pair_j + pair_i)
        data = np.ones(len(rows), dtype=np.int8)
        graph = coo_matrix((data, (rows, cols)), shape=(n_faces, n_faces))
        n_components, labels = connected_components(graph, directed=False)
    else:
        labels = np.arange(n_faces)
        n_components = n_faces

    boundary_edges_by_component: dict[int, list[tuple[int, int]]] = {}
    for key, face_idx in boundary_edge_owner.items():
        boundary_edges_by_component.setdefault(int(labels[face_idx]), []).append(key)

    comp_face_lists: dict[int, list[int]] = {}
    for fi in range(n_faces):
        comp_face_lists.setdefault(int(labels[fi]), []).append(fi)

    areas = triangle_areas(points, triangles)
    face_class = np.zeros(n_faces, dtype=np.int8)
    components: list[dict] = []

    for comp_id, face_idx_list in comp_face_lists.items():
        face_idx_arr = np.array(face_idx_list, dtype=np.int64)
        comp_verts = np.unique(triangles[face_idx_arr])
        boundary_edges = boundary_edges_by_component.get(comp_id, [])
        has_boundary = bool(boundary_edges)

        comp_triangles = triangles[face_idx_arr]

        if not has_boundary:
            detail = {
                "is_wood": True,
                "reason": "closed_no_boundary",
                "flatness_ratio": _pca_flatness_ratio(points[comp_verts]),
                "normal_wrap_ratio": normal_wrap_ratio(points, comp_triangles),
                "loop_count": 0,
                "boundary_vert_ratio": 0.0,
            }
        else:
            detail = _classify_component(
                comp_verts, points, comp_triangles, boundary_edges
            )

        is_wood = detail["is_wood"]
        face_class[face_idx_arr] = 1 if is_wood else 0

        components.append(
            {
                "component_id": comp_id,
                "n_faces": int(len(face_idx_arr)),
                "n_verts": int(len(comp_verts)),
                "area_m2": float(areas[face_idx_arr].sum()),
                "has_boundary": has_boundary,
                "classification": "wood" if is_wood else "leaf",
                "reason": detail["reason"],
                "flatness_ratio": detail["flatness_ratio"],
                "normal_wrap_ratio": detail["normal_wrap_ratio"],
                "loop_count": detail["loop_count"],
                "boundary_vert_ratio": detail["boundary_vert_ratio"],
            }
        )

    return {
        "face_class": face_class,
        "n_components": int(n_components),
        "components": components,
    }


def measure_leaf_wood_split(points: np.ndarray, triangles: np.ndarray) -> dict:
    """Classify + sum areas: the leaf/wood split for one mesh."""
    triangles = np.asarray(triangles, dtype=np.int64)
    classification = classify_twig_mesh(points, triangles)
    face_class = classification["face_class"]
    areas = triangle_areas(points, triangles)

    leaf_mask = face_class == 0
    wood_mask = face_class == 1
    leaf_area = float(areas[leaf_mask].sum())
    wood_area = float(areas[wood_mask].sum())
    total_area = leaf_area + wood_area

    components = classification["components"]
    leaf_components = [c for c in components if c["classification"] == "leaf"]
    wood_components = [c for c in components if c["classification"] == "wood"]

    def _area_stats(comps: list[dict]) -> dict | None:
        if not comps:
            return None
        vals = np.array([c["area_m2"] for c in comps], dtype=np.float64)
        return {
            "count": len(comps),
            "total_m2": float(vals.sum()),
            "min_m2": float(vals.min()),
            "max_m2": float(vals.max()),
            "mean_m2": float(vals.mean()),
        }

    return {
        "leaf_area_m2": leaf_area,
        "wood_area_m2": wood_area,
        "wood_fraction": (wood_area / total_area) if total_area > 0 else 0.0,
        "leaf_faces": int(leaf_mask.sum()),
        "wood_faces": int(wood_mask.sum()),
        "total_faces": int(len(triangles)),
        "n_components": classification["n_components"],
        "n_leaf_components": len(leaf_components),
        "n_wood_components": len(wood_components),
        "leaf_component_stats": _area_stats(leaf_components),
        "wood_component_stats": _area_stats(wood_components),
        "wood_components": sorted(
            wood_components, key=lambda c: c["area_m2"], reverse=True
        ),
    }


# --- USD loading ---------------------------------------------------------------


def load_full_twig_mesh(
    static_usda_path: Path,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Load ``(points, triangles, subsets)`` from a twig ``_static.usda``
    prototype. Unlike ``twig_silhouette.py``'s ``load_leaf_geometry``, this
    returns the FULL mesh (leaf and wood faces both) -- classification here
    is geometric, not material-driven, so no faces are pre-filtered.

    ``subsets`` maps each GeomSubset name to its (sorted) face-index array,
    for cross-checking the geometric wood split against any existing
    material-based bark/branch/wood/dead subset.

    Requires ``growpy.utils.pxr_init.ensure_pxr_with_unreal_schema()`` to
    have been called first (a bare ``from pxr import Usd`` can fail with a
    DLL error outside it -- see ``tools/analyze_usda.py``).
    """
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(static_usda_path))
    if stage is None:
        raise ValueError(f"Could not open USD stage: {static_usda_path}")

    mesh_prim = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "Mesh":
            mesh_prim = prim
            break
    if mesh_prim is None:
        raise ValueError(f"No Mesh prim found in {static_usda_path}")

    mesh = UsdGeom.Mesh(mesh_prim)
    points = np.array(mesh.GetPointsAttr().Get() or [], dtype=np.float64)
    face_vertex_counts = list(mesh.GetFaceVertexCountsAttr().Get() or [])
    face_vertex_indices = np.array(
        mesh.GetFaceVertexIndicesAttr().Get() or [], dtype=np.int64
    )

    if any(c != 3 for c in face_vertex_counts):
        raise ValueError(
            f"{static_usda_path} has non-triangular faces; twig export is "
            "expected to triangulate all faces (see io/usd/twig_export.py)."
        )

    triangles = face_vertex_indices.reshape(-1, 3)

    subsets: dict[str, np.ndarray] = {}
    for child in mesh_prim.GetChildren():
        if child.GetTypeName() != "GeomSubset":
            continue
        idx_attr = UsdGeom.Subset(child).GetIndicesAttr()
        idx = idx_attr.Get() if idx_attr else None
        subsets[child.GetName()] = (
            np.array(sorted(int(i) for i in idx), dtype=np.int64)
            if idx
            else np.array([], dtype=np.int64)
        )

    return points, triangles, subsets


def _subset_area(
    keyword: str,
    subsets: dict[str, np.ndarray],
    areas: np.ndarray,
) -> float | None:
    """Sum area of all GeomSubsets whose name contains ``keyword``
    (case-insensitive); ``None`` if no subset matches."""
    matching = [idx for name, idx in subsets.items() if keyword in name.lower()]
    if not matching:
        return None
    all_idx = np.unique(np.concatenate(matching))
    if len(all_idx) == 0:
        return 0.0
    return float(areas[all_idx].sum())


# --- prototype-level measurement -----------------------------------------------


def prototype_name_from_static_path(static_usda_path: Path) -> str:
    """The prototype's asset name: the static USD's file stem, ``_static``
    stripped -- matches ``<prototype>_leaf_area.json`` (XRFF-274) naming.
    """
    stem = Path(static_usda_path).stem
    if stem.endswith("_static"):
        stem = stem[: -len("_static")]
    return stem


LEAF_GEOMETRY_DEFINITION = (
    "Leaf-only and wood-only surface area re-derived from mesh GEOMETRY "
    "and TOPOLOGY, not material tags (fixes XRFF-274: leaf_area_m2 "
    "sidecars are whole-mesh area, wood included -- material-name "
    "exclusion either never fired or, for single-material conifer sprays, "
    "cannot fire at all). Faces are grouped into connected mesh components "
    "via shared interior edges; each component is classified WOOD if (a) "
    "it has no open boundary (closed 3D volume: branch cylinder, acorn, "
    "berry), or (a2) its normal wrap ratio is below "
    f"{CLOSED_NORMAL_WRAP_RATIO}, which requires double curvature and so "
    "means a nearly-closed body (a bud or berry with an opening), or (b) "
    "its boundary-vertex ratio is below "
    f"{LOOP2_BOUNDARY_VERT_RATIO} (>= 2 boundary loops) or "
    f"{LOOP1_BOUNDARY_VERT_RATIO} (exactly 1 loop) AND its normal wrap "
    "ratio -- the largest eigenvalue of the area-weighted face-normal "
    f"orientation tensor -- is below {TUBE_NORMAL_WRAP_GUARD} (open tube), "
    "or (c) it has >= 2 boundary loops and a normal wrap ratio below "
    f"{NORMAL_WRAP_RATIO} (branched woody shell whose normals sweep around "
    "an axis rather than facing one way). Components with fewer than "
    f"{MIN_COMPONENT_VERTS} vertices default to leaf (too small to test "
    "reliably). Every other component is LEAF. NOTE: unlike the first "
    "version of this module, PCA flatness (sv[2]/sv[0]) is NOT used -- "
    "broadleaf blades are modelled with real curvature and cannot be told "
    "from 3D volumes that way; it is still reported per component as a "
    "diagnostic. wood_fraction = wood_area_m2 / (leaf_area_m2 + "
    "wood_area_m2)."
)


def measure_prototype_leaf_geometry(
    static_usda_path: Path,
    *,
    old_leaf_area_json_path: Path | None = None,
) -> dict:
    """Measure a twig prototype's geometric leaf/wood split and package it
    with provenance, the old (XRFF-274) leaf_area_m2 for comparison, and a
    material-subset cross-check where available, for the
    ``<prototype>_leaf_area_geom.json`` sidecar.
    """
    static_usda_path = Path(static_usda_path)
    points, triangles, subsets = load_full_twig_mesh(static_usda_path)
    areas = triangle_areas(points, triangles)
    total_mesh_area = float(areas.sum())

    split = measure_leaf_wood_split(points, triangles)

    prototype_name = prototype_name_from_static_path(static_usda_path)

    if old_leaf_area_json_path is None:
        old_leaf_area_json_path = (
            static_usda_path.parent / f"{prototype_name}_leaf_area.json"
        )
    old_leaf_area_m2 = None
    old_leaf_area_json_path = Path(old_leaf_area_json_path)
    if old_leaf_area_json_path.exists():
        try:
            old_data = json.loads(old_leaf_area_json_path.read_text())
            old_leaf_area_m2 = old_data.get("leaf_area_m2")
        except (json.JSONDecodeError, OSError):
            old_leaf_area_m2 = None

    bark_subset_area = _subset_area("bark", subsets, areas)
    bark_subset_fraction = (
        bark_subset_area / total_mesh_area
        if bark_subset_area is not None and total_mesh_area > 0
        else None
    )

    result = {
        "prototype": prototype_name,
        "source_usda": str(static_usda_path),
        "old_leaf_area_m2": old_leaf_area_m2,
        "leaf_area_m2": split["leaf_area_m2"],
        "wood_area_m2": split["wood_area_m2"],
        "wood_fraction": split["wood_fraction"],
        "leaf_faces": split["leaf_faces"],
        "wood_faces": split["wood_faces"],
        "total_faces": split["total_faces"],
        "n_components": split["n_components"],
        "n_leaf_components": split["n_leaf_components"],
        "n_wood_components": split["n_wood_components"],
        "leaf_component_stats": split["leaf_component_stats"],
        "wood_component_stats": split["wood_component_stats"],
        "wood_components": split["wood_components"],
        "material_subset_names": sorted(subsets.keys()),
        "bark_subset_area_m2": bark_subset_area,
        "bark_subset_fraction": bark_subset_fraction,
        "classifier_thresholds": {
            "min_component_verts": MIN_COMPONENT_VERTS,
            "loop2_boundary_vert_ratio": LOOP2_BOUNDARY_VERT_RATIO,
            "loop1_boundary_vert_ratio": LOOP1_BOUNDARY_VERT_RATIO,
            "normal_wrap_ratio": NORMAL_WRAP_RATIO,
            "closed_normal_wrap_ratio": CLOSED_NORMAL_WRAP_RATIO,
            "tube_normal_wrap_guard": TUBE_NORMAL_WRAP_GUARD,
        },
        "definition": LEAF_GEOMETRY_DEFINITION,
    }
    return result


def write_leaf_geometry_sidecar(
    result: dict,
    static_usda_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """Write an already-computed ``measure_prototype_leaf_geometry`` result
    to ``<prototype>_leaf_area_geom.json`` (NOT the original
    ``<prototype>_leaf_area.json`` -- that sidecar is left untouched).
    """
    static_usda_path = Path(static_usda_path)
    prototype_name = result.get("prototype") or prototype_name_from_static_path(
        static_usda_path
    )
    out_dir = Path(output_dir) if output_dir is not None else static_usda_path.parent
    out_path = out_dir / f"{prototype_name}_leaf_area_geom.json"
    out_path.write_text(json.dumps(result, indent=2))
    return out_path


def measure_and_write_prototype(static_usda_path: Path, **kwargs) -> tuple[dict, Path]:
    """Measure a prototype and write its sidecar in one call."""
    output_dir = kwargs.pop("output_dir", None)
    result = measure_prototype_leaf_geometry(static_usda_path, **kwargs)
    out_path = write_leaf_geometry_sidecar(result, static_usda_path, output_dir)
    return result, out_path


# --- batch discovery -------------------------------------------------------------


def _default_twigs_root() -> Path:
    from growpy.config.paths import get_project_root

    return get_project_root() / "data" / "assets" / "twigs"


def discover_static_prototypes(twigs_root: Path | None = None) -> list[Path]:
    """Find every ``*_static.usda`` twig prototype under ``twigs_root``."""
    root = Path(twigs_root) if twigs_root is not None else _default_twigs_root()
    return sorted(root.rglob("*_static.usda"))


def run_over_all_twigs(twigs_root: Path | None = None, **kwargs) -> list[dict]:
    """Measure and write sidecars for every twig prototype under
    ``twigs_root`` (default: ``<project_root>/data/assets/twigs``).
    """
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()

    results = []
    for static_path in discover_static_prototypes(twigs_root):
        result, _ = measure_and_write_prototype(static_path, **kwargs)
        results.append(result)
    return results


# --- CLI -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-derive twig prototype leaf/wood area from geometry "
        "and write <prototype>_leaf_area_geom.json sidecars."
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="Override the twig asset root (default: "
        "<project_root>/data/assets/twigs).",
    )
    parser.add_argument(
        "--json", type=Path, default=None, help="Also write all records to this file."
    )
    args = parser.parse_args(argv)

    results = run_over_all_twigs(args.twigs_dir)

    if not results:
        print(f"No *_static.usda prototypes found under {args.twigs_dir}")
        return 1

    header = (
        f"{'prototype':<45} {'old_m2':>9} {'new_leaf_m2':>12} "
        f"{'wood_m2':>9} {'wood_frac':>9} {'bark_frac':>9}"
    )
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda r: r["prototype"]):
        old = r.get("old_leaf_area_m2")
        old_str = f"{old:.5f}" if old is not None else "n/a"
        bark_frac = r.get("bark_subset_fraction")
        bark_str = f"{bark_frac:.3f}" if bark_frac is not None else "n/a"
        print(
            f"{r['prototype']:<45} {old_str:>9} {r['leaf_area_m2']:>12.5f} "
            f"{r['wood_area_m2']:>9.5f} {r['wood_fraction']:>9.3f} {bark_str:>9}"
        )

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2))
        print(f"\nWrote JSON: {args.json}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
