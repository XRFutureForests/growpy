"""Tests for growpy.utils.leaf_geometry.

Pure-geometry tests (no pxr) build synthetic point/triangle arrays for the
canonical shapes the classifier has to separate: a flat sheet (leaf), a
*curved* sheet (leaf -- the XRFF-318 broadleaf-blade case that the original
PCA-flatness classifier got wrong), a closed cylinder (wood), an open tube
(wood), a sphere (wood), and meshes mixing them. USD-loading / sidecar
tests build tiny synthetic ``.usda`` stages with pxr directly (mirroring
test_twig_silhouette.py's ``pxr_usd`` fixture pattern), so nothing here
depends on the licensed twig assets under data/assets/twigs/.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from growpy.utils.leaf_geometry import (
    CLOSED_NORMAL_WRAP_RATIO,
    LOOP1_BOUNDARY_VERT_RATIO,
    LOOP2_BOUNDARY_VERT_RATIO,
    MIN_COMPONENT_VERTS,
    NORMAL_WRAP_RATIO,
    TUBE_NORMAL_WRAP_GUARD,
    build_edge_face_map,
    classify_twig_mesh,
    discover_static_prototypes,
    load_full_twig_mesh,
    measure_and_write_prototype,
    measure_leaf_wood_split,
    measure_prototype_leaf_geometry,
    normal_wrap_ratio,
    prototype_name_from_static_path,
    run_over_all_twigs,
    triangle_areas,
    write_leaf_geometry_sidecar,
)

# --- synthetic mesh builders --------------------------------------------------


def _grid_plane(nx=6, ny=6, spacing=1.0, origin=(0.0, 0.0, 0.0)):
    """Flat leaf-like plane: nx*ny grid of vertices in the XY plane,
    triangulated into (nx-1)*(ny-1)*2 triangles. Area == (nx-1)*(ny-1)*spacing^2.
    """
    ox, oy, oz = origin
    pts = [
        (ox + i * spacing, oy + j * spacing, oz) for j in range(ny) for i in range(nx)
    ]
    points = np.array(pts, dtype=np.float64)
    tris = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            b = j * nx + i + 1
            c = (j + 1) * nx + i + 1
            d = (j + 1) * nx + i
            tris.append([a, b, c])
            tris.append([a, c, d])
    return points, np.array(tris, dtype=np.int64)


def _curved_plane(nx=12, ny=12, spacing=0.01, bend=7.0, curl=0.0, origin=(0, 0, 0)):
    """Leaf-blade-like sheet with GENUINE non-planar curvature.

    A grid bent into a shallow parabolic arc across x (``bend``, the vein
    bulge) and optionally across y (``curl``, the leaf curl). Topologically
    identical to :func:`_grid_plane` -- one boundary loop, mostly boundary
    vertices -- but its vertex cloud fills three dimensions, so whole-
    component PCA flatness (``sv[2]/sv[0]``) climbs well past the 0.08
    threshold the classifier originally used to mean "3D volume => wood".
    This is the real broadleaf failure mode from XRFF-318.
    """
    ox, oy, oz = origin
    cx = (nx - 1) * spacing / 2.0
    cy = (ny - 1) * spacing / 2.0
    pts = []
    for j in range(ny):
        for i in range(nx):
            x = i * spacing
            y = j * spacing
            z = bend * (x - cx) ** 2 + curl * (y - cy) ** 2
            pts.append((ox + x, oy + y, oz + z))
    points = np.array(pts, dtype=np.float64)
    tris = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            b = j * nx + i + 1
            c = (j + 1) * nx + i + 1
            d = (j + 1) * nx + i
            tris.append([a, b, c])
            tris.append([a, c, d])
    return points, np.array(tris, dtype=np.int64)


def _closed_cylinder(n_seg=12, radius=1.0, height=2.0, origin=(0.0, 0.0, 0.0)):
    """Watertight capped cylinder (no boundary edges at all)."""
    ox, oy, oz = origin
    pts = [(ox, oy, oz)]  # bottom center: 0
    bottom_ring = list(range(1, n_seg + 1))
    for i in range(n_seg):
        ang = 2 * np.pi * i / n_seg
        pts.append((ox + radius * np.cos(ang), oy + radius * np.sin(ang), oz))
    top_ring = list(range(n_seg + 1, 2 * n_seg + 1))
    for i in range(n_seg):
        ang = 2 * np.pi * i / n_seg
        pts.append((ox + radius * np.cos(ang), oy + radius * np.sin(ang), oz + height))
    top_center = 2 * n_seg + 1
    pts.append((ox, oy, oz + height))
    points = np.array(pts, dtype=np.float64)

    tris = []
    for i in range(n_seg):
        i2 = (i + 1) % n_seg
        b_i, b_i2 = bottom_ring[i], bottom_ring[i2]
        t_i, t_i2 = top_ring[i], top_ring[i2]
        tris.append([b_i, b_i2, t_i2])
        tris.append([b_i, t_i2, t_i])
        tris.append([0, b_i2, b_i])  # bottom cap
        tris.append([top_center, t_i, t_i2])  # top cap
    return points, np.array(tris, dtype=np.int64)


def _open_tube(n_seg=12, radius=1.0, height=2.0, n_rings=5, origin=(0.0, 0.0, 0.0)):
    """Uncapped tube with intermediate rings: only the first and last ring
    circles are boundary loops (2 loops), everything between is interior --
    exercises the boundary-loop-count signal specifically.
    """
    ox, oy, oz = origin
    pts = []
    ring_start = []
    for r in range(n_rings):
        ring_start.append(len(pts))
        z = oz + height * r / (n_rings - 1)
        for i in range(n_seg):
            ang = 2 * np.pi * i / n_seg
            pts.append((ox + radius * np.cos(ang), oy + radius * np.sin(ang), z))
    points = np.array(pts, dtype=np.float64)

    tris = []
    for r in range(n_rings - 1):
        for i in range(n_seg):
            i2 = (i + 1) % n_seg
            a = ring_start[r] + i
            b = ring_start[r] + i2
            c = ring_start[r + 1] + i2
            d = ring_start[r + 1] + i
            tris.append([a, b, c])
            tris.append([a, c, d])
    return points, np.array(tris, dtype=np.int64)


def _uv_sphere(n_lat=6, n_lon=12, radius=1.0, origin=(0.0, 0.0, 0.0)):
    """Watertight closed UV sphere (no boundary edges)."""
    ox, oy, oz = origin
    pts = [(ox, oy, oz + radius)]  # north pole: 0
    lat_ring_start = []
    for la in range(1, n_lat):
        theta = np.pi * la / n_lat
        z = oz + radius * np.cos(theta)
        r = radius * np.sin(theta)
        lat_ring_start.append(len(pts))
        for lo in range(n_lon):
            phi = 2 * np.pi * lo / n_lon
            pts.append((ox + r * np.cos(phi), oy + r * np.sin(phi), z))
    south_idx = len(pts)
    pts.append((ox, oy, oz - radius))
    points = np.array(pts, dtype=np.float64)

    tris = []
    first_ring = lat_ring_start[0]
    for lo in range(n_lon):
        lo2 = (lo + 1) % n_lon
        tris.append([0, first_ring + lo, first_ring + lo2])
    for k in range(len(lat_ring_start) - 1):
        r0, r1 = lat_ring_start[k], lat_ring_start[k + 1]
        for lo in range(n_lon):
            lo2 = (lo + 1) % n_lon
            a, b, c, d = r0 + lo, r0 + lo2, r1 + lo2, r1 + lo
            tris.append([a, b, c])
            tris.append([a, c, d])
    last_ring = lat_ring_start[-1]
    for lo in range(n_lon):
        lo2 = (lo + 1) % n_lon
        tris.append([south_idx, last_ring + lo2, last_ring + lo])
    return points, np.array(tris, dtype=np.int64)


def _concat(*meshes):
    """Concatenate (points, triangles) pairs into one mesh, offsetting vertex
    indices so each source's triangles stay valid. Returns
    (points, triangles, [triangle_count_per_source])."""
    all_points = []
    all_tris = []
    offset = 0
    counts = []
    for pts, tris in meshes:
        all_points.append(pts)
        all_tris.append(tris + offset)
        offset += len(pts)
        counts.append(len(tris))
    return np.vstack(all_points), np.vstack(all_tris), counts


# --- basic geometry helpers ---------------------------------------------------


class TestTriangleAreas:
    def test_unit_right_triangle(self):
        points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        triangles = np.array([[0, 1, 2]])
        areas = triangle_areas(points, triangles)
        assert areas == pytest.approx([0.5])

    def test_empty(self):
        areas = triangle_areas(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
        assert len(areas) == 0


class TestBuildEdgeFaceMap:
    def test_square_two_triangles(self):
        # Two triangles sharing the diagonal: 4 boundary edges + 1 shared.
        triangles = np.array([[0, 1, 2], [0, 2, 3]])
        edge_faces = build_edge_face_map(triangles)
        counts = sorted(len(v) for v in edge_faces.values())
        assert counts == [1, 1, 1, 1, 2]


# --- the five required synthetic-mesh scenarios --------------------------------


class TestClassifyFlatPlane:
    def test_all_faces_classified_leaf(self):
        points, triangles = _grid_plane(nx=6, ny=6)
        result = classify_twig_mesh(points, triangles)
        assert np.all(result["face_class"] == 0)
        assert result["n_components"] == 1
        assert result["components"][0]["classification"] == "leaf"

    def test_leaf_area_matches_analytic_area(self):
        points, triangles = _grid_plane(nx=6, ny=6, spacing=1.0)
        split = measure_leaf_wood_split(points, triangles)
        assert split["leaf_area_m2"] == pytest.approx(25.0)  # 5x5 m grid
        assert split["wood_area_m2"] == pytest.approx(0.0)
        assert split["wood_fraction"] == pytest.approx(0.0)


class TestClassifyClosedCylinder:
    def test_all_faces_classified_wood(self):
        points, triangles = _closed_cylinder(n_seg=12, radius=1.0, height=2.0)
        result = classify_twig_mesh(points, triangles)
        assert np.all(result["face_class"] == 1)
        assert result["n_components"] == 1
        comp = result["components"][0]
        assert comp["classification"] == "wood"
        assert comp["has_boundary"] is False
        assert comp["reason"] == "closed_no_boundary"

    def test_wood_area_is_full_mesh_area(self):
        points, triangles = _closed_cylinder(n_seg=12, radius=1.0, height=2.0)
        split = measure_leaf_wood_split(points, triangles)
        total = float(triangle_areas(points, triangles).sum())
        assert split["wood_area_m2"] == pytest.approx(total)
        assert split["leaf_area_m2"] == pytest.approx(0.0)
        assert split["wood_fraction"] == pytest.approx(1.0)


class TestClassifyOpenTube:
    def test_all_faces_classified_wood(self):
        # radius >> height=2.0 here also has full 3D extent, so PCA alone
        # already flags it wood; classification correctness is what matters.
        points, triangles = _open_tube(n_seg=12, radius=1.0, height=2.0, n_rings=5)
        result = classify_twig_mesh(points, triangles)
        assert np.all(result["face_class"] == 1)
        assert result["n_components"] == 1
        comp = result["components"][0]
        assert comp["classification"] == "wood"
        assert comp["has_boundary"] is True

    def test_wood_via_boundary_loop_signal_on_a_nearly_flat_band(self):
        # height << radius: the tube is a short washer band whose vertex
        # cloud is nearly planar, so no point-cloud measure can decide --
        # classification must come from the two-open-ends boundary-loop
        # signal. Isolates that code path specifically.
        points, triangles = _open_tube(
            n_seg=12, radius=1.0, height=0.05, n_rings=5
        )
        result = classify_twig_mesh(points, triangles)
        comp = result["components"][0]
        assert comp["flatness_ratio"] < 0.08  # point cloud looks flat
        assert comp["classification"] == "wood"
        assert comp["has_boundary"] is True
        assert comp["loop_count"] == 2
        assert comp["boundary_vert_ratio"] == pytest.approx(2 / 5)
        assert comp["reason"] == "tube_two_open_ends"


class TestNormalWrapRatio:
    """The signal itself, on shapes with known Gauss-map spread."""

    def test_flat_sheet_is_one(self):
        assert normal_wrap_ratio(*_grid_plane(nx=6, ny=6)) == pytest.approx(1.0)

    def test_cylinder_wall_is_one_half(self):
        # Normals sweep a full circle in the plane normal to the axis, so
        # the orientation tensor is diag(1/2, 1/2, 0).
        points, triangles = _open_tube(n_seg=64, radius=1.0, height=2.0, n_rings=3)
        assert normal_wrap_ratio(points, triangles) == pytest.approx(0.5, abs=0.02)

    def test_sphere_is_one_third(self):
        # Normals cover the whole sphere uniformly => isotropic tensor.
        points, triangles = _uv_sphere(n_lat=24, n_lon=48, radius=1.0)
        assert normal_wrap_ratio(points, triangles) == pytest.approx(1 / 3, abs=0.02)

    def test_curved_sheet_stays_high(self):
        # A leaf blade's normals stay in a narrow cone, unlike a tube's.
        points, triangles = _curved_plane(bend=7.0, curl=3.0)
        assert normal_wrap_ratio(points, triangles) > NORMAL_WRAP_RATIO

    def test_invariant_to_face_winding(self):
        # n n^T is invariant under n -> -n, so flipping triangles must not
        # change the result. Guards the classifier against winding bugs.
        points, triangles = _curved_plane(bend=7.0)
        flipped = triangles[:, ::-1].copy()
        assert normal_wrap_ratio(points, flipped) == pytest.approx(
            normal_wrap_ratio(points, triangles)
        )

    def test_invariant_to_uniform_scale(self):
        # Scale-free: a 5 cm leaf and a 50 cm leaf score identically. This
        # is why the classifier needs no size prior.
        points, triangles = _curved_plane(bend=7.0, curl=3.0)
        assert normal_wrap_ratio(points * 10.0, triangles) == pytest.approx(
            normal_wrap_ratio(points, triangles)
        )

    def test_degenerate_faces_return_none(self):
        points = np.zeros((3, 3))
        assert normal_wrap_ratio(points, np.array([[0, 1, 2]])) is None
        assert normal_wrap_ratio(points, np.zeros((0, 3), dtype=np.int64)) is None


class TestClassifyCurvedSheet:
    """XRFF-318 regression: a broadleaf blade is curved, not flat, and must
    still classify as leaf. The original classifier called these wood via
    PCA flatness (``sv[2]/sv[0] >= 0.08``), producing wood fractions of
    0.70-1.00 on beech/birch/linden/maple against bark references of
    0.003-0.19.
    """

    # Curvatures spanning the wrap range measured on real broadleaf blades
    # (0.79-0.99 across beech, oak, birch, linden, maple and cherry).
    @pytest.mark.parametrize(
        "bend,curl",
        [
            (3.0, 0.0),  # mild vein bulge     -> wrap ~0.97
            (5.0, 2.0),  # bulge + light curl  -> wrap ~0.90
            (7.0, 0.0),  # pronounced bulge    -> wrap ~0.85
            (7.0, 3.0),  # bulge + curl        -> wrap ~0.82
        ],
    )
    def test_curved_blade_is_leaf(self, bend, curl):
        points, triangles = _curved_plane(bend=bend, curl=curl)
        result = classify_twig_mesh(points, triangles)
        assert result["n_components"] == 1
        comp = result["components"][0]
        assert comp["normal_wrap_ratio"] > TUBE_NORMAL_WRAP_GUARD
        assert comp["classification"] == "leaf"
        assert np.all(result["face_class"] == 0)

    def test_blade_curled_past_a_half_pipe_is_wood_and_that_is_intended(self):
        # Documents the boundary of the method. Bent this far the sheet is a
        # 6 cm deep bowl on an 11 cm blade -- its normals wrap almost as much
        # as a tube's (0.55), well outside the 0.79-0.99 range measured on
        # every real broadleaf blade. The classifier cannot separate that
        # from a woody shell, and does not pretend to.
        points, triangles = _curved_plane(bend=14.0, curl=6.0)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["normal_wrap_ratio"] < TUBE_NORMAL_WRAP_GUARD
        assert comp["classification"] == "wood"

    def test_deep_bowl_with_a_leaf_like_boundary_ratio_stays_leaf(self):
        # The same deep bowl, coarsely tessellated so its boundary-vertex
        # ratio (0.79) matches a real leaf blade's rather than a tube's.
        # Neither tube test can fire, so it stays leaf -- confirming the
        # previous case is decided by the tube rule, not by curvature alone.
        points, triangles = _curved_plane(nx=5, ny=5, spacing=0.03, bend=14.0, curl=6.0)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["boundary_vert_ratio"] > LOOP1_BOUNDARY_VERT_RATIO
        assert comp["classification"] == "leaf"

    def test_the_old_pca_signal_would_have_called_it_wood(self):
        # Makes the regression explicit: flatness is still reported, is
        # still above the old 0.08 threshold, and no longer drives the
        # decision.
        points, triangles = _curved_plane(bend=7.0, curl=3.0)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["flatness_ratio"] > 0.08
        assert comp["classification"] == "leaf"

    def test_curved_blade_area_is_all_leaf_area(self):
        points, triangles = _curved_plane(bend=7.0, curl=3.0)
        split = measure_leaf_wood_split(points, triangles)
        assert split["wood_area_m2"] == pytest.approx(0.0)
        assert split["wood_fraction"] == pytest.approx(0.0)

    def test_curved_blade_and_branched_stem_separated(self):
        # The realistic broadleaf twig: curved blades plus a woody stem.
        blade = _curved_plane(bend=7.0, curl=3.0, origin=(0.0, 0.0, 0.0))
        stem = _open_tube(
            n_seg=12, radius=0.004, height=0.15, n_rings=6, origin=(1.0, 0.0, 0.0)
        )
        points, triangles, counts = _concat(blade, stem)
        n_blade = counts[0]
        result = classify_twig_mesh(points, triangles)
        assert result["n_components"] == 2
        assert np.all(result["face_class"][:n_blade] == 0)
        assert np.all(result["face_class"][n_blade:] == 1)


class TestNearlyClosedBody:
    """A bud/berry with an opening punched in it: not watertight, so the
    closed-volume rule cannot fire, but its normals still cover more of the
    sphere than any sheet or tube can.
    """

    def test_sphere_missing_a_cap_is_wood(self):
        points, triangles = _uv_sphere(n_lat=8, n_lon=16, radius=0.01)
        # Drop the north polar cap -> one boundary loop, still a body.
        keep = ~np.any(triangles == 0, axis=1)
        triangles = triangles[keep]
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["has_boundary"] is True
        assert comp["normal_wrap_ratio"] < CLOSED_NORMAL_WRAP_RATIO
        assert comp["classification"] == "wood"
        assert comp["reason"] == "closed_normals_wrap_sphere"

    def test_a_full_cylinder_does_not_trip_the_body_rule(self):
        # 0.5 is the floor for a developable surface; the body rule sits
        # below it so tubes are decided by the tube rules instead.
        points, triangles = _open_tube(n_seg=48, radius=0.01, height=0.1, n_rings=6)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["normal_wrap_ratio"] > CLOSED_NORMAL_WRAP_RATIO
        assert comp["reason"] == "tube_two_open_ends"


class TestNormalWrapGating:
    """The wrap test is applied only to components with >= 2 boundary
    loops. Both halves of that gate matter.
    """

    def test_two_loop_tube_missed_by_boundary_ratio_is_caught_by_wrap(self):
        # A two-ring tube: every vertex is on a boundary loop, so the
        # boundary-vertex-ratio test cannot fire (ratio == 1.0). Only the
        # normal-wrap signal identifies it. This is the beech/oak stem case
        # (measured boundary-vertex ratios 0.58-0.90).
        points, triangles = _open_tube(n_seg=24, radius=0.01, height=0.1, n_rings=2)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["loop_count"] == 2
        assert comp["boundary_vert_ratio"] == pytest.approx(1.0)
        assert comp["boundary_vert_ratio"] >= LOOP2_BOUNDARY_VERT_RATIO
        assert comp["normal_wrap_ratio"] < NORMAL_WRAP_RATIO
        assert comp["classification"] == "wood"
        assert comp["reason"] == "normals_wrap_axis"

    @pytest.mark.parametrize("n", [6, 12, 24, 40])
    def test_flat_sheet_stays_leaf_at_any_tessellation_density(self, n):
        # Boundary-vertex ratio falls as 1/n for a subdivided sheet (0.56 at
        # 6x6, 0.10 at 40x40), so the ratio test alone would flip a flat leaf
        # to wood somewhere in this range at ANY threshold. The wrap guard
        # makes the answer density-independent.
        points, triangles = _grid_plane(nx=n, ny=n, spacing=1.0 / n)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["normal_wrap_ratio"] == pytest.approx(1.0)
        assert comp["classification"] == "leaf"

    @pytest.mark.parametrize("n", [12, 24, 40])
    def test_curved_sheet_stays_leaf_at_any_tessellation_density(self, n):
        points, triangles = _curved_plane(nx=n, ny=n, spacing=0.12 / n, bend=7.0)
        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["normal_wrap_ratio"] > TUBE_NORMAL_WRAP_GUARD
        assert comp["classification"] == "leaf"

    def test_single_loop_rolled_sheet_stays_leaf(self):
        # A sheet rolled far enough that its normals wrap like a tube's,
        # but with only ONE boundary loop -- the Scots pine needle-fascicle
        # morphology (measured wrap 0.523-0.73). The gate keeps it leaf;
        # ungated, the wrap test would misclassify every pine spray.
        n_seg, n_rows = 40, 4
        pts, tris = [], []
        for r in range(n_rows):
            for i in range(n_seg):
                ang = 2 * np.pi * i / n_seg
                pts.append((np.cos(ang), np.sin(ang), r * 0.05))
        for r in range(n_rows - 1):
            for i in range(n_seg - 1):  # open seam => a single boundary loop
                a, b = r * n_seg + i, r * n_seg + i + 1
                c, d = (r + 1) * n_seg + i + 1, (r + 1) * n_seg + i
                tris.append([a, b, c])
                tris.append([a, c, d])
        points = np.array(pts, dtype=np.float64)
        triangles = np.array(tris, dtype=np.int64)

        comp = classify_twig_mesh(points, triangles)["components"][0]
        assert comp["loop_count"] == 1
        assert comp["normal_wrap_ratio"] < NORMAL_WRAP_RATIO
        assert comp["classification"] == "leaf"


class TestClassifySphere:
    def test_all_faces_classified_wood(self):
        points, triangles = _uv_sphere(n_lat=6, n_lon=12, radius=1.0)
        result = classify_twig_mesh(points, triangles)
        assert np.all(result["face_class"] == 1)
        assert result["n_components"] == 1
        comp = result["components"][0]
        assert comp["classification"] == "wood"
        assert comp["has_boundary"] is False


class TestClassifyMixedMesh:
    def test_leaf_plane_and_wood_cylinder_separated(self):
        plane = _grid_plane(nx=6, ny=6, spacing=1.0, origin=(0.0, 0.0, 0.0))
        cylinder = _closed_cylinder(
            n_seg=12, radius=1.0, height=2.0, origin=(10.0, 0.0, 0.0)
        )
        points, triangles, counts = _concat(plane, cylinder)
        n_plane_tris, n_cyl_tris = counts

        result = classify_twig_mesh(points, triangles)
        assert result["n_components"] == 2
        face_class = result["face_class"]
        assert np.all(face_class[:n_plane_tris] == 0)
        assert np.all(face_class[n_plane_tris:] == 1)

        split = measure_leaf_wood_split(points, triangles)
        assert split["leaf_area_m2"] == pytest.approx(25.0)
        cyl_area = float(triangle_areas(*cylinder).sum())
        assert split["wood_area_m2"] == pytest.approx(cyl_area)
        assert split["n_leaf_components"] == 1
        assert split["n_wood_components"] == 1
        assert len(split["wood_components"]) == 1
        assert split["wood_components"][0]["area_m2"] == pytest.approx(cyl_area)


# --- edge cases -----------------------------------------------------------------


class TestClassifyEdgeCases:
    def test_empty_mesh(self):
        result = classify_twig_mesh(
            np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
        )
        assert result["n_components"] == 0
        assert len(result["face_class"]) == 0

        split = measure_leaf_wood_split(
            np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
        )
        assert split["leaf_area_m2"] == 0.0
        assert split["wood_area_m2"] == 0.0
        assert split["wood_fraction"] == 0.0

    def test_tiny_component_defaults_to_leaf(self):
        # A single triangle has only 3 verts, below MIN_COMPONENT_VERTS --
        # too small to trust the PCA/loop-count signals, so it defaults leaf.
        points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        triangles = np.array([[0, 1, 2]])
        result = classify_twig_mesh(points, triangles)
        assert result["components"][0]["classification"] == "leaf"
        assert result["components"][0]["reason"] == "too_small_default_leaf"
        assert result["components"][0]["n_verts"] < MIN_COMPONENT_VERTS

    def test_thresholds_are_module_constants_not_magic_numbers(self):
        # Guards against silent threshold drift. Each value sits inside an
        # empty band measured across all 49 twig prototypes, NOT at an error
        # minimum -- see the constants' comments in leaf_geometry.py. Moving
        # any of them requires re-running that validation.
        assert LOOP2_BOUNDARY_VERT_RATIO == 0.5
        assert LOOP1_BOUNDARY_VERT_RATIO == 0.35
        assert NORMAL_WRAP_RATIO == 0.57
        assert CLOSED_NORMAL_WRAP_RATIO == 0.45
        assert TUBE_NORMAL_WRAP_GUARD == 0.80
        # The body threshold must stay below a developable surface's 0.5
        # floor, or every branch cylinder becomes a "body".
        assert CLOSED_NORMAL_WRAP_RATIO < 0.5 < TUBE_NORMAL_WRAP_GUARD
        assert MIN_COMPONENT_VERTS == 8

    def test_pca_flatness_is_reported_but_not_used(self):
        # It stays in the diagnostics for audit; if it ever drives the
        # decision again, TestClassifyCurvedSheet regresses.
        import growpy.utils.leaf_geometry as lg

        assert not hasattr(lg, "FLATNESS_SVD_RATIO")
        comp = classify_twig_mesh(*_grid_plane(nx=6, ny=6))["components"][0]
        assert "flatness_ratio" in comp
        assert "normal_wrap_ratio" in comp


# --- pxr-backed tests (require the growpy conda env) ----------------------------


@pytest.fixture
def pxr_usd():
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Usd, UsdGeom, Vt

    return SimpleNamespace(Usd=Usd, UsdGeom=UsdGeom, Vt=Vt)


def _build_synthetic_static_usda(
    pxr_usd,
    path,
    prototype_name: str,
    points,
    triangles,
    subsets: dict[str, list[int]] | None = None,
):
    Usd = pxr_usd.Usd
    UsdGeom = pxr_usd.UsdGeom
    Vt = pxr_usd.Vt

    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, f"/{prototype_name}")
    stage.SetDefaultPrim(root.GetPrim())

    mesh_path = f"/{prototype_name}/{prototype_name}_mesh"
    mesh = UsdGeom.Mesh.Define(stage, mesh_path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([tuple(p) for p in points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(triangles)))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray([int(i) for tri in triangles for i in tri])
    )

    if subsets:
        for name, face_indices in subsets.items():
            subset = UsdGeom.Subset.Define(stage, f"{mesh_path}/{name}")
            subset.CreateElementTypeAttr("face")
            subset.CreateIndicesAttr(Vt.IntArray([int(i) for i in face_indices]))

    stage.GetRootLayer().Save()
    return stage


class TestLoadFullTwigMesh:
    def test_no_subsets(self, tmp_path, pxr_usd):
        points, triangles = _grid_plane(nx=3, ny=3)
        path = tmp_path / "conifer_spray_static.usda"
        _build_synthetic_static_usda(pxr_usd, path, "conifer_spray", points, triangles)

        loaded_points, loaded_tris, subsets = load_full_twig_mesh(path)
        assert loaded_tris.shape[0] == len(triangles)
        assert subsets == {}

    def test_subsets_returned_by_name(self, tmp_path, pxr_usd):
        points, triangles = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
        ), np.array([[0, 1, 2], [0, 2, 3]])
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(
            pxr_usd,
            path,
            "broadleaf",
            points,
            triangles,
            subsets={"broadleaf_leaf": [0], "broadleaf_bark": [1]},
        )
        _, _, subsets = load_full_twig_mesh(path)
        assert set(subsets.keys()) == {"broadleaf_leaf", "broadleaf_bark"}
        assert list(subsets["broadleaf_bark"]) == [1]

    def test_non_triangular_face_raises(self, tmp_path, pxr_usd):
        Usd, UsdGeom, Vt = pxr_usd.Usd, pxr_usd.UsdGeom, pxr_usd.Vt
        path = tmp_path / "quad_static.usda"
        stage = Usd.Stage.CreateNew(str(path))
        root = UsdGeom.Xform.Define(stage, "/quad")
        stage.SetDefaultPrim(root.GetPrim())
        mesh = UsdGeom.Mesh.Define(stage, "/quad/quad_mesh")
        mesh.CreatePointsAttr(
            Vt.Vec3fArray(
                [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
            )
        )
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([0, 1, 2, 3]))
        stage.GetRootLayer().Save()

        with pytest.raises(ValueError, match="non-triangular"):
            load_full_twig_mesh(path)


class TestMeasurePrototypeLeafGeometry:
    def test_bark_subset_cross_check_agrees_with_geometry(self, tmp_path, pxr_usd):
        """A prototype where leaf/wood ARE separated by a bark GeomSubset:
        the geometric wood_area_m2 should match bark_subset_area_m2 -- the
        main validation this module relies on.
        """
        plane = _grid_plane(nx=6, ny=6, origin=(0.0, 0.0, 0.0))  # leaf, 25 m^2
        cylinder = _closed_cylinder(
            n_seg=12, radius=1.0, height=2.0, origin=(10.0, 0.0, 0.0)
        )  # wood
        points, triangles, counts = _concat(plane, cylinder)
        n_plane_tris, n_cyl_tris = counts

        path = tmp_path / "mixedspecies_static.usda"
        _build_synthetic_static_usda(
            pxr_usd,
            path,
            "mixedspecies",
            points,
            triangles,
            subsets={
                "mixedspecies_leaf": list(range(n_plane_tris)),
                "mixedspecies_bark": list(
                    range(n_plane_tris, n_plane_tris + n_cyl_tris)
                ),
            },
        )
        # Simulate the XRFF-274 bug: old sidecar reports whole-mesh area.
        old_total = float(triangle_areas(points, triangles).sum())
        (tmp_path / "mixedspecies_leaf_area.json").write_text(
            json.dumps({"leaf_area_m2": old_total})
        )

        result = measure_prototype_leaf_geometry(path)

        assert result["old_leaf_area_m2"] == pytest.approx(old_total)
        assert result["leaf_area_m2"] == pytest.approx(25.0)
        assert result["leaf_area_m2"] < result["old_leaf_area_m2"]
        assert result["bark_subset_area_m2"] == pytest.approx(result["wood_area_m2"])
        assert result["material_subset_names"] == [
            "mixedspecies_bark",
            "mixedspecies_leaf",
        ]

    def test_no_old_sidecar_leaves_old_leaf_area_none(self, tmp_path, pxr_usd):
        points, triangles = _grid_plane(nx=3, ny=3)
        path = tmp_path / "nosidecar_static.usda"
        _build_synthetic_static_usda(pxr_usd, path, "nosidecar", points, triangles)
        result = measure_prototype_leaf_geometry(path)
        assert result["old_leaf_area_m2"] is None
        assert result["bark_subset_area_m2"] is None
        assert "definition" in result and "geometry" in result["definition"].lower()


class TestSidecarWriting:
    def test_writes_geom_suffixed_file_without_touching_original(
        self, tmp_path, pxr_usd
    ):
        points, triangles = _grid_plane(nx=3, ny=3)
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(pxr_usd, path, "broadleaf", points, triangles)
        original_sidecar = tmp_path / "broadleaf_leaf_area.json"
        original_sidecar.write_text(json.dumps({"leaf_area_m2": 999.0}))

        result, out_path = measure_and_write_prototype(path)

        assert out_path.name == "broadleaf_leaf_area_geom.json"
        assert out_path.parent == tmp_path
        # Original XRFF-274 sidecar must be untouched.
        assert json.loads(original_sidecar.read_text()) == {"leaf_area_m2": 999.0}

        loaded = json.loads(out_path.read_text())
        assert loaded["prototype"] == "broadleaf"
        assert loaded["old_leaf_area_m2"] == pytest.approx(999.0)

    def test_output_dir_override(self, tmp_path, pxr_usd):
        points, triangles = _grid_plane(nx=3, ny=3)
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(pxr_usd, path, "broadleaf", points, triangles)
        result = measure_prototype_leaf_geometry(path)
        out_dir = tmp_path / "elsewhere"
        out_dir.mkdir()
        out_path = write_leaf_geometry_sidecar(result, path, output_dir=out_dir)
        assert out_path == out_dir / "broadleaf_leaf_area_geom.json"
        assert out_path.exists()


class TestBatchDiscoveryAndRun:
    def test_discover_finds_only_static_files(self, tmp_path, pxr_usd):
        species_dir = tmp_path / "some_species_twig"
        species_dir.mkdir()
        points, triangles = _grid_plane(nx=3, ny=3)
        _build_synthetic_static_usda(
            pxr_usd,
            species_dir / "some_species_a_static.usda",
            "some_species_a",
            points,
            triangles,
        )
        (species_dir / "some_species_a_skeletal.usda").write_text("#usda 1.0\n")

        found = discover_static_prototypes(tmp_path)
        assert found == [species_dir / "some_species_a_static.usda"]

    def test_run_over_all_twigs_writes_sidecar_per_prototype(self, tmp_path, pxr_usd):
        species_dir = tmp_path / "some_species_twig"
        species_dir.mkdir()
        points, triangles = _grid_plane(nx=3, ny=3)
        for name in ("some_species_a", "some_species_b"):
            _build_synthetic_static_usda(
                pxr_usd,
                species_dir / f"{name}_static.usda",
                name,
                points,
                triangles,
            )

        results = run_over_all_twigs(tmp_path)
        assert len(results) == 2
        names = {r["prototype"] for r in results}
        assert names == {"some_species_a", "some_species_b"}
        for name in names:
            assert (species_dir / f"{name}_leaf_area_geom.json").exists()


def test_prototype_name_from_static_path_strips_suffix():
    from pathlib import Path

    assert (
        prototype_name_from_static_path(Path("x/broadleaf_static.usda")) == "broadleaf"
    )
    assert prototype_name_from_static_path(Path("x/broadleaf.usda")) == "broadleaf"
