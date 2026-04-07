"""Tests for Chapman-Richards growth model and fit utility."""

import json
from pathlib import Path

import joblib
import numpy as np
import pytest

from growpy.utils.analysis import (
    ChapmanRichardsModel,
    PiecewiseLinearModel,
    SimpleLinearModel,
    _chapman_richards,
    _chapman_richards_with_baseline,
    fit_chapman_richards,
)


# --- Synthetic data generators ---


def _make_cr_data(A=30.0, k=0.04, p=1.8, n=75, noise=0.0):
    """Generate synthetic Chapman-Richards height curve."""
    cycles = np.arange(n)
    heights = A * (1.0 - np.exp(-k * cycles)) ** p
    if noise > 0:
        rng = np.random.default_rng(42)
        heights += rng.normal(0, noise, len(heights))
        heights = np.maximum(heights, 0.0)
    return cycles, heights


# --- fit_chapman_richards tests ---


class TestFitChapmanRichards:

    def test_recovers_known_parameters(self):
        cycles, heights = _make_cr_data(A=30.0, k=0.04, p=1.8)
        A, k, p, r_sq = fit_chapman_richards(cycles, heights)
        assert abs(A - 30.0) < 2.0
        assert abs(k - 0.04) < 0.01
        assert abs(p - 1.8) < 0.5
        assert r_sq > 0.99

    def test_noisy_data_still_fits(self):
        cycles, heights = _make_cr_data(noise=0.3)
        A, k, p, r_sq = fit_chapman_richards(cycles, heights)
        assert r_sq > 0.95

    def test_with_baseline(self):
        cycles = np.arange(75)
        y0 = 0.5
        A_true, k_true, p_true = 35.0, 0.03, 2.0
        heights = y0 + (A_true - y0) * (1.0 - np.exp(-k_true * cycles)) ** p_true
        A, k, p, r_sq = fit_chapman_richards(cycles, heights, y0=y0)
        assert r_sq > 0.99
        assert A > max(heights) * 0.95

    def test_too_few_points_raises(self):
        with pytest.raises(RuntimeError, match="Need >= 4"):
            fit_chapman_richards(np.array([1, 2, 3]), np.array([1, 2, 3]))

    def test_all_zeros_raises(self):
        with pytest.raises(RuntimeError, match="<= 0"):
            fit_chapman_richards(np.arange(10), np.zeros(10))

    def test_dbh_like_data(self):
        """DBH curves start at 0, may be less sigmoidal."""
        cycles = np.arange(75)
        A_true, k_true, p_true = 0.5, 0.02, 1.2
        dbhs = A_true * (1.0 - np.exp(-k_true * cycles)) ** p_true
        A, k, p, r_sq = fit_chapman_richards(cycles, dbhs)
        assert r_sq > 0.99


# --- ChapmanRichardsModel tests ---


