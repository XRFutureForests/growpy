"""growpy-structure-descriptors: a synthetic whorled conifer with known geometry (XRFF-532)."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from growpy.tools import structure_descriptors as sd

TRUNK_R = 0.10
BRANCH_R = 0.02


def _tree(tmp_path: Path, *, whorls=(6, 9, 12, 15, 18), per_whorl=4, angle=100.0, length=3.0,
          jitter: random.Random | None = None, phase_step=30.0, name="Tree_r07_h20m_d20cm_full_growth_data.json") -> Path:
    """A 20 m trunk with a whorl of ``per_whorl`` straight branches at each listed height.

    Every branch leaves ``angle`` degrees from vertical, ``length`` metres long. With
    ``jitter`` the angles, lengths, azimuth gaps and whorl phase are randomised.
    """
    positions: list[list[float]] = []
    prims: list[list[int]] = []
    radii: list[list[float]] = []

    def add(points, r):
        idx = []
        for p in points:
            positions.append([float(c) for c in p])
            radii.append([r, 0.0])
            idx.append(len(positions) - 1)
        prims.append(idx)

    add([(0.0, float(y), 0.0) for y in range(21)], TRUNK_R)
    for k, y in enumerate(whorls):
        phase = math.radians(phase_step * k if jitter is None else jitter.uniform(0, 360))
        for j in range(per_whorl):
            az = phase + 2 * math.pi * j / per_whorl
            ang, ln = angle, length
            if jitter is not None:
                az += math.radians(jitter.uniform(-25, 25))
                ang += jitter.uniform(-12, 12)
                ln *= jitter.uniform(0.6, 1.4)
            a = math.radians(ang)
            d = (math.sin(a) * math.cos(az), math.cos(a), math.sin(a) * math.sin(az))
            steps = 6
            pts = [(d[0] * ln * s / steps, y + d[1] * ln * s / steps, d[2] * ln * s / steps) for s in range(steps + 1)]
            add(pts, BRANCH_R)
    n = len(prims)
    data = {
        "points": {"positions": positions, "attributes": {"budLateralMeristem": {"values": radii}}},
        "primitives": {
            "points": prims,
            "attributes": {
                "branchNumber": {"values": list(range(n))},
                "branchParentNumber": {"values": [-1] + [0] * (n - 1)},
                "branchHierarchyNumber": {"values": [1] + [2] * (n - 1)},
            },
        },
    }
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestMechanicalWhorlTree:
    def test_counts_and_whorl_structure(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.n_first_order == 20
        assert d.whorl["nodes_with_branches"] == 5
        assert d.whorl["branches_per_node_p10_p50_p90"][1] == 4
        assert d.whorl["tier_spacing_m_p10_p50_p90"][1] == pytest.approx(3.0)

    def test_a_perfectly_regular_tree_scores_zero_on_every_regularity_index(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.whorl["tier_spacing_cv"] == 0.0
        assert d.whorl["divergence_gap_cv"] == 0.0
        assert d.whorl["length_cv_within_node"] == 0.0
        assert d.whorl["phase_step_cv"] == 0.0
        assert d.shape["branch_length_cv"] == 0.0

    def test_angles_are_in_the_declared_frame(self, tmp_path):
        d = sd.describe(_tree(tmp_path, angle=100.0))
        for third in sd.THIRDS:
            assert d.angles["chord_to_half_length_deg_by_third"][third] == pytest.approx(100.0, abs=0.5)
            assert d.angles["initial_30cm_deg_by_third"][third] == pytest.approx(100.0, abs=0.5)

    def test_straight_branches_have_no_bend(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.shape["straightness_median"] == pytest.approx(1.0, abs=1e-6)
        assert d.shape["bend_deg_median"] == pytest.approx(0.0, abs=1e-6)

    def test_branch_to_stem_radius_ratio(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.diameters["branch_to_stem_radius_by_third"]["middle"] == pytest.approx(BRANCH_R / TRUNK_R)

    def test_crown_base_and_ratio(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.crown["crown_base_m"] == pytest.approx(6.0)
        assert d.crown["crown_ratio"] == pytest.approx((d.height_m - 6.0) / d.height_m, abs=0.01)

    def test_order_counts(self, tmp_path):
        d = sd.describe(_tree(tmp_path))
        assert d.orders["branches_by_order"] == {"2": 20}


class TestIrregularTree:
    def test_a_randomised_tree_is_no_longer_regular(self, tmp_path):
        rng = random.Random(7)
        d = sd.describe(_tree(tmp_path, jitter=rng))
        assert d.whorl["divergence_gap_cv"] > 0.05
        assert d.whorl["length_cv_within_node"] > 0.05
        assert d.whorl["phase_step_cv"] > 0.05
        assert d.shape["chord_angle_cv"] > 0.0

    def test_irregular_spacing_raises_the_tier_spacing_cv(self, tmp_path):
        even = sd.describe(_tree(tmp_path, whorls=(4, 7, 10, 13, 16)))
        uneven = sd.describe(_tree(tmp_path, whorls=(4, 6, 11, 12, 18), name="Other_r07_h20m_d20cm_full_growth_data.json"))
        assert even.whorl["tier_spacing_cv"] == 0.0
        assert uneven.whorl["tier_spacing_cv"] > 0.3


class TestEdges:
    def test_a_trunk_with_no_branches_has_no_descriptors(self, tmp_path):
        assert sd.describe(_tree(tmp_path, whorls=())) is None

    def test_flatten_gives_the_headline_row(self, tmp_path):
        row = sd.flatten(sd.describe(_tree(tmp_path)))
        assert row["br/node_p50"] == 4 and row["tier_cv"] == 0.0 and row["straight"] == pytest.approx(1.0)

    def test_command_line_prints_a_row_per_cell_and_writes_json(self, tmp_path, capsys):
        _tree(tmp_path)
        out = tmp_path / "d.json"
        assert sd.main([str(tmp_path), "--out", str(out)]) == 0
        assert "Tree r07 h20" in capsys.readouterr().out
        assert json.loads(out.read_text(encoding="utf-8"))
