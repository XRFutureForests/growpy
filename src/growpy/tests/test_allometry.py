"""Tests for height-DBH allometry: fitting, artifacts, and the low-end blend."""

import json

import numpy as np
import pytest

from growpy.utils import allometry
from growpy.utils.allometry import (
    BLEND_FLOOR_FRAC,
    _smoothstep,
    correction_weight,
    get_height_dbh_model,
    load_species_allometry,
    write_species_allometry,
)
from growpy.utils.yield_tables import MIN_FIT_DBH_M, fit_height_dbh_model


def _power_table(a, b, heights):
    """Exact DBH values for a known power model."""
    return [a * (h**b) for h in heights]


class TestFitHeightDbhModel:
    """fit_height_dbh_model recovers power models and weights small trees fairly."""

    def test_recovers_exact_power_model(self):
        heights = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]
        dbhs = _power_table(0.002, 1.6, heights)
        model = fit_height_dbh_model(heights, dbhs)
        assert model["a"] == pytest.approx(0.002, rel=1e-3)
        assert model["b"] == pytest.approx(1.6, rel=1e-3)
        assert model["max_rel_err"] < 1e-6

    def test_too_few_points_returns_none(self):
        assert fit_height_dbh_model([10.0, 20.0], [0.1, 0.2]) is None

    def test_drops_rows_below_dbh_floor(self):
        # A near-zero DBH row (stand just reaching breast height) would dominate
        # a log-space fit; it must be excluded.
        heights = [4.0, 10.0, 15.0, 20.0, 25.0, 30.0]
        dbhs = [0.003] + _power_table(0.002, 1.6, heights[1:])
        model = fit_height_dbh_model(heights, dbhs)
        assert model["n_points"] == 5
        assert model["b"] == pytest.approx(1.6, rel=1e-3)

    def test_small_trees_not_systematically_underestimated(self):
        """Relative error must stay bounded across the whole range.

        Fitting raw residuals lets large-diameter rows dominate and
        underestimates saplings; the log-space fit must not.
        """
        heights = [6.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0]
        dbhs = _power_table(0.0015, 1.75, heights)
        # perturb the largest stems so an absolute-residual fit would chase them
        dbhs[-1] *= 1.08
        dbhs[-2] *= 1.05

        model = fit_height_dbh_model(heights, dbhs)
        pred = np.array([model["a"] * (h ** model["b"]) for h in heights])
        rel = np.abs(pred - np.array(dbhs)) / np.array(dbhs)

        assert rel.max() < 0.10
        # the smallest tree must be fitted about as well as the largest
        assert rel[0] < 0.10

    def test_min_dbh_floor_is_one_centimetre(self):
        assert MIN_FIT_DBH_M == pytest.approx(0.01)


class TestSmoothstep:
    def test_endpoints(self):
        assert _smoothstep(0.0) == 0.0
        assert _smoothstep(1.0) == 1.0

    def test_midpoint(self):
        assert _smoothstep(0.5) == pytest.approx(0.5)

    def test_clamps_out_of_range(self):
        assert _smoothstep(-2.0) == 0.0
        assert _smoothstep(5.0) == 1.0


class TestCorrectionWeight:
    """Below the fitted range the allometric correction fades toward Grove."""

    @pytest.fixture
    def fitted(self, monkeypatch):
        record = {
            "species": "test_species",
            "height_dbh_model": {"a": 0.002, "b": 1.6},
            "height_range_m": [10.0, 30.0],
        }
        monkeypatch.setattr(
            allometry, "load_species_allometry", lambda species: record
        )
        return record

    def test_full_weight_inside_range(self, fitted):
        assert correction_weight("test_species", 10.0) == 1.0
        assert correction_weight("test_species", 25.0) == 1.0

    def test_full_weight_above_range(self, fitted):
        # Above the fitted range the power law still behaves; only the low end
        # is faded out.
        assert correction_weight("test_species", 40.0) == 1.0

    def test_zero_weight_far_below_range(self, fitted):
        floor = 10.0 * BLEND_FLOOR_FRAC
        assert correction_weight("test_species", floor) == 0.0
        assert correction_weight("test_species", floor - 1.0) == 0.0

    def test_partial_weight_in_blend_band(self, fitted):
        w = correction_weight("test_species", 7.5)  # midway between 5 and 10
        assert w == pytest.approx(0.5)

    def test_monotonic_across_band(self, fitted):
        heights = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        weights = [correction_weight("test_species", h) for h in heights]
        assert weights == sorted(weights)

    def test_missing_artifact_gives_full_weight(self, monkeypatch):
        monkeypatch.setattr(allometry, "load_species_allometry", lambda species: None)
        assert correction_weight("unknown", 3.0) == 1.0


class TestArtifactRoundTrip:
    def test_write_then_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(allometry, "get_allometry_dir", lambda: tmp_path)
        record = {
            "species": "european_beech",
            "height_dbh_model": {"a": 0.0008, "b": 1.8},
            "height_range_m": [6.0, 35.0],
        }
        path = write_species_allometry(record)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["species"] == "european_beech"
        assert load_species_allometry("european_beech") == record

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(allometry, "get_allometry_dir", lambda: tmp_path)
        assert load_species_allometry("nonexistent") is None


class TestGetHeightDbhModel:
    """The artifact wins; seed.json calibration is only a migration fallback."""

    def test_prefers_artifact_over_preset(self, tmp_path, monkeypatch):
        monkeypatch.setattr(allometry, "get_allometry_dir", lambda: tmp_path)
        write_species_allometry(
            {
                "species": "european_oak",
                "height_dbh_model": {"a": 0.0015, "b": 1.72},
                "height_range_m": [7.0, 29.0],
            }
        )
        preset = tmp_path / "european_oak.seed.json"
        preset.write_text(
            json.dumps(
                {"_yield_table_calibration": {"height_dbh_model": {"a": 9.9, "b": 9.9}}}
            )
        )
        model = get_height_dbh_model("european_oak", preset)
        assert model["a"] == pytest.approx(0.0015)

    def test_falls_back_to_preset(self, tmp_path, monkeypatch):
        monkeypatch.setattr(allometry, "get_allometry_dir", lambda: tmp_path)
        preset = tmp_path / "european_oak.seed.json"
        preset.write_text(
            json.dumps(
                {
                    "_yield_table_calibration": {
                        "height_dbh_model": {"a": 0.003, "b": 1.5}
                    }
                }
            )
        )
        model = get_height_dbh_model("european_oak", preset)
        assert model["a"] == pytest.approx(0.003)

    def test_returns_none_without_either(self, tmp_path, monkeypatch):
        monkeypatch.setattr(allometry, "get_allometry_dir", lambda: tmp_path)
        assert get_height_dbh_model("european_oak") is None
