"""Twig prototype silhouette-area measurement (XRFF-273 support).

A per-tree twig-density resolver needs to hit a **visual** crown-fill
target::

    crown_fill ~= instances * prototype_silhouette_area / crown_hull_area

This module supplies ``prototype_silhouette_area``: the projected area a
twig prototype actually covers when viewed, accounting for self-overlap
between its own leaves/needles.

This is deliberately **not** leaf area (see ``io/usd/twig_export.py``'s
``_save_leaf_area_sidecar``, XRFF-274). Leaf area sums every triangle's
area independently, so it double-counts overlapping leaves/needles within
one prototype. A needle spray packs a large leaf area into a small
projected silhouette -- that mismatch is exactly why leaf area proved to be
the wrong quantity for visual crown density (XRFF-318): ``silver_fir`` h15
hit its allometric leaf-area target to three significant figures and a
blind critic still graded the crown "too sparse (severe)".

Definition
----------
"Projected silhouette area" is the **mean, over many uniformly-distributed
viewing orientations, of the projected footprint (2D union) of a
prototype's leaf/needle triangles**.

A twig prototype is instanced at arbitrary orientations across a crown, so
a single axis-aligned projection is not representative -- we need the
*expected* footprint over the distribution of orientations it is actually
seen at. The classical convex-body result (a convex body's mean projected
area equals 1/4 of its surface area) does **not** apply here: a twig
prototype is a highly non-convex assembly of dozens to hundreds of
thousands of separate, mutually-overlapping leaf/needle cards. So the mean
is *measured* by sampling orientations, not derived analytically.

For each sampled orientation:

1. Leaf/needle triangles are projected onto the view plane.
2. The projected triangles are rasterized onto a fine 2D grid.
3. The silhouette area is the count of grid cells covered by **at least
   one** triangle, times cell area -- i.e. the area of the union of the
   projected triangles, not the sum of their individual projected areas.
   This is what makes the measurement not double-count overlap: a needle
   spray where every needle is projected on top of its neighbours still
   only counts each covered pixel once.

Orientations are sampled deterministically via a Fibonacci sphere (evenly
spaced points on the unit sphere), not random, so repeated runs and tests
are reproducible. Axis-aligned (local X/Y/Z) projections are additionally
reported for provenance/comparison, but are NOT used as the primary
silhouette figure -- they are one arbitrary orientation each, not the mean
a prototype experiences once instanced.

Alpha-trimmed mesh boundary == true visual outline (confirmed, not assumed)
-----------------------------------------------------------------------------
Leaf geometry is alpha-textured cards; the exported *mesh* silhouette could
in principle overstate the *visually opaque* silhouette if the alpha mask
still had a soft/partial-transparency border at the mesh edge. It does not:
``config/twigs.toml`` documents that One-leaved ash's alpha mask measured
55.5% of texels below 0.5 alpha, 43.5% above 0.99, under 1% in between --
i.e. effectively binary. Independently re-measuring the alpha textures
here confirms the same pattern holds broadly, not just for that one
species::

    one_leaved_ash_twig_alpha.png: below0.5=55.5% above0.99=43.5% between=1.0%
    pacific_silver_fir_twig_alpha.png: below0.5=76.7% above0.99=21.8% between=1.6%
    BeechAlpha.jpg (european_beech): below0.5=56.8% above0.99=41.5% between=1.7%

Because the mask is binary, the alpha-contour trim (``alpha_trim = 0.9``)
always cuts at essentially the same true edge regardless of exact
threshold, so the trimmed mesh boundary already IS the true visual
outline. No separate opacity-weighted correction is applied here.

Leaf/needle face selection
---------------------------
The exported ``_static.usda`` prototype mesh carries one ``GeomSubset``
per Blender material (e.g. ``<species>_leaf`` / ``<species>_bark``). Faces
are treated as leaf/needle geometry unless their subset name matches one of
the same exclude keywords used by
``io/usd/twig_export.py::_detect_leaf_material_indices``
(``bark``, ``branch``, ``wood``, ``dead``) -- mirroring that convention,
just read from the exported GeomSubsets instead of Blender's material list.
Single-material prototypes (all measured conifers) have no GeomSubsets at
all; in that case every face is leaf/needle geometry, matching
``_detect_leaf_material_indices``'s "no materials -> treat everything as
leaf" fallback.

Instance scale
---------------
All instance scales in exported crowns are exactly 1.0 (verified
separately), so no scale^2 correction is applied anywhere in this module.

Sidecar
-------
``write_silhouette_sidecar`` writes ``<prototype>_silhouette.json`` next to
the existing ``<prototype>_leaf_area.json`` sidecar (XRFF-274), where
``<prototype>`` is the static USD's file stem with ``_static`` stripped --
the same naming convention used throughout the twig pipeline (see
``tools/analyze_usda.py``'s triangle-budget sidecar lookup).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# --- tunables -------------------------------------------------------------

DEFAULT_N_ORIENTATIONS = 48
# 0.05 mm. Convergence-tested against the largest real prototype (Pacific
# silver fir spray, 107,876 needle triangles): mean silhouette area over 16
# orientations was still drifting ~5% between 0.4mm and 0.2mm pixels (needle
# triangles are thin enough that coarse rasterization inflates their footprint),
# but had settled to <1% drift between 0.07mm and 0.05mm. 0.05mm is finer than
# the twig pipeline's own alpha-contour target edge length (boundary_edge_mm =
# 0.25mm in config/twigs.toml), so it resolves the mesh's actual outline detail.
DEFAULT_PX_SIZE_M = 5e-5
# Safety cap on rasterization grid size (per axis) so a pathological/unexpected
# input (huge bounding box) can't blow up memory or runtime; px_size is
# coarsened automatically if the requested resolution would exceed this.
DEFAULT_MAX_GRID_DIM = 6000

_LEAF_EXCLUDE_KEYWORDS = ("bark", "branch", "wood", "dead")


# --- orientation sampling --------------------------------------------------


def fibonacci_sphere_directions(n: int) -> np.ndarray:
    """Return ``n`` unit vectors evenly spaced over the sphere.

    Deterministic (a Fibonacci spiral, not random sampling), so repeated
    calls/runs/tests are reproducible.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    i = np.arange(n, dtype=np.float64)
    phi = np.arccos(1.0 - 2.0 * (i + 0.5) / n)
    golden_angle = np.pi * (1.0 + 5.0**0.5)
    theta = golden_angle * i
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)
    return np.stack([x, y, z], axis=1)


