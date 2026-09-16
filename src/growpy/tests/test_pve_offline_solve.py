"""Tests for the offline PVE foliage solve (pve_offline_solve).

The distributor model underneath is validated against logged exports in
test_pve_distributor_model; here the question is whether the solver lands a
density on its target, reads a tree's DBH the way the exporter wrote it, and
lays out the compound chain the way the plan expects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growpy.config.pve_calibration import CompoundSpec, LadderSpec
from growpy.io.unreal.pve_graph_builder import DistributorSpec, PaletteEntry
from growpy.io.unreal.pve_offline_solve import (
    compound_layout,
    mean_triangles_per_prototype,
    quantile_targets,
    solve_flat,
    solve_graded,
    tree_stats,
)

PROFILE_MEAN = 0.8215


def _tree(tmp_path: Path, branches: int = 10) -> Path:
    """A synthetic growth JSON in the exporter's frame: Y-up, metres.

    One 12 m trunk of radius 0.10 m at the base tapering to 0.02 m at the
    top, with ``branches`` side branches of varying length, radius 0.02.
    """
    positions: list[list[float]] = []
    branch_points: list[list[int]] = []
    parents: list[int] = []
    numbers: list[int] = []
    radii: list[list[float]] = []
    generations: list[list[int]] = []

    trunk = []
    steps = 13
    for i in range(steps):
        positions.append([0.0, i * 1.0, 0.0])
        radii.append([0.10 - 0.08 * i / (steps - 1), 0.0])
        generations.append([1])
        trunk.append(len(positions) - 1)
    branch_points.append(trunk)
    parents.append(-1)
    numbers.append(0)

    for b in range(branches):
        attach = trunk[min(2 + b, steps - 1)]
        points = [attach]
        span = 3 + (b % 4)
        for j in range(1, span + 1):
            base = positions[attach]
            positions.append(
                [base[0] + j * 0.6, base[1] + j * 0.25, base[2] + j * 0.12]
            )
            radii.append([0.02, 0.0])
            generations.append([2])
            points.append(len(positions) - 1)
        branch_points.append(points)
        parents.append(0)
        numbers.append(b + 1)

    path = tmp_path / "Test_Species_r08_h10m_d10cm_growth_data.json"
    path.write_text(
        json.dumps(
            {
                "points": {
                    "positions": positions,
                    "attributes": {
                        "budLateralMeristem": {"values": radii},
                        "budDevelopment": {"values": generations},
                    },
                },
                "primitives": {
                    "points": branch_points,
                    "attributes": {
                        "branchParentNumber": {"values": parents},
                        "branchNumber": {"values": numbers},
                    },
                },
            }
        )
    )
    return path


def _base(**overrides) -> DistributorSpec:
    defaults = {"branch_density": 1, "scale_ramp": (1.0, 1.0)}
    defaults.update(overrides)
    return DistributorSpec(**defaults)


class TestTreeStats:
    def test_dbh_is_the_trunk_radius_at_breast_height_in_cm(self, tmp_path):
        stats = tree_stats(_tree(tmp_path), PROFILE_MEAN)
        # radius at 1.3 m on a 0.10 -> 0.02 taper over 12 m
        radius = 0.10 - 0.08 * 1.3 / 12.0
        assert stats.dbh_cm == pytest.approx(2 * radius * PROFILE_MEAN * 100, rel=1e-6)
        assert stats.height_m == pytest.approx(12.0)
        assert stats.branches == 11
        assert stats.longest_branch_m == pytest.approx(12.0)


class TestQuantiles:
    def test_mid_quantiles_ascend_and_cover_the_range(self):
        targets = quantile_targets([0.1 * i for i in range(1, 11)], 4)
        assert list(targets) == sorted(targets)
        assert targets[0] >= 0.1 and targets[-1] <= 1.0

    def test_empty_samples_give_zeros(self):
        assert quantile_targets([], 3) == (0.0, 0.0, 0.0)


class TestSolveFlat:
    def test_lands_on_the_nearest_reachable_area(self, tmp_path):
        path = _tree(tmp_path)
        solved = solve_flat(path, _base(), 0.02, target_m2=2.0)
        assert solved.density >= 1
        assert solved.instances > 0
        assert solved.area_m2 == pytest.approx(solved.instances * 0.02)
        # The neighbours on the staircase must not be closer to the target.
        for other in (solved.density - 1, solved.density + 1):
            if other < 1:
                continue
            neighbour = solve_flat(path, _base(), 0.02, target_m2=2.0)
            assert abs(neighbour.area_m2 - 2.0) >= abs(solved.area_m2 - 2.0) - 1e-9
        assert solved.target_m2 == 2.0

    def test_more_target_never_means_fewer_instances(self, tmp_path):
        path = _tree(tmp_path)
        low = solve_flat(path, _base(), 0.02, target_m2=0.5)
        high = solve_flat(path, _base(), 0.02, target_m2=3.0)
        assert high.instances >= low.instances


class TestSolveGraded:
    def test_grades_every_tier_and_adds_the_apex(self, tmp_path):
        path = _tree(tmp_path)
        meshes = ("/G/SM_small", "/G/SM_mid", "/G/SM_big")
        areas = (0.005, 0.01, 0.03)
        solved = solve_graded(path, _base(), meshes, areas, LadderSpec(), 1.0)
        assert solved.scale_targets is not None and len(solved.scale_targets) == 3
        assert list(solved.scale_targets) == sorted(solved.scale_targets)
        # main placements (gen >= 2) plus exactly one apex spray
        assert solved.instances >= 2
        assert solved.instance_area_m2 == pytest.approx(
            solved.area_m2 / solved.instances
        )


class TestCompoundLayout:
    def test_fill_cap_and_apex_are_laid_out_and_counted(self, tmp_path):
        path = _tree(tmp_path)
        names = [f"test_compound_p0{i}" for i in range(5)]
        meshes = tuple(f"/G/SM_{n}_ZUP" for n in names)
        areas = (0.13, 0.19, 0.29, 0.45, 0.67)
        layout = compound_layout(
            path, _base(), names, meshes, areas, CompoundSpec(), longest_branch_m=12.0
        )
        # fill over the three small tiers, graded
        assert [e.mesh for e in layout.palette] == list(meshes[:3])
        assert layout.distributor.conditions is not None
        assert layout.distributor.generation_band == (2, None)
        assert layout.distributor.relative_start == pytest.approx(0.15)
        assert layout.distributor.relative_end == pytest.approx(0.90)
        # spacing rule: 12 m * 0.75 / 0.4 m = 22.5 -> 22 (or 23)
        assert layout.distributor.branch_density in (22, 23)
        # tip cap on p00 at density 1 over gen >= 2, apex on p02 on the leader
        assert len(layout.layers) == 2
        cap, apex = layout.layers
        assert cap.palette == (PaletteEntry(mesh=meshes[0]),)
        assert cap.distributor.branch_density == 1
        assert cap.distributor.generation_band == (2, None)
        assert apex.palette == (PaletteEntry(mesh=meshes[2]),)
        assert apex.distributor.generation_band == (1, 1)
        assert layout.apex_instances == 1
        assert layout.cap_instances == 10  # one per side branch end
        assert layout.instances == (
            layout.fill_instances + layout.cap_instances + layout.apex_instances
        )
        assert layout.area_m2 > 0

    def test_an_unknown_tier_is_refused(self, tmp_path):
        path = _tree(tmp_path)
        names = ["x_compound_p00", "x_compound_p01"]
        with pytest.raises(ValueError, match="tier 'p02'"):
            compound_layout(
                path,
                _base(),
                names,
                ("/G/a", "/G/b"),
                (0.1, 0.2),
                CompoundSpec(fill_tiers=("p00", "p01"), apex_tier="p02"),
                longest_branch_m=5.0,
            )


class TestMeanTriangles:
    def test_counts_faceVertexCounts_entries(self, tmp_path):
        a = tmp_path / "a_static.usda"
        b = tmp_path / "b_static.usda"
        a.write_text('def Mesh "m" {\n int[] faceVertexCounts = [3, 3, 3, 3]\n}\n')
        b.write_text('def Mesh "m" {\n int[] faceVertexCounts = [3, 3]\n}\n')
        assert mean_triangles_per_prototype([a, b]) == pytest.approx(3.0)

    def test_no_faces_is_refused(self, tmp_path):
        empty = tmp_path / "e_static.usda"
        empty.write_text("#usda 1.0\n")
        with pytest.raises(ValueError, match="faceVertexCounts"):
            mean_triangles_per_prototype([empty])


class TestRandomizeScaleInTheSolve:
    """XRFF-467: the solve has to divide E[scale^2] back out.

    Randomising instance scale raises the area each instance carries (E[U^2]
    >= 1 for any spread about 1.0), so a solve that ignores it asks for the
    same instance count and lands the tree over its target -- invisibly,
    because neither the count nor the triangle telemetry moves.
    """

    def test_the_identity_range_changes_nothing(self, tmp_path):
        path = _tree(tmp_path)
        plain = solve_flat(path, _base(), 0.02, 4.0)
        identity = solve_flat(path, _base(randomize_scale=(1.0, 1.0)), 0.02, 4.0)
        assert identity.density == plain.density
        assert identity.area_m2 == pytest.approx(plain.area_m2)

    def test_a_spread_lowers_the_density_it_asks_for(self, tmp_path):
        path = _tree(tmp_path)
        plain = solve_flat(path, _base(), 0.02, 4.0)
        varied = solve_flat(path, _base(randomize_scale=(0.7, 1.3)), 0.02, 4.0)
        assert varied.instance_area_m2 == pytest.approx(0.02 * 1.03)
        assert varied.instances <= plain.instances
        # Both still land on the target; that is the point of the correction.
        assert abs(varied.error) < 0.10
