"""Tests for the milestone ceiling and shortfall reporting.

The ceiling must come from the authored tree_asset_lookup.csv Max Height, not
from a simulated growth model. Deriving it from the model produced the wrong
stage count for 10 of 11 dataset species: growth models are bounded by
[growth_models] max_height (20 m), so their Chapman-Richards asymptotes either
pinned at the 5x guard and fell back to ~20 m, or ran away from the authored
value entirely.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from growpy.pipelines.forest_stages import (
    _load_species_max_heights,
    _warn_uncaptured_milestones,
)


class TestLoadSpeciesMaxHeights:
    def _row(self, max_height):
        return pd.Series({"Common Name": "Douglas fir", "Max Height": max_height})

    def test_uses_authored_max_height(self):
        with patch(
            "growpy.config.paths._find_species_row", return_value=self._row(45.0)
        ):
            assert _load_species_max_heights(["Douglas fir"]) == {"Douglas fir": 45.0}

    def test_ignores_growth_model_asymptote(self, tmp_path):
        """The simulated asymptote must not override the authored value.

        Scots pine's model fitted A=55m for a species authored at 30m, which
        would emit 11 stages instead of 6.
        """
        row = pd.Series({"Common Name": "Scots pine", "Max Height": 30.0})
        with patch("growpy.config.paths._find_species_row", return_value=row):
            assert _load_species_max_heights(["Scots pine"])["Scots pine"] == 30.0

    def test_unknown_species_omitted(self):
        with patch(
            "growpy.config.paths._find_species_row", side_effect=ValueError("nope")
        ):
            assert _load_species_max_heights(["Nonexistent"]) == {}

    def test_missing_max_height_omitted(self):
        with patch(
            "growpy.config.paths._find_species_row", return_value=self._row(None)
        ):
            assert _load_species_max_heights(["Douglas fir"]) == {}

    def test_nan_max_height_omitted(self):
        row = self._row(float("nan"))
        with patch("growpy.config.paths._find_species_row", return_value=row):
            assert _load_species_max_heights(["Douglas fir"]) == {}


def _milestones(species, heights):
    """Build a milestone_map with one tree capturing the given heights."""
    return {i: {species: {0: h}} for i, h in enumerate(heights, start=1)}


class TestWarnUncapturedMilestones:
    def test_warns_when_short_of_ceiling(self, caplog):
        mmap = _milestones("Douglas fir", [5.0, 10.0, 15.0])
        with caplog.at_level("WARNING"):
            _warn_uncaptured_milestones(mmap, {"Douglas fir": 25.0}, 5.0, 140)
        assert "Douglas fir" in caplog.text
        assert "2 stage(s) missing" in caplog.text
        assert "20m" in caplog.text and "25m" in caplog.text
        assert "growth_cycle_limit" in caplog.text

    def test_silent_when_all_captured(self, caplog):
        mmap = _milestones("European oak", [5.0, 10.0, 15.0])
        with caplog.at_level("WARNING"):
            _warn_uncaptured_milestones(mmap, {"European oak": 15.0}, 5.0, 140)
        assert caplog.text == ""

    def test_no_ceilings_is_silent(self, caplog):
        with caplog.at_level("WARNING"):
            _warn_uncaptured_milestones({}, {}, 5.0, 140)
        assert caplog.text == ""

    def test_reports_species_that_captured_nothing(self, caplog):
        with caplog.at_level("WARNING"):
            _warn_uncaptured_milestones({}, {"Silver fir": 10.0}, 5.0, 140)
        assert "Silver fir" in caplog.text
        assert "2 stage(s) missing" in caplog.text

    @pytest.mark.parametrize(
        "ceiling,expected_stages", [(30.0, 6), (35.0, 7), (45.0, 9), (25.0, 5)]
    )
    def test_stage_count_matches_ceiling(self, ceiling, expected_stages, caplog):
        """Stage count is ceiling / interval -- the dataset spec's own arithmetic."""
        with caplog.at_level("WARNING"):
            _warn_uncaptured_milestones({}, {"X": ceiling}, 5.0, 140)
        assert f"{expected_stages} stage(s) missing" in caplog.text
