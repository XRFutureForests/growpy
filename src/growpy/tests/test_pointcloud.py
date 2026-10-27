"""L2 point-cloud metrics on synthetic toy clouds (growpy.structure.pointcloud)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from growpy.structure import pointcloud as pc
from growpy.tools.pointcloud_metrics import main as cli_main


def _ball(n, centre, radius, rng):
    v = rng.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return np.asarray(centre) + v * radius * rng.random(n)[:, None] ** (1 / 3)


def _stem(height, radius, rng, n=4000):
    a = rng.random(n) * 2 * math.pi
    return np.column_stack(
        [radius * np.cos(a), radius * np.sin(a), rng.random(n) * height]
    )


def _toy_tree(rng, offset=0.0):
    """Stem r = 0.15 m from 0 to 6 m, a filled crown ball r = 3 m centred at 9 m."""
    return np.vstack(
        [_stem(6.0, 0.15, rng), _ball(60_000, (offset, 0.0, 9.0), 3.0, rng)]
    )


def _grid(shape, step=0.05):
    axes = [np.arange(n) * step for n in shape]
    return np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)


def test_box_dimension_of_line_plane_cube():
    for shape, dim in (((64, 1, 1), 1.0), ((64, 64, 1), 2.0), ((64, 64, 64), 3.0)):
        db = pc.box_dimension(_grid(shape), min_box=0.1)["L2.box_dimension"]
        assert db == pytest.approx(dim, abs=0.12), shape


def test_toy_tree_stem_crown_and_envelope():
    rng = np.random.default_rng(1)
    m = pc.metrics(_toy_tree(rng))
    assert m["L2.height_m"] == pytest.approx(12.0, abs=0.1)
    assert m["L2.dbh_m"] == pytest.approx(0.30, abs=0.01)
    assert m["L2.crown_base_m"] == pytest.approx(6.0, abs=0.5)
    ball = 4 / 3 * math.pi * 27
    assert m["L2.hull_volume_m3"] == pytest.approx(ball, rel=0.1)
    assert m["L2.layered_hull_volume_m3"] == pytest.approx(ball, rel=0.15)
    assert m["L2.alpha_volume_m3"] <= m["L2.hull_volume_m3"] * 1.001
    assert m["L2.alpha_volume_m3"] > 0.7 * ball
    assert m["L2.crown_diameter_m"] == pytest.approx(6.0, rel=0.05)
    assert m["L2.crown_offset_rel"] < 0.05
    assert m["L2.crown_sector_ratio"] > 0.85
    assert m["L2.gap_fraction_vertical"] < 0.05
    shares = [m[f"L2.points_z{k:02d}"] for k in range(1, 11)]
    voxels = [m[f"L2.voxels_z{k:02d}"] for k in range(1, 11)]
    assert sum(shares) == pytest.approx(1.0)
    assert sum(voxels) == pytest.approx(1.0)
    assert int(np.argmax(voxels)) in (6, 7)  # widest crown at 9 of 12 m
    assert 0 < m["L2.voxel_occupancy"] <= 1


def test_offset_crown_is_asymmetric():
    m = pc.metrics(_toy_tree(np.random.default_rng(2), offset=1.5))
    assert m["L2.crown_offset_rel"] == pytest.approx(0.5, abs=0.1)
    assert m["L2.crown_sector_ratio"] < 0.6


def test_sparse_crown_has_gaps_and_less_alpha_volume():
    rng = np.random.default_rng(3)
    a = rng.random(20_000) * 2 * math.pi
    ring = np.column_stack([3 * np.cos(a), 3 * np.sin(a), 8 + rng.random(20_000) * 0.2])
    cloud = np.vstack([_stem(8.0, 0.15, rng), ring])
    m = pc.metrics(cloud)
    assert m["L2.gap_fraction_vertical"] > 0.8
    two = np.vstack(
        [_ball(20_000, (0, 0, 0), 1.0, rng), _ball(20_000, (6, 0, 0), 1.0, rng)]
    )
    alpha = pc.alpha_volume(pc.thin(two, 0.1), 0.5)
    assert alpha == pytest.approx(2 * 4 / 3 * math.pi, rel=0.15)
    assert alpha < 0.5 * pc._hull_volume(two)


@pytest.mark.parametrize("ext", [".npy", ".xyz", ".csv", ".ply-ascii", ".ply-binary"])
def test_read_points_formats(tmp_path, ext):
    pts = np.random.default_rng(4).random((50, 3)) * 10
    if ext == ".npy":
        path = tmp_path / "t.npy"
        np.save(path, pts)
    elif ext == ".xyz":
        path = tmp_path / "t.xyz"
        np.savetxt(path, np.column_stack([pts, np.ones(50)]))
    elif ext == ".csv":
        path = tmp_path / "t.csv"
        np.savetxt(path, pts, delimiter=",", header="x,y,z", comments="")
    else:
        path = tmp_path / "t.ply"
        binary = ext.endswith("binary")
        head = (
            "ply\nformat {} 1.0\nelement vertex 50\nproperty float x\nproperty float y\n"
            "property float z\nproperty uchar intensity\nend_header\n"
        ).format("binary_little_endian" if binary else "ascii")
        with open(path, "wb") as f:
            f.write(head.encode("ascii"))
            if binary:
                rec = np.zeros(
                    50, dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("i", "u1")]
                )
                rec["x"], rec["y"], rec["z"] = pts.T
                f.write(rec.tobytes())
            else:
                for p in pts:
                    f.write(f"{p[0]} {p[1]} {p[2]} 7\n".encode("ascii"))
    got = pc.read_points(path)
    assert got.shape == (50, 3)
    np.testing.assert_allclose(got, pts, rtol=1e-6, atol=1e-5)


def test_cli_writes_one_row_per_cloud(tmp_path):
    rng = np.random.default_rng(5)
    for name in ("A_TLS", "B"):
        np.save(tmp_path / f"{name}.npy", _toy_tree(rng))
    out = tmp_path / "m.csv"
    assert (
        cli_main(
            [str(tmp_path / "A_TLS.npy"), str(tmp_path / "B.npy"), "--out", str(out)]
        )
        == 0
    )
    import pandas as pd

    table = pd.read_csv(out)
    assert list(table["tree_id"]) == ["A", "B"]
    assert "L2.box_dimension" in table


def test_stem_circle_ignores_branches_crossing_the_slice():
    """A branch and a clump of low twigs in the 1.2-1.4 m slice (the HELIOS Grove-stem
    case that gave a 1.66 m DBH with a plain circle fit) leave the stem DBH alone."""
    rng = np.random.default_rng(6)
    a = rng.random(1500) * 2 * math.pi
    stem = np.column_stack([0.15 * np.cos(a), 0.15 * np.sin(a)])
    stem += rng.normal(scale=0.003, size=stem.shape)
    t = rng.random(1500)
    branch = np.column_stack([0.15 + 1.35 * t, 0.3 * t]) + rng.normal(
        scale=0.03, size=(1500, 2)
    )
    clump = np.array([1.2, -1.0]) + rng.normal(scale=0.15, size=(800, 2))
    ring = np.vstack([stem, branch, clump])
    cx, cy, r = pc.fit_stem_circle(ring)
    assert 2 * r == pytest.approx(0.30, abs=0.02)
    assert math.hypot(cx, cy) < 0.02
    # half the stem hidden from the scanner: the arc still gives the radius
    half = stem[stem[:, 0] > 0]
    assert 2 * pc.fit_stem_circle(np.vstack([half, branch]))[2] == pytest.approx(
        0.30, abs=0.03
    )
    # the same clutter in a whole tree: metrics() reads the DBH through it
    z = 1.2 + rng.random(len(ring)) * 0.2
    tree = np.vstack([_toy_tree(rng), np.column_stack([ring, z])])
    assert pc.metrics(tree)["L2.dbh_m"] == pytest.approx(0.30, abs=0.02)


def test_keep_connected_drops_a_detached_crown_fragment():
    rng = np.random.default_rng(7)
    tree = _toy_tree(rng)
    fragment = _ball(
        3000, (4.0, 0.0, 20.0), 1.0, rng
    )  # a neighbour's crown, 8 m higher
    kept = pc.keep_connected(np.vstack([tree, fragment]))
    assert len(kept) == len(tree)
    assert pc.metrics(kept)["L2.height_m"] == pytest.approx(12.0, abs=0.1)
    assert len(pc.keep_connected(tree)) == len(tree)  # a clean tree passes intact