class TestChapmanRichardsModel:

    def test_fit_and_predict_roundtrip(self):
        """Forward then inverse should approximately round-trip."""
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        # Pick some heights within range
        test_heights = np.array([5.0, 10.0, 15.0, 20.0])
        predicted_cycles = model.predict(test_heights)
        reconstructed_heights = model.forward(predicted_cycles)
        np.testing.assert_allclose(reconstructed_heights, test_heights, atol=0.5)

    def test_predict_interface_compatible(self):
        """model.predict([[15.0]])[0] must return a float."""
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        result = model.predict([[15.0]])
        assert isinstance(result, np.ndarray)
        val = float(result[0])
        assert val > 0

    def test_predict_zero_height(self):
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)
        assert model.predict([0.0])[0] == 0.0

    def test_extrapolation_beyond_asymptote(self):
        """Heights >= A should extrapolate linearly, not crash."""
        cycles, heights = _make_cr_data(A=30.0)
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        # Ask for a height well beyond asymptote
        result = model.predict([35.0])
        assert np.isfinite(result[0])
        assert result[0] > model.predict([25.0])[0]

    def test_extrapolation_monotonic(self):
        """Predicted cycles should increase monotonically with height."""
        cycles, heights = _make_cr_data(A=30.0)
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        test_heights = np.linspace(1.0, 40.0, 50)
        predicted = model.predict(test_heights)
        assert np.all(np.diff(predicted) > 0)

    def test_forward_matches_data(self):
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)
        predicted_heights = model.forward(cycles)
        np.testing.assert_allclose(predicted_heights, heights, atol=0.5)

    def test_r_squared_stored(self):
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)
        assert model.r_squared is not None
        assert model.r_squared > 0.95

    def test_to_dict_from_dict_roundtrip(self):
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        d = model.to_dict()
        assert d["model_type"] == "chapman_richards"

        restored = ChapmanRichardsModel.from_dict(d)
        assert restored.A == model.A
        assert restored.k == model.k
        assert restored.p == model.p

        test_h = np.array([5.0, 15.0, 25.0])
        np.testing.assert_allclose(
            model.predict(test_h), restored.predict(test_h), atol=1e-6
        )

    def test_serialization_with_joblib(self, tmp_path):
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        pkl_path = tmp_path / "model.pkl"
        joblib.dump(model, pkl_path)
        loaded = joblib.load(pkl_path)

        test_h = np.array([10.0, 20.0])
        np.testing.assert_allclose(
            model.predict(test_h), loaded.predict(test_h), atol=1e-6
        )

    def test_json_params_saved(self, tmp_path):
        """Verify to_dict produces valid JSON."""
        cycles, heights = _make_cr_data()
        model = ChapmanRichardsModel()
        model.fit(heights, cycles)

        params_path = tmp_path / "params.json"
        with open(params_path, "w") as f:
            json.dump(model.to_dict(), f)

        with open(params_path) as f:
            loaded = json.load(f)
        assert loaded["A"] == model.A
        assert loaded["k"] == model.k


# --- Backward compatibility ---


class TestBackwardCompatibility:

    def test_piecewise_linear_still_works(self):
        model = PiecewiseLinearModel()
        model.fit(np.array([1.0, 5.0, 10.0, 15.0]), np.array([0, 10, 30, 60]))
        result = model.predict([[7.5]])
        assert result[0] > 0

    def test_simple_linear_alias(self):
        assert SimpleLinearModel is PiecewiseLinearModel

    def test_old_pkl_still_loads(self, tmp_path):
        """Simulate loading a PiecewiseLinearModel from an old pkl."""
        model = PiecewiseLinearModel()
        model.fit(np.array([1.0, 5.0, 10.0]), np.array([0, 20, 50]))
        pkl_path = tmp_path / "old_model.pkl"
        joblib.dump(model, pkl_path)

        loaded = joblib.load(pkl_path)
        assert isinstance(loaded, PiecewiseLinearModel)
        assert loaded.predict([[7.5]])[0] > 0


# --- Yield-table-like data ---


class TestFitYieldTableData:
    """Test Chapman-Richards on realistic yield table shapes."""

    def test_spruce_like_height_curve(self):
        """Norway spruce: rapid early growth, plateaus around 35m."""
        ages = np.array([0, 10, 20, 30, 40, 50, 60, 80, 100, 120])
        heights = np.array([0.5, 4.0, 11.0, 18.0, 23.0, 27.0, 29.5, 32.0, 33.5, 34.0])
        A, k, p, r_sq = fit_chapman_richards(ages, heights, y0=0.5)
        assert r_sq > 0.99
        # Extrapolation: height at age 150 should be below A and above 34
        h_150 = 0.5 + (A - 0.5) * (1.0 - np.exp(-k * 150)) ** p
        assert 34.0 < h_150 < A

    def test_beech_like_height_curve(self):
        """European beech: slower growth, max around 32m."""
        ages = np.array([0, 10, 20, 30, 40, 50, 60, 80, 100, 120])
        heights = np.array([0.5, 2.5, 7.0, 13.0, 18.0, 22.0, 25.0, 28.0, 30.0, 31.0])
        A, k, p, r_sq = fit_chapman_richards(ages, heights, y0=0.5)
        assert r_sq > 0.99

    def test_dbh_curve(self):
        """DBH curve: starts at 0, quasi-linear then saturating."""
        ages = np.array([0, 10, 20, 30, 40, 50, 60, 80, 100, 120])
        dbhs = np.array([0.0, 0.03, 0.08, 0.14, 0.19, 0.24, 0.28, 0.34, 0.38, 0.40])
        A, k, p, r_sq = fit_chapman_richards(ages, dbhs, y0=0.0)
        assert r_sq > 0.99
