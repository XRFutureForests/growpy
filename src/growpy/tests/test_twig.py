"""Tests for growpy.core.twig module."""

import math

import pytest

from growpy.core.twig import (
    TwigPlacement,
    get_face_center_and_normal,
    normal_to_rotation_matrix,
)


class TestTwigPlacement:
    """Tests for TwigPlacement dataclass."""

    def test_default_values(self):
        tp = TwigPlacement(
            type="twig_long",
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 0.0, 1.0),
        )
        assert tp.scale == 1.0
        assert tp.bone_id is None
        assert tp.branch_id is None
        assert tp.orientation == (0.0, 0.0, 1.0)

    def test_to_dict(self):
        tp = TwigPlacement(
            type="twig_short",
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 1.0, 0.0),
            scale=0.5,
            bone_id=10,
            branch_id=3,
        )
        d = tp.to_dict()
        assert d["type"] == "twig_short"
        assert d["position"] == (1.0, 2.0, 3.0)
        assert d["normal"] == (0.0, 1.0, 0.0)
        assert d["scale"] == 0.5
        assert d["bone_id"] == 10
        assert d["branch_id"] == 3

    def test_to_dict_roundtrip(self):
        tp = TwigPlacement(
            type="twig_dead",
            position=(0.0, 0.0, 0.0),
            normal=(1.0, 0.0, 0.0),
        )
        d = tp.to_dict()
        tp2 = TwigPlacement(**d)
        assert tp2.type == tp.type
        assert tp2.position == tp.position
        assert tp2.normal == tp.normal


class TestGetFaceCenterAndNormal:
    """Tests for face center and normal calculation."""

    def test_triangle_center(self):
        vertices = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 2.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        assert center[0] == pytest.approx(1.0)
        assert center[1] == pytest.approx(2.0 / 3.0)
        assert center[2] == pytest.approx(0.0)

    def test_triangle_normal_z_up(self):
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        # Normal should point in Z direction for XY-plane triangle
        assert abs(normal[2]) == pytest.approx(1.0, abs=1e-6)

    def test_quad_center(self):
        vertices = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
        face = [0, 1, 2, 3]
        center, normal = get_face_center_and_normal(vertices, face)
        assert center[0] == pytest.approx(1.0)
        assert center[1] == pytest.approx(1.0)
        assert center[2] == pytest.approx(0.0)

    def test_degenerate_face_returns_default_normal(self):
        vertices = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        assert normal == (0.0, 0.0, 1.0)

    def test_normal_is_unit_length(self):
        vertices = [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 4.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        length = math.sqrt(sum(n * n for n in normal))
        assert length == pytest.approx(1.0, abs=1e-6)


class TestNormalToRotationMatrix:
    """Tests for normal-to-rotation matrix conversion."""

    def test_z_up_normal(self):
        matrix = normal_to_rotation_matrix((0.0, 0.0, 1.0))
        assert len(matrix) == 3
        assert len(matrix[0]) == 3

    def test_x_axis_normal(self):
        matrix = normal_to_rotation_matrix((1.0, 0.0, 0.0))
        # X-axis of result should be the input normal
        assert matrix[0][0] == pytest.approx(1.0)
        assert matrix[1][0] == pytest.approx(0.0)
        assert matrix[2][0] == pytest.approx(0.0)

    def test_matrix_orthogonality(self):
        matrix = normal_to_rotation_matrix((0.577, 0.577, 0.577))
        # Columns should be orthogonal
        col0 = [matrix[i][0] for i in range(3)]
        col1 = [matrix[i][1] for i in range(3)]
        col2 = [matrix[i][2] for i in range(3)]
        dot_01 = sum(a * b for a, b in zip(col0, col1))
        dot_02 = sum(a * b for a, b in zip(col0, col2))
        dot_12 = sum(a * b for a, b in zip(col1, col2))
        assert dot_01 == pytest.approx(0.0, abs=1e-4)
        assert dot_02 == pytest.approx(0.0, abs=1e-4)
        assert dot_12 == pytest.approx(0.0, abs=1e-4)
