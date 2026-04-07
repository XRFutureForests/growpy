"""Tests for growpy.utils.plotting growth curve plot functions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from growpy.utils.plotting import SEED_COLORS, _extract_common, _seed_envelope


class TestExtractCommon:
    """Tests for common data extraction from metadata."""

    def test_basic_extraction(self):
        meta = {"flushes_per_year": 2.0}
        heights = [0.5, 1.0, 2.0, 3.5]
        dbhs = [0.01, 0.02, 0.04, 0.06]
        fpy, ages, h, d, ind_h, ind_d, seeds = _extract_common(meta, heights, dbhs)
        assert fpy == 2.0
        assert len(ages) == 4
        assert ages[0] == pytest.approx(0.5)  # (0+1)/2.0
        assert ages[1] == pytest.approx(1.0)
        np.testing.assert_allclose(h, heights)
        np.testing.assert_allclose(d, np.array(dbhs) * 100)

    def test_default_fpy(self):
        meta = {}
        fpy, ages, h, d, ind_h, ind_d, seeds = _extract_common(meta, [1.0], [0.01])
        assert fpy == 1.0
        assert ages[0] == pytest.approx(1.0)

    def test_individual_curves_returned(self):
        meta = {
            "flushes_per_year": 1.0,
            "individual_height_curves": [[1, 2], [1.5, 2.5]],
            "individual_dbh_curves": [[0.01, 0.02]],
            "seeds_tested": [42, 99],
        }
        fpy, ages, h, d, ind_h, ind_d, seeds = _extract_common(meta, [1.0, 2.0], [0.01, 0.02])
        assert len(ind_h) == 2
        assert len(ind_d) == 1
        assert seeds == [42, 99]


class TestSeedEnvelope:
    """Tests for seed curve min/max envelope."""

    def test_returns_none_for_single_curve(self):
        lo, hi = _seed_envelope([[1.0, 2.0, 3.0]])
        assert lo is None
        assert hi is None

    def test_returns_none_for_empty(self):
        lo, hi = _seed_envelope([])
        assert lo is None
        assert hi is None

    def test_two_curves(self):
        curves = [[1.0, 2.0, 3.0], [1.5, 1.8, 3.5]]
        lo, hi = _seed_envelope(curves)
        np.testing.assert_allclose(lo, [1.0, 1.8, 3.0])
        np.testing.assert_allclose(hi, [1.5, 2.0, 3.5])

    def test_unequal_lengths_padded(self):
        curves = [[1.0, 2.0], [1.0, 2.0, 3.0]]
        lo, hi = _seed_envelope(curves)
        assert len(lo) == 3
        assert len(hi) == 3

    def test_scale_factor(self):
        curves = [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]]
        lo, hi = _seed_envelope(curves, scale=100.0)
        np.testing.assert_allclose(lo, [100.0, 200.0, 300.0])
        np.testing.assert_allclose(hi, [200.0, 400.0, 600.0])

    def test_identical_curves(self):
        curves = [[5.0, 10.0], [5.0, 10.0]]
        lo, hi = _seed_envelope(curves)
        np.testing.assert_allclose(lo, hi)

    def test_three_curves(self):
        curves = [[1.0, 2.0], [0.5, 3.0], [1.5, 2.5]]
        lo, hi = _seed_envelope(curves)
        np.testing.assert_allclose(lo, [0.5, 2.0])
        np.testing.assert_allclose(hi, [1.5, 3.0])


class TestSeedColors:
    """Tests for SEED_COLORS constant."""

    def test_has_at_least_5_colors(self):
        assert len(SEED_COLORS) >= 5

    def test_all_strings(self):
        assert all(isinstance(c, str) for c in SEED_COLORS)
        assert len(lo) == 3
        assert len(hi) == 3

    def test_scale_factor(self):
        curves = [[1.0, 2.0], [1.5, 2.5]]
        lo, hi = _seed_envelope(curves, scale=100.0)
        np.testing.assert_allclose(lo, [100.0, 200.0])
        np.testing.assert_allclose(hi, [150.0, 250.0])


class TestSeedColors:
    """Tests for color palette constant."""

    def test_has_multiple_colors(self):
        assert len(SEED_COLORS) >= 5

    def test_all_strings(self):
        for c in SEED_COLORS:
            assert isinstance(c, str)
