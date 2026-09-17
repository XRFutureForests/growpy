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

    def test_generation_is_the_branch_depth_and_the_attach_point_stays_the_parents(
        self,
    ):
        # budDevelopment[0] is what StartGeneration/EndGeneration gate on, read
        # off a branch's LAST point. A child's first point is the parent's
        # point: PVE gives it to the parent (ForEachUniquePointOnBranches skips
        # index 0 of a non-trunk branch), so writing it from the child would
        # stamp the child's depth onto a parent whose tip carries a child.
        points = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 2.0),  # trunk tip, and the attach point of branch 1
            (1.0, 0.0, 2.0),
            (2.0, 0.0, 2.0),  # branch 1 tip, and the attach point of branch 2
            (2.0, 1.0, 2.0),
        ]
        skel = _make_skeleton(
            points=points, poly_lines=[[0, 1, 2], [2, 3, 4], [4, 5]]
        )
        data = build_growth_data_json(skel)
        generation = [
            v[0] for v in data["points"]["attributes"]["budDevelopment"]["values"]
        ]
        assert data["primitives"]["attributes"]["branchHierarchyNumber"]["values"] == [
            1,
            2,
            3,
        ]
        # Trunk points 1, side branch interior 2, twig interior 3; the shared
        # attach points 2 and 4 keep the depth of the branch they end.
        assert generation == [1, 1, 1, 2, 2, 3]

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

    def test_branch_tip_apical_follows_incoming_segment(self):
        # A horizontal branch heading +X (Grove Z-up). The last point has no
        # next point; its apical must be the incoming segment direction, not
        # the (0,0,1) fallback, or PVE stands every tip twig vertically.
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1, 2]])
        data = build_growth_data_json(skel)
        tip = data["points"]["attributes"]["budDirection"]["values"][2]
        # JSON is Y-up: Grove (x, y, z) -> (x, z, y)
        assert tip[0:3] == [1.0, 0.0, 0.0]
        assert tip[15:18] == [0.0, 1.0, 0.0]  # up stays the most-upward perpendicular

    def test_schema_metadata_matches_pve_schema_conventions(self):
        points = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        skel = _make_skeleton(points=points, poly_lines=[[0, 1]])
        data = build_growth_data_json(skel)
        prim_attrs = data["primitives"]["attributes"]
        assert prim_attrs["branchNumber"]["isArray"] is False
        assert prim_attrs["children"]["isArray"] is True
        assert data["points"]["attributes"]["budDirection"]["isArray"] is True


class TestMinPointSpacing:
    """Points are the exported bones; the spacing thins them WITHIN a branch.

    Beech at fraction 0.02 was 82,408 points at r16_h15m and UE would not open
    it (XRFF-471). The fraction sets branch count (the look); Grove's internode
    sets points per branch (the weight), and this is the only knob for it --
    quality.toml's skeleton_length tags USD bones and never reaches this file.
    """

    # Trunk 0..5 straight up at 0.5 m steps; a side branch from point 2 with
    # 0.5 m steps; a twig from the side branch's interior point 7.
    _POINTS = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.5),
        (0.0, 0.0, 1.0),  # attach point of branch 1
        (0.0, 0.0, 1.5),
        (0.0, 0.0, 2.0),
        (0.0, 0.0, 2.5),
        (0.5, 0.0, 1.0),
        (1.0, 0.0, 1.0),  # attach point of branch 2 (interior of branch 1)
        (1.5, 0.0, 1.0),
        (2.0, 0.0, 1.0),
        (1.0, 0.5, 1.0),
        (1.0, 1.0, 1.0),
    ]
    _LINES = [[0, 1, 2, 3, 4, 5], [2, 6, 7, 8, 9], [7, 10, 11]]

    def test_zero_keeps_every_node(self):
        skel = _make_skeleton(points=self._POINTS, poly_lines=self._LINES)
        data = build_growth_data_json(skel, min_point_spacing=0.0)
        assert len(data["points"]["positions"]) == 12
        assert data["primitives"]["points"] == self._LINES

    def test_keeps_root_tip_and_attach_points_and_thins_between(self):
        skel = _make_skeleton(points=self._POINTS, poly_lines=self._LINES)
        data = build_growth_data_json(skel, min_point_spacing=1.0)
        prims = data["primitives"]["points"]
        pos = data["points"]["positions"]
        # Trunk: root, the attach point at 1.0 m, 2.0 m, the tip at 2.5 m.
        assert [pos[i][1] for i in prims[0]] == [0.0, 1.0, 2.0, 2.5]
        # Side branch: attach, the twig's anchor at 1.0 m along, tip at 2.0 m.
        assert [pos[i][0] for i in prims[1]] == [0.0, 1.0, 2.0]
        # The twig is shorter than the spacing: root and tip only.
        assert len(prims[2]) == 2
        # Shared points stay shared after renumbering.
        assert prims[1][0] == prims[0][1]
        assert prims[2][0] == prims[1][1]
        # No branch dropped, hierarchy untouched, every point attribute
        # renumbered with the positions.
        assert data["primitives"]["attributes"]["branchParentNumber"]["values"] == [
            0,
            1,
            2,
        ]
        assert len(pos) == 4 + 2 + 1
        for attr in data["points"]["attributes"].values():
            assert len(attr["values"]) == len(pos)

    def test_an_attach_point_is_kept_even_short_of_the_spacing(self):
        # At 1.2 m the trunk would keep 1.5 m, not 1.0 m -- unless a child
        # hangs there. Same skeleton with the child decimated away: the point
        # is no longer an anchor and the plain spacing rule takes over.
        skel = _make_skeleton(points=self._POINTS, poly_lines=self._LINES)
        data = build_growth_data_json(skel, min_point_spacing=1.2)
        pos = data["points"]["positions"]
        assert [pos[i][1] for i in data["primitives"]["points"][0]] == [0.0, 1.0, 2.5]
        # Every radius is 0 on a mock skeleton, so an absolute cutoff keeps
        # only the trunk (the decimation never returns an empty tree).
        trunk_only = build_growth_data_json(
            skel, min_branch_radius=1.0, min_point_spacing=1.2
        )
        assert len(trunk_only["primitives"]["points"]) == 1
        pos = trunk_only["points"]["positions"]
        assert [pos[i][1] for i in trunk_only["primitives"]["points"][0]] == [
            0.0,
            1.5,
            2.5,
        ]
