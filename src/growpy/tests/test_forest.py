"""Tests for growpy.core.forest pure-logic functions."""

import pytest

try:
    import the_grove_23_core as _gc

    from growpy.core.forest import _compute_grove_offsets, _split_bones_by_tree
    from growpy.core.grove import enable_surround

    _IMPORT_OK = True
except (ImportError, OSError):
    _IMPORT_OK = False
    _gc = None
    _split_bones_by_tree = None
    _compute_grove_offsets = None
    enable_surround = None

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


class TestComputeGroveOffsets:
    """Tests for _compute_grove_offsets."""

    def _grove_entry(self, species_name, tree_count):
        """Create a minimal forest entry tuple: (grove, species_name, tree_count, fids)."""
        return (None, species_name, tree_count, [])

    def test_single_grove(self):
        forest = [self._grove_entry("spruce", 5)]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0]

    def test_different_species(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("beech", 4),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 0]

    def test_same_species_multiple_groves(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("spruce", 4),
            self._grove_entry("spruce", 2),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 3, 7]

    def test_mixed_species(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("beech", 2),
            self._grove_entry("spruce", 4),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 0, 3]

    def test_empty_forest(self):
        assert _compute_grove_offsets([]) == []



class TestEnableSurround:
    """Tests for enabling Grove's Surround shell on a grove."""

    def test_sets_surround_properties(self):
        grove = _gc.Grove()
        grove.clear_trees()
        applied = enable_surround(
            grove, density=0.6, distance=10.0, height=5.0, grow=True
        )
        assert applied is True
        props = grove.get_properties()
        assert props.surround_enabled is True
        assert props.surround_density == pytest.approx(0.6)
        assert props.surround_distance == pytest.approx(10.0)
        assert props.surround_height == pytest.approx(5.0)
        assert props.surround_grow is True

    def test_surround_reduces_branch_count(self):
        # A tree grown with Surround competes for light and self-prunes, so it
        # should end up with fewer branches than the same tree grown open.
        def grow(surround):
            g = _gc.Grove()
            g.clear_trees()
            g.set_random_seed(42)
            if surround:
                enable_surround(g, density=0.7, distance=7.0, height=5.0, grow=True)
            g.add_new_tree(_gc.Vector(0, 0, 0), _gc.Vector(0, 0, 1), 0)
            for _ in range(12):
                g.weigh_and_bend()
                g.simulate(1)
            return g.number_of_branches

        assert grow(surround=True) < grow(surround=False)
