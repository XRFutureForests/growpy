"""Tests for the per-radius crown floor (2026-09-21).

Two halves that must draw the same line: the skeleton prune keeps any branch
that reaches above it and drops what lies wholly under it, and the palette
gate makes the picker choose the mask below it and the twigs above it.
"""

from __future__ import annotations

import pytest

from growpy.config.pve_calibration import SpeciesCalibration
from growpy.io.unreal.pve_distributor_model import pick_candidates
from growpy.io.unreal.pve_graph_builder import PaletteEntry, masked_palette
from growpy.io.unreal.pve_graph_plan import crown_floor_gate
from growpy.io.unreal.pve_growth_data_exporter import (
    _attr,
    prune_subtrees_below_height,
)


def _tree(branches: list[list[list[float]]], parents: list[int]) -> dict:
    """A growth JSON from per-branch point lists (JSON y = up) and 1-based
    parent numbers (0 = trunk)."""
    positions: list[list[float]] = []
    branch_points: list[list[int]] = []
    for pts in branches:
        idx = list(range(len(positions), len(positions) + len(pts)))
        positions.extend(pts)
        branch_points.append(idx)
    n = len(branches)
    chains = []
    for b in range(n):
        chain, cur = [], parents[b]
        while cur:
            chain.append(cur)
            cur = parents[cur - 1]
        chains.append([0] + list(reversed(chain)))
    return {
        "points": {
            "positions": positions,
            "attributes": {
                "budNumber": _attr("int", 1, False, list(range(len(positions))))
            },
        },
        "primitives": {
            "points": branch_points,
            "attributes": {
                "parents": _attr("int", 1, True, chains),
                "children": _attr(
                    "int",
                    1,
                    True,
                    [
                        [c + 1 for c in range(n) if parents[c] == b + 1]
                        for b in range(n)
                    ],
                ),
                "branchNumber": _attr("int", 1, False, list(range(1, n + 1))),
                "branchSourceBudNumber": _attr("int", 1, False, [0] * n),
                "branchParentNumber": _attr("int", 1, False, parents),
                "branchHierarchyNumber": _attr(
                    "int", 1, False, [len(c) for c in chains]
                ),
                "plantNumber": _attr("int", 1, False, [1] * n),
            },
        },
    }


class TestPruneSubtreesBelowHeight:
    def test_a_low_fork_that_carries_the_crown_survives_its_low_attachment(self):
        # trunk 0-20 m; fork attached at 2 m reaching 18 m (the beech case);
        # stub attached at 3 m topping out at 5 m; twig on the fork at 15 m.
        data = _tree(
            [
                [[0, 0, 0], [0, 10, 0], [0, 20, 0]],
                [[0, 2, 0], [1, 10, 0], [2, 18, 0]],
                [[0, 3, 0], [1, 5, 0]],
                [[1, 10, 0], [2, 15, 0]],
            ],
            [0, 1, 1, 2],
        )
        out = prune_subtrees_below_height(data, 8.0)
        kept = out["primitives"]["points"]
        assert len(kept) == 3  # trunk, fork, fork's twig; the stub is gone
        assert out["primitives"]["attributes"]["branchParentNumber"]["values"] == [
            0,
            1,
            2,
        ]
        assert len(out["points"]["positions"]) == 3 + 3 + 2

    def test_the_trunk_never_goes_and_zero_is_a_no_op(self):
        data = _tree([[[0, 0, 0], [0, 1, 0]]], [0])
        assert prune_subtrees_below_height(data, 5.0)["primitives"]["points"] == [
            [0, 1]
        ]
        assert prune_subtrees_below_height(data, 0.0) is data


class TestCrownFloorGate:
    @pytest.mark.parametrize("floor", [0.3, 0.4])
    def test_the_picker_masks_below_and_keeps_the_thinning_share_above(self, floor):
        palette = masked_palette(["a", "b", "c", "d", "e"], 3)  # beech: 3 masks in 8
        gated, conditions = crown_floor_gate(floor, palette)
        assert len(gated) == 9
        assert gated[-1].use_as_mask and gated[-1].attributes.height == 0.0
        assert all(e.attributes.height == 1.0 for e in gated[:-1])
        for h in (0.0, floor - 0.05):
            assert pick_candidates({"height": h}, gated, conditions) == [8]
        for h in (floor + 0.05, 1.0):
            assert pick_candidates({"height": h}, gated, conditions) == list(range(8))

    def test_a_floor_outside_the_open_interval_is_refused(self):
        with pytest.raises(ValueError):
            crown_floor_gate(0.0, (PaletteEntry(mesh="a"),))


class TestCalibration:
    def test_crown_floor_is_read_per_radius_label(self):
        cal = SpeciesCalibration(
            species="x",
            relative_start=0.4,
            fraction=0.06,
            prototype_leaf_area_m2=None,
            palette_flat_mean_triangles=None,
            history_relative_start=0.0,
            trees={},
            crown_floor={"r07": 0.4, "r10": 0.3},
        )
        assert cal.crown_floor_for("r07_h20m") == 0.4
        assert cal.crown_floor_for("r10_h05m") == 0.3
        assert cal.crown_floor_for("r00_h25m") == 0.0

    def test_a_floor_of_one_is_refused(self):
        with pytest.raises(ValueError, match="crown_floor"):
            SpeciesCalibration(
                species="x",
                relative_start=0.4,
                fraction=0.06,
                prototype_leaf_area_m2=None,
                palette_flat_mean_triangles=None,
                history_relative_start=0.0,
                trees={},
                crown_floor={"r07": 1.0},
            )
