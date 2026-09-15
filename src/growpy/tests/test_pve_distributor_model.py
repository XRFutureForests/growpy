"""Tests for the offline distributor model and scale-aware leaf area (XRFF-443).

The bug this guards against is not a crash. A count-based measurement --
instances times prototype area, or foliage triangles times area per triangle --
reports the same number whatever size the instances are, because scaling a mesh
changes neither its count nor its triangles. Fifteen trees measured exactly on
their Forrester target while carrying about an eighth of the leaf they were
credited with, and three export arms differing only in the scale ramp produced
byte-identical telemetry.

So these tests care most about the cases where the instruments used to agree
and the truth did not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growpy.io.unreal.pve_distributor_model import (
    ENGINE_DEFAULT_RAMP,
    FLAT_RAMP,
    LeafAreaMeasurement,
    expected_instances,
    measure_leaf_area,
    ramp_eval,
    simulate_placements,
)
from growpy.io.unreal.pve_graph_builder import DistributorSpec

PROTOTYPE_AREA = 0.0158

# The real growth JSONs are gitignored scratch. When they are present the
# validation cases below run; when they are not, the synthetic tree still
# covers the behaviour.
REAL_JSONS = Path("data/tmp/pve_test/growthjson")

# (file, density, instances logged from the editor). The model reproduced 13 of
# these exactly and fir r05_h25m within one instance.
LOGGED_CASES = [
    ("beech_r05_h05m_f006.json", 16, 357),
    ("beech_r05_h05m_f006.json", 20, 523),
    ("beech_r05_h05m_f006.json", 17, 394),
    ("beech_r10_h05m_f006.json", 17, 574),
    ("beech_r20_h05m_f006.json", 18, 656),
    ("beech_r05_h10m_f006.json", 33, 1085),
    ("beech_r05_h15m_f006.json", 66, 1522),
    ("beech_r10_h15m_f006.json", 88, 4764),
    ("beech_r20_h15m_f006.json", 112, 11587),
    ("fir_r05_h05m_f060.json", 20, 281),
    ("fir_r10_h05m_f060.json", 19, 306),
    ("fir_r20_h05m_f060.json", 20, 389),
    ("fir_r05_h25m_f060.json", 158, 5788),
    ("fir_r10_h25m_f060.json", 133, 5829),
]


def _tree(tmp_path: Path, trunk_points: int = 12, branches: int = 8) -> Path:
    """A synthetic growth JSON: one trunk plus side branches of varying length.

    Positions are centimetres, as the exporter writes them. Branch lengths
    vary so length_ratio -- and therefore the per-branch loop count -- is not
    uniform, which is what makes the placement loop interesting.
    """
    positions: list[list[float]] = []
    branch_points: list[list[int]] = []
    parents: list[int] = []
    numbers: list[int] = []

    trunk = []
    for i in range(trunk_points):
        positions.append([0.0, 0.0, i * 100.0])
        trunk.append(len(positions) - 1)
    branch_points.append(trunk)
    parents.append(-1)
    numbers.append(0)

    for b in range(branches):
        attach = trunk[min(2 + b, trunk_points - 1)]
        points = [attach]
        span = 3 + (b % 4)
        for j in range(1, span + 1):
            base = positions[attach]
            positions.append(
                [base[0] + j * 60.0, base[1] + j * 12.0, base[2] + j * 25.0]
            )
            points.append(len(positions) - 1)
        branch_points.append(points)
        parents.append(0)
        numbers.append(b + 1)

    path = tmp_path / "synthetic_growth_data.json"
    path.write_text(
        json.dumps(
            {
                "points": {"positions": positions},
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


def _spec(**overrides) -> DistributorSpec:
    defaults = {"branch_density": 20, "scale_ramp": FLAT_RAMP}
    defaults.update(overrides)
    return DistributorSpec(**defaults)


class TestRampEval:
    def test_it_interpolates_linearly(self):
        keys = ((0.0, 1.0), (1.0, 0.1))
        assert ramp_eval(keys, 0.0) == pytest.approx(1.0)
        assert ramp_eval(keys, 1.0) == pytest.approx(0.1)
        assert ramp_eval(keys, 0.5) == pytest.approx(0.55)

    def test_it_clamps_outside_the_range(self):
        keys = ((0.0, 1.0), (1.0, 0.1))
        assert ramp_eval(keys, -5.0) == pytest.approx(1.0)
        assert ramp_eval(keys, 5.0) == pytest.approx(0.1)

    def test_a_flat_ramp_is_flat_everywhere(self):
        keys = ((0.0, 1.0), (1.0, 1.0))
        assert all(ramp_eval(keys, x) == 1.0 for x in (0.0, 0.3, 0.7, 1.0))


class TestPlacement:
    def test_it_places_instances(self, tmp_path):
        placements = simulate_placements(_tree(tmp_path), _spec())
        assert placements
        assert all(p.scale > 0 for p in placements)

    def test_density_raises_the_count(self, tmp_path):
        path = _tree(tmp_path)
        low = len(simulate_placements(path, _spec(branch_density=5)))
        high = len(simulate_placements(path, _spec(branch_density=40)))
        assert high > low

    def test_the_scale_ramp_changes_scale_but_not_count(self, tmp_path):
        # The heart of the bug: these two exports differ only in instance size,
        # and every count-based instrument reports them as identical.
        path = _tree(tmp_path)
        flat = simulate_placements(path, _spec(scale_ramp=FLAT_RAMP))
        tapered = simulate_placements(path, _spec(scale_ramp=ENGINE_DEFAULT_RAMP))
        assert len(flat) == len(tapered)
        assert sum(p.scale for p in flat) > sum(p.scale for p in tapered)

    def test_base_scale_multiplies_every_instance(self, tmp_path):
        path = _tree(tmp_path)
        one = simulate_placements(path, _spec(base_scale=1.0))
        two = simulate_placements(path, _spec(base_scale=2.0))
        assert len(one) == len(two)
        assert sum(p.scale for p in two) == pytest.approx(
            2.0 * sum(p.scale for p in one)
        )

    def test_relative_start_moves_instances_outward(self, tmp_path):
        # It remaps the placement span; it is not count-neutral against 0.0,
        # because the branch-root sample 0.0 discards is kept.
        path = _tree(tmp_path)
        rooted = simulate_placements(path, _spec(relative_start=0.0))
        outer = simulate_placements(path, _spec(relative_start=0.4))
        assert min(p.along_branch for p in outer) >= 0.4 - 1e-9
        assert len(outer) >= len(rooted)

    def test_plant_spacing_is_refused_by_default(self, tmp_path):
        # Reproduced +32.4 % out; no calibration graph uses it.
        with pytest.raises(ValueError, match="32.4"):
            simulate_placements(_tree(tmp_path), _spec(spacing_basis="PLANT"))

    def test_plant_spacing_can_be_opted_into_knowingly(self, tmp_path):
        placements = simulate_placements(
            _tree(tmp_path), _spec(spacing_basis="PLANT"), allow_plant_spacing=True
        )
        assert isinstance(placements, list)

    def test_a_degenerate_tree_is_refused(self, tmp_path):
        path = tmp_path / "flat.json"
        path.write_text(
            json.dumps(
                {
                    "points": {"positions": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]},
                    "primitives": {
                        "points": [[0, 1]],
                        "attributes": {
                            "branchParentNumber": {"values": [-1]},
                            "branchNumber": {"values": [0]},
                        },
                    },
                }
            )
        )
        with pytest.raises(ValueError, match="degenerate"):
            simulate_placements(path, _spec())


class TestMaskedCount:
    def test_unmasked_is_the_point_count_exactly(self):
        count = expected_instances(437)
        assert (count.expected, count.sd, count.band) == (437, 0.0, 0)

    def test_a_mask_thins_binomially(self):
        # Uniform pick over k real + m mask entries: mean N(1-f), sd sqrt(Nf(1-f)).
        count = expected_instances(437, 3 / 11)
        assert count.expected == round(437 * 8 / 11)
        assert count.sd == pytest.approx((437 * (3 / 11) * (8 / 11)) ** 0.5)
        assert count.band == 19  # ceil(2 sd): what a click should land inside

    def test_rejects_a_full_mask_and_negative_points(self):
        with pytest.raises(ValueError, match="mask_fraction"):
            expected_instances(10, 1.0)
        with pytest.raises(ValueError, match="points"):
            expected_instances(-1)

    def test_leaf_area_reports_the_spawned_count_and_keeps_the_points(self, tmp_path):
        path = _tree(tmp_path)
        plain = measure_leaf_area(path, _spec(scale_ramp=FLAT_RAMP), PROTOTYPE_AREA)
        masked = measure_leaf_area(
            path, _spec(scale_ramp=FLAT_RAMP), PROTOTYPE_AREA, mask_fraction=0.25
        )
        assert masked.points == plain.instances
        assert masked.instances == round(0.75 * plain.instances)
        assert masked.area_m2 == pytest.approx(0.75 * plain.area_m2, abs=PROTOTYPE_AREA)
        assert plain.mask_fraction == 0.0 and masked.mask_fraction == 0.25


class TestLeafArea:
    def test_a_flat_ramp_matches_the_count_based_figure(self, tmp_path):
        measured = measure_leaf_area(
            _tree(tmp_path), _spec(scale_ramp=FLAT_RAMP), PROTOTYPE_AREA
        )
        assert measured.correction_factor == pytest.approx(1.0)
        assert measured.area_m2 == pytest.approx(measured.count_based_area_m2)

    def test_a_tapered_ramp_reports_materially_less(self, tmp_path):
        # Under the engine default the shipped trees carried roughly an eighth
        # of the leaf a count-based measurement credited them with.
        measured = measure_leaf_area(
            _tree(tmp_path), _spec(scale_ramp=ENGINE_DEFAULT_RAMP), PROTOTYPE_AREA
        )
        assert measured.correction_factor < 0.5
        assert measured.area_m2 < 0.5 * measured.count_based_area_m2

    def test_the_two_ramps_agree_on_count_and_disagree_on_area(self, tmp_path):
        path = _tree(tmp_path)
        flat = measure_leaf_area(path, _spec(scale_ramp=FLAT_RAMP), PROTOTYPE_AREA)
        tapered = measure_leaf_area(
            path, _spec(scale_ramp=ENGINE_DEFAULT_RAMP), PROTOTYPE_AREA
        )
        assert flat.instances == tapered.instances
        assert flat.count_based_area_m2 == tapered.count_based_area_m2
        assert tapered.area_m2 < flat.area_m2

    def test_area_goes_as_scale_squared(self, tmp_path):
        path = _tree(tmp_path)
        one = measure_leaf_area(path, _spec(base_scale=1.0), PROTOTYPE_AREA)
        two = measure_leaf_area(path, _spec(base_scale=2.0), PROTOTYPE_AREA)
        assert two.area_m2 == pytest.approx(4.0 * one.area_m2)

    def test_a_ramp_mismatch_raises(self, tmp_path):
        # A measurement taken against a different ramp than the graph carries
        # reproduces the original bug exactly.
        with pytest.raises(ValueError, match="scale ramp mismatch"):
            measure_leaf_area(
                _tree(tmp_path),
                _spec(scale_ramp=FLAT_RAMP),
                PROTOTYPE_AREA,
                graph_scale_ramp=ENGINE_DEFAULT_RAMP,
            )

    def test_a_matching_ramp_passes(self, tmp_path):
        measured = measure_leaf_area(
            _tree(tmp_path),
            _spec(scale_ramp=FLAT_RAMP),
            PROTOTYPE_AREA,
            graph_scale_ramp=FLAT_RAMP,
        )
        assert measured.instances > 0

    def test_the_key_list_and_endpoint_forms_are_the_same_ramp(self, tmp_path):
        measure_leaf_area(
            _tree(tmp_path),
            _spec(scale_ramp=(1.0, 0.1)),
            PROTOTYPE_AREA,
            graph_scale_ramp=((0.0, 1.0), (1.0, 0.1)),
        )

    def test_describe_shows_both_figures(self, tmp_path):
        measured = measure_leaf_area(
            _tree(tmp_path), _spec(scale_ramp=ENGINE_DEFAULT_RAMP), PROTOTYPE_AREA
        )
        text = measured.describe()
        assert "scale^2" in text
        assert "count-based" in text

    def test_the_correction_is_the_mean_of_squared_scales(self):
        measured = LeafAreaMeasurement(
            instances=100,
            mean_scale=0.3,
            mean_scale_squared=0.09,
            prototype_leaf_area_m2=0.02,
        )
        assert measured.count_based_area_m2 == pytest.approx(2.0)
        assert measured.area_m2 == pytest.approx(0.18)
        assert measured.correction_factor == 0.09


@pytest.mark.skipif(
    not REAL_JSONS.is_dir(), reason="calibration growth JSONs are gitignored scratch"
)
class TestAgainstLoggedCounts:
    """The model's own validation: does it reproduce what the editor logged?

    A loop that lands the instance count to within one instance across 281 to
    11,587 instances is trustworthy for the scale distribution it produces
    along the way.
    """

    @pytest.mark.parametrize("name,density,logged", LOGGED_CASES)
    def test_it_reproduces_the_logged_instance_count(self, name, density, logged):
        path = REAL_JSONS / name
        if not path.is_file():
            pytest.skip(f"{name} not present")
        predicted = len(
            simulate_placements(
                path, _spec(branch_density=density, scale_ramp=ENGINE_DEFAULT_RAMP)
            )
        )
        assert abs(predicted - logged) <= 1, f"{name}: {predicted} vs {logged}"

    def test_the_shipped_ramp_costs_nothing_and_the_default_costs_everything(self):
        path = REAL_JSONS / "beech_r20_h15m_f006.json"
        if not path.is_file():
            pytest.skip("beech r20_h15m not present")
        flat = measure_leaf_area(
            path,
            _spec(branch_density=95, relative_start=0.4, scale_ramp=FLAT_RAMP),
            PROTOTYPE_AREA,
        )
        tapered = measure_leaf_area(
            path,
            _spec(
                branch_density=95,
                relative_start=0.4,
                scale_ramp=ENGINE_DEFAULT_RAMP,
            ),
            PROTOTYPE_AREA,
        )
        assert flat.correction_factor == pytest.approx(1.0)
        # The measured range across the shipped set was 0.087 to 0.141.
        assert 0.08 < tapered.correction_factor < 0.15


class TestCli:
    """growpy-pve-leaf-area: the runnable form of the measurement."""

    def _stub_jsons(self, tmp_path: Path) -> Path:
        """Synthetic growth JSONs under the names the calibration records."""
        from growpy.config.pve_calibration import load_pve_calibration

        source = _tree(tmp_path)
        directory = tmp_path / "growthjson"
        directory.mkdir()
        calibration = load_pve_calibration()
        for species in calibration.species.values():
            for tree in species.trees.values():
                (directory / tree.growth_json).write_bytes(source.read_bytes())
        return directory

    def test_it_measures_every_calibrated_tree(self, tmp_path, capsys):
        from growpy.tools.pve_leaf_area import main

        rc = main(["--growth-json-dir", str(self._stub_jsons(tmp_path))])
        assert rc == 0
        out = capsys.readouterr().out
        assert "TOTAL" in out
        assert "european_beech" in out
        assert "silver_fir" in out

    def test_the_shipped_flat_ramp_reports_a_factor_of_one(self, tmp_path, capsys):
        from growpy.tools.pve_leaf_area import main

        main(["--growth-json-dir", str(self._stub_jsons(tmp_path))])
        rows = [
            line for line in capsys.readouterr().out.splitlines()
            if line.startswith("european_beech")
        ]
        assert rows
        assert all("1.0000" in row for row in rows)

    def test_a_tapered_ramp_is_called_out(self, tmp_path, capsys):
        from growpy.tools.pve_leaf_area import main

        main([
            "--growth-json-dir", str(self._stub_jsons(tmp_path)),
            "--scale-ramp", "1.0", "0.1",
        ])
        out = capsys.readouterr().out
        assert "is not flat" in out
        assert "count-based" in out

    def test_a_missing_growth_json_is_reported_not_skipped_silently(
        self, tmp_path, capsys
    ):
        from growpy.tools.pve_leaf_area import main

        directory = self._stub_jsons(tmp_path)
        next(iter(sorted(directory.glob("*.json")))).unlink()
        rc = main(["--growth-json-dir", str(directory)])
        assert rc == 2

    def test_nothing_measurable_fails(self, tmp_path):
        from growpy.tools.pve_leaf_area import main

        empty = tmp_path / "empty"
        empty.mkdir()
        assert main(["--growth-json-dir", str(empty)]) == 1
