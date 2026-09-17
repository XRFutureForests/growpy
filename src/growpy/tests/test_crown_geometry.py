"""Tests for growpy.utils.crown_geometry.

All fixtures are synthetic point clouds constructed here (no ``bpy``/Grove
dependency), so these tests run without the licensed Grove add-on.
"""

from __future__ import annotations

import numpy as np
import pytest

from growpy.io.usd.preview import _VIEW_AXES
from growpy.utils.crown_geometry import (
    VIEWS,
    CrownGeometry,
    LAIResult,
    ViewCrownHull,
    _alpha_shape_area_2d,
    _estimate_crown_base_height,
    _hull_area_2d,
    _nn_median_spacing,
    _points_array,
    compute_crown_geometry,
    compute_lai,
    compute_view_hulls,
)


class _FakeSkeleton:
    """Minimal duck type matching what preview.py reads off a Grove skeleton."""

    def __init__(self, points: np.ndarray) -> None:
        self.points = points


def _cylinder_tree(
    trunk_height: float = 2.0,
    crown_height: float = 3.0,
    crown_radius: float = 2.0,
    n_trunk: int = 20,
    n_crown_rings: int = 10,
    n_per_ring: int = 16,
    center_xy: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """A synthetic "tree": a thin vertical trunk topped by a widening crown.

    Trunk: points at (cx, cy, z) for z in [0, trunk_height), radial spread
    ~0 (a pole).
    Crown: rings of points from z=trunk_height to trunk_height+crown_height,
    radius linearly ramping 0 -> crown_radius -- so the crown reads as
    "wide" almost immediately above the trunk, giving a known, unambiguous
    crown_base_height_m == trunk_height.
    """
    cx, cy = center_xy
    trunk_z = np.linspace(0, trunk_height, n_trunk, endpoint=False)
    trunk_pts = np.stack(
        [np.full(n_trunk, cx), np.full(n_trunk, cy), trunk_z], axis=1
    )

    ring_z = np.linspace(trunk_height, trunk_height + crown_height, n_crown_rings)
    angles = np.linspace(0, 2 * np.pi, n_per_ring, endpoint=False)
    crown_pts = []
    for z in ring_z:
        r = crown_radius  # constant full radius for every ring above the trunk
        for a in angles:
            crown_pts.append((cx + r * np.cos(a), cy + r * np.sin(a), z))
    crown_pts = np.array(crown_pts)

    return np.vstack([trunk_pts, crown_pts])


# --- axis convention -----------------------------------------------------


def test_views_match_preview_view_axes():
    """VIEWS/_VIEW_AXES must be the exact same convention preview.py uses,
    since icon_crown_metrics measures crown_fill against icons rendered
    with that convention."""
    assert VIEWS == tuple(_VIEW_AXES.keys())
    assert _VIEW_AXES == {"front": (0, 2), "side": (1, 2), "top": (0, 1)}


def test_compute_view_hulls_uses_correct_axis_pairs():
    points = _cylinder_tree()
    hulls = compute_view_hulls(points)
    for view, (axis_h, axis_v) in _VIEW_AXES.items():
        assert hulls[view].axis_h == axis_h
        assert hulls[view].axis_v == axis_v
        assert hulls[view].view == view


# --- hull area geometry ---------------------------------------------------


def test_hull_area_2d_unit_square():
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    area, degenerate = _hull_area_2d(square)
    assert not degenerate
    assert area == pytest.approx(1.0)


def test_hull_area_2d_interior_points_dont_change_area():
    square = np.array(
        [[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5], [0.2, 0.7]], dtype=float
    )
    area, degenerate = _hull_area_2d(square)
    assert not degenerate
    assert area == pytest.approx(1.0)


def test_hull_area_2d_collinear_is_degenerate():
    line = np.array([[0, 0], [1, 0], [2, 0], [3, 0]], dtype=float)
    area, degenerate = _hull_area_2d(line)
    assert degenerate
    assert area == pytest.approx(0.0)


def test_hull_area_2d_too_few_points_is_degenerate():
    area, degenerate = _hull_area_2d(np.array([[0, 0], [1, 1]], dtype=float))
    assert degenerate
    assert area == 0.0

    area0, degenerate0 = _hull_area_2d(np.empty((0, 2)))
    assert degenerate0
    assert area0 == 0.0


def test_hull_area_translation_invariant():
    """Trap #2 in the XRFF-276 brief: skeleton points may be in
    grove-world coordinates (offset by ~100m per surround radius) while
    twig placements are tree-local. Hull AREA must not care which frame
    it's given, since area is translation-invariant."""
    rng = np.random.default_rng(0)
    pts = rng.uniform(-3, 3, size=(50, 2))
    area_local, _ = _hull_area_2d(pts)
    area_shifted, _ = _hull_area_2d(pts + np.array([200.0, -100.0]))
    assert area_local == pytest.approx(area_shifted)


# --- points extraction / duck typing --------------------------------------


def test_points_array_from_raw_array():
    pts = np.zeros((5, 3))
    out = _points_array(pts)
    assert out.shape == (5, 3)


def test_points_array_from_skeleton_object():
    pts = np.zeros((5, 3))
    skel = _FakeSkeleton(pts)
    out = _points_array(skel)
    assert out.shape == (5, 3)


def test_points_array_rejects_bad_shape():
    with pytest.raises(ValueError):
        _points_array(np.zeros((5, 2)))


# --- crown base / tip heuristic --------------------------------------------


def test_crown_base_height_matches_synthetic_trunk_height():
    trunk_height = 2.0
    points = _cylinder_tree(trunk_height=trunk_height, crown_height=3.0)
    base = _estimate_crown_base_height(points)
    # Binned estimate -- allow one bin's worth of slack.
    z_span = points[:, 2].max() - points[:, 2].min()
    bin_width = z_span / 40
    assert base == pytest.approx(trunk_height, abs=bin_width * 1.5)


def test_crown_base_height_bare_pole_falls_back_to_tip():
    """A perfectly vertical point cloud (no crown spread at all) should
    not report a crown base partway up the pole."""
    z = np.linspace(0, 5, 30)
    points = np.stack([np.zeros(30), np.zeros(30), z], axis=1)
    base = _estimate_crown_base_height(points)
    assert base == pytest.approx(float(z.max()))


def test_crown_base_height_zero_height_tree():
    points = np.array([[0, 0, 1.0], [0.1, 0, 1.0], [0, 0.1, 1.0]])
    base = _estimate_crown_base_height(points)
    assert base == pytest.approx(1.0)


def test_crown_base_persistence_ignores_stray_low_branch():
    """One outlier point with wide radial spread near the ground should
    not by itself drag the crown base down to near zero."""
    trunk_height = 2.0
    points = _cylinder_tree(trunk_height=trunk_height, crown_height=3.0)
    stray = np.array([[5.0, 0.0, 0.1]])  # wide spread at almost ground level
    points_with_stray = np.vstack([points, stray])
    base = _estimate_crown_base_height(points_with_stray)
    assert base > 1.0  # not dragged down near the stray point's height


# --- full compute_crown_geometry -------------------------------------------


def test_compute_crown_geometry_basic_shape():
    points = _cylinder_tree(trunk_height=2.0, crown_height=3.0, crown_radius=2.0)
    geom = compute_crown_geometry(points)

    assert isinstance(geom, CrownGeometry)
    assert set(geom.views.keys()) == set(VIEWS)
    for v in geom.views.values():
        assert isinstance(v, ViewCrownHull)

    assert geom.crown_tip_height_m == pytest.approx(5.0, abs=0.2)
    assert geom.crown_base_height_m == pytest.approx(2.0, abs=0.3)
    assert geom.crown_vertical_extent_m == pytest.approx(
        geom.crown_tip_height_m - geom.crown_base_height_m
    )

    # Top view sees a circle of radius 2 -> hull area should approach
    # pi*r^2 as ring/angle sampling density increases (it's inscribed, so
    # slightly less than pi*r^2 for finite sampling).
    top_area = geom.hull_area_m2("top")
    assert top_area < np.pi * 2.0**2
    assert top_area > np.pi * 2.0**2 * 0.9


def test_compute_crown_geometry_accepts_skeleton_duck_type():
    points = _cylinder_tree()
    skel = _FakeSkeleton(points)
    geom = compute_crown_geometry(skel)
    assert geom.crown_tip_height_m == pytest.approx(points[:, 2].max())


def test_compute_crown_geometry_only_requested_views():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points, views=("top",))
    assert set(geom.views.keys()) == {"top"}


