"""Tests for seeding budDirection[1] (Axillary) from Grove's twig frames.

PVE reads Axillary from each BRANCH's FIRST point and derives the roll of every
twig on that branch from it.

NOTE the original justification for this feature was RETRACTED: it was written
believing Axillary was usually zero, so PVE fell back to an arbitrary
perpendicular. Measured on real exports, branch-first-point coverage was already
99.4-99.9 % and never near-degenerate, so that fallback was not being hit. What
this actually changes is the SOURCE of the seed -- Grove's twig phase instead of
the sibling branch's heading at the fork. See ``assign_axillary_from_twigs``.

These tests therefore pin the transform's behaviour, not a bug fix.
"""

import math

from growpy.io.unreal.pve_skeleton_calculators import (
    _nearest_point_indices,
    assign_axillary_from_twigs,
    calculate_bud_directions,
)


class FakeSkeleton:
    def __init__(self, points, poly_lines):
        self.points = points
        self.poly_lines = poly_lines


def _straight_branch_up(n=4, spacing=1.0):
    """A single branch running along +Z, so its axis is unambiguous."""
    points = [(0.0, 0.0, i * spacing) for i in range(n)]
    return FakeSkeleton(points, [list(range(n))])


def _axillary(bud_directions, point_index):
    row = bud_directions[point_index]
    return (row[3], row[4], row[5])


