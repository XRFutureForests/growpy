"""Tests for growpy.core.skeleton module."""

from types import SimpleNamespace

import pytest

from growpy.core.skeleton import (
    JointTransform,
    SkeletonHierarchy,
    Vector3,
    _apply_falloff,
    _distance_3d,
    build_skeleton_hierarchy,
    calculate_rotation_to_align,
    filter_bones_for_mesh,
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


def _make_grove_vector(x, y, z):
    """Helper to create a mock Grove vector with as_tuple() method."""
    return SimpleNamespace(x=x, y=y, z=z, as_tuple=lambda: (x, y, z))


class TestBuildSkeletonHierarchy:
    """Tests for build_skeleton_hierarchy function."""

    def test_single_bone(self):
        bones = [
            (0, -1, _make_grove_vector(0, 0, 0), _make_grove_vector(0, 0, 1), 0.1),
        ]
        skel = build_skeleton_hierarchy(bones)
        assert skel.joint_names[0] == "root"
        assert skel.joint_names[1] == "joint_1"
        assert skel.joint_parents[0] == -1
        assert skel.joint_parents[1] == 0

    def test_two_bone_chain(self):
        bones = [
            (0, -1, _make_grove_vector(0, 0, 0), _make_grove_vector(0, 0, 1), 0.1),
            (1, 0, _make_grove_vector(0, 0, 1), _make_grove_vector(0, 0, 2), 0.05),
        ]
        skel = build_skeleton_hierarchy(bones)
        assert len(skel.joint_names) == 3  # root + 2 joints
        assert skel.joint_parents[2] == 1  # second bone parents to first

    def test_branching_skeleton(self):
        bones = [
            (0, -1, _make_grove_vector(0, 0, 0), _make_grove_vector(0, 0, 2), 0.2),
            (1, 0, _make_grove_vector(0, 0, 2), _make_grove_vector(1, 0, 3), 0.1),
            (2, 0, _make_grove_vector(0, 0, 2), _make_grove_vector(-1, 0, 3), 0.1),
        ]
        skel = build_skeleton_hierarchy(bones)
        assert len(skel.joint_names) == 4
        # Both branches should parent to the trunk joint
        assert skel.joint_parents[2] == 1
        assert skel.joint_parents[3] == 1

    def test_bone_to_joint_map_populated(self):
        bones = [
            (0, -1, _make_grove_vector(0, 0, 0), _make_grove_vector(0, 0, 1), 0.1),
        ]
        skel = build_skeleton_hierarchy(bones)
        assert 0 in skel.bone_to_joint_map
        assert skel.bone_to_joint_map[0] == 1

    def test_zero_length_bone_gets_identity_rotation(self):
        bones = [
            (0, -1, _make_grove_vector(0, 0, 0), _make_grove_vector(0, 0, 0), 0.1),
        ]
        skel = build_skeleton_hierarchy(bones)
        # Zero-length bone should have identity rotation
        transform = skel.bind_transforms[1]
        assert transform.is_identity_rotation()

    def test_empty_bones_returns_root_only(self):
        skel = build_skeleton_hierarchy([])
        assert skel.joint_names == ["root"]
        assert skel.joint_parents == [-1]


class TestFilterBonesForMesh:
    """Tests for filter_bones_for_mesh function."""

    def _make_model(self, bone_ids):
        """Create a mock model with point_attribute_bone_id."""
        return SimpleNamespace(point_attribute_bone_id=bone_ids)

    def _make_bone(self, parent_id=0, is_root=False, is_branch_root=False, branch_id=0):
        """Create a bone tuple matching Grove format."""
        return (
            is_root,      # is_tree_root
            parent_id,    # parent_bone_id
            (0, 0, 0),   # start_point
            (0, 0, 1),   # end_point
            0.1,          # radius
            1.0,          # mass
            is_branch_root,  # is_branch_root
            branch_id,   # branch_id
        )

    def test_all_bones_referenced(self):
        bones = [self._make_bone(parent_id=-1, is_root=True), self._make_bone(parent_id=0)]
        model = self._make_model([0, 1])
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        assert len(filtered) == 2

    def test_unreferenced_bones_removed(self):
        bones = [
            self._make_bone(parent_id=-1, is_root=True),
            self._make_bone(parent_id=0),
            self._make_bone(parent_id=1),  # bone idx 2: not referenced by any vertex
        ]
        model = self._make_model([0, 1])
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        assert len(filtered) == 2
        assert 2 not in bone_map

    def test_root_always_included(self):
        bones = [self._make_bone(parent_id=-1, is_root=True), self._make_bone(parent_id=0)]
        model = self._make_model([1])  # only references bone 1
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        assert 0 in bone_map  # root must be present

    def test_parent_chain_included(self):
        bones = [
            self._make_bone(parent_id=-1, is_root=True),
            self._make_bone(parent_id=0),
            self._make_bone(parent_id=1),
        ]
        model = self._make_model([2])  # only references leaf bone
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        # All three bones should be kept (root + parent chain to referenced bone)
        assert len(filtered) == 3

    def test_no_bone_id_attribute_returns_original(self):
        model = SimpleNamespace()  # no point_attribute_bone_id
        bones = [self._make_bone(parent_id=-1, is_root=True)]
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        assert len(filtered) == 1

    def test_bone_map_remaps_ids_correctly(self):
        bones = [
            self._make_bone(parent_id=-1, is_root=True),
            self._make_bone(parent_id=0),
            self._make_bone(parent_id=0),  # bone 2: not referenced
            self._make_bone(parent_id=0),  # bone 3: referenced
        ]
        model = self._make_model([0, 1, 3])
        filtered, bone_map = filter_bones_for_mesh(model, bones)
        # bone 3 should be remapped to a lower index
        assert bone_map[3] < 4


class TestDistanceAndFalloff:
    """Tests for _distance_3d and _apply_falloff helpers."""

    def test_distance_same_point(self):
        assert _distance_3d((0, 0, 0), (0, 0, 0)) == 0.0

    def test_distance_unit(self):
        assert _distance_3d((0, 0, 0), (1, 0, 0)) == pytest.approx(1.0)

    def test_distance_3d(self):
        assert _distance_3d((1, 2, 3), (4, 6, 3)) == pytest.approx(5.0)

    def test_falloff_linear_zero(self):
        assert _apply_falloff(0.0, "linear") == pytest.approx(0.0)

    def test_falloff_linear_one(self):
        assert _apply_falloff(1.0, "linear") == pytest.approx(1.0)

    def test_falloff_linear_mid(self):
        assert _apply_falloff(0.5, "linear") == pytest.approx(0.5)

    def test_falloff_smooth_endpoints(self):
        assert _apply_falloff(0.0, "smooth") == pytest.approx(0.0)
        assert _apply_falloff(1.0, "smooth") == pytest.approx(1.0)

    def test_falloff_smooth_midpoint(self):
        # Smoothstep at 0.5: 0.5^2 * (3 - 2*0.5) = 0.25 * 2 = 0.5
        assert _apply_falloff(0.5, "smooth") == pytest.approx(0.5)

    def test_falloff_cosine_endpoints(self):
        assert _apply_falloff(0.0, "cosine") == pytest.approx(0.0)
        assert _apply_falloff(1.0, "cosine") == pytest.approx(1.0)

    def test_falloff_cosine_midpoint(self):
        assert _apply_falloff(0.5, "cosine") == pytest.approx(0.5)

    def test_falloff_smooth_monotonic(self):
        prev = 0.0
        for i in range(1, 11):
            t = i / 10.0
            val = _apply_falloff(t, "smooth")
            assert val >= prev
            prev = val
