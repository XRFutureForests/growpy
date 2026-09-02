"""Tests for the compound-part harvester's cut and clustering (XRFF-357).

These cover the pure branch-walking half of the tool. Growing a reference tree
needs `the_grove_23_core`, so the fixtures here build `BranchRecord` lists by
hand rather than simulating.
"""

import pytest

from growpy.tools.harvest_compound_parts import (
    DEFAULT_MAX_SPAN,
    DEFAULT_MAX_TIPS,
    BranchRecord,
    cluster_prototypes,
    find_cut_set_adaptive,
    precompute_subtrees,
    subtree_stats,
)


def _record(index, parent, base_radius, base_pos=(0.0, 0.0, 0.0), length=0.1):
    return BranchRecord(
        index=index,
        parent=parent,
        depth=0,
        base_radius=base_radius,
        tip_radius=base_radius * 0.5,
        length=length,
        base_pos=base_pos,
        base_dir=(0.0, 0.0, 1.0),
        node_count=2,
    )


def _link(records):
    """Populate children from the parent field, as flatten_branches does."""
    for record in records:
        if record.parent >= 0:
            records[record.parent].children.append(record.index)
    return records


def _fan(child_count, trunk_radius=0.10, child_radius=0.005, spread=0.2):
    """A trunk with `child_count` thin children hanging off it."""
    records = [_record(0, -1, trunk_radius)]
    for i in range(child_count):
        records.append(
            _record(i + 1, 0, child_radius, base_pos=(spread * i, 0.0, 1.0))
        )
    return _link(records)


class TestFindCutSetAdaptive:
    def test_thin_children_below_the_cut_become_parts(self):
        records = _fan(4)
        metrics = precompute_subtrees(records)
        cut = find_cut_set_adaptive(records, metrics, 0.010)
        assert sorted(cut) == [1, 2, 3, 4]

    def test_the_trunk_is_never_a_part(self):
        # The root has no parent, so it can never be cut off the tree.
        records = _fan(3)
        metrics = precompute_subtrees(records)
        assert 0 not in find_cut_set_adaptive(records, metrics, 1.0)

    def test_no_branch_appears_in_two_parts(self):
        # A deep chain: whichever level is emitted, the ancestors of an emitted
        # part must not also be emitted, or its geometry is baked twice.
        records = [_record(0, -1, 0.10)]
        for i in range(1, 12):
            records.append(_record(i, i - 1, 0.004))
        _link(records)
        metrics = precompute_subtrees(records)
        cut = find_cut_set_adaptive(records, metrics, 0.010)

        def ancestors(idx):
            out = []
            current = records[idx].parent
            while current >= 0:
                out.append(current)
                current = records[current].parent
            return out

        chosen = set(cut)
        for idx in cut:
            assert not (chosen & set(ancestors(idx)))

    def test_a_childless_branch_is_emitted_even_when_it_breaks_the_band(self):
        # It cannot be subdivided further, so dropping it would lose foliage.
        records = _link([_record(0, -1, 0.10), _record(1, 0, 0.004, length=50.0)])
        metrics = precompute_subtrees(records)
        cut = find_cut_set_adaptive(records, metrics, 0.010, max_tips=0, max_span=0.0)
        assert cut == [1]

    def test_an_oversized_subtree_is_descended_into(self):
        # Trunk -> big limb (below the cut) -> two thin twiglets. With a band of
        # one tip, the limb does not fit, so its children become the parts and
        # its own axis stays in the base mesh.
        records = _link(
            [
                _record(0, -1, 0.10),
                _record(1, 0, 0.009),
                _record(2, 1, 0.004),
                _record(3, 1, 0.004),
            ]
        )
        metrics = precompute_subtrees(records)
        assert find_cut_set_adaptive(records, metrics, 0.010, max_tips=1) == [3, 2]

    def test_the_same_subtree_fits_when_the_band_allows_it(self):
        records = _link(
            [
                _record(0, -1, 0.10),
                _record(1, 0, 0.009),
                _record(2, 1, 0.004),
                _record(3, 1, 0.004),
            ]
        )
        metrics = precompute_subtrees(records)
        assert find_cut_set_adaptive(records, metrics, 0.010, max_tips=5) == [1]

    def test_the_span_bound_is_respected(self):
        records = _link(
            [
                _record(0, -1, 0.10),
                _record(1, 0, 0.009, base_pos=(0.0, 0.0, 0.0)),
                _record(2, 1, 0.004, base_pos=(0.0, 0.0, 0.0)),
                _record(3, 1, 0.004, base_pos=(10.0, 0.0, 0.0)),
            ]
        )
        metrics = precompute_subtrees(records)
        assert metrics["span"][1] > 5.0
        assert find_cut_set_adaptive(records, metrics, 0.010, max_span=1.0) == [3, 2]

    def test_the_twig_bound_splits_a_subtree_the_tip_bound_would_accept(self):
        # The bound that actually decides a part's face count: every twig is a
        # whole twig asset welded in.
        records = _link(
            [
                _record(0, -1, 0.10),
                _record(1, 0, 0.009),
                _record(2, 1, 0.004),
                _record(3, 1, 0.004),
            ]
        )
        metrics = precompute_subtrees(records)
        # Subtree 1 carries 200 twigs across two 100-twig children. tips (2) and
        # span both sit well inside their bands, so only the twig bound moves.
        twigs = [200, 200, 100, 100]
        assert find_cut_set_adaptive(
            records, metrics, 0.010, twig_totals=twigs, max_twigs=250
        ) == [1]
        assert find_cut_set_adaptive(
            records, metrics, 0.010, twig_totals=twigs, max_twigs=150
        ) == [3, 2]

    def test_the_twig_bound_is_inert_when_no_totals_are_given(self):
        # The sizing sweeps run without a built model, so the bound must not
        # fire on its default when twig_totals is None.
        records = _fan(3)
        metrics = precompute_subtrees(records)
        assert find_cut_set_adaptive(
            records, metrics, 0.010, DEFAULT_MAX_TIPS, DEFAULT_MAX_SPAN, None, 0
        ) == [3, 2, 1]

    def test_every_cut_branch_is_below_the_cut_radius(self):
        records = _fan(6, child_radius=0.004)
        metrics = precompute_subtrees(records)
        for idx in find_cut_set_adaptive(records, metrics, 0.010):
            assert records[idx].base_radius < 0.010