def test_compute_crown_geometry_translation_invariant_frame():
    """Whether points are grove-world (offset ~100m per surround radius)
    or tree-local, hull areas and vertical extent must match -- only
    crown_base/tip absolute heights along Z are frame-sensitive, and Z is
    never offset by the grove-world/tree-local split (only X/Y are)."""
    points = _cylinder_tree()
    shifted = points.copy()
    shifted[:, 0] += 100.0
    shifted[:, 1] += 200.0

    geom_a = compute_crown_geometry(points)
    geom_b = compute_crown_geometry(shifted)

    assert geom_a.crown_base_height_m == pytest.approx(geom_b.crown_base_height_m)
    assert geom_a.crown_tip_height_m == pytest.approx(geom_b.crown_tip_height_m)
    for view in VIEWS:
        assert geom_a.hull_area_m2(view) == pytest.approx(geom_b.hull_area_m2(view))


def test_compute_crown_geometry_empty_points_raises():
    with pytest.raises(ValueError):
        compute_crown_geometry(np.empty((0, 3)))


def test_compute_crown_geometry_hull_area_accessor():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    for view in VIEWS:
        assert geom.hull_area_m2(view) == geom.views[view].hull_area_m2


def test_narrow_conifer_vs_broad_crown_are_distinguishable():
    """XRFF-276 motivation check: a tall, narrow crown and a short, broad
    crown must not collapse to the same geometry."""
    narrow = _cylinder_tree(trunk_height=1.0, crown_height=8.0, crown_radius=1.0)
    broad = _cylinder_tree(trunk_height=1.0, crown_height=2.0, crown_radius=4.0)

    geom_narrow = compute_crown_geometry(narrow)
    geom_broad = compute_crown_geometry(broad)

    assert geom_narrow.crown_vertical_extent_m > geom_broad.crown_vertical_extent_m
    assert geom_narrow.hull_area_m2("top") < geom_broad.hull_area_m2("top")


