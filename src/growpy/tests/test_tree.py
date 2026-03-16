"""Tests for growpy.core.tree module."""

from types import SimpleNamespace

import pytest

from growpy.core.tree import (
    calculate_dbh_at_height,
    calculate_tree_height,
    find_max_height_in_branch,
)


def _make_node(z, radius=0.1, side_branches=None):
    """Create a mock tree node with position and radius."""
    return SimpleNamespace(
        pos=SimpleNamespace(z=z, x=0.0, y=0.0),
        radius=radius,
        side_branches=side_branches or [],
    )


def _make_branch(nodes):
    """Create a mock branch with nodes."""
    return SimpleNamespace(nodes=nodes)


class TestFindMaxHeightInBranch:
    """Tests for recursive branch height finding."""

    def test_single_node(self):
        branch = _make_branch([_make_node(5.0)])
        assert find_max_height_in_branch(branch) == pytest.approx(5.0)

    def test_multiple_nodes_returns_max(self):
        branch = _make_branch([_make_node(1.0), _make_node(3.0), _make_node(2.0)])
        assert find_max_height_in_branch(branch) == pytest.approx(3.0)

    def test_side_branches_included(self):
        side = _make_branch([_make_node(10.0)])
        trunk_node = _make_node(5.0, side_branches=[side])
        branch = _make_branch([trunk_node])
        assert find_max_height_in_branch(branch) == pytest.approx(10.0)

    def test_nested_side_branches(self):
        deepest = _make_branch([_make_node(20.0)])
        mid_node = _make_node(8.0, side_branches=[deepest])
        mid = _make_branch([mid_node])
        trunk_node = _make_node(5.0, side_branches=[mid])
        branch = _make_branch([trunk_node])
        assert find_max_height_in_branch(branch) == pytest.approx(20.0)

    def test_empty_branch(self):
        branch = _make_branch([])
        assert find_max_height_in_branch(branch) == 0.0

    def test_branch_without_nodes_attribute(self):
        branch = SimpleNamespace()
        assert find_max_height_in_branch(branch) == 0.0

    def test_trunk_taller_than_side_branches(self):
        side = _make_branch([_make_node(3.0)])
        trunk_node = _make_node(15.0, side_branches=[side])
        branch = _make_branch([trunk_node])
        assert find_max_height_in_branch(branch) == pytest.approx(15.0)


class TestCalculateTreeHeight:
    """Tests for calculate_tree_height (wrapper around find_max_height_in_branch)."""

    def test_simple_tree(self):
        tree = _make_branch([_make_node(1.0), _make_node(5.0), _make_node(3.0)])
        assert calculate_tree_height(tree) == pytest.approx(5.0)

    def test_tree_with_zero_height(self):
        tree = _make_branch([_make_node(0.0)])
        assert calculate_tree_height(tree) == 0.0


class TestCalculateDbhAtHeight:
    """Tests for diameter at breast height calculation."""

    def test_exact_height_match(self):
        tree = _make_branch([
            _make_node(0.0, radius=0.2),
            _make_node(1.3, radius=0.1),
            _make_node(5.0, radius=0.02),
        ])
        dbh = calculate_dbh_at_height(tree, target_height=1.3)
        assert dbh == pytest.approx(0.2)  # radius * 2

    def test_interpolation_between_nodes(self):
        tree = _make_branch([
            _make_node(0.0, radius=0.2),
            _make_node(1.0, radius=0.15),
            _make_node(2.0, radius=0.10),
        ])
        dbh = calculate_dbh_at_height(tree, target_height=1.5)
        # Interpolation: radius at 1.0 = 0.15, at 2.0 = 0.10
        # At 1.5: 0.15 + 0.5 * (0.10 - 0.15) = 0.125
        assert dbh == pytest.approx(0.25)  # 0.125 * 2

    def test_tree_shorter_than_target(self):
        tree = _make_branch([_make_node(0.0, radius=0.1), _make_node(1.0, radius=0.05)])
        dbh = calculate_dbh_at_height(tree, target_height=1.3)
        assert dbh == 0.0

    def test_no_nodes(self):
        tree = _make_branch([])
        assert calculate_dbh_at_height(tree) == 0.0

    def test_no_nodes_attribute(self):
        tree = SimpleNamespace()
        assert calculate_dbh_at_height(tree) == 0.0

    def test_default_target_height_is_1_3(self):
        tree = _make_branch([
            _make_node(0.0, radius=0.2),
            _make_node(1.0, radius=0.15),
            _make_node(2.0, radius=0.10),
        ])
        dbh = calculate_dbh_at_height(tree)
        # Should use 1.3m as default
        expected_radius = 0.15 + 0.3 * (0.10 - 0.15)
        assert dbh == pytest.approx(expected_radius * 2)

    def test_node_near_target_within_tolerance(self):
        # Single node at 1.24 with target 1.3: max_height < target, returns 0.0
        # Tolerance check only applies when no node below AND first node is near target
        tree = _make_branch([_make_node(1.24, radius=0.1)])
        dbh = calculate_dbh_at_height(tree, target_height=1.3)
        assert dbh == 0.0  # max_height < target_height -> returns 0.0

    def test_tolerance_check_no_node_below(self):
        # Only node at 1.25 (>= 1.3*0.95=1.235), no node below target
        # But we need max_height >= target for the function to proceed
        tree = _make_branch([_make_node(1.25, radius=0.1), _make_node(2.0, radius=0.05)])
        dbh = calculate_dbh_at_height(tree, target_height=1.3)
        # node_below=node at 1.25, node_above=node at 2.0, interpolation
        assert dbh > 0

    def test_only_node_above_target(self):
        # Single node at 5.0 with target 1.3: max_height >= target, node_below=None
        # First node at 5.0 >= 1.3*0.95=1.235, so tolerance check returns radius*2
        tree = _make_branch([_make_node(5.0, radius=0.1)])
        dbh = calculate_dbh_at_height(tree, target_height=1.3)
        assert dbh == pytest.approx(0.2)
