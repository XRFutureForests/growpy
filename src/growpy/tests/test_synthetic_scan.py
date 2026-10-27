"""Tests for growpy.structure.synthetic_scan (XRFF-344).

The XML and geometry tests need nothing but numpy. The scan test runs HELIOS++ on a
cylinder-plus-cone "tree" at a coarse resolution and is skipped when helios++ is absent.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from growpy.structure import synthetic_scan as ss


def write_toy_tree(
    path: Path, stem_r=0.2, stem_h=8.0, crown_r=2.0, crown_z0=4.0, top=10.0, n=24
):
    """Open cylinder (stem) plus cone (crown), z up, base at the origin."""
    v, f = [], []
    for k in range(n):  # stem ring bottom/top
        a = 2 * math.pi * k / n
        v.append((stem_r * math.cos(a), stem_r * math.sin(a), 0.0))
        v.append((stem_r * math.cos(a), stem_r * math.sin(a), stem_h))
    for k in range(n):
        b0, t0, b1, t1 = (
            2 * k + 1,
            2 * k + 2,
            2 * ((k + 1) % n) + 1,
            2 * ((k + 1) % n) + 2,
        )
        f += [(b0, b1, t1), (b0, t1, t0)]
    base = len(v)
    for k in range(n):  # cone rim
        a = 2 * math.pi * k / n
        v.append((crown_r * math.cos(a), crown_r * math.sin(a), crown_z0))
    v.append((0.0, 0.0, top))
    apex = len(v)
    for k in range(n):
        f.append((base + k + 1, base + (k + 1) % n + 1, apex))
    lines = [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in v] + [
        f"f {a} {b} {c}" for a, b, c in f
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_head_angle_convention():
    assert ss.head_angle_deg(0, 1) == pytest.approx(0)  # +y
    assert ss.head_angle_deg(-1, 0) == pytest.approx(90)  # west, counter-clockwise
    assert ss.head_angle_deg(0, -1) == pytest.approx(180)
    assert ss.head_angle_deg(1, 0) == pytest.approx(270)


def test_ring_positions_window_faces_centre():
    pos = ss.ring_positions(4, 10.0, window_half_deg=20)
    assert len(pos) == 4
    for p in pos:
        assert math.hypot(p.x, p.y) == pytest.approx(10.0)
        mid = (p.head_start_deg + p.head_stop_deg) / 2
        diff = (mid - ss.head_angle_deg(-p.x, -p.y) + 180) % 360 - 180
        assert diff == pytest.approx(0, abs=1e-6)
        assert p.head_stop_deg - p.head_start_deg == pytest.approx(40)


def test_xml_parses_and_sets_parts_and_height(tmp_path):
    parts = [(tmp_path / "g.obj", "z", (0, 0, 0)), (tmp_path / "t.obj", "y", (1, 2, 0))]
    scene = ET.fromstring(ss.scene_xml(parts, "s"))
    ids = [p.get("id") for p in scene.iter("part")]
    assert ids == ["0", "1"]
    sc = ss.ScannerSetup(height_m=1.5)
    survey = ET.fromstring(
        ss.survey_xml("n", tmp_path / "scene.xml", "s", ss.ring_positions(3, 5), sc)
    )
    legs = list(survey.iter("leg"))
    assert len(legs) == 3
    # platform z + tripod mount 1.5 + beam origin 0.2 = optical centre height
    z = float(legs[0].find("platformSettings").get("z"))
    assert z + 1.5 + 0.2 == pytest.approx(1.5)


def test_read_legs_streams_chunks_and_drops_ground(tmp_path):
    # HELIOS ASCII rows: x y z intensity echo_width rn nr fwi hit_object_id class gps
    rng = np.random.default_rng(0)
    expected = []
    for leg in range(2):
        n = 1003  # not a multiple of the chunk size
        xyz = rng.normal(size=(n, 3))
        part = rng.integers(0, 3, n)  # 0 ground, 1 target, 2 neighbour
        rows = np.column_stack([xyz, np.ones((n, 7))])
        rows[:, 8] = part
        np.savetxt(tmp_path / f"leg{leg:03d}_points.xyz", rows, fmt="%.6f")
        expected.append((xyz, part, leg))
    (tmp_path / "leg002_points.xyz").write_text("", encoding="utf-8")  # empty leg

    xyz, part, leg = ss.read_legs(tmp_path, chunk_rows=100)
    keep = [p != 0 for _, p, _ in expected]
    want = np.vstack([x[k] for (x, _, _), k in zip(expected, keep, strict=True)])
    assert np.allclose(xyz, want, atol=1e-6)  # written with %.6f
    assert (part != 0).all()
    assert np.array_equal(
        part, np.concatenate([p[k] for (_, p, _), k in zip(expected, keep, strict=True)])
    )
    assert np.array_equal(
        leg, np.concatenate([np.full(k.sum(), i) for i, k in enumerate(keep)])
    )
    assert xyz.dtype == np.float64 and xyz.flags.c_contiguous

    xyz_all, part_all, _ = ss.read_legs(tmp_path, keep_ground=True, chunk_rows=100)
    assert len(xyz_all) == 2 * 1003
    assert (part_all == 0).sum() == sum((p == 0).sum() for _, p, _ in expected)


def _helios_available() -> bool:
    try:
        ss.find_helios()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _helios_available(), reason="helios++ not installed")
def test_scan_toy_tree_alone(tmp_path):
    obj = write_toy_tree(tmp_path / "toy.obj")
    sc = ss.ScannerSetup(pulse_freq_hz=100_000, resolution_deg=0.2)
    res = ss.scan_alone(
        obj,
        tmp_path / "run",
        n_positions=3,
        distance_m=8.0,
        window_half_deg=25,
        scanner=sc,
        threads=2,
        keep_ground=True,
    )
    tree = res.tree(1)
    assert len(tree) > 500
    assert set(np.unique(res.part)) <= {0, 1}
    assert set(np.unique(res.position)) == {0, 1, 2}
    # frame: base at the origin, z up, inside the toy's extent
    assert tree[:, 2].min() == pytest.approx(0.0, abs=0.3)
    assert tree[:, 2].max() <= 10.05
    assert np.abs(tree[:, :2]).max() <= 2.05
    ground = res.xyz[res.part == 0]
    assert np.abs(ground[:, 2]).max() < 0.05
    # the stem radius comes back from the points below the crown
    stem = tree[(tree[:, 2] > 1.0) & (tree[:, 2] < 3.5)]
    r = np.hypot(stem[:, 0], stem[:, 1])
    assert np.median(r) == pytest.approx(0.2, abs=0.02)
    # default read drops ground; the target points are unchanged
    no_ground, part, _ = ss.read_legs(res.run_dir)
    assert (part != 0).all()
    assert len(no_ground) == len(tree)