class TestClusterPrototypes:
    def _cut_and_metrics(self):
        records = _fan(40, child_radius=0.004, spread=0.05)
        # Give the candidates different shapes so clustering has something to do.
        for i, record in enumerate(records[1:], start=1):
            record.length = 0.05 * (i % 7 + 1)
        metrics = precompute_subtrees(records)
        cut = find_cut_set_adaptive(records, metrics, 0.010)
        return records, metrics, cut

    def test_is_deterministic_for_a_fixed_seed(self):
        records, metrics, cut = self._cut_and_metrics()
        first = cluster_prototypes(records, metrics, cut, 5, seed=42)
        second = cluster_prototypes(records, metrics, cut, 5, seed=42)
        assert first[0] == second[0]
        assert first[1] == second[1]

    def test_returns_at_most_k_medoids(self):
        records, metrics, cut = self._cut_and_metrics()
        medoids, _, _ = cluster_prototypes(records, metrics, cut, 5, seed=42)
        assert len(medoids) <= 5

    def test_every_medoid_is_a_real_candidate(self):
        # Medoids, not centroids: a prototype has to be an actual harvestable
        # subtree, not an average of several.
        records, metrics, cut = self._cut_and_metrics()
        medoids, _, _ = cluster_prototypes(records, metrics, cut, 5, seed=42)
        assert set(medoids) <= set(cut)

    def test_every_candidate_is_assigned_to_a_medoid(self):
        records, metrics, cut = self._cut_and_metrics()
        medoids, assignment, stats = cluster_prototypes(
            records, metrics, cut, 5, seed=42
        )
        assert len(assignment) == len(cut) == len(stats)
        assert all(0 <= a < len(medoids) for a in assignment)

    def test_k_is_clamped_to_the_candidate_count(self):
        records, metrics, cut = self._cut_and_metrics()
        medoids, _, _ = cluster_prototypes(records, metrics, cut, len(cut) + 10, seed=1)
        assert len(medoids) <= len(cut)

    @pytest.mark.parametrize("seed", [1, 7, 99])
    def test_different_seeds_still_produce_valid_output(self, seed):
        records, metrics, cut = self._cut_and_metrics()
        medoids, assignment, _ = cluster_prototypes(records, metrics, cut, 4, seed=seed)
        assert set(medoids) <= set(cut)
        assert all(0 <= a < len(medoids) for a in assignment)


class TestSubtreeStats:
    def test_reports_the_descriptors_clustering_uses(self):
        records = _fan(3)
        metrics = precompute_subtrees(records)
        stats = subtree_stats(records, metrics, 0)
        for key in (
            "branches",
            "tips",
            "total_length",
            "span",
            "base_radius",
            "up_alignment",
            "height",
        ):
            assert key in stats

    def test_a_leaf_branch_counts_as_one_tip(self):
        records = _fan(3)
        metrics = precompute_subtrees(records)
        assert subtree_stats(records, metrics, 1)["tips"] == 1
        assert subtree_stats(records, metrics, 0)["tips"] == 3


class TestSeedingTerminates:
    """k-means++ seeding used to spin forever on a degenerate candidate set.

    A crown's cut set is dominated by near-identical single-tip stubs -- 60% of
    a 25-cycle beech's candidates at cut diameter 0.030 -- so asking for more
    prototypes than there are distinct shapes is the normal case, not an edge
    case. With every weight zero, no index satisfied `acc >= pick` and the tool
    hung with no output. Measured before the fix: 3 distinct shapes and k=5 ran
    past 200,000 iterations without terminating.
    """

    def _identical_candidates(self, count, distinct_shapes):
        records = [_record(0, -1, 0.10)]
        for i in range(count):
            records.append(_record(i + 1, 0, 0.004))
        _link(records)
        for i, record in enumerate(records[1:]):
            record.length = 0.1 * (i % distinct_shapes)
        metrics = precompute_subtrees(records)
        cut = find_cut_set_adaptive(records, metrics, 0.010)
        return records, metrics, cut

    @pytest.mark.parametrize("k", [1, 2, 4, 8, 40])
    def test_terminates_with_fewer_distinct_shapes_than_clusters(self, k):
        records, metrics, cut = self._identical_candidates(30, distinct_shapes=3)
        medoids, assignment, _ = cluster_prototypes(records, metrics, cut, k, seed=42)
        assert 1 <= len(medoids) <= k
        assert all(0 <= a < len(medoids) for a in assignment)

    def test_terminates_when_every_candidate_is_identical(self):
        records, metrics, cut = self._identical_candidates(20, distinct_shapes=1)
        medoids, assignment, _ = cluster_prototypes(records, metrics, cut, 7, seed=42)
        # One distinct shape means one useful prototype; returning it is honest.
        assert len(medoids) == 1
        assert set(assignment) == {0}

    def test_still_finds_every_distinct_shape_when_it_can(self):
        records, metrics, cut = self._identical_candidates(30, distinct_shapes=5)
        medoids, _, _ = cluster_prototypes(records, metrics, cut, 5, seed=42)
        assert len(medoids) == 5
