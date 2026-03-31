"""Tests for growpy.core.forest pure-logic functions.

Only covers _split_bones_by_tree which is pure logic. Other forest
functions require The Grove API and are not unit-tested.

Uses try/except import to gracefully skip if Grove is unavailable.
"""

import pytest

try:
    from growpy.core.forest import _split_bones_by_tree

    _IMPORT_OK = True
except (ImportError, OSError):
    _IMPORT_OK = False
    _split_bones_by_tree = None

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="growpy.core.forest requires The Grove API",
)


class TestSplitBonesByTree:
    """Tests for splitting combined bone list into per-tree lists."""

    def _bone(self, is_root, parent_id=0):
        """Create a minimal bone tuple: (is_tree_root, parent_id, ...)."""
        return (is_root, parent_id, (0, 0, 0), (0, 1, 0), 0.1, 1.0, False, 0)

    def test_single_tree(self):
        bones = [self._bone(True), self._bone(False), self._bone(False)]
        result = _split_bones_by_tree(bones, 1)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_two_trees(self):
        bones = [
            self._bone(True), self._bone(False),  # tree 1
            self._bone(True), self._bone(False), self._bone(False),  # tree 2
        ]
        result = _split_bones_by_tree(bones, 2)
        assert len(result) == 2
        assert len(result[0]) == 2
        assert len(result[1]) == 3

    def test_three_trees_different_sizes(self):
        bones = [
            self._bone(True),  # tree 1: 1 bone
            self._bone(True), self._bone(False), self._bone(False),  # tree 2: 3
            self._bone(True), self._bone(False),  # tree 3: 2
        ]
        result = _split_bones_by_tree(bones, 3)
        assert len(result) == 3
        assert len(result[0]) == 1
        assert len(result[1]) == 3
        assert len(result[2]) == 2

    def test_empty_bones(self):
        result = _split_bones_by_tree([], 3)
        assert len(result) == 3
        assert all(b == [] for b in result)

    def test_zero_trees(self):
        result = _split_bones_by_tree([], 0)
        assert result == []

    def test_fewer_trees_than_expected_pads(self):
        bones = [self._bone(True), self._bone(False)]
        result = _split_bones_by_tree(bones, 3)
        assert len(result) >= 1
        assert len(result[0]) == 2
