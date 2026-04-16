"""Tests for growpy.utils.plotting growth curve plot functions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from growpy.utils.plotting import _display_name, _extract_common


class TestExtractCommon:
    """Tests for common data extraction from metadata."""

    def test_basic_extraction(self):
        meta = {"flushes_per_year": 2.0}
        heights = [0.5, 1.0, 2.0, 3.5]
        dbhs = [0.01, 0.02, 0.04, 0.06]
        fpy, ages, h, d = _extract_common(meta, heights, dbhs)
        assert fpy == 2.0
        assert len(ages) == 4
        assert ages[0] == pytest.approx(0.5)  # (0+1)/2.0
        assert ages[1] == pytest.approx(1.0)
        np.testing.assert_allclose(h, heights)
        np.testing.assert_allclose(d, np.array(dbhs) * 100)

    def test_default_fpy(self):
        meta = {}
        fpy, ages, h, d = _extract_common(meta, [1.0], [0.01])
        assert fpy == 1.0
        assert ages[0] == pytest.approx(1.0)


class TestDisplayName:
    """Tests for species display name formatting."""

    def test_basic(self):
        assert _display_name("norway_spruce") == "Norway Spruce"

    def test_single_word(self):
        assert _display_name("oak") == "Oak"

    def test_three_words(self):
        assert _display_name("pacific_silver_fir") == "Pacific Silver Fir"
