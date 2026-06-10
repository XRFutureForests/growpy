"""Tests for growpy.io.wind_json module."""


from growpy.io.unreal.wind_json import (
    _classify_by_hierarchy_depth,
    _classify_joint,
    extract_joint_names_from_bones_info,
)


class TestExtractJointNamesFromBonesInfo:
    """Tests for extracting joint names from bone tuples."""

    def _make_bone(self, is_tree_root=False, parent_id=0, branch_id=0, is_branch_root=False):
        return (
            is_tree_root,
            parent_id,
            (0, 0, 0),  # start_point
            (0, 0, 1),  # end_point
            0.1,         # radius
            1.0,         # mass
            is_branch_root,
            branch_id,
        )

    def test_empty_bones_info(self):
        assert extract_joint_names_from_bones_info([]) == []

    def test_single_root_bone(self):
        bones = [self._make_bone(is_tree_root=True, parent_id=0, branch_id=0)]
        result = extract_joint_names_from_bones_info(bones)
        assert len(result) == 1
        assert result[0] == "tree_root"

    def test_root_plus_joint(self):
        bones = [
            self._make_bone(is_tree_root=True, parent_id=0, branch_id=0),
            self._make_bone(is_tree_root=False, parent_id=0, branch_id=0),
        ]
        result = extract_joint_names_from_bones_info(bones)
        assert len(result) == 2
        assert result[0] == "tree_root"
        assert "joint_" in result[1]

    def test_branch_root_creates_branch_name(self):
        bones = [
            self._make_bone(is_tree_root=True, parent_id=0, branch_id=0),
            self._make_bone(is_tree_root=False, parent_id=0, branch_id=1, is_branch_root=True),
        ]
        result = extract_joint_names_from_bones_info(bones)
        assert len(result) == 2
        assert "branch_" in result[1]

    def test_hierarchical_paths_include_parents(self):
        bones = [
            self._make_bone(is_tree_root=True, parent_id=0, branch_id=0),
            self._make_bone(is_tree_root=False, parent_id=0, branch_id=0),
            self._make_bone(is_tree_root=False, parent_id=0, branch_id=1, is_branch_root=True),
        ]
        result = extract_joint_names_from_bones_info(bones)
        # Branch path should include parent joint path
        assert "tree_root" in result[2]


class TestClassifyByHierarchyDepth:
    """Tests for joint classification by path depth."""

    def test_trunk_joint(self):
        assert _classify_by_hierarchy_depth("tree_root") == 0
        assert _classify_by_hierarchy_depth("tree_root/joint_1") == 0

    def test_primary_branch(self):
        assert _classify_by_hierarchy_depth("tree_root/branch_0") == 1
        assert _classify_by_hierarchy_depth("tree_root/joint_1/branch_0") == 1

    def test_secondary_branch(self):
        assert _classify_by_hierarchy_depth("tree_root/branch_0/branch_1") == 2
        assert _classify_by_hierarchy_depth("tree_root/branch_0/joint_1/branch_1") == 2

    def test_deep_nesting(self):
        path = "tree_root/branch_0/branch_1/branch_2"
        assert _classify_by_hierarchy_depth(path) == 2  # capped at 2


class TestClassifyJoint:
    """Tests for joint classification with skeleton attributes."""

    def test_no_skeleton_attrs_uses_hierarchy_fallback(self):
        result = _classify_joint("tree_root", 0, skeleton_attrs=None)
        assert result == 0  # trunk

    def test_no_skeleton_attrs_branch_depth(self):
        result = _classify_joint("tree_root/branch_0", 0, skeleton_attrs=None)
        assert result == 1  # primary

    def test_with_skeleton_attrs_max_age_is_trunk(self):
        attrs = {"age": [10, 10, 5, 2, 1]}
        result = _classify_joint("tree_root", 0, skeleton_attrs=attrs)
        assert result == 0  # max age -> trunk

    def test_with_skeleton_attrs_mid_age_is_primary(self):
        attrs = {"age": [10, 10, 6, 2, 1]}
        result = _classify_joint("branch_0", 2, skeleton_attrs=attrs)
        assert result == 1  # 6 >= 10 * 0.5 -> primary

    def test_with_skeleton_attrs_low_age_is_tips(self):
        attrs = {"age": [10, 10, 5, 2, 1]}
        result = _classify_joint("branch_1", 4, skeleton_attrs=attrs)
        assert result == 2  # age 1 < 10 * 0.5 -> tips

    def test_index_out_of_range_uses_fallback(self):
        attrs = {"age": [10]}  # only 1 entry
        result = _classify_joint("tree_root/branch_0", 5, skeleton_attrs=attrs)
        assert result == 1  # fallback to hierarchy depth