def _orthonormal_basis(view_dir: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return two unit vectors spanning the plane perpendicular to ``view_dir``."""
    view_dir = view_dir / np.linalg.norm(view_dir)
    reference = (
        np.array([0.0, 1.0, 0.0])
        if abs(view_dir[1]) < 0.9
        else np.array([1.0, 0.0, 0.0])
    )
    u = np.cross(reference, view_dir)
    u = u / np.linalg.norm(u)
    w = np.cross(view_dir, u)
    return u, w


# --- rasterization ----------------------------------------------------------


def project_silhouette_area(
    points: np.ndarray,
    triangles: np.ndarray,
    view_dir: np.ndarray,
    px_size_m: float = DEFAULT_PX_SIZE_M,
    max_grid_dim: int = DEFAULT_MAX_GRID_DIM,
) -> float:
    """Project ``triangles`` (index array into ``points``) along ``view_dir``
    and return the union footprint area in m^2.

    The result is the area of pixels covered by AT LEAST ONE projected
    triangle -- overlapping triangles are not double-counted, unlike a sum
    of per-triangle projected areas.
    """
    triangles = np.asarray(triangles)
    if triangles.shape[0] == 0:
        return 0.0

    u, w = _orthonormal_basis(np.asarray(view_dir, dtype=np.float64))
    proj = np.stack([points @ u, points @ w], axis=1)
    tri_pts = proj[triangles]

    mn = proj.min(axis=0)
    mx = proj.max(axis=0)
    extent = np.maximum(mx - mn, 1e-9)

    px = px_size_m
    grid = np.ceil(extent / px).astype(int)
    largest = int(grid.max())
    if largest > max_grid_dim:
        px = px * (largest / max_grid_dim)
        grid = np.ceil(extent / px).astype(int)

    width = max(2, int(grid[0]))
    height = max(2, int(grid[1]))

    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)
    xs = (tri_pts[:, :, 0] - mn[0]) / px
    ys = (mx[1] - tri_pts[:, :, 1]) / px  # flip so +w is "up" in image space
    for i in range(tri_pts.shape[0]):
        draw.polygon(
            [(xs[i, 0], ys[i, 0]), (xs[i, 1], ys[i, 1]), (xs[i, 2], ys[i, 2])],
            fill=1,
        )

    covered_px = int(np.asarray(img, dtype=bool).sum())
    return covered_px * (px * px)


def measure_silhouette(
    points: np.ndarray,
    triangles: np.ndarray,
    *,
    n_orientations: int = DEFAULT_N_ORIENTATIONS,
    px_size_m: float = DEFAULT_PX_SIZE_M,
    max_grid_dim: int = DEFAULT_MAX_GRID_DIM,
) -> dict:
    """Measure mean projected silhouette area over ``n_orientations`` views.

    ``points`` is an (N, 3) array; ``triangles`` an (M, 3) index array into
    ``points`` for the leaf/needle faces only (see
    :func:`load_leaf_geometry`).
    """
    points = np.asarray(points, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int64)

    directions = fibonacci_sphere_directions(n_orientations)
    areas = np.array(
        [
            project_silhouette_area(points, triangles, d, px_size_m, max_grid_dim)
            for d in directions
        ]
    )
    axis_areas = {
        axis: project_silhouette_area(
            points, triangles, np.eye(3)[i], px_size_m, max_grid_dim
        )
        for i, axis in enumerate("xyz")
    }

    return {
        "silhouette_area_m2": float(areas.mean()),
        "silhouette_area_std_m2": float(areas.std()),
        "silhouette_area_min_m2": float(areas.min()),
        "silhouette_area_max_m2": float(areas.max()),
        "n_orientations": int(n_orientations),
        "px_size_m": float(px_size_m),
        "axis_aligned_silhouette_area_m2": {
            k: float(v) for k, v in axis_areas.items()
        },
    }


# --- USD loading -------------------------------------------------------------


def _leaf_face_indices(mesh_prim, n_faces: int) -> np.ndarray:
    """Return indices of leaf/needle faces under ``mesh_prim``.

    Mirrors ``io/usd/twig_export.py::_detect_leaf_material_indices``'s
    "anything not tagged bark/branch/wood/dead is leaf" convention, reading
    it from the exported GeomSubsets (one per material) rather than
    Blender's material index list.
    """
    from pxr import UsdGeom

    subset_prims = [
        c for c in mesh_prim.GetChildren() if c.GetTypeName() == "GeomSubset"
    ]
    if not subset_prims:
        # No materials at all (single-material conifer sprays): everything
        # is leaf/needle geometry.
        return np.arange(n_faces)

    leaf_indices: list[int] = []
    for subset_prim in subset_prims:
        name = subset_prim.GetName().lower()
        if any(kw in name for kw in _LEAF_EXCLUDE_KEYWORDS):
            continue
        idx_attr = UsdGeom.Subset(subset_prim).GetIndicesAttr()
        idx = idx_attr.Get() if idx_attr else None
        if idx:
            leaf_indices.extend(int(i) for i in idx)

    if not leaf_indices:
        # Every subset was excluded (or all empty): fall back to treating
        # the whole mesh as leaf rather than silently returning zero area.
        return np.arange(n_faces)
    return np.array(sorted(set(leaf_indices)), dtype=np.int64)


def load_leaf_geometry(static_usda_path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    """Load ``(points, leaf_triangles, total_face_count)`` from a twig
    ``_static.usda`` prototype.

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

    total_faces = len(face_vertex_counts)
    triangles = face_vertex_indices.reshape(-1, 3)
    leaf_idx = _leaf_face_indices(mesh_prim, total_faces)
    return points, triangles[leaf_idx], total_faces


# --- prototype-level measurement ---------------------------------------------


def prototype_name_from_static_path(static_usda_path: Path) -> str:
    """The prototype's asset name: the static USD's file stem, ``_static``
    stripped -- matches ``<prototype>_leaf_area.json`` (XRFF-274) naming.
    """
    stem = Path(static_usda_path).stem
    if stem.endswith("_static"):
        stem = stem[: -len("_static")]
    return stem


SILHOUETTE_DEFINITION = (
    "Mean projected silhouette area over {n} uniformly-distributed viewing "
    "orientations (deterministic Fibonacci-sphere directions). For each "
    "orientation, leaf/needle triangles are rasterized onto a 2D grid "
    "({px_mm:.3f} mm pixels) and the area is the pixel count covered by AT "
    "LEAST ONE triangle (the union footprint) times pixel area -- "
    "overlapping leaves/needles within one prototype are NOT double-"
    "counted, unlike leaf_area_m2 (XRFF-274) which sums every triangle's "
    "area independently. Convex-body mean-projection theory (mean "
    "projection = 1/4 surface area) does not apply: twig prototypes are "
    "non-convex sprays of many separate, overlapping cards, so the mean is "
    "measured by sampling orientations, not derived analytically. "
    "axis_aligned_silhouette_area_m2 (local X/Y/Z single-view projections) "
    "is reported for provenance only; silhouette_area_m2 (the "
    "orientation-mean) is the quantity to use downstream."
)


def measure_prototype_silhouette(
    static_usda_path: Path,
    *,
    n_orientations: int = DEFAULT_N_ORIENTATIONS,
    px_size_m: float = DEFAULT_PX_SIZE_M,
    max_grid_dim: int = DEFAULT_MAX_GRID_DIM,
    leaf_area_json_path: Path | None = None,
) -> dict:
    """Measure a twig prototype's silhouette area and package it with
    provenance and the leaf-area ratio for the ``<prototype>_silhouette.json``
    sidecar.
    """
    static_usda_path = Path(static_usda_path)
    points, leaf_triangles, total_faces = load_leaf_geometry(static_usda_path)

    result = measure_silhouette(
        points,
        leaf_triangles,
        n_orientations=n_orientations,
        px_size_m=px_size_m,
        max_grid_dim=max_grid_dim,
    )

    prototype_name = prototype_name_from_static_path(static_usda_path)
    result["prototype"] = prototype_name
    result["source_usda"] = str(static_usda_path)
    result["leaf_faces"] = int(leaf_triangles.shape[0])
    result["total_faces"] = int(total_faces)
    result["definition"] = SILHOUETTE_DEFINITION.format(
        n=n_orientations, px_mm=px_size_m * 1000.0
    )

    if leaf_area_json_path is None:
        leaf_area_json_path = (
            static_usda_path.parent / f"{prototype_name}_leaf_area.json"
        )
    leaf_area_m2 = None
    if leaf_area_json_path.exists():
        try:
            leaf_area_data = json.loads(leaf_area_json_path.read_text())
            leaf_area_m2 = leaf_area_data.get("leaf_area_m2")
        except (json.JSONDecodeError, OSError):
            leaf_area_m2 = None

    result["leaf_area_m2"] = leaf_area_m2
    result["silhouette_to_leaf_area_ratio"] = (
        result["silhouette_area_m2"] / leaf_area_m2
        if leaf_area_m2
        else None
    )

    return result


def write_silhouette_sidecar(
    result: dict,
    static_usda_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """Write an already-computed ``measure_prototype_silhouette`` result to
    ``<prototype>_silhouette.json``.
    """
    static_usda_path = Path(static_usda_path)
    prototype_name = result.get("prototype") or prototype_name_from_static_path(
        static_usda_path
    )
    out_dir = Path(output_dir) if output_dir is not None else static_usda_path.parent
    out_path = out_dir / f"{prototype_name}_silhouette.json"
    out_path.write_text(json.dumps(result, indent=2))
    return out_path


def measure_and_write_prototype(static_usda_path: Path, **kwargs) -> tuple[dict, Path]:
    """Measure a prototype and write its sidecar in one call."""
    output_dir = kwargs.pop("output_dir", None)
    result = measure_prototype_silhouette(static_usda_path, **kwargs)
    out_path = write_silhouette_sidecar(result, static_usda_path, output_dir)
    return result, out_path


# --- batch discovery ----------------------------------------------------------


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
        description="Measure twig prototype silhouette area and write "
        "<prototype>_silhouette.json sidecars."
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="Override the twig asset root (default: "
        "<project_root>/data/assets/twigs).",
    )
    parser.add_argument("--n-orientations", type=int, default=DEFAULT_N_ORIENTATIONS)
    parser.add_argument("--px-size-m", type=float, default=DEFAULT_PX_SIZE_M)
    parser.add_argument(
        "--json", type=Path, default=None, help="Also write all records to this file."
    )
    args = parser.parse_args(argv)

    results = run_over_all_twigs(
        args.twigs_dir,
        n_orientations=args.n_orientations,
        px_size_m=args.px_size_m,
    )

    if not results:
        print(f"No *_static.usda prototypes found under {args.twigs_dir}")
        return 1

    header = (
        f"{'prototype':<50} {'leaf_area_m2':>13} {'silhouette_m2':>14} {'ratio':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda r: r["prototype"]):
        leaf = r.get("leaf_area_m2")
        ratio = r.get("silhouette_to_leaf_area_ratio")
        leaf_str = f"{leaf:.5f}" if leaf is not None else "n/a"
        ratio_str = f"{ratio:.3f}" if ratio is not None else "n/a"
        print(
            f"{r['prototype']:<50} {leaf_str:>13} {r['silhouette_area_m2']:>14.5f} "
            f"{ratio_str:>7}"
        )

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2))
        print(f"\nWrote JSON: {args.json}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