# --- concave hull (alpha shape) ---------------------------------------------


def _dense_disk(radius: float = 2.0, n: int = 400, seed: int = 0) -> np.ndarray:
    """Uniformly-sampled 2D points filling a disk -- no gaps, so a
    well-chosen alpha shape should recover close to the full disk area."""
    rng = np.random.default_rng(seed)
    r = radius * np.sqrt(rng.uniform(0, 1, n))
    theta = rng.uniform(0, 2 * np.pi, n)
    return np.stack([r * np.cos(theta), r * np.sin(theta)], axis=1)


def test_nn_median_spacing_matches_known_grid():
    # 1x1 grid spacing -> 1st-nearest-neighbour distance is exactly 1.0
    # for every interior/edge point (k explicit here since the module
    # DEFAULT is k=10, not 1 -- see _nn_median_spacing's docstring for
    # why k=1 is the wrong default for this module's actual inputs).
    xs, ys = np.meshgrid(np.arange(5), np.arange(5))
    grid = np.stack([xs.ravel(), ys.ravel()], axis=1).astype(float)
    spacing = _nn_median_spacing(grid, k=1)
    assert spacing == pytest.approx(1.0)


def test_nn_median_spacing_default_k_uses_a_farther_neighbour():
    """The module DEFAULT (k=_DEFAULT_ALPHA_SPACING_K, currently 10) must
    report a LARGER spacing than the literal 1st-nearest-neighbour
    distance on the same non-trivial point cloud -- this is the whole
    point of the k=1 -> k=10 fix (see module docstring 'Convex vs.
    concave hull' section)."""
    xy = _dense_disk(radius=2.0, n=300, seed=2)
    spacing_k1 = _nn_median_spacing(xy, k=1)
    spacing_default = _nn_median_spacing(xy)
    assert spacing_default > spacing_k1


