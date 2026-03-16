"""Tests for growpy.io.pve_hierarchy_builder module."""

from types import SimpleNamespace

import pytest

from growpy.io.pve_hierarchy_builder import (
    _derive_parents_from_skeleton,
    build_hierarchy_arrays,
    get_branch_generation,
)


def _make_skeleton(poly_lines):
    """Create a mock skeleton with poly_lines attribute."""
    return SimpleNamespace(poly_lines=poly_lines)


class TestDeriveParentsFromSkeleton:
    """Tests for parent derivation from skeleton poly_lines."""

    def test_empty_poly_lines(self):
        skel = _make_skeleton([])
        assert _derive_parents_from_skeleton(skel) == []

    def test_single_branch_is_root(self):
        skel = _make_skeleton([[0, 1, 2, 3]])
        parents = _derive_parents_from_skeleton(skel)
        assert parents == [-1]

    def test_child_branch_connects_to_parent(self):
        # Branch 0: points 0->1->2->3
        # Branch 1: starts at point 2 (mid-way on branch 0)
        skel = _make_skeleton([[0, 1, 2, 3], [2, 4, 5]])
        parents = _derive_parents_from_skeleton(skel)
        assert parents[0] == -1  # root
        assert parents[1] == 0   # child of branch 0

    def test_two_children_from_same_parent(self):
        skel = _make_skeleton([
            [0, 1, 2, 3],  # trunk
            [2, 4, 5],      # branch from point 2
            [1, 6, 7],      # branch from point 1
        ])
        parents = _derive_parents_from_skeleton(skel)
        assert parents[0] == -1
        assert parents[1] == 0
        assert parents[2] == 0

    def test_grandchild_branch(self):
        skel = _make_skeleton([
            [0, 1, 2, 3],   # trunk
            [2, 4, 5, 6],   # primary branch from trunk point 2
            [5, 7, 8],      # secondary branch from primary branch point 5
        ])
        parents = _derive_parents_from_skeleton(skel)
        assert parents[0] == -1  # root
        assert parents[1] == 0   # child of trunk
        assert parents[2] == 1   # child of primary branch

    def test_empty_poly_line_returns_no_parent(self):
        skel = _make_skeleton([[]])
        parents = _derive_parents_from_skeleton(skel)
        assert parents == [-1]


class TestBuildHierarchyArrays:
    """Tests for building PVE parent/children arrays."""

    def test_no_skeleton_returns_self_referencing(self):
        result = build_hierarchy_arrays(model=None, num_branches=3, skeleton=None)
        parents = result["parents"]["values"]
        children = result["children"]["values"]
        assert parents == [[0], [1], [2]]
        assert all(c == [] for c in children)

    def test_simple_hierarchy(self):
        skel = _make_skeleton([
            [0, 1, 2, 3],
            [2, 4, 5],
        ])
        result = build_hierarchy_arrays(model=None, num_branches=2, skeleton=skel)
        parents = result["parents"]["values"]
        children = result["children"]["values"]
        # Branch 0 is root: parents = [0] (self-reference)
        assert parents[0] == [0]
        # Branch 1 parents to branch 0
        assert 0 in parents[1]
        # Branch 0 should have branch 1 as child
        assert 1 in children[0]

    def test_output_structure(self):
        skel = _make_skeleton([[0, 1, 2]])
        result = build_hierarchy_arrays(model=None, num_branches=1, skeleton=skel)
        assert result["parents"]["isArray"] is True
        assert result["parents"]["type"] == "int"
        assert result["children"]["isArray"] is True
        assert result["children"]["type"] == "int"


class TestGetBranchGeneration:
    """Tests for branch generation calculation."""

    def test_no_skeleton_returns_all_zeros(self):
        result = get_branch_generation(model=None, num_branches=5, skeleton=None)
        assert result == [0, 0, 0, 0, 0]

    def test_single_branch_is_generation_0(self):
        skel = _make_skeleton([[0, 1, 2, 3]])
        result = get_branch_generation(model=None, num_branches=1, skeleton=skel)
        assert result == [0]

    def test_child_branch_is_generation_1(self):
        skel = _make_skeleton([
            [0, 1, 2, 3],   # trunk: gen 0
            [2, 4, 5],      # primary: gen 1
        ])
        result = get_branch_generation(model=None, num_branches=2, skeleton=skel)
        assert result[0] == 0
        assert result[1] == 1

    def test_grandchild_is_generation_2(self):
        skel = _make_skeleton([
            [0, 1, 2, 3],
            [2, 4, 5, 6],
            [5, 7, 8],
        ])
        result = get_branch_generation(model=None, num_branches=3, skeleton=skel)
        assert result[0] == 0
        assert result[1] == 1
        assert result[2] == 2

    def test_num_branches_larger_than_poly_lines(self):
        skel = _make_skeleton([[0, 1, 2]])
        result = get_branch_generation(model=None, num_branches=3, skeleton=skel)
        assert len(result) == 3
        assert result[0] == 0
