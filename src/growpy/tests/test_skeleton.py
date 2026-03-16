"""Tests for growpy.core.skeleton module."""

import math

import pytest

from growpy.core.skeleton import (
    JointTransform,
    SkeletonHierarchy,
    Vector3,
    calculate_rotation_to_align,
)


class TestVector3:
    """Tests for Vector3 dataclass."""

    def test_subtraction(self):
        a = Vector3(3.0, 5.0, 7.0)
        b = Vector3(1.0, 2.0, 3.0)
        result = a - b
        assert result.x == 2.0
        assert result.y == 3.0
        assert result.z == 4.0

    def test_division(self):
        v = Vector3(4.0, 6.0, 8.0)
        result = v / 2.0
        assert result.x == 2.0
        assert result.y == 3.0
        assert result.z == 4.0

    def test_length(self):
        v = Vector3(3.0, 4.0, 0.0)
        assert v.length() == pytest.approx(5.0)

    def test_length_unit_vector(self):
        v = Vector3(1.0, 0.0, 0.0)
        assert v.length() == pytest.approx(1.0)

    def test_length_zero_vector(self):
        v = Vector3(0.0, 0.0, 0.0)
        assert v.length() == 0.0

    def test_length_3d(self):
        v = Vector3(1.0, 2.0, 2.0)
        assert v.length() == pytest.approx(3.0)

    def test_as_tuple(self):
        v = Vector3(1.5, 2.5, 3.5)
        assert v.as_tuple() == (1.5, 2.5, 3.5)


class TestJointTransform:
    """Tests for JointTransform dataclass."""

    def test_identity_rotation_when_none(self):
        t = JointTransform(translation=Vector3(0, 0, 0))
        assert t.is_identity_rotation() is True

    def test_identity_rotation_matrix(self):
        t = JointTransform(
            translation=Vector3(0, 0, 0),
            rotation_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        )
        assert t.is_identity_rotation() is True

    def test_non_identity_rotation(self):
        t = JointTransform(
            translation=Vector3(0, 0, 0),
            rotation_matrix=[[0, -1, 0], [1, 0, 0], [0, 0, 1]],
        )
        assert t.is_identity_rotation() is False

    def test_near_identity_rotation(self):
        t = JointTransform(
            translation=Vector3(0, 0, 0),
            rotation_matrix=[
                [1.0 + 1e-8, 1e-8, 0],
                [0, 1.0, 1e-8],
                [0, 0, 1.0],
            ],
        )
        assert t.is_identity_rotation() is True


class TestCalculateRotationToAlign:
    """Tests for rotation matrix calculation."""

    def test_already_aligned(self):
        v = Vector3(0, 0, 1)
        result = calculate_rotation_to_align(v, v)
        assert result == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def test_opposite_vectors(self):
        a = Vector3(0, 0, 1)
        b = Vector3(0, 0, -1)
        result = calculate_rotation_to_align(a, b)
        assert result is not None
        # 180-degree rotation should negate x and y
        assert result[0][0] == pytest.approx(-1)
        assert result[1][1] == pytest.approx(-1)

    def test_zero_vector_returns_none(self):
        a = Vector3(0, 0, 0)
        b = Vector3(0, 0, 1)
        assert calculate_rotation_to_align(a, b) is None

    def test_90_degree_rotation(self):
        a = Vector3(1, 0, 0)
        b = Vector3(0, 1, 0)
        result = calculate_rotation_to_align(a, b)
        assert result is not None
        # Applying rotation to a should give b
        rx = (
            result[0][0] * a.x + result[0][1] * a.y + result[0][2] * a.z
        )
        ry = (
            result[1][0] * a.x + result[1][1] * a.y + result[1][2] * a.z
        )
        rz = (
            result[2][0] * a.x + result[2][1] * a.y + result[2][2] * a.z
        )
        assert rx == pytest.approx(0, abs=1e-6)
        assert ry == pytest.approx(1, abs=1e-6)
        assert rz == pytest.approx(0, abs=1e-6)

    def test_arbitrary_rotation(self):
        a = Vector3(1, 0, 0)
        b = Vector3(0, 0, 1)
        result = calculate_rotation_to_align(a, b)
        assert result is not None
        rx = result[0][0] * a.x + result[0][1] * a.y + result[0][2] * a.z
        ry = result[1][0] * a.x + result[1][1] * a.y + result[1][2] * a.z
        rz = result[2][0] * a.x + result[2][1] * a.y + result[2][2] * a.z
        assert rx == pytest.approx(0, abs=1e-6)
        assert ry == pytest.approx(0, abs=1e-6)
        assert rz == pytest.approx(1, abs=1e-6)


class TestSkeletonHierarchy:
    """Tests for SkeletonHierarchy data structure."""

    def test_construction(self):
        skel = SkeletonHierarchy(
            joint_names=["root", "joint_1"],
            joint_parents=[-1, 0],
            bind_transforms=[
                JointTransform(translation=Vector3(0, 0, 0)),
                JointTransform(translation=Vector3(0, 0, 1)),
            ],
            rest_transforms=[
                JointTransform(translation=Vector3(0, 0, 0)),
                JointTransform(translation=Vector3(0, 0, 1)),
            ],
            bone_to_joint_map={0: 1},
        )
        assert len(skel.joint_names) == 2
        assert skel.joint_parents[0] == -1
        assert skel.joint_parents[1] == 0
        assert skel.bone_to_joint_map[0] == 1