def test_alpha_shape_never_exceeds_convex_hull():
    """Delaunay-triangle filtering only removes area from the convex
    hull's own triangulation -- concave area must never exceed convex."""
    xy = _dense_disk()
    convex_area, _ = _hull_area_2d(xy)
    for mult in (0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 50.0):
        concave_area, _degenerate, _alpha_r = _alpha_shape_area_2d(
            xy, alpha_multiplier=mult
        )
        assert concave_area <= convex_area + 1e-9


def test_alpha_shape_large_multiplier_approaches_convex_hull():
    """A dense, gap-free disk of points: a generous alpha radius should
    keep essentially every Delaunay triangle, converging to the convex
    hull area."""
    xy = _dense_disk()
    convex_area, _ = _hull_area_2d(xy)
    concave_area, degenerate, _alpha_r = _alpha_shape_area_2d(
        xy, alpha_multiplier=50.0
    )
    assert not degenerate
    assert concave_area == pytest.approx(convex_area, rel=0.01)


def test_alpha_shape_tiny_multiplier_degenerates():
    """An alpha radius far smaller than the point spacing rejects every
    Delaunay triangle -- reported honestly as degenerate/zero-area, not
    silently substituted with a bounding-box fallback (unlike the convex
    degenerate case)."""
    xy = _dense_disk()
    concave_area, degenerate, _alpha_r = _alpha_shape_area_2d(
        xy, alpha_multiplier=1e-6
    )
    assert degenerate
    assert concave_area == pytest.approx(0.0)


def test_alpha_shape_excludes_sparse_outlier_shoot():
    """XRFF-276 motivation: a dense crown cluster plus a few sparse,
    far-flung 'leader shoot' points should inflate the CONVEX hull a lot
    but the CONCAVE hull much less, because the shoot's own points are
    spaced far apart relative to the dense cluster's alpha radius."""
    rng = np.random.default_rng(1)
    dense_cluster = rng.uniform(-1.0, 1.0, size=(200, 2))  # dense 2x2 square
    # A handful of sparse points strung far out in one direction -- like a
    # broadleaf leader shoot -- each far from its neighbours relative to
    # the dense cluster's spacing.
    shoot = np.array([[3.0, 0.0], [6.0, 0.5], [9.0, -0.5], [12.0, 0.2]])
    xy = np.vstack([dense_cluster, shoot])

    convex_area, _ = _hull_area_2d(xy)
    concave_area, _degenerate, alpha_r = _alpha_shape_area_2d(xy)

    # The convex hull is dominated by the long thin triangle out to the
    # shoot tip; the concave hull (alpha radius derived from the DENSE
    # cluster's own tight spacing) should reject the huge shoot-spanning
    # triangles and report an area close to just the dense cluster.
    dense_only_area, _ = _hull_area_2d(dense_cluster)
    assert concave_area < convex_area
    # Concave area should track the dense cluster far more closely than
    # the convex (shoot-inflated) hull does.
    assert abs(concave_area - dense_only_area) < abs(convex_area - dense_only_area)


def test_alpha_shape_area_2d_too_few_points_falls_back():
    # Fewer than 4 points -- no interior structure left to make concave,
    # so this falls back to _hull_area_2d's own verdict/area directly.
    area, degenerate, _alpha_r = _alpha_shape_area_2d(
        np.array([[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]])
    )
    assert not degenerate  # 3 non-collinear points -> a valid triangle
    assert area == pytest.approx(0.5)

    area2, degenerate2, _alpha_r2 = _alpha_shape_area_2d(
        np.array([[0.0, 0.0], [1.0, 1.0]])
    )
    assert degenerate2
    assert area2 == pytest.approx(0.0)


