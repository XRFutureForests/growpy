"""growpy-twig-audit: skeleton metrics, offline placements, thresholds (XRFF-525)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growpy.tools import twig_audit as ta

RAMP = (
    "(EditorCurveData=(Keys=((InterpMode=RCIM_Linear,Time=0.000000,Value=1.000000),"
    "(InterpMode=RCIM_Linear,Time=1.000000,Value=1.000000))))"
)


def _tree_json(tmp_path: Path, species: str = "norway_spruce") -> Path:
    """A 10 m y-up tree: a straight trunk, two level branches at 4 m and 5 m, and
    a shoot at 6 m that leaves sideways and turns up (a 'candle'). The topmost
    first-order branch attaches at 6 m, so the leader is 4 m."""
    positions: list[list[float]] = []
    prims: list[list[int]] = []

    def add(points):
        idx = []
        for p in points:
            positions.append([float(c) for c in p])
            idx.append(len(positions) - 1)
        prims.append(idx)

    add([(0.0, float(y), 0.0) for y in range(11)])  # trunk, primitive 0
    add([(0.0, 4.0, 0.0), (1.0, 4.0, 0.0), (2.0, 4.1, 0.0), (3.0, 4.2, 0.0)])
    add([(0.0, 5.0, 0.0), (0.0, 5.0, 1.0), (0.0, 5.1, 2.0), (0.0, 5.2, 3.0)])
    add([(0.0, 6.0, 0.0), (1.0, 6.0, 0.0), (2.0, 6.1, 0.0), (2.2, 7.0, 0.0), (2.2, 8.0, 0.0)])
    n = len(prims)
    data = {
        "points": {"positions": positions},
        "primitives": {
            "points": prims,
            "attributes": {
                "branchNumber": {"values": list(range(n))},
                "branchParentNumber": {"values": [-1] + [0] * (n - 1)},
                "branchHierarchyNumber": {"values": [1] + [2] * (n - 1)},
            },
        },
    }
    path = tmp_path / species / "r07" / "Tree_r07_h10m_d20cm_full_growth_data.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _spec(density: int, band, **extra) -> dict:
    spec = {
        "branch_density": density,
        "spacing_basis": "BRANCH",
        "relative_start": 0.0,
        "relative_end": 1.0,
        "generation_band": band,
        "scale_ramp": RAMP,
        "spacing_ramp": None,
        "node_buds": [1, 1],
        "phyllotaxy_type": "SPIRAL",
        "scale_ramp_basis": "PLANT",
        "base_scale": 1.0,
        "single_bud_tip": True,
    }
    spec.update(extra)
    return spec


def _chain(path: Path, *layers: dict) -> dict:
    return {
        "growth_json": str(path),
        "mesh_name": "SK_NorwaySpruce_r07_h10m",
        **_spec(20, [2, None]),
        "layers": list(layers),
    }


APEX = _spec(1, [1, 1])
# a leader layer: sixteen sprays along the trunk's top 40 % (a 4 m leader, so with
# the apex that is 4.25 per metre, over the 3 per metre floor)
LEADER = _spec(16, [1, 1], relative_start=0.6, relative_end=1.0)

LIMITS = {
    "upturned_max": 0.05,
    "leader_min_m": 0.5,
    "leader_sprays_per_m_min": 3.0,
    "top_band_ratio_min": 0.5,
}
THRESHOLDS = ta.Thresholds(
    conifers=frozenset({"norway_spruce"}), conifer=LIMITS, broadleaf={"top_band_ratio_min": 0.5}
)


class TestPlanParsing:
    def test_parse_ue_curve(self):
        assert ta.parse_ue_curve(RAMP) == ((0.0, 1.0), (1.0, 1.0))
        assert ta.parse_ue_curve(None) is None

    def test_distributor_from_literal_keeps_what_the_model_reads(self):
        spec = ta.distributor_from_literal(_spec(776, [2, None]))
        assert spec.branch_density == 776
        assert spec.generation_band == (2, None)
        assert spec.scale_ramp == (1.0, 1.0)
        assert spec.spacing_ramp is None

    def test_tree_id_and_species_from_the_export_layout(self, tmp_path):
        assert ta.tree_id_of("SK_DouglasFir_r10_h35m") == "r10_h35m"
        assert ta.species_of(_tree_json(tmp_path)) == "norway_spruce"

    def test_load_chains_reads_the_graph_script_literal(self, tmp_path):
        chain = _chain(Path("x.json"))
        script = tmp_path / "growpy_pve_graphs.py"
        script.write_text(f"import x\nGRAPHS = {[{'chains': [chain]}]!r}\nPV = 1\n", encoding="utf-8")
        assert ta.load_chains(script)[0]["mesh_name"] == "SK_NorwaySpruce_r07_h10m"

    def test_load_chains_rejects_a_file_that_is_not_a_graph_script(self, tmp_path):
        script = tmp_path / "other.py"
        script.write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(ValueError):
            ta.load_chains(script)


class TestSkeleton:
    def test_leader_is_the_trunk_above_the_topmost_first_order_branch(self, tmp_path):
        skeleton = ta.measure_skeleton(_tree_json(tmp_path))
        assert skeleton.height_m == pytest.approx(10.0)
        assert skeleton.leader.length_m == pytest.approx(4.0)
        assert skeleton.leader.start_along == pytest.approx(0.6)

    def test_a_curved_leader_is_measured_along_the_trunk_not_by_height(self, tmp_path):
        """A real Scots pine: 1.16 m of leader that gains 0.11 m of height. The plan
        puts its sprays along the trunk, so the audit has to count that way."""
        path = _tree_json(tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        pos = data["points"]["positions"]
        trunk = data["primitives"]["points"][0]
        # bend the top three trunk points sideways: more arc than height above y=6
        for k, i in enumerate(trunk[-3:], start=1):
            pos[i][0] = 1.5 * k
            pos[i][1] = 7.0 + 0.1 * k
        path.write_text(json.dumps(data), encoding="utf-8")
        leader = ta.measure_skeleton(path).leader
        assert leader.length_m > 4.0  # the arc is longer than the 4 m it used to climb
        assert leader.start_along < 0.6

    def test_a_shoot_that_leaves_sideways_and_turns_up_is_a_candle(self, tmp_path):
        skeleton = ta.measure_skeleton(_tree_json(tmp_path))
        assert skeleton.side_branches == 3
        assert skeleton.upturned == pytest.approx(1 / 3)
        assert skeleton.tips_up == pytest.approx(1 / 3)

    def test_wood_is_counted_per_tenth_of_the_height(self, tmp_path):
        wood = ta.measure_skeleton(_tree_json(tmp_path)).band_branch_m
        assert len(wood) == ta.BANDS
        assert wood[0] == 0.0 and wood[9] == 0.0  # no side wood at the foot or the tip
        assert sum(wood) > 8.0


class TestPlacements:
    def test_the_apex_layer_alone_gives_the_leader_exactly_one_spray(self, tmp_path):
        audit = ta.audit_chain(_chain(_tree_json(tmp_path), APEX), THRESHOLDS)
        assert audit.leader_instances == 1
        assert audit.leader_sprays_per_m == pytest.approx(0.25)  # 1 spray on a 4 m leader

    def test_a_leader_layer_puts_sprays_along_the_leader(self, tmp_path):
        path = _tree_json(tmp_path)
        apex_only = ta.audit_chain(_chain(path, APEX), THRESHOLDS)
        with_leader = ta.audit_chain(_chain(path, APEX, LEADER), THRESHOLDS)
        assert with_leader.leader_instances > apex_only.leader_instances + 5
        assert with_leader.leader_sprays_per_m > apex_only.leader_sprays_per_m
        assert with_leader.layer_instances[2] > 5  # the third layer is the leader layer

    def test_layers_are_reported_separately_and_sum_to_the_total(self, tmp_path):
        audit = ta.audit_chain(_chain(_tree_json(tmp_path), APEX), THRESHOLDS)
        assert len(audit.layer_instances) == 2
        assert sum(audit.layer_instances) == audit.instances
        assert sum(audit.band_instances) == audit.instances


class TestJudgement:
    def test_a_lonely_leader_and_a_candle_both_fail(self, tmp_path):
        audit = ta.audit_chain(_chain(_tree_json(tmp_path), APEX), THRESHOLDS)
        kinds = {f.split()[0] for f in audit.failures}
        assert {"upturned", "leader"} <= kinds

    def test_a_foliated_leader_passes_the_leader_check(self, tmp_path):
        audit = ta.audit_chain(_chain(_tree_json(tmp_path), APEX, LEADER), THRESHOLDS)
        assert not any(f.startswith("leader") for f in audit.failures)

    def test_a_broadleaf_is_not_judged_on_candles_or_leader(self, tmp_path):
        path = _tree_json(tmp_path, species="european_beech")
        audit = ta.audit_chain(_chain(path, APEX), THRESHOLDS)
        assert audit.habit == "broadleaf"
        assert not any(f.startswith(("upturned", "leader")) for f in audit.failures)

    def test_a_short_leader_is_not_judged(self):
        audit = ta.TreeAudit(
            "SK_X_r07_h05m", "norway_spruce", "r07_h05m", "conifer", 5.0, 100, [100],
            0.0, 0.0, 0.03, 1, 33.3, 1.0, [0] * 10, [0.0] * 10,
        )
        assert ta.judge(audit, LIMITS) == []

    def test_top_band_ratio_is_even_for_a_uniform_crown(self):
        counts = [0, 0, 0, 0, 10, 10, 10, 0, 0, 10]
        wood = (0, 0, 0, 0, 1.0, 1.0, 1.0, 0, 0, 1.0)
        assert ta.top_band_ratio(counts, wood) == pytest.approx(1.0)
        assert ta.top_band_ratio(counts, (0,) * 10) is None


class TestCommandLine:
    def _plan(self, tmp_path, *layers) -> Path:
        path = _tree_json(tmp_path)
        plan = tmp_path / "plan"
        plan.mkdir()
        (plan / "growpy_pve_graphs.py").write_text(
            f"GRAPHS = {[{'chains': [_chain(path, *layers)]}]!r}\n", encoding="utf-8"
        )
        return plan

    def _thresholds(self, tmp_path) -> Path:
        toml = tmp_path / "twig_audit.toml"
        toml.write_text(
            '[habits]\nconifer = ["norway_spruce"]\n[conifer]\nupturned_max = 0.5\n'
            "leader_min_m = 0.5\nleader_sprays_per_m_min = 3.0\n",
            encoding="utf-8",
        )
        return toml

    def test_exit_1_and_a_report_when_a_cell_fails(self, tmp_path):
        plan = self._plan(tmp_path, APEX)
        code = ta.main([str(plan), "--thresholds", str(self._thresholds(tmp_path))])
        assert code == 1
        report = json.loads((plan / "twig_audit.json").read_text(encoding="utf-8"))
        assert report["failing"] == ["SK_NorwaySpruce_r07_h10m"]

    def test_exit_0_when_the_leader_is_foliated(self, tmp_path):
        plan = self._plan(tmp_path, APEX, LEADER)
        assert ta.main([str(plan), "--thresholds", str(self._thresholds(tmp_path))]) == 0

    def test_no_fail_reports_without_failing(self, tmp_path):
        plan = self._plan(tmp_path, APEX)
        args = [str(plan), "--thresholds", str(self._thresholds(tmp_path)), "--no-fail"]
        assert ta.main(args) == 0