def _norm(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


class TestNearestPointIndices:
    def test_empty_inputs_return_empty(self):
        assert _nearest_point_indices([], [(0.0, 0.0, 0.0)]) == []
        assert _nearest_point_indices([(0.0, 0.0, 0.0)], []) == []

    def test_picks_the_actual_nearest(self):
        points = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
        got = _nearest_point_indices(points, [(9.6, 0.0, 0.0), (0.2, 0.0, 0.0)])
        assert got == [1, 0]

    def test_finds_a_point_far_outside_the_grid(self):
        """A target beyond the search rings still resolves, via the full scan."""
        points = [(0.0, 0.0, float(i)) for i in range(5)]
        got = _nearest_point_indices(points, [(0.0, 0.0, 10_000.0)])
        assert got == [4]


class TestAssignAxillaryFromTwigs:
    def test_no_twigs_leaves_bud_directions_untouched(self):
        sk = _straight_branch_up()
        bud = calculate_bud_directions(sk)
        before = [list(r) for r in bud]
        stats = assign_axillary_from_twigs(sk, bud, [], [])
        assert bud == before
        assert stats["seeded"] == 0

    def test_mismatched_input_lengths_raise(self):
        sk = _straight_branch_up()
        bud = calculate_bud_directions(sk)
        try:
            assign_axillary_from_twigs(sk, bud, [(0.0, 0.0, 0.0)], [])
        except ValueError as err:
            assert "same length" in str(err)
        else:
            raise AssertionError("expected ValueError on mismatched lengths")

    def test_seeds_the_branch_from_its_twig(self):
        sk = _straight_branch_up()
        bud = calculate_bud_directions(sk)
        # One twig near the branch base, growing along +X.
        stats = assign_axillary_from_twigs(
            sk, bud, [(0.05, 0.0, 1.0)], [(1.0, 0.0, 0.0)]
        )
        assert stats["seeded"] == 1
        ax = _axillary(bud, 0)
        assert math.isclose(ax[0], 1.0, abs_tol=1e-6)
        assert math.isclose(_norm(ax), 1.0, abs_tol=1e-6)

    def test_seed_is_projected_perpendicular_to_the_branch_axis(self):
        """PVE crosses Axillary with Apical; a parallel seed makes that zero."""
        sk = _straight_branch_up()
        bud = calculate_bud_directions(sk)
        # Twig tilted 45 deg out of the horizontal, i.e. partly along the branch.
        d = 1.0 / math.sqrt(2.0)
        assign_axillary_from_twigs(sk, bud, [(0.0, 0.0, 1.0)], [(d, 0.0, d)])
        ax = _axillary(bud, 0)
        # The +Z (branch-axis) component must be gone, and it stays a unit vector.
        assert math.isclose(ax[2], 0.0, abs_tol=1e-6)
        assert math.isclose(_norm(ax), 1.0, abs_tol=1e-6)

    def test_seed_parallel_to_the_axis_is_rejected_not_written(self):
        sk = _straight_branch_up()
        bud = calculate_bud_directions(sk)
        stats = assign_axillary_from_twigs(
            sk, bud, [(0.0, 0.0, 1.0)], [(0.0, 0.0, 1.0)]
        )
        assert stats["degenerate"] == 1
        assert stats["seeded"] == 0
        assert _axillary(bud, 0) == (0.0, 0.0, 0.0)

    def test_every_point_of_the_branch_carries_the_seed(self):
        """Only index 0 is read by PVE, but writing all keeps it inspectable."""
        sk = _straight_branch_up(n=5)
        bud = calculate_bud_directions(sk)
        assign_axillary_from_twigs(sk, bud, [(0.05, 0.0, 0.0)], [(0.0, 1.0, 0.0)])
        for i in range(5):
            assert math.isclose(_axillary(bud, i)[1], 1.0, abs_tol=1e-6)

    def test_earliest_twig_wins_so_opposite_ranks_cannot_cancel(self):
        """A mean would cancel distichous ranks to zero; the first twig must win."""
        sk = _straight_branch_up(n=4)
        bud = calculate_bud_directions(sk)
        stats = assign_axillary_from_twigs(
            sk,
            bud,
            [(0.0, 0.0, 0.0), (0.0, 0.0, 2.0)],
            [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)],  # opposite ranks
        )
        assert stats["seeded"] == 1
        ax = _axillary(bud, 0)
        assert math.isclose(_norm(ax), 1.0, abs_tol=1e-6)
        assert math.isclose(ax[0], 1.0, abs_tol=1e-6)

    def test_branch_without_twigs_is_counted_and_left_zero(self):
        # Two disjoint branches; only the first gets a twig.
        points = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (50.0, 0.0, 0.0),
            (50.0, 0.0, 1.0),
        ]
        sk = FakeSkeleton(points, [[0, 1], [2, 3]])
        bud = calculate_bud_directions(sk)
        stats = assign_axillary_from_twigs(
            sk, bud, [(0.05, 0.0, 0.0)], [(0.0, 1.0, 0.0)]
        )
        assert stats["branches"] == 2
        assert stats["seeded"] == 1
        assert stats["no_twig"] == 1
        assert _axillary(bud, 2) == (0.0, 0.0, 0.0)


class TestGrowthDataIntegration:
    def test_exporter_seeds_axillary_when_twigs_are_supplied(self):
        from growpy.io.unreal.pve_growth_data_exporter import build_growth_data_json

        sk = _straight_branch_up(n=4)
        sk.point_attribute_radius = [0.1, 0.09, 0.08, 0.07]

        without = build_growth_data_json(sk)
        with_twigs = build_growth_data_json(
            sk,
            twig_positions=[(0.05, 0.0, 0.0)],
            twig_directions=[(0.0, 1.0, 0.0)],
        )

        a = without["points"]["attributes"]["budDirection"]["values"][0]
        b = with_twigs["points"]["attributes"]["budDirection"]["values"][0]

        # Axillary occupies floats 3..5 and is zero without twig data.
        assert a[3:6] == [0.0, 0.0, 0.0]
        assert b[3:6] != [0.0, 0.0, 0.0]
        # The exporter swaps Z-up to Y-up AFTER seeding, so a Grove +Y direction
        # must land in the JSON's third component, not its second.
        assert math.isclose(b[5], 1.0, abs_tol=1e-6)
        # Everything else is untouched.
        assert a[0:3] == b[0:3]
