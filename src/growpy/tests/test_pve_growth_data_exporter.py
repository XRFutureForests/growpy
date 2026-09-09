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

    def test_positions_are_origin_local_and_swapped_to_y_up(self):
        """Grove Z-up must be pre-swapped to Y-up, verified against a live editor.

        The loader does FVector3f(P[0], P[2], P[1]) * 100, so UE Z (up) comes
        from json index 1. Grove puts height at index 2, so writing its native
        order unconverted lands the height in UE Y and the tree falls over.
        This test previously asserted the unswapped form.
        """
        # Trunk: 0 -> 1 -> 2, straight up in Z (Grove Z-up convention).
        points = [(5.0, 5.0, 0.0), (5.0, 5.0, 1.0), (5.0, 5.0, 2.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2]])
        data = build_growth_data_json(skel)
        # Origin-subtracted, metres, height moved to index 1. No *100 here --
        # the loader applies that.
        assert data["points"]["positions"] == [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 2.0, 0.0],
        ]

    def test_single_root_branch(self):
        points = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 2.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2]])
        data = build_growth_data_json(skel)
        prim_attrs = data["primitives"]["attributes"]
        assert data["primitives"]["points"] == [[0, 1, 2]]
        # branchNumber is 1-BASED in Epic's own Beech_01 sample.
        assert prim_attrs["branchNumber"]["values"] == [1]
        # parents is the ancestor CHAIN of branchNumbers headed by a virtual 0,
        # and is TArray<int32> -- declaring it scalar registers the wrong C++
        # type and the facade accessor asserts.
        assert prim_attrs["parents"]["values"] == [[0]]
        assert prim_attrs["parents"]["isArray"] is True
        assert prim_attrs["children"]["values"] == [[]]
        # branchParentNumber carries the immediate parent; 0 for the trunk.
        assert prim_attrs["branchParentNumber"]["values"] == [0]
        assert prim_attrs["plantNumber"]["values"] == [1]

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
        # Trunk -> [0]; a child of the trunk -> [0, 1], root-first in 1-based
        # branchNumbers. growpy's own hierarchy builder uses the mirror-image
        # convention (self-first, 0-based), which is why this is built from the
        # immediate parents instead.
        assert prim_attrs["parents"]["values"] == [[0], [0, 1]]
        assert prim_attrs["children"]["values"][0] == [2]  # 1-based branchNumber
        assert prim_attrs["branchParentNumber"]["values"] == [0, 1]
        assert prim_attrs["branchHierarchyNumber"]["values"] == [1, 2]
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
