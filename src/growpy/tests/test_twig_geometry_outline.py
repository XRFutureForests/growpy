"""Densify cut choice, face-cap warning and outline dissolve (twig_geometry, E156)."""

import logging
import math

import pytest

bpy = pytest.importorskip("bpy")
bmesh = pytest.importorskip("bmesh")

from growpy.io.usd import twig_geometry as tg  # noqa: E402


def _object(verts, faces):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("m")
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new("o", me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return obj


def _square(edge_m):
    return _object(
        [(0, 0, 0), (edge_m, 0, 0), (edge_m, edge_m, 0), (0, edge_m, 0)], [(0, 1, 2, 3)]
    )


def test_densify_does_not_overshoot_the_target():
    obj = _square(0.010)  # 10 mm edges; one cut reaches the 5 mm target exactly
    got = tg.densify_mesh_to_target_edge(obj, target_edge_mm=5.0)
    assert got == pytest.approx(5.0, rel=0.01)
    assert len(obj.data.polygons) == 4


def test_densify_warns_when_the_cap_binds(caplog):
    obj = _square(0.010)
    with caplog.at_level(logging.WARNING, logger=tg.logger.name):
        tg.densify_mesh_to_target_edge(obj, target_edge_mm=0.01, max_faces=10)
    assert "face cap" in caplog.text


def test_outline_dissolve_keeps_the_outline_with_fewer_triangles():
    n = 64
    ring = [
        (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0)
        for i in range(n)
    ]
    fan = [(n, i, (i + 1) % n) for i in range(n)]  # fan around a centre vertex
    obj = _object([*ring, (0.0, 0.0, 0.0)], fan)
    area0 = tg.mesh_surface_area(obj.data)
    tg.planar_dissolve(obj, angle_deg=1.0)
    plain = len(obj.data.polygons)
    obj = _object([*ring, (0.0, 0.0, 0.0)], fan)
    fb, fa, bb, ba = tg.planar_dissolve(obj, angle_deg=1.0, outline_angle_deg=20.0)
    assert plain == n - 2
    assert fa < plain / 2
    assert ba == fa + 2  # still one closed outline around a fan
    assert tg.mesh_surface_area(obj.data) == pytest.approx(area0, rel=0.05)
