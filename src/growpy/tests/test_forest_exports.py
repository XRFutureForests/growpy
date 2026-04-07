"""Tests for growpy.pipelines.forest_exports constants."""

from growpy.pipelines.forest_exports import GROWTH_CYCLE_LIMIT, SMOOTH_ITERATIONS


class TestForestExportsConstants:
    """Tests for pipeline constants."""

    def test_growth_cycle_limit(self):
        assert isinstance(GROWTH_CYCLE_LIMIT, int)
        assert GROWTH_CYCLE_LIMIT > 0

    def test_smooth_iterations(self):
        assert isinstance(SMOOTH_ITERATIONS, int)
        assert SMOOTH_ITERATIONS >= 0
