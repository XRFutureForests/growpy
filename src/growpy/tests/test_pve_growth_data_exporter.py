"""Tests for growpy.io.unreal.pve_growth_data_exporter module."""

from types import SimpleNamespace

from growpy.io.unreal.pve_growth_data_exporter import build_growth_data_json


def _make_skeleton(points, poly_lines):
    """Create a mock skeleton with points + poly_lines attributes."""
    return SimpleNamespace(points=points, poly_lines=poly_lines)


class TestBuildGrowthDataJson:
    """Tests for the minimal Growth Data JSON Importer schema builder."""

    def test_empty_skeleton_returns_empty_schema(self):
        skel = _make_skeleton(points=[], poly_lines=[])
        data = build_growth_data_json(skel)
        assert data["points"]["positions"] == []
        assert data["primitives"]["points"] == []
        assert data["primitives"]["attributes"]["parents"]["values"] == []

    def test_positions_are_origin_local_and_unswapped(self):
        # Trunk: 0 -> 1 -> 2, straight up in Z (Grove Z-up convention).
        points = [(5.0, 5.0, 0.0), (5.0, 5.0, 1.0), (5.0, 5.0, 2.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2]])
        data = build_growth_data_json(skel)
        # Origin-subtracted, native (x, y, z) order -- no Y/Z swap, no *100 scale.
        assert data["points"]["positions"] == [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 2.0],
        ]

    def test_single_root_branch(self):
        points = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 2.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2]])
        data = build_growth_data_json(skel)
        prim_attrs = data["primitives"]["attributes"]
        assert data["primitives"]["points"] == [[0, 1, 2]]
        assert prim_attrs["branchNumber"]["values"] == [0]
        assert prim_attrs["parents"]["values"] == [0]  # root self-references
        assert prim_attrs["children"]["values"] == [[]]

    def test_parent_child_hierarchy(self):
        points = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 2.0),
            (0.0, 0.0, 3.0),
            (1.0, 0.0, 2.0),
            (2.0, 0.0, 2.0),
        ]
        # Branch 0: trunk (0,1,2,3). Branch 1: side branch from point 2.
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2, 3], [2, 4, 5]])
        data = build_growth_data_json(skel)
        prim_attrs = data["primitives"]["attributes"]
        assert prim_attrs["parents"]["values"] == [0, 0]
        assert prim_attrs["children"]["values"][0] == [1]
        assert data["primitives"]["points"] == [[0, 1, 2, 3], [2, 4, 5]]

    def test_branch_indices_rebased_to_zero(self):
        # Simulate Grove's global point indexing (offset starts at 10).
        points = [(0.0, 0.0, float(i)) for i in range(3)]
        skel = _make_skeleton(points=points, poly_lines=[[10, 11, 12]])
        data = build_growth_data_json(skel)
        assert data["primitives"]["points"] == [[0, 1, 2]]

    def test_bud_direction_present_per_point(self):
        points = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1]])
        data = build_growth_data_json(skel)
        bud_dir = data["points"]["attributes"]["budDirection"]
        assert bud_dir["values"]
        assert len(bud_dir["values"]) == len(points)

    def test_schema_metadata_matches_pve_schema_conventions(self):
        points = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1]])
        data = build_growth_data_json(skel)
        prim_attrs = data["primitives"]["attributes"]
        assert prim_attrs["branchNumber"]["isArray"] is False
        assert prim_attrs["children"]["isArray"] is True
        assert data["points"]["attributes"]["budDirection"]["isArray"] is True