def test_view_crown_hull_has_concave_fields():
    points = _cylinder_tree()
    hulls = compute_view_hulls(points)
    for view in VIEWS:
        h = hulls[view]
        assert isinstance(h.concave_hull_area_m2, float)
        assert isinstance(h.alpha_radius_m, float)
        assert isinstance(h.concave_is_degenerate, bool)
        assert h.concave_hull_area_m2 <= h.hull_area_m2 + 1e-9


def test_compute_crown_geometry_concave_area_accessor():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    for view in VIEWS:
        assert geom.concave_hull_area_m2(view) == geom.views[view].concave_hull_area_m2
        assert geom.concave_hull_area_m2(view) <= geom.hull_area_m2(view) + 1e-9


def test_compute_crown_geometry_alpha_multiplier_is_threaded_through():
    points = _cylinder_tree()
    geom_tight = compute_crown_geometry(points, alpha_multiplier=0.5)
    geom_loose = compute_crown_geometry(points, alpha_multiplier=50.0)
    # Looser multiplier can only keep as many or more Delaunay triangles.
    assert geom_loose.concave_hull_area_m2("top") >= geom_tight.concave_hull_area_m2(
        "top"
    ) - 1e-9


# --- LAI (leaf area index) ---------------------------------------------------


def test_compute_lai_basic_concave():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    top_concave_area = geom.concave_hull_area_m2("top")
    assert top_concave_area > 0

    result = compute_lai(
        leaf_area_m2=10.0,
        crown_geometry=geom,
        leaf_area_provisional=True,
        leaf_area_source="unit-test",
    )
    assert isinstance(result, LAIResult)
    assert result.hull_type == "concave"
    assert result.view == "top"
    assert result.leaf_area_provisional is True
    assert result.leaf_area_source == "unit-test"
    assert result.crown_area_m2 == pytest.approx(top_concave_area)
    assert result.lai == pytest.approx(10.0 / top_concave_area)


def test_compute_lai_convex_vs_concave_differ_when_hulls_differ():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    concave_result = compute_lai(
        5.0, geom, leaf_area_provisional=False, hull_type="concave"
    )
    convex_result = compute_lai(
        5.0, geom, leaf_area_provisional=False, hull_type="convex"
    )
    assert convex_result.crown_area_m2 == pytest.approx(geom.hull_area_m2("top"))
    assert concave_result.crown_area_m2 == pytest.approx(
        geom.concave_hull_area_m2("top")
    )
    if geom.concave_hull_area_m2("top") != geom.hull_area_m2("top"):
        assert concave_result.lai != convex_result.lai


def test_compute_lai_invalid_hull_type_raises():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    with pytest.raises(ValueError):
        compute_lai(1.0, geom, leaf_area_provisional=True, hull_type="side")


def test_compute_lai_requires_top_view():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points, views=("front", "side"))
    with pytest.raises(ValueError):
        compute_lai(1.0, geom, leaf_area_provisional=True)


def test_compute_lai_zero_area_returns_nan_not_inf():
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    result = compute_lai(1.0, geom, leaf_area_provisional=True)
    object.__setattr__(result, "crown_area_m2", result.crown_area_m2)  # no-op, frozen
    # Directly exercise the zero-area path via a degenerate single-view geometry.
    zero_area_view = ViewCrownHull(
        view="top",
        axis_h=0,
        axis_v=1,
        hull_area_m2=0.0,
        n_points=1,
        is_degenerate=True,
        concave_hull_area_m2=0.0,
        alpha_radius_m=0.0,
        concave_is_degenerate=True,
    )
    zero_geom = CrownGeometry(
        crown_base_height_m=0.0,
        crown_tip_height_m=1.0,
        crown_vertical_extent_m=1.0,
        views={"top": zero_area_view},
    )
    zero_result = compute_lai(5.0, zero_geom, leaf_area_provisional=True)
    assert np.isnan(zero_result.lai)


def test_compute_lai_requires_explicit_provisional_flag():
    """leaf_area_provisional has no default -- every call site must state
    whether the leaf area it is passing in is trustworthy."""
    points = _cylinder_tree()
    geom = compute_crown_geometry(points)
    with pytest.raises(TypeError):
        compute_lai(1.0, geom)  # type: ignore[call-arg]
